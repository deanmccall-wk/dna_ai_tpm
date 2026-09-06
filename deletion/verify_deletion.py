#!/usr/bin/env python3
"""Automated data deletion verification against Snowflake and Redshift.

Extracts the org_id from a Jira ticket, runs redaction and Salesforce
verification queries against both databases, and optionally posts results
to Jira and closes the ticket.

Usage:
    python verify_deletion.py DATA-2439                    # Print results
    python verify_deletion.py DATA-2439 --post             # Post to Jira
    python verify_deletion.py DATA-2439 --post --close     # Post + close
    python verify_deletion.py DATA-2439 --snowflake-only   # Skip Redshift
    python verify_deletion.py DATA-2439 --redshift-only    # Skip Snowflake
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone

from clients.config import load_settings
from clients.jira_client import JiraClient


# ---------------------------------------------------------------------------
# Queries — Redshift (original schema paths from Deepika's process)
# ---------------------------------------------------------------------------

REDSHIFT_REDACTION_QUERIES = {
    "audit.workiva_workspace": (
        "SELECT * FROM audit.workiva_workspace WHERE organization_id = %s"
    ),
    "workiva.organization": (
        "SELECT * FROM workiva.organization WHERE organization_id = %s"
    ),
    "audit.wdesk_classic_account": (
        "SELECT * FROM audit.wdesk_classic_account WHERE organization_id = %s"
    ),
}

REDSHIFT_SF_QUERY = """
SELECT DISTINCT swa.id AS sf_account_id
FROM admin.workiva_org_deletes d
LEFT JOIN public.workiva_workspace ww
  ON ww.organization_id = d.organization_id
LEFT JOIN admin.salesforce_wdesk_classic_account swa
  ON swa.account_resource_id = ww.account_resource_id
WHERE d.organization_id = %s
"""

# ---------------------------------------------------------------------------
# Queries — Snowflake (SILVER_PROD equivalents of Redshift tables)
# ---------------------------------------------------------------------------

SNOWFLAKE_REDACTION_QUERIES = {
    "SILVER_PROD.ADMIN.STG_WORKIVA_WORKSPACE": (
        "SELECT WORKSPACE_ID, WORKSPACE_NAME, DELETED_FLAG, DELETED_TIMESTAMP, ACTIVE_FLAG "
        "FROM SILVER_PROD.ADMIN.STG_WORKIVA_WORKSPACE "
        "WHERE ORGANIZATION_ID = %s"
    ),
    "COMMON.WORKIVA_ORGANIZATION_ENVIRONMENT": (
        "SELECT * FROM SILVER_PROD.COMMON.WORKIVA_ORGANIZATION_ENVIRONMENT "
        "WHERE ORGANIZATION_ID = %s"
    ),
    "SILVER_PROD.ADMIN.SALESFORCE_WDESK_CLASSIC_ACCOUNT": (
        "SELECT ID, NAME, ORGANIZATION_ID, ACCOUNT_RESOURCE_ID, STATUS, IS_DELETED "
        "FROM SILVER_PROD.ADMIN.SALESFORCE_WDESK_CLASSIC_ACCOUNT "
        "WHERE ORGANIZATION_ID = %s"
    ),
}

SNOWFLAKE_SF_QUERY = """
SELECT DISTINCT swa.ID AS sf_account_id
FROM SILVER_PROD.ADMIN.WORKIVA_ORG_DELETES d
LEFT JOIN SILVER_PROD.ADMIN.STG_WORKIVA_WORKSPACE ww
  ON ww.ORGANIZATION_ID = d.ORGANIZATION_ID
LEFT JOIN SILVER_PROD.ADMIN.SALESFORCE_WDESK_CLASSIC_ACCOUNT swa
  ON swa.ACCOUNT_RESOURCE_ID = ww.WORKSPACE_ID
