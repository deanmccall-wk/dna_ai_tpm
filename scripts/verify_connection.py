#!/usr/bin/env python3
"""Verify connectivity to Jira and Confluence, and discover DNA project fields."""

import json
import sys
from clients.config import load_settings
from clients.jira_client import JiraClient
from clients.confluence_client import ConfluenceClient


def check(label: str, fn):
    try:
        result = fn()
        print(f"  [OK]  {label}")
        return result
    except Exception as e:
        print(f"  [FAIL] {label} -- {e}")
        return None


def main():
    print("Loading configuration...")
    try:
        settings = load_settings()
    except EnvironmentError as e:
        print(f"\n  [FAIL] {e}")
        sys.exit(1)

    jira = JiraClient(settings.jira_base_url, settings.jira_pat)
    confluence = ConfluenceClient(settings.confluence_base_url, settings.confluence_pat)

    # -- Jira checks --
    print(f"\nJira ({settings.jira_base_url})")
    user = check("Authenticate (myself)", jira.myself)
    if user:
        print(f"         Logged in as: {user.get('displayName', '?')} ({user.get('name', '?')})")

    check("Access DATA project", lambda: jira.search("project = DATA", max_results=1))
    check("Access DNA project", lambda: jira.search("project = DNA", max_results=1))

    # -- Confluence checks --
    print(f"\nConfluence ({settings.confluence_base_url})")
    cu = check("Authenticate (current_user)", confluence.current_user)
    if cu:
        print(f"         Logged in as: {cu.get('displayName', '?')} ({cu.get('username', '?')})")

    # -- DNA create metadata --
    print("\nDNA Project - Create Metadata")
    meta = check("Fetch create metadata", lambda: jira.get_create_meta("DNA"))
    if meta:
        issue_types = meta.get("values") or meta.get("issueTypes") or []
        # Legacy format nests under projects
        if not issue_types and meta.get("projects"):
            for it in meta["projects"][0].get("issuetypes", []):
                issue_types.append(it)

        for it in issue_types:
            it_id = it.get("id", "?")
            it_name = it.get("name", it.get("untranslatedName", "?"))
            print(f"\n  Issue Type: {it_name} (id={it_id})")

            # Try fetching fields for this issue type (new endpoint)
            fields_meta = check(
                f"  Fields for {it_name}",
                lambda _id=it_id: jira.get_create_meta_fields("DNA", _id),
            )
            if fields_meta:
                field_values = fields_meta.get("values") or fields_meta.get("fields") or {}
                if isinstance(field_values, dict):
                    field_values = [{"fieldId": k, **v} for k, v in field_values.items()]
                required = [f for f in field_values if f.get("required")]
                if required:
                    print("    Required fields:")
                    for f in required:
                        fid = f.get("fieldId", "?")
                        fname = f.get("name", "?")
                        allowed = f.get("allowedValues", [])
                        values_str = ""
                        if allowed:
                            names = [v.get("name") or v.get("value", "?") for v in allowed[:10]]
                            values_str = f" -- allowed: {names}"
                            if len(allowed) > 10:
                                values_str += f" ... ({len(allowed)} total)"
                        print(f"      - {fid}: {fname}{values_str}")

        if not issue_types:
            print("  No issue types returned. Check your permissions on the DNA project.")

    print("\n--- Verification complete ---")


if __name__ == "__main__":
    main()
