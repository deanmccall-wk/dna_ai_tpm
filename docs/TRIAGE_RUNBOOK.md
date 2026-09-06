# DnA Triage Runbook -- Data Operations

## Overview

This runbook describes the triage process for incoming Data & Analytics requests. Tickets arrive in the **DATA** Jira project (JSM service desk) and are either resolved at the desk, moved to **Waiting for Customer**, or moved to the **DNA** project (engineering execution).

**Who:** TPM (Data & Analytics) with Cortex Code assistance
**When:** Daily (check the queue each morning)
**Tools:** Python scripts in `~/Documents/dna_ai_tpm/`, Cortex Code, Snowflake, Atlan, AWS CLI

## Process Rules

These rules are non-negotiable. They exist because violations during the initial triage effort caused irreversible damage (permanently closed tickets that should have been assigned).

1. **Never close or transition a ticket without explicit TPM confirmation.** JSM tickets cannot be reopened once Closed.
2. **Always create a snapshot before any changes.** No exceptions.
3. **Never auto-advance to the next ticket.** Present findings, wait for direction.
4. **Self-service is always preferred** over data exports or routing to a team for a data pull.
5. **Verify the ticket key before posting.** Confirm you are commenting on the correct ticket.
6. **Review technical statements before posting.** Do not post information you are uncertain about.
7. **Estimated RICE score goes in a separate comment**, not in the public triage comment.
8. **Update the summary** from "General Request" to a descriptive title on every ticket.
9. **Update the priority** to match the calculated recommendation.
10. **Link related tickets** when found during investigation.

## Setup (First Time)

```bash
cd ~/Documents/dna_ai_tpm
cp .env.example .env
# Edit .env with your Jira PAT, Confluence PAT, Atlan API token, Redshift creds, GitHub PAT
# Ensure ATLAN_BASE_URL=https://workiva.atlan.com is set
source .venv/bin/activate
PYTHONPATH=$PWD python scripts/verify_connection.py
```

## Deletion Tickets

Data deletion tickets (from SaaS Ops) are automatically detected during triage and routed to the deletion process. They skip standard triage.

