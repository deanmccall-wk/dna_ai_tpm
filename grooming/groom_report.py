#!/usr/bin/env python3
"""Generate grooming report in HTML and Markdown from audit data."""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from project_root import PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def generate_report():
    data_audit = load_json(os.path.join(OUTPUT_DIR, "data_audit.json"))
    dna_audit = load_json(os.path.join(OUTPUT_DIR, "dna_audit.json"))
    stale_report = load_json(os.path.join(OUTPUT_DIR, "stale_report.json"))

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Compute heatmap data from dna_audit
    heatmap = {}  # team -> {violation: count}
    if dna_audit.get("tickets"):
        for t in dna_audit["tickets"]:
            team = t.get("team") or "(No Team)"
            for v, is_set in t.get("violations", {}).items():
                if v == "has_any" or not is_set:
                    continue
                heatmap.setdefault(team, Counter())[v] += 1

    violation_fields = ["missing_team", "invalid_team", "missing_stakeholder",
                        "missing_effort", "missing_official_component",
                        "missing_epic_link", "missing_epic_name"]

    md = generate_markdown(ts, data_audit, dna_audit, stale_report, heatmap, violation_fields)
    html = generate_html(ts, data_audit, dna_audit, stale_report, heatmap, violation_fields)

    md_path = os.path.join(OUTPUT_DIR, "groom_report.md")
    html_path = os.path.join(OUTPUT_DIR, "groom_report.html")

    with open(md_path, "w") as f:
        f.write(md)
    with open(html_path, "w") as f:
        f.write(html)

    print(f"Markdown: {md_path}")
    print(f"HTML:     {html_path}")


def generate_markdown(ts, data_audit, dna_audit, stale_report, heatmap, violation_fields) -> str:
    lines = [f"# DnA Grooming Report", f"Generated: {ts}", ""]

    # DATA section
    if data_audit:
        lines.append("## DATA Project (Intake)")
        lines.append(f"- Total open tickets: {data_audit.get('total', '?')}")
        lines.append(f"- AUTO path (conforming): {data_audit.get('auto', '?')}")
        lines.append(f"- ENRICH path (non-conforming): {data_audit.get('enrich', '?')}")
        lines.append("")

    # Stale section
    if stale_report:
        lines.append("## Stale Tickets")
        lines.append(f"- Threshold: {stale_report.get('min_days', '?')}+ days")
        lines.append(f"- Total stale: {stale_report.get('total', '?')}")
        tiers = stale_report.get("tiers", {})
        lines.append(f"- Auto-close candidates: {tiers.get('auto_close', 0)}")
        lines.append(f"- Review candidates: {tiers.get('review', 0)}")
        lines.append(f"- Check-in candidates: {tiers.get('check_in', 0)}")
        lines.append("")

    # DNA section
    if dna_audit:
        lines.append("## DNA Project (Compliance)")
        lines.append(f"- Total open: {dna_audit.get('total', '?')}")
        lines.append(f"- Clean: {dna_audit.get('clean', '?')}")
        lines.append(f"- Has violations: {dna_audit.get('has_violations', '?')}")
        lines.append("")

        vc = dna_audit.get("violation_counts", {})
        if vc:
            lines.append("### Violation Counts")
            lines.append("| Violation | Count | % |")
            lines.append("|---|---:|---:|")
            total = dna_audit.get("total", 1)
            for v in violation_fields:
                c = vc.get(v, 0)
                lines.append(f"| {v} | {c} | {c*100//total}% |")
            lines.append("")

        # Heatmap
        if heatmap:
            lines.append("### Violations by Team")
            teams = sorted(heatmap.keys(), key=lambda t: -sum(heatmap[t].values()))
            header = "| Team | " + " | ".join(v.replace("missing_", "").replace("invalid_", "inv_") for v in violation_fields) + " | Total |"
            lines.append(header)
            lines.append("|---|" + "---:|" * (len(violation_fields) + 1))
            for team in teams[:15]:
                counts = heatmap[team]
                row = f"| {team} | " + " | ".join(str(counts.get(v, 0)) for v in violation_fields)
                row += f" | {sum(counts.values())} |"
                lines.append(row)
            lines.append("")

        # Repair queue
        epics = dna_audit.get("repair_queue_epics", [])
        issues = dna_audit.get("repair_queue_issues", [])
        lines.append("### Repair Queue")
        lines.append(f"- Epics to repair first: {len(epics)}")
        lines.append(f"- Issues to repair: {len(issues)}")

    return "\n".join(lines)


def generate_html(ts, data_audit, dna_audit, stale_report, heatmap, violation_fields) -> str:
    md = generate_markdown(ts, data_audit, dna_audit, stale_report, heatmap, violation_fields)

    # Simple HTML wrapper with table styling
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>DnA Grooming Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1000px; margin: 40px auto; padding: 0 20px; color: #333; }}
  h1 {{ border-bottom: 2px solid #2563eb; padding-bottom: 8px; }}
  h2 {{ color: #1e40af; margin-top: 32px; }}
  h3 {{ color: #374151; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #d1d5db; padding: 8px 12px; text-align: left; }}
  th {{ background: #f3f4f6; font-weight: 600; }}
  td:not(:first-child) {{ text-align: right; }}
  tr:nth-child(even) {{ background: #f9fafb; }}
  ul {{ line-height: 1.8; }}
  .metric {{ display: inline-block; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 16px 24px; margin: 8px; text-align: center; }}
  .metric .value {{ font-size: 2em; font-weight: 700; color: #1e40af; }}
  .metric .label {{ font-size: 0.9em; color: #6b7280; }}
</style>
</head>
<body>
"""
    # Convert markdown to basic HTML
    for line in md.split("\n"):
        if line.startswith("# "):
            html += f"<h1>{line[2:]}</h1>\n"
        elif line.startswith("## "):
            html += f"<h2>{line[3:]}</h2>\n"
        elif line.startswith("### "):
            html += f"<h3>{line[4:]}</h3>\n"
        elif line.startswith("| ") and "---|" not in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if any(line.startswith("| Team") or line.startswith("| Violation") for _ in [1]):
                html += "<table><tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>\n"
            else:
                html += "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>\n"
        elif line.startswith("|---"):
            pass  # skip markdown table separators
        elif line.startswith("- "):
            html += f"<li>{line[2:]}</li>\n"
        elif line == "":
            html += "\n"
        else:
            html += f"<p>{line}</p>\n"

    html += "</body></html>"
    return html


def main():
    generate_report()


if __name__ == "__main__":
    main()
