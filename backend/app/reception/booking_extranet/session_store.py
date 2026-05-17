"""Encrypted Playwright storage_state persistence for Booking.com extranet."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_STORAGE_FILENAME = "state.enc"

# Playwright storage_state cookie fields; extra keys (e.g. partitionKey) break new_context on worker.
_PLAYWRIGHT_COOKIE_KEYS = frozenset(
    {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
)
_EXCLUDED_COOKIE_NAMES = frozenset({"OptanonConsent"})


def _normalize_expires(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def sanitize_cookie(cookie: Any) -> dict[str, Any] | None:
    """Keep only Playwright-compatible cookie fields; drop problematic cookies."""
    if not isinstance(cookie, dict):
        return None
    name = cookie.get("name")
    if not name or not isinstance(name, str):
        return None
    if name in _EXCLUDED_COOKIE_NAMES:
        return None
    value = cookie.get("value")
    domain = cookie.get("domain")
    path = cookie.get("path", "/")
    if value is None or domain is None:
        return None
    cleaned: dict[str, Any] = {
        "name": name,
        "value": str(value),
        "domain": str(domain),
        "path": str(path) if path else "/",
    }
    expires = _normalize_expires(cookie.get("expires"))
    if expires is not None:
        cleaned["expires"] = int(expires) if isinstance(expires, float) and expires == int(expires) else expires
    for flag in ("httpOnly", "secure"):
        if flag in cookie:
            cleaned[flag] = bool(cookie[flag])
    same_site = cookie.get("sameSite")
    if same_site in ("Strict", "Lax", "None"):
        cleaned["sameSite"] = same_site
    return cleaned


def sanitize_storage_state(state: dict[str, Any]) -> dict[str, Any]:
    """Filter cookies for Playwright compatibility before save/load."""
    validated = validate_storage_state(state)
    out: dict[str, Any] = {}
    cookies = validated.get("cookies")
    if cookies is not None:
        sanitized: list[dict[str, Any]] = []
        for item in cookies:
            cleaned = sanitize_cookie(item)
            if cleaned is not None:
                sanitized.append(cleaned)
        out["cookies"] = sanitized
    origins = validated.get("origins")
    if origins is not None:
        out["origins"] = origins
    return out


class BookingExtranetSessionError(Exception):
    """Configuration or storage errors for Booking extranet session."""


def _fernet() -> Fernet:
    key = (settings.BOOKING_EXTRANET_FERNET_KEY or "").strip()
    if not key:
        raise BookingExtranetSessionError("BOOKING_EXTRANET_FERNET_KEY nije postavljen.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise BookingExtranetSessionError(
            "BOOKING_EXTRANET_FERNET_KEY nije valjan Fernet ključ."
        ) from exc


def storage_dir() -> Path:
    root = (settings.BOOKING_EXTRANET_STORAGE_DIR or "").strip()
    if not root:
        raise BookingExtranetSessionError("BOOKING_EXTRANET_STORAGE_DIR nije postavljen.")
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_storage_file(relative_path: str = DEFAULT_STORAGE_FILENAME) -> Path:
    rel = (relative_path or DEFAULT_STORAGE_FILENAME).strip()
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        raise BookingExtranetSessionError(f"Nevaljana storage putanja: {relative_path!r}")
    return storage_dir() / rel


def ensure_configured() -> None:
    """Verify Fernet key and storage directory settings."""
    _fernet()
    storage_dir()


def validate_storage_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise BookingExtranetSessionError("storage_state mora biti JSON objekt.")
    if "cookies" not in state and "origins" not in state:
        raise BookingExtranetSessionError(
            "storage_state mora sadržavati 'cookies' i/ili 'origins'."
        )
    cookies = state.get("cookies")
    if cookies is not None and not isinstance(cookies, list):
        raise BookingExtranetSessionError("'cookies' mora biti lista.")
    origins = state.get("origins")
    if origins is not None and not isinstance(origins, list):
        raise BookingExtranetSessionError("'origins' mora biti lista.")
    return state


def save_storage_state(
    state: dict[str, Any],
    *,
    relative_path: str = DEFAULT_STORAGE_FILENAME,
) -> Path:
    """Encrypt and write Playwright storage_state JSON to disk."""
    validated = sanitize_storage_state(state)
    target = resolve_storage_file(relative_path)
    payload = json.dumps(validated, separators=(",", ":")).encode("utf-8")
    encrypted = _fernet().encrypt(payload)
    target.write_bytes(encrypted)
    logger.info("Booking extranet storage_state saved (%s bytes ciphertext)", len(encrypted))
    return target


def load_storage_state(
    *,
    relative_path: str = DEFAULT_STORAGE_FILENAME,
) -> dict[str, Any] | None:
    """Load and decrypt storage_state; return None if the file does not exist."""
    target = resolve_storage_file(relative_path)
    if not target.is_file():
        return None
    raw = target.read_bytes()
    try:
        decrypted = _fernet().decrypt(raw)
    except InvalidToken as exc:
        raise BookingExtranetSessionError(
            "Ne mogu dekriptirati storage_state (pogrešan Fernet ključ ili oštećena datoteka)."
        ) from exc
    try:
        parsed = json.loads(decrypted.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BookingExtranetSessionError("Dekriptirani storage_state nije valjan JSON.") from exc
    return sanitize_storage_state(validate_storage_state(parsed))


def clear_storage_state(*, relative_path: str = DEFAULT_STORAGE_FILENAME) -> None:
    """Remove encrypted storage_state file if present."""
    target = resolve_storage_file(relative_path)
    if target.is_file():
        target.unlink()
        logger.info("Booking extranet storage_state removed.")


def has_storage_state(*, relative_path: str = DEFAULT_STORAGE_FILENAME) -> bool:
    return resolve_storage_file(relative_path).is_file()
