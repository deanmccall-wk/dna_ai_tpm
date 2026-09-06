#!/usr/bin/env python3
"""Upload the triage workflow diagram to the Confluence page and embed it."""
import os, sys, base64, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from clients.config import load_settings
from clients.confluence_client import ConfluenceClient

s = load_settings()
conf = ConfluenceClient(s.confluence_base_url, s.confluence_pat)

PAGE_ID = "530849232"
IMG_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "triage_workflow.png")

# Step 1: Upload the image as an attachment
with open(IMG_PATH, "rb") as f:
    img_data = f.read()

attach_url = conf._url(f'/content/{PAGE_ID}/child/attachment')
# Use the session but override Content-Type for multipart upload
sess = requests.Session()
sess.headers.update(conf.session.headers)
sess.headers["X-Atlassian-Token"] = "nocheck"
del sess.headers["Content-Type"]  # let requests set multipart boundary
resp = sess.post(
    attach_url,
    files={"file": ("triage_workflow.png", img_data, "image/png")},
    params={"allowDuplicated": "true"},
)
resp.raise_for_status()
print(f"Attachment uploaded: {resp.json()['results'][0]['title']}")

# Step 2: Update the page body to reference the attachment instead of the ASCII art
page = conf.get_page(PAGE_ID)
body = page["body"]["storage"]["value"]
version = page["version"]["number"]

# Replace the ASCII workflow diagram with the embedded image
old_diagram_start = '<table>\n<tbody>\n<tr><td style="background-color:#f4f5f7; text-align:center; padding:20px; font-family:monospace; white-space:pre; line-height:1.8;">'
old_diagram_end = '</td></tr>\n</tbody>\n</table>'

if old_diagram_start in body:
    start_idx = body.index(old_diagram_start)
    end_idx = body.index(old_diagram_end, start_idx) + len(old_diagram_end)
    new_diagram = '<p><ac:image ac:width="900"><ri:attachment ri:filename="triage_workflow.png" /></ac:image></p>'
    body = body[:start_idx] + new_diagram + body[end_idx:]
    
    result = conf.update_page(
        page_id=PAGE_ID,
        title=page["title"],
        body_html=body,
        version=version + 1,
    )
    print(f"Page updated with embedded diagram (version {version + 1})")
    print(f"URL: {result['_links']['base']}{result['_links']['webui']}")
else:
    print("Could not find the ASCII diagram section to replace. Checking for existing image tag...")
    if "triage_workflow.png" in body:
        print("Image already embedded. Attachment was updated (new version of the image uploaded).")
    else:
        # Insert after the "Workflow Diagram" heading
        marker = "<h3>Workflow Diagram</h3>"
        if marker in body:
            new_diagram = '\n<p><ac:image ac:width="900"><ri:attachment ri:filename="triage_workflow.png" /></ac:image></p>\n'
            body = body.replace(marker, marker + new_diagram)
            result = conf.update_page(
                page_id=PAGE_ID,
                title=page["title"],
                body_html=body,
                version=version + 1,
            )
            print(f"Page updated with diagram after heading (version {version + 1})")
        else:
            print("Could not find insertion point. Manual update needed.")
