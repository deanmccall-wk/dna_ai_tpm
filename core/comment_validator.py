"""Validate triage comments against the 10-point standard.

Checks that a Jira wiki markup comment contains the required structural
sections and data elements before posting.
"""

import re


# Required h4 sections in every triage comment
REQUIRED_SECTIONS = [
    "h4. Request",
    "h4. Conformance",
    "h4. Investigation",
    "h4. Next Steps",
]

# Regex patterns for data elements
RE_CONFORMANCE_SCORE = re.compile(r"Conformance\s*\|\s*\d/5", re.IGNORECASE)
RE_RICE_SCORE = re.compile(r"RICE\s+Score", re.IGNORECASE)
RE_TEAM_RECOMMENDATION = re.compile(r"Recommended\s+Team", re.IGNORECASE)
RE_ATLAN_LINK = re.compile(r"atlan\.com/assets/", re.IGNORECASE)


def validate_triage_comment(comment: str, assessment: dict = None) -> list[str]:
    """Check a triage comment against the 10-point standard.

    Args:
        comment: Jira wiki markup comment text
        assessment: Optional assessment dict from assess_data_ticket() for
            consistency checks (conformance score, team)

    Returns:
        List of warning strings. Empty list means the comment passes.
    """
    warnings = []

    if not comment or not comment.strip():
        return ["Comment is empty"]

    # Check required h4 sections
    for section in REQUIRED_SECTIONS:
        if section.lower() not in comment.lower():
            warnings.append(f"Missing required section: {section}")

    # Check conformance score table row
    if not RE_CONFORMANCE_SCORE.search(comment):
        warnings.append("Missing conformance score (expected 'Conformance | X/5')")

    # Check RICE score is present inline
    if not RE_RICE_SCORE.search(comment):
        warnings.append("Missing RICE score (expected inline in comment)")

    # Check team recommendation
    if not RE_TEAM_RECOMMENDATION.search(comment):
        warnings.append("Missing team recommendation (expected 'Recommended Team')")

    # Check Atlan links when assets are known
    if assessment and assessment.get("asset_names"):
        if not RE_ATLAN_LINK.search(comment):
            warnings.append(
                "Atlan links expected but not found (assets detected in description)"
            )

    # Consistency checks against assessment data
    if assessment:
        # Verify conformance score matches
        conformance = assessment.get("conformance", {})
        expected_score = conformance.get("score")
        if expected_score is not None:
            score_pattern = re.compile(rf"Conformance\s*\|\s*{expected_score}/5")
            if RE_CONFORMANCE_SCORE.search(comment) and not score_pattern.search(comment):
                warnings.append(
                    f"Conformance score mismatch: assessment says {expected_score}/5"
                )

        # Verify team matches
        expected_team = assessment.get("team", {}).get("team", "")
        if expected_team and expected_team.lower() not in comment.lower():
            warnings.append(
                f"Team mismatch: assessment recommends '{expected_team}' "
                f"but not found in comment"
            )

    return warnings
