from __future__ import annotations

from typing import Any
from decimal import Decimal
from django.utils.dateparse import parse_date

from django.db import transaction

from communications.booking_parser import BookingParseException, parse_booking_email
from communications.models import InboundEmail, ParseError, ParseStatus
from reception.booking_import import status_from_booking_kind, upsert_reservation_from_booking_payload
from reception.models import ImportSource, Reservation, ReservationStatus
from rooms.services import canonical_room_info


def _record_error(
    *,
    inbound: InboundEmail,
    code: str,
    message: str,
    context: dict[str, Any] | None = None,
):
    ParseError.objects.create(
        inbound_email=inbound,
        code=code,
        message=message,
        context=context or {},
    )


def _cancel_suffix_reservations(booking_number: str) -> int:
    return Reservation.objects.filter(external_id__startswith=f"{booking_number}-").update(
        status=ReservationStatus.CANCELED
    )


@transaction.atomic
def process_booking_inbound_email(*, inbound_email_id: int, dry_run: bool = False) -> dict[str, Any]:
    inbound = InboundEmail.objects.select_for_update().get(id=inbound_email_id)

    inbound.parse_errors.all().delete()
    inbound.parse_note = ""

    try:
        payload = parse_booking_email(
            subject=inbound.subject or "",
            body_text=inbound.body_text or "",
            body_html=getattr(inbound, "body_html", "") or "",
        )
        payload_dict = payload.to_dict()
        inbound.parsed_payload = payload_dict

        missing = []
        if not payload.check_in_date:
            missing.append("check_in_date")
        if not payload.check_out_date:
            missing.append("check_out_date")
        if not (payload.property_name or payload.room_name or payload.rooms):
            missing.append("room_name")

        if missing:
            inbound.parse_status = ParseStatus.PARTIAL
            _record_error(
                inbound=inbound,
                code="missing_fields",
                message=f"Missing required fields: {', '.join(missing)}",
                context={"missing": missing, "payload": payload_dict},
            )
            inbound.save(update_fields=["parsed_payload", "parse_status", "parse_note", "updated_at"])
            return {"status": "partial", "missing": missing}

        status = status_from_booking_kind(payload.kind)

        if dry_run:
            inbound.parse_status = ParseStatus.PARSED
            inbound.save(update_fields=["parsed_payload", "parse_status", "parse_note", "updated_at"])
            return {"status": "dry_run", "external_id": payload.booking_number}

        if status == ReservationStatus.CANCELED:
            Reservation.objects.filter(external_id=payload.booking_number).update(status=ReservationStatus.CANCELED)
            canceled_suffix = _cancel_suffix_reservations(payload.booking_number)

            inbound.parse_status = ParseStatus.PARSED
            inbound.save(update_fields=["parsed_payload", "parse_status", "parse_note", "updated_at"])
            return {
                "status": "parsed",
                "external_id": payload.booking_number,
                "reservation_ids": [],
                "primary_guest_ids": [],
                "canceled_suffix": canceled_suffix,
            }

        room_items = payload.rooms or [
            {
                "room_name": payload.room_name,
                "check_in_date": payload.check_in_date.isoformat() if payload.check_in_date else None,
                "check_out_date": payload.check_out_date.isoformat() if payload.check_out_date else None,
                "amount": str(payload.total_amount) if payload.total_amount is not None else None,
                "currency": payload.currency,
            }
        ]

        canonical_names: list[str] = []
        for item in room_items:
            parsed_room_name = (item.get("room_name") or "").strip() or payload.room_name
            _room_type, room_name = canonical_room_info(
                parsed_room_name=parsed_room_name,
                fallback_room_name=payload.property_name,
            )
            canonical_names.append(room_name)

        combined_room_name = ", ".join(canonical_names) if canonical_names else (payload.room_name or "Unknown")
        first_item = room_items[0]

        multi = len(room_items) > 1
        amount = None
        raw_amount = first_item.get("amount")
        if raw_amount:
            try:
                amount = Decimal(str(raw_amount))
            except Exception:
                amount = None
        if amount is None and payload.total_amount is not None and not multi:
            amount = payload.total_amount

        currency = (first_item.get("currency") or payload.currency or "").strip() or None
        check_in = parse_date((first_item.get("check_in_date") or "").strip()) or payload.check_in_date
        check_out = parse_date((first_item.get("check_out_date") or "").strip()) or payload.check_out_date

        result = upsert_reservation_from_booking_payload(
            external_id=payload.booking_number,
            room_name=combined_room_name,
            check_in_date=check_in,
            check_out_date=check_out,
            status=status,
            guest_full_name=payload.guest_full_name,
            guest_email=payload.guest_email,
            guest_nationality_iso2=payload.guest_nationality_iso2,
            total_amount=amount,
            currency=currency,
            import_source=ImportSource.BOOKING_EMAIL,
        )

        canceled_suffix = _cancel_suffix_reservations(payload.booking_number)

        inbound.parse_status = ParseStatus.PARSED
        inbound.save(update_fields=["parsed_payload", "parse_status", "parse_note", "updated_at"])
        return {
            "status": "parsed",
            "external_id": payload.booking_number,
            "reservation_ids": [result.reservation_id],
            "primary_guest_ids": [result.primary_guest_id] if result.primary_guest_id else [],
            "canceled_suffix": canceled_suffix,
        }
    except BookingParseException as e:
        inbound.parse_status = ParseStatus.FAILED
        _record_error(inbound=inbound, code=e.code, message=e.message, context=e.context)
        inbound.save(update_fields=["parsed_payload", "parse_status", "parse_note", "updated_at"])
        return {"status": "failed", "code": e.code}
    except Exception as e:
        inbound.parse_status = ParseStatus.FAILED
        _record_error(inbound=inbound, code="unexpected", message=str(e), context={})
        inbound.save(update_fields=["parsed_payload", "parse_status", "parse_note", "updated_at"])
        return {"status": "failed", "code": "unexpected"}
