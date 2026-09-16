#!/usr/bin/env python3
"""Create DATA tickets via the JSM service desk API.

Usage:
  # Interactive (prompts for all fields, infers from description):
  python scripts/create_data_ticket.py --on-behalf-of john.doe

  # Interactive with dry-run (prints payload, does not submit):
  python scripts/create_data_ticket.py --on-behalf-of john.doe --dry-run

  # Batch mode from JSON file:
  python scripts/create_data_ticket.py --from-json tickets.json --dry-run

JSON file format (array of objects):
  [
    {
      "on_behalf_of": "john.doe",
      "summary": "Need Snowflake access for analytics team",
      "description": "The analytics team needs read access to GOLD_PROD...",
      "service_type": "System/DB access",
      "teams_impacted": "My team",
      "business_priority": "Standard Business Operation",
      "primary_solution": "Warehouse",
      "executive_sponsor": "Jane Smith"
    }
  ]
"""
import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import project_root  # noqa: F401

from clients.config import load_settings
from clients.jira_client import JiraClient
from core.tpm_workflow import (
    SERVICE_DESK_ID, REQUEST_TYPE_ID,
    SERVICE_TYPE_IDS, TEAMS_IMPACTED_IDS, BUSINESS_PRIORITY_IDS,
    PRIMARY_SOLUTION_IDS, CF_SERVICE_TYPE, CF_TEAMS_IMPACTED,
    CF_BIZ_PRIORITY, CF_PRIMARY_SOLUTION, CF_EXEC_SPONSOR,
    infer_fields_from_description, assess_data_ticket, recommend_team,
    resolve_virtual_team, propose_summary, find_related_tickets,
)
from core.rice_scoring import calculate_rice
from core.asset_lookup import lookup_assets_for_ticket, format_asset_context

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interactive prompting helpers
# ---------------------------------------------------------------------------

def prompt_menu(label: str, options: dict, default_key: str = None) -> str:
    """Show a numbered menu and return the selected key.

    options: OrderedDict-like {display_label: id_value}
    default_key: pre-selected label (user presses Enter to accept)
    """
    keys = list(options.keys())
    print(f"\n{label}:")
    for i, key in enumerate(keys, 1):
        marker = " (inferred)" if key == default_key else ""
        print(f"  [{i}] {key}{marker}")
    skip_allowed = default_key is None
    if skip_allowed:
        print(f"  [Enter] Skip")

    while True:
        default_num = keys.index(default_key) + 1 if default_key else ""
        prompt_text = f"  Select [{'Enter to skip' if skip_allowed else default_num}]: "
        raw = input(prompt_text).strip()

        if not raw:
            if default_key:
                return default_key
            if skip_allowed:
                return None
        try:
            idx = int(raw)
            if 1 <= idx <= len(keys):
                return keys[idx - 1]
        except ValueError:
            pass
        print(f"  Please enter 1-{len(keys)}" + (" or Enter to skip" if skip_allowed else ""))


def prompt_text(label: str, required: bool = True) -> str:
    """Prompt for a single line of text."""
    while True:
        val = input(f"\n{label}: ").strip()
        if val or not required:
            return val
        print("  This field is required.")


def prompt_multiline(label: str) -> str:
    """Prompt for multi-line text (end with an empty line)."""
    print(f"\n{label} (end with an empty line):")
    lines = []
    while True:
        line = input()
        if line == "" and lines:
            break
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------

def build_request_field_values(
    summary: str,
    description: str,
    service_type: str,
    teams_impacted: str,
    business_priority: str,
    primary_solution: str = None,
    executive_sponsor: str = None,
) -> dict:
    """Build the requestFieldValues dict for the service desk API."""
    fv = {
        "summary": summary,
        "description": description,
        CF_SERVICE_TYPE: {"id": SERVICE_TYPE_IDS[service_type]},
        CF_TEAMS_IMPACTED: [{"id": TEAMS_IMPACTED_IDS[teams_impacted]}],
        CF_BIZ_PRIORITY: {"id": BUSINESS_PRIORITY_IDS[business_priority]},
    }
    if primary_solution and primary_solution in PRIMARY_SOLUTION_IDS:
        fv[CF_PRIMARY_SOLUTION] = [{"id": PRIMARY_SOLUTION_IDS[primary_solution]}]
    if executive_sponsor:
        fv[CF_EXEC_SPONSOR] = executive_sponsor
    return fv


# ---------------------------------------------------------------------------
# Post-creation triage
# ---------------------------------------------------------------------------

