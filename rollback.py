#!/usr/bin/env python3
"""Rollback Jira ticket changes from per-ticket snapshots or change logs."""

import argparse
import json
import os
import sys

from config import load_settings
from jira_client import JiraClient
from snapshot import SNAPSHOT_DIR, get_latest_snapshot


def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


RESTORABLE_FIELDS = [
    "customfield_10288", "customfield_36420", "components",
    "story_points", "customfield_10004", "customfield_10008",
    "customfield_13720", "priority", "summary", "description",
]


def restore_ticket(jira: JiraClient, key: str, snapshot_path: str = None, dry_run: bool = True) -> None:
    """Restore a single ticket from its snapshot."""
    if snapshot_path:
        data = load_json(snapshot_path)
    else:
        data = get_latest_snapshot(key)
        if not data:
            print(f"  [{key}] No snapshot found")
            return

    fields = data.get("fields", {})
    if "_error" in fields:
        print(f"  [{key}] SKIP (snapshot had error)")
        return

    restore_payload = {fid: fields[fid] for fid in RESTORABLE_FIELDS if fid in fields}
    if not restore_payload:
        print(f"  [{key}] SKIP (no restorable fields)")
        return

    if dry_run:
        print(f"  [{key}] WOULD RESTORE {len(restore_payload)} fields: {list(restore_payload.keys())}")
    else:
        try:
            jira.update_issue(key, restore_payload)
            print(f"  [{key}] RESTORED {len(restore_payload)} fields")
        except Exception as e:
            print(f"  [{key}] FAIL: {e}")


def restore_tickets(jira: JiraClient, keys: list[str], dry_run: bool = True) -> None:
    """Restore multiple tickets from their latest snapshots."""
    print(f"Restoring {len(keys)} tickets from latest snapshots")
    for key in keys:
        restore_ticket(jira, key, dry_run=dry_run)


def restore_from_snapshot_file(jira: JiraClient, snapshot_path: str, dry_run: bool = True) -> None:
    """Restore a ticket from a specific snapshot file."""
    data = load_json(snapshot_path)
    key = data.get("key", os.path.basename(os.path.dirname(snapshot_path)))
    print(f"Restoring {key} from {snapshot_path} (taken {data.get('timestamp', '?')})")
    restore_ticket(jira, key, snapshot_path=snapshot_path, dry_run=dry_run)


def undo_from_changelog(jira: JiraClient, changes_path: str,
                         keys: list[str] = None, fields: list[str] = None,
                         dry_run: bool = True) -> None:
    """Undo specific changes by reverting to old_value."""
    data = load_json(changes_path)
    changes = data.get("changes") or data.get("results", [])
    print(f"Change log: {changes_path}")
    print(f"  Timestamp: {data.get('timestamp', '?')}")
    print(f"  Total entries: {len(changes)}")

    if keys:
        changes = [c for c in changes if c.get("key") in keys]
    if fields:
        changes = [c for c in changes if c.get("field") in fields]

    actionable = [c for c in changes if "old_value" in c]
    print(f"  Changes to undo: {len(actionable)}")

    for change in actionable:
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
                    print(f"  [{key}] SKIP {field} (current value differs — someone else changed it)")
            except Exception as e:
                print(f"  [{key}] FAIL {field}: {e}")


def _summarize(val) -> str:
    s = json.dumps(val, default=str)
    return s[:80] + "..." if len(s) > 80 else s


def _values_match(a, b) -> bool:
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def main():
    parser = argparse.ArgumentParser(description="Rollback Jira ticket changes")
    sub = parser.add_subparsers(dest="command", required=True)

    restore = sub.add_parser("restore", help="Restore ticket(s) from snapshots")
    restore.add_argument("target", help="Ticket key (DATA-2496), comma-separated keys, or path to a snapshot file")
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
        target = args.target
        if os.path.isfile(target):
            restore_from_snapshot_file(jira, target, dry_run=dry_run)
        else:
            keys = [k.strip() for k in target.split(",")]
            restore_tickets(jira, keys, dry_run=dry_run)

    elif args.command == "undo":
        keys = [k.strip() for k in args.keys.split(",")] if args.keys else None
        fields = [f.strip() for f in args.fields.split(",")] if args.fields else None
        undo_from_changelog(jira, args.changelog, keys=keys, fields=fields, dry_run=dry_run)

    if dry_run:
        print("\n=== Run with --execute to apply changes ===")


if __name__ == "__main__":
    main()
