"""BookingExtranetJob helpers and upsert from scrape payload."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth.models import User
from django.db import transaction
from django.utils.dateparse import parse_date

from reception.booking_import import upsert_reservation_from_booking_payload
from reception.models import (
    BookingExtranetJob,
    BookingExtranetJobKind,
    BookingExtranetJobStatus,
    ImportSource,
    ReservationStatus,
)


def create_job(
    *,
    kind: str,
    booking_number: str = "",
    target_url: str = "",
    inbound_email_id: int | None = None,
    user: User | None = None,
    celery_task_id: str = "",
) -> BookingExtranetJob:
    return BookingExtranetJob.objects.create(
        kind=kind,
        status=BookingExtranetJobStatus.PENDING,
        booking_number=booking_number or "",
        target_url=target_url or "",
        inbound_email_id=inbound_email_id,
        created_by=user,
        celery_task_id=celery_task_id or "",
    )


def set_job_status(
    job: BookingExtranetJob,
    status: str,
    *,
    error: str = "",
    result_payload: dict | None = None,
) -> BookingExtranetJob:
    job.status = status
    if error:
        job.error = error[:2000]
    if result_payload is not None:
        job.result_payload = result_payload
    job.save()
    return job


@transaction.atomic
def upsert_reservation_from_fetch_payload(payload: dict[str, Any]) -> int:
    booking_number = (payload.get("booking_number") or "").strip()
    if not booking_number:
        raise ValueError("booking_number missing from fetch payload")

    check_in = parse_date((payload.get("check_in_date") or "").strip() or "")
    check_out = parse_date((payload.get("check_out_date") or "").strip() or "")
    if not check_in or not check_out:
        raise ValueError("check_in_date and check_out_date required from fetch")

    amount_raw = payload.get("total_amount")
    amount = None
    if amount_raw:
        try:
            amount = Decimal(str(amount_raw))
        except InvalidOperation:
            amount = None

    result = upsert_reservation_from_booking_payload(
        external_id=booking_number,
        room_name=(payload.get("room_name") or "Unknown").strip() or "Unknown",
        check_in_date=check_in,
        check_out_date=check_out,
        status=ReservationStatus.EXPECTED,
        guest_full_name=(payload.get("guest_name") or "").strip() or None,
        guest_email=None,
        total_amount=amount,
        currency=(payload.get("currency") or "EUR").strip() or "EUR",
        import_source=ImportSource.BOOKING_EMAIL,
    )

    from reception.models import Reservation

    Reservation.objects.filter(pk=result.reservation_id).update(details_pending=False)
    return result.reservation_id