def run_post_creation_triage(jira: JiraClient, issue_key: str) -> None:
    """Fetch the newly created ticket and run the triage assessment pipeline."""
    if issue_key.startswith("DRYRUN"):
        print("\n--- Post-creation triage (skipped: dry-run) ---")
        return

    print(f"\n--- Post-creation triage: {issue_key} ---")
    issue = jira.get_issue(issue_key)
    fields = issue["fields"]

    # Assessment
    assessment = assess_data_ticket(fields, issue_key)
    print(f"Conformance: {assessment['conformance']['score']}/5 ({assessment['conformance']['path']})")
    print(f"  Checks: {json.dumps(assessment['conformance']['checks'])}")
    print(f"Service Type: {assessment['service_type']}")
    print(f"Biz Priority: {assessment['biz_priority']}")
    print(f"Jira Priority: {assessment['jira_priority']}")
    print(f"SLA: {assessment['sla']}")
    print(f"Tier: {assessment['tier']}")
    print(f"Primary Solution: {assessment['primary_solution']}")
    print(f"Teams Impacted: {assessment['teams_impacted']}")
    print(f"Sponsor: {assessment['sponsor']}")

    # RICE
    rice = calculate_rice(fields)
    print(f"\nRICE Score: {rice['rice_score']} ({rice['priority_bucket']})")
    print(f"  Reach={rice['reach']} Impact={rice['impact']} "
          f"Confidence={int(rice['confidence'] * 100)}% Effort={rice['effort']}")

    # Team recommendation
    rec = recommend_team(fields)
    resolved = resolve_virtual_team(rec["team"])
    print(f"\nTeam: {rec['team']} ({rec['confidence']} - {rec['reason']})")
    if resolved["component"]:
        print(f"  Jira: Team={resolved['team']}, Component={resolved['component']}")
    else:
        print(f"  Jira: Team={resolved['team']}")

    # Summary proposal
    proposed = propose_summary(fields)
    if proposed:
        print(f"\nProposed Summary: {proposed}")

    # Asset lookup
    try:
        ctx = lookup_assets_for_ticket(fields)
        if ctx.get("asset_names"):
            print(f"\nAsset Lookup:")
            print(format_asset_context(ctx))
    except Exception as e:
        log.debug("Asset lookup skipped: %s", e)

    # Related tickets
    related = find_related_tickets(jira, issue_key, fields)
    if related:
        print(f"\nRelated tickets: {', '.join(related)}")

    print("--- end triage ---")


# ---------------------------------------------------------------------------
# Interactive flow
# ---------------------------------------------------------------------------

def interactive_create(jira: JiraClient, on_behalf_of: str) -> None:
    """Walk the user through ticket creation with description-driven inference."""
    summary = prompt_text("Summary")
    description = prompt_multiline("Description")

    # Infer fields from the text
    inferred = infer_fields_from_description(summary, description)
    if any(v for k, v in inferred.items() if k != "reasons"):
        print("\n--- Inferred from description ---")
        for field in ("service_type", "business_priority", "primary_solution"):
            val = inferred[field]
            reason = inferred["reasons"].get(field, "")
            if val:
                print(f"  {field}: {val}  ({reason})")
        print("---")

    # Prompt with inferred defaults
    service_type = prompt_menu("Service Type", SERVICE_TYPE_IDS,
                               default_key=inferred.get("service_type"))
    if not service_type:
        service_type = "Other"

    teams_impacted = prompt_menu("Teams Impacted", TEAMS_IMPACTED_IDS)
    if not teams_impacted:
        teams_impacted = "Just me"

    business_priority = prompt_menu("Business Priority", BUSINESS_PRIORITY_IDS,
                                     default_key=inferred.get("business_priority"))
    if not business_priority:
        business_priority = "Standard Business Operation"

    primary_solution = prompt_menu("Primary Solution", PRIMARY_SOLUTION_IDS,
                                    default_key=inferred.get("primary_solution"))

    executive_sponsor = prompt_text("Executive Sponsor (optional, Enter to skip)", required=False)

    # Confirmation
    print("\n=== Confirmation ===")
    print(f"  On behalf of: {on_behalf_of}")
    print(f"  Summary:      {summary}")
    print(f"  Service Type:  {service_type}")
    print(f"  Teams Impacted: {teams_impacted}")
    print(f"  Biz Priority:  {business_priority}")
    print(f"  Primary Soln:  {primary_solution or '(none)'}")
    print(f"  Sponsor:       {executive_sponsor or '(none)'}")
    print(f"  Description:   {description[:120]}{'...' if len(description) > 120 else ''}")

    confirm = input("\nSubmit? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    field_values = build_request_field_values(
        summary=summary,
        description=description,
        service_type=service_type,
        teams_impacted=teams_impacted,
        business_priority=business_priority,
        primary_solution=primary_solution,
        executive_sponsor=executive_sponsor,
    )

    result = jira.create_service_request(
        SERVICE_DESK_ID, REQUEST_TYPE_ID, field_values, on_behalf_of=on_behalf_of,
    )
    issue_key = result.get("issueKey", "???")
    web_link = result.get("_links", {}).get("web", "")
    print(f"\nCreated: {issue_key}")
    if web_link:
        print(f"  URL: {web_link}")

    run_post_creation_triage(jira, issue_key)


