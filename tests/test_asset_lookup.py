"""Tests for asset extraction patterns in core.asset_lookup."""

from core.asset_lookup import extract_asset_names


def test_snowflake_fqn():
    text = "Check GOLD_PROD.MARTS.DIM_WORKERS for employee data"
    names = extract_asset_names(text)
    assert "GOLD_PROD.MARTS.DIM_WORKERS" in names


def test_dbt_model_ref():
    text = "This uses {{ ref('stg_salesforce_account') }} in the model"
    names = extract_asset_names(text)
    assert "stg_salesforce_account" in names


def test_table_name_pattern():
    text = "The dim_workers table has the data"
    names = extract_asset_names(text)
    assert "dim_workers" in names


def test_quicksight_dashboard_url():
    text = "See https://us-east-1.quicksight.aws.amazon.com/sn/dashboards/abc-123-def"
    names = extract_asset_names(text)
    assert "qs-dashboard:abc-123-def" in names


def test_quicksight_dataset_url():
    text = "Dataset at https://us-east-1.quicksight.aws.amazon.com/sn/start/data-sets/xyz-789"
    names = extract_asset_names(text)
    assert "qs-dataset:xyz-789" in names


def test_no_assets():
    text = "Please help me with my report"
    names = extract_asset_names(text)
    assert names == []


def test_multiple_assets():
    text = (
        "Check SILVER_PROD.SALESFORCE.LEAD and also the dim_workers table. "
        "Dashboard: https://us-east-1.quicksight.aws.amazon.com/sn/dashboards/dash-1"
    )
    names = extract_asset_names(text)
    assert len(names) >= 3
    assert "SILVER_PROD.SALESFORCE.LEAD" in names
    assert "dim_workers" in names
    assert "qs-dashboard:dash-1" in names
