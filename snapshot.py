#!/usr/bin/env python3
"""Capture full field snapshots of Jira tickets before modifications."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from config import load_settings
from jira_client import JiraClient


SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "snapshots")


def take_snapshot(jira: JiraClient, keys: list[str]) -> dict:
    """Fetch full field data for a list of ticket keys."""
    tickets = {}
    for i, key in enumerate(keys, 1):
        print(f"  [{i}/{len(keys)}] {key}", end="", flush=True)
        try:
            issue = jira.get_issue_full(key)
            tickets[key] = issue.get("fields", {})
            print(" OK")
        except Exception as e:
            print(f" FAIL: {e}")
            tickets[key] = {"_error": str(e)}
    return tickets


def save_snapshot(tickets: dict, label: str = "") -> str:
    """Save snapshot to disk. Returns the file path."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"snapshot_{ts}"
    if label:
        filename += f"_{label}"
    filename += ".json"
    path = os.path.join(SNAPSHOT_DIR, filename)

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "ticket_count": len(tickets),
        "tickets": tickets,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    size_kb = os.path.getsize(path) / 1024
    print(f"\nSnapshot saved: {path} ({len(tickets)} tickets, {size_kb:.1f} KB)")
    return path


def snapshot_from_jql(jira: JiraClient, jql: str, label: str = "") -> str:
    """Snapshot all tickets matching a JQL query."""
    print(f"Searching: {jql}")
    issues = jira.search_all(jql, fields=["key"])
    keys = [i["key"] for i in issues]
    print(f"Found {len(keys)} tickets")
    if not keys:
        print("Nothing to snapshot.")
        return ""
    tickets = take_snapshot(jira, keys)
    return save_snapshot(tickets, label)


def snapshot_from_keys(jira: JiraClient, keys: list[str], label: str = "") -> str:
    """Snapshot specific tickets by key."""
    print(f"Snapshotting {len(keys)} tickets")
    tickets = take_snapshot(jira, keys)
    return save_snapshot(tickets, label)


def main():
    parser = argparse.ArgumentParser(description="Snapshot Jira tickets before modifications")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--jql", help="JQL query to select tickets")
    group.add_argument("--keys", help="Comma-separated ticket keys (e.g., DNA-5001,DNA-5002)")
    parser.add_argument("--label", default="", help="Optional label for the snapshot file")
    args = parser.parse_args()

    settings = load_settings()
    jira = JiraClient(settings.jira_base_url, settings.jira_pat)

    if args.jql:
        snapshot_from_jql(jira, args.jql, args.label)
    else:
        keys = [k.strip() for k in args.keys.split(",")]
        snapshot_from_keys(jira, keys, args.label)


if __name__ == "__main__":
    main()