# ---------------------------------------------------------------------------
# Batch flow
# ---------------------------------------------------------------------------

VALID_SERVICE_TYPES = set(SERVICE_TYPE_IDS.keys())
VALID_TEAMS_IMPACTED = set(TEAMS_IMPACTED_IDS.keys())
VALID_BUSINESS_PRIORITIES = set(BUSINESS_PRIORITY_IDS.keys())
VALID_PRIMARY_SOLUTIONS = set(PRIMARY_SOLUTION_IDS.keys())


def validate_batch_entry(entry: dict, idx: int) -> list[str]:
    """Validate a single batch entry. Returns list of error messages."""
    errors = []
    for req_field in ("on_behalf_of", "summary", "description", "service_type",
                      "teams_impacted", "business_priority"):
        if not entry.get(req_field):
            errors.append(f"[{idx}] Missing required field: {req_field}")

    st = entry.get("service_type", "")
    if st and st not in VALID_SERVICE_TYPES:
        errors.append(f"[{idx}] Invalid service_type '{st}'. Valid: {sorted(VALID_SERVICE_TYPES)}")

    ti = entry.get("teams_impacted", "")
    if ti and ti not in VALID_TEAMS_IMPACTED:
        errors.append(f"[{idx}] Invalid teams_impacted '{ti}'. Valid: {sorted(VALID_TEAMS_IMPACTED)}")

    bp = entry.get("business_priority", "")
    if bp and bp not in VALID_BUSINESS_PRIORITIES:
        errors.append(f"[{idx}] Invalid business_priority '{bp}'. Valid: {sorted(VALID_BUSINESS_PRIORITIES)}")

    ps = entry.get("primary_solution", "")
    if ps and ps not in VALID_PRIMARY_SOLUTIONS:
        errors.append(f"[{idx}] Invalid primary_solution '{ps}'. Valid: {sorted(VALID_PRIMARY_SOLUTIONS)}")

    return errors


def batch_create(jira: JiraClient, json_path: str) -> None:
    """Create tickets from a JSON spec file."""
    with open(json_path) as f:
        entries = json.load(f)

    if not isinstance(entries, list):
        entries = [entries]

    # Validate all before submitting any
    all_errors = []
    for i, entry in enumerate(entries):
        all_errors.extend(validate_batch_entry(entry, i))
    if all_errors:
        print("Validation errors:")
        for err in all_errors:
            print(f"  {err}")
        sys.exit(1)

    print(f"Submitting {len(entries)} ticket(s)...\n")
    for i, entry in enumerate(entries):
        field_values = build_request_field_values(
            summary=entry["summary"],
            description=entry["description"],
            service_type=entry["service_type"],
            teams_impacted=entry["teams_impacted"],
            business_priority=entry["business_priority"],
            primary_solution=entry.get("primary_solution"),
            executive_sponsor=entry.get("executive_sponsor"),
        )
        result = jira.create_service_request(
            SERVICE_DESK_ID, REQUEST_TYPE_ID, field_values,
            on_behalf_of=entry["on_behalf_of"],
        )
        issue_key = result.get("issueKey", "???")
        web_link = result.get("_links", {}).get("web", "")
        print(f"[{i + 1}/{len(entries)}] Created: {issue_key}  (on behalf of {entry['on_behalf_of']})")
        if web_link:
            print(f"  URL: {web_link}")

        run_post_creation_triage(jira, issue_key)
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Create DATA tickets via the JSM service desk API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--on-behalf-of", "-r",
                        help="Jira username of the requester (required for interactive mode)")
    parser.add_argument("--from-json",
                        help="Path to a JSON file for batch creation (skips interactive prompts)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print payload without submitting")
    args = parser.parse_args()

    if not args.from_json and not args.on_behalf_of:
        parser.error("--on-behalf-of is required for interactive mode")

    settings = load_settings()
    jira = JiraClient(settings.jira_base_url, settings.jira_pat, dry_run=args.dry_run)

    if args.from_json:
        batch_create(jira, args.from_json)
    else:
        interactive_create(jira, args.on_behalf_of)


if __name__ == "__main__":
    main()
