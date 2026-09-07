from clients.jira_client import JiraClient

# ---------------------------------------------------------------------------
# SLA / Priority
# ---------------------------------------------------------------------------

SLA_COMMENTS = {
    "Blocker": "Reviewed immediately.",
    "High": "Reviewed over the next business day.",
    "Medium": "Reviewed in 2\u20133 business days.",
    "Low": "Reviewed in 5 business days.",
}

BIZ_PRIORITY_TO_JIRA = {
    "System Outage / Production Blocker": "Blocker",
    "Fixed Deadline / Upcoming Milestone": "High",
    "Standard Business Operation": "Medium",
    "Nice-to-have / Backlog": "Low",
}

BIZ_PRIORITY_TO_SLA = {
    k: SLA_COMMENTS[v] for k, v in BIZ_PRIORITY_TO_JIRA.items()
}

# ---------------------------------------------------------------------------
# DATA project custom fields (intake form)
# ---------------------------------------------------------------------------

CF_SERVICE_TYPE = "customfield_18121"
CF_TEAMS_IMPACTED = "customfield_29221"
CF_BIZ_PRIORITY = "customfield_30221"
CF_PRIMARY_SOLUTION = "customfield_18124"
CF_EXEC_SPONSOR = "customfield_26721"
CF_MILESTONE = "customfield_23823"
CF_REQUEST_TYPE = "customfield_24027"

SERVICE_TYPES = {
    "build_new": "I need to build something new (e.g., new data integration, report or dashboard)",
    "change_existing": "I need to make changes to the existing service (e.g., modify report, add columns in Gold data model)",
    "business_question": "I need to answer a business question (e.g., data investigation or statistical analysis)",
    "troubleshooting": "I need help or troubleshooting (e.g., pipeline failure, data quality issue, or fixing a bug)",
    "access": "I need system or database access (e.g., Snowflake, BigQuery, or BI tool permissions)",
    "ml_ai": "I need predictive modeling, machine learning, or AI solutions (e.g., Cortex agents, classification models)",
    "other": "Other / General Request",
}

SERVICE_TYPE_TIERS = {
    SERVICE_TYPES["build_new"]: 3,
    SERVICE_TYPES["change_existing"]: 3,
    SERVICE_TYPES["business_question"]: 1,
    SERVICE_TYPES["troubleshooting"]: 2,
    SERVICE_TYPES["access"]: 1,
    SERVICE_TYPES["ml_ai"]: 3,
    SERVICE_TYPES["other"]: 2,
}

# ---------------------------------------------------------------------------
# DNA project custom fields
# ---------------------------------------------------------------------------

CF_TEAM = "customfield_10288"
CF_STAKEHOLDER = "customfield_36420"
CF_EPIC_NAME = "customfield_13720"
CF_EPIC_LINK = "customfield_10008"

# ---------------------------------------------------------------------------
# Valid enums
# ---------------------------------------------------------------------------

VALID_TEAMS = [
    "Data Engineering",
    "Analytics Engineering",
    "BI",
    "Data Science",
    "Data & Analytics",
    "Data Operations",
    "Data Platform and AI",
]

VALID_COMPONENTS = [
    "Ingestion / Collection",
    "Storage / Lakehouse",
    "Transformation / Compute",
    "Orchestration",
    "Data Governance & Quality",
    "BI & Consumption",
    "Core Infrastructure & CI/CD",
    "ECM",
    "C360",
]

VALID_EFFORT_POINTS = [1, 2, 3, 5, 8, 13]

EFFORT_POINT_LABELS = {
    1: "XS (1 day)",
    2: "S (2-3 days)",
    3: "M (4-5 days)",
    5: "L (2 weeks)",
    8: "XL (1-2 months)",
    13: "XXL (>2 months)",
}

