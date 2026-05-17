"""Booking extranet connection singleton — status, import, rate limits."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from reception.booking_extranet.outcomes import (
    NEEDS_2FA_MESSAGE,
    NEEDS_2FA_SMS_LIMIT_MESSAGE,
    NEEDS_HUMAN_MESSAGE,
    ConnectOutcome,
    ConnectResult,
)
from reception.booking_extranet.session_store import (
    BookingExtranetSessionError,
    clear_storage_state,
    has_storage_state,
    save_storage_state,
    validate_storage_state,
)
from reception.booking_extranet.vnc import (
    build_vnc_url,
    get_active_vnc,
    get_vnc_token_payload,
    issue_vnc_token,
    refresh_vnc_token_ttl,
)
from reception.models import (
    BookingExtranetConnection,
    BookingExtranetJob,
    BookingExtranetJobStatus,
    BookingExtranetStatus,
)

logger = logging.getLogger(__name__)


def connect_mode() -> str:
    mode = (settings.BOOKING_EXTRANET_CONNECT_MODE or "human_assisted").strip().lower()
    if mode not in {"human_assisted", "automatic"}:
        return "human_assisted"
    return mode


def is_automatic_connect_enabled() -> bool:
    return connect_mode() == "automatic"


def auto_connect_rate_limit_hours() -> int:
    return max(1, int(settings.BOOKING_EXTRANET_AUTO_CONNECT_MIN_HOURS or 24))


def vnc_login_cooldown_hours() -> int:
    return max(1, int(getattr(settings, "BOOKING_EXTRANET_VNC_LOGIN_COOLDOWN_HOURS", 24) or 24))


def is_vnc_connect_enabled() -> bool:
    return bool(
        settings.BOOKING_EXTRANET_ENABLED
        and settings.BOOKING_EXTRANET_VNC_ENABLED
        and settings.BOOKING_EXTRANET_HEADED
    )


def tailscale_exit_node_enabled() -> bool:
    return bool((settings.BOOKING_EXTRANET_TAILSCALE_EXIT_NODE or "").strip())


def can_start_vnc_connect(conn: BookingExtranetConnection | None = None) -> tuple[bool, str]:
    if not is_vnc_connect_enabled():
        return False, "VNC prijava nije omogućena (BOOKING_EXTRANET_VNC_ENABLED / HEADED)."
    conn = conn or BookingExtranetConnection.get_solo()
    if conn.status == BookingExtranetStatus.CONNECTING:
        return False, "Povezivanje je već u tijeku."
    if conn.status == BookingExtranetStatus.CONNECTED:
        return False, "Extranet je već povezan."
    if not is_automatic_connect_enabled() and not tailscale_exit_node_enabled():
        return (
            False,
            "Prijava s servera (VNC) je isključena u human_assisted načinu — "
            "postavite TAILSCALE_EXIT_NODE (laptop exit node) ili uvezite sesiju (JSON).",
        )
    if conn.status == BookingExtranetStatus.NEEDS_2FA:
        return False, NEEDS_2FA_SMS_LIMIT_MESSAGE
    if conn.status == BookingExtranetStatus.NEEDS_HUMAN:
        return False, (
            "CAPTCHA je već otvoren u VNC prozoru ili uvezite sesiju (JSON)."
        )
    if conn.last_connect_at and conn.status == BookingExtranetStatus.ERROR:
        min_interval = timedelta(hours=vnc_login_cooldown_hours())
        elapsed = timezone.now() - conn.last_connect_at
        if elapsed < min_interval:
            remaining = min_interval - elapsed
            hours = max(1, int(remaining.total_seconds() // 3600) + 1)
            return (
                False,
                f"Pričekajte ~{hours}h prije novog pokušaja prijave s servera "
                f"(Booking SMS/CAPTCHA limit). Uvezite sesiju (JSON) ili pričekajte.",
            )
    return True, ""


def can_verify_2fa(conn: BookingExtranetConnection | None = None) -> tuple[bool, str]:
    conn = conn or BookingExtranetConnection.get_solo()
    if conn.status != BookingExtranetStatus.NEEDS_2FA:
        return False, "Veza nije u stanju needs_2fa."
    if not is_automatic_connect_enabled() and not tailscale_exit_node_enabled():
        return (
            False,
            NEEDS_2FA_SMS_LIMIT_MESSAGE,
        )
    return True, ""


def can_start_auto_connect(conn: BookingExtranetConnection | None = None) -> tuple[bool, str]:
    if not settings.BOOKING_EXTRANET_ENABLED:
        return False, "Booking extranet nije omogućen na serveru."
    if not is_automatic_connect_enabled():
        return (
            False,
            "Automatsko povezivanje je isključeno (BOOKING_EXTRANET_CONNECT_MODE=human_assisted). "
            "Koristite VNC prijavu (Tailscale) ili uvezite sesiju (JSON).",
        )
    conn = conn or BookingExtranetConnection.get_solo()
    if conn.status == BookingExtranetStatus.CONNECTING:
        return False, "Povezivanje je već u tijeku."
    if conn.last_connect_at:
        min_interval = timedelta(hours=auto_connect_rate_limit_hours())
        elapsed = timezone.now() - conn.last_connect_at
        if elapsed < min_interval:
            remaining = min_interval - elapsed
            hours = max(1, int(remaining.total_seconds() // 3600) + 1)
            return (
                False,
                f"Automatsko povezivanje je ograničeno na jednom pokušaju u "
                f"{auto_connect_rate_limit_hours()}h. Pokušajte ponovno za ~{hours}h "
                f"ili uvezite sesiju ručno (JSON).",
            )
    return True, ""


def _vnc_fields(conn: BookingExtranetConnection) -> dict[str, Any]:
    vnc_active = False
    vnc_url: str | None = None
    active_job_id: int | None = None

    if not settings.BOOKING_EXTRANET_VNC_ENABLED:
        return {
            "vnc_active": False,
            "vnc_url": None,
            "active_job_id": None,
        }

    active = get_active_vnc()
    if not active or not active.get("token"):
        return {
            "vnc_active": False,
            "vnc_url": None,
            "active_job_id": None,
        }

    token = str(active["token"])
    if not get_vnc_token_payload(token):
        return {
            "vnc_active": False,
            "vnc_url": None,
            "active_job_id": None,
        }

    job_id = active.get("job_id")
    show_vnc = conn.status in (
        BookingExtranetStatus.NEEDS_HUMAN,
        BookingExtranetStatus.CONNECTING,
    )
    if not show_vnc and job_id:
        job = BookingExtranetJob.objects.filter(pk=job_id).first()
        show_vnc = bool(
            job and job.status == BookingExtranetJobStatus.NEEDS_HUMAN
        )

    if show_vnc:
        vnc_active = True
        if not refresh_vnc_token_ttl(token):
            user_id = active.get("user_id")
            if user_id:
                token = issue_vnc_token(user_id=int(user_id), job_id=job_id)
            else:
                return {
                    "vnc_active": False,
                    "vnc_url": None,
                    "active_job_id": None,
                }
        vnc_url = build_vnc_url(token)
        active_job_id = int(job_id) if job_id else None

    return {
        "vnc_active": vnc_active,
        "vnc_url": vnc_url,
        "active_job_id": active_job_id,
    }


def serialize_connection(conn: BookingExtranetConnection) -> dict[str, Any]:
    allowed, rate_reason = can_start_auto_connect(conn)
    vnc_allowed, vnc_reason = can_start_vnc_connect(conn)
    verify_allowed, verify_reason = can_verify_2fa(conn)
    payload = {
        "status": conn.status,
        "hotel_id": conn.hotel_id or settings.BOOKING_EXTRANET_HOTEL_ID or "",
        "storage_version": conn.storage_version,
        "last_ok_at": conn.last_ok_at.isoformat() if conn.last_ok_at else None,
        "last_connect_at": conn.last_connect_at.isoformat() if conn.last_connect_at else None,
        "last_error": conn.last_error or "",
        "connected_by": conn.connected_by.username if conn.connected_by_id else None,
        "updated_at": conn.updated_at.isoformat() if conn.updated_at else None,
        "enabled": settings.BOOKING_EXTRANET_ENABLED,
        "connect_mode": connect_mode(),
        "has_session": has_storage_state(relative_path=conn.storage_path or "state.enc"),
        "auto_connect_allowed": allowed,
        "auto_connect_message": rate_reason,
        "vnc_start_allowed": vnc_allowed,
        "vnc_start_message": vnc_reason,
        "verify_2fa_allowed": verify_allowed,
        "verify_2fa_message": verify_reason,
        "login_url_configured": bool((settings.BOOKING_EXTRANET_LOGIN_URL or "").strip()),
        "vnc_enabled": is_vnc_connect_enabled(),
        "tailscale_exit_node": settings.BOOKING_EXTRANET_TAILSCALE_EXIT_NODE or None,
        "tailscale_exit_node_enabled": tailscale_exit_node_enabled(),
    }
    payload.update(_vnc_fields(conn))
    return payload


def mark_connecting(*, user: User | None = None) -> BookingExtranetConnection:
    conn = BookingExtranetConnection.get_solo()
    conn.status = BookingExtranetStatus.CONNECTING
    conn.last_error = ""
    if user is not None:
        conn.connected_by = user
        if is_vnc_connect_enabled():
            from reception.booking_extranet.vnc import issue_vnc_token

            issue_vnc_token(user_id=user.id)
    conn.save(update_fields=["status", "last_error", "connected_by", "updated_at"])
    return conn


def apply_connect_result(
    result: ConnectResult,
    *,
    user: User | None = None,
    error_message: str = "",
) -> BookingExtranetConnection:
    conn = BookingExtranetConnection.get_solo()
    now = timezone.now()
    conn.last_connect_at = now

    if result.outcome == ConnectOutcome.CONNECTED:
        conn.status = BookingExtranetStatus.CONNECTED
        conn.last_ok_at = now
        conn.last_error = ""
        conn.storage_version = (conn.storage_version or 0) + 1
        if not conn.hotel_id:
            conn.hotel_id = (settings.BOOKING_EXTRANET_HOTEL_ID or "").strip()
    elif result.outcome == ConnectOutcome.NEEDS_2FA:
        conn.status = BookingExtranetStatus.NEEDS_2FA
        conn.last_error = error_message or (
            NEEDS_2FA_SMS_LIMIT_MESSAGE
            if not is_automatic_connect_enabled() and not tailscale_exit_node_enabled()
            else NEEDS_2FA_MESSAGE
        )
    elif result.outcome == ConnectOutcome.NEEDS_HUMAN:
        conn.status = BookingExtranetStatus.NEEDS_HUMAN
        conn.last_error = error_message or NEEDS_HUMAN_MESSAGE
    else:
        conn.status = BookingExtranetStatus.ERROR
        conn.last_error = error_message or "Nepoznat ishod povezivanja."

    if user is not None:
        conn.connected_by = user

    conn.save()
    return conn


def mark_connect_error(message: str, *, user: User | None = None) -> BookingExtranetConnection:
    conn = BookingExtranetConnection.get_solo()
    conn.status = BookingExtranetStatus.ERROR
    conn.last_error = message[:2000]
    conn.last_connect_at = timezone.now()
    if user is not None:
        conn.connected_by = user
    conn.save()
    return conn


def import_storage_state(
    state: dict[str, Any],
    *,
    user: User | None = None,
    hotel_id: str | None = None,
) -> BookingExtranetConnection:
    validated = validate_storage_state(state)
    conn = BookingExtranetConnection.get_solo()
    relative_path = conn.storage_path or "state.enc"
    save_storage_state(validated, relative_path=relative_path)

    now = timezone.now()
    conn.status = BookingExtranetStatus.CONNECTED
    conn.hotel_id = (hotel_id or settings.BOOKING_EXTRANET_HOTEL_ID or conn.hotel_id or "").strip()
    conn.storage_version = (conn.storage_version or 0) + 1
    conn.last_connect_at = now
    conn.last_ok_at = now
    conn.last_error = ""
    if user is not None:
        conn.connected_by = user
    conn.save()
    logger.info("Booking extranet session imported (storage_version=%s)", conn.storage_version)
    return conn


def disconnect_session(*, user: User | None = None) -> BookingExtranetConnection:
    conn = BookingExtranetConnection.get_solo()
    try:
        clear_storage_state(relative_path=conn.storage_path or "state.enc")
    except BookingExtranetSessionError as exc:
        logger.warning("disconnect clear_storage_state: %s", exc)

    conn.status = BookingExtranetStatus.DISCONNECTED
    conn.last_error = ""
    conn.last_ok_at = None
    if user is not None:
        conn.connected_by = user
    conn.save()
    return conn


def apply_health_result(
    outcome: str,
    *,
    detail: str = "",
) -> BookingExtranetConnection:
    conn = BookingExtranetConnection.get_solo()
    now = timezone.now()

    if outcome == "connected":
        conn.status = BookingExtranetStatus.CONNECTED
        conn.last_ok_at = now
        conn.last_error = ""
    elif outcome == "needs_human":
        conn.status = BookingExtranetStatus.NEEDS_HUMAN
        conn.last_error = detail or NEEDS_HUMAN_MESSAGE
    elif outcome in {"expired", "no_session"}:
        conn.status = BookingExtranetStatus.EXPIRED
        conn.last_error = detail or "Sesija je istekla."
    else:
        conn.status = BookingExtranetStatus.ERROR
        conn.last_error = detail or "Health check nije uspio."

    conn.save()
    return conn
