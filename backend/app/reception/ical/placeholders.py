"""iCal feed events without a Booking reservation number (opaque UID → ical-… external_id)."""

from __future__ import annotations

import re

from django.db.models import QuerySet

from reception.models import ImportSource, Reservation

BOOKING_NUMBER_RE = re.compile(r"\d{8,12}")


def is_ical_placeholder_external_id(external_id: str) -> bool:
    """True for legacy/sync-skipped opaque imports (not a numeric Booking id)."""
    value = (external_id or "").strip()
    if not value.lower().startswith("ical-"):
        return False
    return BOOKING_NUMBER_RE.fullmatch(value) is None


def exclude_ical_placeholder_reservations(qs: QuerySet[Reservation]) -> QuerySet[Reservation]:
    """Drop iCal availability-style rows; keep XLS/email and iCal rows with Booking numbers."""
    return qs.exclude(
        import_source=ImportSource.BOOKING_ICAL,
        external_id__startswith="ical-",
    )
