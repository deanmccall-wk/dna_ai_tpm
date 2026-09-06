from jira_client import JiraClient

SLA_COMMENTS = {
    "Blocker": "Reviewed immediately.",
    "High": "Reviewed over the next business day.",
    "Medium": "Reviewed in 2\u20133 business days.",
    "Low": "Reviewed in 5 business days.",
}

REQUIRED_CRITERIA = [
    "Goal / Service Type",
    "Stakeholder Impact",
    "Business Timeline",
    "Data Domains Involved",
    "Structured Description",
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

VALID_TEAMS = [
    "Data Engineering",
    "Analytics Engineering",
    "Automation Engineering",
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

# Custom field IDs from the DNA project
CF_TEAM = "customfield_10288"
CF_STAKEHOLDER = "customfield_36420"
CF_EPIC_NAME = "customfield_13720"


def assess_ticket(jira: JiraClient, issue_key: str) -> dict:
    """Fetch a DATA ticket and check for the 5 structured criteria."""
    issue = jira.get_issue(issue_key)
    description = (issue.get("fields", {}).get("description") or "").lower()

    missing = []
    keyword_map = {
        "Goal / Service Type": ["goal", "service type"],
        "Stakeholder Impact": ["stakeholder", "impact"],
        "Business Timeline": ["timeline", "deadline", "due"],
        "Data Domains Involved": ["data domain", "domain"],
        "Structured Description": ["strategic context", "scope of work", "success metrics"],
    }

    for criterion, keywords in keyword_map.items():
        if not any(kw in description for kw in keywords):
            missing.append(criterion)

    priority_name = (
        issue.get("fields", {}).get("priority", {}).get("name", "Medium")
    )

    return {
        "issue_key": issue_key,
        "summary": issue.get("fields", {}).get("summary", ""),
        "priority": priority_name,
        "missing_criteria": missing,
        "sla_comment": SLA_COMMENTS.get(priority_name, SLA_COMMENTS["Medium"]),
        "is_complete": len(missing) == 0,
    }


def post_sla_comment(jira: JiraClient, issue_key: str, priority: str) -> dict:
    """Post the priority-based SLA auto-comment to a DATA ticket."""
    comment_body = (
        f"*Priority:* {priority}\n"
        f"*SLA:* {SLA_COMMENTS.get(priority, SLA_COMMENTS['Medium'])}"
    )
    return jira.add_comment(issue_key, comment_body)


def validate_dna_fields(issue_type: str, fields: dict) -> list[str]:
    """Validate DNA ticket fields against the DnA Ticket Requirements. Returns list of errors."""
    errors = []

    # Team is required on all issue types
    if not fields.get(CF_TEAM):
        errors.append(f"Team ({CF_TEAM}) is required.")

    # Stakeholder is required on all issue types
    if not fields.get(CF_STAKEHOLDER):
        errors.append(f"Stakeholder ({CF_STAKEHOLDER}) is required.")

    # Components validation
    components = fields.get("components", [])
    if components:
        for c in components:
            name = c.get("name", c) if isinstance(c, dict) else c
            if name not in VALID_COMPONENTS:
                errors.append(f"Invalid component '{name}'. Valid: {VALID_COMPONENTS}")

    # Epic-specific rules
    if issue_type == "Epic":
        if not fields.get(CF_EPIC_NAME):
            errors.append(f"Epic Name ({CF_EPIC_NAME}) is required for Epics.")

    # Issue-level rules (Story, Task, Bug, Support Ticket)
    if issue_type in ("Story", "Task", "Bug", "Support Ticket"):
        if not fields.get("story_points") and not fields.get("customfield_10004"):
            errors.append("Effort points are required on all issues.")
        if not components:
            errors.append("At least one Component is required on issues.")

    # Excluded fields that must not be sent
    if "reporter" in fields:
        errors.append("reporter must not be included (auto-set by Jira).")
    if "duedate" in fields:
        errors.append("duedate must not be included (not on DNA screens).")

    return errors


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
    """Build a DNA ticket creation payload from a DATA issue.

    Enforces DnA Ticket Requirements:
    - Components as array of {"name": ...} objects
    - Team (cf[10288]) required
    - Stakeholder (cf[36420]) required
    - Effort points required on issues
    - Epic Name required on Epics
    - No reporter or due date fields
    - Empty string for missing optional fields
    """
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
        payload_fields["customfield_10008"] = epic_link

    if epic_name:
        payload_fields[CF_EPIC_NAME] = epic_name

    if service_type:
        payload_fields["customfield_service_type"] = {"value": service_type}

    if extra_fields:
        for k, v in extra_fields.items():
            if k not in ("reporter", "duedate"):
                payload_fields[k] = v

    payload = {"fields": payload_fields}

    if validate:
        errors = validate_dna_fields(issue_type, payload_fields)
        if errors:
            raise ValueError(
                f"DNA payload validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

    return payload


def create_dna_ticket(
    jira: JiraClient, data_issue_key: str, dna_payload: dict
) -> str:
    """Create the DNA execution ticket. Returns the new issue key."""
    result = jira.create_issue(dna_payload)
    dna_key = result["key"]
    cross_reference(jira, data_issue_key, dna_key)
    return dna_key


def cross_reference(jira: JiraClient, data_key: str, dna_key: str) -> None:
    """Post linking comments on both DATA and DNA tickets."""
    jira.add_comment(
        data_key,
        f"Engineering ticket created: {dna_key}",
    )
    jira.add_comment(
        dna_key,
        f"Originated from service desk ticket: {data_key}",
    )


def close_data_ticket(jira: JiraClient, issue_key: str) -> None:
    """Transition the DATA ticket to Done/Closed."""
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
