"""Playwright locators for Booking.com account / extranet login (fallback chain)."""

from __future__ import annotations

from typing import Iterable

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from .errors import BookingExtranetConnectError

_DEFAULT_LOCATOR_TIMEOUT_MS = 8_000


def _first_visible(
    locators: Iterable[Locator],
    *,
    timeout_ms: int = _DEFAULT_LOCATOR_TIMEOUT_MS,
    error_message: str,
) -> Locator:
    last_error: Exception | None = None
    for locator in locators:
        try:
            locator.first.wait_for(state="visible", timeout=timeout_ms)
            return locator.first
        except PlaywrightTimeoutError as exc:
            last_error = exc
            continue
    raise BookingExtranetConnectError(error_message) from last_error


def _labeled_input(page: Page, label: str) -> Locator:
    """Label text on Booking often sits on a wrapper div — scope to real inputs."""
    return page.get_by_label(label, exact=False).locator(
        "input, textarea, select, [contenteditable=true]"
    )


def username_input(page: Page) -> Locator:
    return _first_visible(
        (
            page.locator('input[name="loginname"]'),
            page.locator('input[autocomplete="username"]'),
            page.locator('input[type="email"]'),
            _labeled_input(page, "Username"),
            _labeled_input(page, "Email address"),
            _labeled_input(page, "Email"),
            page.get_by_role("textbox", name="Username"),
        ),
        error_message="Polje za korisničko ime nije pronađeno na stranici za prijavu.",
    )


def next_button(page: Page) -> Locator:
    return _first_visible(
        (
            page.get_by_role("button", name="Next"),
            page.get_by_role("button", name="Dalje"),
            page.locator('button[type="submit"]'),
        ),
        error_message='Gumb "Next" nije pronađen.',
    )


def password_input(page: Page) -> Locator:
    return _first_visible(
        (
            page.locator('input[type="password"]'),
            page.locator('input[name="password"]'),
            page.locator('input[autocomplete="current-password"]'),
            page.locator('input[autocomplete="new-password"]'),
            _labeled_input(page, "Password"),
            page.get_by_role("textbox", name="Password"),
        ),
        error_message="Polje za lozinku nije pronađeno (drugi korak prijave).",
    )


def sign_in_button(page: Page) -> Locator:
    return _first_visible(
        (
            page.get_by_role("button", name="Sign in"),
            page.get_by_role("button", name="Prijava"),
            page.locator('button[type="submit"]'),
        ),
        error_message='Gumb "Sign in" nije pronađen.',
    )


def verification_code_input(page: Page) -> Locator | None:
    """Return a visible 2FA / verification input, or None if not on screen."""
    candidates = (
        page.locator('input[name="pin"]'),
        page.locator('input[name="verification_code"]'),
        page.locator('input[autocomplete="one-time-code"]'),
        page.locator('input[inputmode="numeric"]'),
        _labeled_input(page, "Verification code"),
        _labeled_input(page, "Enter verification code"),
    )
    for locator in candidates:
        try:
            locator.first.wait_for(state="visible", timeout=2_000)
            return locator.first
        except PlaywrightTimeoutError:
            continue
    return None


def has_password_step_text(page: Page) -> bool:
    patterns = (
        "Enter your password",
        "Unesite lozinku",
        "password",
    )
    for pattern in patterns:
        try:
            page.get_by_text(pattern, exact=False).first.wait_for(
                state="visible", timeout=2_000
            )
            return True
        except PlaywrightTimeoutError:
            continue
    return False
