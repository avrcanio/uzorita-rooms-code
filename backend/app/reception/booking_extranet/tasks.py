from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

from reception.booking_extranet.connection_service import (
    apply_connect_result,
    apply_health_result,
    mark_connect_error,
    serialize_connection,
)
from reception.models import BookingExtranetConnection

logger = logging.getLogger(__name__)
User = get_user_model()

_HUMAN_WAIT_S = 900


def _user(user_id: int | None):
    if not user_id:
        return None
    return User.objects.filter(pk=user_id).first()


def _use_headed() -> bool:
    return bool(settings.BOOKING_EXTRANET_HEADED and settings.BOOKING_EXTRANET_VNC_ENABLED)


def _headed_connect(user, relative_path: str):
    from reception.booking_extranet.browser_session import (
        detect_needs_human,
        get_page,
        open_headed_context,
        save_context_state,
        wait_until_not_human,
    )
    from reception.booking_extranet.connect import run_connect_on_page
    from reception.booking_extranet.outcomes import ConnectOutcome, ConnectResult
    from reception.booking_extranet.urls import is_connected_url
    from reception.booking_extranet.vnc import clear_active_vnc, issue_vnc_token

    if user is not None:
        issue_vnc_token(user_id=user.id)

    open_headed_context(storage_relative_path=relative_path)
    page = get_page()
    if is_connected_url(page.url or ""):
        save_context_state(relative_path=relative_path)
        clear_active_vnc()
        apply_connect_result(
            ConnectResult(
                outcome=ConnectOutcome.CONNECTED,
                storage_relative_path=relative_path,
            ),
            user=user,
        )
        return

    result = run_connect_on_page(page, storage_relative_path=relative_path)

    if result.outcome == ConnectOutcome.NEEDS_HUMAN:
        if user is not None:
            issue_vnc_token(user_id=user.id)
        apply_connect_result(result, user=user)
        # Ne blokiraj worker 15 min — operator rješava u VNC, zatim POST vnc/continue.
        return

    if result.outcome == ConnectOutcome.CONNECTED:
        save_context_state(relative_path=relative_path)
        clear_active_vnc()

    apply_connect_result(result, user=user)


def _headed_vnc_continue(user, relative_path: str) -> None:
    """After operator solves CAPTCHA in VNC, verify page and save session on worker."""
    from reception.booking_extranet.browser_session import (
        detect_needs_human,
        get_page,
        open_headed_context,
        save_context_state,
        wait_until_not_human,
    )
    from reception.booking_extranet.outcomes import ConnectOutcome, ConnectResult
    from reception.booking_extranet.urls import is_connected_url
    from reception.booking_extranet.vnc import clear_active_vnc
    from reception.models import BookingExtranetJob, BookingExtranetJobStatus, BookingExtranetStatus

    open_headed_context(storage_relative_path=relative_path)
    page = get_page()
    page_url = page.url or ""

    if is_connected_url(page_url):
        save_context_state(relative_path=relative_path)
        clear_active_vnc()
        apply_connect_result(
            ConnectResult(
                outcome=ConnectOutcome.CONNECTED,
                storage_relative_path=relative_path,
            ),
            user=user,
        )
        return

    resolved = wait_until_not_human(
        page,
        timeout_s=30,
        is_resolved=lambda p: is_connected_url(p.url or "") or not detect_needs_human(p),
    )

    if resolved and is_connected_url(page.url or ""):
        save_context_state(relative_path=relative_path)
        clear_active_vnc()
        apply_connect_result(
            ConnectResult(
                outcome=ConnectOutcome.CONNECTED,
                storage_relative_path=relative_path,
            ),
            user=user,
        )
        return

    conn = BookingExtranetConnection.get_solo()
    if conn.status in (
        BookingExtranetStatus.NEEDS_HUMAN,
        BookingExtranetStatus.CONNECTING,
        BookingExtranetStatus.EXPIRED,
        BookingExtranetStatus.ERROR,
        BookingExtranetStatus.DISCONNECTED,
    ):
        mark_connect_error(
            "Extranet nije prepoznat u VNC prozoru — prijavite se ili riješite CAPTCHA, zatim Nastavi.",
            user=user,
        )

    active_job = (
        BookingExtranetJob.objects.filter(status=BookingExtranetJobStatus.NEEDS_HUMAN)
        .order_by("-created_at")
        .first()
    )
    if active_job:
        booking_extranet_fetch_reservation_task.delay(
            job_id=active_job.id,
            user_id=user.id if user else None,
        )


def _headed_health(relative_path: str):
    from reception.booking_extranet.health import HealthOutcome, run_session_health_check
    from reception.booking_extranet.vnc import issue_vnc_token

    health = run_session_health_check(
        relative_path=relative_path,
        headless=False,
        wait_for_human=True,
    )
    if health.outcome == HealthOutcome.NEEDS_HUMAN:
        conn = BookingExtranetConnection.get_solo()
        if conn.connected_by_id:
            issue_vnc_token(user_id=conn.connected_by_id)
    return health


