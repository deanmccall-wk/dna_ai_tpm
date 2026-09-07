# Customer Data Deletion Runbook — Data Operations

## Overview

This runbook documents the Data Operations process for redacting customer data in the Snowflake and Redshift data warehouses after SSE completes platform deletion.

**Entry point:** SSE has completed all 6 platform deletion actions and attached JSON result files to the Jira ticket.

**Workflow diagram:** See `docs/deletion_workflow.png`

---

## Quick Reference — Redaction Checklist

For every deletion, **all three** org_deletes locations must be updated:

| # | Location | How |
|---|----------|-----|
| 1 | `SILVER_PROD.COMMON.WORKIVA_ORG_DELETES` (Snowflake) | Add row to dbt seed CSV in `dbt_core_models`, merge PR. Nightly deploy or trigger job 908937. |
| 2 | `SILVER_PROD.ADMIN.WORKIVA_ORG_DELETES` (Snowflake) | Direct INSERT + update [GitHub script](https://github.com/Workiva/enterprise_silver_dbt/blob/master/scripts/SQL/manual_table_ddl/admin_workiva_org_deletes.sql) |
| 3 | `admin.workiva_org_deletes` (Redshift) | Direct INSERT via psql |

Missing any one of these leaves customer names unredacted in downstream views.

---

## Step 1 — Identify

Extract the org_id and account_id from the ticket and identify all workspaces.

The org_id is in the ticket description or comments:

```
Org ID: e4e54d60-463d-4b7d-ab5d-9f6a8a426a5c
```

If the account_id is not provided, look it up in Snowflake:

```sql
SELECT DISTINCT
    JSON_EXTRACT_PATH_TEXT(organization, 'id') AS org_id,
    id AS workspace_id,
    name AS workspace_name
FROM LAKE_PROD.WORKIVA.workiva_workspace
WHERE JSON_EXTRACT_PATH_TEXT(organization, 'id') = '<org_id>';
```

List all workspaces for the org and post the baseline to the ticket before making changes.

---

## Step 2 — Redact in Snowflake (COMMON)

This table feeds the primary redaction views (`ADMIN.STG_WORKIVA_WORKSPACE`, `WORKIVA.ORGANIZATION`).

1. Open the `dbt_core_models` repo (dbt Cloud project 396950)
2. Edit the `workiva_org_deletes` seed CSV — add a new row:
   ```csv
   organization_id,account_id,deleted_date
   <org-uuid>,<account-id>,YYYY-MM-DD
   ```
3. Open a PR and get it merged
4. The nightly dbt Cloud job (908937) will `INSERT OVERWRITE` the table
5. To apply immediately: trigger job 908937 manually in dbt Cloud

---

## Step 3 — Redact in Snowflake (ADMIN)

This table feeds `WORKIVA.WORKSPACE_SOLUTION` and its downstream Gold-layer views.

Run directly in Snowflake (requires `APP_SILVER_ADMIN_RW_PROD` role):

```sql
INSERT INTO SILVER_PROD.ADMIN.WORKIVA_ORG_DELETES
  (organization_id, account_id, deleted_date)
VALUES ('<org-uuid>', '<account-id>', '<YYYY-MM-DD>');
```

Then update the script file in GitHub for traceability:
- [admin_workiva_org_deletes.sql](https://github.com/Workiva/enterprise_silver_dbt/blob/master/scripts/SQL/manual_table_ddl/admin_workiva_org_deletes.sql)

---

## Step 4 — Redact in Redshift

This table feeds all Redshift redaction views.

Connect to Redshift:

```bash
psql "host=redshift.it.workiva.net port=5439 dbname=defaultdb user=<your_admin_user> sslmode=require"
```

Run the INSERT:

```sql
INSERT INTO admin.workiva_org_deletes (organization_id, account_id, deleted_date)
VALUES ('<org-uuid>', '<account-id>', '<YYYY-MM-DD>');
```

There is no seed or GitHub script for the Redshift table — it is populated exclusively via direct INSERT.

---

## Step 5 — Verify

Run the following queries to confirm redaction and post the results to the Jira ticket as proof.

### Snowflake Verification Queries

```sql
-- 1. Primary redaction view (fed by COMMON.WORKIVA_ORG_DELETES)
SELECT WORKSPACE_ID, WORKSPACE_NAME, DELETED_FLAG, ACTIVE_FLAG
FROM SILVER_PROD.ADMIN.STG_WORKIVA_WORKSPACE
WHERE ORGANIZATION_ID = '<org_id>';

-- 2. Secondary redaction view (fed by ADMIN.WORKIVA_ORG_DELETES)
SELECT WORKSPACE_ID, WORKSPACE_NAME, DELETED_FLAG
FROM SILVER_PROD.WORKIVA.WORKSPACE_SOLUTION
WHERE ORGANIZATION_ID = '<org_id>';

-- 3. Organization-level redaction
SELECT ORGANIZATION_ID, ORGANIZATION_NAME, DELETED_FLAG
FROM SILVER_PROD.WORKIVA.ORGANIZATION
WHERE ORGANIZATION_ID = '<org_id>';

-- 4. Org deletes record
SELECT ORGANIZATION_ID, ACCOUNT_ID, DELETED_DATE
FROM SILVER_PROD.COMMON.WORKIVA_ORG_DELETES
WHERE ORGANIZATION_ID = '<org_id>';
```

### Redshift Verification Queries

```sql
-- 1. Workspace redaction
SELECT account_resource_id, workspace_name, deleted_flag, active_flag
FROM audit.workiva_workspace
WHERE organization_id = '<org_id>';

-- 2. Organization redaction
SELECT organization_id, organization_name, deleted_flag
FROM audit.workiva_organization
WHERE organization_id = '<org_id>';

-- 3. Workspace solution redaction
SELECT account_resource_id, workspace_name, deleted_flag
FROM public.workiva_workspace_solution
WHERE organization_id = '<org_id>';

-- 4. Org deletes record
SELECT organization_id, account_id, deleted_date
FROM admin.workiva_org_deletes
WHERE organization_id = '<org_id>';
```

### Expected Results

All queries should return:
- `WORKSPACE_NAME` / `ORGANIZATION_NAME` = `REDACTED`
- `DELETED_FLAG` = `TRUE`
- `ACTIVE_FLAG` = `FALSE`
- A matching row in `workiva_org_deletes`

**If verification fails:** Identify which table is missing the org_id row and repeat the corresponding step (2, 3, or 4).

---

## Step 6 — Close

### Verify Salesforce

```sql
-- Redshift
SELECT DISTINCT swa.id AS salesforce_id
FROM admin.workiva_org_deletes d
LEFT JOIN public.workiva_workspace ww ON ww.organization_id = d.organization_id
LEFT JOIN admin.salesforce_wdesk_classic_account swa ON swa.account_resource_id = ww.account_resource_id
WHERE d.organization_id = '<org_id>';
```

### Post Completion Comment and Close

Post a comment tagging SaaS Ops, then transition the ticket to Done/Closed.

For parent/child tickets (e.g., Bank of America): close each child first, then the parent.

If the customer requests a Certificate of Destruction, that is handled by Legal (Clay Stanley) and DocuSign — not a Data Operations step.

---

## Reference: How Redaction Works

Redaction is **not automatic**. Views LEFT JOIN against org_deletes tables and replace customer names with `'REDACTED'` when a matching org_id is found.

### Redaction Logic

```sql
CASE WHEN d.organization_id IS NOT NULL THEN 'REDACTED'
     ELSE workspace_name
END AS workspace_name,

d.organization_id IS NOT NULL AS deleted_flag
```

### Snowflake — Org Deletes Tables

| Table | Source | Populated By |
|-------|--------|-------------|
| `SILVER_PROD.COMMON.WORKIVA_ORG_DELETES` | dbt seed in `dbt_core_models` (project 396950, job 908937) | Edit seed CSV, merge PR. Nightly `INSERT OVERWRITE`. |
| `SILVER_PROD.ADMIN.WORKIVA_ORG_DELETES` | Manual SQL in `enterprise_silver_dbt` | Ad-hoc INSERT via DNA release scripts |

Both must be updated for every deletion.

### Snowflake Lineage

See `docs/snowflake_deletion_lineage.png`

### Redshift — Org Deletes Table

| Table | Source | Populated By |
|-------|--------|-------------|
| `admin.workiva_org_deletes` | No source control (DMADE-1085) | Direct INSERT via psql |

### Redshift Lineage

See `docs/redshift_deletion_lineage.png`

### Known Issues (as of Sep 2026)

- The two Snowflake tables are out of sync (COMMON: 86 rows, ADMIN: 85 rows)
- Some rows have malformed UUIDs and missing account_ids
- The ADMIN table has not been updated since Nov 2025
- No automation to keep the three tables in sync
- The Redshift table has no source control

---

## Reference: Jira Field Values

| Field | Value |
|-------|-------|
| Team | Data Engineering |
| Stakeholder | Legal |
| Component | Operations |
| Work Type | Maintenance |
| Epic Link | DNA-2543 (Data Deletion epic) |
| Priority | Per business priority, default High |

## Reference: Edge Cases

- **Blocked by CSADMIN:** Operator may need org/workspace access. Watch for CSADMIN ticket links.
- **Blocked by Integrated Automations (IA):** Orphaned automations must be deleted first.
- **Cross-region (EU appspot):** PwC UK tickets use EU infrastructure.
- **Carbon data:** May require coordination with Carbon dev team.

## Reference: SSE Platform Deletion (Before Data Operations)

The SSE operator completes intake (confirm Org ID, create Deletion Tracking Document, link SUPP/CSADMIN tickets) and runs 6 platform deletion actions via Support Viewer (Force Shred, S16/Filing Deletion, Workspace Data Deletion, Group Deletion, Organization Retention Policy, GES Lifecycle Event). Data Operations entry point is when all 6 result files are attached.

---

## Planned Improvements

- **Automated verification script** (`verify_deletion.py`): A CLI tool has been developed in `dna_ai_tpm` that automates the identify and verify steps, posts proof of redaction directly to Jira with SQL queries and results, and can auto-close tickets on pass. Pending rollout to Data Operations users.
- **Consolidate org_deletes tables**: The three separate tables should be replaced with a single source of truth to eliminate sync issues.
