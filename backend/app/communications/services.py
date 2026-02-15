from __future__ import annotations

from typing import Any
from decimal import Decimal
from django.utils.dateparse import parse_date

from django.db import transaction

from communications.booking_parser import BookingParseException, parse_booking_email
from communications.models import InboundEmail, ParseError, ParseStatus
from reception.booking_import import status_from_booking_kind, upsert_reservation_from_booking_payload
from reception.models import Reservation, ReservationStatus
from rooms.services import canonical_room_info, preferred_room_code_from_parsed_room_name


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


@transaction.atomic
def process_booking_inbound_email(*, inbound_email_id: int, dry_run: bool = False) -> dict[str, Any]:
    inbound = InboundEmail.objects.select_for_update().get(id=inbound_email_id)

    # Re-processing should replace previous error info for this email.
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

        # Cancellation emails can apply to multi-room bookings; cancel all reservations for this booking.
        if status == ReservationStatus.CANCELED:
            Reservation.objects.filter(external_id=payload.booking_number).update(status=ReservationStatus.CANCELED)
            Reservation.objects.filter(external_id__startswith=f"{payload.booking_number}-").update(
                status=ReservationStatus.CANCELED
            )

            inbound.parse_status = ParseStatus.PARSED
            inbound.save(update_fields=["parsed_payload", "parse_status", "parse_note", "updated_at"])
            return {"status": "parsed", "external_id": payload.booking_number, "reservation_ids": [], "primary_guest_ids": []}

        room_items = payload.rooms or [
            {
                "room_name": payload.room_name,
                "check_in_date": payload.check_in_date.isoformat() if payload.check_in_date else None,
                "check_out_date": payload.check_out_date.isoformat() if payload.check_out_date else None,
                "amount": str(payload.total_amount) if payload.total_amount is not None else None,
                "currency": payload.currency,
            }
        ]

        reservation_ids: list[int] = []
        primary_guest_ids: list[int] = []

        for idx, item in enumerate(room_items):
            external_id = payload.booking_number if idx == 0 else f"{payload.booking_number}-{idx + 1}"
            parsed_room_name = (item.get("room_name") or "").strip() or payload.room_name
            preferred_code = preferred_room_code_from_parsed_room_name(parsed_room_name)
            room_type, room_name = canonical_room_info(
                parsed_room_name=parsed_room_name,
                fallback_room_name=payload.property_name,
            )

            amount = None
            raw_amount = item.get("amount")
            if raw_amount:
                try:
                    amount = Decimal(str(raw_amount))
                except Exception:
                    amount = None

            currency = (item.get("currency") or payload.currency or "").strip() or None

            item_check_in = parse_date((item.get("check_in_date") or "").strip()) or payload.check_in_date
            item_check_out = parse_date((item.get("check_out_date") or "").strip()) or payload.check_out_date

            multi = len(room_items) > 1
            amount_to_save = amount if amount is not None else (payload.total_amount if not multi else None)

            result = upsert_reservation_from_booking_payload(
                external_id=external_id,
                room_name=room_name,
                room_type=room_type,
                check_in_date=item_check_in,
                check_out_date=item_check_out,
                status=status,
                guest_full_name=payload.guest_full_name,
                guest_email=payload.guest_email,
                guest_nationality_iso2=payload.guest_nationality_iso2,
                preferred_room_code=preferred_code,
                total_amount=amount_to_save,
                currency=currency,
            )
            reservation_ids.append(result.reservation_id)
            if result.primary_guest_id:
                primary_guest_ids.append(result.primary_guest_id)

        inbound.parse_status = ParseStatus.PARSED
        inbound.save(update_fields=["parsed_payload", "parse_status", "parse_note", "updated_at"])
        return {
            "status": "parsed",
            "external_id": payload.booking_number,
            "reservation_ids": reservation_ids,
            "primary_guest_ids": primary_guest_ids,
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
