from __future__ import annotations

from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reception.booking_xls_import import (
    import_booking_xls_bytes,
    is_acceptable_booking_export_filename,
    is_legacy_xls_content,
    validate_booking_export_file,
)

MAX_FILES_PER_REQUEST = 20


class BookingXlsImportSerializer(serializers.Serializer):
    files = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False,
        write_only=True,
    )
    dry_run = serializers.BooleanField(required=False, default=False)
    only_status = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_files(self, files):
        if len(files) > MAX_FILES_PER_REQUEST:
            raise serializers.ValidationError(
                f"Maksimalno {MAX_FILES_PER_REQUEST} datoteka po zahtjevu."
            )
        max_bytes = int(getattr(settings, "BOOKING_XLS_IMPORT_MAX_BYTES", 5 * 1024 * 1024))
        validated = []
        for uploaded in files:
            if uploaded.size > max_bytes:
                raise serializers.ValidationError(
                    f"Datoteka '{uploaded.name}' je prevelika (max {max_bytes} bajtova)."
                )
            head = uploaded.read(8)
            uploaded.seek(0)
            if not is_legacy_xls_content(head):
                raise serializers.ValidationError(
                    f"Datoteka '{uploaded.name}' nije Booking .xls export (Excel 97–2003)."
                )
            if not is_acceptable_booking_export_filename(uploaded.name or ""):
                raise serializers.ValidationError(
                    f"Datoteka '{uploaded.name}' nije podržan format (očekivan .xls ili naziv bez ekstenzije, npr. Prijava)."
                )
            validated.append(uploaded)
        return validated


def _aggregate_summary(file_results: list[dict]) -> dict:
    summary = {
        "files": len(file_results),
        "total": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }
    for item in file_results:
        summary["total"] += item.get("total", 0)
        summary["created"] += item.get("created", 0)
        summary["updated"] += item.get("updated", 0)
        summary["skipped"] += item.get("skipped", 0)
        summary["errors"] += len(item.get("errors") or [])
    return summary


class BookingXlsImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Reception"],
        request=BookingXlsImportSerializer,
        responses={
            200: OpenApiResponse(description="Import results per file and summary"),
            400: OpenApiResponse(description="Validation error"),
        },
    )
    def post(self, request):
        uploaded_files = request.FILES.getlist("files")
        if not uploaded_files:
            return Response(
                {"detail": "Potrebna je barem jedna .xls datoteka (polje files)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "files": uploaded_files,
            "dry_run": request.data.get("dry_run") in (True, "true", "True", "1", 1),
            "only_status": request.data.get("only_status"),
        }
        serializer = BookingXlsImportSerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        dry_run = serializer.validated_data.get("dry_run", False)
        only_status = (serializer.validated_data.get("only_status") or "").strip() or None
        uploaded_files = serializer.validated_data["files"]

        file_results: list[dict] = []

        for uploaded in uploaded_files:
            content = uploaded.read()
            filename = uploaded.name or "upload.xls"
            try:
                validate_booking_export_file(filename=filename, content=content)
            except ValueError as exc:
                file_results.append(
                    {
                        "filename": filename,
                        "total": 0,
                        "created": 0,
                        "updated": 0,
                        "skipped": 0,
                        "errors": [{"external_id": "", "error": str(exc)}],
                    }
                )
                continue
            try:
                with transaction.atomic():
                    stats = import_booking_xls_bytes(
                        content,
                        dry_run=dry_run,
                        only_status=only_status,
                    )
            except Exception as exc:
                file_results.append(
                    {
                        "filename": filename,
                        "total": 0,
                        "created": 0,
                        "updated": 0,
                        "skipped": 0,
                        "errors": [{"external_id": "", "error": str(exc)}],
                    }
                )
                continue

            file_results.append(
                {
                    "filename": filename,
                    "total": stats.get("total", 0),
                    "created": stats.get("created", 0),
                    "updated": stats.get("updated", 0),
                    "skipped": stats.get("skipped", 0),
                    "errors": stats.get("errors") or [],
                }
            )

        return Response(
            {
                "summary": _aggregate_summary(file_results),
                "files": file_results,
                "dry_run": dry_run,
            },
            status=status.HTTP_200_OK,
        )