- **Runbook:** [Customer Data Deletion -- Data Operations Runbook](https://wiki.atl.workiva.net/spaces/BT/pages/530849217)
- **Automation:** `PYTHONPATH=$PWD python deletion/verify_deletion.py <ticket_key>`
- **Indicators:** Summary contains "Data Deletion", "Delete End Client Data", "Certificate of Destruction"

---

## AI-Assisted Triage (Primary Workflow)

This is the primary triage workflow. Each ticket is triaged individually with investigation and TPM review. For bulk cleanup of stale queues, see "Batch Triage" below.

### Workflow Overview

```
Select ticket
    |
    v
Step 1: SNAPSHOT --- mandatory, no exceptions
    |
    v
Step 2: ASSESS --- run _assess.py for conformance, RICE, team, assets
    |
    v
Step 3: INVESTIGATE --- Snowflake, Atlan, QuickSight, related tickets
    |
    v
Step 4: PRESENT FINDINGS --- STOP. Wait for TPM review.
    |
    v
    TPM reviews and decides action
    |
    v
Step 5: POST TRIAGE --- comment + RICE (separate), update summary + priority
    |
    v
Step 6: ROUTE --- close, assign, Waiting for Customer, or handoff to DNA
    |
    v
    STOP --- wait for TPM to direct to next ticket
```

### Step 1: Snapshot

Before any changes, create a pre-triage snapshot:

```bash
cd ~/Documents/dna_ai_tpm
source .venv/bin/activate
PYTHONPATH=$PWD python safety/snapshot.py --keys DATA-XXXX --label pre_triage
```

This saves the full ticket state to `snapshots/DATA-XXXX/` for rollback if needed.

### Step 2: Assess

Run the assessment script to get conformance score, RICE, team recommendation, and asset references:

```bash
PYTHONPATH=$PWD python scripts/_assess.py DATA-XXXX
```

Output includes:
- Conformance score (0-5) and path (AUTO or ENRICH)
- RICE score with Reach/Impact/Confidence/Effort breakdown
- Recommended team and Jira field values
- Asset references found in the description with Atlan links
- Existing comments and DNA cross-references

### Step 3: Investigate

Follow the Standard Investigation Sequence (see section below). At minimum:

1. **Related ticket search** -- check for duplicates and prior work
2. **Reporter lookup** -- check `dim_workers` for role, department, active status
3. **Asset search** -- verify Snowflake objects exist, get Atlan links

Additional investigation depends on ticket type (see Investigation Patterns).

### Step 4: Present Findings (STOP)

Present the triage assessment to the TPM. Include:
- Request summary
- Key investigation findings
- Recommended action (close, assign, Waiting for Customer, handoff)
- Any questions or ambiguities

**Do not proceed until the TPM confirms the action.**

### Step 5: Post Triage

After TPM confirmation, post the triage comment following the 10-Point Standard (see section below). In a separate action:
- Post the Estimated RICE score as a separate comment
- Update the summary from "General Request" to a descriptive title
- Update the priority to match the calculated recommendation
- Link any related tickets found during investigation

### Step 6: Route

Based on TPM decision:

| Action | Steps |
|--------|-------|
| **Close** | Post closing comment with polite reopen message. Transition: Cancel -> Close (or Done if from Open). |
| **Waiting for Customer** | Post triage with specific questions. Transition to Waiting for Customer. |
| **Assign in DATA** | Set assignee. Leave in current status. |
| **Handoff to DNA** | Post handoff comment. TPM manually moves in Jira UI. Then set Team, Component, Assignee on new DNA key via API. |

**After routing: STOP. Do not proceed to the next ticket until the TPM directs.**

---

## Mandatory Checklists

### Pre-Change Checklist

Complete before any Jira modification:

- [ ] Snapshot created (`safety/snapshot.py --keys <KEY> --label pre_triage`)
- [ ] `_assess.py` run (conformance, RICE, team recommendation, asset lookup)
- [ ] Investigation complete (Snowflake, Atlan, related tickets, employee/access check as applicable)
- [ ] Findings presented to TPM
- [ ] TPM has confirmed the action to take

### Pre-Post Checklist

Complete before posting triage comment:

- [ ] Correct ticket key verified (not posting to wrong ticket)
- [ ] Summary updated from "General Request" to descriptive title
- [ ] Priority updated to match calculated recommendation
- [ ] Triage comment includes all applicable items from the 10-Point Standard
- [ ] Estimated RICE posted as a SEPARATE comment (not in the public triage)
- [ ] Atlan links verified (correct Snowflake objects, not Redshift)
- [ ] No incorrect or uncertain technical statements
- [ ] Related tickets linked

### Post-Action Checklist

Complete before moving to next ticket:

- [ ] Ticket status is correct (Waiting for Customer, assigned, or confirmed for close)
- [ ] If moved to DNA: Team, Component, and Assignee are set on the DNA ticket
- [ ] STOP -- do not proceed to next ticket until TPM directs

---

## 10-Point Triage Comment Standard

Every triage comment must include all applicable items:

1. **Request summary** -- clear description of what is being asked
2. **Conformance score** -- X/5 (AUTO or ENRICH) and SLA tier
3. **Estimated RICE score** -- posted as a SEPARATE internal comment, never in the public triage
4. **Team recommendation** -- which team should own this and why
5. **Investigation results** -- what was found in Snowflake, Atlan, QuickSight, or related tickets
6. **Atlan links** -- for every Snowflake object referenced (table, view, column)
7. **Self-service path** -- if the requester can resolve this themselves, explain how
8. **Role recommendation** -- if Snowflake access needed, recommend the specific role + [DnA Knowledge Hub](https://wiki.atl.workiva.net/spaces/BT/pages/505678345/Runbooks) link
9. **Example SQL** -- when it would help the requester get started
10. **Next steps** -- specific actions for the requester or the assigned team

### Public Triage Comment Template

```
*Triage Assessment -- DATA-XXXX*

h4. Request
<1-2 sentence summary of what is being asked>

h4. Conformance & Prioritization
|| Metric || Value ||
| Conformance | X/5 (AUTO/ENRICH) |
| SLA Tier | X -- <SLA text> |
| Jira Priority | <priority> (updated from <old>) |
| Recommended Team | <team> |

h4. Investigation
<tables found, columns checked, Atlan links, related tickets, Snowflake query results>

|| Asset || Link ||
| <table_name> | [Atlan|https://workiva.atlan.com/assets/<guid>/overview] |

h4. Self-Service Path
<role recommendation, Knowledge Hub link, example SQL>

h4. Next Steps
Hi [~reporter.username],
<specific questions or actions for the requester>

Thank you,
Dean
```

### Estimated RICE Comment Template (separate comment)

```
*Internal -- Estimated RICE Scoring*
|| Metric || Value ||
| Conformance | X/5 (AUTO/ENRICH) -- <missing fields if any> |
| Estimated RICE Score | X.XX (<bucket>) -- Reach=X, Impact=X, Confidence=X%, Effort=X |
| Calculated Priority | <priority> |
| Biz Priority | <from intake form> |
| Recommended Team | <team> |
```

---

## Standard Investigation Sequence

### Always Do (Every Ticket)

1. **Related ticket search** -- find duplicates and prior work:
   ```
   project IN (DATA, DNA) AND text ~ "<key terms>" ORDER BY created DESC
   ```

2. **Reporter lookup** -- check active status and reporting structure:
   ```sql
   SELECT PREFERRED_NAME, BUSINESS_TITLE, DEPARTMENT_DESCRIPTION, MANAGER_1
   FROM GOLD_PROD.MARTS.DIM_WORKERS
   WHERE IS_LATEST = TRUE AND LOWER(PRIMARY_EMAIL_ADDRESS) = '<email>'
   ```

3. **Asset search** -- run `_assess.py` asset lookup, then search Atlan for referenced objects:
   - Use Atlan API wildcard on `qualifiedName`: `*snowflake*<DB>/<SCHEMA>/<TABLE>`
   - Verify links point to Snowflake objects, not Redshift

### By Ticket Type

| Type | Additional Investigation |
|------|------------------------|
| **Data availability / new fields** | Check `INFORMATION_SCHEMA.COLUMNS` in Silver and Gold. Get Atlan links for source tables. Check if field arrives via Fivetran or Overlord (LAKE_PROD). Determine if fix is in ingestion config or dbt model. |
| **QuickSight access** | Follow the QuickSight Access Troubleshooting sub-process (see below). |
| **Data quality / pipeline** | Query the table to verify the reported issue with sample data. Check Atlan lineage for upstream source. |
| **Access / permissions** | Run `SHOW GRANTS ON <object>` and trace the role chain with `SHOW GRANTS OF ROLE <role>`. Use the DnA Snowflake Access Agent for role recommendations. Check if user has a Snowflake account (`SHOW USERS LIKE '%name%'`). |
| **Customer data pull** | Verify data exists in Snowflake. Route to CPX Insights (not DnA). |
| **Dashboard / Streamlit enhancement** | Identify the dashboard/Streamlit owner. Verify the requested data is available in Snowflake Gold layer. |
| **Atlan metadata** | Check the current Atlan description/column definition. Route to Analytics Engineering for dbt YAML updates. |

---

## QuickSight Access Troubleshooting

### Step 1: Check QuickSight User Roster

Search `quicksight_users.csv` (exported from the QuickSight admin console) for the requester's email:

```bash
grep -i "<email>" quicksight_users.csv
```

- **Not found:** User has not accessed QuickSight in 60+ days. They may have never been provisioned.
- **Found with READER role:** User is provisioned. The issue is dashboard-level permissions.

### Step 2: Check Employee Status

Verify the requester is an active employee:

```sql
SELECT PREFERRED_NAME, IS_ACTIVE, IS_TERMINATED, BUSINESS_TITLE, DEPARTMENT_DESCRIPTION
FROM GOLD_PROD.MARTS.DIM_WORKERS
WHERE IS_LATEST = TRUE AND LOWER(PRIMARY_EMAIL_ADDRESS) = '<email>'
```

### Step 3: Identify Dashboard Owner (if dashboard URL provided)

Extract the dashboard ID from the URL and look up the owner:

```bash
aws quicksight describe-dashboard --aws-account-id 048025451352 \
  --dashboard-id "<id>" --query 'Dashboard.Name' --output text

aws quicksight describe-dashboard-permissions --aws-account-id 048025451352 \
  --dashboard-id "<id>" \
  --query 'Permissions[?contains(Actions, `quicksight:UpdateDashboardPermissions`)].Principal' \
  --output text
```

### Step 4: Post Triage

Include in the triage comment:
- QuickSight roster status (found or not found)
- Dashboard owner(s) who can grant access
- Link to [QuickSight: Authentication Failed When Clicking Dashboard Links](https://wiki.atl.workiva.net/spaces/BT/pages/530849193)

**Key fact:** A QuickSight account is automatically provisioned when the Okta tile is used. Dashboard-level access must be granted separately by a dashboard owner.

---

## Handoff to DNA (Two-Phase Process)

The DATA project is JSM and the DNA project is standard Jira. The REST API cannot move issues between these project types.

### Phase 1: Post triage and handoff comment on the DATA ticket

Include in the handoff comment:
- Recommended Team, Component, and Assignee for the DNA ticket
- Any investigation context that the assigned engineer will need

### Phase 2: TPM manually moves in the Jira UI

1. Open the ticket in Jira UI
2. Click **Move** (top-right menu or ... -> Move)
3. Target project: **DNA**
4. Set issue type to **Story** (Service Request does not exist in DNA)
5. Complete the wizard and note the new DNA key

### Phase 3: Set fields on the new DNA ticket via API

After the TPM provides the new DNA key, set:
- Team (`customfield_10288`)
- Component(s)
- Assignee
- Priority

**Issue Type Mapping (DATA -> DNA):**

| DATA Type | DNA Type |
|-----------|----------|
| Service Request | **Story** |
| Task | Task |
| Epic | Epic |
| Sub-task | Sub-task |

**DNA Team Field:** `customfield_10288` (not `customfield_14703` which is DATA-only)

**Valid DNA Components:** access, Atlan, BI, C360, Cortex, Data Platform and AI, Data Warehouse, DBT, Gainsight, Jira, Operations, Salesforce, Snowflake, Zendesk (and others -- check editmeta for full list)

---

## Batch Triage (Scripted Process)

For high-volume queue cleanup, use the scripted plan/apply workflow:

```bash
source .venv/bin/activate
PYTHONPATH=$PWD python triage/audit_data.py                      # Check the queue
PYTHONPATH=$PWD python triage/triage_data.py plan --path auto    # Plan for conforming tickets
PYTHONPATH=$PWD python triage/triage_data.py plan --path enrich  # Plan for non-conforming tickets
PYTHONPATH=$PWD python triage/triage_data.py apply plans/<file>  # Execute the plan
```

The scripted process handles SLA comments, RICE scoring, and handoff prompts automatically. Use this for bulk operations; use the AI-Assisted workflow for individual ticket investigation.

---

## RICE Prioritization

Every triaged ticket gets an Estimated RICE score posted as a separate comment. The score is calculated from the intake form fields:

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
PYTHONPATH=$PWD python grooming/groom_stale.py --report-only
PYTHONPATH=$PWD python grooming/groom_stale.py --interactive --execute
```

| Tier | Criteria | Default Action |
|------|----------|----------------|
| Auto-close | 365+ days, Open, Unassigned | Close with grooming comment |
| Review | 180-364 days | Review with team lead: close or re-prioritize |
| Check-in | 90-179 days, has assignee | Ping assignee: "Still active?" |

## Monthly Health Check

```bash
PYTHONPATH=$PWD python grooming/audit_dna.py
PYTHONPATH=$PWD python grooming/groom_report.py
PYTHONPATH=$PWD python grooming/repair_dna.py --dry-run
PYTHONPATH=$PWD python grooming/repair_dna.py --execute --batch-size 10
```

## Safety and Rollback

| Feature | How It Works |
|---------|--------------|
| Snapshots | **Mandatory** before any modifications. `PYTHONPATH=$PWD python safety/snapshot.py --keys <KEY> --label pre_triage` |
| Change log | Every action logged to `changes/`. |
| Rollback (full) | `PYTHONPATH=$PWD python safety/rollback.py restore snapshots/<file>.json --execute` |
| Rollback (surgical) | `PYTHONPATH=$PWD python safety/rollback.py undo changes/<file>.json --keys DNA-5001 --execute` |
| Additive only | Component repairs only add official values. Existing components are never removed. |

## Quick Reference

```bash
# Daily -- AI-Assisted Triage
PYTHONPATH=$PWD python safety/snapshot.py --keys DATA-XXXX --label pre_triage
PYTHONPATH=$PWD python scripts/_assess.py DATA-XXXX

# Daily -- Batch Triage
PYTHONPATH=$PWD python triage/audit_data.py
PYTHONPATH=$PWD python triage/triage_data.py plan --path auto
PYTHONPATH=$PWD python triage/triage_data.py apply plans/<file>

# QuickSight Access
grep -i "<email>" quicksight_users.csv
aws quicksight describe-dashboard-permissions --aws-account-id 048025451352 --dashboard-id "<id>"

# Weekly
PYTHONPATH=$PWD python grooming/groom_stale.py --interactive --execute

# Monthly
PYTHONPATH=$PWD python grooming/audit_dna.py
PYTHONPATH=$PWD python grooming/groom_report.py

# Emergency
PYTHONPATH=$PWD python safety/rollback.py restore snapshots/<latest>.json --execute
```
