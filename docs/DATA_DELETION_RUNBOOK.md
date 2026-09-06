# Customer Data Deletion Runbook — Data Operations

## Overview

This runbook covers the Data Operations steps for processing customer data deletion requests. These tickets originate from SaaS Ops, flow through SSE operators for deletion execution, and require Data Operations to verify redaction and close the ticket.

**Data Operations owns Steps 3, 4, and 5.** The other steps are documented here for context.

## End-to-End Workflow

| Step | Owner | Description |
|------|-------|-------------|
| 1. Intake and verification | SSE Operator (Zachary Hakanson, Dawn Hollis, etc.) | Confirm org/workspace IDs with requester, create Deletion Tracking Document, request CSADMIN access |
| 2. Deletion actions | SSE Operator | Run 6 ordered actions via Support Viewer (see below) |
| **3. Field redaction verification** | **Data Operations** | Run verification queries in Snowflake and Redshift, confirm PII redacted |
| **4. Salesforce verification** | **Data Operations** | Verify deletion reflected in Salesforce account records |
| **5. Close and notify** | **Data Operations** | Post completion comment, close ticket |
| 6. Certificate of Destruction | Legal (Clay Stanley) + DocuSign (Sarah Goodall / Lynn Peng) | Only if requested by customer |

## Context: Steps 1-2 (SSE Operator)

### Step 1 — Intake and Verification

The SSE operator:
- Confirms Org ID and Workspace ID(s) with the requester
- Creates a Deletion Tracking Document in the Wdesk sandbox
- Grants the requester viewer permission to the tracking doc
- Creates a CSADMIN ticket if org/workspace access is needed
- Links related tickets (SUPP, CSADMIN, OMR)

### Step 2 — Deletion Actions via Support Viewer

The SSE operator runs these actions in order, attaching JSON result files to the ticket:

1. **Force Shred** — Content Management Support: "Shred - Force Shred for Account"
2. **S16/Filing Deletion** — Filing Data Server: "Delete All Section 16 Data For Account" or "Delete Account Data"
3. **Workspace Data Deletion** — Cerebral Support Service: "Workspace Data Deletion"
4. **Group Deletion** — IAM Support Viewer: "Delete all groups in a workspace" or "Delete all groups in an organization"
5. **Organization Retention Policy** — "Update Organization Retention Policy"
6. **GES Lifecycle Event** — Support Viewer Service: "Submit Delete Workspace or Organization Lifecycle Event to GES"

**Data Operations picks up after all 6 action result files are attached to the ticket.**

---

## Step 3 — Field Redaction Verification (Data Operations)

### When to Run

After the SSE operator posts all deletion action result files to the ticket. Look for comments with attached JSON files named like:
- `Workspace Data Deletion-Results-*.json`
- `Delete all groups in a workspace-Results-*.json`
- `Submit Delete Workspace or Organization Lifecycle Event to GES-Results-*.json`

### Finding the Org ID

The org_id is in the ticket description, typically in a `{code}` block:
```
Org ID: e4e54d60-463d-4b7d-ab5d-9f6a8a426a5c
```

### Step 3a — Identify Workspaces (run first, before deletion actions)

```bash
source .venv/bin/activate
python -m deletion.verify_deletion identify DATA-2487              # List workspaces
python -m deletion.verify_deletion identify DATA-2487 --post       # List and post to Jira
python -m deletion.verify_deletion identify DATA-2487 --org-id <uuid>  # Manual org_id
```

This queries Snowflake for all workspaces in the org and posts a confirmation comment listing each workspace ID, name, and current deleted/active status. Use this to confirm scope before deletion actions begin.

### Step 3b — Verify Redaction (run after deletion actions complete)

```bash
python -m deletion.verify_deletion verify DATA-2487               # Check redaction status
python -m deletion.verify_deletion verify DATA-2487 --post        # Check and post to Jira
python -m deletion.verify_deletion verify DATA-2487 --post --close   # Check, post, and close
```

The script checks each workspace for:
- `WORKSPACE_NAME = 'REDACTED'` (name has been scrubbed)
- `DELETED_FLAG = TRUE`
- `ACTIVE_FLAG = FALSE`
- A record exists in `WORKIVA_ORG_DELETES` with a `DELETED_DATE`

