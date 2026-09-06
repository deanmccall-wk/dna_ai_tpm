# DATA Queue Health Update — Data & Analytics

## Queue Summary

| Status | Count | Notes |
|---|---|---|
| Closed / Done | 223 | Terminal — no further action required |
| Open | 23 | All Data Deletion tickets (separate process) |
| Waiting for Support | 8 | Triaged, assigned, awaiting team action |
| Waiting for Customer | 8 | Triaged, awaiting requester response |
| Pending | 1 | Pipeline staleness issue (FCT_FORECAST_HISTORY) |
| **Total** | **263** | |

---

## Triage Impact

- **89 tickets bulk-closed** — 48 Resolved and 41 Canceled tickets moved to terminal status. These were completed or withdrawn requests with no remaining action. No active requests were affected.
- **44 tickets individually triaged** — each investigated with Snowflake data verification, Atlan asset lookup, related ticket search, and reporter validation:
  - 10 closed as stale or resolved
  - 8 moved to Waiting for Customer with specific questions
  - 8 handed off to DNA (Analytics Engineering, Data Operations, CPX Insights) with full triage context
  - 8 assigned within DATA (Waiting for Support) with investigation notes
- **Active queue reduced to 17 non-deletion tickets** across Waiting for Support, Waiting for Customer, and Pending
- **23 Data Deletion tickets** remain Open — these follow a separate deletion process

---

## Risk Mitigation

- The 89 bulk-closed tickets were already in terminal states (Resolved/Canceled) — no active work was stopped. The closure is hygiene, not triage.
- All 44 individually triaged tickets have pre-change snapshots and documented triage comments.
- Two tickets were inadvertently closed early in the process before safety controls were hardened; both had assignees set and the process rules were updated to prevent recurrence.
- A stakeholder heads-up was posted to Slack before closure notifications arrived in inboxes.
- A triage runbook and tooling are in place for ongoing queue hygiene so this backlog does not rebuild.

---

## AI-Assisted Triage Tooling

A Python tooling suite (`dna_ai_tpm`) was used throughout the triage effort, orchestrated through Cortex Code (Snowflake's AI IDE). Key capabilities:

- **Automated assessment** — Conformance scoring, RICE prioritization, team routing recommendations, and Atlan asset discovery
- **Cross-system investigation** — Snowflake queries (RBAC grant chains, data availability, employee lookups), Atlan lineage, AWS QuickSight dashboard permissions, Jira related ticket search
- **Safety controls** — Pre-change ticket snapshots, rollback capability, change logging
- **Standardized output** — 10-point triage comment standard with Jira wiki markup templates, estimated RICE in separate internal comments

Triage runbook published to Confluence: [DATA Queue Triage Runbook — Data Operations](https://wiki.atl.workiva.net/spaces/BT/pages/530849232)

---

## Next Steps

1. **DNA backlog grooming** — Large number of stale tickets to review, guided by the triage runbook
2. **Jira dashboard** — For ongoing queue health visibility
3. **Data Deletion routing** — Process the 23 open deletion tickets through the deletion workflow
