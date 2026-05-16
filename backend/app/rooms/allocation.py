from __future__ import annotations

from django.db import transaction

from reception.models import Reservation, ReservationStatus, ReservationUnit
from rooms.models import Room
from rooms.services import preferred_room_code_from_parsed_room_name


def _room_is_booked(
    *,
    room: Room,
    reservation_id: int,
    check_in_date,
    check_out_date,
) -> bool:
    return (
        ReservationUnit.objects.filter(room=room)
        .exclude(reservation_id=reservation_id)
        .exclude(reservation__status=ReservationStatus.CANCELED)
        .filter(
            reservation__check_in_date__lt=check_out_date,
            reservation__check_out_date__gt=check_in_date,
        )
        .exists()
    )


@transaction.atomic
def assign_room_for_unit(
    *,
    unit: ReservationUnit,
    preferred_room_code: str | None = None,
) -> Room | None:
    reservation = unit.reservation
    if reservation.status == ReservationStatus.CANCELED:
        return unit.room
    if reservation.check_in_date >= reservation.check_out_date:
        return None

    preferred_room_code = preferred_room_code or preferred_room_code_from_parsed_room_name(unit.room_name)

    if preferred_room_code:
        preferred = (
            Room.objects.select_for_update()
            .filter(code=str(preferred_room_code).strip().upper(), is_active=True)
            .first()
        )
        if preferred:
            if not _room_is_booked(
                room=preferred,
                reservation_id=reservation.id,
                check_in_date=reservation.check_in_date,
                check_out_date=reservation.check_out_date,
            ):
                unit.room = preferred
                unit.room_type = preferred.room_type
                unit.save(update_fields=["room", "room_type", "updated_at"])
                return preferred
            for alt in (
                Room.objects.select_for_update()
                .filter(room_type=preferred.room_type, is_active=True)
                .exclude(id=preferred.id)
                .order_by("code")
            ):
                if not _room_is_booked(
                    room=alt,
                    reservation_id=reservation.id,
                    check_in_date=reservation.check_in_date,
                    check_out_date=reservation.check_out_date,
                ):
                    unit.room = alt
                    unit.room_type = alt.room_type
                    unit.save(update_fields=["room", "room_type", "updated_at"])
                    return alt

    if unit.room and unit.room.is_active:
        if not _room_is_booked(
            room=unit.room,
            reservation_id=reservation.id,
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
        ):
            return unit.room

    room_type = unit.room_type
    if not room_type:
        return None

    for room in Room.objects.select_for_update().filter(room_type=room_type, is_active=True).order_by("code"):
        if not _room_is_booked(
            room=room,
            reservation_id=reservation.id,
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
        ):
            unit.room = room
            unit.save(update_fields=["room", "updated_at"])
            return room

    return None


@transaction.atomic
def assign_rooms_for_reservation(*, reservation_id: int) -> list[Room | None]:
    reservation = Reservation.objects.select_for_update().prefetch_related("units").get(id=reservation_id)

    units = list(reservation.units.order_by("sort_order", "id"))
    if not units:
        return []

    assigned: list[Room | None] = []
    for unit in units:
        preferred = preferred_room_code_from_parsed_room_name(unit.room_name)
        assigned.append(assign_room_for_unit(unit=unit, preferred_room_code=preferred))

    return assigned


@transaction.atomic
def assign_room_for_reservation(*, reservation_id: int, preferred_room_code: str | None = None) -> Room | None:
    """Assign physical rooms via ReservationUnit rows."""
    assigned = assign_rooms_for_reservation(reservation_id=reservation_id)
    if not assigned:
        return None
    if preferred_room_code and len(assigned) == 1:
        return assigned[0]
    return assigned[0]
