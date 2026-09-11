# Triage Agent Instructions — Gap Analysis

**Compared:** `docs/triage_runbook.md` (human-driven process) vs `data_triage_agent_instructions v0.1` (autonomous agent spec)

**Date:** September 10, 2026

---

## Missing from the Agent Instructions

### 1. Conformance Scoring (0-5)

Our process scores every ticket on conformance (how well the intake form was filled out: 0-5 scale, AUTO vs ENRICH path). The agent instructions have a confidence rubric (Section 9.2) but no equivalent of conformance — it doesn't assess intake form completeness as a distinct metric.

### 2. RICE Prioritization

Our process calculates a RICE score (Reach x Impact x Confidence / Effort) from intake fields and includes it inline in the triage comment. The agent uses a P1-P4 severity/priority model (Section 6.3/6.4) but has no RICE scoring at all.

### 3. Atlan Asset Lookup and Links

Our process searches Atlan for every referenced Snowflake object and includes Atlan links (with GUIDs) in the triage comment. The agent instructions mention `pipeline.status()` and `freshness.check()` but have no Atlan integration — no asset catalog search, no lineage lookup, no Atlan links in comments.

### 4. Reporter Lookup (dim_workers)

Our process queries `GOLD_PROD.MARTS.DIM_WORKERS` on every ticket to verify the requester is an active employee and get their title/department/manager. The agent instructions don't include employee verification.

### 5. Snowflake Investigation

Our runbook includes direct Snowflake queries: `INFORMATION_SCHEMA.COLUMNS`, `SHOW GRANTS`, role hierarchy tracing, masking policy analysis, data population checks. The agent instructions treat investigation as read-only tool calls to pipeline/freshness checks only — no direct warehouse querying.

### 6. QuickSight Access Troubleshooting

Our runbook has a dedicated sub-process: check the QuickSight user roster CSV, verify employee status, look up dashboard owners via AWS CLI, link to the KB article. The agent instructions classify these as `ACCESS_BI` and route to `decision_science` but have no QuickSight-specific investigation steps.

### 7. Snapshot and Rollback Safety

Our process mandates a pre-triage snapshot before any modification, enforced programmatically by the JiraClient. The agent instructions have no snapshot mechanism, no rollback capability, and no change logging.

### 8. Comment Validation (10-Point Standard)

Our process validates every triage comment against a 10-point standard (request summary, conformance, RICE, team recommendation, investigation results, Atlan links, self-service path, role recommendation, example SQL, next steps). The agent instructions have templates (T1-T8) but no validation layer.

### 9. Deletion Ticket Detection and Routing

Our process auto-detects data deletion tickets (by summary keywords) and routes them to a separate Confluence-documented deletion runbook. The agent instructions have no deletion ticket handling.

### 10. Self-Service Path and Example SQL

Our triage comments include a self-service path (can the requester solve this themselves?), role recommendations with Knowledge Hub links, and example SQL queries. The agent instructions focus on routing decisions but don't generate self-service guidance.

### 11. Summary Rewrite

Our process updates every ticket summary from "General Request" to a descriptive title. The agent normalizes a summary internally (Step 0) but doesn't write it back to the Jira summary field.

### 12. Related Ticket Linking

Our process searches DATA/DNA for duplicates and related work, then creates Jira links between them. The agent searches for duplicates (Step 0) but only for redirect purposes — it doesn't link non-duplicate related tickets.

### 13. DNA Handoff Field Setting

Our process sets specific fields on the new DNA ticket after the move (Team via `customfield_10288`, Components from a known valid list, Assignee, Priority). The agent instructions reference `jira.teams` keys but don't document the actual Jira custom field IDs or valid component values.

---

## Present in Agent Instructions but Missing from Our Runbook

| Agent Feature | Gap in Our Runbook |
|---|---|
| **Security screen** (Section 6.1) — credential/PII/breach detection | We have no security screening step |
| **Slack intake** (Section 12) — ticket creation from Slack threads | We don't handle Slack-originated requests |
| **OpsGenie paging** for P1/P2 incidents | We don't integrate with on-call |
| **Follow-up timers** (Section 13) — auto-reminders and auto-close | We have no automated timer system |
| **Confidence scoring** with numeric rubric (0.50 base + adjustments) | We don't quantify triage confidence |
| **Structured triage record** (JSON schema, Section 10) | Our output is a Jira comment, not structured data |
| **Incident type taxonomy** (11 incident types) | We classify by investigation pattern, not formal type IDs |
| **Upstream-first verification** as a formal gated process | We do this ad hoc during investigation |
| **Autonomy levels** (0/1/2) with risk-gated actions | We have TPM confirmation gates but no formal autonomy model |
| **Audit fields** (Section 17) for measuring triage quality | We log changes but don't track triage quality metrics |
