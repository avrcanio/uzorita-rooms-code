from __future__ import annotations

from django.utils import timezone

DOCUMENT_TYPE_PASSPORT = "passport"
DOCUMENT_TYPE_NATIONAL_ID = "national_id"


def _photo_timestamp() -> str:
    return timezone.localtime().strftime("%d%m%y%H%M")


def document_photo_filename(*, guest_id: int, document_type: str, side: str) -> str:
    ts = _photo_timestamp()
    if document_type == DOCUMENT_TYPE_PASSPORT:
        return f"{ts}_{guest_id}_pass.jpg"
    if side == "front":
        return f"{ts}_{guest_id}_frontID.jpg"
    return f"{ts}_{guest_id}_backID.jpg"


def id_document_front_upload_to(instance, filename: str) -> str:
    if getattr(instance, "_passport_photo", False):
        return f"id_documents/passports/{filename}"
    return f"id_documents/{filename}"


def id_document_back_upload_to(instance, filename: str) -> str:
    return f"id_documents/{filename}"
