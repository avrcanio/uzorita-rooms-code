from __future__ import annotations

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .document_photo_storage import (
    DOCUMENT_TYPE_NATIONAL_ID,
    DOCUMENT_TYPE_PASSPORT,
    document_photo_filename,
)
from .models import Guest, IDDocument

_GUEST_DOCUMENT_TYPE_LABELS = {
    DOCUMENT_TYPE_PASSPORT: "Putovnica",
    DOCUMENT_TYPE_NATIONAL_ID: "Osobna iskaznica",
}


def _max_photo_bytes() -> int:
    return int(
        getattr(
            settings,
            "DOCUMENT_PHOTO_MAX_BYTES",
            getattr(settings, "PADDLE_OCR_SCAN_MAX_BYTES", 8 * 1024 * 1024),
        )
    )


def _validate_photo_file(value) -> object:
    max_bytes = _max_photo_bytes()
    if value.size > max_bytes:
        raise serializers.ValidationError(f"Datoteka je prevelika (max {max_bytes} bajtova).")
    return value


class DocumentPhotosUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(
        choices=[DOCUMENT_TYPE_PASSPORT, DOCUMENT_TYPE_NATIONAL_ID],
    )
    front = serializers.FileField()
    back = serializers.FileField(required=False, allow_null=True)

    def validate_front(self, value):
        return _validate_photo_file(value)

    def validate_back(self, value):
        if value is None:
            return value
        return _validate_photo_file(value)

    def validate(self, attrs):
        document_type = attrs["document_type"]
        back = attrs.get("back")
        if document_type == DOCUMENT_TYPE_NATIONAL_ID and not back:
            raise serializers.ValidationError({"back": "Stražnja strana je obavezna za osobnu iskaznicu."})
        return attrs


def _active_id_document_for_guest(guest: Guest) -> IDDocument:
    doc = guest.id_documents.order_by("-created_at", "-id").first()
    if doc is None:
        doc = IDDocument.objects.create(guest=guest, image_path="")
    return doc


class DocumentPhotosUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, reservation_id: int, guest_id: int):
        guest = Guest.objects.filter(pk=guest_id, reservation_id=reservation_id).first()
        if guest is None:
            return Response({"detail": "Gost nije pronadjen."}, status=status.HTTP_404_NOT_FOUND)

        serializer = DocumentPhotosUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        id_document = _active_id_document_for_guest(guest)
        front_saved = False
        back_saved = False

        doc_type = data["document_type"]
        id_document._passport_photo = doc_type == DOCUMENT_TYPE_PASSPORT

        front = data["front"]
        front_name = document_photo_filename(
            guest_id=guest.id,
            document_type=doc_type,
            side="front",
        )
        id_document.front_photo.save(front_name, front, save=False)
        front_saved = True

        back = data.get("back")
        if back is not None:
            back_name = document_photo_filename(
                guest_id=guest.id,
                document_type=doc_type,
                side="back",
            )
            id_document.back_photo.save(back_name, back, save=False)
            back_saved = True

        id_document.save(update_fields=["front_photo", "back_photo", "updated_at"])

        guest.document_type = _GUEST_DOCUMENT_TYPE_LABELS[data["document_type"]]
        guest.save(update_fields=["document_type", "updated_at"])

        return Response(
            {
                "id_document_id": id_document.id,
                "document_type": data["document_type"],
                "front_saved": front_saved,
                "back_saved": back_saved,
            },
            status=status.HTTP_200_OK,
        )
