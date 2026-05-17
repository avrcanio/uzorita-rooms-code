"""Enqueue extranet fetch after email stub ingest."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def enqueue_fetch_after_email_stub(
    *,
    inbound_email_id: int,
    booking_number: str,
    body_html: str = "",
    body_text: str = "",
) -> int | None:
    """
    Create fetch_reservation job when extranet is enabled and session is connected.

    Returns job id or None if skipped.
    """
    if not settings.BOOKING_EXTRANET_ENABLED:
        return None

    from reception.booking_extranet.fetch_reservation import resolve_target_url
    from reception.booking_extranet.job_service import create_job
    from reception.booking_extranet.tasks import booking_extranet_fetch_reservation_task
    from reception.models import (
        BookingExtranetConnection,
        BookingExtranetJobKind,
        BookingExtranetStatus,
    )

    conn = BookingExtranetConnection.get_solo()
    if conn.status != BookingExtranetStatus.CONNECTED:
        return None

    target_url = resolve_target_url(
        booking_number=booking_number,
        email_html=body_html,
        email_text=body_text,
    )
    if not target_url:
        logger.info("enqueue_fetch_after_email_stub: no target URL for %s", booking_number)
        return None

    job = create_job(
        kind=BookingExtranetJobKind.FETCH_RESERVATION,
        booking_number=booking_number,
        target_url=target_url,
        inbound_email_id=inbound_email_id,
    )
    async_result = booking_extranet_fetch_reservation_task.delay(job_id=job.id)
    job.celery_task_id = async_result.id
    job.save(update_fields=["celery_task_id", "updated_at"])
    logger.info(
        "Enqueued booking extranet fetch job=%s for booking=%s",
        job.id,
        booking_number,
    )
    return job.id
