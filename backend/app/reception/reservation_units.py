from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from reception.models import Reservation, ReservationUnit
from rooms.services import canonical_room_info, preferred_room_code_from_parsed_room_name


@dataclass(frozen=True)
class UnitSpec:
    room_name: str
    room_type_id: int | None
    sort_order: int


def split_unit_amounts(total_amount: Decimal, unit_count: int) -> list[Decimal]:
    """Split booking total evenly; remainder cents go to the last unit."""
    if unit_count <= 0:
        return []
    base = (total_amount / unit_count).quantize(Decimal("0.01"))
    amounts = [base] * unit_count
    remainder = total_amount - sum(amounts)
    if remainder:
        amounts[-1] = (amounts[-1] + remainder).quantize(Decimal("0.01"))
    return amounts


def apply_unit_amounts_from_total(
    *,
    reservation: Reservation,
    total_amount: Decimal | None,
    units: list[ReservationUnit] | None = None,
) -> None:
    unit_list = units if units is not None else list(reservation.units.order_by("sort_order", "id"))
    if not unit_list or total_amount is None:
        return
    for unit, amount in zip(unit_list, split_unit_amounts(total_amount, len(unit_list))):
        if unit.amount != amount:
            unit.amount = amount
            unit.save(update_fields=["amount", "updated_at"])


def split_room_names(room_name: str) -> list[str]:
    if not room_name:
        return []
    return [part.strip() for part in room_name.split(",") if part.strip()]


def build_unit_specs(room_name: str) -> list[UnitSpec]:
    segments = split_room_names(room_name)
    if not segments:
        return []
    specs: list[UnitSpec] = []
    for idx, segment in enumerate(segments):
        room_type, canonical = canonical_room_info(
            parsed_room_name=segment,
            fallback_room_name=room_name,
        )
        specs.append(
            UnitSpec(
                room_name=canonical or segment,
                room_type_id=room_type.id if room_type else None,
                sort_order=idx,
            )
        )
    return specs


def sync_reservation_units(*, reservation: Reservation, room_name: str) -> list[ReservationUnit]:
    specs = build_unit_specs(room_name)
    if not specs:
        return []

    existing = {u.sort_order: u for u in reservation.units.all()}
    kept_ids: list[int] = []

    for spec in specs:
        unit = existing.get(spec.sort_order)
        if unit is None:
            unit = ReservationUnit.objects.create(
                reservation=reservation,
                sort_order=spec.sort_order,
                room_name=spec.room_name,
                room_type_id=spec.room_type_id,
            )
        else:
            changed = False
            if unit.room_name != spec.room_name:
                unit.room_name = spec.room_name
                changed = True
            if spec.room_type_id is not None and unit.room_type_id != spec.room_type_id:
                unit.room_type_id = spec.room_type_id
                changed = True
            if changed:
                unit.save(update_fields=["room_name", "room_type", "updated_at"])
        kept_ids.append(unit.id)

    reservation.units.exclude(id__in=kept_ids).delete()
    units = list(reservation.units.order_by("sort_order", "id"))
    sync_reservation_denormalized_room_name(reservation, units=units)
    return units


def unit_specs_snapshot(reservation: Reservation) -> tuple[tuple[int, str, int | None], ...]:
    return tuple(
        (u.sort_order, u.room_name, u.room_type_id)
        for u in reservation.units.order_by("sort_order", "id")
    )


def unit_specs_from_room_name(room_name: str) -> tuple[tuple[int, str, int | None], ...]:
    return tuple(
        (spec.sort_order, spec.room_name, spec.room_type_id)
        for spec in build_unit_specs(room_name)
    )


def sync_reservation_denormalized_room_name(
    reservation: Reservation,
    *,
    units: list[ReservationUnit] | None = None,
) -> None:
    unit_list = units if units is not None else list(reservation.units.order_by("sort_order", "id"))
    if not unit_list:
        return
    joined = ", ".join(u.room_name for u in unit_list)
    if reservation.room_name != joined:
        reservation.room_name = joined
        reservation.save(update_fields=["room_name", "updated_at"])


def preferred_codes_for_units(reservation: Reservation) -> list[str | None]:
    codes: list[str | None] = []
    for unit in reservation.units.order_by("sort_order", "id"):
        codes.append(preferred_room_code_from_parsed_room_name(unit.room_name))
    return codes