If all workspaces pass, the verification is complete. If any workspace is not yet redacted, the script reports which ones still need action.

### Manual Verification (if needed)

Run these queries in both **Snowflake** and **Redshift**, substituting the org_id:

```sql
-- 1. Workspace records
SELECT * FROM audit.workiva_workspace
WHERE organization_id = '<org_id>';

-- 2. Organization record
SELECT * FROM workiva.organization
WHERE organization_id = '<org_id>';

-- 3. Classic account records
SELECT * FROM audit.wdesk_classic_account
WHERE organization_id = '<org_id>';

-- 4. Workspace solution records
SELECT * FROM public.workiva_workspace_solution
WHERE organization_id = '<org_id>';
```

**What to look for:** All returned rows should show redacted/nulled PII fields. If any fields still contain customer data, escalate back to the SSE operator.

Post query output to the Jira ticket with: **"Field redaction completed."**

## Step 4 — Salesforce Verification (Data Operations)

Verify the deletion is reflected in Salesforce account records:

```sql
-- Get Salesforce account ID(s) linked to the deleted org
SELECT DISTINCT swa.id AS id
FROM admin.workiva_org_deletes d
LEFT JOIN public.workiva_workspace ww
  ON ww.organization_id = d.organization_id
LEFT JOIN admin.salesforce_wdesk_classic_account swa
  ON swa.account_resource_id = ww.account_resource_id
WHERE d.organization_id = '<org_id>';

-- Full audit trail
SELECT *
FROM admin.workiva_org_deletes d
LEFT JOIN public.workiva_workspace ww
  ON ww.organization_id = d.organization_id
LEFT JOIN admin.salesforce_wdesk_classic_account swa
  ON swa.account_resource_id = ww.account_resource_id
WHERE d.organization_id = '<org_id>';
```

Post results to the ticket.

## Step 5 — Close and Notify (Data Operations)

Post a completion comment tagging the SSE operator and SaaS Ops:

```
<Customer Name> - <Request Type> is completed.
[~<sse_operator_username>] [~service_saasops] request is completed.
```

Then close the ticket (transition to Done/Closed).

### Parent/Child Tickets

Some customers (e.g., Bank of America, PwC UK) have a parent ticket with multiple child workspace tickets. Process:
1. Verify and close each **child** workspace ticket first
2. Once all children are closed, verify and close the **parent** ticket
3. The parent ticket usually has a pinned comment tracking the status of each child

## Context: Step 6 — Certificate of Destruction

Only required if the customer requests a CoD. Not a Data Operations step, but for awareness:

1. SSE operator fills out the CoD PDF template
2. Legal (Clay Stanley) reviews and approves
3. Sarah Goodall / Lynn Peng format in DocuSign for signature
4. Signed PDF posted to the ticket and delivered to customer via SaaS Ops

## Jira Field Values

When deletion tickets are moved from DATA to DNA, set:

| Field | Value |
|-------|-------|
| Team | Data Engineering |
| Stakeholder | Legal |
| Component | Operations |
| Work Type | Maintenance |
| Epic Link | DNA-2543 (Data Deletion epic) |
| Priority | Per business priority, default High |

## Edge Cases

- **Blocked by CSADMIN:** Operator may need org/workspace access before deletion actions can run. Watch for CSADMIN ticket links.
- **Blocked by Integrated Automations (IA):** Some workspaces have orphaned automations that must be deleted first. Look for IA ticket links.
- **Blocked by dev PRs:** Occasionally a code fix is needed before force shred works (e.g., timeout issues). Watch for RM/PR links in comments.
- **Cross-region (EU appspot):** PwC UK tickets use EU infrastructure. The org/workspace IDs and Support Viewer URLs will point to EU endpoints.
- **Carbon data:** Carbon-specific deletions may require coordination with the Carbon dev team for AWS data removal.

## Backlog

There are currently ~27 data deletion tickets in the DATA project that need to be moved to DNA and processed. These arrived after the previous process owner left. Work through them using the standard flow above.
