from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import xlrd
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from reception.models import Guest, ImportSource, Reservation, ReservationStatus
from reception.reservation_units import (
    apply_unit_amounts_from_total,
    split_unit_amounts,
    sync_reservation_units,
    unit_specs_from_room_name,
    unit_specs_snapshot,
)
from rooms.allocation import assign_rooms_for_reservation

# Legacy Excel .xls (OLE compound document) — Booking export without .xls extension uses same format.
LEGACY_XLS_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
BLOCKED_BOOKING_EXPORT_EXTENSIONS = (".xlsx", ".xlsm", ".csv", ".txt", ".pdf", ".zip", ".doc", ".docx")


def is_legacy_xls_content(content: bytes) -> bool:
    return len(content) >= 8 and content[:8] == LEGACY_XLS_OLE_SIGNATURE


def is_acceptable_booking_export_filename(filename: str) -> bool:
    """Booking.com often saves as 'Prijava' without .xls extension."""
    name = (filename or "").strip()
    lower = name.lower()
    if lower.endswith(".xls"):
        return True
    if any(lower.endswith(ext) for ext in BLOCKED_BOOKING_EXPORT_EXTENSIONS):
        return False
    return "." not in name


def validate_booking_export_file(*, filename: str, content: bytes) -> None:
    lower = (filename or "").lower()
    if any(lower.endswith(ext) for ext in BLOCKED_BOOKING_EXPORT_EXTENSIONS):
        raise ValueError(f"Datoteka '{filename}' nije podržana (koristite Booking .xls export).")
    if not is_legacy_xls_content(content):
        raise ValueError(
            f"Datoteka '{filename}' nije stari Excel (.xls) format. "
            "Booking export mora biti .xls (Excel 97–2003), ne .xlsx."
        )


XLS_HEADER_ALIASES = {
    "broj rezervacije": "external_id",
    "nositelj rezervacije": "booker_name",
    "ime(na) gosta": "guest_names",
    "prijava": "check_in_date",
    "odjava": "check_out_date",
    "rezervirano": "booked_at",
    "status": "booking_status",
    "jedinice": "units_count",
    "osobe": "persons_count",
    "odrasli": "adults_count",
    "djeca": "children_count",
    "dob djece": "children_ages",
    "cijena": "price",
    "provizija %": "commission_percent",
    "iznos provizije": "commission_amount",
    "status placanja": "payment_status",
    "status plaćanja": "payment_status",
    "nacin placanja (pruzatelj usluga naplate)": "payment_provider",
    "način plaćanja (pružatelj usluga naplate)": "payment_provider",
    "napomene": "notes",
    "booker country": "booker_country",
    "svrha putovanja": "travel_purpose",
    "uredaj": "booking_device",
    "uređaj": "booking_device",
    "vrsta jedinice": "room_name",
    "trajanje (nocenja)": "nights_count",
    "trajanje (noćenja)": "nights_count",
    "datum otkazivanja": "canceled_at",
    "adresa": "booker_address",
    "broj telefona": "booker_phone",
}


@dataclass(frozen=True)
class BookingXlsRow:
    external_id: str
    booker_name: str
    guest_names: list[str]
    check_in_date: date
    check_out_date: date
    booked_at: datetime | None
    booking_status: str
    units_count: int | None
    persons_count: int | None
    adults_count: int | None
    children_count: int | None
    children_ages: str
    total_amount: Decimal | None
    currency: str
    commission_percent: Decimal | None
    commission_amount: Decimal | None
    payment_status: str
    payment_provider: str
    notes: str
    booker_country: str
    travel_purpose: str
    booking_device: str
    room_name: str
    nights_count: int | None
    canceled_at: datetime | None
    booker_address: str
    booker_phone: str


