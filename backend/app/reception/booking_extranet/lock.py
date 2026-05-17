"""Redis lock for Booking extranet Playwright connect (single flight)."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

CONNECT_LOCK_KEY = "booking_extranet:connect"
DEFAULT_LOCK_TTL_SECONDS = 600


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


@contextmanager
def booking_extranet_connect_lock(
    *,
    ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
) -> Iterator[bool]:
    """Yield True if lock acquired; False if another connect is in progress."""
    client = _redis_client()
    acquired = bool(client.set(CONNECT_LOCK_KEY, "1", nx=True, ex=ttl_seconds))
    try:
        yield acquired
    finally:
        if acquired:
            try:
                client.delete(CONNECT_LOCK_KEY)
            except redis.RedisError:
                logger.exception("Failed to release booking extranet connect lock")
