"""Singleton headed Playwright browser on DISPLAY=:99 for CAPTCHA + scrape."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable

from django.conf import settings
from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .errors import BookingExtranetConnectError
from .session_store import (
    DEFAULT_STORAGE_FILENAME,
    load_storage_state,
    save_storage_state,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_playwright = None
_browser: Browser | None = None
_context: BrowserContext | None = None
_page: Page | None = None


def _display_env() -> str:
    return (settings.BOOKING_EXTRANET_VNC_DISPLAY or ":99").strip() or ":99"


def _ensure_x_display() -> None:
    """Fail fast when Xvfb is down (stale socket or wrong Celery worker)."""
    display = _display_env()
    os.environ["DISPLAY"] = display
    if not display.startswith(":"):
        return
    socket_path = f"/tmp/.X11-unix/X{display[1:]}"
    if os.path.exists(socket_path):
        return
    raise BookingExtranetConnectError(
        f"Xvfb nije aktivan ({display}, nema {socket_path}). "
        "Playwright headed radi samo u kontejneru uzorita-celery-booking-browser — "
        "provjerite da celery-worker ne sluša booking_browser red i restartajte booking-browser."
    )


def detect_needs_human(page: Page) -> bool:
    """Detect CAPTCHA / AWS WAF Human Verification — do not solve automatically."""
    title = str(page.title() or "").lower()
    if "human verification" in title or "access denied" in title:
        return True

    url = str(page.url or "").lower()
    if "human verification" in url or "/challenge" in url or "awswaf" in url:
        return True

    captcha_iframes = (
        'iframe[src*="recaptcha"]',
        'iframe[title*="reCAPTCHA"]',
        'iframe[name*="captcha"]',
        'iframe[src*="captcha"]',
    )
    for selector in captcha_iframes:
        try:
            if page.locator(selector).first.is_visible(timeout=800):
                return True
        except PlaywrightTimeoutError:
            continue

    challenge_patterns = (
        "captcha",
        "verify you are human",
        "verify you're human",
        "human verification",
        "select all images",
        "choose all",
        "security check",
        "robot",
        "unusual traffic",
        "aws waf",
    )
    for pattern in challenge_patterns:
        try:
            page.get_by_text(pattern, exact=False).first.wait_for(
                state="visible", timeout=1_000
            )
            return True
        except PlaywrightTimeoutError:
            continue

    try:
        locator = page.locator(
            '[class*="captcha"], [id*="captcha"], [data-testid*="captcha"], '
            '[class*="awswaf"], [id*="awswaf"]'
        ).first
        if locator.count() > 0 and locator.is_visible(timeout=800):
            return True
    except (PlaywrightTimeoutError, AttributeError, TypeError):
        pass

    return False


def open_headed_context(
    *,
    storage_relative_path: str = DEFAULT_STORAGE_FILENAME,
) -> BrowserContext:
    """Open or reuse a single headed browser context on the worker process."""
    global _playwright, _browser, _context, _page

    with _lock:
        if _context is not None:
            return _context

        _ensure_x_display()
        state = load_storage_state(relative_path=storage_relative_path)
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=False)
        kwargs: dict[str, Any] = {}
        if state:
            kwargs["storage_state"] = state
        _context = _browser.new_context(**kwargs)
        _page = _context.new_page()
        logger.info("Booking extranet headed browser opened (display=%s)", _display_env())
        return _context


def get_page() -> Page:
    if _page is None:
        open_headed_context()
    assert _page is not None
    return _page


def save_context_state(*, relative_path: str = DEFAULT_STORAGE_FILENAME) -> None:
    if _context is None:
        raise RuntimeError("No headed browser context to save.")
    state: dict[str, Any] = _context.storage_state()
    save_storage_state(state, relative_path=relative_path)


def close_all() -> None:
    global _playwright, _browser, _context, _page

    with _lock:
        if _page is not None:
            try:
                _page.close()
            except Exception:
                logger.exception("Error closing headed page")
            _page = None
        if _context is not None:
            try:
                _context.close()
            except Exception:
                logger.exception("Error closing headed context")
            _context = None
        if _browser is not None:
            try:
                _browser.close()
            except Exception:
                logger.exception("Error closing headed browser")
            _browser = None
        if _playwright is not None:
            try:
                _playwright.stop()
            except Exception:
                logger.exception("Error stopping playwright")
            _playwright = None


def wait_until_not_human(
    page: Page,
    *,
    timeout_s: int = 900,
    poll_ms: int = 1_000,
    is_resolved: Callable[[Page], bool] | None = None,
) -> bool:
    """
    Poll until CAPTCHA/WAF is gone and optional ``is_resolved(page)`` returns True.

    Returns True when resolved, False on timeout.
    """
    elapsed_ms = 0
    timeout_ms = timeout_s * 1000
    while elapsed_ms < timeout_ms:
        if not detect_needs_human(page):
            if is_resolved is None or is_resolved(page):
                return True
        page.wait_for_timeout(poll_ms)
        elapsed_ms += poll_ms
    return not detect_needs_human(page) and (
        is_resolved is None or is_resolved(page)
    )
