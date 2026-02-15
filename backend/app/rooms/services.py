from __future__ import annotations

import re

from rooms.models import RoomType


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
