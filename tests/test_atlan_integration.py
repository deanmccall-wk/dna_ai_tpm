"""Tests for end-to-end Atlan link flow through triage pipeline."""

import json
import pytest
from unittest.mock import MagicMock, patch

from core.tpm_workflow import build_triage_comment, assess_data_ticket
from core.asset_lookup import format_asset_jira_comment
from core.comment_validator import validate_triage_comment
from core.triage_checklist import check_pre_post


# -- Fixtures ----------------------------------------------------------------

SAMPLE_ASSET_CONTEXT = {
    "asset_names": ["GOLD_PROD.MARTS.OBT_PIPELINE", "SILVER_PROD.SALESFORCE.ACCOUNT"],
    "atlan": {
        "GOLD_PROD.MARTS.OBT_PIPELINE": [
            {
                "name": "OBT_PIPELINE",
                "qualified_name": "default/snowflake/1/GOLD_PROD/MARTS/OBT_PIPELINE",
                "type": "Table",
                "guid": "abc-123-def",
                "owners": ["data.eng@workiva.com"],
                "url": "https://workiva.atlan.com/assets/abc-123-def/overview",
            }
        ],
        "SILVER_PROD.SALESFORCE.ACCOUNT": [
            {
                "name": "ACCOUNT",
                "qualified_name": "default/snowflake/1/SILVER_PROD/SALESFORCE/ACCOUNT",
                "type": "Table",
                "guid": "xyz-456-ghi",
                "owners": ["salesforce.admin@workiva.com"],
                "url": "https://workiva.atlan.com/assets/xyz-456-ghi/overview",
            }
        ],
    },
    "github": {},
}

SAMPLE_RICE = {
    "rice_score": 3.0,
    "priority_bucket": "Medium",
    "reach": 2,
    "reach_label": "My team",
    "impact": 1.5,
    "impact_label": "1.0 (type) x 1.5 (urgency)",
    "confidence": 0.6,
    "confidence_label": "3/5 signals",
    "effort": 2,
    "effort_label": "Estimated",
}


# -- build_triage_comment tests ----------------------------------------------

def test_build_triage_comment_includes_atlan_section():
    comment = build_triage_comment("High", rice=SAMPLE_RICE,
                                   asset_context=SAMPLE_ASSET_CONTEXT)
    assert "atlan.com/assets/" in comment
    assert "OBT_PIPELINE" in comment
    assert "ACCOUNT" in comment


def test_build_triage_comment_without_assets():
    comment = build_triage_comment("Medium", rice=SAMPLE_RICE, asset_context={})
    assert "atlan.com" not in comment


def test_build_triage_comment_with_empty_asset_names():
    ctx = {"asset_names": [], "atlan": {}, "github": {}}
    comment = build_triage_comment("Medium", rice=SAMPLE_RICE, asset_context=ctx)
    assert "atlan.com" not in comment


def test_build_triage_comment_with_none_asset_context():
    comment = build_triage_comment("Medium", rice=SAMPLE_RICE, asset_context=None)
    assert "atlan.com" not in comment


# -- format_asset_jira_comment tests -----------------------------------------

def test_format_asset_jira_comment_structure():
    output = format_asset_jira_comment(SAMPLE_ASSET_CONTEXT)
    assert "h4. Asset Context" in output
    assert "||Asset||Type||Owners||Link||" in output
    assert "[View in Atlan|https://workiva.atlan.com/assets/abc-123-def/overview]" in output
    assert "[View in Atlan|https://workiva.atlan.com/assets/xyz-456-ghi/overview]" in output


def test_format_asset_jira_comment_empty():
    output = format_asset_jira_comment({"asset_names": [], "atlan": {}})
    assert "No asset references found" in output


def test_format_asset_jira_comment_skips_errors():
    ctx = {
        "asset_names": ["dim_workers"],
        "atlan": {"dim_workers": [{"error": "connection timeout"}]},
    }
    output = format_asset_jira_comment(ctx)
    assert "View in Atlan" not in output


# -- assess_data_ticket returns asset_names ----------------------------------

def test_assess_data_ticket_includes_asset_names():
    fields = {
        "summary": "Grant access to GOLD_PROD.MARTS.OBT_PIPELINE",
        "description": "Need SELECT on SILVER_PROD.SALESFORCE.ACCOUNT too",
        "issuetype": {"name": "Service Request"},
        "priority": {"name": "Medium"},
    }
    assessment = assess_data_ticket(fields, "DATA-9999")
    assert "asset_names" in assessment
    assert "GOLD_PROD.MARTS.OBT_PIPELINE" in assessment["asset_names"]
    assert "SILVER_PROD.SALESFORCE.ACCOUNT" in assessment["asset_names"]


