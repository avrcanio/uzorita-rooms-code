from __future__ import annotations

import logging

from celery import shared_task
from django.core.management import call_command

from communications.guest_messaging import deliver_outbound_guest_email, record_outbound_send_failure

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
)
def run_booking_email_pipeline_task(self, *, fetch_limit: int = 50, process_limit: int = 50) -> dict:
    """Fetch Booking.com IMAP messages and process pending rows into reservations."""
    logger.info("booking-email-pipeline: fetch_booking_emails (limit=%s)", fetch_limit)
    call_command("fetch_booking_emails", limit=fetch_limit, mark_seen=True)

    logger.info("booking-email-pipeline: process_booking_emails (limit=%s)", process_limit)
    call_command("process_booking_emails", limit=process_limit, only_pending=True)

    logger.info("booking-email-pipeline: process_inbound_guest_messages (limit=%s)", process_limit)
    call_command("process_inbound_guest_messages", limit=process_limit)

    return {"status": "ok", "fetch_limit": fetch_limit, "process_limit": process_limit}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
)
def send_guest_email_task(self, outbound_email_id: int) -> dict:
    """Send a queued OutboundEmail to the guest via SMTP."""
    try:
        deliver_outbound_guest_email(outbound_email_id)
    except Exception as exc:
        final = self.request.retries >= self.max_retries
        record_outbound_send_failure(
            outbound_email_id,
            str(exc),
            final=final,
        )
        logger.warning(
            "send_guest_email_task failed outbound_id=%s retries=%s final=%s",
            outbound_email_id,
            self.request.retries,
            final,
        )
        raise

    return {"status": "sent", "outbound_email_id": outbound_email_id}