@dataclass(frozen=True)
class XlsImportResult:
    external_id: str
    created: bool
    skipped: bool = False
    updated: bool = False
    reservation_id: int | None = None


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_money(value: Any) -> tuple[Decimal | None, str]:
    raw = _cell_str(value)
    if not raw:
        return (None, "EUR")
    match = re.match(r"^([\d.,]+)\s*([A-Za-z]{3})?$", raw.replace(" ", ""))
    if not match:
        try:
            return (Decimal(raw.replace(",", ".")), "EUR")
        except InvalidOperation:
            return (None, "EUR")
    amount_raw, currency = match.group(1), (match.group(2) or "EUR")
    amount_raw = amount_raw.replace(",", ".")
    try:
        return (Decimal(amount_raw), currency.upper())
    except InvalidOperation:
        return (None, currency.upper())


def _parse_decimal(value: Any) -> Decimal | None:
    raw = _cell_str(value)
    if not raw:
        return None
    raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _parse_int(value: Any) -> int | None:
    raw = _cell_str(value)
    if not raw:
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _parse_xls_datetime(value: Any, book: xlrd.book.Book) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            dt_tuple = xlrd.xldate_as_tuple(value, book.datemode)
            dt = datetime(*dt_tuple[:6])
        except Exception:
            return None
    else:
        raw = _cell_str(value)
        if not raw:
            return None
        parsed = parse_datetime(raw)
        if parsed:
            dt = parsed
        else:
            d = parse_date(raw)
            if not d:
                return None
            dt = datetime.combine(d, datetime.min.time())
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_xls_date(value: Any, book: xlrd.book.Book) -> date | None:
    dt = _parse_xls_datetime(value, book)
    if dt:
        return dt.date()
    raw = _cell_str(value)
    if not raw:
        return None
    return parse_date(raw[:10]) if len(raw) >= 10 else parse_date(raw)


def _split_guest_names(raw: str) -> list[str]:
    if not raw:
        return []
    text = raw.strip()
    if ";" in text:
        return [p.strip() for p in text.split(";") if p.strip()]
    if "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        # "Last, First" (booker style) vs "Guest One, Guest Two" (two full names).
        if len(parts) > 1 and all(len(part.split()) >= 2 for part in parts):
            return parts
    return [text]


def _parse_guest_name(full_name: str) -> tuple[str, str]:
    name = html.unescape((full_name or "").strip())
    if not name:
        return ("", "")
    if "," in name:
        last, _, first = name.partition(",")
        return (first.strip() or "-", last.strip() or "-")
    parts = [p for p in name.split() if p]
    if len(parts) == 1:
        return (parts[0], "")
    return (" ".join(parts[:-1]), parts[-1])


def _operational_status_from_booking(booking_status: str) -> str:
    normalized = (booking_status or "").strip().lower()
    if normalized in {"cancelled_by_guest", "cancelled", "canceled", "cancelled_by_hotel"}:
        return ReservationStatus.CANCELED
    return ReservationStatus.EXPECTED


def _decimal_equal(left: Decimal | None, right: Decimal | None) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    # Match DB storage (DecimalField decimal_places=2).
    quant = Decimal("0.01")
    return Decimal(left).quantize(quant) == Decimal(right).quantize(quant)


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return value.astimezone(dt_timezone.utc)


def _datetime_equal(left: datetime | None, right: datetime | None) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return _normalize_dt(left) == _normalize_dt(right)


def _guest_snapshot_from_row(row: BookingXlsRow) -> tuple[tuple[str, str, bool, str], ...]:
    items: list[tuple[str, str, bool, str]] = []
    for idx, full_name in enumerate(row.guest_names):
        first_name, last_name = _parse_guest_name(full_name)
        if not first_name and not last_name:
            continue
        items.append(
            (
                first_name or "-",
                last_name or "-",
                idx == 0,
                (row.booker_country if idx == 0 else "").upper(),
            )
        )
    return tuple(sorted(items))


def _guest_snapshot_from_reservation(reservation: Reservation) -> tuple[tuple[str, str, bool, str], ...]:
    items = [
        (
            g.first_name,
            g.last_name,
            g.is_primary,
            (g.nationality or "").upper(),
        )
        for g in reservation.guests.all()
    ]
    return tuple(sorted(items))


def _row_guests_present_in_reservation(reservation: Reservation, row: BookingXlsRow) -> bool:
    """All guests from XLS must exist on reservation; extra guests in DB are allowed."""
    row_guests = _guest_snapshot_from_row(row)
    if not row_guests:
        return True
    db_guests = set(_guest_snapshot_from_reservation(reservation))
    return all(guest in db_guests for guest in row_guests)