def test_assess_data_ticket_empty_description():
    fields = {
        "summary": "General Request",
        "description": "",
        "issuetype": {"name": "Service Request"},
    }
    assessment = assess_data_ticket(fields, "DATA-0000")
    assert "asset_names" in assessment
    assert assessment["asset_names"] == []


# -- comment_validator Atlan link edge cases ---------------------------------

def test_validator_no_warning_with_empty_asset_names_list():
    comment = "h4. Request\nSome comment without Atlan links"
    warnings = validate_triage_comment(comment, assessment={"asset_names": []})
    assert not any("Atlan" in w for w in warnings)


def test_validator_no_warning_with_none_assessment():
    comment = "h4. Request\nSome comment without Atlan links"
    warnings = validate_triage_comment(comment, assessment=None)
    assert not any("Atlan" in w for w in warnings)


def test_validator_warns_when_assets_but_no_link():
    comment = "h4. Request\nNeed access to OBT_PIPELINE"
    warnings = validate_triage_comment(
        comment, assessment={"asset_names": ["GOLD_PROD.MARTS.OBT_PIPELINE"]},
    )
    assert any("Atlan" in w for w in warnings)


def test_validator_passes_when_assets_and_link_present():
    comment = (
        "h4. Request\nNeed access to OBT_PIPELINE\n"
        "[View in Atlan|https://workiva.atlan.com/assets/abc-123/overview]"
    )
    warnings = validate_triage_comment(
        comment, assessment={"asset_names": ["GOLD_PROD.MARTS.OBT_PIPELINE"]},
    )
    assert not any("Atlan" in w for w in warnings)


# -- check_pre_post integration tests ----------------------------------------

def test_check_pre_post_blocks_missing_atlan_links(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    key_dir = snapshot_dir / "DATA-9999"
    key_dir.mkdir(parents=True)
    (key_dir / "issue.json").write_text("{}")

    comment = (
        "h4. Request\nAccess to OBT_PIPELINE\n"
        "h4. Conformance & Prioritization\n"
        "|| Metric || Value ||\n| Conformance | 4/5 |\n"
        "| Recommended Team | Data Operations |\n"
        "*RICE Score: 3.0* (Medium)\n"
        "h4. Investigation\nChecked tables.\n"
        "h4. Next Steps\nGrant access."
    )
    assessment = {"asset_names": ["GOLD_PROD.MARTS.OBT_PIPELINE"]}

    failures = check_pre_post(
        "DATA-9999", comment,
        assessment=assessment,
        snapshot_dir=str(snapshot_dir),
        current_summary="Grant access to OBT_PIPELINE",
    )
    assert any("Atlan" in f for f in failures)


def test_check_pre_post_passes_with_atlan_links(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    key_dir = snapshot_dir / "DATA-9999"
    key_dir.mkdir(parents=True)
    (key_dir / "issue.json").write_text("{}")

    comment = (
        "h4. Request\nAccess to OBT_PIPELINE\n"
        "h4. Conformance & Prioritization\n"
        "|| Metric || Value ||\n| Conformance | 4/5 |\n"
        "| Recommended Team | Data Operations |\n"
        "*RICE Score: 3.0* (Medium)\n"
        "h4. Investigation\nChecked tables.\n"
        "[View in Atlan|https://workiva.atlan.com/assets/abc-123/overview]\n"
        "h4. Next Steps\nGrant access."
    )
    assessment = {"asset_names": ["GOLD_PROD.MARTS.OBT_PIPELINE"]}

    failures = check_pre_post(
        "DATA-9999", comment,
        assessment=assessment,
        snapshot_dir=str(snapshot_dir),
        current_summary="Grant access to OBT_PIPELINE",
    )
    assert not any("Atlan" in f for f in failures)


# -- plan_entry stores asset_context -----------------------------------------

@patch("triage.triage_data.lookup_assets_for_ticket")
@patch("triage.triage_data.calculate_rice")
@patch("triage.triage_data.propose_summary", return_value=None)
@patch("builtins.input", return_value="sla")
def test_plan_auto_stores_asset_context(mock_input, mock_propose, mock_rice, mock_lookup):
    from triage.triage_data import plan_auto_ticket

    mock_rice.return_value = SAMPLE_RICE
    mock_lookup.return_value = SAMPLE_ASSET_CONTEXT

    jira = MagicMock()
    jira.get_issue.return_value = {
        "fields": {
            "summary": "Access to OBT_PIPELINE",
            "description": "Grant SELECT on GOLD_PROD.MARTS.OBT_PIPELINE",
        }
    }

    ticket = {
        "key": "DATA-9999",
        "summary": "Access to OBT_PIPELINE",
        "service_type": "access",
        "biz_priority": "Medium",
        "jira_priority": "Medium",
        "tier": 1,
    }

    entry = plan_auto_ticket(jira, ticket)
    assert "asset_context" in entry
    assert entry["asset_context"]["asset_names"] == SAMPLE_ASSET_CONTEXT["asset_names"]
