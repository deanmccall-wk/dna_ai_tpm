#!/usr/bin/env python3
"""Capture full field snapshots of Jira tickets before modifications.

Each ticket gets its own directory under snapshots/<KEY>/.
"""

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


def save_snapshot(tickets: dict, label: str = "") -> list[str]:
    """Save one snapshot file per ticket. Returns list of saved paths."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    timestamp_iso = datetime.now(timezone.utc).isoformat()
    paths = []

    for key, fields in tickets.items():
        ticket_dir = os.path.join(SNAPSHOT_DIR, key)
        os.makedirs(ticket_dir, exist_ok=True)

        filename = ts
        if label:
            filename += f"_{label}"
        filename += ".json"
        path = os.path.join(ticket_dir, filename)

        payload = {
            "key": key,
            "timestamp": timestamp_iso,
            "label": label,
            "fields": fields,
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        paths.append(path)

    total_kb = sum(os.path.getsize(p) for p in paths) / 1024
    print(f"\nSnapshot saved: {len(paths)} tickets in {SNAPSHOT_DIR}/ ({total_kb:.1f} KB total)")
    return paths


def snapshot_from_jql(jira: JiraClient, jql: str, label: str = "") -> list[str]:
    """Snapshot all tickets matching a JQL query."""
    print(f"Searching: {jql}")
    issues = jira.search_all(jql, fields=["key"])
    keys = [i["key"] for i in issues]
    print(f"Found {len(keys)} tickets")
    if not keys:
        print("Nothing to snapshot.")
        return []
    tickets = take_snapshot(jira, keys)
    return save_snapshot(tickets, label)


def snapshot_from_keys(jira: JiraClient, keys: list[str], label: str = "") -> list[str]:
    """Snapshot specific tickets by key."""
    print(f"Snapshotting {len(keys)} tickets")
    tickets = take_snapshot(jira, keys)
    return save_snapshot(tickets, label)


def get_latest_snapshot(key: str) -> dict:
    """Load the most recent snapshot for a given ticket key."""
    ticket_dir = os.path.join(SNAPSHOT_DIR, key)
    if not os.path.exists(ticket_dir):
        return {}
    files = sorted(os.listdir(ticket_dir))
    if not files:
        return {}
    latest = os.path.join(ticket_dir, files[-1])
    with open(latest) as f:
        return json.load(f)


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