def _target_operational_status(reservation: Reservation, row: BookingXlsRow) -> str:
    if reservation.status in (ReservationStatus.CHECKED_IN, ReservationStatus.CHECKED_OUT):
        return reservation.status
    return _operational_status_from_booking(row.booking_status)


def row_matches_reservation(
    reservation: Reservation,
    row: BookingXlsRow,
) -> bool:
    if reservation.external_id != row.external_id:
        return False
    if reservation.check_in_date != row.check_in_date:
        return False
    if reservation.check_out_date != row.check_out_date:
        return False
    if reservation.status != _target_operational_status(reservation, row):
        return False
    if not _decimal_equal(reservation.total_amount, row.total_amount):
        return False
    if (reservation.currency or "EUR") != (row.currency or "EUR"):
        return False
    if (reservation.booker_name or "") != (row.booker_name or ""):
        return False
    if not _datetime_equal(reservation.booked_at, row.booked_at):
        return False
    if (reservation.booking_status or "") != (row.booking_status or ""):
        return False
    if reservation.units_count != row.units_count:
        return False
    if reservation.persons_count != row.persons_count:
        return False
    if reservation.adults_count != row.adults_count:
        return False
    if reservation.children_count != row.children_count:
        return False
    if (reservation.children_ages or "") != (row.children_ages or ""):
        return False
    if not _decimal_equal(reservation.commission_percent, row.commission_percent):
        return False
    if not _decimal_equal(reservation.commission_amount, row.commission_amount):
        return False
    if (reservation.payment_status or "") != (row.payment_status or ""):
        return False
    if (reservation.payment_provider or "") != (row.payment_provider or ""):
        return False
    if (reservation.notes or "") != (row.notes or ""):
        return False
    if (reservation.booker_country or "").upper() != (row.booker_country or "").upper():
        return False
    if (reservation.travel_purpose or "") != (row.travel_purpose or ""):
        return False
    if (reservation.booking_device or "") != (row.booking_device or ""):
        return False
    if reservation.nights_count != row.nights_count:
        return False
    if not _datetime_equal(reservation.canceled_at, row.canceled_at):
        return False
    if (reservation.booker_address or "") != (row.booker_address or ""):
        return False
    if (reservation.booker_phone or "") != (row.booker_phone or ""):
        return False
    if not _row_guests_present_in_reservation(reservation, row):
        return False
    if unit_specs_snapshot(reservation) != unit_specs_from_room_name(row.room_name):
        return False
    units = list(reservation.units.order_by("sort_order", "id"))
    if row.total_amount is not None and units:
        expected_amounts = split_unit_amounts(row.total_amount, len(units))
        for unit, expected in zip(units, expected_amounts):
            if not _decimal_equal(unit.amount, expected):
                return False
    return True


def classify_xls_row(row: BookingXlsRow) -> str:
    """Return 'created', 'updated', or 'skipped' without writing."""
    reservation = (
        Reservation.objects.filter(external_id=row.external_id)
        .prefetch_related("guests", "units")
        .first()
    )
    if reservation is None:
        return "created"
    if row_matches_reservation(reservation, row):
        return "skipped"
    return "updated"