COMPONENT_KEYWORD_MAP = {
    "Snowflake": ["Transformation / Compute", "Storage / Lakehouse"],
    "Snowflake Cortex": ["Transformation / Compute"],
    "DBT": ["Transformation / Compute"],
    "DBT Cloud": ["Transformation / Compute"],
    "Redshift": ["Storage / Lakehouse"],
    "Data Warehouse": ["Storage / Lakehouse"],
    "Warehouse": ["Storage / Lakehouse"],
    "Cortex": ["Transformation / Compute"],
    "Claude": ["Transformation / Compute"],
    "Airflow": ["Orchestration"],
    "Chains": ["Orchestration"],
    "Salesforce": ["Ingestion / Collection"],
    "Gainsight": ["Ingestion / Collection"],
    "OpenAir": ["Ingestion / Collection"],
    "Zendesk": ["Ingestion / Collection"],
    "Workday": ["Ingestion / Collection"],
    "Fivetran": ["Ingestion / Collection"],
    "Workato": ["Ingestion / Collection"],
    "Pitchbook": ["Ingestion / Collection"],
    "Ingestion": ["Ingestion / Collection"],
    "GES": ["Ingestion / Collection"],
    "Atlan": ["Data Governance & Quality"],
    "Data Quality": ["Data Governance & Quality"],
    "Data Governance Support": ["Data Governance & Quality"],
    "Data Governance": ["Data Governance & Quality"],
    "Data Observability": ["Data Governance & Quality"],
    "Observability": ["Data Governance & Quality"],
    "QuickSuite": ["BI & Consumption"],
    "Quick Suite": ["BI & Consumption"],
    "Streamlit": ["BI & Consumption"],
    "Snowflake CoWork": ["BI & Consumption"],
    "Consumption": ["BI & Consumption"],
    "ECM": ["ECM"],
    "C360": ["C360"],
    "C360 Support": ["C360"],
    "C360 Account": ["C360"],
    "C360 Survey": ["C360"],
    "C360 Product Usage": ["C360"],
}

REQUIRED_CRITERIA = [
    "Goal / Service Type",
    "Stakeholder Impact",
    "Business Timeline",
    "Data Domains Involved",
    "Structured Description",
]

# ---------------------------------------------------------------------------
# Team recommendation
# ---------------------------------------------------------------------------

# Primary Solution -> team mapping (most specific signal)
SOLUTION_TO_TEAM = {
    # Data Engineering owns infrastructure, ingestion, orchestration
    "Snowflake": "Data Engineering",
    "Redshift": "Data Engineering",
    "Airflow": "Data Engineering",
    "Fivetran": "Data Engineering",
    "Chains": "Data Engineering",
    "Workato": "Data Engineering",
    "Ingestion": "Data Engineering",
    "Warehouse": "Data Engineering",
    "Data Governance": "Data Engineering",
    "Data Observability": "Data Engineering",
    "Atlan": "Data Engineering",
    # Analytics Engineering owns transformations and data models
    "DBT": "Analytics Engineering",
    "DBT Cloud": "Analytics Engineering",
    # BI owns dashboards and consumption tools
    "Quick Suite": "BI",
    "Streamlit": "BI",
    "Snowflake CoWork": "BI",
    "Consumption": "BI",
    # Data Science owns statistical modeling
    # (Cortex/AI routes to Data Platform and AI virtual team instead)
    "Snowflake Cortex": "Data Platform and AI",
    "Cortex": "Data Platform and AI",
    "Claude": "Data Platform and AI",
    # Domain-specific
    "Salesforce": "Analytics Engineering",
    "Gainsight": "Analytics Engineering",
    "Zendesk": "Analytics Engineering",
    "Workday": "Analytics Engineering",
    "OpenAir": "Analytics Engineering",
    "Pitchbook": "Analytics Engineering",
    "ECM": "Analytics Engineering",
    "C360": "Analytics Engineering",
    "C360 Support": "Analytics Engineering",
    "C360 Account": "Analytics Engineering",
    "C360 Survey": "Analytics Engineering",
    "C360 Product Usage": "Analytics Engineering",
    "GES": "Data Engineering",
    "Data Quality": "Data Engineering",
}

