"""Combined asset lookup for triage — searches Atlan and GitHub for context
about tables, models, and code referenced in a ticket.

Extracts asset names from ticket description, then:
- Atlan: ownership, lineage links, documentation
- GitHub: related PRs, code that populates models
"""

import re


# Patterns for extracting asset references from ticket text
SNOWFLAKE_FQN = re.compile(
    r"(?:(?:GOLD|SILVER|BRONZE|LAKE)_(?:PROD|DEV|TEST)\.)"
    r"(\w+\.\w+)",
    re.IGNORECASE,
)
DBT_MODEL_REF = re.compile(r"\{\{\s*ref\s*\(\s*['\"](\w+)['\"]\s*\)\s*\}\}")
TABLE_NAME_PATTERN = re.compile(
    r"\b((?:dim|fct|stg|int|raw|obt|mart)_\w+)\b",
    re.IGNORECASE,
)
QUICKSIGHT_DASHBOARD_URL = re.compile(
    r"quicksight[\w.-]*\.aws\.amazon\.com/sn/dashboards/([\w-]+)",
    re.IGNORECASE,
)
QUICKSIGHT_DATASET_URL = re.compile(
    r"quicksight[\w.-]*\.aws\.amazon\.com/sn/start/data-sets/([\w-]+)",
    re.IGNORECASE,
)


def extract_asset_names(text: str) -> list[str]:
    """Extract probable table/model names and QuickSight IDs from ticket text."""
    names = set()

    for match in SNOWFLAKE_FQN.finditer(text):
        names.add(match.group(0))

    for match in DBT_MODEL_REF.finditer(text):
        names.add(match.group(1))

    for match in TABLE_NAME_PATTERN.finditer(text):
        names.add(match.group(1))

    for match in QUICKSIGHT_DASHBOARD_URL.finditer(text):
        names.add(f"qs-dashboard:{match.group(1)}")

    for match in QUICKSIGHT_DATASET_URL.finditer(text):
        names.add(f"qs-dataset:{match.group(1)}")

    return sorted(names)


def lookup_atlan(asset_names: list[str], atlan=None) -> dict:
    """Search Atlan for each asset name. Returns {name: [results]}."""
    if atlan is None:
        from clients.atlan_client import AtlanClient
        atlan = AtlanClient()

    results = {}
    for name in asset_names:
        try:
            if name.startswith("qs-dashboard:") or name.startswith("qs-dataset:"):
                qs_id = name.split(":", 1)[1]
                hits = atlan.search_quicksight(qs_id, limit=3)
            else:
                hits = atlan.search_tables(name, limit=3)
                if not hits:
                    hits = atlan.search_models(name, limit=3)
            results[name] = hits
        except Exception as e:
            results[name] = [{"error": str(e)}]
    return results


def lookup_github(asset_names: list[str], github=None) -> dict:
    """Search GitHub for code and PRs related to each asset name. Returns {name: {...}}."""
    if github is None:
        from clients.github_mcp_client import GitHubMCPClient
        github = GitHubMCPClient()

    results = {}
    try:
        for name in asset_names:
            code = []
            prs = []
            try:
                code = github.search_code(name, per_page=5)
            except Exception as e:
                code = [{"error": str(e)}]
            try:
                prs = github.search_prs(name, per_page=5)
            except Exception as e:
                prs = [{"error": str(e)}]
            results[name] = {"code": code, "prs": prs}
    finally:
        if github:
            github.close()
    return results


def lookup_assets_for_ticket(fields: dict, use_atlan: bool = True, use_github: bool = True) -> dict:
    """Extract asset names from a ticket and search Atlan + GitHub.

    Args:
        fields: Jira issue fields dict (needs 'summary' and 'description')
        use_atlan: Whether to search Atlan
        use_github: Whether to search GitHub

    Returns:
        {
            "asset_names": [...],
            "atlan": {name: [results]},
            "github": {name: {"code": [...], "prs": [...]}},
        }
    """
    text = (fields.get("summary") or "") + "\n" + (fields.get("description") or "")
    asset_names = extract_asset_names(text)

    result = {"asset_names": asset_names, "atlan": {}, "github": {}}

    if not asset_names:
        return result

    if use_atlan:
        try:
            result["atlan"] = lookup_atlan(asset_names)
        except Exception as e:
            result["atlan"] = {"_error": str(e)}

    if use_github:
        try:
            result["github"] = lookup_github(asset_names)
        except Exception as e:
            result["github"] = {"_error": str(e)}

    return result


def format_asset_context(context: dict) -> str:
    """Format asset lookup results for console display during triage."""
    lines = []
    asset_names = context.get("asset_names", [])
    if not asset_names:
        lines.append("  No asset references found in ticket.")
        return "\n".join(lines)

    lines.append(f"  Asset references found: {', '.join(asset_names)}")

    atlan = context.get("atlan", {})
    if atlan and "_error" not in atlan:
        lines.append("\n  Atlan:")
        for name, hits in atlan.items():
            if not hits or (len(hits) == 1 and "error" in hits[0]):
                lines.append(f"    {name}: no results")
                continue
            for hit in hits[:2]:
                owners = ", ".join(hit.get("owners", [])[:3]) or "no owner"
                lines.append(f"    {name}: {hit['type']} | owners: {owners} | {hit.get('url', '')}")

    github = context.get("github", {})
    if github and "_error" not in github:
        lines.append("\n  GitHub:")
        for name, data in github.items():
            code = data.get("code", [])
            prs = data.get("prs", [])
            if code and "error" not in code[0]:
                for c in code[:2]:
                    lines.append(f"    {name} code: {c.get('repository', '')}/{c.get('path', '')}")
            if prs and "error" not in prs[0]:
                for p in prs[:2]:
                    lines.append(f"    {name} PR: #{p.get('number', '')} {p.get('title', '')[:60]} ({p.get('state', '')})")

    return "\n".join(lines)


def format_asset_jira_comment(context: dict) -> str:
    """Format asset lookup results as a Jira wiki markup comment."""
    lines = ["h4. Asset Context"]
    asset_names = context.get("asset_names", [])
    if not asset_names:
        lines.append("No asset references found in ticket.")
        return "\n".join(lines)

    lines.append(f"*Assets referenced:* {', '.join(asset_names)}")

    atlan = context.get("atlan", {})
    if atlan and "_error" not in atlan:
        lines.append("\nh5. Atlan")
        lines.append("||Asset||Type||Owners||Link||")
        for name, hits in atlan.items():
            for hit in hits[:2]:
                if "error" in hit:
                    continue
                owners = ", ".join(hit.get("owners", [])[:3]) or "—"
                url = hit.get("url", "")
                link = f"[View in Atlan|{url}]" if url else "—"
                lines.append(f"|{name}|{hit.get('type', '')}|{owners}|{link}|")

    github = context.get("github", {})
    if github and "_error" not in github:
        lines.append("\nh5. GitHub")
        for name, data in github.items():
            code = [c for c in data.get("code", []) if "error" not in c]
            prs = [p for p in data.get("prs", []) if "error" not in p]
            if code:
                for c in code[:2]:
                    lines.append(f"* Code: [{c.get('path', '')}|{c.get('url', '')}] in {c.get('repository', '')}")
            if prs:
                for p in prs[:2]:
                    lines.append(f"* PR: [#{p.get('number', '')} {p.get('title', '')[:50]}|{p.get('url', '')}]")

    return "\n".join(lines)
