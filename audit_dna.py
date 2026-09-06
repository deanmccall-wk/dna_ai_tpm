#!/usr/bin/env python3
"""Full DNA ticket compliance audit against DnA Ticket Requirements."""

import csv
import json
import os
import sys
from collections import Counter

from config import load_settings
from jira_client import JiraClient
from tpm_workflow import (
    CF_TEAM, CF_STAKEHOLDER, CF_EPIC_NAME, CF_EPIC_LINK,
    VALID_TEAMS, VALID_COMPONENTS, check_dna_compliance,
)

FIELDS = [
    "summary", "issuetype", "status", "priority", "updated", "assignee",
    "components", "story_points", "customfield_10004",
    CF_TEAM, CF_STAKEHOLDER, CF_EPIC_NAME, CF_EPIC_LINK,
]


def main():
    settings = load_settings()
    jira = JiraClient(settings.jira_base_url, settings.jira_pat)

    print("Fetching open DNA tickets...")
    issues = jira.search_all(
        "project = DNA AND statusCategory != Done ORDER BY key ASC",
        fields=FIELDS,
    )
    print(f"Total open: {len(issues)}\n")

    results = []
    violation_counts = Counter()
    by_type = Counter()
    by_team = Counter()
    violations_by_team = {}

    for issue in issues:
        compliance = check_dna_compliance(issue)
        results.append(compliance)

        itype = compliance["issue_type"]
        team = compliance["team"] or "(No Team)"
        by_type[itype] += 1
        by_team[team] += 1

        for vname, is_violated in compliance["violations"].items():
            if vname == "has_any":
                continue
            if is_violated:
                violation_counts[vname] += 1
                violations_by_team.setdefault(team, Counter())[vname] += 1

    # Console summary
    has_violations = sum(1 for r in results if r["violations"]["has_any"])
    clean = len(results) - has_violations
    print(f"=== Compliance Summary ===")
    print(f"  Total tickets:    {len(results)}")
    print(f"  Clean:            {clean} ({clean*100//len(results)}%)")
    print(f"  Has violations:   {has_violations} ({has_violations*100//len(results)}%)")

    print(f"\n=== Violation Counts ===")
    for vname, count in violation_counts.most_common():
        print(f"  {vname:30s}: {count:>5} ({count*100//len(results)}%)")

    print(f"\n=== By Issue Type ===")
    for itype, count in by_type.most_common():
        type_violations = sum(1 for r in results if r["issue_type"] == itype and r["violations"]["has_any"])
        print(f"  {itype:20s}: {count:>5} total, {type_violations} with violations")

    print(f"\n=== Top 10 Teams by Violation Count ===")
    team_violation_totals = {t: sum(v.values()) for t, v in violations_by_team.items()}
    for team, total in sorted(team_violation_totals.items(), key=lambda x: -x[1])[:10]:
        details = violations_by_team[team]
        top = ", ".join(f"{k}={v}" for k, v in details.most_common(3))
        print(f"  {team:30s}: {total:>5} violations ({top})")

    # Repair queue: Epics first, then issues by team
    epics = [r for r in results if r["issue_type"] == "Epic" and r["violations"]["has_any"]]
    non_epics = [r for r in results if r["issue_type"] != "Epic" and r["violations"]["has_any"]]
    non_epics.sort(key=lambda r: (r["team"] or "zzz", r["key"]))

    print(f"\n=== Repair Queue ===")
    print(f"  Epics to repair first: {len(epics)}")
    print(f"  Issues to repair:      {len(non_epics)}")

    # Save CSV
    csv_path = os.path.join(os.path.dirname(__file__), "dna_audit.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        violation_fields = ["missing_team", "invalid_team", "missing_stakeholder",
                            "missing_effort", "missing_official_component",
                            "missing_epic_link", "missing_epic_name"]
        writer.writerow(["key", "issue_type", "team", "status"] + violation_fields + ["has_any"])
        for r in results:
            writer.writerow([
                r["key"], r["issue_type"], r["team"], r["status"],
            ] + [r["violations"].get(v, False) for v in violation_fields] + [r["violations"]["has_any"]])
    print(f"\nCSV saved: {csv_path}")

    # Save JSON with repair queue
    json_path = os.path.join(os.path.dirname(__file__), "dna_audit.json")
    with open(json_path, "w") as f:
        json.dump({
            "total": len(results),
            "clean": clean,
            "has_violations": has_violations,
            "violation_counts": dict(violation_counts),
            "repair_queue_epics": [r["key"] for r in epics],
            "repair_queue_issues": [r["key"] for r in non_epics],
            "tickets": results,
        }, f, indent=2)
    print(f"JSON saved: {json_path}")


if __name__ == "__main__":
    main()