@shared_task(bind=True, name="reception.booking_extranet.tasks.booking_extranet_vnc_continue_task")
def booking_extranet_vnc_continue_task(self, *, user_id: int | None = None) -> dict:
    from reception.booking_extranet.errors import BookingExtranetConnectError
    from reception.booking_extranet.lock import booking_extranet_connect_lock

    user = _user(user_id)
    conn = BookingExtranetConnection.get_solo()
    relative_path = conn.storage_path or "state.enc"

    with booking_extranet_connect_lock(ttl_seconds=120) as acquired:
        if not acquired:
            mark_connect_error("Drugi Playwright zadatak je u tijeku.", user=user)
            return {
                "error": "Drugi Playwright zadatak je u tijeku.",
                "connection": serialize_connection(BookingExtranetConnection.get_solo()),
            }

        try:
            if _use_headed():
                _headed_vnc_continue(user, relative_path)
            else:
                raise BookingExtranetConnectError(
                    "VNC nastavi zahtijeva BOOKING_EXTRANET_HEADED i VNC_ENABLED."
                )
        except BookingExtranetConnectError as exc:
            mark_connect_error(str(exc), user=user)
            return {
                "error": str(exc),
                "connection": serialize_connection(BookingExtranetConnection.get_solo()),
            }
        except Exception as exc:
            logger.exception("booking_extranet_vnc_continue failed")
            mark_connect_error(str(exc), user=user)
            return {
                "error": str(exc),
                "connection": serialize_connection(BookingExtranetConnection.get_solo()),
            }

    conn = BookingExtranetConnection.get_solo()
    return {"connection": serialize_connection(conn)}


@shared_task(bind=True, name="reception.booking_extranet.tasks.booking_extranet_start_connect_task")
def booking_extranet_start_connect_task(self, *, user_id: int | None = None) -> dict:
    from reception.booking_extranet.connect import run_connect
    from reception.booking_extranet.errors import BookingExtranetConnectError
    from reception.booking_extranet.lock import booking_extranet_connect_lock

    user = _user(user_id)
    conn = BookingExtranetConnection.get_solo()
    relative_path = conn.storage_path or "state.enc"

    with booking_extranet_connect_lock(ttl_seconds=180) as acquired:
        if not acquired:
            mark_connect_error(
                "Drugi pokušaj povezivanja je u tijeku. Pričekajte ili uvezite sesiju ručno.",
                user=user,
            )
            return {
                "status": "busy",
                "connection": serialize_connection(BookingExtranetConnection.get_solo()),
            }

        try:
            if _use_headed():
                _headed_connect(user, relative_path)
            else:
                result = run_connect(headless=True, storage_relative_path=relative_path)
                apply_connect_result(result, user=user)
        except BookingExtranetConnectError as exc:
            logger.warning("booking_extranet_start_connect: %s", exc)
            mark_connect_error(str(exc), user=user)
        except Exception as exc:
            logger.exception("booking_extranet_start_connect failed")
            mark_connect_error(str(exc), user=user)
            raise

    conn = BookingExtranetConnection.get_solo()
    return {"status": conn.status, "connection": serialize_connection(conn)}


@shared_task(bind=True, name="reception.booking_extranet.tasks.booking_extranet_verify_2fa_task")
def booking_extranet_verify_2fa_task(
    self,
    *,
    code: str,
    user_id: int | None = None,
) -> dict:
    from reception.booking_extranet.browser_session import (
        get_page,
        open_headed_context,
        save_context_state,
    )
    from reception.booking_extranet.connect import run_verify_2fa, run_verify_2fa_on_page
    from reception.booking_extranet.errors import BookingExtranetConnectError
    from reception.booking_extranet.lock import booking_extranet_connect_lock
    from reception.booking_extranet.vnc import clear_active_vnc

    user = _user(user_id)
    conn = BookingExtranetConnection.get_solo()
    relative_path = conn.storage_path or "state.enc"

    with booking_extranet_connect_lock(ttl_seconds=_HUMAN_WAIT_S + 120) as acquired:
        if not acquired:
            mark_connect_error("Drugi Playwright zadatak je u tijeku.", user=user)
            return {
                "status": "busy",
                "connection": serialize_connection(BookingExtranetConnection.get_solo()),
            }

        try:
            if _use_headed():
                open_headed_context(storage_relative_path=relative_path)
                page = get_page()
                result = run_verify_2fa_on_page(
                    page, code, storage_relative_path=relative_path
                )
                from reception.booking_extranet.outcomes import ConnectOutcome

                if result.outcome == ConnectOutcome.CONNECTED:
                    save_context_state(relative_path=relative_path)
                    clear_active_vnc()
                apply_connect_result(result, user=user)
            else:
                result = run_verify_2fa(code, headless=True, storage_relative_path=relative_path)
                apply_connect_result(result, user=user)
        except BookingExtranetConnectError as exc:
            mark_connect_error(str(exc), user=user)
        except Exception:
            logger.exception("booking_extranet_verify_2fa failed")
            raise

    conn = BookingExtranetConnection.get_solo()
    return {"status": conn.status, "connection": serialize_connection(conn)}


