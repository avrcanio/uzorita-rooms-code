from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from reception.models import Guest, ImportSource, Reservation, ReservationStatus
from reception.reservation_units import sync_reservation_units
from rooms.allocation import assign_rooms_for_reservation

@dataclass(frozen=True)
class ImportResult:
    reservation_id: int
    primary_guest_id: int | None


def _should_update_guest_email(current: str | None, new_email: str | None) -> bool:
    if not new_email:
        return False
    current_norm = (current or "").strip().lower()
    new_norm = new_email.strip().lower()
    if not new_norm or current_norm == new_norm:
        return False
    if current_norm.endswith("@guest.booking.com") and not new_norm.endswith("@guest.booking.com"):
        return False
    if new_norm.endswith("@uzorita.hr"):
        return False
    if new_norm.split("@", 1)[0] in {"room_reservations", "reservations", "noreply", "no-reply"}:
        return False
    return True


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
    check_in_date: date,
    check_out_date: date,
    status: str,
    guest_full_name: str | None,
    guest_email: str | None,
    guest_nationality_iso2: str | None = None,
    total_amount,
    currency: str | None,
    import_source: str | None = None,
    sync_units: bool = True,
) -> ImportResult:
    reservation, _created = Reservation.objects.get_or_create(
        external_id=external_id,
        defaults={
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "status": status,
        },
    )

    changed = False
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
    if import_source and reservation.import_source != import_source:
        reservation.import_source = import_source
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
            if _should_update_guest_email(primary.email, guest_email):
                primary.email = guest_email.strip()
                g_changed = True
            if guest_nationality_iso2:
                nat = guest_nationality_iso2.strip().upper()
                if nat and primary.nationality != nat:
                    primary.nationality = nat
                    g_changed = True
            if g_changed:
                primary.save()
        primary_guest_id = primary.id

    sync_reservation_units(reservation=reservation, room_name=room_name)
    assign_rooms_for_reservation(reservation_id=reservation.id)

    return ImportResult(reservation_id=reservation.id, primary_guest_id=primary_guest_id)


def status_from_booking_kind(kind: str) -> str:
    if kind == "cancel":
        return ReservationStatus.CANCELED
    return ReservationStatus.EXPECTED


def _placeholder_stay_dates(
    *,
    check_in_date: date | None,
    check_out_date: date | None,
) -> tuple[date, date]:
    """Minimal valid range until XLS/XML import fills real dates."""
    if check_in_date:
        check_out = check_out_date or (check_in_date + timedelta(days=1))
        if check_out <= check_in_date:
            check_out = check_in_date + timedelta(days=1)
        return (check_in_date, check_out)
    today = timezone.localdate()
    return (today, today + timedelta(days=1))


@transaction.atomic
def upsert_booking_email_stub(
    *,
    external_id: str,
    check_in_date: date | None = None,
    check_out_date: date | None = None,
    status: str | None = None,
    booker_name: str | None = None,
) -> ImportResult:
    """
    Create or refresh a reservation that only has a Booking number (and optional check-in).
    Full details are applied later via XLS/XML import.
    """
    check_in, check_out = _placeholder_stay_dates(
        check_in_date=check_in_date,
        check_out_date=check_out_date,
    )
    operational_status = status or ReservationStatus.EXPECTED

    reservation, created = Reservation.objects.get_or_create(
        external_id=external_id,
        defaults={
            "check_in_date": check_in,
            "check_out_date": check_out,
            "status": operational_status,
            "details_pending": True,
            "import_source": ImportSource.BOOKING_EMAIL,
        },
    )

    if not created and not reservation.details_pending:
        return ImportResult(reservation_id=reservation.id, primary_guest_id=None)

    changed = created
    if reservation.details_pending != True:
        reservation.details_pending = True
        changed = True
    if check_in_date and reservation.check_in_date != check_in:
        reservation.check_in_date = check_in
        changed = True
    if check_out_date and reservation.check_out_date != check_out:
        reservation.check_out_date = check_out
        changed = True
    if reservation.status != operational_status:
        if reservation.status not in (ReservationStatus.CHECKED_IN, ReservationStatus.CHECKED_OUT):
            reservation.status = operational_status
            changed = True
    if booker_name and reservation.booker_name != booker_name:
        reservation.booker_name = booker_name
        changed = True
    if reservation.import_source != ImportSource.BOOKING_EMAIL:
        reservation.import_source = ImportSource.BOOKING_EMAIL
        changed = True
    if changed:
        reservation.save()

    return ImportResult(reservation_id=reservation.id, primary_guest_id=None)
