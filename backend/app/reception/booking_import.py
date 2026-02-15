from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction

from reception.models import Guest, Reservation, ReservationStatus
from rooms.allocation import assign_room_for_reservation
from rooms.models import RoomType


@dataclass(frozen=True)
class ImportResult:
    reservation_id: int
    primary_guest_id: int | None


def _split_name(full_name: str | None) -> tuple[str, str]:
    if not full_name:
        return ("", "")
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (" ".join(parts[:-1]), parts[-1])


@transaction.atomic
def upsert_reservation_from_booking_payload(
    *,
    external_id: str,
    room_name: str,
    room_type: RoomType | None,
    check_in_date: date,
    check_out_date: date,
    status: str,
    guest_full_name: str | None,
    guest_email: str | None,
    guest_nationality_iso2: str | None = None,
    preferred_room_code: str | None = None,
    total_amount,
    currency: str | None,
) -> ImportResult:
    reservation, _created = Reservation.objects.get_or_create(
        external_id=external_id,
        defaults={
            "room_name": room_name,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "status": status,
        },
    )

    changed = False
    if reservation.room_name != room_name:
        reservation.room_name = room_name
        changed = True
    if reservation.room_type_id != (room_type.id if room_type else None):
        reservation.room_type = room_type
        changed = True
    if reservation.check_in_date != check_in_date:
        reservation.check_in_date = check_in_date
        changed = True
    if reservation.check_out_date != check_out_date:
        reservation.check_out_date = check_out_date
        changed = True
    if reservation.status != status:
        reservation.status = status
        changed = True
    if total_amount is not None and reservation.total_amount != total_amount:
        reservation.total_amount = total_amount
        changed = True
    if currency and reservation.currency != currency:
        reservation.currency = currency
        changed = True
    if changed:
        reservation.save()

    first_name, last_name = _split_name(guest_full_name)
    primary_guest_id: int | None = None
    if first_name or last_name:
        primary = Guest.objects.filter(reservation=reservation, is_primary=True).first()
        if primary is None:
            primary = Guest.objects.create(
                reservation=reservation,
                first_name=first_name or "-",
                last_name=last_name or "-",
                email=(guest_email or "").strip(),
                nationality=(guest_nationality_iso2 or "").strip().upper(),
                is_primary=True,
            )
        else:
            g_changed = False
            if first_name and primary.first_name != first_name:
                primary.first_name = first_name
                g_changed = True
            if last_name and primary.last_name != last_name:
                primary.last_name = last_name
                g_changed = True
            if guest_email:
                normalized_email = guest_email.strip()
                if normalized_email and primary.email != normalized_email:
                    primary.email = normalized_email
                    g_changed = True
            if guest_nationality_iso2:
                nat = guest_nationality_iso2.strip().upper()
                if nat and primary.nationality != nat:
                    primary.nationality = nat
                    g_changed = True
            if g_changed:
                primary.save()
        primary_guest_id = primary.id

    # Try to assign a physical room unit (K1/K2/D1/T1) based on date range.
    # If a preferred room code was parsed (R1/R2/R3 mapping), prefer that unit.
    assign_room_for_reservation(reservation_id=reservation.id, preferred_room_code=preferred_room_code)

    return ImportResult(reservation_id=reservation.id, primary_guest_id=primary_guest_id)


def status_from_booking_kind(kind: str) -> str:
    if kind == "cancel":
        return ReservationStatus.CANCELED
    return ReservationStatus.EXPECTED