# Virtual teams: not yet created as Jira Team values.
# Each maps to an actual Team + a Component tag for tracking.
VIRTUAL_TEAMS = {
    "Data Platform and AI": {
        "jira_team": "Data Engineering",
        "component": "Data Platform and AI",
        "keywords": ["architecture", "snowflake agent", "cortex", "vector", "rls",
                     "mcp", "semantic", "ai ", "llm", "governance analytics",
                     "access governance"],
    },
    "Data Operations": {
        "jira_team": "Data Engineering",
        "component": "Operations",
        "keywords": ["small change", "minor", "quick fix", "access", "permission",
                     "role", "grant", "deletion", "delete", "data deletion",
                     "audit", "cleanup", "silver", "changes to silver",
                     "add field", "add fields", "add column", "add columns",
                     "existing source", "new field", "new column"],
    },
}

# Service Type -> team fallback (when no primary solution is set)
SERVICE_TYPE_TO_TEAM = {
    SERVICE_TYPES["build_new"]: "Analytics Engineering",
    SERVICE_TYPES["change_existing"]: "Data Operations",
    SERVICE_TYPES["business_question"]: "BI",
    SERVICE_TYPES["troubleshooting"]: "Data Engineering",
    SERVICE_TYPES["access"]: "Data Operations",
    SERVICE_TYPES["ml_ai"]: "Data Platform and AI",
    SERVICE_TYPES["other"]: "Data Operations",
}


def recommend_team(fields: dict) -> dict:
    """Recommend a DNA team based on Primary Solution, Service Type, and keywords.

    May return a virtual team name (e.g. "Data Platform and AI").
    Use resolve_virtual_team() to get the actual Jira Team + Component.

    Returns {"team": str, "confidence": str, "reason": str}.
    """
    text = ((fields.get("summary") or "") + " " + (fields.get("description") or "")).lower()

    # Check virtual team keywords first (they're more specific than general signals)
    for vteam, config in VIRTUAL_TEAMS.items():
        if any(kw in text for kw in config["keywords"]):
            matched = [kw for kw in config["keywords"] if kw in text]
            return {"team": vteam, "confidence": "medium",
                    "reason": f"Keywords: {', '.join(matched[:3])}"}

    # Primary Solution (most specific)
    primary_solutions = _get_field_value(fields, CF_PRIMARY_SOLUTION) or []
    if isinstance(primary_solutions, str):
        primary_solutions = [primary_solutions]

    solution_teams = []
    for ps in primary_solutions:
        team = SOLUTION_TO_TEAM.get(ps)
        if team:
            solution_teams.append((team, ps))

    if solution_teams:
        unique_teams = set(t for t, _ in solution_teams)
        if len(unique_teams) == 1:
            team = solution_teams[0][0]
            sources = ", ".join(ps for _, ps in solution_teams)
            return {"team": team, "confidence": "high", "reason": f"Primary Solution: {sources}"}
        else:
            from collections import Counter
            team_counts = Counter(t for t, _ in solution_teams)
            team = team_counts.most_common(1)[0][0]
            return {"team": team, "confidence": "medium", "reason": f"Primary Solution (mixed): {', '.join(ps for _, ps in solution_teams)}"}

    # Service Type fallback
    service_type = _get_field_value(fields, CF_SERVICE_TYPE) or ""
    if service_type and service_type in SERVICE_TYPE_TO_TEAM:
        team = SERVICE_TYPE_TO_TEAM[service_type]
        return {"team": team, "confidence": "low", "reason": f"Service Type: {service_type[:60]}"}

    # General keyword fallback
    keyword_teams = {
        "Data Engineering": ["pipeline", "ingestion", "airflow", "fivetran", "snowflake", "infrastructure", "etl", "data load"],
        "Analytics Engineering": ["dbt", "transformation", "gold layer", "obt", "mart", "dimension", "fact table"],
        "BI": ["dashboard", "report", "quicksuite", "quicksight", "visualization", "chart"],
    }
    for team, keywords in keyword_teams.items():
        if any(kw in text for kw in keywords):
            matched = [kw for kw in keywords if kw in text]
            return {"team": team, "confidence": "low", "reason": f"Keywords: {', '.join(matched[:3])}"}

    return {"team": "Data Operations", "confidence": "low", "reason": "No signals — default"}


