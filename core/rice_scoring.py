"""RICE prioritization scoring derived from DATA intake form fields.

RICE = (Reach x Impact x Confidence) / Effort

- Reach: How many people/teams are affected
- Impact: How significant is the business outcome
- Confidence: How well-defined is the request
- Effort: Estimated work required
"""

from core.tpm_workflow import (
    CF_SERVICE_TYPE, CF_TEAMS_IMPACTED, CF_BIZ_PRIORITY,
    CF_PRIMARY_SOLUTION, CF_EXEC_SPONSOR, CF_MILESTONE,
    SERVICE_TYPES, _get_field_value,
)

# -- Reach: from Teams Impacted (cf[29221]) --

REACH_SCORES = {
    "Entire company / Critical operations": 10,
    "Multiple teams / Cross-functional reporting (If selected, please name the impacted teams)": 5,
    "My specific team / Sub-department (If selected, please name your team)": 2,
    "Just me / Individual request": 1,
}

# -- Impact: from Service Type x Business Priority --

SERVICE_TYPE_IMPACT = {
    SERVICE_TYPES["build_new"]: 2.0,
    SERVICE_TYPES["change_existing"]: 1.5,
    SERVICE_TYPES["business_question"]: 1.0,
    SERVICE_TYPES["troubleshooting"]: 2.0,
    SERVICE_TYPES["access"]: 0.5,
    SERVICE_TYPES["ml_ai"]: 2.5,
    SERVICE_TYPES["other"]: 1.0,
}

BIZ_PRIORITY_IMPACT_MULTIPLIER = {
    "System Outage / Production Blocker": 1.5,
    "Fixed Deadline / Upcoming Milestone": 1.25,
    "Standard Business Operation": 1.0,
    "Nice-to-have / Backlog": 0.75,
}

# -- Effort: default estimates by service type (in Fibonacci story points) --

SERVICE_TYPE_DEFAULT_EFFORT = {
    SERVICE_TYPES["build_new"]: 5,
    SERVICE_TYPES["change_existing"]: 3,
    SERVICE_TYPES["business_question"]: 2,
    SERVICE_TYPES["troubleshooting"]: 3,
    SERVICE_TYPES["access"]: 1,
    SERVICE_TYPES["ml_ai"]: 8,
    SERVICE_TYPES["other"]: 3,
}


def calculate_rice(fields: dict, effort_override: int = None,
                   reach_override: int = None) -> dict:
    """Calculate RICE score from DATA ticket form fields.

    Returns dict with each component score, the final RICE score, and a summary.
    """
    # Reach
    teams_impacted = _get_field_value(fields, CF_TEAMS_IMPACTED)
    if isinstance(teams_impacted, list) and teams_impacted:
        reach = max(REACH_SCORES.get(t, 1) for t in teams_impacted)
        reach_label = teams_impacted[0] if len(teams_impacted) == 1 else f"{len(teams_impacted)} selections"
    elif isinstance(teams_impacted, str):
        reach = REACH_SCORES.get(teams_impacted, 1)
        reach_label = teams_impacted
    else:
        reach = 1
        reach_label = "Unknown (defaulted to 1)"

    # Reach boost: platform-level enablement requests affect all users of that tool,
    # not just the requester. Detect and adjust.
    description = (fields.get("description") or "").lower()
    summary = (fields.get("summary") or "").lower()
    text = summary + " " + description
    platform_keywords = ["enable", "turn on", "activate", "flip the switch",
                         "feature flag", "account-level", "org-level", "all users",
                         "account setting"]
    if reach <= 2 and any(kw in text for kw in platform_keywords):
        service_type_val = _get_field_value(fields, CF_SERVICE_TYPE) or ""
        if "access" in service_type_val.lower() or "system" in service_type_val.lower():
            matched = [kw for kw in platform_keywords if kw in text]
            reach = 10
            reach_label = f"Platform enablement (boosted from {REACH_SCORES.get(teams_impacted[0] if isinstance(teams_impacted, list) and teams_impacted else '', 1)}): {', '.join(matched[:2])}"

    # Manual override (from plan file edits)
    if reach_override is not None:
        reach = reach_override
        reach_label = f"Manual override ({reach_override})"

    # Impact
    service_type = _get_field_value(fields, CF_SERVICE_TYPE) or ""
    biz_priority = _get_field_value(fields, CF_BIZ_PRIORITY) or ""

    base_impact = SERVICE_TYPE_IMPACT.get(service_type, 1.0)
    priority_mult = BIZ_PRIORITY_IMPACT_MULTIPLIER.get(biz_priority, 1.0)
    impact = round(base_impact * priority_mult, 2)
    impact_label = f"{base_impact} (type) x {priority_mult} (urgency)"

    # Confidence
    confidence_factors = []
    has_description = bool(fields.get("description") and len(fields["description"]) > 50)
    has_sponsor = bool(fields.get(CF_EXEC_SPONSOR))
    has_service_type = bool(service_type)
    has_solution = bool(fields.get(CF_PRIMARY_SOLUTION))
    has_milestone = bool(fields.get(CF_MILESTONE))

    if has_description:
        confidence_factors.append(("Description provided", 0.20))
    if has_sponsor:
        confidence_factors.append(("Executive sponsor named", 0.20))
    if has_service_type:
        confidence_factors.append(("Service type selected", 0.20))
    if has_solution:
        confidence_factors.append(("Data domain identified", 0.20))
    if has_milestone:
        confidence_factors.append(("Milestone/deadline specified", 0.20))

    confidence_pct = max(sum(s for _, s in confidence_factors), 0.50)  # floor at 50%
    confidence_label = f"{int(confidence_pct * 100)}% ({len(confidence_factors)}/5 signals)"

    # Effort
    if effort_override:
        effort = effort_override
        effort_label = f"{effort} (manually set)"
    else:
        effort = SERVICE_TYPE_DEFAULT_EFFORT.get(service_type, 3)
        effort_label = f"{effort} (estimated from service type)"

    # RICE Score
    rice_score = round((reach * impact * confidence_pct) / effort, 2)

    # Priority bucket
    if rice_score >= 5:
        priority_bucket = "Blocker"
    elif rice_score >= 2:
        priority_bucket = "High"
    elif rice_score >= 1:
        priority_bucket = "Medium"
    else:
        priority_bucket = "Low"

    return {
        "reach": reach,
        "reach_label": reach_label,
        "impact": impact,
        "impact_label": impact_label,
        "confidence": confidence_pct,
        "confidence_label": confidence_label,
        "effort": effort,
        "effort_label": effort_label,
        "rice_score": rice_score,
        "priority_bucket": priority_bucket,
    }


def format_rice_comment(rice: dict) -> str:
    """Format RICE score as a standalone Jira comment (legacy)."""
    return format_rice_inline(rice)


def format_rice_inline(rice: dict) -> str:
    """Format RICE score as an embeddable Jira wiki table fragment."""
    return (
        f"*RICE Score: {rice['rice_score']}* ({rice['priority_bucket']})\n"
        f"||Factor||Score||Detail||\n"
        f"|Reach|{rice['reach']}|{rice['reach_label']}|\n"
        f"|Impact|{rice['impact']}|{rice['impact_label']}|\n"
        f"|Confidence|{int(rice['confidence'] * 100)}%|{rice['confidence_label']}|\n"
        f"|Effort|{rice['effort']}|{rice['effort_label']}|\n"
        f"\n_RICE = (Reach x Impact x Confidence) / Effort_"
    )
