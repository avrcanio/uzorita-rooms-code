from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

from rooms.models import Room, RoomType, RoomTypePricingPlan


def preferred_room_code_from_parsed_room_name(text: str | None) -> str | None:
    """
    Rentlio / Booking forwarded templates often use "R1/R2/R3..." room numbers.
    In Uzorita these map to physical room units:
      R1 -> K1
      R2 -> K2
      R3 -> T1
    """
    if not text:
        return None
    m = re.search(r"\bR\s*-?\s*(\d+)\b", text, re.I)
    if not m:
        return None
    n = m.group(1)
    if n == "1":
        return "K1"
    if n == "2":
        return "K2"
    if n == "3":
        return "T1"
    return None


def resolve_room_type_from_text(text: str | None) -> RoomType | None:
    if not text:
        return None
    raw = text.strip()
    if not raw:
        return None

    # NOTE: R1/R2/R3 in emails are "room numbers", not stable room-type codes.
    # We match room types only via aliases below.

    lowered = raw.lower()
    # Alias match (exact-ish) across active room types.
    for rt in RoomType.objects.filter(is_active=True).order_by("code"):
        for alias in (rt.match_aliases or []):
            a = str(alias or "").strip().lower()
            if not a:
                continue
            if a in lowered:
                return rt

    return None


def canonical_room_info(*, parsed_room_name: str | None, fallback_room_name: str | None) -> tuple[RoomType | None, str]:
    rt = resolve_room_type_from_text(parsed_room_name) or resolve_room_type_from_text(fallback_room_name)
    if rt:
        return (rt, rt.get_i18n_text("name_i18n", "en") or rt.code)
    return (None, (parsed_room_name or fallback_room_name or "Unknown").strip() or "Unknown")


def resolve_active_pricing_plan(room: Room, target_date: date) -> RoomTypePricingPlan | None:
    plans = RoomTypePricingPlan.objects.filter(room=room, is_active=True).order_by("-is_default", "code")
    for plan in plans:
        if plan.valid_from and target_date < plan.valid_from:
            continue
        if plan.valid_to and target_date > plan.valid_to:
            continue
        return plan
    return None


def resolve_price_for_date(
    room: Room,
    target_date: date,
    adults: int | None = None,
    children: int | None = None,
) -> Decimal | None:
    plan = resolve_active_pricing_plan(room, target_date)
    if not plan:
        return None

    matched_rules = [
        r
        for r in plan.rules.filter(is_active=True).order_by("sort_order", "id")
        if r.matches_date(target_date) and r.matches_occupancy_with_children(adults=adults, children=children)
    ]
    if matched_rules:
        # Prefer more specific occupancy rule (adults/children set) over generic one.
        matched_rules.sort(
            key=lambda r: (
                r.priority,
                (1 if r.adults_count is not None else 0) + (1 if r.children_count is not None else 0),
                r.sort_order,
                -r.id,
            ),
            reverse=True,
        )
        return matched_rules[0].price_per_night
    return plan.base_price_per_night


def accommodation_total_for_period(
    room: Room,
    checkin: date,
    checkout: date,
    adults: int | None = None,
    children: int | None = None,
) -> Decimal | None:
    if checkout <= checkin:
        return Decimal("0.00")
    total = Decimal("0.00")
    day = checkin
    while day < checkout:
        daily_price = resolve_price_for_date(room, day, adults=adults, children=children)
        if daily_price is None:
            return None
        total += daily_price
        day += timedelta(days=1)
    return total
