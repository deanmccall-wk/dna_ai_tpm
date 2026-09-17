"""Tests for clients.github_client.GitHubClient (REST API)."""

import base64
import json
import pytest
from unittest.mock import MagicMock, patch

from clients.github_client import GitHubClient


@pytest.fixture
def client():
    with patch.dict("os.environ", {"GITHUB_PAT": "test-token", "GITHUB_ORG": "TestOrg"}):
        return GitHubClient()


def _mock_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


def test_search_code(client):
    mock_data = {
        "total_count": 2,
        "items": [
            {
                "path": "terraform/workato.tf",
                "repository": {"full_name": "TestOrg/infra"},
                "html_url": "https://github.com/TestOrg/infra/blob/main/terraform/workato.tf",
                "score": 1.0,
            },
            {
                "path": "roles/workato.sql",
                "repository": {"full_name": "TestOrg/sql-scripts"},
                "html_url": "https://github.com/TestOrg/sql-scripts/blob/main/roles/workato.sql",
                "score": 0.8,
            },
        ],
    }
    client.session.get = MagicMock(return_value=_mock_response(mock_data))

    results = client.search_code("SERVICE_WORKATO_PROD", per_page=5)

    assert len(results) == 2
    assert results[0]["path"] == "terraform/workato.tf"
    assert results[0]["repository"] == "TestOrg/infra"
    assert "html_url" not in results[0]  # normalized to 'url'
    assert results[0]["url"] == "https://github.com/TestOrg/infra/blob/main/terraform/workato.tf"

    call_args = client.session.get.call_args
    assert "/search/code" in call_args[0][0]
    assert "org:TestOrg" in call_args[1]["params"]["q"]


def test_search_code_empty(client):
    client.session.get = MagicMock(return_value=_mock_response({"total_count": 0, "items": []}))
    results = client.search_code("nonexistent_thing")
    assert results == []


def test_search_prs(client):
    mock_data = {
        "total_count": 1,
        "items": [
            {
                "title": "Add Workato role grant",
                "number": 42,
                "state": "closed",
                "html_url": "https://github.com/TestOrg/infra/pull/42",
                "user": {"login": "jdodson"},
                "created_at": "2026-06-15T10:00:00Z",
            },
        ],
    }
    client.session.get = MagicMock(return_value=_mock_response(mock_data))

    results = client.search_prs("workato")

    assert len(results) == 1
    assert results[0]["title"] == "Add Workato role grant"
    assert results[0]["number"] == 42
    assert results[0]["state"] == "closed"
    assert results[0]["user"] == "jdodson"
    assert results[0]["created_at"] == "2026-06-15"

    call_args = client.session.get.call_args
    assert "type:pr" in call_args[1]["params"]["q"]
    assert "org:TestOrg" in call_args[1]["params"]["q"]


def test_search_prs_specific_repo(client):
    client.session.get = MagicMock(return_value=_mock_response({"total_count": 0, "items": []}))

    client.search_prs("workato", repo="TestOrg/infra")

    call_args = client.session.get.call_args
    q = call_args[1]["params"]["q"]
    assert "repo:TestOrg/infra" in q
    assert "org:" not in q


def test_get_file_contents(client):
    content_text = 'resource "snowflake_grant_account_role" "workato" {\n  role_name = "APP_GOLD_MARTS_R_PROD"\n}'
    encoded = base64.b64encode(content_text.encode()).decode()
    mock_data = {
        "content": encoded,
        "encoding": "base64",
        "name": "workato.tf",
    }
    client.session.get = MagicMock(return_value=_mock_response(mock_data))

    result = client.get_file_contents("TestOrg/infra", "terraform/workato.tf")

    assert result == content_text
    call_args = client.session.get.call_args
    assert "/repos/TestOrg/infra/contents/terraform/workato.tf" in call_args[0][0]


def test_list_commits(client):
    mock_data = [
        {
            "sha": "abc123def456",
            "commit": {
                "message": "Add Workato role grant\n\nGranting APP_GOLD_MARTS_R_PROD",
                "author": {"name": "Joseph Dodson", "date": "2026-06-25T14:00:00Z"},
            },
            "html_url": "https://github.com/TestOrg/infra/commit/abc123def456",
        },
    ]
    client.session.get = MagicMock(return_value=_mock_response(mock_data))

    results = client.list_commits("TestOrg/infra", path="terraform/workato.tf")

    assert len(results) == 1
    assert results[0]["sha"] == "abc123de"
    assert results[0]["message"] == "Add Workato role grant"
    assert results[0]["author"] == "Joseph Dodson"
    assert results[0]["date"] == "2026-06-25"


def test_list_commits_no_path(client):
    client.session.get = MagicMock(return_value=_mock_response([]))
    client.list_commits("TestOrg/infra")
    call_args = client.session.get.call_args
    assert "path" not in call_args[1]["params"]


def test_close_is_noop(client):
    client.close()  # should not raise


def test_context_manager(client):
    with client as gh:
        assert gh is client
