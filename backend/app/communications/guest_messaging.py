from __future__ import annotations

import logging
import re
import uuid
from email import message_from_string
from email.utils import parseaddr
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from communications.booking_parser import _parse_booking_number_from_subject
from communications.models import (
    GuestConversation,
    GuestMessage,
    GuestMessageDirection,
    InboundEmail,
    OutboundEmail,
    OutboundEmailStatus,
)
from reception.models import Guest, Reservation

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

logger = logging.getLogger(__name__)

SMTP_MESSAGE_ID_DOMAIN = "uzorita.hr"


def get_primary_guest(reservation: Reservation) -> Guest | None:
    return Guest.objects.filter(reservation=reservation, is_primary=True).first()


def guest_message_subject(reservation: Reservation) -> str:
    external_id = (reservation.external_id or "").strip()
    if external_id:
        return f"Re: Booking {external_id}"
    return f"Poruka o rezervaciji #{reservation.pk}"


def make_smtp_message_id() -> str:
    return f"<{uuid.uuid4()}@{SMTP_MESSAGE_ID_DOMAIN}>"


def _validate_guest_email(email: str) -> str:
    normalized = (email or "").strip()
    if not normalized:
        raise ValidationError({"guest": "Primarni gost nema email adresu."})
    validate_email(normalized)
    return normalized


@transaction.atomic
def send_guest_message(
    *,
    reservation_id: int,
    body_text: str,
    user: AbstractBaseUser,
) -> GuestMessage:
    text = (body_text or "").strip()
    if not text:
        raise ValidationError({"body_text": "Poruka ne smije biti prazna."})

    try:
        reservation = Reservation.objects.get(pk=reservation_id)
    except Reservation.DoesNotExist as exc:
        raise ValidationError({"reservation": "Rezervacija ne postoji."}) from exc

    guest = get_primary_guest(reservation)
    if guest is None:
        raise ValidationError({"guest": "Nema primarnog gosta na rezervaciji."})

    to_email = _validate_guest_email(guest.email)

    conversation, _ = GuestConversation.objects.get_or_create(reservation=reservation)
    subject = guest_message_subject(reservation)
    smtp_message_id = make_smtp_message_id()

    outbound = OutboundEmail.objects.create(
        reservation=reservation,
        guest=guest,
        conversation=conversation,
        to_email=to_email,
        subject=subject,
        body_text=text,
        smtp_message_id=smtp_message_id,
        sent_by=user,
        status=OutboundEmailStatus.QUEUED,
    )
    message = GuestMessage.objects.create(
        conversation=conversation,
        direction=GuestMessageDirection.OUTBOUND,
        body_text=text,
        outbound_email=outbound,
        sent_by=user,
    )
    GuestConversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())

    outbound_id = outbound.pk
    transaction.on_commit(lambda: _enqueue_send_guest_email(outbound_id))

    return message


def _enqueue_send_guest_email(outbound_email_id: int) -> None:
    from communications.tasks import send_guest_email_task

    send_guest_email_task.delay(outbound_email_id)


def deliver_outbound_guest_email(outbound_email_id: int) -> None:
    outbound = OutboundEmail.objects.select_related("reservation", "guest").get(
        pk=outbound_email_id
    )

    if outbound.status == OutboundEmailStatus.SENT:
        return

    if not outbound.smtp_message_id:
        outbound.smtp_message_id = make_smtp_message_id()
        outbound.save(update_fields=["smtp_message_id", "updated_at"])

    email = EmailMessage(
        subject=outbound.subject,
        body=outbound.body_text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[outbound.to_email],
    )
    headers = {"Message-ID": outbound.smtp_message_id}
    if outbound.in_reply_to:
        headers["In-Reply-To"] = outbound.in_reply_to
        headers["References"] = outbound.in_reply_to
    email.extra_headers = headers

    email.send(fail_silently=False)

    outbound.status = OutboundEmailStatus.SENT
    outbound.sent_at = timezone.now()
    outbound.error_message = ""
    outbound.save(update_fields=["status", "sent_at", "error_message", "updated_at"])


def record_outbound_send_failure(
    outbound_email_id: int,
    error: str,
    *,
    final: bool,
) -> None:
    updates: dict[str, object] = {
        "error_message": error[:2000],
        "updated_at": timezone.now(),
    }
    if final:
        updates["status"] = OutboundEmailStatus.FAILED
    OutboundEmail.objects.filter(pk=outbound_email_id).update(**updates)


_MESSAGE_ID_RE = re.compile(r"<[^>\s]+>")


def _extract_message_ids(header_value: str) -> list[str]:
    return _MESSAGE_ID_RE.findall((header_value or "").strip())


def _reply_header_message_ids(inbound: InboundEmail) -> list[str]:
    raw = (inbound.raw_headers or "").strip()
    if not raw:
        return []
    msg = message_from_string(raw)
    ids: list[str] = []
    for header in ("In-Reply-To", "References"):
        value = msg.get(header, "")
        if value:
            ids.extend(_extract_message_ids(str(value)))
    return ids


