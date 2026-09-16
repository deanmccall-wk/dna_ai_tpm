"""Backward-compatibility shim — imports from the new REST API client.

The Docker/MCP-based client has been replaced by a direct REST API client
in github_client.py. This file re-exports the class under the old name.
"""

from clients.github_client import GitHubClient as GitHubMCPClient  # noqa: F401
