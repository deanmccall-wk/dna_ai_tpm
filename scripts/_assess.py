#!/usr/bin/env python3
"""Triage assessment for DATA-2472."""
import os, json, re
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from clients.config import load_settings
from clients.jira_client import JiraClient
from core.tpm_workflow import (
    assess_data_ticket, recommend_team, resolve_virtual_team,
    propose_summary, SLA_COMMENTS, is_deletion_ticket,
)
from core.rice_scoring import calculate_rice
from core.asset_lookup import lookup_assets_for_ticket, format_asset_context

s = load_settings()
jira = JiraClient(s.jira_base_url, s.jira_pat)

issue = jira.get_issue("DATA-2472")
fields = issue["fields"]

print("=== DATA-2472 Assessment ===")
print(f"Summary: {fields.get('summary', '')}")
print(f"Type: {fields.get('issuetype', {}).get('name', '')}")
print(f"Status: {fields.get('status', {}).get('name', '')}")
print(f"Priority: {fields.get('priority', {}).get('name', '')}")
reporter = fields.get("reporter") or {}
print(f"Reporter: {reporter.get('displayName', '')} ({reporter.get('name', '')})")
print(f"Created: {fields.get('created', '')[:10]}")
assignee = fields.get("assignee") or {}
print(f"Assignee: {assignee.get('displayName', 'Unassigned')}")
print()

if is_deletion_ticket(fields):
    print("*** DELETION TICKET ***\n")

desc = (fields.get("description") or "")[:1200]
print(f"Description:\n{desc}\n")

assessment = assess_data_ticket(fields, "DATA-2472")
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
print()

rice = calculate_rice(fields)
print(f"RICE Score: {rice['rice_score']} ({rice['priority_bucket']})")
print(f"  Reach={rice['reach']} Impact={rice['impact']} Confidence={int(rice['confidence']*100)}% Effort={rice['effort']}")
print()

rec = recommend_team(fields)
resolved = resolve_virtual_team(rec["team"])
print(f"Team: {rec['team']} ({rec['confidence']} - {rec['reason']})")
if resolved["component"]:
    print(f"  Jira: Team={resolved['team']}, Component={resolved['component']}")
else:
    print(f"  Jira: Team={resolved['team']}")
print()

proposed = propose_summary(fields)
if proposed:
    print(f"Proposed Summary: {proposed}\n")

ctx = lookup_assets_for_ticket(fields, use_github=False)
if ctx.get("asset_names"):
    print("Asset Lookup:")
    print(format_asset_context(ctx))
    print()

comments = jira.session.get(jira._url("/issue/DATA-2472/comment")).json()
dna_refs = []
for c in comments.get("comments", []):
    refs = re.findall(r"DNA-\d+", c.get("body", ""))
    dna_refs.extend(refs)
if dna_refs:
    print(f"Existing DNA refs: {list(set(dna_refs))}")
print(f"Comments: {len(comments.get('comments', []))}")
for c in comments.get("comments", [])[:5]:
    author = c.get("author", {}).get("displayName", "")
    body = c.get("body", "")[:250]
    print(f"  [{author}] {body}\n")