def _map_row_dict(raw: dict[str, Any], book: xlrd.book.Book) -> BookingXlsRow:
    external_raw = raw.get("external_id")
    external_id = _cell_str(external_raw)
    if not external_id:
        raise ValueError("Missing booking number (Broj rezervacije)")
    try:
        external_id = str(int(float(external_id)))
    except (TypeError, ValueError):
        pass

    check_in = _parse_xls_date(raw.get("check_in_date"), book)
    check_out = _parse_xls_date(raw.get("check_out_date"), book)
    if not check_in or not check_out:
        raise ValueError(f"Missing check-in/out dates for booking {external_id}")

    total_amount, currency = _parse_money(raw.get("price"))

    return BookingXlsRow(
        external_id=external_id,
        booker_name=_cell_str(raw.get("booker_name")),
        guest_names=_split_guest_names(_cell_str(raw.get("guest_names"))),
        check_in_date=check_in,
        check_out_date=check_out,
        booked_at=_parse_xls_datetime(raw.get("booked_at"), book),
        booking_status=_cell_str(raw.get("booking_status")),
        units_count=_parse_int(raw.get("units_count")),
        persons_count=_parse_int(raw.get("persons_count")),
        adults_count=_parse_int(raw.get("adults_count")),
        children_count=_parse_int(raw.get("children_count")),
        children_ages=_cell_str(raw.get("children_ages")),
        total_amount=total_amount,
        currency=currency,
        commission_percent=_parse_decimal(raw.get("commission_percent")),
        commission_amount=_parse_money(raw.get("commission_amount"))[0],
        payment_status=_cell_str(raw.get("payment_status")),
        payment_provider=_cell_str(raw.get("payment_provider")),
        notes=html.unescape(_cell_str(raw.get("notes"))),
        booker_country=_cell_str(raw.get("booker_country")).upper()[:8],
        travel_purpose=_cell_str(raw.get("travel_purpose")),
        booking_device=_cell_str(raw.get("booking_device")),
        room_name=_cell_str(raw.get("room_name")) or "Unknown",
        nights_count=_parse_int(raw.get("nights_count")),
        canceled_at=_parse_xls_datetime(raw.get("canceled_at"), book),
        booker_address=_cell_str(raw.get("booker_address")),
        booker_phone=_cell_str(raw.get("booker_phone")),
    )


def parse_booking_xls_workbook(book) -> list[BookingXlsRow]:
    sheet = book.sheet_by_index(0)
    if sheet.nrows < 2:
        return []

    header_map: dict[int, str] = {}
    for col in range(sheet.ncols):
        label = _normalize_header(_cell_str(sheet.cell_value(0, col)))
        field = XLS_HEADER_ALIASES.get(label)
        if field:
            header_map[col] = field

    rows: list[BookingXlsRow] = []
    for row_idx in range(1, sheet.nrows):
        raw: dict[str, Any] = {}
        empty = True
        for col, field in header_map.items():
            value = sheet.cell_value(row_idx, col)
            if _cell_str(value):
                empty = False
            raw[field] = value
        if empty:
            continue
        rows.append(_map_row_dict(raw, book))
    return rows


def parse_booking_xls(path: str) -> list[BookingXlsRow]:
    return parse_booking_xls_workbook(xlrd.open_workbook(path))


def parse_booking_xls_bytes(content: bytes) -> list[BookingXlsRow]:
    return parse_booking_xls_workbook(xlrd.open_workbook(file_contents=content))


def _sync_guests(*, reservation: Reservation, guest_names: list[str], booker_country: str, booker_phone: str) -> None:
    if not guest_names:
        return

    # Clear primary first to satisfy unique_primary_guest_per_reservation.
    Guest.objects.filter(reservation=reservation).update(is_primary=False)

    synced_ids: list[int] = []
    for idx, full_name in enumerate(guest_names):
        first_name, last_name = _parse_guest_name(full_name)
        if not first_name and not last_name:
            continue
        is_primary = idx == 0
        guest = Guest.objects.filter(
            reservation=reservation,
            first_name=first_name or "-",
            last_name=last_name or "-",
        ).first()
        if guest is None:
            guest = Guest.objects.create(
                reservation=reservation,
                first_name=first_name or "-",
                last_name=last_name or "-",
                nationality=booker_country if is_primary else "",
                is_primary=is_primary,
            )
        else:
            guest.is_primary = is_primary
            if is_primary and booker_country and not guest.nationality:
                guest.nationality = booker_country
            guest.save(update_fields=["is_primary", "nationality", "updated_at"])
        synced_ids.append(guest.id)

    if booker_phone:
        primary = Guest.objects.filter(reservation=reservation, is_primary=True).first()
        if primary and not primary.email:
            # phone stored on reservation; guest model has no phone field
            pass