def resolve_virtual_team(team_name: str) -> dict:
    """Resolve a team name (possibly virtual) to actual Jira field values.

    Returns {"team": str, "component": str or None}.
    - team: the Jira Team field value to set
    - component: an additional component to add (for virtual team tracking), or None
    """
    if team_name in VIRTUAL_TEAMS:
        config = VIRTUAL_TEAMS[team_name]
        return {"team": config["jira_team"], "component": config["component"]}
    return {"team": team_name, "component": None}


def propose_summary(fields: dict) -> str:
    """Propose a concise title when the current summary is generic (e.g. 'General Request').

    Aims for a short, scannable title like:
      "Add Gainsight CTA fields to Snowflake"
      "FX rates missing from OANDA candle table"
      "[Warehouse] T&E dashboard spend reporting"
    """
    current = (fields.get("summary") or "").strip()
    if current.lower() not in ("general request", "general request ", ""):
        return ""

    description = fields.get("description") or ""
    service_type = _get_field_value(fields, CF_SERVICE_TYPE) or ""
    primary_solutions = _get_field_value(fields, CF_PRIMARY_SOLUTION) or []
    if isinstance(primary_solutions, str):
        primary_solutions = [primary_solutions]

    skip_phrases = [
        "please write a few sentence",
        "the core problem, its business value",
        "acceptance criteria",
        "definition of \"done\"",
        "specific requirements, deliverables",
        "post-launch impact",
    ]

    lines = description.replace("\r\n", "\n").split("\n")

    # Check for explicit title
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("*Title:*"):
            title = stripped.replace("*Title:*", "").strip().rstrip(".")
            if title and len(title) > 5:
                return _truncate_title(title)

    # Extract meaningful content lines
    meaningful = []
    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) < 15:
            continue
        if any(p in stripped.lower() for p in skip_phrases):
            continue
        # Strip Jira markup labels
        for label in ["*Strategic Context:*", "*Scope of Work:*", "*Success Metrics:*",
                       "Strategic Context:", "Scope of Work:", "Success Metrics:"]:
            stripped = stripped.replace(label, "").strip()
        if stripped and len(stripped) > 10:
            meaningful.append(stripped)

    if not meaningful:
        # Fallback from service type + solution
        return _fallback_title(service_type, primary_solutions)

    # Take the first meaningful line and condense it to a title
    raw = meaningful[0].rstrip(".")

    # Trim common filler openings
    filler = ["we have created ", "we have ", "we need to ", "we need ", "we would like to ",
              "we'd like to ", "we are ", "we're ",
              "i need to ", "i need ", "i would like to ", "i'd like to ",
              "i'm requesting support to help with the ", "i'm requesting support to ",
              "i'm requesting ", "i am requesting ",
              "requesting ", "request to ", "can we ", "could we ", "please ",
              "hi team, ", "hello, ", "hi! ", "hi, ",
              "currently ", "our ", "the ", "with the "]
    lower = raw.lower()
    for f in filler:
        if lower.startswith(f):
            raw = raw[len(f):]
            raw = raw[0].upper() + raw[1:] if raw else raw
            break

    title = _truncate_title(raw, max_len=60)

    # Prepend primary solution tag if not already referenced
    if primary_solutions:
        sol = primary_solutions[0]
        if sol.lower() not in title.lower():
            title = f"[{sol}] {title}"
            title = _truncate_title(title, max_len=72)

    return title


def _truncate_title(text: str, max_len: int = 80) -> str:
    if len(text) <= max_len:
        return text
    # Cut at last word boundary
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip(" .,;:") + "..."


def _fallback_title(service_type: str, primary_solutions: list[str]) -> str:
    short_types = {
        SERVICE_TYPES["build_new"]: "New build",
        SERVICE_TYPES["change_existing"]: "Change request",
        SERVICE_TYPES["business_question"]: "Data question",
        SERVICE_TYPES["troubleshooting"]: "Troubleshooting",
        SERVICE_TYPES["access"]: "Access request",
        SERVICE_TYPES["ml_ai"]: "ML/AI request",
        SERVICE_TYPES["other"]: "Request",
    }
    parts = []
    if service_type and service_type in short_types:
        parts.append(short_types[service_type])
    if primary_solutions:
        parts.append(" + ".join(primary_solutions[:2]))
    return " — ".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# DATA ticket assessment (form-field based)
