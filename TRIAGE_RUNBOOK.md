# DnA Triage Runbook — Data Operations

## Overview

This runbook describes the daily triage process for incoming Data & Analytics requests. Tickets arrive in the **DATA** Jira project (service desk) and are either resolved at the desk or moved to the **DNA** project (engineering).

**Who:** Data Operations team
**When:** Daily (check the queue each morning)
**Tools:** Python scripts in `~/Documents/dna_ai_tpm/`

## Setup (First Time)

```bash
cd ~/Documents/dna_ai_tpm
cp .env.example .env
# Edit .env with your Jira and Confluence PATs
source .venv/bin/activate
python verify_connection.py
```

## Daily Triage

### 0. Deletion Tickets

Data deletion tickets (from SaaS Ops) are automatically detected during triage and routed to the deletion process. They skip standard triage.

- **Runbook:** [Customer Data Deletion — Data Operations Runbook](https://wiki.atl.workiva.net/spaces/BT/pages/530849217)
- **Automation:** `python verify_deletion.py <ticket_key> --post --close`
- **Indicators:** Summary contains "Data Deletion", "Delete End Client Data", "Certificate of Destruction"

### 1. Check the Queue

```bash
source .venv/bin/activate
python audit_data.py
```

This fetches all open DATA tickets and classifies them into two paths:

- **AUTO** (4-5/5 form fields present) — the requester used the portal form. These can be triaged quickly.
- **ENRICH** (0-3/5 form fields present) — the ticket was created directly in Jira or the form was only partially filled. These need manual attention.

The output shows each ticket with its conformance score, inferred priority, service type, and whether a DNA cross-reference already exists.

### 2. Triage the AUTO Path

```bash
python triage_data.py plan --path auto
```

For each conforming ticket you will see:

```
================================================================================
[AUTO] DATA-2492: Add ARR columns to subscription reporting model
  Service Type: I need to make changes to the existing service (...)
  Biz Priority: Fixed Deadline / Upcoming Milestone
  Jira Priority: High -> SLA: Reviewed over the next business day.
  Tier: 3 (Handoff to DNA)
  RICE Score: 3.13 (High) [R=5 I=1.88 C=80% E=3]

  Action (sla/handoff/close/skip) [handoff]:
```

**Decision Guide:**

| Tier | Service Type | Default Action | What Happens |
|------|-------------|----------------|--------------|
| 1 | Access / Permissions | `sla` | Post SLA + RICE comments, resolve at desk |
| 1 | Business Question | `sla` | Post SLA + RICE comments, resolve at desk |
| 2 | Troubleshooting | `sla` or `handoff` | If quick fix: resolve. If engineering needed: move to DNA |
| 2 | Other / General | `sla` or `handoff` | Use judgment based on description |
| 3 | Build New | `handoff` | Move to DNA |
| 3 | Change Existing | `handoff` | Move to DNA |
| 3 | ML / AI | `handoff` | Move to DNA |

**When you choose `handoff`:**

You will be prompted for the DNA ticket fields:

| Prompt | What to enter |
|--------|---------------|
| Team | The engineering team that will do the work. Pick from: Data Engineering, Analytics Engineering, BI, Data Science, Data & Analytics, Data Operations, Data Platform and AI |
| Effort points | Estimated size: 1 (XS/1 day), 2 (S/2-3 days), 3 (M/4-5 days), 5 (L/2 weeks), 8 (XL/1-2 months), 13 (XXL/>2 months). Type `skip` if unsure. |
| Epic link | The DNA Epic this work falls under (e.g., DNA-5472). Type `skip` if unsure. |
| Stakeholder | Jira username of the Director+ stakeholder (e.g., victoria.zhang). Type `skip` to auto-infer from reporter's org. |

**Handoff is a two-phase process** because the DATA project is Jira Service Management (JSM) and the DNA project is standard Jira. The REST API cannot move issues between these project types.

**Phase 1 — Plan:** The script records the move instructions and planned DNA fields.

**Phase 2 — Apply:** During apply, the script will:
1. Display move instructions for each handoff ticket
2. Pause and ask you to move the ticket manually in the Jira UI:
   - Open the ticket → click **Move** (top-right menu or **•••** → **Move**)
   - Target project: **DNA**
   - **Set issue type to Story** (Service Request does not exist in DNA — the wizard will show a dropdown; select **Story**)
   - Leave other fields as-is in the wizard — the API will set them in the next step
   - Complete the wizard and note the new DNA key (e.g., DNA-6103)
3. Prompt you for the new DNA key
4. Set all DNA fields via the API on the new key (Team, Components, Priority, Stakeholder, Effort, Epic Link)
5. Post a RICE score comment and a triage summary comment

If you type `skip` instead of a DNA key, the ticket is skipped — you can run `set_dna_fields` later.

**Issue Type Mapping (DATA → DNA):**

| DATA Type | DNA Type |
|-----------|----------|
| Service Request | **Story** |
| Task | Task |
| Epic | Epic |
| Sub-task | Sub-task |

### 3. Triage the ENRICH Path

```bash
python triage_data.py plan --path enrich
```

For each non-conforming ticket:

```
================================================================================
[ENRICH] DATA-2491: [Data Deletion] Discover Financial Services - DNA
  Issue Type: Task
  Status: Open
  Missing: service_type, teams_impacted, biz_priority, primary_solution
  Description: Please delete all Discover Financial Services data from the DNA...

  Action (triage/request_info/close/skip) [triage]:
```

**Decision Guide:**

| Situation | Action |
|-----------|--------|
| You understand the request and can classify it | `triage` — set service type and priority manually, then handoff or resolve |
| The request is unclear or missing critical info | `request_info` — posts a comment asking the requester to update |
| The ticket is a duplicate or no longer relevant | `close` — enter a reason |
| You want to come back to it later | `skip` |

### 4. Review and Apply Plans

After running `plan` for both paths, review the generated plan files in `plans/`, then apply:

```bash
python triage_data.py apply plans/triage_plan_<timestamp>.json
```

The apply phase takes a snapshot before making changes, then executes each action. For handoff actions, it will pause for the manual Jira move.

### 5. Verify

After triage, spot-check 2-3 tickets in Jira:

- **DATA tickets with `sla` action:** Should have an SLA comment and a RICE score comment
- **Tickets moved to DNA:** Should be in the DNA project with correct Team, Components, Priority, and a move summary comment

All actions are logged to `changes/triage_YYYYMMDD_HHMMSS.json`.

## RICE Prioritization

Every triaged ticket gets a RICE score posted as a comment. The score is calculated from the intake form fields:

| Factor | Source | Scale |
|--------|--------|-------|
| Reach | Teams Impacted field | Entire company = 10, Multiple teams = 5, My team = 2, Just me = 1 |
| Impact | Service Type x Business Priority | 0.375 to 3.75 |
| Confidence | How complete the ticket is (5 signals at 20% each) | 50% to 100% |
| Effort | Story points if set, otherwise estimated from service type | 1 to 13 |

**RICE = (Reach x Impact x Confidence) / Effort**

| RICE Score | Priority Bucket |
|------------|----------------|
| 5+ | Blocker |
| 2 - 5 | High |
| 1 - 2 | Medium |
| < 1 | Low |

## SLA Expectations

| Business Priority (from form) | Jira Priority | SLA |
|-------------------------------|---------------|-----|
| System Outage / Production Blocker | Blocker | Reviewed immediately |
| Fixed Deadline / Upcoming Milestone | High | Reviewed over the next business day |
| Standard Business Operation | Medium | Reviewed in 2-3 business days |
| Nice-to-have / Backlog | Low | Reviewed in 5 business days |

## Weekly Grooming

Once per week, review stale DNA tickets:

```bash
python groom_stale.py --report-only               # See what's stale
python groom_stale.py --interactive --execute      # Walk through and close stale tickets
```

The script categorizes stale tickets into tiers:

| Tier | Criteria | Default Action |
|------|----------|----------------|
| Auto-close | 365+ days, Open, Unassigned | Close with grooming comment |
| Review | 180-364 days | Review with team lead: close or re-prioritize |
| Check-in | 90-179 days, has assignee | Ping assignee: "Still active?" |

## Monthly Health Check

Once per month, run the full compliance audit and generate a report for engineering leads:

```bash
python audit_dna.py                                # Audit all open DNA tickets
python groom_report.py                             # Generate HTML + Markdown reports
python repair_dna.py --dry-run                     # Preview auto-repairs
python repair_dna.py --execute --batch-size 10     # Apply repairs in batches
```

## Safety and Rollback

| Feature | How It Works |
|---------|--------------|
| Dry run | All scripts default to `--dry-run`. You must pass `--execute` to make changes. |
| Snapshots | Taken automatically before any modifications. Stored in `snapshots/`. |
| Change log | Every action logged to `changes/`. |
| Rollback (full) | `python rollback.py restore snapshots/<file>.json --execute` |
| Rollback (surgical) | `python rollback.py undo changes/<file>.json --keys DNA-5001 --execute` |
| Additive only | Component repairs only add official values. Existing components are never removed. |

## Quick Reference

```bash
# Daily
python audit_data.py                               # Check the queue
python triage_data.py plan --path auto              # Plan fast-triage for conforming tickets
python triage_data.py plan --path enrich            # Plan for non-conforming tickets
python triage_data.py apply plans/<plan_file>.json  # Execute the plan

# Weekly
python groom_stale.py --interactive --execute       # Close stale DNA tickets

# Monthly
python audit_dna.py                                 # Full DNA compliance audit
python groom_report.py                              # Reports for eng leads
python repair_dna.py --execute --batch-size 10      # Bulk repairs

# Emergency
python rollback.py restore snapshots/<latest>.json --execute
```
