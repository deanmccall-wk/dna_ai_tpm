#!/usr/bin/env python3
"""Publish the DATA Triage Runbook to Confluence with proper HTML."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import project_root  # noqa: F401
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from clients.config import load_settings
from clients.confluence_client import ConfluenceClient

s = load_settings()
conf = ConfluenceClient(s.confluence_base_url, s.confluence_pat)

body = """
<h1>DnA Triage Runbook &mdash; Data Operations</h1>

<h2>Overview</h2>
<p>This runbook describes the triage process for incoming Data &amp; Analytics requests. Tickets arrive in the <strong>DATA</strong> Jira project (JSM service desk) and are either resolved at the desk, moved to <strong>Waiting for Customer</strong>, or moved to the <strong>DNA</strong> project (engineering execution).</p>
<p><strong>Who:</strong> TPM (Data &amp; Analytics) with Cortex Code assistance<br/>
<strong>When:</strong> Daily (check the queue each morning)<br/>
<strong>Tools:</strong> Python scripts in <code>~/Documents/dna_ai_tpm/</code>, Cortex Code, Snowflake, Atlan, AWS CLI</p>

<hr/>

<h2>Process Rules</h2>
<p>These rules are non-negotiable. They exist because violations during the initial triage effort caused irreversible damage (permanently closed tickets that should have been assigned).</p>
<ol>
<li><strong>Never close or transition a ticket without explicit TPM confirmation.</strong> JSM tickets cannot be reopened once Closed.</li>
<li><strong>Always create a snapshot before any changes.</strong> No exceptions.</li>
<li><strong>Never auto-advance to the next ticket.</strong> Present findings, wait for direction.</li>
<li><strong>Self-service is always preferred</strong> over data exports or routing to a team for a data pull.</li>
<li><strong>Verify the ticket key before posting.</strong> Confirm you are commenting on the correct ticket.</li>
<li><strong>Review technical statements before posting.</strong> Do not post information you are uncertain about.</li>
<li><strong>Estimated RICE score goes in a separate comment</strong>, not in the public triage comment.</li>
<li><strong>Update the summary</strong> from &ldquo;General Request&rdquo; to a descriptive title on every ticket.</li>
<li><strong>Update the priority</strong> to match the calculated recommendation.</li>
<li><strong>Link related tickets</strong> when found during investigation.</li>
</ol>

<hr/>

<h2>AI-Assisted Triage Workflow (Primary)</h2>
<p>This is the primary triage workflow. Each ticket is triaged individually with investigation and TPM review.</p>

<h3>Workflow Diagram</h3>
<table>
<tbody>
<tr><td style="background-color:#f4f5f7; text-align:center; padding:20px; font-family:monospace; white-space:pre; line-height:1.8;">
SELECT TICKET<br/>
&darr;<br/>
<strong>Step 1: SNAPSHOT</strong> &mdash; mandatory, no exceptions<br/>
&darr;<br/>
<strong>Step 2: ASSESS</strong> &mdash; run _assess.py for conformance, RICE, team, assets<br/>
&darr;<br/>
<strong>Step 3: INVESTIGATE</strong> &mdash; Snowflake, Atlan, QuickSight, related tickets<br/>
&darr;<br/>
<strong>Step 4: PRESENT FINDINGS</strong> &mdash; STOP. Wait for TPM review.<br/>
&darr;<br/>
TPM reviews and decides action<br/>
&darr;<br/>
<strong>Step 5: POST TRIAGE</strong> &mdash; comment + RICE (separate), update summary + priority<br/>
&darr;<br/>
<strong>Step 6: ROUTE</strong> &mdash; close, assign, Waiting for Customer, or handoff to DNA<br/>
&darr;<br/>
<strong>STOP</strong> &mdash; wait for TPM to direct to next ticket
</td></tr>
</tbody>
</table>

<h3>Step 1: Snapshot</h3>
<p>Before any changes, create a pre-triage snapshot:</p>
<pre>cd ~/Documents/dna_ai_tpm
source .venv/bin/activate
PYTHONPATH=$PWD python safety/snapshot.py --keys DATA-XXXX --label pre_triage</pre>
<p>This saves the full ticket state to <code>snapshots/DATA-XXXX/</code> for rollback if needed.</p>

