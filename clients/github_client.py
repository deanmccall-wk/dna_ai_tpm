"""GitHub REST API client for code search, PR search, file contents, and commit history.

Uses the GitHub REST API (api.github.com) with a personal access token.
Replaces the previous Docker/MCP-based client that required device auth.

Requires GITHUB_PAT in .env.
"""

import base64
import json
import os

import requests


class GitHubClient:
    """Direct REST API client for GitHub — no Docker, no MCP."""

    def __init__(self, github_token: str = None, org: str = None):
        self.token = github_token or os.getenv("GITHUB_PAT", "")
        self.org = org or os.getenv("GITHUB_ORG", "Workiva")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        self.base_url = "https://api.github.com"

    def _get(self, path: str, params: dict = None) -> dict | list:
        resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        """No-op — kept for backward compatibility with lookup_github() finally block."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # -- Tool wrappers (same signatures as the old MCP client) --

    def search_code(self, query: str, per_page: int = 10) -> list[dict]:
        """Search for code across the org's repos.

        Returns list of dicts with: path, repository, url, score
        """
        full_query = f"{query} org:{self.org}"
        data = self._get("/search/code", {"q": full_query, "per_page": per_page})
        return [
            {
                "path": item.get("path", ""),
                "repository": item.get("repository", {}).get("full_name", ""),
                "url": item.get("html_url", ""),
                "score": item.get("score", 0),
            }
            for item in data.get("items", [])
        ]

    def search_prs(self, query: str, repo: str = None, per_page: int = 10) -> list[dict]:
        """Search for pull requests related to a query.

        Returns list of dicts with: title, number, state, url, user, created_at
        """
        full_query = f"{query} type:pr"
        if repo:
            full_query += f" repo:{repo}"
        else:
            full_query += f" org:{self.org}"

        data = self._get("/search/issues", {"q": full_query, "per_page": per_page})
        return [
            {
                "title": item.get("title", ""),
                "number": item.get("number", ""),
                "state": item.get("state", ""),
                "url": item.get("html_url", ""),
                "user": item.get("user", {}).get("login", ""),
                "created_at": item.get("created_at", "")[:10],
            }
            for item in data.get("items", [])
        ]

    def get_file_contents(self, repo: str, path: str) -> str:
        """Read a file from a GitHub repo.

        Args:
            repo: Full repo name (e.g., "Workiva/dbt-project")
            path: File path within the repo
        """
        data = self._get(f"/repos/{repo}/contents/{path}")
        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8")
        # Fallback: if the API returns content directly (e.g., for symlinks)
        return data.get("content", "") if isinstance(data, dict) else ""

    def list_commits(self, repo: str, path: str = None, per_page: int = 10) -> list[dict]:
        """List recent commits for a repo, optionally filtered to a path."""
        params = {"per_page": per_page}
        if path:
            params["path"] = path
        data = self._get(f"/repos/{repo}/commits", params)
        return [
            {
                "sha": item.get("sha", "")[:8],
                "message": item.get("commit", {}).get("message", "").split("\n")[0],
                "author": item.get("commit", {}).get("author", {}).get("name", ""),
                "date": item.get("commit", {}).get("author", {}).get("date", "")[:10],
                "url": item.get("html_url", ""),
            }
            for item in (data if isinstance(data, list) else [])
        ]


# Backward-compatible alias
GitHubMCPClient = GitHubClient
