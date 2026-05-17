from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from communications.models import (
    GuestConversation,
    GuestMessage,
    GuestMessageDirection,
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
