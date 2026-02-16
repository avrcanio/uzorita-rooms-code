from __future__ import annotations

import calendar
import itertools
from datetime import date, datetime, timedelta
from decimal import Decimal

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from reception.models import Reservation, ReservationStatus
from rooms.models import Room
from rooms.public_booking_serializers import (
    PublicAvailabilityQuerySerializer,
    PublicAvailabilityResponseSerializer,
    PublicRoomCalendarQuerySerializer,
    PublicRoomCalendarResponseSerializer,
)
from rooms.services import accommodation_total_for_period, resolve_price_for_date


def _room_capacity(room: Room) -> int:
    # Temporary capacity map until we introduce explicit capacity fields on Room.
    code = (room.code or "").upper()
    rt_code = (room.room_type.code or "").upper()
    if code.startswith("T") or rt_code in {"R3"}:
        return 4
    return 2


def _allocate_party(*, capacities: list[int], adults: int, children: int) -> list[tuple[int, int]] | None:
    remaining_adults = adults
    remaining_children = children
    allocation: list[tuple[int, int]] = []

    for cap in capacities:
        adults_here = min(remaining_adults, cap)
        remaining_adults -= adults_here
        free_after_adults = cap - adults_here
        children_here = min(remaining_children, free_after_adults)
        remaining_children -= children_here
        allocation.append((adults_here, children_here))

    if remaining_adults > 0 or remaining_children > 0:
        return None
    return allocation