def _parse_sender_email(sender: str) -> str:
    _, email = parseaddr((sender or "").strip())
    return email.strip().lower()


def _inbound_body_text(inbound: InboundEmail) -> str:
    text = (inbound.body_text or "").strip()
    if text:
        return text
    html = (inbound.body_html or "").strip()
    if not html:
        return ""
    return re.sub(r"<[^>]+>", " ", html).strip()


def _booking_number_for_inbound(inbound: InboundEmail) -> str | None:
    payload = inbound.parsed_payload or {}
    number = (payload.get("booking_number") or "").strip()
    if number:
        return number
    from_subject = _parse_booking_number_from_subject(inbound.subject or "")
    if from_subject:
        return from_subject
    match = re.search(r"\b(\d{8,12})\b", inbound.subject or "")
    return match.group(1) if match else None


def _is_guest_message_like(
    inbound: InboundEmail,
    *,
    booking_number: str | None,
    sender_email: str,
) -> bool:
    payload = inbound.parsed_payload or {}
    if payload.get("kind") == "message":
        return True
    if sender_email and sender_email.endswith("@guest.booking.com"):
        return True
    subject = (inbound.subject or "").strip().lower()
    if subject.startswith("re:"):
        return True
    if booking_number and booking_number in (inbound.subject or ""):
        return True
    return False


def _match_reservation_by_reply_headers(inbound: InboundEmail) -> Reservation | None:
    message_ids = _reply_header_message_ids(inbound)
    if not message_ids:
        return None
    outbound = (
        OutboundEmail.objects.filter(smtp_message_id__in=message_ids)
        .select_related("reservation")
        .order_by("-created_at")
        .first()
    )
    if outbound and outbound.reservation_id:
        return outbound.reservation
    return None


def _match_reservation_by_booking_number(
    inbound: InboundEmail,
    booking_number: str,
    *,
    sender_email: str,
) -> Reservation | None:
    if not _is_guest_message_like(
        inbound,
        booking_number=booking_number,
        sender_email=sender_email,
    ):
        return None
    return Reservation.objects.filter(external_id=booking_number).first()


def _reference_date(inbound: InboundEmail):
    if inbound.received_at:
        return inbound.received_at.date()
    return timezone.localdate()


def _match_reservation_by_guest_email(
    inbound: InboundEmail,
    sender_email: str,
) -> Reservation | None:
    ref_date = _reference_date(inbound)
    guests = Guest.objects.filter(
        is_primary=True,
        email__iexact=sender_email,
        reservation__check_in_date__lte=ref_date,
        reservation__check_out_date__gte=ref_date,
    ).select_related("reservation")
    matches = list(guests[:5])
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0].reservation

    linked = [
        g.reservation
        for g in matches
        if GuestConversation.objects.filter(reservation=g.reservation_id).exists()
    ]
    if len(linked) == 1:
        return linked[0]

    return max(matches, key=lambda g: g.reservation.check_in_date).reservation


def _find_reservation_for_inbound(inbound: InboundEmail) -> Reservation | None:
    reservation = _match_reservation_by_reply_headers(inbound)
    if reservation:
        return reservation

    sender_email = _parse_sender_email(inbound.sender)
    booking_number = _booking_number_for_inbound(inbound)
    if booking_number:
        reservation = _match_reservation_by_booking_number(
            inbound,
            booking_number,
            sender_email=sender_email,
        )
        if reservation:
            return reservation

    if sender_email:
        return _match_reservation_by_guest_email(inbound, sender_email)
    return None


@transaction.atomic
def link_inbound_to_conversation(inbound: InboundEmail) -> GuestMessage | None:
    """Link a stored inbound email to the reservation guest thread, if possible."""
    existing = (
        GuestMessage.objects.filter(inbound_email=inbound)
        .select_related("conversation", "inbound_email")
        .first()
    )
    if existing:
        return existing

    reservation = _find_reservation_for_inbound(inbound)
    if reservation is None:
        return None

    body_text = _inbound_body_text(inbound)
    if not body_text:
        body_text = (inbound.subject or "").strip() or "(prazna poruka)"

    conversation, _ = GuestConversation.objects.get_or_create(reservation=reservation)
    message = GuestMessage.objects.create(
        conversation=conversation,
        direction=GuestMessageDirection.INBOUND,
        body_text=body_text,
        inbound_email=inbound,
    )
    inbound.reservation = reservation
    inbound.save(update_fields=["reservation", "updated_at"])
    GuestConversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
    return message


def process_inbound_guest_messages(*, limit: int = 50) -> dict[str, int]:
    """Try to link unprocessed inbound emails to guest conversations."""
    linked_inbound_ids = GuestMessage.objects.filter(
        inbound_email__isnull=False,
    ).values_list("inbound_email_id", flat=True)

    qs = InboundEmail.objects.exclude(id__in=linked_inbound_ids).order_by("id")

    processed = 0
    linked = 0
    for inbound in qs[: max(1, limit)]:
        processed += 1
        if link_inbound_to_conversation(inbound):
            linked += 1

    return {"processed": processed, "linked": linked, "skipped": processed - linked}
