# COCO.md - Cortex Code Project Instructions

This file is read automatically by Cortex Code when opening this repository.
It encodes the triage rules, safety mechanisms, and conventions that the AI
assistant must follow when assisting any TPM with DATA/DNA ticket workflows.

## Project Overview

This is a TPM tooling suite for triaging incoming Data & Analytics requests.
Tickets arrive in the **DATA** Jira project (JSM service desk) and are either
resolved at the desk, moved to **Waiting for Customer**, or handed off to the
**DNA** project (engineering execution).

Primary operational reference: `docs/triage_runbook.md`

## Triage Rules (Non-Negotiable)

1. **Never resolve, close, or transition tickets without explicit TPM confirmation.** JSM tickets cannot be reopened once Closed. Post comments and update fields only. Let the TPM decide on status changes.

2. **Never post Jira comments without presenting them to the TPM for review first.** Compose the full comment, display it in conversation, and wait for approval before calling the API.

3. **Always create a snapshot before any changes.** Use `make snapshot KEY=<key>` or `safety/snapshot.py`. The JiraClient enforces this -- writes will fail without a snapshot.

4. **Never post RICE scores to Jira.** Calculate RICE internally for prioritization and present it in conversation, but omit it entirely from Jira comments. RICE on tickets causes confusion.

5. **Always include Atlan links for every Snowflake object referenced.** Use `scripts/lookup_asset.py` to get GUIDs. In Jira comments: `[View in Atlan|https://workiva.atlan.com/assets/<guid>/overview]`. Never reference a data asset without its Atlan link.

6. **Never recommend LAKE_PROD tables or views.** Lake layer is raw/staging data not intended for consumption. Prefer GOLD_PROD first, then SILVER_PROD.

7. **Always update generic summaries.** Replace "General Request" with a descriptive title during triage.

8. **Never auto-advance to the next ticket.** Present findings, wait for the TPM to direct you to the next ticket.

9. **Self-service is always preferred** over data exports or routing to a team.

10. **Verify technical statements before posting.** Do not post information you are uncertain about.

## Safety Mechanisms

- **Snapshot gate:** JiraClient blocks writes if no snapshot exists. Use `jira.bypass_snapshot(key)` only for just-created tickets.
- **Comment validator:** `core/comment_validator.py` checks required sections before posting.
- **Triage checklists:** `core/triage_checklist.py` enforces pre-change, pre-post, and post-action checklists.
- **Dry-run mode:** `JiraClient(base_url, pat, dry_run=True)` logs without executing.
- **Change log:** Every action logged to `changes/` directory.
- **Rollback:** `safety/rollback.py restore` or `safety/rollback.py undo`.

## Common Commands

```bash
make assess KEY=DATA-XXXX       # Triage assessment (conformance, RICE, team, assets)
make snapshot KEY=DATA-XXXX     # Snapshot before changes
make lookup ARGS="dim_workers"  # Atlan asset search
make test                       # Run all 54 tests
make verify                     # Test Jira + Confluence auth
```

For ad-hoc Atlan lookups during triage:
```bash
.venv/bin/python scripts/lookup_asset.py <asset_name> [--json]
```

## Jira Project Conventions

- **DATA** = JSM service desk (intake). Issue types: Service Request, Task.
- **DNA** = Standard Jira (engineering execution). Issue types: Story, Task, Epic, Bug.
- JSM tickets **cannot be moved via the REST API**. Handoff to DNA requires a manual Jira UI move, then API field-set via `set_dna_fields()`.
- Use "Data Operations" as the team value for ops tickets, not "Data Engineering".

### Valid Teams
Data Engineering, Analytics Engineering, BI & Consumption, Data Science,
Data & Analytics, Data Operations, Data Platform & AI

### SLA Mapping
| Business Priority | Jira Priority | SLA |
|-------------------|---------------|-----|
| System Outage / Production Blocker | Blocker | Reviewed immediately |
| Fixed Deadline / Upcoming Milestone | High | Reviewed over the next business day |
| Standard Business Operation | Medium | Reviewed in 2-3 business days |
| Nice-to-have / Backlog | Low | Reviewed in 5 business days |

## Triage Comment Structure

Every triage comment should include applicable items from this list:
1. Request summary
2. Investigation results (Snowflake, Atlan, related tickets)
3. Atlan links for all referenced Snowflake objects
4. Self-service path (if the requester can resolve it themselves)
5. Role recommendation (if Snowflake access is needed)
6. Example SQL (when helpful)
7. Next steps for the requester or assigned team

Do NOT include: RICE scores, conformance scores, team recommendation. These are for internal prioritization only.

## Investigation Patterns

### Every Ticket
1. Related ticket search: `project IN (DATA, DNA) AND text ~ "<terms>"`
2. Reporter lookup via `GOLD_PROD.MARTS.DIM_WORKERS`
3. Asset search via `scripts/lookup_asset.py` or `scripts/_assess.py`

### By Type
- **Data availability:** Check INFORMATION_SCHEMA.COLUMNS in GOLD_PROD and SILVER_PROD
- **Access/permissions:** `SHOW GRANTS ON <object>`, trace role chain
- **Data quality:** Query the table, check Atlan lineage for upstream
- **Dashboard enhancement:** Identify owner, verify data availability in Gold layer

## Environment Setup

```bash
cp .env.example .env    # Edit with your tokens
make setup              # Creates .venv, installs requirements.txt
make verify             # Tests auth
```

Required tokens: Jira PAT, Atlan API token.
Optional: Confluence PAT (runbook publishing), GitHub PAT (code search), Redshift creds (deletion only).
