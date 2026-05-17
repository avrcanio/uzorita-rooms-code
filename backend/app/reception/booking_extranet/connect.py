"""Playwright connect flow for Booking.com extranet (username → password → save session)."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from playwright.sync_api import Browser, Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .errors import BookingExtranetConnectError
from .outcomes import ConnectOutcome, ConnectResult, NEEDS_HUMAN_MESSAGE
from .urls import is_connected_url, is_login_redirect_url
from .session_store import (
    BookingExtranetSessionError,
    DEFAULT_STORAGE_FILENAME,
    ensure_configured,
    save_storage_state,
)
from . import selectors

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_MS = 120_000
_NAVIGATION_TIMEOUT_MS = 90_000


def ensure_connect_settings() -> None:
    """Validate env-backed settings required for automated login."""
    if not settings.BOOKING_EXTRANET_ENABLED:
        raise BookingExtranetConnectError("BOOKING_EXTRANET_ENABLED nije true.")
    username = (settings.BOOKING_EXTRANET_USERNAME or "").strip()
    password = (settings.BOOKING_EXTRANET_PASSWORD or "").strip()
    login_url = (settings.BOOKING_EXTRANET_LOGIN_URL or "").strip()
    if not username:
        raise BookingExtranetConnectError("BOOKING_EXTRANET_USERNAME nije postavljen.")
    if not password:
        raise BookingExtranetConnectError("BOOKING_EXTRANET_PASSWORD nije postavljen.")
    if not login_url:
        raise BookingExtranetConnectError("BOOKING_EXTRANET_LOGIN_URL nije postavljen.")
    try:
        ensure_configured()
    except BookingExtranetSessionError as exc:
        raise BookingExtranetConnectError(str(exc)) from exc


def detect_needs_human(page: Page) -> bool:
    """Detect CAPTCHA / AWS WAF — re-export from browser_session."""
    from .browser_session import detect_needs_human as _detect

    return _detect(page)


def detect_needs_2fa(page: Page) -> bool:
    if selectors.verification_code_input(page) is not None:
        return True
    for pattern in (
        "verification code",
        "two-factor",
        "2-step",
        "authenticator",
        "SMS code",
    ):
        try:
            page.get_by_text(pattern, exact=False).first.wait_for(
                state="visible", timeout=1_500
            )
            return True
        except PlaywrightTimeoutError:
            continue
    return False


def _fill_username_and_next(page: Page, username: str) -> None:
    logger.info("Booking extranet connect: username step")
    user_field = selectors.username_input(page)
    user_field.fill(username)
    selectors.next_button(page).click()
    page.wait_for_load_state("domcontentloaded", timeout=_NAVIGATION_TIMEOUT_MS)
    if not selectors.has_password_step_text(page):
        try:
            selectors.password_input(page)
        except BookingExtranetConnectError as exc:
            raise BookingExtranetConnectError(
                "Nakon klika Next nije učitan korak za lozinku."
            ) from exc


def _fill_password_and_sign_in(page: Page, password: str) -> None:
    logger.info("Booking extranet connect: password step")
    pwd_field = selectors.password_input(page)
    pwd_field.fill(password)
    selectors.sign_in_button(page).click()


def _wait_for_post_signin(page: Page) -> ConnectOutcome:
    from .urls import success_url_pattern

    success_fragment = success_url_pattern()

    def _resolved() -> str | None:
        url = page.url or ""
        if is_connected_url(url):
            return ConnectOutcome.CONNECTED.value
        if detect_needs_human(page):
            return ConnectOutcome.NEEDS_HUMAN.value
        if detect_needs_2fa(page):
            return ConnectOutcome.NEEDS_2FA.value
        if is_login_redirect_url(url):
            raise BookingExtranetConnectError(
                "Prijavljeni smo natrag na stranicu za prijavu (provjeri credentials ili op_token u LOGIN_URL)."
            )
        return None

    early = _resolved()
    if early == ConnectOutcome.CONNECTED.value:
        return ConnectOutcome.CONNECTED
    if early == ConnectOutcome.NEEDS_2FA.value:
        return ConnectOutcome.NEEDS_2FA
    if early == ConnectOutcome.NEEDS_HUMAN.value:
        return ConnectOutcome.NEEDS_HUMAN

    try:
        if success_fragment:
            page.wait_for_url(f"**{success_fragment}**", timeout=_NAVIGATION_TIMEOUT_MS)
            return ConnectOutcome.CONNECTED
    except PlaywrightTimeoutError:
        pass

    try:
        page.wait_for_url("**admin.booking.com/**", timeout=15_000)
    except PlaywrightTimeoutError:
        pass

    deadline_ms = _NAVIGATION_TIMEOUT_MS
    poll_ms = 500
    elapsed = 0
    while elapsed < deadline_ms:
        outcome_value = _resolved()
        if outcome_value == ConnectOutcome.CONNECTED.value:
            return ConnectOutcome.CONNECTED
        if outcome_value == ConnectOutcome.NEEDS_2FA.value:
            return ConnectOutcome.NEEDS_2FA
        if outcome_value == ConnectOutcome.NEEDS_HUMAN.value:
            return ConnectOutcome.NEEDS_HUMAN
        page.wait_for_timeout(poll_ms)
        elapsed += poll_ms

    if detect_needs_human(page):
        return ConnectOutcome.NEEDS_HUMAN
    if detect_needs_2fa(page):
        return ConnectOutcome.NEEDS_2FA
    if is_connected_url(page.url or ""):
        return ConnectOutcome.CONNECTED

    raise BookingExtranetConnectError(
        "Prijava nije dovršena: nije prepoznat extranet ni 2FA korak. "
        f"Trenutni URL: {page.url!r}"
    )


def run_connect_on_page(
    page: Page,
    *,
    storage_relative_path: str = DEFAULT_STORAGE_FILENAME,
) -> ConnectResult:
    """
    Execute login on an existing Playwright page (for tests or shared browser).

    Does not launch or close the browser.
    """
    ensure_connect_settings()
    username = settings.BOOKING_EXTRANET_USERNAME.strip()
    password = settings.BOOKING_EXTRANET_PASSWORD.strip()
    login_url = settings.BOOKING_EXTRANET_LOGIN_URL.strip()

    page.set_default_timeout(CONNECT_TIMEOUT_MS)
    logger.info("Booking extranet connect: opening login URL")
    page.goto(login_url, wait_until="domcontentloaded", timeout=_NAVIGATION_TIMEOUT_MS)

    _fill_username_and_next(page, username)
    _fill_password_and_sign_in(page, password)

    outcome = _wait_for_post_signin(page)
    if outcome == ConnectOutcome.NEEDS_HUMAN:
        logger.info("Booking extranet connect: CAPTCHA / human step required")
        return ConnectResult(outcome=ConnectOutcome.NEEDS_HUMAN)
    if outcome == ConnectOutcome.NEEDS_2FA:
        logger.info("Booking extranet connect: 2FA required")
        return ConnectResult(outcome=ConnectOutcome.NEEDS_2FA)

    state: dict[str, Any] = page.context.storage_state()
    try:
        save_storage_state(state, relative_path=storage_relative_path)
    except BookingExtranetSessionError as exc:
        raise BookingExtranetConnectError(str(exc)) from exc

    logger.info("Booking extranet connect: session saved")
    return ConnectResult(
        outcome=ConnectOutcome.CONNECTED,
        storage_relative_path=storage_relative_path,
    )


def run_connect(
    *,
    headless: bool = True,
    storage_relative_path: str = DEFAULT_STORAGE_FILENAME,
    browser: Browser | None = None,
    page: Page | None = None,
) -> ConnectResult:
    """
    Full connect: launch Chromium (unless page/browser provided), login, save encrypted state.

    When ``page`` is passed, the caller owns the browser lifecycle.
    When only ``browser`` is passed, a new context/page is created and closed after connect.
    """
    if page is not None:
        return run_connect_on_page(page, storage_relative_path=storage_relative_path)

    if browser is not None:
        context = browser.new_context()
        page = context.new_page()
        try:
            return run_connect_on_page(page, storage_relative_path=storage_relative_path)
        finally:
            context.close()

    with sync_playwright() as playwright:
        launched = playwright.chromium.launch(headless=headless)
        try:
            context = launched.new_context()
            page = context.new_page()
            try:
                return run_connect_on_page(
                    page, storage_relative_path=storage_relative_path
                )
            finally:
                context.close()
        finally:
            launched.close()


def submit_2fa_code(page: Page, code: str) -> ConnectOutcome:
    """Fill SMS / verification code and wait for extranet or next challenge."""
    code_value = (code or "").strip()
    if not code_value:
        raise BookingExtranetConnectError("2FA kod je prazan.")

    field = selectors.verification_code_input(page)
    if field is None:
        raise BookingExtranetConnectError("Polje za verifikacijski kod nije vidljivo.")

    field.fill(code_value)
    for locator in (
        page.get_by_role("button", name="Verify"),
        page.get_by_role("button", name="Continue"),
        page.get_by_role("button", name="Sign in"),
        page.get_by_role("button", name="Next"),
        page.locator('button[type="submit"]'),
    ):
        try:
            locator.first.click(timeout=3_000)
            break
        except PlaywrightTimeoutError:
            continue

    page.wait_for_load_state("domcontentloaded", timeout=_NAVIGATION_TIMEOUT_MS)
    return _wait_for_post_signin(page)


def run_verify_2fa_on_page(
    page: Page,
    code: str,
    *,
    storage_relative_path: str = DEFAULT_STORAGE_FILENAME,
) -> ConnectResult:
    """Complete login after needs_2fa using verification code on current page."""
    ensure_connect_settings()
    page.set_default_timeout(CONNECT_TIMEOUT_MS)
    outcome = submit_2fa_code(page, code)
    if outcome == ConnectOutcome.NEEDS_HUMAN:
        return ConnectResult(outcome=ConnectOutcome.NEEDS_HUMAN)
    if outcome == ConnectOutcome.NEEDS_2FA:
        raise BookingExtranetConnectError("Kod nije prihvaćen ili je potreban novi kod.")
    state: dict[str, Any] = page.context.storage_state()
    save_storage_state(state, relative_path=storage_relative_path)
    return ConnectResult(
        outcome=ConnectOutcome.CONNECTED,
        storage_relative_path=storage_relative_path,
    )


def run_verify_2fa(
    code: str,
    *,
    headless: bool = True,
    storage_relative_path: str = DEFAULT_STORAGE_FILENAME,
) -> ConnectResult:
    """Re-run login through password step, then submit 2FA code."""
    ensure_connect_settings()
    username = settings.BOOKING_EXTRANET_USERNAME.strip()
    password = settings.BOOKING_EXTRANET_PASSWORD.strip()
    login_url = settings.BOOKING_EXTRANET_LOGIN_URL.strip()

    with sync_playwright() as playwright:
        launched = playwright.chromium.launch(headless=headless)
        try:
            context = launched.new_context()
            page = context.new_page()
            try:
                page.set_default_timeout(CONNECT_TIMEOUT_MS)
                page.goto(
                    login_url,
                    wait_until="domcontentloaded",
                    timeout=_NAVIGATION_TIMEOUT_MS,
                )
                _fill_username_and_next(page, username)
                _fill_password_and_sign_in(page, password)
                post_signin = _wait_for_post_signin(page)
                if post_signin == ConnectOutcome.NEEDS_HUMAN:
                    return ConnectResult(outcome=ConnectOutcome.NEEDS_HUMAN)
                if post_signin == ConnectOutcome.CONNECTED:
                    state = page.context.storage_state()
                    save_storage_state(state, relative_path=storage_relative_path)
                    return ConnectResult(
                        outcome=ConnectOutcome.CONNECTED,
                        storage_relative_path=storage_relative_path,
                    )
                return run_verify_2fa_on_page(
                    page, code, storage_relative_path=storage_relative_path
                )
            finally:
                context.close()
        finally:
            launched.close()
