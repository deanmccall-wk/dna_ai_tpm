#!/usr/bin/env python3
"""CLI tool for ad-hoc Atlan asset lookups during triage.

Usage:
    python scripts/lookup_asset.py dim_pipeline_with_signature_products
    python scripts/lookup_asset.py "GOLD_PROD.CPX.DIM_PIPELINE" --json
    python scripts/lookup_asset.py rpt_pipeline dim_subscriptions --json
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from clients.atlan_client import AtlanClient


def main():
    parser = argparse.ArgumentParser(description="Search Atlan for data assets")
    parser.add_argument("names", nargs="+", help="Asset names to search for")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    parser.add_argument("--limit", type=int, default=3, help="Max results per name")
    args = parser.parse_args()

    client = AtlanClient()

    all_results = {}
    for name in args.names:
        hits = client.search_tables(name, limit=args.limit)
        if not hits:
            hits = client.search_models(name, limit=args.limit)
        all_results[name] = hits

    if args.as_json:
        print(json.dumps(all_results, indent=2))
        return

    for name, hits in all_results.items():
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")
        if not hits:
            print("  No results found")
            continue
        for hit in hits:
            owners = ", ".join(hit.get("owners", [])[:3]) or "no owner"
            print(f"  {hit['type']:20s} | {hit.get('database','')}.{hit.get('schema','')}.{hit['name']}")
            print(f"  {'':20s} | owners: {owners}")
            print(f"  {'':20s} | {hit.get('url', '')}")


if __name__ == "__main__":
    main()