WHERE d.ORGANIZATION_ID = %s
"""


# ---------------------------------------------------------------------------
# Database connections
# ---------------------------------------------------------------------------

def connect_snowflake():
    import snowflake.connector
    return snowflake.connector.connect(connection_name="keazvso-business_tech_prod")


def connect_redshift():
    import psycopg2
    conn = psycopg2.connect(
        host=os.getenv("REDSHIFT_HOST", "redshift.it.workiva.net"),
        port=int(os.getenv("REDSHIFT_PORT", "5439")),
        dbname=os.getenv("REDSHIFT_DB", "defaultdb"),
        user=os.getenv("REDSHIFT_USER"),
        password=os.getenv("REDSHIFT_PASSWORD"),
        sslmode="require",
        connect_timeout=10,
    )
    cur = conn.cursor()
    cur.execute("SET statement_timeout = 30000")  # 30 second per-query timeout
    cur.close()
    return conn


def run_queries(conn, org_id: str, db_label: str) -> dict:
    """Run all verification queries and return results dict."""
    results = {}
    cur = conn.cursor()

    redaction_queries = SNOWFLAKE_REDACTION_QUERIES if db_label == "Snowflake" else REDSHIFT_REDACTION_QUERIES
    sf_query = SNOWFLAKE_SF_QUERY if db_label == "Snowflake" else REDSHIFT_SF_QUERY

    for table, query in redaction_queries.items():
        try:
            cur.execute(query, (org_id,))
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description] if cur.description else []
            results[table] = {"rows": len(rows), "columns": cols, "status": "ok"}
        except Exception as e:
            results[table] = {"rows": 0, "columns": [], "status": f"error: {e}"}

    try:
        cur.execute(sf_query, (org_id,))
        rows = cur.fetchall()
        if db_label == "Redshift":
            sf_ids = [row[0] for row in rows if row[0]]
            results["salesforce_verification"] = {
                "sf_account_ids": sf_ids,
                "rows": len(rows),
                "status": "ok",
            }
        else:
            results["org_deletes_check"] = {
                "rows": len(rows),
                "data": [row for row in rows[:10]],
                "status": "ok",
            }
    except Exception as e:
        key = "salesforce_verification" if db_label == "Redshift" else "org_deletes_check"
        results[key] = {
            "sf_account_ids": [] if db_label == "Redshift" else None,
            "rows": 0,
            "status": f"error: {e}",
        }

    cur.close()
    return results


# ---------------------------------------------------------------------------
# Org ID extraction
# ---------------------------------------------------------------------------

UUID_PATTERN = re.compile(
    r"[Oo]rg(?:anization)?[\s_]*[Ii][Dd][\s:=]*"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)

UUID_BARE = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def extract_org_id(description: str) -> str:
    match = UUID_PATTERN.search(description)
    if match:
        return match.group(1)
    # Fallback: first UUID in description
    match = UUID_BARE.search(description)
    if match:
        return match.group(1)
    return ""


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_results(snowflake_results: dict, redshift_results: dict, org_id: str) -> str:
    """Format verification results as a Jira wiki markup comment."""
    lines = [
        f"h4. Data Deletion Verification",
        f"*Org ID:* {{{{monospace:{org_id}}}}}",
        "",
    ]

    for db_label, results in [("Snowflake", snowflake_results), ("Redshift", redshift_results)]:
        if results is None:
            continue
        lines.append(f"h5. {db_label}")
        lines.append("||Table||Rows||Status||")
        for table, info in results.items():
            if table == "salesforce_verification":
                continue
            status = info["status"]
            icon = "(/) " if status == "ok" else "(x) "
            lines.append(f"|{table}|{info['rows']}|{icon}{status}|")

        sf = results.get("salesforce_verification", {})
        if sf:
            sf_ids = sf.get("sf_account_ids", [])
            sf_str = ", ".join(str(sid) for sid in sf_ids) if sf_ids else "none"
            lines.append(f"\n*SF Account IDs:* {sf_str}")
        lines.append("")

    lines.append("Field redaction verification completed.")
    return "\n".join(lines)


def format_console(snowflake_results: dict, redshift_results: dict, org_id: str) -> str:
    """Format results for console output."""
    lines = [f"\nVerification Results for org_id: {org_id}", "=" * 60]

    for db_label, results in [("Snowflake", snowflake_results), ("Redshift", redshift_results)]:
        if results is None:
            lines.append(f"\n  {db_label}: skipped")
            continue
        lines.append(f"\n  {db_label}:")
        for table, info in results.items():
            if table == "salesforce_verification":
                sf_ids = info.get("sf_account_ids", [])
                lines.append(f"    SF Account IDs: {sf_ids}")
            else:
                lines.append(f"    {table:45s}  rows={info['rows']:3d}  {info['status']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Verify data deletion in Snowflake and Redshift")
    parser.add_argument("ticket", help="Jira ticket key (e.g., DATA-2439)")
    parser.add_argument("--post", action="store_true", help="Post results as Jira comment")
    parser.add_argument("--close", action="store_true", help="Close the ticket after posting")
    parser.add_argument("--snowflake-only", action="store_true", help="Skip Redshift")
    parser.add_argument("--redshift-only", action="store_true", help="Skip Snowflake")
    parser.add_argument("--org-id", help="Override org_id (skip extraction from ticket)")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    settings = load_settings()
    jira = JiraClient(settings.jira_base_url, settings.jira_pat)

    # Get ticket and extract org_id
    issue = jira.get_issue(args.ticket, fields=["description", "summary", "status"])
    description = issue["fields"].get("description") or ""

    org_id = args.org_id or extract_org_id(description)
    if not org_id:
        print(f"ERROR: Could not extract org_id from {args.ticket} description.")
        print("Use --org-id to provide it manually.")
        sys.exit(1)

    print(f"Ticket: {args.ticket}")
    print(f"Org ID: {org_id}")

    # Run queries
    snowflake_results = None
    redshift_results = None

    if not args.redshift_only:
        print("\nConnecting to Snowflake...")
        try:
            sf_conn = connect_snowflake()
            snowflake_results = run_queries(sf_conn, org_id, "Snowflake")
            sf_conn.close()
            print("  Snowflake queries complete.")
        except Exception as e:
            print(f"  Snowflake connection failed: {e}")

    if not args.snowflake_only:
        rs_user = os.getenv("REDSHIFT_USER")
        if not rs_user:
            print("\n  Redshift skipped (REDSHIFT_USER not set in .env)")
        else:
            print("\nConnecting to Redshift...")
            try:
                rs_conn = connect_redshift()
                redshift_results = run_queries(rs_conn, org_id, "Redshift")
                rs_conn.close()
                print("  Redshift queries complete.")
            except Exception as e:
                print(f"  Redshift connection failed: {e}")

    # Display results
    print(format_console(snowflake_results, redshift_results, org_id))

    # Post to Jira
    if args.post:
        comment = format_results(snowflake_results, redshift_results, org_id)
        jira.add_comment(args.ticket, comment)
        print(f"\nVerification posted to {args.ticket}")

    # Close ticket
    if args.close:
        summary = issue["fields"].get("summary", "")
        # Extract customer name from summary (before " - Data Deletion" or " - Request to Delete")
        customer = summary.split(" - ")[0] if " - " in summary else summary
        close_comment = (
            f"{customer} - deletion request is completed.\n"
            f"[~service_saasops] request is completed."
        )
        jira.add_comment(args.ticket, close_comment)

        from core.tpm_workflow import close_data_ticket
        try:
            close_data_ticket(jira, args.ticket)
            print(f"Ticket {args.ticket} closed.")
        except Exception as e:
            print(f"Could not close {args.ticket}: {e}")
            print("Close the ticket manually in Jira.")


if __name__ == "__main__":
    main()
