from __future__ import annotations

import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from reception.models import EvisitorGuestStatus, EvisitorSubmission, Guest

from .client import EvisitorClient
from .exceptions import EvisitorApiError, EvisitorConfigError, EvisitorValidationError
from .mapper import build_check_in_payload, mask_payload_for_log


def submit_guest_checkin(guest: Guest, *, user=None, force_retry: bool = False) -> EvisitorSubmission:
    if not settings.EVISITOR_ENABLED:
        raise EvisitorConfigError("eVisitor integracija nije uključena.")

    guest = Guest.objects.select_related("reservation").get(pk=guest.pk)

    if guest.evisitor_status == EvisitorGuestStatus.SENT and not force_retry:
        return (
            EvisitorSubmission.objects.filter(
                guest=guest, status=EvisitorGuestStatus.SENT
            )
            .order_by("-created_at")
            .first()
        )

    registration_id = uuid.uuid4()
    if guest.evisitor_registration_id and guest.evisitor_status == EvisitorGuestStatus.FAILED:
        if not force_retry:
            registration_id = guest.evisitor_registration_id
    elif guest.evisitor_registration_id and guest.evisitor_status == EvisitorGuestStatus.SENT:
        registration_id = guest.evisitor_registration_id

    payload = build_check_in_payload(guest, registration_id=registration_id)
    masked = mask_payload_for_log(payload)

    submission = EvisitorSubmission.objects.create(
        guest=guest,
        registration_id=registration_id,
        status=EvisitorGuestStatus.PENDING,
        submitted_by=user,
        request_payload=masked,
    )

    Guest.objects.filter(pk=guest.pk).update(
        evisitor_status=EvisitorGuestStatus.PENDING,
        evisitor_registration_id=registration_id,
    )

    client = EvisitorClient()
    try:
        client.login()
        client.execute_action("CheckInTourist", payload)
    except (EvisitorApiError, EvisitorValidationError, EvisitorConfigError) as exc:
        user_msg = getattr(exc, "user_message", "") or str(exc)
        system_msg = getattr(exc, "system_message", "") or ""
        field_errors = getattr(exc, "field_errors", None)
        if field_errors:
            user_msg = "; ".join(f"{k}: {v}" for k, v in field_errors.items())

        submission.status = EvisitorGuestStatus.FAILED
        submission.error_user_message = user_msg[:2000]
        submission.error_system_message = system_msg[:2000]
        submission.response_payload = {
            "error": user_msg,
            "system": system_msg,
        }
        submission.save(
            update_fields=[
                "status",
                "error_user_message",
                "error_system_message",
                "response_payload",
            ]
        )
        Guest.objects.filter(pk=guest.pk).update(
            evisitor_status=EvisitorGuestStatus.FAILED,
        )
        raise
    finally:
        try:
            client.logout()
        finally:
            client.close()

    now = timezone.now()
    submission.status = EvisitorGuestStatus.SENT
    submission.submitted_at = now
    submission.response_payload = {"ok": True}
    submission.save(update_fields=["status", "submitted_at", "response_payload"])

    with transaction.atomic():
        Guest.objects.filter(pk=guest.pk).update(
            evisitor_status=EvisitorGuestStatus.SENT,
            evisitor_registration_id=registration_id,
        )

    return submission
