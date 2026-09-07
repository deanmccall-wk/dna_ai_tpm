"""Programmatic enforcement of the three mandatory triage checklists.

Each function returns a list of failure strings. An empty list means
all checks pass.

Checklists:
  - pre_change: before any Jira modification
  - pre_post: before posting a triage comment
  - post_action: after routing/closing a ticket
"""

from pathlib import Path

from core.comment_validator import validate_triage_comment


def check_pre_change(
    key: str,
    snapshot_dir: str = "snapshots",
    assessment: dict = None,
) -> list[str]:
    """Verify pre-change checklist items.

    Checks:
      - Snapshot exists for the ticket
      - Assessment has been run
    """
    failures = []

    snap_path = Path(snapshot_dir) / key
    if not snap_path.exists() or not any(snap_path.iterdir()):
        failures.append(f"No snapshot found for {key}")

    if assessment is None:
        failures.append("Assessment has not been run (_assess.py)")

    return failures


def check_pre_post(
    key: str,
    comment: str,
    assessment: dict = None,
    snapshot_dir: str = "snapshots",
    current_summary: str = "",
) -> list[str]:
    """Verify pre-post checklist items.

    Checks:
      - Snapshot exists
      - Comment passes 10-point validation
      - Summary is not 'General Request'
    """
    failures = []

    snap_path = Path(snapshot_dir) / key
    if not snap_path.exists() or not any(snap_path.iterdir()):
        failures.append(f"No snapshot found for {key}")

    comment_warnings = validate_triage_comment(comment, assessment=assessment)
    failures.extend(comment_warnings)

    if current_summary and current_summary.strip().lower() == "general request":
        failures.append("Summary is still 'General Request' -- update before posting")

    return failures


def check_post_action(
    key: str,
    jira=None,
    expected_status: str = None,
) -> list[str]:
    """Verify post-action checklist items.

    Checks:
      - Ticket status matches expected (if provided)
      - If DNA handoff: DNA ticket has required fields
    """
    failures = []

    if jira and expected_status:
        try:
            issue = jira.get_issue(key, fields=["status"])
            actual = issue["fields"]["status"]["name"]
            if actual.lower() != expected_status.lower():
                failures.append(
                    f"Status mismatch on {key}: expected '{expected_status}', "
                    f"got '{actual}'"
                )
        except Exception as e:
            failures.append(f"Could not verify status for {key}: {e}")

    if jira and key.startswith("DNA-"):
        try:
            from core.tpm_workflow import check_dna_compliance
            issue = jira.get_issue(key)
            compliance = check_dna_compliance(issue)
            violations = compliance.get("violations", [])
            if violations:
                failures.append(
                    f"DNA compliance issues on {key}: {', '.join(violations)}"
                )
        except Exception as e:
            failures.append(f"Could not check DNA compliance for {key}: {e}")

    return failures
