from __future__ import annotations

from django.db import transaction

from reception.models import Reservation, ReservationStatus
from rooms.models import Room


def _overlaps(*, a_start, a_end, b_start, b_end) -> bool:
    # half-open intervals: [start, end)
    return a_start < b_end and a_end > b_start


@transaction.atomic
def assign_room_for_reservation(*, reservation_id: int, preferred_room_code: str | None = None) -> Room | None:
    reservation = Reservation.objects.select_for_update().get(id=reservation_id)

    if reservation.status == ReservationStatus.CANCELED:
        return reservation.room

    if reservation.check_in_date >= reservation.check_out_date:
        return None

    if preferred_room_code:
        preferred = (
            Room.objects.select_for_update()
            .filter(code=str(preferred_room_code).strip().upper(), is_active=True)
            .first()
        )
        if preferred:
            conflicts = (
                Reservation.objects.filter(room=preferred)
                .exclude(id=reservation.id)
                .exclude(status=ReservationStatus.CANCELED)
                .filter(check_in_date__lt=reservation.check_out_date, check_out_date__gt=reservation.check_in_date)
                .exists()
            )
            if not conflicts:
                reservation.room = preferred
                # Keep room_type consistent with the physical room.
                reservation.room_type = preferred.room_type
                reservation.save(update_fields=["room", "room_type", "updated_at"])
                return preferred
            # Preferred room is not available; try other units of the same room_type (e.g. K1 -> K2).
            for alt in (
                Room.objects.select_for_update()
                .filter(room_type=preferred.room_type, is_active=True)
                .exclude(id=preferred.id)
                .order_by("code")
            ):
                alt_conflicts = (
                    Reservation.objects.filter(room=alt)
                    .exclude(id=reservation.id)
                    .exclude(status=ReservationStatus.CANCELED)
                    .filter(
                        check_in_date__lt=reservation.check_out_date,
                        check_out_date__gt=reservation.check_in_date,
                    )
                    .exists()
                )
                if alt_conflicts:
                    continue
                reservation.room = alt
                reservation.room_type = alt.room_type
                reservation.save(update_fields=["room", "room_type", "updated_at"])
                return alt

    if reservation.room and reservation.room.is_active:
        # Keep existing assignment if it doesn't conflict.
        conflicts = (
            Reservation.objects.filter(room=reservation.room)
            .exclude(id=reservation.id)
            .exclude(status=ReservationStatus.CANCELED)
            .filter(check_in_date__lt=reservation.check_out_date, check_out_date__gt=reservation.check_in_date)
            .exists()
        )
        if not conflicts:
            return reservation.room

    if not reservation.room_type:
        return None

    rooms = list(Room.objects.select_for_update().filter(room_type=reservation.room_type, is_active=True).order_by("code"))
    if not rooms:
        return None

    # Find a free room.
    for room in rooms:
        conflicts = (
            Reservation.objects.filter(room=room)
            .exclude(id=reservation.id)
            .exclude(status=ReservationStatus.CANCELED)
            .filter(check_in_date__lt=reservation.check_out_date, check_out_date__gt=reservation.check_in_date)
            .exists()
        )
        if not conflicts:
            reservation.room = room
            reservation.save(update_fields=["room", "updated_at"])
            return room

    return None
