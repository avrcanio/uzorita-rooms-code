"""Headless session health check using saved Playwright storage_state."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from django.conf import settings
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .browser_session import detect_needs_human, get_page, open_headed_context, wait_until_not_human
from .urls import is_connected_url, is_login_redirect_url
from .session_store import BookingExtranetSessionError, load_storage_state

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT_MS = 60_000


class HealthOutcome(str, Enum):
    CONNECTED = "connected"
    EXPIRED = "expired"
    NO_SESSION = "no_session"
    NEEDS_HUMAN = "needs_human"
    ERROR = "error"


@dataclass(frozen=True)
class HealthResult:
    outcome: HealthOutcome
    detail: str = ""


def _evaluate_page(page) -> HealthResult:
    url = page.url or ""
    if is_connected_url(url):
        return HealthResult(outcome=HealthOutcome.CONNECTED)
    if is_login_redirect_url(url) or detect_needs_human(page):
        return HealthResult(
            outcome=HealthOutcome.NEEDS_HUMAN,
            detail="Sesija zahtijeva CAPTCHA ili ponovnu prijavu.",
        )
    if "admin.booking.com" in url.lower():
        return HealthResult(outcome=HealthOutcome.CONNECTED)
    return HealthResult(
        outcome=HealthOutcome.EXPIRED,
        detail=f"Neočekivani URL nakon health checka: {url!r}",
    )


def run_session_health_check(
    *,
    relative_path: str = "state.enc",
    headless: bool = True,
    wait_for_human: bool = True,
) -> HealthResult:
    try:
        state = load_storage_state(relative_path=relative_path)
    except BookingExtranetSessionError as exc:
        return HealthResult(outcome=HealthOutcome.ERROR, detail=str(exc))

    if not state:
        return HealthResult(
            outcome=HealthOutcome.NO_SESSION,
            detail="Nema spremljene sesije.",
        )

    check_url = (settings.BOOKING_EXTRANET_HEALTH_CHECK_URL or "").strip()
    if not check_url:
        check_url = "https://admin.booking.com/"

    if not headless:
        try:
            open_headed_context(storage_relative_path=relative_path)
            page = get_page()
            page.set_default_timeout(_HEALTH_TIMEOUT_MS)
            logger.info("Booking extranet health check (headed): %s", check_url)
            page.goto(check_url, wait_until="domcontentloaded", timeout=_HEALTH_TIMEOUT_MS)
            result = _evaluate_page(page)
            if result.outcome == HealthOutcome.NEEDS_HUMAN and wait_for_human:
                resolved = wait_until_not_human(
                    page,
                    timeout_s=900,
                    is_resolved=lambda p: _evaluate_page(p).outcome == HealthOutcome.CONNECTED,
                )
                if resolved:
                    return _evaluate_page(page)
            return result
        except PlaywrightTimeoutError as exc:
            return HealthResult(
                outcome=HealthOutcome.ERROR,
                detail=f"Health check timeout: {exc}",
            )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state=state)
            page = context.new_page()
            page.set_default_timeout(_HEALTH_TIMEOUT_MS)
            logger.info("Booking extranet health check: %s", check_url)
            page.goto(check_url, wait_until="domcontentloaded", timeout=_HEALTH_TIMEOUT_MS)
            return _evaluate_page(page)
        except PlaywrightTimeoutError as exc:
            return HealthResult(
                outcome=HealthOutcome.ERROR,
                detail=f"Health check timeout: {exc}",
            )
        finally:
            browser.close()
