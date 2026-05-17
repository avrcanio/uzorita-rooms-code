"""Mjesečne agregacije prihoda, provizije i noći za recepcijsku statistiku."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from reception.ical.placeholders import exclude_ical_placeholder_reservations
from reception.models import Reservation, ReservationStatus

PROPERTY_LABEL = "Uzorita Luxury Rooms"
DEFAULT_CURRENCY = "EUR"


def _statistics_queryset(year: int):
    comparison_year = year - 1
    return exclude_ical_placeholder_reservations(
        Reservation.objects.filter(
            status__in=[
                ReservationStatus.CHECKED_IN,
                ReservationStatus.CHECKED_OUT,
            ],
            check_in_date__gte=date(comparison_year, 1, 1),
            check_in_date__lte=date(year, 12, 31),
        )
    ).only(
        "check_in_date",
        "check_out_date",
        "total_amount",
        "commission_amount",
        "nights_count",
        "currency",
    )


def _effective_nights(reservation: Reservation) -> int:
    if reservation.nights_count is not None:
        return int(reservation.nights_count)
    if reservation.check_in_date and reservation.check_out_date:
        return (reservation.check_out_date - reservation.check_in_date).days
    return 0


def _decimal_str(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def aggregate_monthly_statistics(year: int) -> dict:
    comparison_year = year - 1
    buckets: dict[int, dict[str, dict]] = {
        month: {
            "current": {
                "revenue": Decimal("0"),
                "commission": Decimal("0"),
                "nights": 0,
            },
            "previous": {
                "revenue": Decimal("0"),
                "commission": Decimal("0"),
                "nights": 0,
            },
        }
        for month in range(1, 13)
    }

    currency = DEFAULT_CURRENCY
    for reservation in _statistics_queryset(year).iterator():
        check_in = reservation.check_in_date
        if check_in is None:
            continue
        y = check_in.year
        if y == year:
            key = "current"
        elif y == comparison_year:
            key = "previous"
        else:
            continue

        month = check_in.month
        slot = buckets[month][key]
        slot["revenue"] += reservation.total_amount or Decimal("0")
        slot["commission"] += reservation.commission_amount or Decimal("0")
        slot["nights"] += _effective_nights(reservation)
        if reservation.currency:
            currency = reservation.currency

    months_payload = []
    for month in range(1, 13):
        current = buckets[month]["current"]
        previous = buckets[month]["previous"]
        months_payload.append(
            {
                "month": month,
                "current": {
                    "revenue": _decimal_str(current["revenue"]),
                    "commission": _decimal_str(current["commission"]),
                    "nights": current["nights"],
                },
                "previous": {
                    "revenue": _decimal_str(previous["revenue"]),
                    "commission": _decimal_str(previous["commission"]),
                    "nights": previous["nights"],
                },
            }
        )

    return {
        "property_label": PROPERTY_LABEL,
        "year": year,
        "comparison_year": comparison_year,
        "currency": currency,
        "months": months_payload,
    }