# ---------------------------------------------------------------------------

def _get_field_value(fields: dict, field_id: str):
    val = fields.get(field_id)
    if isinstance(val, dict):
        return val.get("value", val.get("name", ""))
    if isinstance(val, list) and val:
        return [v.get("value", v.get("name", "")) if isinstance(v, dict) else v for v in val]
    return val


def classify_conformance(fields: dict) -> dict:
    """Score a DATA ticket's conformance 0-5 based on form field presence."""
    checks = {
        "service_type": bool(fields.get(CF_SERVICE_TYPE)),
        "teams_impacted": bool(fields.get(CF_TEAMS_IMPACTED)),
        "biz_priority": bool(fields.get(CF_BIZ_PRIORITY)),
        "primary_solution": bool(fields.get(CF_PRIMARY_SOLUTION)),
        "description": bool(fields.get("description") and len(fields["description"]) > 20),
    }
    score = sum(checks.values())
    return {
        "checks": checks,
        "score": score,
        "path": "AUTO" if score >= 4 else "ENRICH",
    }


def assess_data_ticket(fields: dict, issue_key: str = "") -> dict:
    """Assess a DATA ticket using form fields (not keyword matching)."""
    conformance = classify_conformance(fields)

    service_type_val = _get_field_value(fields, CF_SERVICE_TYPE) or ""
    biz_priority_val = _get_field_value(fields, CF_BIZ_PRIORITY) or ""
    teams_impacted_val = _get_field_value(fields, CF_TEAMS_IMPACTED) or []
    primary_solution_val = _get_field_value(fields, CF_PRIMARY_SOLUTION) or []
    sponsor_val = _get_field_value(fields, CF_EXEC_SPONSOR) or ""
    milestone_val = fields.get(CF_MILESTONE) or ""

    jira_priority = BIZ_PRIORITY_TO_JIRA.get(biz_priority_val, "Medium")
    sla = SLA_COMMENTS.get(jira_priority, SLA_COMMENTS["Medium"])
    tier = SERVICE_TYPE_TIERS.get(service_type_val, 2)

    return {
        "issue_key": issue_key,
        "summary": fields.get("summary", ""),
        "issue_type": fields.get("issuetype", {}).get("name", ""),
        "conformance": conformance,
        "service_type": service_type_val,
        "biz_priority": biz_priority_val,
        "jira_priority": jira_priority,
        "sla": sla,
        "tier": tier,
        "teams_impacted": teams_impacted_val,
        "primary_solution": primary_solution_val,
        "sponsor": sponsor_val,
        "milestone": milestone_val,
    }


# ---------------------------------------------------------------------------
# SLA comment posting
# ---------------------------------------------------------------------------

def post_sla_comment(jira: JiraClient, issue_key: str, priority: str,
                     rice: dict = None, asset_context: dict = None) -> dict:
    """Post the main triage comment with SLA, optional RICE, and optional asset links."""
    from core.rice_scoring import format_rice_inline
    from core.asset_lookup import format_asset_jira_comment

    parts = [
        f"*Priority:* {priority}",
        f"*SLA:* {SLA_COMMENTS.get(priority, SLA_COMMENTS['Medium'])}",
    ]
    if rice:
        parts.append("")
        parts.append(format_rice_inline(rice))
    if asset_context and asset_context.get("asset_names"):
        parts.append("")
        parts.append(format_asset_jira_comment(asset_context))

    comment_body = "\n".join(parts)
    return jira.add_comment(issue_key, comment_body)


# ---------------------------------------------------------------------------
# DNA ticket validation
# ---------------------------------------------------------------------------

