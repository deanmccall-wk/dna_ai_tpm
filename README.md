# DNA AI TPM - Jira & Confluence Tooling

Python tooling for the TPM intake/triage/handoff workflow between the **DATA** (Service Desk) and **DNA** (Engineering) Jira projects at Workiva.

Designed for use with **Cortex Code** (AI-assisted triage). See [COCO.md](COCO.md) for AI assistant rules that Cortex Code follows automatically.

## Architecture

```
clients/     API clients (Jira, Confluence, Atlan, GitHub)
core/        Business logic (triage assessment, RICE, asset lookup, validation)
triage/      Triage workflow scripts (audit queue, plan/apply)
grooming/    DNA backlog grooming (stale tickets, compliance repair, reports)
deletion/    Customer data deletion verification
safety/      Snapshot, rollback, dry-run safety mechanisms
scripts/     CLI entry points (assess, verify, lookup, create ticket)
tests/       Pytest test suite (54 tests)
docs/        Runbooks, Mermaid diagrams, reports
```

## Modules

### clients/
| Module | Purpose |
|--------|---------|
| `config.py` | Loads `.env` settings into a `Settings` dataclass |
| `jira_client.py` | Jira Data Center REST API v2 client with snapshot gate and dry-run |
| `confluence_client.py` | Confluence Data Center REST API client |
| `atlan_client.py` | Atlan search, lineage, and asset detail API client |
| `github_client.py` | GitHub code search, PR search, file/commit lookup |

### core/
| Module | Purpose |
|--------|---------|
| `tpm_workflow.py` | Triage assessment, SLA mapping, team recommendation, handoff |
| `rice_scoring.py` | RICE prioritization scoring from intake form fields |
| `asset_lookup.py` | Extract asset names from tickets, search Atlan and GitHub |
| `comment_validator.py` | Validate triage comments for required sections and Atlan links |
| `triage_checklist.py` | Pre-change, pre-post, and post-action checklist enforcement |
| `stakeholder_lookup.py` | Map ticket reporters to Snowflake dim_workers |

### triage/
| Module | Purpose |
|--------|---------|
| `audit_data.py` | Audit open DATA queue: conformance scoring and path classification |
| `triage_data.py` | Two-phase plan/apply triage workflow (batch mode) |

### grooming/
| Module | Purpose |
|--------|---------|
| `groom_stale.py` | Identify and close stale DNA tickets (90/180/365 day tiers) |
| `audit_dna.py` | Full compliance audit on DNA backlog |
| `groom_report.py` | Generate HTML + Markdown grooming reports |
| `repair_dna.py` | Bulk DNA ticket field repair (plan/apply with batch throttling) |

### safety/
| Module | Purpose |
|--------|---------|
| `snapshot.py` | Capture full ticket state before modifications |
| `rollback.py` | Restore tickets from snapshots or undo specific changes |

### scripts/
| Module | Purpose |
|--------|---------|
| `verify_connection.py` | Test auth and discover field schemas |
| `_assess.py` | Single-ticket triage assessment (conformance, RICE, team, assets) |
| `lookup_asset.py` | CLI tool for ad-hoc Atlan asset search |
| `create_data_ticket.py` | Create DATA tickets via JSM API (interactive or batch) |
| `publish_triage_runbook.py` | Publish triage runbook to Confluence |
| `publish_deletion_runbook.py` | Publish deletion runbook to Confluence |
| `upload_diagram.py` | Upload diagram images to Confluence pages |

## Prerequisites

- Python 3.12+
- **Jira PAT** (Data Center) -- required for all triage operations
- **Confluence PAT** (Data Center) -- required for runbook publishing
- **Atlan API token** -- required for asset lookup during triage
- **GitHub PAT** -- optional, for code/PR search during triage
- **Redshift credentials** -- optional, only for `deletion/verify_deletion.py`
- **Snowflake access** -- via Cortex Code connection (not in .env)

## Quick Start

```bash
git clone <repo-url>
cd dna_ai_tpm
make setup              # Creates venv, installs deps
cp .env.example .env    # Edit with your tokens
make verify             # Tests Jira + Confluence auth
```

### Common Tasks

```bash
make assess KEY=DATA-XXXX       # Triage assessment for one ticket
make snapshot KEY=DATA-XXXX     # Snapshot before changes
make lookup ARGS="dim_workers"  # Search Atlan for an asset
make test                       # Run all tests
```

See `make help` for all targets.

## Safety Mechanisms

| Feature | Description |
|---------|-------------|
| **Snapshot gate** | JiraClient blocks all writes unless a snapshot exists for the ticket |
| **Dry-run mode** | `JiraClient(..., dry_run=True)` logs intended writes without executing |
| **Comment validation** | Checks triage comments for required sections before posting |
| **Triage checklists** | Pre-change, pre-post, and post-action checklists enforced in code |
| **Change log** | Every modification logged to `changes/` directory |
| **Rollback** | Restore from snapshot or surgically undo specific changes |
| **Additive only** | Component repairs only add values, never remove existing ones |

## Operational Runbook

The primary operational reference is [docs/triage_runbook.md](docs/triage_runbook.md). It covers:
- AI-assisted triage workflow (daily)
- Batch triage with plan/apply
- Investigation patterns by ticket type
- Handoff to DNA (manual move + API field-set)
- RICE scoring and SLA mapping
- Weekly grooming and monthly health checks
- Safety and rollback procedures
