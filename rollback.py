#!/usr/bin/env python3
"""Rollback Jira ticket changes from snapshots or change logs."""

import argparse
import json
import os
import sys

from config import load_settings
from jira_client import JiraClient


def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def restore_from_snapshot(jira: JiraClient, snapshot_path: str,
                          keys: list[str] = None, dry_run: bool = True) -> None:
    """Restore tickets to their snapshot state."""
    data = load_json(snapshot_path)
    tickets = data["tickets"]
    print(f"Snapshot: {snapshot_path}")
    print(f"  Taken: {data['timestamp']}")
    print(f"  Tickets: {data['ticket_count']}")

    if keys:
        tickets = {k: v for k, v in tickets.items() if k in keys}
        print(f"  Filtered to {len(tickets)} tickets: {keys}")

    restorable_fields = [
        "customfield_10288", "customfield_36420", "components",
        "story_points", "customfield_10004", "customfield_10008",
        "customfield_13720", "priority", "summary", "description",
    ]

    for key, fields in tickets.items():
        if "_error" in fields:
            print(f"  [{key}] SKIP (snapshot had error)")
            continue

        restore_payload = {}
        for field_id in restorable_fields:
            if field_id in fields:
                restore_payload[field_id] = fields[field_id]

        if not restore_payload:
            print(f"  [{key}] SKIP (no restorable fields)")
            continue

        if dry_run:
            print(f"  [{key}] WOULD RESTORE {len(restore_payload)} fields: {list(restore_payload.keys())}")
        else:
            try:
                jira.update_issue(key, restore_payload)
                print(f"  [{key}] RESTORED {len(restore_payload)} fields")
            except Exception as e:
                print(f"  [{key}] FAIL: {e}")


def undo_from_changelog(jira: JiraClient, changes_path: str,
                         keys: list[str] = None, fields: list[str] = None,
                         dry_run: bool = True) -> None:
    """Undo specific changes by reverting to old_value."""
    data = load_json(changes_path)
    changes = data["changes"]
    print(f"Change log: {changes_path}")
    print(f"  Timestamp: {data['timestamp']}")
    print(f"  Total changes: {len(changes)}")

    if keys:
        changes = [c for c in changes if c["key"] in keys]
    if fields:
        changes = [c for c in changes if c["field"] in fields]

    print(f"  Changes to undo: {len(changes)}")

    for change in changes:
        key = change["key"]
        field = change["field"]
        old_value = change["old_value"]
        expected_new = change["new_value"]

        if dry_run:
            print(f"  [{key}] WOULD UNDO {field}: {_summarize(expected_new)} -> {_summarize(old_value)}")
        else:
            try:
                current = jira.get_issue(key, fields=[field])
                current_val = current.get("fields", {}).get(field)
                if _values_match(current_val, expected_new):
                    jira.update_issue(key, {field: old_value})
                    print(f"  [{key}] UNDONE {field}")
                else:
                    print(f"  [{key}] SKIP {field} (current value differs from expected — someone else changed it)")
            except Exception as e:
                print(f"  [{key}] FAIL {field}: {e}")


def _summarize(val) -> str:
    s = json.dumps(val, default=str)
    return s[:80] + "..." if len(s) > 80 else s


def _values_match(a, b) -> bool:
    """Loose comparison for Jira field values."""
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def main():
    parser = argparse.ArgumentParser(description="Rollback Jira ticket changes")
    sub = parser.add_subparsers(dest="command", required=True)

    restore = sub.add_parser("restore", help="Restore from a snapshot file")
    restore.add_argument("snapshot", help="Path to snapshot JSON file")
    restore.add_argument("--keys", help="Comma-separated keys to restore (default: all)")
    restore.add_argument("--execute", action="store_true", help="Actually apply (default: dry-run)")

    undo = sub.add_parser("undo", help="Undo specific changes from a change log")
    undo.add_argument("changelog", help="Path to change log JSON file")
    undo.add_argument("--keys", help="Comma-separated keys to undo")
    undo.add_argument("--fields", help="Comma-separated field IDs to undo")
    undo.add_argument("--execute", action="store_true", help="Actually apply (default: dry-run)")

    args = parser.parse_args()
    settings = load_settings()
    jira = JiraClient(settings.jira_base_url, settings.jira_pat)
    dry_run = not getattr(args, "execute", False)

    if dry_run:
        print("=== DRY RUN (no changes will be made) ===\n")

    if args.command == "restore":
        keys = [k.strip() for k in args.keys.split(",")] if args.keys else None
        restore_from_snapshot(jira, args.snapshot, keys=keys, dry_run=dry_run)
    elif args.command == "undo":
        keys = [k.strip() for k in args.keys.split(",")] if args.keys else None
        fields = [f.strip() for f in args.fields.split(",")] if args.fields else None
        undo_from_changelog(jira, args.changelog, keys=keys, fields=fields, dry_run=dry_run)

    if dry_run:
        print("\n=== Run with --execute to apply changes ===")


if __name__ == "__main__":
    main()
