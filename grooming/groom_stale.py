#!/usr/bin/env python3
"""Stale DNA ticket grooming with plan/apply phases.

Usage:
    python groom_stale.py plan [--min-days 90]    # Interactive: build a grooming plan
    python groom_stale.py apply <plan_file>        # Execute the plan
    python groom_stale.py report [--min-days 90]   # Just print stats, no plan
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from clients.config import load_settings
from clients.jira_client import JiraClient
from safety.snapshot import snapshot_from_keys
from core.tpm_workflow import CF_TEAM, VALID_TEAMS

from project_root import PROJECT_ROOT

PLANS_DIR = os.path.join(PROJECT_ROOT, "plans")
CHANGES_DIR = os.path.join(PROJECT_ROOT, "changes")

FIELDS = [
    "summary", "issuetype", "status", "priority", "updated", "assignee",
    CF_TEAM,
]


def classify_stale(days: int, status: str, assignee: str) -> str:
    if days >= 365 and status == "Open" and not assignee:
        return "auto_close"
    if days >= 180:
        return "review"
    if days >= 90:
        return "check_in"
    return "keep"


def fetch_stale(jira: JiraClient, min_days: int) -> list[dict]:
    print(f"Fetching open DNA tickets...")
    issues = jira.search_all(
        "project = DNA AND statusCategory != Done ORDER BY updated ASC",
        fields=FIELDS,
    )
    print(f"Total open: {len(issues)}")

    now = datetime.now(timezone.utc)
    stale = []

    for issue in issues:
        f = issue["fields"]
        updated_str = f.get("updated", "")[:19]
        updated = datetime.fromisoformat(updated_str).replace(tzinfo=timezone.utc)
        days = (now - updated).days

        if days < min_days:
            continue

        team_field = f.get(CF_TEAM)
        team = team_field.get("value") if isinstance(team_field, dict) else ""
        assignee = (f.get("assignee") or {}).get("displayName", "")

        tier = classify_stale(days, f["status"]["name"], assignee)
        stale.append({
            "key": issue["key"],
            "summary": f.get("summary", ""),
            "issue_type": f["issuetype"]["name"],
            "status": f["status"]["name"],
            "team": team or "(No Team)",
            "assignee": assignee or "Unassigned",
            "days_stale": days,
            "tier": tier,
        })

    return stale


def print_summary(stale: list[dict], min_days: int):
    print(f"\nStale tickets ({min_days}+ days): {len(stale)}")
    tier_counts = Counter(s["tier"] for s in stale)
    for tier in ["auto_close", "review", "check_in"]:
        print(f"  {tier}: {tier_counts.get(tier, 0)}")

    print(f"\nBy team:")
    for team, count in Counter(s["team"] for s in stale).most_common():
        print(f"  {team}: {count}")

    print(f"\nBy type:")
    for itype, count in Counter(s["issue_type"] for s in stale).most_common():
        print(f"  {itype}: {count}")


# ---------------------------------------------------------------------------
# PLAN PHASE
# ---------------------------------------------------------------------------

def run_plan(jira: JiraClient, min_days: int):
    stale = fetch_stale(jira, min_days)
    print_summary(stale, min_days)

    print(f"\n=== PLAN PHASE ===")
    print(f"Walk through stale tickets by tier and team. Choose an action for each.\n")

    plan_entries = []

    for tier_name, tier_label in [("auto_close", "AUTO-CLOSE (365+d, Open, Unassigned)"),
                                   ("review", "REVIEW (180+d)"),
                                   ("check_in", "CHECK-IN (90+d)")]:
        tier_tickets = [s for s in stale if s["tier"] == tier_name]
        if not tier_tickets:
            continue

        print(f"\n--- {tier_label}: {len(tier_tickets)} tickets ---")

        by_team = {}
        for t in tier_tickets:
            by_team.setdefault(t["team"], []).append(t)

        for team, team_tickets in sorted(by_team.items()):
            print(f"\n  Team: {team} ({len(team_tickets)} tickets)")
            for t in team_tickets:
                print(f"    {t['key']:10s} | {t['days_stale']:>4d}d | {t['status']:12s} | {t['assignee']:20s} | {t['summary'][:50]}")

            action = input(f"\n  Action for {team} batch: [c]lose all / [s]kip / [r]eview individually: ").strip().lower()

            if action == "c":
                for t in team_tickets:
                    plan_entries.append({"key": t["key"], "action": "close", "tier": tier_name,
                                         "days_stale": t["days_stale"], "summary": t["summary"][:80]})
            elif action == "r":
                for t in team_tickets:
                    print(f"\n    {t['key']}: {t['summary']}")
                    print(f"      {t['days_stale']}d stale | {t['status']} | {t['assignee']}")
                    ind = input("      [c]lose / [s]kip / [p]ing assignee: ").strip().lower()
                    if ind == "c":
                        plan_entries.append({"key": t["key"], "action": "close", "tier": tier_name,
                                             "days_stale": t["days_stale"], "summary": t["summary"][:80]})
                    elif ind == "p" and t["assignee"] != "Unassigned":
                        plan_entries.append({"key": t["key"], "action": "ping", "tier": tier_name,
                                             "days_stale": t["days_stale"], "assignee": t["assignee"],
                                             "summary": t["summary"][:80]})
                    else:
                        plan_entries.append({"key": t["key"], "action": "skip", "tier": tier_name})
            else:
                for t in team_tickets:
                    plan_entries.append({"key": t["key"], "action": "skip", "tier": tier_name})

    # Save plan
    os.makedirs(PLANS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    plan_path = os.path.join(PLANS_DIR, f"groom_plan_{ts}.json")

    summary = Counter(e["action"] for e in plan_entries)
    plan = {
        "type": "groom_stale",
        "created": datetime.now(timezone.utc).isoformat(),
        "min_days": min_days,
        "total_entries": len(plan_entries),
        "summary": dict(summary),
        "entries": plan_entries,
    }
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2)

    print(f"\n{'='*80}")
    print(f"Plan saved: {plan_path}")
    print(f"  Close: {summary.get('close', 0)}, Ping: {summary.get('ping', 0)}, Skip: {summary.get('skip', 0)}")
    print(f"\nReview the plan, then run:")
    print(f"  python groom_stale.py apply {plan_path}")


# ---------------------------------------------------------------------------
# APPLY PHASE
# ---------------------------------------------------------------------------

def apply_plan(jira: JiraClient, plan_path: str):
    with open(plan_path) as f:
        plan = json.load(f)

    entries = plan["entries"]
    actionable = [e for e in entries if e["action"] in ("close", "ping")]

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

    # Snapshot
    keys = [e["key"] for e in actionable]
    print(f"\nTaking pre-apply snapshot ({len(keys)} tickets)...")
    snapshot_from_keys(jira, keys, label="pre_groom_apply")

    results = []
    for entry in entries:
        key = entry["key"]
        action = entry["action"]

        if action == "skip":
            continue

        try:
            if action == "close":
                days = entry.get("days_stale", "?")
                comment = (f"Closed during backlog grooming — no activity in {days}+ days. "
                           "Reopen or create a new ticket if this work is still needed.")
                jira.add_comment(key, comment)
                transitions = jira.get_transitions(key)
                close_t = next((t for t in transitions if t["name"].lower() in ("done", "closed", "close", "resolve")), None)
                if close_t:
                    jira.transition_issue(key, close_t["id"])
                    print(f"  [{key}] Closed ({days}d stale)")
                    results.append({"key": key, "action": "close", "status": "ok"})
                else:
                    print(f"  [{key}] No close transition available")
                    results.append({"key": key, "action": "close", "status": "no_transition"})

            elif action == "ping":
                days = entry.get("days_stale", "?")
                msg = f"This ticket has had no updates in {days} days. Is this still active? Will be closed in 7 days if no response."
                jira.add_comment(key, msg)
                print(f"  [{key}] Pinged {entry.get('assignee', '?')}")
                results.append({"key": key, "action": "ping", "status": "ok"})

        except Exception as e:
            print(f"  [{key}] FAIL: {e}")
            results.append({"key": key, "action": action, "status": "error", "error": str(e)})

    # Save results
    os.makedirs(CHANGES_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(CHANGES_DIR, f"groom_{ts}.json")
    with open(log_path, "w") as f:
        json.dump({"timestamp": datetime.now(timezone.utc).isoformat(), "plan_file": plan_path, "results": results}, f, indent=2)

    ok = sum(1 for r in results if r["status"] == "ok")
    errors = sum(1 for r in results if r["status"] == "error")
    print(f"\n{'='*80}")
    print(f"Apply complete: {ok} succeeded, {errors} failed")
    print(f"Change log: {log_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Stale DNA ticket grooming (plan/apply)")
    sub = parser.add_subparsers(dest="command", required=True)

    plan_cmd = sub.add_parser("plan", help="Build a grooming plan (interactive)")
    plan_cmd.add_argument("--min-days", type=int, default=90)

    apply_cmd = sub.add_parser("apply", help="Execute a grooming plan")
    apply_cmd.add_argument("plan_file", help="Path to the plan JSON file")

    report_cmd = sub.add_parser("report", help="Print stale ticket stats only")
    report_cmd.add_argument("--min-days", type=int, default=90)

    args = parser.parse_args()
    settings = load_settings()
    jira = JiraClient(settings.jira_base_url, settings.jira_pat)

    if args.command == "plan":
        run_plan(jira, args.min_days)
    elif args.command == "apply":
        apply_plan(jira, args.plan_file)
    elif args.command == "report":
        stale = fetch_stale(jira, args.min_days)
        print_summary(stale, args.min_days)
        report_path = os.path.join(PROJECT_ROOT, "stale_report.json")
        with open(report_path, "w") as f:
            json.dump({"min_days": args.min_days, "total": len(stale),
                        "tiers": dict(Counter(s["tier"] for s in stale)), "tickets": stale}, f, indent=2)
        print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
