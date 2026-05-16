from __future__ import annotations

import logging

from celery import shared_task
from django.core.management import call_command

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

    return {"status": "ok", "fetch_limit": fetch_limit, "process_limit": process_limit}
