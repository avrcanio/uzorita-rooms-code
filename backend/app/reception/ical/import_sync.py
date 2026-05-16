from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx
from django.utils import timezone
from icalendar import Calendar

from reception.booking_import import upsert_reservation_from_booking_payload
from reception.ical.placeholders import is_ical_placeholder_external_id
from reception.models import BookingIcalFeed, ImportSource, ReservationStatus

BOOKING_NUMBER_RE = re.compile(r"\d{8,12}")
UID_SAFE_RE = re.compile(r"[^a-zA-Z0-9_-]+")


@dataclass
class ImportSyncResult:
    feed_code: str
    status: str
    events_seen: int = 0
    skipped_blocks: int = 0
    upserted: int = 0
    canceled: int = 0
    errors: list[str] | None = None


def is_availability_block(summary: str) -> bool:
    """Booking export marks unavailable dates as CLOSED, not guest reservations."""
    s = (summary or "").strip().lower()
    if not s:
        return False
    if "closed" in s and "not available" in s:
        return True
    return s in {"closed", "not available", "blocked", "unavailable"}


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, "dt"):
        dt = value.dt
        if isinstance(dt, datetime):
            return dt.date()
        if isinstance(dt, date):
            return dt
    return None


def extract_external_id(*, uid: str, summary: str, description: str) -> str:
    for text in (uid, description, summary):
        if not text:
            continue
        match = BOOKING_NUMBER_RE.search(str(text))
        if match:
            return match.group(0)
    safe = UID_SAFE_RE.sub("-", str(uid or "event")).strip("-")[:100] or "event"
    return f"ical-{safe}"


def _event_text(component: Any, key: str) -> str:
    raw = component.get(key)
    if raw is None:
        return ""
    return str(raw.to_ical(), "utf-8") if hasattr(raw, "to_ical") else str(raw)


def _parse_events(ics_body: bytes) -> list[dict[str, Any]]:
    cal = Calendar.from_ical(ics_body)
    events: list[dict[str, Any]] = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        check_in = _to_date(component.get("dtstart"))
        check_out = _to_date(component.get("dtend"))
        if not check_in or not check_out or check_in >= check_out:
            continue
        uid = _event_text(component, "uid")
        summary = _event_text(component, "summary")
        description = _event_text(component, "description")
        status_raw = _event_text(component, "status").upper()
        events.append(
            {
                "uid": uid,
                "check_in": check_in,
                "check_out": check_out,
                "summary": summary,
                "description": description,
                "canceled": status_raw == "CANCELLED",
            }
        )
    return events


def sync_feed(feed: BookingIcalFeed, *, dry_run: bool = False) -> ImportSyncResult:
    if not feed.is_active:
        return ImportSyncResult(feed_code=feed.code, status="inactive")
    if not (feed.import_url or "").strip():
        return ImportSyncResult(feed_code=feed.code, status="no_import_url")

    headers: dict[str, str] = {}
    if feed.last_import_etag:
        headers["If-None-Match"] = feed.last_import_etag

    try:
        response = httpx.get(
            feed.import_url.strip(),
            headers=headers,
            follow_redirects=True,
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        return ImportSyncResult(feed_code=feed.code, status="fetch_error", errors=[str(exc)])

    if response.status_code == 304:
        return ImportSyncResult(feed_code=feed.code, status="not_modified")

    if response.status_code >= 400:
        return ImportSyncResult(
            feed_code=feed.code,
            status="fetch_error",
            errors=[f"HTTP {response.status_code}"],
        )

    etag = response.headers.get("ETag", "").strip()
    if not dry_run:
        feed.last_import_at = timezone.now()
        if etag:
            feed.last_import_etag = etag
        feed.save(update_fields=["last_import_at", "last_import_etag", "updated_at"])

    events = _parse_events(response.content)
    upserted = 0
    skipped_blocks = 0
    canceled = 0
    errors: list[str] = []

    for ev in events:
        if is_availability_block(ev["summary"]):
            skipped_blocks += 1
            continue

        external_id = extract_external_id(
            uid=ev["uid"],
            summary=ev["summary"],
            description=ev["description"],
        )
        if is_ical_placeholder_external_id(external_id):
            skipped_blocks += 1
            continue

        status = ReservationStatus.CANCELED if ev["canceled"] else ReservationStatus.EXPECTED
        guest_name = (ev["summary"] or "").strip() or None

        if dry_run:
            if status == ReservationStatus.CANCELED:
                canceled += 1
            else:
                upserted += 1
            continue

        try:
            upsert_reservation_from_booking_payload(
                external_id=external_id,
                room_name=feed.booking_listing_name,
                check_in_date=ev["check_in"],
                check_out_date=ev["check_out"],
                status=status,
                guest_full_name=guest_name,
                guest_email=None,
                total_amount=None,
                currency=None,
                import_source=ImportSource.BOOKING_ICAL,
            )
            if status == ReservationStatus.CANCELED:
                canceled += 1
            else:
                upserted += 1
        except Exception as exc:
            errors.append(f"{external_id}: {exc}")

    return ImportSyncResult(
        feed_code=feed.code,
        status="ok" if not errors else "partial",
        events_seen=len(events),
        skipped_blocks=skipped_blocks,
        upserted=upserted,
        canceled=canceled,
        errors=errors or None,
    )