<h3>Step 2: Assess</h3>
<p>Run the assessment script:</p>
<pre>PYTHONPATH=$PWD python scripts/_assess.py DATA-XXXX</pre>
<p>Output includes: conformance score (0-5), RICE score, recommended team and Jira field values, asset references with Atlan links, existing comments and DNA cross-references.</p>

<h3>Step 3: Investigate</h3>
<p>Follow the Standard Investigation Sequence (see below). At minimum:</p>
<ol>
<li><strong>Related ticket search</strong> &mdash; check for duplicates and prior work</li>
<li><strong>Reporter lookup</strong> &mdash; check dim_workers for role, department, active status</li>
<li><strong>Asset search</strong> &mdash; verify Snowflake objects exist, get Atlan links</li>
</ol>

<h3>Step 4: Present Findings (STOP)</h3>
<p>Present the triage assessment to the TPM. <strong>Do not proceed until the TPM confirms the action.</strong></p>

<h3>Step 5: Post Triage</h3>
<p>After TPM confirmation, post the triage comment following the 10-Point Standard. Separately:</p>
<ul>
<li>Post the Estimated RICE score as a separate comment</li>
<li>Update the summary from &ldquo;General Request&rdquo; to a descriptive title</li>
<li>Update the priority to match the calculated recommendation</li>
<li>Link any related tickets found during investigation</li>
</ul>

<h3>Step 6: Route</h3>
<table>
<thead><tr><th>Action</th><th>Steps</th></tr></thead>
<tbody>
<tr><td><strong>Close</strong></td><td>Post closing comment with polite reopen message. Transition: Cancel &rarr; Close (or Done if from Open).</td></tr>
<tr><td><strong>Waiting for Customer</strong></td><td>Post triage with specific questions. Transition to Waiting for Customer.</td></tr>
<tr><td><strong>Assign in DATA</strong></td><td>Set assignee. Leave in current status.</td></tr>
<tr><td><strong>Handoff to DNA</strong></td><td>Post handoff comment. TPM manually moves in Jira UI. Then set Team, Component, Assignee on new DNA key via API.</td></tr>
</tbody>
</table>
<p><strong>After routing: STOP. Do not proceed to the next ticket until the TPM directs.</strong></p>

<hr/>

<h2>Mandatory Checklists</h2>

<h3>Pre-Change Checklist</h3>
<p>Complete before any Jira modification:</p>
<ul>
<li>Snapshot created (<code>safety/snapshot.py --keys &lt;KEY&gt; --label pre_triage</code>)</li>
<li><code>_assess.py</code> run (conformance, RICE, team recommendation, asset lookup)</li>
<li>Investigation complete (Snowflake, Atlan, related tickets, employee/access check as applicable)</li>
<li>Findings presented to TPM</li>
<li>TPM has confirmed the action to take</li>
</ul>

<h3>Pre-Post Checklist</h3>
<p>Complete before posting triage comment:</p>
<ul>
<li>Correct ticket key verified (not posting to wrong ticket)</li>
<li>Summary updated from &ldquo;General Request&rdquo; to descriptive title</li>
<li>Priority updated to match calculated recommendation</li>
<li>Triage comment includes all applicable items from the 10-Point Standard</li>
<li>Estimated RICE posted as a SEPARATE comment</li>
<li>Atlan links verified (correct Snowflake objects, not Redshift)</li>
<li>No incorrect or uncertain technical statements</li>
<li>Related tickets linked</li>
</ul>

<h3>Post-Action Checklist</h3>
<p>Complete before moving to next ticket:</p>
<ul>
<li>Ticket status is correct (Waiting for Customer, assigned, or confirmed for close)</li>
<li>If moved to DNA: Team, Component, and Assignee are set on the DNA ticket</li>
<li>STOP &mdash; do not proceed to next ticket until TPM directs</li>
</ul>

<hr/>

