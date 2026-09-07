import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)


class JiraClient:
    def __init__(self, base_url: str, pat: str, dry_run: bool = False,
                 snapshot_dir: str = "snapshots"):
        self.base_url = base_url
        self.dry_run = dry_run
        self._snapshot_dir = Path(snapshot_dir)
        self._snapshot_checked: set[str] = set()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # -- Write guards --

    def _require_snapshot(self, key: str) -> None:
        """Raise if no snapshot exists for this ticket key."""
        if key in self._snapshot_checked:
            return
        snap_dir = self._snapshot_dir / key
        if not snap_dir.exists() or not any(snap_dir.iterdir()):
            raise RuntimeError(
                f"No snapshot found for {key}. "
                f"Run snapshot before modifying: "
                f"PYTHONPATH=$PWD python safety/snapshot.py --keys {key} --label pre_triage"
            )
        self._snapshot_checked.add(key)

    def bypass_snapshot(self, key: str) -> None:
        """Mark a key as snapshot-exempt (e.g. just-created tickets)."""
        self._snapshot_checked.add(key)

    def _url(self, path: str) -> str:
        return f"{self.base_url}/rest/api/2{path}"

    def _get(self, path: str, params: dict = None) -> dict:
        resp = self.session.get(self._url(path), params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json: dict = None) -> dict:
        resp = self.session.post(self._url(path), json=json)
        resp.raise_for_status()
        return resp.json()

    # -- Auth check --

    def myself(self) -> dict:
        return self._get("/myself")

    # -- Issues --

    def get_issue(self, key: str, fields: list[str] = None) -> dict:
        params = {}
        if fields:
            params["fields"] = ",".join(fields)
        return self._get(f"/issue/{key}", params=params)

    def create_issue(self, payload: dict) -> dict:
        if self.dry_run:
            log.info("[DRY RUN] create_issue: %s", payload.get("fields", {}).get("summary", ""))
            return {"key": "DRYRUN-0", "id": "0"}
        result = self._post("/issue", json=payload)
        if "key" in result:
            self.bypass_snapshot(result["key"])
        return result

    def update_issue(self, key: str, fields: dict) -> None:
        """Update fields on an existing issue via PUT."""
        self._require_snapshot(key)
        if self.dry_run:
            log.info("[DRY RUN] update_issue %s: %s", key, list(fields.keys()))
            return
        resp = self.session.put(
            self._url(f"/issue/{key}"),
            json={"fields": fields},
        )
        resp.raise_for_status()

    def move_issue(self, key: str, target_project: str, issue_type: str = None) -> None:
        """Move an issue to another project. Optionally change issue type."""
        fields = {"project": {"key": target_project}}
        if issue_type:
            fields["issuetype"] = {"name": issue_type}
        self.update_issue(key, fields)

    def get_issue_full(self, key: str) -> dict:
        """Get all fields for a ticket (no field filter). Used for snapshots."""
        return self._get(f"/issue/{key}")

    def get_issue_changelog(self, key: str) -> dict:
        """Get issue with changelog expanded."""
        return self._get(f"/issue/{key}", params={"expand": "changelog"})

    # -- Comments --

    def add_comment(self, key: str, body: str) -> dict:
        self._require_snapshot(key)
        if self.dry_run:
            log.info("[DRY RUN] add_comment %s: %s...", key, body[:80])
            return {}
        return self._post(f"/issue/{key}/comment", json={"body": body})

    # -- Transitions --

    def get_transitions(self, key: str) -> list[dict]:
        return self._get(f"/issue/{key}/transitions")["transitions"]

    def transition_issue(self, key: str, transition_id: str) -> None:
        self._require_snapshot(key)
        if self.dry_run:
            log.info("[DRY RUN] transition_issue %s: transition=%s", key, transition_id)
            return
        resp = self.session.post(
            self._url(f"/issue/{key}/transitions"),
            json={"transition": {"id": transition_id}},
        )
        resp.raise_for_status()

    # -- Search --

    def search(self, jql: str, fields: list[str] = None, max_results: int = 50, start_at: int = 0) -> dict:
        payload = {"jql": jql, "maxResults": max_results, "startAt": start_at}
        if fields:
            payload["fields"] = fields
        return self._post("/search", json=payload)

    def search_all(self, jql: str, fields: list[str] = None, page_size: int = 200) -> list[dict]:
        """Paginate through all results for a JQL query."""
        all_issues = []
        start_at = 0
        while True:
            result = self.search(jql, fields=fields, max_results=page_size, start_at=start_at)
            all_issues.extend(result["issues"])
            start_at += len(result["issues"])
            if start_at >= result["total"]:
                break
        return all_issues

    # -- Create metadata --

    def get_create_meta(self, project_key: str) -> dict:
        """Fetch create metadata. Tries the new endpoint first (Jira DC 8.4+), falls back to legacy."""
        try:
            return self._get(f"/issue/createmeta/{project_key}/issuetypes")
        except requests.HTTPError:
            return self._get("/issue/createmeta", params={
                "projectKeys": project_key,
                "expand": "projects.issuetypes.fields",
            })

    def get_create_meta_fields(self, project_key: str, issuetype_id: str) -> dict:
        """Fetch fields for a specific issue type (Jira DC 8.4+ endpoint)."""
        return self._get(f"/issue/createmeta/{project_key}/issuetypes/{issuetype_id}")