@transaction.atomic
def upsert_reservation_from_xls_row(row: BookingXlsRow) -> XlsImportResult:
    new_operational_status = _operational_status_from_booking(row.booking_status)
    now = timezone.now()

    existing = (
        Reservation.objects.filter(external_id=row.external_id)
        .prefetch_related("guests", "units")
        .first()
    )
    if existing and row_matches_reservation(existing, row):
        return XlsImportResult(
            external_id=row.external_id,
            created=False,
            skipped=True,
            updated=False,
            reservation_id=existing.id,
        )

    reservation, created = Reservation.objects.get_or_create(
        external_id=row.external_id,
        defaults={
            "check_in_date": row.check_in_date,
            "check_out_date": row.check_out_date,
            "status": new_operational_status,
            "total_amount": row.total_amount,
            "currency": row.currency or "EUR",
            "import_source": ImportSource.BOOKING_XLS,
            "imported_at": now,
        },
    )

    reservation.check_in_date = row.check_in_date
    reservation.check_out_date = row.check_out_date
    reservation.total_amount = row.total_amount
    reservation.currency = row.currency or "EUR"
    reservation.booker_name = row.booker_name
    reservation.booked_at = row.booked_at
    reservation.booking_status = row.booking_status
    reservation.units_count = row.units_count
    reservation.persons_count = row.persons_count
    reservation.adults_count = row.adults_count
    reservation.children_count = row.children_count
    reservation.children_ages = row.children_ages
    reservation.commission_percent = row.commission_percent
    reservation.commission_amount = row.commission_amount
    reservation.payment_status = row.payment_status
    reservation.payment_provider = row.payment_provider
    reservation.notes = row.notes
    reservation.booker_country = row.booker_country
    reservation.travel_purpose = row.travel_purpose
    reservation.booking_device = row.booking_device
    reservation.nights_count = row.nights_count
    reservation.canceled_at = row.canceled_at
    reservation.booker_address = row.booker_address
    reservation.booker_phone = row.booker_phone
    reservation.import_source = ImportSource.BOOKING_XLS
    reservation.imported_at = now

    if reservation.status not in (ReservationStatus.CHECKED_IN, ReservationStatus.CHECKED_OUT):
        reservation.status = new_operational_status

    reservation.save()

    _sync_guests(
        reservation=reservation,
        guest_names=row.guest_names,
        booker_country=row.booker_country,
        booker_phone=row.booker_phone,
    )

    units = sync_reservation_units(reservation=reservation, room_name=row.room_name)
    assign_rooms_for_reservation(reservation_id=reservation.id)
    apply_unit_amounts_from_total(
        reservation=reservation,
        total_amount=row.total_amount,
        units=units,
    )

    return XlsImportResult(
        external_id=row.external_id,
        created=created,
        skipped=False,
        updated=not created,
        reservation_id=reservation.id,
    )


def import_booking_xls_rows(
    rows: list[BookingXlsRow],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    stats: dict[str, Any] = {"created": 0, "updated": 0, "skipped": 0, "errors": []}

    for row in rows:
        try:
            if dry_run:
                action = classify_xls_row(row)
                stats[action] += 1
                continue

            result = upsert_reservation_from_xls_row(row)
            if result.created:
                stats["created"] += 1
            elif result.skipped:
                stats["skipped"] += 1
            else:
                stats["updated"] += 1
        except Exception as exc:
            stats["errors"].append({"external_id": row.external_id, "error": str(exc)})

    stats["total"] = len(rows)
    return stats


def import_booking_xls_file(
    path: str,
    *,
    dry_run: bool = False,
    only_status: str | None = None,
) -> dict[str, Any]:
    rows = parse_booking_xls(path)
    if only_status:
        filter_status = only_status.strip().lower()
        rows = [r for r in rows if r.booking_status.lower() == filter_status]
    return import_booking_xls_rows(rows, dry_run=dry_run)


def import_booking_xls_bytes(
    content: bytes,
    *,
    dry_run: bool = False,
    only_status: str | None = None,
) -> dict[str, Any]:
    rows = parse_booking_xls_bytes(content)
    if only_status:
        filter_status = only_status.strip().lower()
        rows = [r for r in rows if r.booking_status.lower() == filter_status]
    return import_booking_xls_rows(rows, dry_run=dry_run)
