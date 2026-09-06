#!/usr/bin/env python3
"""Look up stakeholders from Jira reporter email via Snowflake dim_workers."""

import os
import json

try:
    import snowflake.connector
    HAS_SNOWFLAKE = True
except ImportError:
    HAS_SNOWFLAKE = False

from config import load_settings

DIRECTOR_LEVELS = {"D", "Director", "Senior Director", "VP", "Vice President",
                   "Senior Vice President", "Executive Vice President",
                   "CFO", "CEO", "CLO"}

CACHE_PATH = os.path.join(os.path.dirname(__file__), "stakeholder_cache.json")


def _get_snowflake_connection():
    """Get a Snowflake connection using default connection config."""
    return snowflake.connector.connect(
        connection_name="default",
    )


def build_stakeholder_cache(reporter_emails: list[str]) -> dict:
    """Query dim_workers for reporter org details. Returns {email: stakeholder_info}."""
    if not reporter_emails:
        return {}

    conn = _get_snowflake_connection()
    try:
        cur = conn.cursor()
        placeholders = ",".join(["%s"] * len(reporter_emails))
        query = f"""
            SELECT
                w.primary_email_address,
                w.preferred_name,
                w.department_description,
                w.supervisory_organization,
                w.management_level_abbreviated,
                w.management_level_reference,
                w.manager_1,
                w.manager_2,
                w.manager_3,
                w.manager_4,
                w.manager_5,
                -- Look up manager_1 details
                m1.primary_email_address AS manager_1_email,
                m1.management_level_abbreviated AS manager_1_level,
                m1.management_level_reference AS manager_1_level_ref,
                -- Look up manager_2 details
                m2.primary_email_address AS manager_2_email,
                m2.management_level_abbreviated AS manager_2_level,
                m2.management_level_reference AS manager_2_level_ref,
                -- Look up manager_3 details
                m3.primary_email_address AS manager_3_email,
                m3.management_level_abbreviated AS manager_3_level,
                m3.management_level_reference AS manager_3_level_ref
            FROM gold_prod.marts.dim_workers w
            LEFT JOIN gold_prod.marts.dim_workers m1
                ON m1.preferred_name = w.manager_1 AND m1.is_latest = TRUE AND m1.is_active = TRUE
            LEFT JOIN gold_prod.marts.dim_workers m2
                ON m2.preferred_name = w.manager_2 AND m2.is_latest = TRUE AND m2.is_active = TRUE
            LEFT JOIN gold_prod.marts.dim_workers m3
                ON m3.preferred_name = w.manager_3 AND m3.is_latest = TRUE AND m3.is_active = TRUE
            WHERE w.is_latest = TRUE
              AND w.is_active = TRUE
              AND w.primary_email_address IN ({placeholders})
        """
        cur.execute(query, reporter_emails)
        columns = [desc[0].lower() for desc in cur.description]
        rows = cur.fetchall()
    finally:
        conn.close()

    cache = {}
    for row in rows:
        record = dict(zip(columns, row))
        email = record["primary_email_address"]

        # Find the first Director+ in the management chain
        stakeholder = _find_director_stakeholder(record)

        cache[email] = {
            "reporter_name": record["preferred_name"],
            "department": record["department_description"],
            "supervisory_org": record["supervisory_organization"],
            "reporter_level": record["management_level_abbreviated"],
            "stakeholder_name": stakeholder["name"],
            "stakeholder_email": stakeholder["email"],
            "stakeholder_level": stakeholder["level"],
            "stakeholder_source": stakeholder["source"],
        }

    return cache


def _find_director_stakeholder(record: dict) -> dict:
    """Walk up the management chain to find the first Director+ person."""
    # Check if the reporter themselves is Director+
    if record.get("management_level_abbreviated") in DIRECTOR_LEVELS or \
       record.get("management_level_reference") in DIRECTOR_LEVELS:
        return {
            "name": record["preferred_name"],
            "email": record["primary_email_address"],
            "level": record.get("management_level_reference", record.get("management_level_abbreviated", "")),
            "source": "reporter_is_director",
        }

    # Walk manager chain
    for i in range(1, 4):  # manager_1 through manager_3
        mgr_name = record.get(f"manager_{i}")
        mgr_email = record.get(f"manager_{i}_email")
        mgr_level = record.get(f"manager_{i}_level")
        mgr_level_ref = record.get(f"manager_{i}_level_ref")

        if not mgr_name:
            continue

        if mgr_level in DIRECTOR_LEVELS or mgr_level_ref in DIRECTOR_LEVELS:
            return {
                "name": mgr_name,
                "email": mgr_email or "",
                "level": mgr_level_ref or mgr_level or "",
                "source": f"manager_{i}",
            }

    # Fallback: use the highest manager we have
    for i in range(3, 0, -1):
        mgr_name = record.get(f"manager_{i}")
        mgr_email = record.get(f"manager_{i}_email")
        if mgr_name:
            return {
                "name": mgr_name,
                "email": mgr_email or "",
                "level": record.get(f"manager_{i}_level_ref", ""),
                "source": f"manager_{i}_fallback",
            }

    return {"name": "", "email": "", "level": "", "source": "not_found"}


def save_cache(cache: dict):
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, default=str)
    print(f"Stakeholder cache saved: {CACHE_PATH} ({len(cache)} entries)")


def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def lookup_stakeholder(email: str, cache: dict = None) -> dict:
    """Look up stakeholder for a single email. Uses cache if available."""
    if cache is None:
        cache = load_cache()
    return cache.get(email, {"stakeholder_name": "", "stakeholder_email": "", "source": "not_in_cache"})


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python stakeholder_lookup.py <email1> [email2] ...")
        print("       python stakeholder_lookup.py --from-jql 'project = DNA AND ...'")
        sys.exit(1)

    if sys.argv[1] == "--from-jql":
        from jira_client import JiraClient
        settings = load_settings()
        jira = JiraClient(settings.jira_base_url, settings.jira_pat)
        jql = " ".join(sys.argv[2:])
        print(f"Fetching reporters from: {jql}")
        issues = jira.search_all(jql, fields=["reporter"])
        emails = list(set(
            i["fields"]["reporter"]["emailAddress"]
            for i in issues
            if i.get("fields", {}).get("reporter", {}).get("emailAddress")
        ))
        print(f"Found {len(emails)} unique reporter emails")
    else:
        emails = sys.argv[1:]

    print(f"Looking up {len(emails)} emails in dim_workers...")
    cache = build_stakeholder_cache(emails)

    for email, info in sorted(cache.items()):
        print(f"\n  {email}:")
        print(f"    Reporter: {info['reporter_name']} ({info['reporter_level']}) - {info['department']}")
        print(f"    Stakeholder: {info['stakeholder_name']} ({info['stakeholder_level']}) via {info['stakeholder_source']}")

    save_cache(cache)
