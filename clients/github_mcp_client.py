"""GitHub MCP server client — communicates with the GitHub MCP server in Docker.

Uses the Model Context Protocol (MCP) over stdio transport to call GitHub tools:
search_code, search_repositories, list_commits, get_file_contents.

Requires GITHUB_PAT in .env. Docker must be available.
"""

import json
import os
import subprocess
import sys


class GitHubMCPClient:
    """Client that spawns the GitHub MCP server as a Docker subprocess
    and communicates via JSON-RPC over stdin/stdout."""

    def __init__(self, github_token: str = None, org: str = None,
                 docker_image: str = "ghcr.io/github/github-mcp-server"):
        self.github_token = github_token or os.getenv("GITHUB_PAT", "")
        self.org = org or os.getenv("GITHUB_ORG", "Workiva")
        self.docker_image = docker_image
        self._proc = None
        self._request_id = 0

    def _ensure_running(self):
        if self._proc is not None and self._proc.poll() is None:
            return
        self._proc = subprocess.Popen(
            [
                "docker", "run", "--rm", "-i",
                "-e", f"GITHUB_PERSONAL_ACCESS_TOKEN={self.github_token}",
                self.docker_image,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait for initialization by sending initialize request
        self._call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "dna_ai_tpm", "version": "1.0"},
        })

    def _call(self, method: str, params: dict = None, timeout: int = 30) -> dict:
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        line = json.dumps(request) + "\n"
        self._proc.stdin.write(line.encode())
        self._proc.stdin.flush()

        # Read response (one JSON line)
        raw = self._proc.stdout.readline()
        if not raw:
            stderr = self._proc.stderr.read().decode() if self._proc.stderr else ""
            raise RuntimeError(f"MCP server returned no response. stderr: {stderr}")
        return json.loads(raw)

    def _tool_call(self, tool_name: str, arguments: dict) -> dict:
        self._ensure_running()
        resp = self._call("tools/call", {"name": tool_name, "arguments": arguments})
        if "error" in resp:
            raise RuntimeError(f"MCP tool error: {resp['error']}")
        return resp.get("result", {})

    def close(self):
        if self._proc and self._proc.poll() is None:
            self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=5)
            self._proc = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # -- Tool wrappers --

    def search_code(self, query: str, per_page: int = 10) -> list[dict]:
        """Search for code across the org's repos.

        Args:
            query: Search term (e.g., a model name, table name)
            per_page: Max results

        Returns list of dicts with: path, repository, url, text_matches
        """
        full_query = f"{query} org:{self.org}"
        result = self._tool_call("search_code", {"q": full_query, "per_page": per_page})
        items = []
        for content in result.get("content", []):
            if content.get("type") == "text":
                try:
                    data = json.loads(content["text"])
                    for item in data.get("items", [data] if "path" in data else []):
                        items.append({
                            "path": item.get("path", ""),
                            "repository": item.get("repository", {}).get("full_name", ""),
                            "url": item.get("html_url", ""),
                            "score": item.get("score", 0),
                        })
                except (json.JSONDecodeError, TypeError):
                    pass
        return items

    def search_prs(self, query: str, repo: str = None, per_page: int = 10) -> list[dict]:
        """Search for pull requests related to a query.

        Args:
            query: Search term
            repo: Optional specific repo (e.g., "Workiva/dbt-project")
            per_page: Max results
        """
        full_query = f"{query} type:pr"
        if repo:
            full_query += f" repo:{repo}"
        else:
            full_query += f" org:{self.org}"

        result = self._tool_call("search_issues", {"q": full_query, "per_page": per_page})
        items = []
        for content in result.get("content", []):
            if content.get("type") == "text":
                try:
                    data = json.loads(content["text"])
                    for item in data.get("items", [data] if "title" in data else []):
                        items.append({
                            "title": item.get("title", ""),
                            "number": item.get("number", ""),
                            "state": item.get("state", ""),
                            "url": item.get("html_url", ""),
                            "user": item.get("user", {}).get("login", ""),
                            "created_at": item.get("created_at", "")[:10],
                        })
                except (json.JSONDecodeError, TypeError):
                    pass
        return items

    def get_file_contents(self, repo: str, path: str) -> str:
        """Read a file from a GitHub repo.

        Args:
            repo: Full repo name (e.g., "Workiva/dbt-project")
            path: File path within the repo
        """
        owner, repo_name = repo.split("/", 1)
        result = self._tool_call("get_file_contents", {
            "owner": owner,
            "repo": repo_name,
            "path": path,
        })
        for content in result.get("content", []):
            if content.get("type") == "text":
                return content["text"]
        return ""

    def list_commits(self, repo: str, path: str = None, per_page: int = 10) -> list[dict]:
        """List recent commits for a repo, optionally filtered to a path."""
        owner, repo_name = repo.split("/", 1)
        args = {"owner": owner, "repo": repo_name, "per_page": per_page}
        if path:
            args["path"] = path
        result = self._tool_call("list_commits", args)
        commits = []
        for content in result.get("content", []):
            if content.get("type") == "text":
                try:
                    data = json.loads(content["text"])
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        commits.append({
                            "sha": item.get("sha", "")[:8],
                            "message": item.get("commit", {}).get("message", "").split("\n")[0],
                            "author": item.get("commit", {}).get("author", {}).get("name", ""),
                            "date": item.get("commit", {}).get("author", {}).get("date", "")[:10],
                            "url": item.get("html_url", ""),
                        })
                except (json.JSONDecodeError, TypeError):
                    pass
        return commits