@shared_task(
    bind=True,
    name="reception.booking_extranet.tasks.check_booking_extranet_session_task",
)
def check_booking_extranet_session_task(self) -> dict:
    from reception.booking_extranet.health import HealthOutcome, run_session_health_check

    conn = BookingExtranetConnection.get_solo()
    relative_path = conn.storage_path or "state.enc"

    if _use_headed():
        health = _headed_health(relative_path)
    else:
        health = run_session_health_check(relative_path=relative_path, headless=True)

    outcome_map = {
        HealthOutcome.CONNECTED: "connected",
        HealthOutcome.EXPIRED: "expired",
        HealthOutcome.NO_SESSION: "no_session",
        HealthOutcome.NEEDS_HUMAN: "needs_human",
        HealthOutcome.ERROR: "error",
    }
    apply_health_result(outcome_map[health.outcome], detail=health.detail)
    conn = BookingExtranetConnection.get_solo()
    return {
        "health": health.outcome.value,
        "detail": health.detail,
        "connection": serialize_connection(conn),
    }


@shared_task(
    bind=True,
    name="reception.booking_extranet.tasks.booking_extranet_fetch_reservation_task",
)
def booking_extranet_fetch_reservation_task(
    self,
    *,
    job_id: int,
    user_id: int | None = None,
) -> dict:
    from reception.booking_extranet.browser_session import save_context_state
    from reception.booking_extranet.fetch_reservation import FetchOutcome, run_fetch_reservation
    from reception.booking_extranet.job_service import set_job_status, upsert_reservation_from_fetch_payload
    from reception.booking_extranet.lock import booking_extranet_connect_lock
    from reception.booking_extranet.vnc import clear_active_vnc, issue_vnc_token
    from reception.models import BookingExtranetJob, BookingExtranetJobStatus

    user = _user(user_id)
    job = BookingExtranetJob.objects.get(pk=job_id)
    conn = BookingExtranetConnection.get_solo()
    relative_path = conn.storage_path or "state.enc"

    with booking_extranet_connect_lock(ttl_seconds=_HUMAN_WAIT_S + 120) as acquired:
        if not acquired:
            set_job_status(
                job,
                BookingExtranetJobStatus.FAILED,
                error="Drugi Playwright zadatak je u tijeku.",
            )
            return {"job_id": job_id, "status": job.status, "error": job.error}

        set_job_status(job, BookingExtranetJobStatus.RUNNING)
        try:
            result = run_fetch_reservation(
                target_url=job.target_url,
                storage_relative_path=relative_path,
                wait_for_human=_use_headed(),
            )

            if result.outcome == FetchOutcome.NEEDS_HUMAN:
                if user is not None:
                    issue_vnc_token(user_id=user.id, job_id=job.id)
                set_job_status(
                    job,
                    BookingExtranetJobStatus.NEEDS_HUMAN,
                    error=result.error or "CAPTCHA / WAF — riješite u VNC iframeu.",
                )
                apply_health_result("needs_human", detail=job.error)
                return {
                    "job_id": job_id,
                    "status": job.status,
                    "connection": serialize_connection(BookingExtranetConnection.get_solo()),
                }

            if result.outcome == FetchOutcome.NO_SESSION:
                set_job_status(job, BookingExtranetJobStatus.FAILED, error=result.error)
                return {"job_id": job_id, "status": job.status, "error": job.error}

            if result.outcome != FetchOutcome.DONE or not result.payload:
                set_job_status(
                    job,
                    BookingExtranetJobStatus.FAILED,
                    error=result.error or "Dohvat nije uspio.",
                )
                return {"job_id": job_id, "status": job.status, "error": job.error}

            if _use_headed():
                save_context_state(relative_path=relative_path)
                clear_active_vnc()

            reservation_id = upsert_reservation_from_fetch_payload(result.payload)
            set_job_status(
                job,
                BookingExtranetJobStatus.DONE,
                result_payload={**result.payload, "reservation_id": reservation_id},
            )
            apply_health_result("connected")
        except Exception as exc:
            logger.exception("booking_extranet_fetch_reservation failed")
            set_job_status(job, BookingExtranetJobStatus.FAILED, error=str(exc))
            raise

    job.refresh_from_db()
    return {
        "job_id": job_id,
        "status": job.status,
        "result": job.result_payload,
        "connection": serialize_connection(BookingExtranetConnection.get_solo()),
    }
