"""Fetch reservation details from Booking extranet booking.html page."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum

from django.conf import settings
from django.utils.dateparse import parse_date
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .browser_session import detect_needs_human, get_page, open_headed_context, wait_until_not_human
from .session_store import DEFAULT_STORAGE_FILENAME, load_storage_state
from .url_extract import build_booking_url, extract_booking_url_from_text, extract_res_id_from_url

logger = logging.getLogger(__name__)

_NAVIGATION_TIMEOUT_MS = 90_000
_HUMAN_WAIT_S = 900


class FetchOutcome(str, Enum):
    DONE = "done"
    NEEDS_HUMAN = "needs_human"
    NO_SESSION = "no_session"
    ERROR = "error"


@dataclass(frozen=True)
class FetchResult:
    outcome: FetchOutcome
    payload: dict | None = None
    error: str = ""


def resolve_target_url(
    *,
    booking_url: str | None = None,
    booking_number: str | None = None,
    email_html: str = "",
    email_text: str = "",
) -> str | None:
    if booking_url:
        return booking_url.strip()
    combined = (email_html or "") + (email_text or "")
    found = extract_booking_url_from_text(combined)
    if found:
        return found
    number = (booking_number or "").strip()
    hotel_id = (settings.BOOKING_EXTRANET_HOTEL_ID or "").strip()
    if number and hotel_id:
        return build_booking_url(res_id=number, hotel_id=hotel_id)
    return None


def _parse_labeled_fields(body_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    patterns = {
        "guest_name": r"(?im)^(?:Guest|Gost|Name|Ime)\s*[:\-]\s*(.+)$",
        "check_in": r"(?im)^(?:Check[- ]?in|Dolazak)\s*[:\-]\s*(.+)$",
        "check_out": r"(?im)^(?:Check[- ]?out|Odlazak)\s*[:\-]\s*(.+)$",
        "room": r"(?im)^(?:Room|Unit|Soba)\s*[:\-]\s*(.+)$",
        "status": r"(?im)^(?:Status)\s*[:\-]\s*(.+)$",
        "total": r"(?im)^(?:Total|Price|Cijena|Amount)\s*[:\-]\s*(.+)$",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, body_text)
        if match:
            fields[key] = match.group(1).strip()
    return fields


def _parse_dates(fields: dict[str, str]) -> tuple[date | None, date | None]:
    check_in = parse_date(fields.get("check_in", "")) if fields.get("check_in") else None
    check_out = parse_date(fields.get("check_out", "")) if fields.get("check_out") else None
    return check_in, check_out


def _parse_amount(raw: str | None) -> tuple[Decimal | None, str | None]:
    if not raw:
        return None, None
    currency_match = re.search(r"\b([A-Z]{3})\b", raw)
    currency = currency_match.group(1) if currency_match else None
    amount_match = re.search(r"([\d.,]+)", raw.replace(" ", ""))
    if not amount_match:
        return None, currency
    normalized = amount_match.group(1).replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized), currency
    except InvalidOperation:
        return None, currency


def scrape_booking_page(page: Page) -> dict:
    body_text = page.inner_text("body")
    fields = _parse_labeled_fields(body_text)
    check_in, check_out = _parse_dates(fields)
    amount, currency = _parse_amount(fields.get("total"))
    booking_number = extract_res_id_from_url(page.url or "") or ""
    return {
        "booking_number": booking_number,
        "guest_name": fields.get("guest_name", ""),
        "room_name": fields.get("room", ""),
        "check_in_date": check_in.isoformat() if check_in else None,
        "check_out_date": check_out.isoformat() if check_out else None,
        "booking_status": fields.get("status", ""),
        "total_amount": str(amount) if amount is not None else None,
        "currency": currency,
        "raw_text": body_text[:8000],
        "page_url": page.url,
        "page_title": page.title(),
    }


def _is_booking_page(page: Page) -> bool:
    url = (page.url or "").lower()
    return "booking.html" in url and "res_id=" in url


def run_fetch_on_page(page: Page, *, target_url: str) -> FetchResult:
    page.set_default_timeout(_NAVIGATION_TIMEOUT_MS)
    logger.info("Booking fetch: %s", target_url)
    page.goto(target_url, wait_until="domcontentloaded", timeout=_NAVIGATION_TIMEOUT_MS)

    if detect_needs_human(page):
        return FetchResult(outcome=FetchOutcome.NEEDS_HUMAN)

    if not _is_booking_page(page):
        if detect_needs_human(page):
            return FetchResult(outcome=FetchOutcome.NEEDS_HUMAN)
        return FetchResult(
            outcome=FetchOutcome.ERROR,
            error=f"Neočekivani URL: {page.url!r}",
        )

    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeoutError:
        pass

    return FetchResult(outcome=FetchOutcome.DONE, payload=scrape_booking_page(page))


def run_fetch_reservation(
    *,
    target_url: str,
    headed: bool | None = None,
    storage_relative_path: str = DEFAULT_STORAGE_FILENAME,
    wait_for_human: bool = True,
) -> FetchResult:
    if not load_storage_state(relative_path=storage_relative_path):
        return FetchResult(outcome=FetchOutcome.NO_SESSION, error="Nema spremljene sesije.")

    use_headed = headed if headed is not None else bool(
        settings.BOOKING_EXTRANET_HEADED and settings.BOOKING_EXTRANET_VNC_ENABLED
    )

    if use_headed:
        open_headed_context(storage_relative_path=storage_relative_path)
        page = get_page()
        result = run_fetch_on_page(page, target_url=target_url)
        if result.outcome == FetchOutcome.NEEDS_HUMAN and wait_for_human:
            resolved = wait_until_not_human(
                page,
                timeout_s=_HUMAN_WAIT_S,
                is_resolved=_is_booking_page,
            )
            if not resolved:
                return FetchResult(
                    outcome=FetchOutcome.NEEDS_HUMAN,
                    error="CAPTCHA nije riješen na vrijeme.",
                )
            if detect_needs_human(page):
                return FetchResult(outcome=FetchOutcome.NEEDS_HUMAN)
            return FetchResult(outcome=FetchOutcome.DONE, payload=scrape_booking_page(page))
        return result

    from playwright.sync_api import sync_playwright

    state = load_storage_state(relative_path=storage_relative_path)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state=state)
            page = context.new_page()
            return run_fetch_on_page(page, target_url=target_url)
        finally:
            browser.close()
