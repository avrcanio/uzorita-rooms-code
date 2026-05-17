from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from icalendar import Calendar, Event

from reception.models import BookingIcalFeed, ImportSource, ReservationStatus, ReservationUnit
from rooms.models import Room

DEFAULT_HORIZON_DAYS = 548  # ~18 months

# Booking already knows its own reservations — export only blocks from other channels.
BOOKING_IMPORT_SOURCES = frozenset(
    {
        ImportSource.BOOKING_XLS,
        ImportSource.BOOKING_EMAIL,
        ImportSource.BOOKING_ICAL,
    }
)


def _merge_consecutive_dates(blocked_days: list[date]) -> list[tuple[date, date]]:
    """Return half-open intervals [start, end) for consecutive blocked days."""
    if not blocked_days:
        return []
    blocked_days = sorted(blocked_days)
    ranges: list[tuple[date, date]] = []
    start = blocked_days[0]
    prev = blocked_days[0]
    for current in blocked_days[1:]:
        if current == prev + timedelta(days=1):
            prev = current
            continue
        ranges.append((start, prev + timedelta(days=1)))
        start = current
        prev = current
    ranges.append((start, prev + timedelta(days=1)))
    return ranges


def blocked_date_ranges_for_feed(
    feed: BookingIcalFeed,
    *,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> list[tuple[date, date]]:
    """
    Days blocked for Booking export: at least min_occupied_units_to_block physical rooms
    of the feed's room type are occupied by non-Booking reservations (direct, other OTAs, manual).
    Reservations imported from Booking (XLS/email) are excluded — Booking already has those dates.
    """
    today = date.today()
    range_start = today - timedelta(days=1)
    range_end = today + timedelta(days=horizon_days)

    room_ids = list(
        Room.objects.filter(room_type_id=feed.room_type_id, is_active=True).values_list("id", flat=True)
    )
    if not room_ids:
        return []

    units = (
        ReservationUnit.objects.filter(room_id__in=room_ids)
        .exclude(reservation__status=ReservationStatus.CANCELED)
        .exclude(reservation__import_source__in=BOOKING_IMPORT_SOURCES)
        .exclude(reservation__details_pending=True)
        .filter(
            reservation__check_in_date__lt=range_end,
            reservation__check_out_date__gt=range_start,
        )
        .select_related("reservation")
    )

    occupancy_by_day: dict[date, set[int]] = defaultdict(set)
    for unit in units:
        if not unit.room_id:
            continue
        d = unit.reservation.check_in_date
        checkout = unit.reservation.check_out_date
        while d < checkout:
            if range_start <= d < range_end:
                occupancy_by_day[d].add(unit.room_id)
            d += timedelta(days=1)

    threshold = max(1, feed.min_occupied_units_to_block)
    blocked_days = [d for d, rooms in sorted(occupancy_by_day.items()) if len(rooms) >= threshold]
    return _merge_consecutive_dates(blocked_days)


def build_export_ics(feed: BookingIcalFeed) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Uzorita//Booking iCal Export//HR")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", f"Uzorita {feed.code.upper()}")

    for block_start, block_end in blocked_date_ranges_for_feed(feed):
        event = Event()
        event.add("uid", f"uzorita-{feed.code}-block-{block_start.isoformat()}-{block_end.isoformat()}@uzorita.hr")
        event.add("dtstart", block_start)
        event.add("dtend", block_end)
        event.add("summary", "Not available")
        event.add("status", "CONFIRMED")
        cal.add_component(event)

    return cal.to_ical()
