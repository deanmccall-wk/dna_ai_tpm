PYTHON = .venv/bin/python
export PYTHONPATH := $(CURDIR)

.PHONY: help setup test verify snapshot assess lookup triage-plan triage-apply \
        audit-data audit-dna groom-stale groom-report repair-dna

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# -- Setup ------------------------------------------------------------------

setup: ## Create venv and install dependencies
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	@echo ""
	@echo "Next: cp .env.example .env  (edit with your tokens)"
	@echo "Then: make verify"

test: ## Run all tests
	$(PYTHON) -m pytest tests/ -v

verify: ## Test Jira + Confluence auth and discover field schemas
	$(PYTHON) scripts/verify_connection.py

# -- Triage -----------------------------------------------------------------

snapshot: ## Take pre-change snapshot (KEY=DATA-XXXX)
	$(PYTHON) safety/snapshot.py --keys $(KEY) --label pre_triage

assess: ## Run triage assessment for one ticket (KEY=DATA-XXXX)
	$(PYTHON) scripts/_assess.py $(KEY)

lookup: ## Search Atlan for assets (ARGS="dim_workers rpt_pipeline")
	$(PYTHON) scripts/lookup_asset.py $(ARGS)

triage-plan: ## Build a triage plan [PATH=auto|enrich|all]
	$(PYTHON) triage/triage_data.py plan --path $(or $(PATH),all)

triage-apply: ## Execute a triage plan (PLAN=plans/<file>.json)
	$(PYTHON) triage/triage_data.py apply $(PLAN)

audit-data: ## Audit open DATA queue
	$(PYTHON) triage/audit_data.py

# -- Grooming ---------------------------------------------------------------

audit-dna: ## Full compliance audit on DNA backlog
	$(PYTHON) grooming/audit_dna.py

groom-stale: ## Review stale DNA tickets (interactive)
	$(PYTHON) grooming/groom_stale.py --interactive --dry-run

groom-report: ## Generate grooming report (HTML + Markdown)
	$(PYTHON) grooming/groom_report.py

repair-dna: ## Bulk DNA ticket repair (dry-run)
	$(PYTHON) grooming/repair_dna.py plan --mode auto
