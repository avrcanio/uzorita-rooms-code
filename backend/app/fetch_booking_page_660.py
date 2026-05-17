"""One-off: open extranet booking link from InboundEmail #660 and print page text."""
from __future__ import annotations

import html
import os
import re
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from communications.models import InboundEmail
from playwright.sync_api import sync_playwright
from reception.booking_extranet.session_store import load_storage_state


def main() -> int:
    inbound_id = int(sys.argv[1]) if len(sys.argv) > 1 else 660
    e = InboundEmail.objects.get(id=inbound_id)
    text = (e.body_html or "") + (e.body_text or "")
    links = re.findall(
        r"https://admin\.booking\.com/hotel/hoteladmin/extranet_ng/manage/booking\.html\?[^\s\"<>]+",
        text,
        re.I,
    )
    if not links:
        print("No booking.html link found", file=sys.stderr)
        return 1
    url = html.unescape(links[0])
    print("subject:", e.subject)
    print("booking_number:", (e.parsed_payload or {}).get("booking_number"))
    print("url:", url)

    state = load_storage_state()
    if not state:
        print("NO SESSION", file=sys.stderr)
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=state)
        page = ctx.new_page()
        page.set_default_timeout(90000)
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(5000)
        print("final_url:", page.url)
        print("title:", page.title())
        body_text = page.inner_text("body")
        print("--- body ---")
        print(body_text)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
