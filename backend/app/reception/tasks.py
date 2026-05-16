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
def sync_booking_ical_task(self, *, feed: str = "all") -> dict:
    """Pull Booking.com iCal export URLs and sync configured feeds."""
    logger.info("sync_booking_ical: feed=%s", feed)
    call_command("sync_booking_ical", feed=feed)
    return {"status": "ok", "feed": feed}
