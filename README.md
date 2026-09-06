# DNA AI TPM - Jira & Confluence Tooling

Python tooling for the TPM intake/triage/handoff workflow between the **DATA** (Service Desk) and **DNA** (Engineering) Jira projects.

## Setup

### 1. Generate Personal Access Tokens

**Jira (Data Center):**
- Go to your Jira profile > Personal Access Tokens
- Click "Create token", give it a name, and copy the value

**Confluence (Data Center):**
- Go to your Confluence profile > Personal Access Tokens
- Create a token the same way (separate host, may need a separate token)

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and paste your PATs
```

### 3. Install Dependencies

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Verify Connection

```bash
python verify_connection.py
```

This tests auth on both Jira and Confluence, confirms access to DATA and DNA projects, and prints the required fields/enums for creating DNA tickets.

## Modules

| File | Purpose |
|------|---------|
| `config.py` | Loads `.env` settings into a `Settings` dataclass |
| `jira_client.py` | Jira Data Center REST API v2 client |
| `confluence_client.py` | Confluence Data Center REST API client |
| `tpm_workflow.py` | High-level TPM functions (triage, SLA, handoff, cross-ref) |
| `verify_connection.py` | Connection test and field discovery script |

## Usage Example

```python
from config import load_settings
from jira_client import JiraClient
from tpm_workflow import assess_ticket, post_sla_comment, build_dna_payload, create_dna_ticket

settings = load_settings()
jira = JiraClient(settings.jira_base_url, settings.jira_pat)

# Triage a DATA ticket
assessment = assess_ticket(jira, "DATA-123")
print(assessment)

# Post SLA comment
post_sla_comment(jira, "DATA-123", assessment["priority"])

# Create DNA ticket from a refined DATA ticket
data_issue = jira.get_issue("DATA-123")
payload = build_dna_payload(data_issue, components=["Analytics"])
dna_key = create_dna_ticket(jira, "DATA-123", payload)
print(f"Created {dna_key}")
```
