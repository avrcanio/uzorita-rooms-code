from django.urls import reverse

from reception.models import Guest, IDDocument


def guest_face_photo_document(guest: Guest) -> IDDocument | None:
    prefetched = getattr(guest, "_prefetched_objects_cache", {}).get("id_documents")
    if prefetched is not None:
        for doc in prefetched:
            if doc.face_photo:
                return doc
        return None
    return (
        guest.id_documents.filter(face_photo__isnull=False)
        .exclude(face_photo="")
        .order_by("-created_at")
        .first()
    )


def guest_face_photo_url(guest: Guest, request) -> str:
    if guest_face_photo_document(guest) is None:
        return ""
    return request.build_absolute_uri(
        reverse(
            "api-reception-guest-face-photo",
            kwargs={
                "reservation_id": guest.reservation_id,
                "guest_id": guest.pk,
            },
        )
    )
