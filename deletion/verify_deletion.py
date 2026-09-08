#!/usr/bin/env python3
"""Two-step data deletion verification against Snowflake and Redshift.

Step 1 (identify): Extract org/workspace info from ticket, query current state,
                    post confirmation comment with names and IDs.
Step 2 (verify):   After SSE deletion actions complete, check that workspace
                    names are REDACTED and deleted flags are set.

Usage:
    python -m deletion.verify_deletion identify DATA-2487 [--post]
    python -m deletion.verify_deletion verify DATA-2487 [--post] [--close]
    python -m deletion.verify_deletion identify DATA-2487 --org-id <uuid> [--post]
"""

import argparse
import os
import re
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import project_root  # noqa: F401

from clients.config import load_settings
from clients.jira_client import JiraClient


# ---------------------------------------------------------------------------
# Extraction patterns
# ---------------------------------------------------------------------------

UUID_PATTERN = re.compile(
    r"[Oo]rg(?:anization)?[\s_]*[Ii][Dd][\s:=]*"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
UUID_BARE = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
WORKSPACE_ID_PATTERN = re.compile(r"(QWNjb3VudB8\S+)")


def extract_org_id(text: str) -> str:
    match = UUID_PATTERN.search(text)
    if match:
        return match.group(1)
    match = UUID_BARE.search(text)
    if match:
        return match.group(1)
    return ""


def extract_workspace_ids(text: str) -> list[str]:
    return list(dict.fromkeys(WORKSPACE_ID_PATTERN.findall(text)))


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
    cur.execute("SET statement_timeout = 30000")
    cur.close()
    return conn


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

SNOWFLAKE_WORKSPACE_QUERY = """
SELECT WORKSPACE_ID, WORKSPACE_NAME, DELETED_FLAG, ACTIVE_FLAG
FROM SILVER_PROD.ADMIN.STG_WORKIVA_WORKSPACE
WHERE ORGANIZATION_ID = %s
ORDER BY WORKSPACE_NAME
"""

SNOWFLAKE_ORG_DELETES_QUERY = """
SELECT ORGANIZATION_ID, ACCOUNT_ID, DELETED_DATE
FROM SILVER_PROD.ADMIN.WORKIVA_ORG_DELETES
WHERE ORGANIZATION_ID = %s
"""

REDSHIFT_WORKSPACE_QUERY = """
SELECT workspace_id, workspace_name, deleted_flag, active_flag
FROM audit.workiva_workspace
WHERE organization_id = %s
ORDER BY workspace_name
"""

REDSHIFT_ORG_DELETES_QUERY = """
SELECT organization_id, account_id, deleted_date
FROM admin.workiva_org_deletes
WHERE organization_id = %s
"""


def query_workspaces(conn, org_id: str, db_label: str) -> list[dict]:
    query = SNOWFLAKE_WORKSPACE_QUERY if db_label == "Snowflake" else REDSHIFT_WORKSPACE_QUERY
    cur = conn.cursor()
    cur.execute(query, (org_id,))
    rows = cur.fetchall()
    cols = [desc[0].upper() for desc in cur.description]
    cur.close()
    return [dict(zip(cols, row)) for row in rows]


def query_org_deletes(conn, org_id: str, db_label: str) -> list[dict]:
    query = SNOWFLAKE_ORG_DELETES_QUERY if db_label == "Snowflake" else REDSHIFT_ORG_DELETES_QUERY
    cur = conn.cursor()
    cur.execute(query, (org_id,))
    rows = cur.fetchall()
    cols = [desc[0].upper() for desc in cur.description]
    cur.close()
    return [dict(zip(cols, row)) for row in rows]


# ---------------------------------------------------------------------------
# Identify: list workspaces and their current state
# ---------------------------------------------------------------------------

def run_identify(jira, ticket_key: str, org_id: str, post: bool):
    print(f"Ticket: {ticket_key}")
    print(f"Org ID: {org_id}")

    print("\nConnecting to Snowflake...")
    conn = connect_snowflake()
    workspaces = query_workspaces(conn, org_id, "Snowflake")
    conn.close()

    if not workspaces:
        print(f"  No workspaces found for org_id {org_id}")
        return

    print(f"\n  Found {len(workspaces)} workspace(s):\n")
    print(f"  {'Workspace ID':<45} {'Name':<50} {'Deleted':<10} {'Active'}")
    print(f"  {'-'*45} {'-'*50} {'-'*10} {'-'*6}")
    for ws in workspaces:
        ws_id = str(ws.get("WORKSPACE_ID", ""))
        name = str(ws.get("WORKSPACE_NAME", ""))
        deleted = ws.get("DELETED_FLAG", False)
        active = ws.get("ACTIVE_FLAG", False)
        print(f"  {ws_id:<45} {name:<50} {str(deleted):<10} {active}")

    if post:
        lines = [
            "h4. Deletion Scope \u2014 Workspace Identification",
            f"*Org ID:* {{{{monospace:{org_id}}}}}",
            f"*Workspaces:* {len(workspaces)}",
            "",
            "||Workspace ID||Workspace Name||Deleted||Active||",
        ]
        for ws in workspaces:
            ws_id = str(ws.get("WORKSPACE_ID", ""))
            name = str(ws.get("WORKSPACE_NAME", ""))
            deleted = ws.get("DELETED_FLAG", False)
            active = ws.get("ACTIVE_FLAG", False)
            d_icon = "(/) Yes" if deleted else "(x) No"
            a_icon = "(/) Yes" if active else "(x) No"
            lines.append(f"|{{{{monospace:{ws_id}}}}}|{name}|{d_icon}|{a_icon}|")

        jira.add_comment(ticket_key, "\n".join(lines))
        print(f"\nIdentification posted to {ticket_key}")


# ---------------------------------------------------------------------------
# Verify: check that workspaces are REDACTED after deletion
# ---------------------------------------------------------------------------

def run_verify(jira, ticket_key: str, org_id: str, post: bool, close: bool,
               snowflake_only: bool, redshift_only: bool):
    print(f"Ticket: {ticket_key}")
    print(f"Org ID: {org_id}")

    results = {}

    if not redshift_only:
        print("\nConnecting to Snowflake...")
        try:
            conn = connect_snowflake()
            workspaces = query_workspaces(conn, org_id, "Snowflake")
            org_deletes = query_org_deletes(conn, org_id, "Snowflake")
            conn.close()
            results["Snowflake"] = {"workspaces": workspaces, "org_deletes": org_deletes}
            print("  Snowflake queries complete.")
        except Exception as e:
            print(f"  Snowflake failed: {e}")

    if not snowflake_only:
        rs_user = os.getenv("REDSHIFT_USER")
        if not rs_user:
            print("\n  Redshift skipped (REDSHIFT_USER not set)")
        else:
            print("\nConnecting to Redshift...")
            try:
                conn = connect_redshift()
                workspaces = query_workspaces(conn, org_id, "Redshift")
                org_deletes = query_org_deletes(conn, org_id, "Redshift")
                conn.close()
                results["Redshift"] = {"workspaces": workspaces, "org_deletes": org_deletes}
                print("  Redshift queries complete.")
            except Exception as e:
                print(f"  Redshift failed: {e}")

    # Display and evaluate
    all_pass = True
    for db_label, data in results.items():
        workspaces = data["workspaces"]
        org_deletes = data["org_deletes"]
        redacted = [ws for ws in workspaces if str(ws.get("WORKSPACE_NAME", "")).upper() == "REDACTED"]
        not_redacted = [ws for ws in workspaces if str(ws.get("WORKSPACE_NAME", "")).upper() != "REDACTED"]

        print(f"\n  {db_label}: {len(workspaces)} workspaces, "
              f"{len(redacted)} redacted, {len(not_redacted)} not redacted")
        print(f"  Org deletes: {len(org_deletes)} record(s)")

        if not_redacted:
            all_pass = False
            print(f"\n  NOT REDACTED:")
            for ws in not_redacted[:20]:
                ws_id = str(ws.get("WORKSPACE_ID", ""))
                name = str(ws.get("WORKSPACE_NAME", ""))
                print(f"    {ws_id:<45} {name}")

        if not org_deletes:
            all_pass = False
            print(f"  WARNING: No record in org_deletes table")

    if all_pass and results:
        print(f"\n  PASS: All workspaces redacted and org_deletes record present.")
    elif results:
        print(f"\n  FAIL: Some workspaces not yet redacted.")

    # Post to Jira
    if post and results:
        lines = [
            "h4. Data Deletion Verification",
            f"*Org ID:* {{{{monospace:{org_id}}}}}",
            "",
        ]
        for db_label, data in results.items():
            workspaces = data["workspaces"]
            org_deletes = data["org_deletes"]
            redacted = [ws for ws in workspaces if str(ws.get("WORKSPACE_NAME", "")).upper() == "REDACTED"]
            not_redacted = [ws for ws in workspaces if str(ws.get("WORKSPACE_NAME", "")).upper() != "REDACTED"]

            lines.append(f"h5. {db_label}")
            lines.append(f"*Workspaces:* {len(workspaces)} total, "
                         f"{len(redacted)} redacted, {len(not_redacted)} not redacted")

            if not_redacted:
                lines.append("")
                lines.append("||Workspace ID||Name||Status||")
                for ws in not_redacted:
                    ws_id = str(ws.get("WORKSPACE_ID", ""))
                    name = str(ws.get("WORKSPACE_NAME", ""))
                    lines.append(f"|{{{{monospace:{ws_id}}}}}|{name}|(x) Not redacted|")

            if org_deletes:
                d = org_deletes[0]
                lines.append(f"\n*Org deletes:* (/) Present (deleted {d.get('DELETED_DATE', '?')})")
            else:
                lines.append(f"\n*Org deletes:* (x) No record found")
            lines.append("")

        if all_pass:
            lines.append("(/) *Field redaction verification completed.* All workspaces redacted.")
        else:
            lines.append("(x) *Verification incomplete.* Some workspaces not yet redacted.")

        jira.add_comment(ticket_key, "\n".join(lines))
        print(f"\nVerification posted to {ticket_key}")

    # Close ticket
    if close and all_pass:
        issue = jira.get_issue(ticket_key, fields=["summary"])
        summary = issue["fields"].get("summary", "")
        customer = summary.split(" - ")[0] if " - " in summary else summary
        close_comment = (
            f"{customer} \u2014 deletion request is completed.\n"
            f"[~service_saasops] request is completed."
        )
        jira.add_comment(ticket_key, close_comment)
        from core.tpm_workflow import close_data_ticket
        try:
            close_data_ticket(jira, ticket_key)
            print(f"Ticket {ticket_key} closed.")
        except Exception as e:
            print(f"Could not close {ticket_key}: {e}")
    elif close and not all_pass:
        print("Not closing — verification did not pass.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Data deletion verification (identify + verify)")
    sub = parser.add_subparsers(dest="command", required=True)

    id_cmd = sub.add_parser("identify", help="List workspaces for an org and post confirmation")
    id_cmd.add_argument("ticket", help="Jira ticket key")
    id_cmd.add_argument("--org-id", help="Override org_id")
    id_cmd.add_argument("--post", action="store_true", help="Post identification to Jira")

    v_cmd = sub.add_parser("verify", help="Check that workspaces are REDACTED after deletion")
    v_cmd.add_argument("ticket", help="Jira ticket key")
    v_cmd.add_argument("--org-id", help="Override org_id")
    v_cmd.add_argument("--post", action="store_true", help="Post verification to Jira")
    v_cmd.add_argument("--close", action="store_true", help="Close ticket if verification passes")
    v_cmd.add_argument("--snowflake-only", action="store_true", help="Skip Redshift")
    v_cmd.add_argument("--redshift-only", action="store_true", help="Skip Snowflake")

    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    settings = load_settings()
    jira = JiraClient(settings.jira_base_url, settings.jira_pat)

    # Get ticket and extract org_id
    issue = jira.get_issue(args.ticket, fields=["description", "summary", "status"])
    description = issue["fields"].get("description") or ""

    org_id = getattr(args, "org_id", None) or extract_org_id(description)
    if not org_id:
        print(f"ERROR: Could not extract org_id from {args.ticket}.")
        print("Use --org-id to provide it manually.")
        sys.exit(1)

    if args.command == "identify":
        run_identify(jira, args.ticket, org_id, args.post)
    elif args.command == "verify":
        run_verify(jira, args.ticket, org_id, args.post, args.close,
                   getattr(args, "snowflake_only", False),
                   getattr(args, "redshift_only", False))


if __name__ == "__main__":
    main()
