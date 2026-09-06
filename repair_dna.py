#!/usr/bin/env python3
"""Bulk DNA ticket repair with plan/apply phases.

Usage:
    python repair_dna.py plan [--mode auto|prompted|all] [--epics-only]   # Build repair plan
    python repair_dna.py apply <plan_file> [--batch-size 10]               # Execute the plan
"""

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone

from config import load_settings
from jira_client import JiraClient
from snapshot import snapshot_from_keys
from tpm_workflow import (
    CF_TEAM, CF_STAKEHOLDER, CF_EPIC_LINK, CF_EPIC_NAME,
    VALID_TEAMS, VALID_COMPONENTS, COMPONENT_KEYWORD_MAP,
    check_dna_compliance,
)
from stakeholder_lookup import build_stakeholder_cache, load_cache, lookup_stakeholder

PLANS_DIR = os.path.join(os.path.dirname(__file__), "plans")
CHANGES_DIR = os.path.join(os.path.dirname(__file__), "changes")
AUDIT_PATH = os.path.join(os.path.dirname(__file__), "dna_audit.json")

FIELDS = [
    "summary", "issuetype", "status", "priority", "assignee", "reporter",
    "components", "story_points", "customfield_10004",
    CF_TEAM, CF_STAKEHOLDER, CF_EPIC_NAME, CF_EPIC_LINK,
]


def load_audit() -> dict:
    if not os.path.exists(AUDIT_PATH):
        print(f"Run audit_dna.py first to generate {AUDIT_PATH}")
        sys.exit(1)
    with open(AUDIT_PATH) as f:
        return json.load(f)


def suggest_components(existing_components: list[str]) -> list[str]:
    suggestions = set()
    for comp in existing_components:
        if comp in COMPONENT_KEYWORD_MAP:
            suggestions.update(COMPONENT_KEYWORD_MAP[comp])
    return sorted(suggestions - set(existing_components))