def validate_dna_fields(issue_type: str, fields: dict) -> list[str]:
    errors = []

    if not fields.get(CF_TEAM):
        errors.append(f"Team ({CF_TEAM}) is required.")

    if not fields.get(CF_STAKEHOLDER):
        errors.append(f"Stakeholder ({CF_STAKEHOLDER}) is required.")

    components = fields.get("components", [])
    if components:
        for c in components:
            name = c.get("name", c) if isinstance(c, dict) else c
            if name not in VALID_COMPONENTS:
                pass  # informal components are allowed (additive-only strategy)

    if issue_type == "Epic":
        if not fields.get(CF_EPIC_NAME):
            errors.append(f"Epic Name ({CF_EPIC_NAME}) is required for Epics.")

    if issue_type in ("Story", "Task", "Bug", "Support Ticket"):
        if not fields.get("story_points") and not fields.get("customfield_10004"):
            errors.append("Effort points are required on all issues.")
        official = [c for c in components
                    if (c.get("name") if isinstance(c, dict) else c) in VALID_COMPONENTS]
        if not official:
            errors.append("At least one official Component is required on issues.")

    if "reporter" in fields:
        errors.append("reporter must not be included (auto-set by Jira).")
    if "duedate" in fields:
        errors.append("duedate must not be included (not on DNA screens).")

    return errors


def check_dna_compliance(issue: dict) -> dict:
    """Check a single DNA issue for field compliance. Returns violation dict."""
    fields = issue.get("fields", {})
    issue_type = fields.get("issuetype", {}).get("name", "")
    key = issue.get("key", "")

    team_field = fields.get(CF_TEAM)
    team_val = team_field.get("value") if isinstance(team_field, dict) else None

    components = [c.get("name", "") for c in fields.get("components", [])]
    has_official_component = any(c in VALID_COMPONENTS for c in components)

    violations = {}
    violations["missing_team"] = team_val is None
    violations["invalid_team"] = team_val is not None and team_val not in VALID_TEAMS
    violations["missing_stakeholder"] = not fields.get(CF_STAKEHOLDER)

    if issue_type in ("Story", "Task", "Bug", "Support Ticket", "Sub-task"):
        violations["missing_effort"] = (
            not fields.get("story_points") and not fields.get("customfield_10004")
        )
        violations["missing_official_component"] = not has_official_component
        violations["missing_epic_link"] = not fields.get(CF_EPIC_LINK)
    else:
        violations["missing_effort"] = False
        violations["missing_official_component"] = False
        violations["missing_epic_link"] = False

    if issue_type == "Epic":
        violations["missing_epic_name"] = not fields.get(CF_EPIC_NAME)
    else:
        violations["missing_epic_name"] = False

    violations["has_any"] = any(violations.values())

    return {
        "key": key,
        "issue_type": issue_type,
        "team": team_val or "",
        "status": fields.get("status", {}).get("name", ""),
        "violations": violations,
    }


# ---------------------------------------------------------------------------
# DNA ticket creation and handoff
# ---------------------------------------------------------------------------