<h2>10-Point Triage Comment Standard</h2>
<p>Every triage comment must include all applicable items:</p>
<ol>
<li><strong>Request summary</strong> &mdash; clear description of what is being asked</li>
<li><strong>Conformance score</strong> &mdash; X/5 (AUTO or ENRICH) and SLA tier</li>
<li><strong>Estimated RICE score</strong> &mdash; posted as a SEPARATE comment, never in the public triage</li>
<li><strong>Team recommendation</strong> &mdash; which team should own this and why</li>
<li><strong>Investigation results</strong> &mdash; what was found in Snowflake, Atlan, QuickSight, or related tickets</li>
<li><strong>Atlan links</strong> &mdash; for every Snowflake object referenced</li>
<li><strong>Self-service path</strong> &mdash; if the requester can resolve this themselves, explain how</li>
<li><strong>Role recommendation</strong> &mdash; if Snowflake access needed, recommend the specific role + Knowledge Hub link</li>
<li><strong>Example SQL</strong> &mdash; when it would help the requester get started</li>
<li><strong>Next steps</strong> &mdash; specific actions for the requester or the assigned team</li>
</ol>

<h3>Public Triage Comment Template (Jira Wiki Markup)</h3>
<pre>*Triage Assessment -- DATA-XXXX*

h4. Request
&lt;1-2 sentence summary&gt;

h4. Conformance &amp; Prioritization
|| Metric || Value ||
| Conformance | X/5 (AUTO/ENRICH) |
| SLA Tier | X -- &lt;SLA text&gt; |
| Jira Priority | &lt;priority&gt; (updated from &lt;old&gt;) |
| Recommended Team | &lt;team&gt; |

h4. Investigation
&lt;tables, Atlan links, Snowflake query results, related tickets&gt;