def _build_repair_comment(changes: list[tuple[str, str]]) -> str:
    lines = ["Backlog grooming \u2014 updated fields:"]
    for field, reason in changes:
        lines.append(f"* {field}: {reason}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PLAN PHASE: analyze tickets and build a plan file
# ---------------------------------------------------------------------------

def plan_auto_repairs(jira: JiraClient, tickets: list[dict], stakeholder_cache: dict) -> list[dict]:
    """Analyze tickets and generate auto-repair plan entries."""
    entries = []

    for ticket in tickets:
        key = ticket["key"]
        fields = ticket.get("fields", {})
        issue_type = fields.get("issuetype", {}).get("name", "")

        entry = {"key": key, "issue_type": issue_type, "summary": fields.get("summary", "")[:80], "updates": {}, "reasons": []}

        # Component suggestions
        existing_comps = [c.get("name", "") for c in fields.get("components", [])]
        has_official = any(c in VALID_COMPONENTS for c in existing_comps)
        if not has_official and existing_comps:
            suggested = suggest_components(existing_comps)
            if suggested:
                entry["updates"]["components"] = [{"name": c} for c in existing_comps + suggested]
                entry["reasons"].append(("Components", f"Added {', '.join(suggested)} (mapped from existing tags)"))

        # Inherit Team from Epic
        team_field = fields.get(CF_TEAM)
        team_val = team_field.get("value") if isinstance(team_field, dict) else None
        epic_link = fields.get(CF_EPIC_LINK)
        if not team_val and epic_link and issue_type != "Epic":
            try:
                epic = jira.get_issue(epic_link, fields=[CF_TEAM])
                epic_team = epic.get("fields", {}).get(CF_TEAM)
                if epic_team and isinstance(epic_team, dict):
                    entry["updates"][CF_TEAM] = epic_team
                    entry["reasons"].append(("Team", f"Set to {epic_team['value']} (from Epic {epic_link})"))
            except Exception:
                pass

        # Stakeholder from reporter
        if not fields.get(CF_STAKEHOLDER):
            reporter = fields.get("reporter", {})
            reporter_email = reporter.get("emailAddress", "") if reporter else ""
            if reporter_email and stakeholder_cache:
                info = lookup_stakeholder(reporter_email, stakeholder_cache)
                if info.get("stakeholder_name") and info.get("stakeholder_email"):
                    username = info["stakeholder_email"].split("@")[0]
                    entry["updates"][CF_STAKEHOLDER] = [{"name": username}]
                    entry["reasons"].append(("Stakeholder", f"Set to {info['stakeholder_name']} ({info['stakeholder_level']}, from reporter's org)"))

        # Inherit Components from Epic
        if not has_official and "components" not in entry["updates"] and epic_link and issue_type != "Epic":
            try:
                epic = jira.get_issue(epic_link, fields=["components"])
                epic_comps = [c.get("name", "") for c in epic.get("fields", {}).get("components", [])]
                epic_official = [c for c in epic_comps if c in VALID_COMPONENTS]
                if epic_official:
                    merged = existing_comps + [c for c in epic_official if c not in existing_comps]
                    entry["updates"]["components"] = [{"name": c} for c in merged]
                    entry["reasons"].append(("Components", f"Added {', '.join(epic_official)} (from Epic {epic_link})"))
            except Exception:
                pass

        if entry["updates"]:
            entries.append(entry)

    return entries


def plan_prompted_repairs(jira: JiraClient, tickets: list[dict]) -> list[dict]:
    """Interactive: prompt for effort points on tickets missing them."""
    entries = []

    by_team = {}
    for t in tickets:
        fields = t.get("fields", {})
        team_field = fields.get(CF_TEAM) if fields else None
        team = team_field.get("value") if isinstance(team_field, dict) else "(No Team)"
        if t.get("violations", {}).get("missing_effort"):
            by_team.setdefault(team, []).append(t)

    for team, team_tickets in sorted(by_team.items()):
        print(f"\n  Team: {team} ({len(team_tickets)} tickets missing effort)")
        for t in team_tickets[:5]:
            print(f"    {t['key']}: {t.get('fields', {}).get('summary', '')[:60]}")
        if len(team_tickets) > 5:
            print(f"    ... and {len(team_tickets) - 5} more")

        action = input(f"  Set effort for this team? [y]es / [s]kip: ").strip().lower()
        if action != "y":
            continue

        for t in team_tickets:
            key = t["key"]
            summary = t.get("fields", {}).get("summary", "")[:60]
            effort = input(f"    {key} ({summary}): effort? [1/2/3/5/8/13/skip]: ").strip()
            if effort in ("1", "2", "3", "5", "8", "13"):
                entries.append({
                    "key": key,
                    "issue_type": t.get("issue_type", ""),
                    "summary": summary,
                    "updates": {"story_points": int(effort)},
                    "reasons": [("Effort Points", f"Set to {effort} during backlog grooming")],
                })

    return entries


def run_plan(jira: JiraClient, mode: str, epics_only: bool):
    """Build a repair plan file."""
    audit = load_audit()
    all_tickets = audit.get("tickets", [])
    epic_keys = set(audit.get("repair_queue_epics", []))
    issue_keys = set(audit.get("repair_queue_issues", []))

    repair_keys = epic_keys | issue_keys
    if epics_only:
        repair_keys = epic_keys

    print(f"Loading field data for {len(repair_keys)} tickets...")
    tickets_with_fields = []
    for t in all_tickets:
        if t["key"] in repair_keys:
            full = jira.get_issue(t["key"], fields=FIELDS)
            t["fields"] = full.get("fields", {})
            tickets_with_fields.append(t)

    epics = [t for t in tickets_with_fields if t["issue_type"] == "Epic"]
    non_epics = [t for t in tickets_with_fields if t["issue_type"] != "Epic"]
    print(f"Epics: {len(epics)}, Issues: {len(non_epics)}")

    # Build stakeholder cache
    stakeholder_cache = {}
    reporter_emails = list(set(
        t["fields"]["reporter"]["emailAddress"]
        for t in tickets_with_fields
        if t.get("fields", {}).get("reporter", {}).get("emailAddress")
        and not t.get("fields", {}).get(CF_STAKEHOLDER)
    ))
    if reporter_emails:
        print(f"\nBuilding stakeholder cache for {len(reporter_emails)} reporters...")
        try:
            stakeholder_cache = build_stakeholder_cache(reporter_emails)
            found = sum(1 for v in stakeholder_cache.values() if v.get("stakeholder_name"))
            print(f"  Resolved {found}/{len(reporter_emails)} stakeholders from dim_workers")
        except Exception as e:
            print(f"  Stakeholder lookup failed: {e}")

    plan_entries = []

    # Auto repairs
    if mode in ("auto", "all"):
        print(f"\n=== Planning auto-repairs ===")
        if epics:
            print(f"  Analyzing {len(epics)} Epics...")
            plan_entries.extend(plan_auto_repairs(jira, epics, stakeholder_cache))
        if non_epics and not epics_only:
            print(f"  Analyzing {len(non_epics)} Issues...")
            plan_entries.extend(plan_auto_repairs(jira, non_epics, stakeholder_cache))

    # Prompted repairs
    if mode in ("prompted", "all") and not epics_only:
        print(f"\n=== Planning prompted repairs ===")
        plan_entries.extend(plan_prompted_repairs(jira, non_epics))

    # Manual queue
    manual_keys = []
    if mode in ("manual", "all") and not epics_only:
        planned_keys = set(e["key"] for e in plan_entries)
        manual_keys = [t["key"] for t in non_epics
                       if t["key"] not in planned_keys and t.get("violations", {}).get("has_any")]

    # Save plan
    os.makedirs(PLANS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    plan_path = os.path.join(PLANS_DIR, f"repair_plan_{ts}.json")

    plan = {
        "type": "repair",
        "created": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "epics_only": epics_only,
        "total_entries": len(plan_entries),
        "manual_review_count": len(manual_keys),
        "entries": plan_entries,
        "manual_review_keys": manual_keys,
    }
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2, default=str)

    # Summary
    update_fields = Counter()
    for e in plan_entries:
        for field in e.get("updates", {}):
            update_fields[field] += 1

    print(f"\n{'='*80}")
    print(f"Plan saved: {plan_path}")
    print(f"  Tickets to repair: {len(plan_entries)}")
    print(f"  Manual review:     {len(manual_keys)}")
    print(f"  Updates by field:")
    for field, count in update_fields.most_common():
        label = field.replace("customfield_10288", "Team").replace("customfield_36420", "Stakeholder")
        print(f"    {label}: {count}")
    print(f"\nReview the plan, then run:")
    print(f"  python repair_dna.py apply {plan_path}")

    if manual_keys:
        print(f"\n  Manual review queue ({len(manual_keys)} tickets):")
        for k in manual_keys[:10]:
            print(f"    https://jira.atl.workiva.net/browse/{k}")
        if len(manual_keys) > 10:
            print(f"    ... and {len(manual_keys) - 10} more (see plan file)")


# ---------------------------------------------------------------------------
# APPLY PHASE: execute a plan file
# ---------------------------------------------------------------------------

def apply_plan(jira: JiraClient, plan_path: str, batch_size: int):
    with open(plan_path) as f:
        plan = json.load(f)

    entries = plan["entries"]
    print(f"=== APPLY PHASE ===")
    print(f"Plan: {plan_path}")
    print(f"Created: {plan['created']}")
    print(f"Entries: {len(entries)}")

    if not entries:
        print("\nNothing to apply.")
        return

    confirm = input(f"\nApply {len(entries)} repairs? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    # Snapshot
    keys = [e["key"] for e in entries]
    print(f"\nTaking pre-apply snapshot ({len(keys)} tickets)...")
    snapshot_from_keys(jira, keys, label="pre_repair_apply")

    results = []
    for i, entry in enumerate(entries, 1):
        key = entry["key"]
        updates = entry.get("updates", {})
        reasons = entry.get("reasons", [])

        if not updates:
            continue

        try:
            jira.update_issue(key, updates)
            if reasons:
                jira.add_comment(key, _build_repair_comment(reasons))
            print(f"  [{i}/{len(entries)}] {key} OK: {list(updates.keys())}")
            results.append({"key": key, "status": "ok", "fields": list(updates.keys())})
        except Exception as e:
            print(f"  [{i}/{len(entries)}] {key} FAIL: {e}")
            results.append({"key": key, "status": "error", "error": str(e)})

        if i % batch_size == 0:
            print(f"  ... pausing after batch {i // batch_size}...")
            time.sleep(1)

    # Save results
    os.makedirs(CHANGES_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(CHANGES_DIR, f"changes_{ts}.json")
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
    parser = argparse.ArgumentParser(description="DNA ticket repair (plan/apply)")
    sub = parser.add_subparsers(dest="command", required=True)

    plan_cmd = sub.add_parser("plan", help="Build a repair plan")
    plan_cmd.add_argument("--mode", choices=["auto", "prompted", "all"], default="all")
    plan_cmd.add_argument("--epics-only", action="store_true")

    apply_cmd = sub.add_parser("apply", help="Execute a repair plan")
    apply_cmd.add_argument("plan_file", help="Path to the plan JSON file")
    apply_cmd.add_argument("--batch-size", type=int, default=10)

    args = parser.parse_args()
    settings = load_settings()
    jira = JiraClient(settings.jira_base_url, settings.jira_pat)

    if args.command == "plan":
        run_plan(jira, args.mode, args.epics_only)
    elif args.command == "apply":
        apply_plan(jira, args.plan_file, args.batch_size)


if __name__ == "__main__":
    main()
