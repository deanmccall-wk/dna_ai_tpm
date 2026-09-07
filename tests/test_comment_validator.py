"""Tests for core.comment_validator."""

import pytest

from core.comment_validator import validate_triage_comment


VALID_COMMENT = """\
*Triage Assessment -- DATA-9999*

h4. Request
User needs access to the FPA schema in Snowflake.

h4. Conformance & Prioritization
|| Metric || Value ||
| Conformance | 3/5 (ENRICH) |
| SLA Tier | 2 -- Reviewed in 2-3 business days |
| Jira Priority | Medium |
| Recommended Team | Data Operations |

*RICE Score: 1.5* (Medium)
||Factor||Score||Detail||
|Reach|2|My team|
|Impact|1.5|1.0 (type) x 1.5 (urgency)|
|Confidence|60%|3/5 signals|
|Effort|2|Estimated|

h4. Investigation
Checked GOLD_PROD.FPA tables. User has ANALYST role.
[View in Atlan|https://workiva.atlan.com/assets/abc-123/overview]

h4. Self-Service Path
Request ANALYST role via the DnA Knowledge Hub.

h4. Next Steps
Hi [~reporter],
Please confirm you need write access or read-only.
"""


def test_valid_comment_passes():
    warnings = validate_triage_comment(VALID_COMMENT)
    assert warnings == []


def test_empty_comment():
    warnings = validate_triage_comment("")
    assert warnings == ["Comment is empty"]


def test_missing_request_section():
    comment = VALID_COMMENT.replace("h4. Request", "h4. Summary")
    warnings = validate_triage_comment(comment)
    assert any("h4. Request" in w for w in warnings)


def test_missing_investigation_section():
    comment = VALID_COMMENT.replace("h4. Investigation", "h4. Findings")
    warnings = validate_triage_comment(comment)
    assert any("h4. Investigation" in w for w in warnings)


def test_missing_next_steps_section():
    comment = VALID_COMMENT.replace("h4. Next Steps", "h4. Actions")
    warnings = validate_triage_comment(comment)
    assert any("h4. Next Steps" in w for w in warnings)


def test_missing_conformance_score():
    comment = VALID_COMMENT.replace("Conformance | 3/5", "Conformance | TBD")
    warnings = validate_triage_comment(comment)
    assert any("conformance score" in w.lower() for w in warnings)


def test_missing_rice_score():
    comment = VALID_COMMENT.replace("RICE Score: 1.5", "Priority Score: 1.5")
    warnings = validate_triage_comment(comment)
    assert any("RICE" in w for w in warnings)


def test_missing_team_recommendation():
    comment = VALID_COMMENT.replace("Recommended Team", "Assigned Group")
    warnings = validate_triage_comment(comment)
    assert any("team recommendation" in w.lower() for w in warnings)


def test_atlan_links_expected_but_missing():
    comment = VALID_COMMENT.replace("atlan.com/assets/abc-123/overview", "snowflake.com")
    assessment = {"asset_names": ["dim_workers"]}
    warnings = validate_triage_comment(comment, assessment=assessment)
    assert any("Atlan" in w for w in warnings)


def test_atlan_links_not_required_without_assets():
    comment = VALID_COMMENT.replace("atlan.com/assets/abc-123/overview", "snowflake.com")
    warnings = validate_triage_comment(comment, assessment={})
    assert not any("Atlan" in w for w in warnings)


def test_conformance_score_mismatch():
    assessment = {"conformance": {"score": 5}}
    warnings = validate_triage_comment(VALID_COMMENT, assessment=assessment)
    assert any("mismatch" in w.lower() for w in warnings)


def test_conformance_score_matches():
    assessment = {"conformance": {"score": 3}}
    warnings = validate_triage_comment(VALID_COMMENT, assessment=assessment)
    assert not any("mismatch" in w.lower() for w in warnings)