|| Asset || Link ||
| &lt;table_name&gt; | [Atlan|https://workiva.atlan.com/assets/&lt;guid&gt;/overview] |

h4. Self-Service Path
&lt;role recommendation, Knowledge Hub link, example SQL&gt;

h4. Next Steps
Hi [~reporter.username],
&lt;specific questions or actions&gt;

Thank you,
Dean</pre>

<h3>Estimated RICE Comment Template (Separate Comment)</h3>
<pre>*Internal -- Estimated RICE Scoring*
|| Metric || Value ||
| Conformance | X/5 (AUTO/ENRICH) -- &lt;details&gt; |
| Estimated RICE Score | X.XX (&lt;bucket&gt;) -- Reach=X, Impact=X, Confidence=X%, Effort=X |
| Calculated Priority | &lt;priority&gt; |
| Biz Priority | &lt;from intake form&gt; |
| Recommended Team | &lt;team&gt; |</pre>

<hr/>

<h2>Standard Investigation Sequence</h2>

<h3>Always Do (Every Ticket)</h3>
<ol>
<li><strong>Related ticket search:</strong>
<pre>project IN (DATA, DNA) AND text ~ "&lt;key terms&gt;" ORDER BY created DESC</pre></li>
<li><strong>Reporter lookup:</strong>
<pre>SELECT PREFERRED_NAME, BUSINESS_TITLE, DEPARTMENT_DESCRIPTION, MANAGER_1
FROM GOLD_PROD.MARTS.DIM_WORKERS
WHERE IS_LATEST = TRUE AND LOWER(PRIMARY_EMAIL_ADDRESS) = '&lt;email&gt;'</pre></li>
<li><strong>Asset search:</strong> Run <code>_assess.py</code> asset lookup, then search Atlan for referenced objects using wildcard on qualifiedName: <code>*snowflake*&lt;DB&gt;/&lt;SCHEMA&gt;/&lt;TABLE&gt;</code></li>
</ol>

<h3>By Ticket Type</h3>
<table>
<thead><tr><th>Type</th><th>Additional Investigation</th></tr></thead>
<tbody>
<tr><td><strong>Data availability / new fields</strong></td><td>Check <code>INFORMATION_SCHEMA.COLUMNS</code> in Silver and Gold. Get Atlan links. Check if field arrives via Fivetran or Overlord (LAKE_PROD). Determine if fix is in ingestion config or dbt model.</td></tr>
<tr><td><strong>QuickSight access</strong></td><td>Follow the QuickSight Access Troubleshooting sub-process (see below).</td></tr>
<tr><td><strong>Data quality / pipeline</strong></td><td>Query the table to verify the reported issue. Check Atlan lineage for upstream source.</td></tr>
<tr><td><strong>Access / permissions</strong></td><td>Run <code>SHOW GRANTS ON &lt;object&gt;</code> and trace the role chain. Use the DnA Snowflake Access Agent for role recommendations. Check if user has a Snowflake account.</td></tr>
<tr><td><strong>Customer data pull</strong></td><td>Verify data exists in Snowflake. Route to CPX Insights (not DnA).</td></tr>
<tr><td><strong>Dashboard / Streamlit enhancement</strong></td><td>Identify the dashboard/Streamlit owner. Verify the requested data is available in Snowflake Gold layer.</td></tr>
<tr><td><strong>Atlan metadata</strong></td><td>Check the current Atlan description/column definition. Route to Analytics Engineering for dbt YAML updates.</td></tr>
</tbody>
</table>

<hr/>

<h2>QuickSight Access Troubleshooting</h2>

<h3>Step 1: Check QuickSight User Roster</h3>
<p>Search <code>quicksight_users.csv</code> (exported from QuickSight admin console):</p>
<pre>grep -i "&lt;email&gt;" quicksight_users.csv</pre>
<ul>
<li><strong>Not found:</strong> User has not accessed QuickSight in 60+ days.</li>
<li><strong>Found with READER role:</strong> User is provisioned. Issue is dashboard-level permissions.</li>
</ul>

<h3>Step 2: Check Employee Status</h3>
<pre>SELECT PREFERRED_NAME, IS_ACTIVE, IS_TERMINATED, BUSINESS_TITLE
FROM GOLD_PROD.MARTS.DIM_WORKERS
WHERE IS_LATEST = TRUE AND LOWER(PRIMARY_EMAIL_ADDRESS) = '&lt;email&gt;'</pre>

<h3>Step 3: Identify Dashboard Owner</h3>
<pre>aws quicksight describe-dashboard --aws-account-id 048025451352 \
  --dashboard-id "&lt;id&gt;" --query 'Dashboard.Name' --output text

aws quicksight describe-dashboard-permissions --aws-account-id 048025451352 \
  --dashboard-id "&lt;id&gt;" \
  --query 'Permissions[?contains(Actions, `quicksight:UpdateDashboardPermissions`)].Principal' \
  --output text</pre>

<h3>Step 4: Post Triage</h3>
<p>Include: QuickSight roster status, dashboard owner(s), link to <a href="https://wiki.atl.workiva.net/spaces/BT/pages/530849193">QuickSight Troubleshooting Runbook</a>.</p>
<p><strong>Key fact:</strong> A QuickSight account is automatically provisioned when the Okta tile is used. Dashboard-level access must be granted separately by a dashboard owner.</p>

<hr/>

<h2>Handoff to DNA (Two-Phase Process)</h2>
<p>The DATA project is JSM and the DNA project is standard Jira. The REST API cannot move issues between these project types.</p>

<h3>Phase 1: Post triage and handoff comment on the DATA ticket</h3>
<h3>Phase 2: TPM manually moves in the Jira UI</h3>
<ol>
<li>Open the ticket &rarr; click <strong>Move</strong></li>
<li>Target project: <strong>DNA</strong></li>
<li>Set issue type to <strong>Story</strong> (Service Request does not exist in DNA)</li>
<li>Complete the wizard, note the new DNA key</li>
</ol>

<h3>Phase 3: Set fields on the new DNA ticket via API</h3>
<ul>
<li>Team (<code>customfield_10288</code>)</li>
<li>Component(s)</li>
<li>Assignee</li>
<li>Priority</li>
</ul>

<h3>Issue Type Mapping</h3>
<table>
<thead><tr><th>DATA Type</th><th>DNA Type</th></tr></thead>
<tbody>
<tr><td>Service Request</td><td><strong>Story</strong></td></tr>
<tr><td>Task</td><td>Task</td></tr>
<tr><td>Epic</td><td>Epic</td></tr>
<tr><td>Sub-task</td><td>Sub-task</td></tr>
</tbody>
</table>

<hr/>

<h2>RICE Prioritization</h2>
<table>
<thead><tr><th>Factor</th><th>Source</th><th>Scale</th></tr></thead>
<tbody>
<tr><td>Reach</td><td>Teams Impacted field</td><td>Entire company = 10, Multiple teams = 5, My team = 2, Just me = 1</td></tr>
<tr><td>Impact</td><td>Service Type x Business Priority</td><td>0.375 to 3.75</td></tr>
<tr><td>Confidence</td><td>Ticket completeness (5 signals at 20% each)</td><td>50% to 100%</td></tr>
<tr><td>Effort</td><td>Story points or estimated from service type</td><td>1 to 13</td></tr>
</tbody>
</table>
<p><strong>RICE = (Reach x Impact x Confidence) / Effort</strong></p>
<table>
<thead><tr><th>RICE Score</th><th>Priority Bucket</th></tr></thead>
<tbody>
<tr><td>5+</td><td>Blocker</td></tr>
<tr><td>2 - 5</td><td>High</td></tr>
<tr><td>1 - 2</td><td>Medium</td></tr>
<tr><td>&lt; 1</td><td>Low</td></tr>
</tbody>
</table>

<h2>SLA Expectations</h2>
<table>
<thead><tr><th>Business Priority (from form)</th><th>Jira Priority</th><th>SLA</th></tr></thead>
<tbody>
<tr><td>System Outage / Production Blocker</td><td>Blocker</td><td>Reviewed immediately</td></tr>
<tr><td>Fixed Deadline / Upcoming Milestone</td><td>High</td><td>Reviewed over the next business day</td></tr>
<tr><td>Standard Business Operation</td><td>Medium</td><td>Reviewed in 2-3 business days</td></tr>
<tr><td>Nice-to-have / Backlog</td><td>Low</td><td>Reviewed in 5 business days</td></tr>
</tbody>
</table>

<hr/>

<h2>Safety and Rollback</h2>
<table>
<thead><tr><th>Feature</th><th>How It Works</th></tr></thead>
<tbody>
<tr><td>Snapshots</td><td><strong>Mandatory</strong> before any modifications. <code>PYTHONPATH=$PWD python safety/snapshot.py --keys &lt;KEY&gt; --label pre_triage</code></td></tr>
<tr><td>Change log</td><td>Every action logged to <code>changes/</code></td></tr>
<tr><td>Rollback (full)</td><td><code>PYTHONPATH=$PWD python safety/rollback.py restore snapshots/&lt;file&gt;.json --execute</code></td></tr>
<tr><td>Rollback (surgical)</td><td><code>PYTHONPATH=$PWD python safety/rollback.py undo changes/&lt;file&gt;.json --keys DNA-5001 --execute</code></td></tr>
</tbody>
</table>

<h2>Quick Reference</h2>
<pre># Daily -- AI-Assisted Triage
PYTHONPATH=$PWD python safety/snapshot.py --keys DATA-XXXX --label pre_triage
PYTHONPATH=$PWD python scripts/_assess.py DATA-XXXX

# QuickSight Access
grep -i "&lt;email&gt;" quicksight_users.csv
aws quicksight describe-dashboard-permissions --aws-account-id 048025451352 --dashboard-id "&lt;id&gt;"

# Weekly
PYTHONPATH=$PWD python grooming/groom_stale.py --interactive --execute

# Monthly
PYTHONPATH=$PWD python grooming/audit_dna.py
PYTHONPATH=$PWD python grooming/groom_report.py

# Emergency
PYTHONPATH=$PWD python safety/rollback.py restore snapshots/&lt;latest&gt;.json --execute</pre>
"""

result = conf.create_page(
    space_key="BT",
    title="DATA Queue Triage Runbook \u2014 Data Operations",
    body_html=body,
    parent_id="505678345",
)
page_url = f"{result['_links']['base']}{result['_links']['webui']}"
print(f"Confluence page created: {result['id']}")
print(f"URL: {page_url}")
