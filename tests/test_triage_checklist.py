"""Tests for core.triage_checklist."""

import os
import json
import tempfile
import pytest

from core.triage_checklist import check_pre_change, check_pre_post


@pytest.fixture
def snapshot_dir(tmp_path):
    """Create a temp snapshot directory with a fake snapshot."""
    key_dir = tmp_path / "DATA-1234"
    key_dir.mkdir()
    snap = key_dir / "20260901_120000_pre_triage.json"
    snap.write_text(json.dumps({"key": "DATA-1234", "fields": {}}))
    return str(tmp_path)


VALID_COMMENT = """\
h4. Request
Test request.

h4. Conformance & Prioritization
| Conformance | 4/5 (AUTO) |
| Recommended Team | Data Engineering |

*RICE Score: 2.0* (High)

h4. Investigation
Checked tables.

h4. Next Steps
Assigned to team.
"""


class TestPreChange:
    def test_passes_with_snapshot_and_assessment(self, snapshot_dir):
        failures = check_pre_change("DATA-1234", snapshot_dir=snapshot_dir, assessment={"score": 4})
        assert failures == []

    def test_fails_without_snapshot(self, snapshot_dir):
        failures = check_pre_change("DATA-9999", snapshot_dir=snapshot_dir, assessment={"score": 4})
        assert any("snapshot" in f.lower() for f in failures)

    def test_fails_without_assessment(self, snapshot_dir):
        failures = check_pre_change("DATA-1234", snapshot_dir=snapshot_dir, assessment=None)
        assert any("assessment" in f.lower() for f in failures)

    def test_fails_both_missing(self):
        with tempfile.TemporaryDirectory() as d:
            failures = check_pre_change("DATA-9999", snapshot_dir=d, assessment=None)
            assert len(failures) == 2


class TestPrePost:
    def test_passes_with_valid_comment(self, snapshot_dir):
        failures = check_pre_post("DATA-1234", VALID_COMMENT, snapshot_dir=snapshot_dir)
        assert failures == []

    def test_fails_with_general_request_summary(self, snapshot_dir):
        failures = check_pre_post(
            "DATA-1234", VALID_COMMENT,
            snapshot_dir=snapshot_dir,
            current_summary="General Request",
        )
        assert any("General Request" in f for f in failures)

    def test_fails_with_empty_comment(self, snapshot_dir):
        failures = check_pre_post("DATA-1234", "", snapshot_dir=snapshot_dir)
        assert any("empty" in f.lower() for f in failures)

    def test_propagates_comment_validator_warnings(self, snapshot_dir):
        failures = check_pre_post("DATA-1234", "just some text", snapshot_dir=snapshot_dir)
        assert any("h4. Request" in f for f in failures)