class PublicAvailabilityView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public"],
        operation_id="public_availability_list",
        summary="Availability and combo recommendations (public)",
        description=(
            "Returns all active rooms with availability for date range, accommodation total (without tourist tax), "
            "and 1-3 combo recommendations with allocation."
        ),
        parameters=[
            OpenApiParameter("checkin", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("checkout", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("adults", OpenApiTypes.INT, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("children", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: PublicAvailabilityResponseSerializer},
        examples=[
            OpenApiExample(
                "Availability example",
                value={
                    "checkin": "2026-04-10",
                    "checkout": "2026-04-12",
                    "nights": 2,
                    "adults": 2,
                    "children": 0,
                    "rooms": [
                        {
                            "room_id": 1,
                            "room_code": "K1",
                            "available": True,
                            "pricing": {"currency": "EUR", "accommodation_total": "152.00"},
                        }
                    ],
                    "combos": [
                        {
                            "code": "combo-1",
                            "rooms_count": 1,
                            "allocation": [{"room_id": 1, "room_code": "K1", "adults": 2, "children": 0}],
                            "pricing": {"currency": "EUR", "accommodation_total": "152.00"},
                        }
                    ],
                },
            )
        ],
    )
    def get(self, request):
        qs = PublicAvailabilityQuerySerializer(data=request.query_params)
        qs.is_valid(raise_exception=True)
        checkin = qs.validated_data["checkin"]
        checkout = qs.validated_data["checkout"]
        adults = qs.validated_data["adults"]
        children = qs.validated_data["children"]
        nights = (checkout - checkin).days

        rooms = list(Room.objects.filter(is_active=True).select_related("room_type").order_by("code"))
        room_ids = [r.id for r in rooms]

        overlaps = (
            Reservation.objects.filter(room_id__in=room_ids)
            .exclude(status=ReservationStatus.CANCELED)
            .filter(check_in_date__lt=checkout, check_out_date__gt=checkin)
            .values_list("room_id", flat=True)
            .distinct()
        )
        unavailable_ids = set(overlaps)

        rooms_payload = []
        available_rooms = []
        for room in rooms:
            is_available = room.id not in unavailable_ids
            capacity = _room_capacity(room)
            can_host_party = capacity >= (adults + children)
            total = None
            if is_available and can_host_party:
                total = accommodation_total_for_period(room, checkin, checkout, adults=adults, children=children)

            rooms_payload.append(
                {
                    "room_id": room.id,
                    "room_code": room.code,
                    "room_type_id": room.room_type_id,
                    "room_type_code": room.room_type.code,
                    "available": is_available,
                    "capacity": capacity,
                    "can_host_party": can_host_party,
                    "pricing": {
                        "currency": "EUR",
                        "accommodation_total": str(total) if total is not None else None,
                    },
                }
            )
            if is_available:
                available_rooms.append(room)

        combos: list[dict] = []
        total_guests = adults + children
        for size in (1, 2, 3):
            for subset in itertools.combinations(available_rooms, size):
                subset_caps = [_room_capacity(r) for r in subset]
                if sum(subset_caps) < total_guests:
                    continue

                order = sorted(range(len(subset)), key=lambda i: subset_caps[i], reverse=True)
                sorted_caps = [subset_caps[i] for i in order]
                alloc_sorted = _allocate_party(capacities=sorted_caps, adults=adults, children=children)
                if not alloc_sorted:
                    continue

                allocation: list[dict] = []
                combo_total = Decimal("0.00")
                valid_combo = True
                for alloc_idx, room_idx in enumerate(order):
                    room = subset[room_idx]
                    ad, ch = alloc_sorted[alloc_idx]
                    room_total = accommodation_total_for_period(room, checkin, checkout, adults=ad, children=ch)
                    if room_total is None:
                        valid_combo = False
                        break
                    combo_total += room_total
                    allocation.append(
                        {
                            "room_id": room.id,
                            "room_code": room.code,
                            "adults": ad,
                            "children": ch,
                        }
                    )
                if not valid_combo:
                    continue

                allocation.sort(key=lambda x: x["room_code"])
                combos.append(
                    {
                        "rooms_count": size,
                        "allocation": allocation,
                        "pricing": {
                            "currency": "EUR",
                            "accommodation_total": str(combo_total),
                        },
                    }
                )

        combos.sort(
            key=lambda c: (
                c["rooms_count"],
                Decimal(c["pricing"]["accommodation_total"]),
                ",".join(str(a["room_id"]) for a in c["allocation"]),
            )
        )
        combos = combos[:3]
        for i, combo in enumerate(combos, start=1):
            combo["code"] = f"combo-{i}"

        return Response(
            {
                "checkin": checkin.isoformat(),
                "checkout": checkout.isoformat(),
                "nights": nights,
                "adults": adults,
                "children": children,
                "rooms": rooms_payload,
                "combos": combos,
            },
            status=status.HTTP_200_OK,
        )


class PublicRoomCalendarView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public"],
        operation_id="public_room_calendar",
        summary="Room month calendar (public)",
        description=(
            "Returns day-by-day availability for a physical room and optional price per night "
            "(accommodation only, without tourist tax)."
        ),
        parameters=[
            OpenApiParameter("room_id", OpenApiTypes.INT, OpenApiParameter.PATH, required=True),
            OpenApiParameter("month", OpenApiTypes.STR, OpenApiParameter.QUERY, required=True, description="YYYY-MM"),
            OpenApiParameter("adults", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("children", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: PublicRoomCalendarResponseSerializer},
    )
    def get(self, request, room_id: int):
        room = Room.objects.filter(id=room_id, is_active=True).select_related("room_type").first()
        if not room:
            return Response({"detail": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        qs = PublicRoomCalendarQuerySerializer(data=request.query_params)
        qs.is_valid(raise_exception=True)
        month_raw = qs.validated_data["month"]
        adults = qs.validated_data["adults"]
        children = qs.validated_data["children"]

        try:
            month_start = datetime.strptime(f"{month_raw}-01", "%Y-%m-%d").date()
        except ValueError:
            return Response({"month": "Invalid month format. Use YYYY-MM."}, status=status.HTTP_400_BAD_REQUEST)

        _, last_day = calendar.monthrange(month_start.year, month_start.month)
        month_end = date(month_start.year, month_start.month, last_day) + timedelta(days=1)

        reservations = list(
            Reservation.objects.filter(room_id=room.id)
            .exclude(status=ReservationStatus.CANCELED)
            .filter(check_in_date__lt=month_end, check_out_date__gt=month_start)
            .values("check_in_date", "check_out_date")
        )

        days = []
        d = month_start
        while d < month_end:
            day_end = d + timedelta(days=1)
            is_booked = any(r["check_in_date"] < day_end and r["check_out_date"] > d for r in reservations)
            nightly = resolve_price_for_date(room, d, adults=adults, children=children)
            days.append(
                {
                    "date": d.isoformat(),
                    "available": not is_booked,
                    "pricing": {
                        "currency": "EUR",
                        "accommodation_nightly": str(nightly) if nightly is not None else None,
                    },
                }
            )
            d = day_end

        return Response(
            {
                "room_id": room.id,
                "room_code": room.code,
                "month": month_raw,
                "adults": adults,
                "children": children,
                "days": days,
            },
            status=status.HTTP_200_OK,
        )
