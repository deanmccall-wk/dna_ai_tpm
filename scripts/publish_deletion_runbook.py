#!/usr/bin/env python3
"""Publish the Data Deletion Runbook to Confluence."""
from clients.config import load_settings
from clients.confluence_client import ConfluenceClient

s = load_settings()
conf = ConfluenceClient(s.confluence_base_url, s.confluence_pat)

body = """
<h2>Overview</h2>
<p>This runbook covers the Data Operations steps for processing customer data deletion requests. These tickets originate from SaaS Ops, flow through SSE operators for deletion execution, and require Data Operations to verify redaction and close the ticket.</p>
<p><strong>Data Operations owns Steps 3, 4, and 5.</strong> The other steps are documented here for context.</p>

<h2>End-to-End Workflow</h2>
<table>
<thead><tr><th>Step</th><th>Owner</th><th>Description</th></tr></thead>
<tbody>
<tr><td>1. Intake and verification</td><td>SSE Operator</td><td>Confirm org/workspace IDs with requester, create Deletion Tracking Document, request CSADMIN access</td></tr>
<tr><td>2. Deletion actions</td><td>SSE Operator</td><td>Run 6 ordered actions via Support Viewer (force shred, S16 deletion, workspace data deletion, group deletion, retention policy, GES lifecycle event)</td></tr>
<tr><td><strong>3. Field redaction verification</strong></td><td><strong>Data Operations</strong></td><td>Run verification queries in Snowflake and Redshift, confirm PII redacted</td></tr>
<tr><td><strong>4. Salesforce verification</strong></td><td><strong>Data Operations</strong></td><td>Verify deletion reflected in Salesforce account records</td></tr>
<tr><td><strong>5. Close and notify</strong></td><td><strong>Data Operations</strong></td><td>Post completion comment, close ticket</td></tr>
<tr><td>6. Certificate of Destruction</td><td>Legal</td><td>If requested by customer (Clay Stanley approval, DocuSign via Sarah Goodall / Lynn Peng)</td></tr>
</tbody>
</table>

<h2>Context: Steps 1-2 (SSE Operator)</h2>

<h3>Step 1 - Intake and Verification</h3>
<p>The SSE operator:</p>
<ul>
<li>Confirms Org ID and Workspace ID(s) with the requester</li>
<li>Creates a Deletion Tracking Document in the Wdesk sandbox</li>
<li>Grants the requester viewer permission to the tracking doc</li>
<li>Creates a CSADMIN ticket if org/workspace access is needed</li>
<li>Links related tickets (SUPP, CSADMIN, OMR)</li>
</ul>

<h3>Step 2 - Deletion Actions via Support Viewer</h3>
<p>The SSE operator runs these actions in order, attaching JSON result files to the ticket:</p>
<ol>
<li><strong>Force Shred</strong> - Content Management Support: "Shred - Force Shred for Account"</li>
<li><strong>S16/Filing Deletion</strong> - Filing Data Server: "Delete All Section 16 Data For Account"</li>
<li><strong>Workspace Data Deletion</strong> - Cerebral Support Service: "Workspace Data Deletion"</li>
<li><strong>Group Deletion</strong> - IAM Support Viewer: "Delete all groups in a workspace/organization"</li>
<li><strong>Organization Retention Policy</strong> - "Update Organization Retention Policy"</li>
<li><strong>GES Lifecycle Event</strong> - Support Viewer Service: "Submit Delete Workspace or Organization Lifecycle Event to GES"</li>
</ol>
<p><strong>Data Operations picks up after all 6 action result files are attached to the ticket.</strong></p>

<hr/>

<h2>Step 3 - Field Redaction Verification (Data Operations)</h2>

<h3>When to Run</h3>
<p>After the SSE operator posts all deletion action result files to the ticket. Look for comments with attached JSON files.</p>

<h3>Finding the Org ID</h3>
<p>The org_id is in the ticket description, typically in a code block, e.g.:<br/>
<code>Org ID: e4e54d60-463d-4b7d-ab5d-9f6a8a426a5c</code></p>

<h3>Automated Verification</h3>
<pre>
source .venv/bin/activate
python verify_deletion.py DATA-2439              # Run queries, print results
python verify_deletion.py DATA-2439 --post       # Run and post results to Jira
python verify_deletion.py DATA-2439 --post --close   # Run, post, and close
</pre>

<p>The script runs all queries against both Snowflake and Redshift and formats a combined report.</p>

<h3>Manual Verification (if needed)</h3>
<p>Run these queries in both <strong>Snowflake</strong> and <strong>Redshift</strong>, substituting the org_id:</p>
<pre>
-- 1. Workspace records
SELECT * FROM audit.workiva_workspace WHERE organization_id = '&lt;org_id&gt;';

-- 2. Organization record
SELECT * FROM workiva.organization WHERE organization_id = '&lt;org_id&gt;';

-- 3. Classic account records
SELECT * FROM audit.wdesk_classic_account WHERE organization_id = '&lt;org_id&gt;';

-- 4. Workspace solution records
SELECT * FROM public.workiva_workspace_solution WHERE organization_id = '&lt;org_id&gt;';
</pre>

<p><strong>What to look for:</strong> All returned rows should show redacted/nulled PII fields. If any fields still contain customer data, escalate back to the SSE operator.</p>
<p>Post query output to the Jira ticket with: <strong>"Field redaction completed."</strong></p>

<h2>Step 4 - Salesforce Verification (Data Operations)</h2>
<p>Verify the deletion is reflected in Salesforce account records:</p>
<pre>
SELECT DISTINCT swa.id AS sf_account_id
FROM admin.workiva_org_deletes d
LEFT JOIN public.workiva_workspace ww
  ON ww.organization_id = d.organization_id
LEFT JOIN admin.salesforce_wdesk_classic_account swa
  ON swa.account_resource_id = ww.account_resource_id
WHERE d.organization_id = '&lt;org_id&gt;';
</pre>

<h2>Step 5 - Close and Notify (Data Operations)</h2>
<p>Post a completion comment tagging the SSE operator and SaaS Ops:</p>
<pre>
&lt;Customer Name&gt; - &lt;Request Type&gt; is completed.
[~&lt;sse_operator_username&gt;] [~service_saasops] request is completed.
</pre>
<p>Then close the ticket (transition to Done/Closed).</p>

<h3>Parent/Child Tickets</h3>
<p>Some customers (e.g., Bank of America, PwC UK) have a parent ticket with multiple child workspace tickets:</p>
<ol>
<li>Verify and close each <strong>child</strong> workspace ticket first</li>
<li>Once all children are closed, verify and close the <strong>parent</strong> ticket</li>
</ol>

<h2>Jira Field Values for DATA-to-DNA Move</h2>
<table>
<thead><tr><th>Field</th><th>Value</th></tr></thead>
<tbody>
<tr><td>Team</td><td>Data Engineering</td></tr>
<tr><td>Stakeholder</td><td>Legal</td></tr>
<tr><td>Component</td><td>Operations</td></tr>
<tr><td>Work Type</td><td>Maintenance</td></tr>
<tr><td>Epic Link</td><td>DNA-2543</td></tr>
<tr><td>Priority</td><td>Per business priority, default High</td></tr>
</tbody>
</table>

<h2>Edge Cases</h2>
<ul>
<li><strong>Blocked by CSADMIN:</strong> Operator may need org/workspace access. Watch for CSADMIN ticket links.</li>
<li><strong>Blocked by Integrated Automations (IA):</strong> Orphaned automations must be deleted first. Look for IA ticket links.</li>
<li><strong>Blocked by dev PRs:</strong> Occasionally a code fix is needed before force shred works.</li>
<li><strong>Cross-region (EU appspot):</strong> PwC UK tickets use EU infrastructure.</li>
<li><strong>Carbon data:</strong> Carbon-specific deletions require coordination with Carbon dev team.</li>
</ul>
"""

result = conf.create_page(
    space_key="BT",
    title="Customer Data Deletion \u2014 Data Operations Runbook",
    body_html=body,
    parent_id="505678345",
)
page_url = f"{result['_links']['base']}{result['_links']['webui']}"
print(f"Confluence page created: {result['id']}")
print(f"URL: {page_url}")
