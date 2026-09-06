#!/usr/bin/env python3
"""Audit open DATA tickets: conformance scoring and two-path classification."""

import json
import os
import re
import sys

from clients.config import load_settings
from clients.jira_client import JiraClient
from core.tpm_workflow import (
    CF_SERVICE_TYPE, CF_TEAMS_IMPACTED, CF_BIZ_PRIORITY,
    CF_PRIMARY_SOLUTION, CF_EXEC_SPONSOR, CF_MILESTONE, CF_REQUEST_TYPE,
    assess_data_ticket, classify_conformance,
)

FIELDS = [
    "summary", "issuetype", "status", "priority", "created", "updated",
    "description", "comment", "assignee",
    CF_SERVICE_TYPE, CF_TEAMS_IMPACTED, CF_BIZ_PRIORITY,
    CF_PRIMARY_SOLUTION, CF_EXEC_SPONSOR, CF_MILESTONE, CF_REQUEST_TYPE,
]


def check_dna_crossref(comments: list[dict]) -> list[str]:
    """Scan comments for DNA-xxx references."""
    refs = set()
    for comment in comments:
        body = comment.get("body", "")
        refs.update(re.findall(r"DNA-\d+", body))
    return sorted(refs)


def main():
    settings = load_settings()
    jira = JiraClient(settings.jira_base_url, settings.jira_pat)

    print("Fetching open DATA tickets...")
    issues = jira.search_all(
        'project = DATA AND status != Closed AND status != Resolved AND status != Canceled AND status != Done ORDER BY key DESC',
        fields=FIELDS,
    )
    print(f"Found {len(issues)} open/active tickets\n")

    results = []
    auto_count = 0
    enrich_count = 0

    for issue in issues:
        key = issue["key"]
        fields = issue["fields"]
        assessment = assess_data_ticket(fields, issue_key=key)
        conformance = assessment["conformance"]

        comments = fields.get("comment", {}).get("comments", [])
        dna_refs = check_dna_crossref(comments)

        result = {
            "key": key,
            "summary": fields.get("summary", ""),
            "issue_type": fields.get("issuetype", {}).get("name", ""),
            "status": fields.get("status", {}).get("name", ""),
            "conformance_score": conformance["score"],
            "path": conformance["path"],
            "service_type": assessment["service_type"],
            "biz_priority": assessment["biz_priority"],
            "jira_priority": assessment["jira_priority"],
            "tier": assessment["tier"],
            "dna_crossrefs": dna_refs,
            "has_dna_crossref": len(dna_refs) > 0,
            "missing_fields": [k for k, v in conformance["checks"].items() if not v],
        }
        results.append(result)

        if conformance["path"] == "AUTO":
            auto_count += 1
        else:
            enrich_count += 1

    # Console output
    print(f"{'Key':12s} {'Type':18s} {'Status':22s} {'Score':6s} {'Path':8s} {'DNA Ref':8s} {'Service Type':40s}")
    print("-" * 120)
    for r in results:
        st_short = r["service_type"][:38] if r["service_type"] else "(empty)"
        ref = ",".join(r["dna_crossrefs"]) if r["dna_crossrefs"] else "-"
        print(f'{r["key"]:12s} {r["issue_type"]:18s} {r["status"]:22s} {r["conformance_score"]}/5    {r["path"]:8s} {ref:8s} {st_short}')

    print(f"\n=== Summary ===")
    print(f"  Total open:     {len(results)}")
    print(f"  AUTO path:      {auto_count} (conformance 4-5/5)")
    print(f"  ENRICH path:    {enrich_count} (conformance 0-3/5)")
    print(f"  Has DNA ref:    {sum(1 for r in results if r['has_dna_crossref'])}")

    by_type = {}
    for r in results:
        by_type.setdefault(r["issue_type"], []).append(r)
    print(f"\n  By Issue Type:")
    for itype, items in sorted(by_type.items()):
        auto = sum(1 for i in items if i["path"] == "AUTO")
        print(f"    {itype}: {len(items)} ({auto} auto, {len(items)-auto} enrich)")

    # Save JSON
    from project_root import PROJECT_ROOT
    output_path = os.path.join(PROJECT_ROOT, "data_audit.json")
    with open(output_path, "w") as f:
        json.dump({"total": len(results), "auto": auto_count, "enrich": enrich_count, "tickets": results}, f, indent=2)
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()
