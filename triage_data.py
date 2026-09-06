#!/usr/bin/env python3
"""Two-path DATA ticket triage with plan/apply phases.

Usage:
    python triage_data.py plan [--path auto|enrich|all]   # Interactive: build a plan file
    python triage_data.py apply <plan_file>                # Execute the plan
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from config import load_settings
from jira_client import JiraClient
from tpm_workflow import (
    SLA_COMMENTS, BIZ_PRIORITY_TO_JIRA, SERVICE_TYPE_TIERS, SERVICE_TYPES,
    CF_SERVICE_TYPE, CF_BIZ_PRIORITY,
    assess_data_ticket, post_sla_comment, build_dna_payload,
    create_dna_ticket, move_to_dna, close_data_ticket, VALID_TEAMS,
    recommend_team, resolve_virtual_team, VIRTUAL_TEAMS,
)
from snapshot import snapshot_from_keys
from rice_scoring import calculate_rice, format_rice_comment

PLANS_DIR = os.path.join(os.path.dirname(__file__), "plans")
CHANGES_DIR = os.path.join(os.path.dirname(__file__), "changes")
AUDIT_PATH = os.path.join(os.path.dirname(__file__), "data_audit.json")


def load_audit() -> dict:
    if not os.path.exists(AUDIT_PATH):
        print(f"Run audit_data.py first to generate {AUDIT_PATH}")
        sys.exit(1)
    with open(AUDIT_PATH) as f:
        return json.load(f)


def prompt_choice(prompt: str, options: list[str], default: str = None) -> str:
    options_str = "/".join(options)
    default_str = f" [{default}]" if default else ""
    while True:
        choice = input(f"{prompt} ({options_str}){default_str}: ").strip()
        if not choice and default:
            return default
        if choice in options:
            return choice
        print(f"  Invalid choice. Options: {options_str}")


# ---------------------------------------------------------------------------
# PLAN PHASE: interactive, builds a reviewable plan file
# ---------------------------------------------------------------------------

def plan_auto_ticket(jira: JiraClient, ticket: dict) -> dict:
    """Plan triage for a conforming ticket. Returns an action dict."""
    key = ticket["key"]
    print(f"\n{'='*80}")
    print(f"[AUTO] {key}: {ticket['summary']}")
    print(f"  Service Type: {ticket['service_type']}")
    print(f"  Biz Priority: {ticket['biz_priority']}")
    print(f"  Jira Priority: {ticket['jira_priority']} -> SLA: {SLA_COMMENTS.get(ticket['jira_priority'], '?')}")
    print(f"  Tier: {ticket['tier']} ({'Resolve at desk' if ticket['tier'] <= 2 else 'Handoff to DNA'})")
    print(f"  DNA refs: {ticket.get('dna_crossrefs', [])}")

    # Fetch full issue for RICE and team recommendation
    full_issue = jira.get_issue(key)
    fields = full_issue["fields"]
    rice = calculate_rice(fields)
    print(f"  RICE Score: {rice['rice_score']} ({rice['priority_bucket']}) "
          f"[R={rice['reach']} I={rice['impact']} C={int(rice['confidence']*100)}% E={rice['effort']}]")

    action = prompt_choice(
        "  Action",
        ["sla", "handoff", "close", "skip"],
        default="sla" if ticket["tier"] <= 2 else "handoff",
    )

    plan_entry = {
        "key": key,
        "summary": ticket["summary"],
        "path": "AUTO",
        "action": action,
        "rice": rice,
    }

    if action == "sla":
        plan_entry["priority"] = ticket["jira_priority"]

    elif action == "handoff":
        rec = recommend_team(fields)
        all_team_choices = VALID_TEAMS + list(VIRTUAL_TEAMS.keys())
        if rec:
            vt = resolve_virtual_team(rec["team"])
            if vt["component"]:
                print(f"  Recommended team: {rec['team']} -> Jira: Team={vt['team']}, Component={vt['component']} ({rec['confidence']} — {rec['reason']})")
            else:
                print(f"  Recommended team: {rec['team']} ({rec['confidence']} — {rec['reason']})")
            default_team = rec["team"]
        else:
            default_team = "Data Engineering"

        team_choice = prompt_choice("  Team", all_team_choices, default=default_team)
        resolved = resolve_virtual_team(team_choice)

        effort = input("  Effort points [1/2/3/5/8/13/skip]: ").strip()
        effort_pts = int(effort) if effort in ("1", "2", "3", "5", "8", "13") else None
        epic = input("  Epic link [DNA-XXXX/skip]: ").strip()
        epic_link = epic if epic.startswith("DNA-") else ""
        stakeholder = input("  Stakeholder username [skip]: ").strip() or ""

        plan_entry["team_choice"] = team_choice
        plan_entry["jira_team"] = resolved["team"]
        plan_entry["component"] = resolved["component"]
        plan_entry["effort_points"] = effort_pts
        plan_entry["epic_link"] = epic_link
        plan_entry["stakeholder"] = stakeholder

    elif action == "close":
        pass  # no extra fields needed

    return plan_entry


def plan_enrich_ticket(jira: JiraClient, ticket: dict) -> dict:
    """Plan triage for a non-conforming ticket."""
    key = ticket["key"]
    print(f"\n{'='*80}")
    print(f"[ENRICH] {key}: {ticket['summary']}")
    print(f"  Issue Type: {ticket['issue_type']}")
    print(f"  Status: {ticket['status']}")
    print(f"  Missing: {', '.join(ticket.get('missing_fields', []))}")
    print(f"  DNA refs: {ticket.get('dna_crossrefs', [])}")

    full = jira.get_issue(key, fields=["description"])
    desc = (full.get("fields", {}).get("description") or "")[:300]
    print(f"  Description: {desc}")

    action = prompt_choice(
        "  Action",
        ["triage", "request_info", "close", "skip"],
        default="triage",
    )

    plan_entry = {
        "key": key,
        "summary": ticket["summary"],
        "path": "ENRICH",
        "action": action,
    }

    if action == "request_info":
        plan_entry["missing_fields"] = ticket.get("missing_fields", [])

    elif action == "triage":
        print("  Manual triage:")
        st_options = list(SERVICE_TYPES.keys())
        for i, (short, full_name) in enumerate(SERVICE_TYPES.items()):
            print(f"    {i+1}. [{short}] {full_name}")
        st_idx = input("  Service type (number or skip): ").strip()
        priority = prompt_choice("  Priority", ["Blocker", "High", "Medium", "Low"], default="Medium")
        plan_entry["service_type_idx"] = st_idx
        plan_entry["priority"] = priority

    elif action == "close":
        reason = input("  Close reason: ").strip() or "Closed during triage grooming."
        plan_entry["reason"] = reason

    return plan_entry


def run_plan(jira: JiraClient, path_filter: str):
    """Interactive plan phase: walk through tickets and build a plan file."""
    audit = load_audit()
    tickets = audit["tickets"]

    if path_filter == "auto":
        tickets = [t for t in tickets if t.get("path") == "AUTO"]
    elif path_filter == "enrich":
        tickets = [t for t in tickets if t.get("path") == "ENRICH"]

    print(f"=== PLAN PHASE ===")
    print(f"Tickets to plan: {len(tickets)} ({path_filter} path)")
    print(f"Walk through each ticket and choose an action. The plan will be saved for review before execution.\n")

    plan_entries = []

    for ticket in tickets:
        try:
            if ticket.get("path") == "AUTO":
                entry = plan_auto_ticket(jira, ticket)
            else:
                entry = plan_enrich_ticket(jira, ticket)
            plan_entries.append(entry)
        except KeyboardInterrupt:
            print("\n\nInterrupted. Saving partial plan...")
            break
        except Exception as e:
            print(f"  ERROR: {e}")
            plan_entries.append({"key": ticket["key"], "action": "error", "error": str(e)})

    # Save plan
    os.makedirs(PLANS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    plan_path = os.path.join(PLANS_DIR, f"triage_plan_{ts}.json")

    plan = {
        "type": "triage",
        "created": datetime.now(timezone.utc).isoformat(),
        "path_filter": path_filter,
        "total_entries": len(plan_entries),
        "summary": {
            "sla": sum(1 for e in plan_entries if e.get("action") == "sla"),
            "handoff": sum(1 for e in plan_entries if e.get("action") == "handoff"),
            "close": sum(1 for e in plan_entries if e.get("action") == "close"),
            "triage": sum(1 for e in plan_entries if e.get("action") == "triage"),
            "request_info": sum(1 for e in plan_entries if e.get("action") == "request_info"),
            "skip": sum(1 for e in plan_entries if e.get("action") == "skip"),
        },
        "entries": plan_entries,
    }

    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2)

    print(f"\n{'='*80}")
    print(f"Plan saved: {plan_path}")
    print(f"  Total:       {plan['total_entries']}")
    for action, count in plan["summary"].items():
        if count > 0:
            print(f"  {action:14s}: {count}")
    print(f"\nReview the plan, then run:")
    print(f"  python triage_data.py apply {plan_path}")


# ---------------------------------------------------------------------------
# APPLY PHASE: non-interactive, executes a plan file
# ---------------------------------------------------------------------------

def apply_plan(jira: JiraClient, plan_path: str):
    """Execute a previously generated plan file."""
    with open(plan_path) as f:
        plan = json.load(f)

    entries = plan["entries"]
    actionable = [e for e in entries if e.get("action") not in ("skip", "error")]

    print(f"=== APPLY PHASE ===")
    print(f"Plan: {plan_path}")
    print(f"Created: {plan['created']}")
    print(f"Entries: {plan['total_entries']} ({len(actionable)} actionable)")
    print(f"Summary: {json.dumps(plan['summary'])}")

    if not actionable:
        print("\nNothing to apply.")
        return

    confirm = input(f"\nApply {len(actionable)} actions? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    # Snapshot before changes
    keys = [e["key"] for e in actionable]
    print(f"\nTaking pre-apply snapshot ({len(keys)} tickets)...")
    snapshot_from_keys(jira, keys, label="pre_triage_apply")

    results = []
    for entry in entries:
        key = entry["key"]
        action = entry.get("action", "skip")

        if action == "skip":
            continue

        print(f"\n  [{key}] {action}: {entry.get('summary', '')[:60]}")

        try:
            if action == "sla":
                priority = entry.get("priority", "Medium")
                post_sla_comment(jira, key, priority)
                rice = entry.get("rice")
                if rice:
                    jira.add_comment(key, format_rice_comment(rice))
                print(f"    Posted SLA + RICE (priority={priority})")
                results.append({"key": key, "action": "sla", "status": "ok"})

            elif action == "handoff":
                jira_team = entry.get("jira_team", "Data Engineering")
                component = entry.get("component")
                effort = entry.get("effort_points")
                epic_link = entry.get("epic_link", "")
                stakeholder = entry.get("stakeholder", "")
                extra_comps = [component] if component else None

                move_to_dna(jira, key, team=jira_team, stakeholder_username=stakeholder,
                            components=extra_comps, effort_points=effort, epic_link=epic_link)

                rice = entry.get("rice")
                if rice:
                    jira.add_comment(key, format_rice_comment(rice))

                print(f"    Moved to DNA (team={jira_team}, component={component})")
                results.append({"key": key, "action": "handoff", "status": "ok"})

            elif action == "close":
                reason = entry.get("reason", "Closed during triage.")
                jira.add_comment(key, reason)
                close_data_ticket(jira, key)
                print(f"    Closed")
                results.append({"key": key, "action": "close", "status": "ok"})

            elif action == "request_info":
                missing = ", ".join(entry.get("missing_fields", []))
                jira.add_comment(key, f"This request is missing the following information: {missing}. "
                                 "Please update the ticket or resubmit via the Data & Analytics portal.")
                print(f"    Posted info request")
                results.append({"key": key, "action": "request_info", "status": "ok"})

            elif action == "triage":
                priority = entry.get("priority", "Medium")
                post_sla_comment(jira, key, priority)
                print(f"    Manual triage: posted SLA (priority={priority})")
                results.append({"key": key, "action": "triage", "status": "ok"})

            elif action == "error":
                continue

        except Exception as e:
            print(f"    FAIL: {e}")
            results.append({"key": key, "action": action, "status": "error", "error": str(e)})

    # Save results
    os.makedirs(CHANGES_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(CHANGES_DIR, f"triage_{ts}.json")
    with open(log_path, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "plan_file": plan_path,
            "results": results,
        }, f, indent=2)

    ok = sum(1 for r in results if r["status"] == "ok")
    errors = sum(1 for r in results if r["status"] == "error")
    print(f"\n{'='*80}")
    print(f"Apply complete: {ok} succeeded, {errors} failed")
    print(f"Change log: {log_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="DATA ticket triage (plan/apply)")
    sub = parser.add_subparsers(dest="command", required=True)

    plan_cmd = sub.add_parser("plan", help="Build a triage plan (interactive)")
    plan_cmd.add_argument("--path", choices=["auto", "enrich", "all"], default="all",
                          help="Which tickets to plan")

    apply_cmd = sub.add_parser("apply", help="Execute a triage plan")
    apply_cmd.add_argument("plan_file", help="Path to the plan JSON file")

    args = parser.parse_args()
    settings = load_settings()
    jira = JiraClient(settings.jira_base_url, settings.jira_pat)

    if args.command == "plan":
        run_plan(jira, args.path)
    elif args.command == "apply":
        apply_plan(jira, args.plan_file)


if __name__ == "__main__":
    main()