def build_dna_payload(
    data_issue: dict,
    project_key: str = "DNA",
    issue_type: str = "Story",
    components: list[str] = None,
    team: str = "",
    stakeholders: list[dict] = None,
    effort_points: int = None,
    epic_link: str = "",
    epic_name: str = "",
    service_type: str = "",
    extra_fields: dict = None,
    validate: bool = True,
) -> dict:
    fields = data_issue.get("fields", {})
    summary = fields.get("summary", "")
    description = fields.get("description", "")
    priority_name = fields.get("priority", {}).get("name", "Medium")

    payload_fields = {
        "project": {"key": project_key},
        "issuetype": {"name": issue_type},
        "summary": summary,
        "description": description,
        "priority": {"name": priority_name},
    }

    if components:
        payload_fields["components"] = [{"name": c} for c in components]
    if team:
        payload_fields[CF_TEAM] = {"value": team}
    if stakeholders:
        payload_fields[CF_STAKEHOLDER] = stakeholders
    if effort_points is not None:
        payload_fields["story_points"] = effort_points
    if epic_link:
        payload_fields[CF_EPIC_LINK] = epic_link
    if epic_name:
        payload_fields[CF_EPIC_NAME] = epic_name
    if service_type:
        payload_fields[CF_SERVICE_TYPE] = {"value": service_type}
    if extra_fields:
        for k, v in extra_fields.items():
            if k not in ("reporter", "duedate"):
                payload_fields[k] = v

    payload = {"fields": payload_fields}
    if validate:
        errors = validate_dna_fields(issue_type, payload_fields)
        if errors:
            raise ValueError(
                "DNA payload validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )
    return payload


# Issue types that exist in both DATA and DNA (moveable)
MOVEABLE_TYPES = {"Epic", "Sub-task", "Task"}

# DATA types that must be converted when moving to DNA
TYPE_CONVERSION = {
    "Service Request": "Story",  # Service Request doesn't exist in DNA
}


def prepare_move_instructions(jira: JiraClient, issue_key: str,
                              team: str = "", components: list[str] = None) -> dict:
    """Prepare instructions for a manual Jira UI move from DATA to DNA.

    Returns a dict with move instructions and planned field values.
    The actual move must be done in the Jira UI because JSM (DATA) to
    standard (DNA) project moves are not supported via the REST API.
    """
    current = jira.get_issue(issue_key, fields=[
        "issuetype", CF_BIZ_PRIORITY, CF_PRIMARY_SOLUTION,
        CF_EXEC_SPONSOR, "priority", "components",
    ])
    current_fields = current["fields"]
    current_type = current_fields["issuetype"]["name"]
    target_type = TYPE_CONVERSION.get(current_type, current_type)

    # Derive components from Primary Solution
    primary_solutions = _get_field_value(current_fields, CF_PRIMARY_SOLUTION) or []
    if isinstance(primary_solutions, str):
        primary_solutions = [primary_solutions]
    existing_comps = [c.get("name", "") for c in current_fields.get("components", [])]
    derived_comps = set()
    for ps in primary_solutions:
        mapped = COMPONENT_KEYWORD_MAP.get(ps, [])
        derived_comps.update(mapped)
    if components:
        derived_comps.update(components)
    all_comps = sorted(set(existing_comps) | derived_comps)

    # Derive priority
    biz_priority = _get_field_value(current_fields, CF_BIZ_PRIORITY)
    jira_priority = BIZ_PRIORITY_TO_JIRA.get(biz_priority, "Medium") if biz_priority else "Medium"

    return {
        "issue_key": issue_key,
        "source_project": "DATA",
        "target_project": "DNA",
        "source_type": current_type,
        "target_type": target_type,
        "team": team,
        "priority": jira_priority,
        "components": all_comps,
        "steps": [
            f"Open {issue_key} in Jira",
            "Click Move (top-right menu or ••• → Move)",
            "Target project: DNA",
            f"Set issue type: {target_type} (maps from {current_type})",
            "Complete the move wizard — leave other fields as-is (the API will set them next)",
        ],
    }


def set_dna_fields(jira: JiraClient, issue_key: str,
                   team: str = "", stakeholder_username: str = "",
                   components: list[str] = None, effort_points: int = None,
                   epic_link: str = "", priority: str = "",
                   extra_fields: dict = None) -> str:
    """Set DNA-required fields on a ticket that has already been moved to DNA.

    Call this after the manual Jira UI move from DATA to DNA.
    Sets team, stakeholder, components (additive), effort, epic link, and priority.
    Posts a triage comment summarizing the changes. Returns the issue key.
    """
    current = jira.get_issue(issue_key, fields=["components"])
    current_fields = current["fields"]

    fields = {}
    comment_lines = ["DNA fields set during triage:"]

    # Priority
    if priority:
        fields["priority"] = {"name": priority}
        comment_lines.append(f"* Priority: {priority}")

    # Team
    if team:
        fields[CF_TEAM] = {"value": team}
        comment_lines.append(f"* Team: {team}")

    # Stakeholder
    if stakeholder_username:
        fields[CF_STAKEHOLDER] = [{"name": stakeholder_username}]
        comment_lines.append(f"* Stakeholder: {stakeholder_username}")

    # Components (additive-only)
    existing_comps = [c.get("name", "") for c in current_fields.get("components", [])]
    if components:
        new_comps = sorted(set(components) - set(existing_comps))
        if new_comps:
            merged = existing_comps + new_comps
            fields["components"] = [{"name": c} for c in merged]
            comment_lines.append(f"* Components: added {', '.join(new_comps)}")

    # Effort points
    if effort_points is not None:
        fields["story_points"] = effort_points
        comment_lines.append(f"* Effort: {effort_points} points")

    # Epic link
    if epic_link:
        fields[CF_EPIC_LINK] = epic_link
        comment_lines.append(f"* Epic: {epic_link}")

    # Extra fields
    if extra_fields:
        for k, v in extra_fields.items():
            if k not in ("reporter", "duedate"):
                fields[k] = v

    if fields:
        jira.update_issue(issue_key, fields)
    jira.add_comment(issue_key, "\n".join(comment_lines))

    return issue_key


def create_dna_ticket(jira: JiraClient, data_issue_key: str, dna_payload: dict) -> str:
    result = jira.create_issue(dna_payload)
    dna_key = result["key"]
    cross_reference(jira, data_issue_key, dna_key)
    return dna_key


def cross_reference(jira: JiraClient, data_key: str, dna_key: str) -> None:
    jira.add_comment(data_key, f"Engineering ticket created: {dna_key}")
    jira.add_comment(dna_key, f"Originated from service desk ticket: {data_key}")


def close_data_ticket(jira: JiraClient, issue_key: str) -> None:
    transitions = jira.get_transitions(issue_key)
    close_transition = None
    for t in transitions:
        if t["name"].lower() in ("done", "closed", "close", "resolve"):
            close_transition = t
            break
    if not close_transition:
        available = [t["name"] for t in transitions]
        raise RuntimeError(
            f"No close/done transition found for {issue_key}. "
            f"Available transitions: {available}"
        )
    jira.transition_issue(issue_key, close_transition["id"])


# ---------------------------------------------------------------------------
# Deletion ticket detection
# ---------------------------------------------------------------------------

DELETION_RUNBOOK_URL = "https://wiki.atl.workiva.net/spaces/BT/pages/530849217"

DELETION_KEYWORDS = [
    "data deletion", "delete end client data", "certificate of destruction",
    "deletion request", "workspace deletion", "org deletion",
]


def is_deletion_ticket(fields: dict) -> bool:
    text = ((fields.get("summary") or "") + " " + (fields.get("description") or "")).lower()
    return any(kw in text for kw in DELETION_KEYWORDS)


# ---------------------------------------------------------------------------
# Related ticket discovery and linking
# ---------------------------------------------------------------------------

def find_related_tickets(jira: JiraClient, key: str, fields: dict,
                         max_results: int = 5) -> list[str]:
    """Search for related DATA/DNA tickets based on summary keywords.

    Returns list of related ticket keys (excluding the source key).
    """
    summary = fields.get("summary", "")
    # Extract meaningful words (skip short/common words)
    stop_words = {"the", "a", "an", "to", "for", "in", "of", "and", "or",
                  "is", "it", "my", "me", "we", "new", "data", "request",
                  "general", "need", "help", "please", "from", "with"}
    words = [w for w in summary.split() if len(w) > 2 and w.lower() not in stop_words]
    if not words:
        return []

    search_terms = " ".join(words[:5])
    jql = (
        f'project IN (DATA, DNA) AND key != "{key}" '
        f'AND text ~ "{search_terms}" ORDER BY created DESC'
    )
    try:
        results = jira.search(jql, fields=["summary"], max_results=max_results)
        return [iss["key"] for iss in results.get("issues", [])]
    except Exception:
        return []


def link_related_tickets(jira: JiraClient, key: str, related_keys: list[str]) -> int:
    """Create 'Related' links between key and each related_key. Returns count of links created."""
    linked = 0
    for related in related_keys:
        try:
            jira.session.post(
                f"{jira.base_url}/rest/api/2/issueLink",
                json={
                    "type": {"name": "Related"},
                    "inwardIssue": {"key": key},
                    "outwardIssue": {"key": related},
                },
            )
            linked += 1
        except Exception:
            pass
    return linked
