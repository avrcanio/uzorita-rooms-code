from __future__ import annotations

import time
from typing import Any

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DocumentScanLog, DocumentScanStatus, Guest
from .services.mrz_pipeline import run_mrz_pipeline
from .services.ocr_service import OCRService, OCRServiceError


class PaddleScanSerializer(serializers.Serializer):
    file = serializers.FileField()
    guest_id = serializers.IntegerField(min_value=1)
    reservation_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate_file(self, value):
        max_bytes = int(getattr(settings, "PADDLE_OCR_SCAN_MAX_BYTES", 8 * 1024 * 1024))
        if value.size > max_bytes:
            raise serializers.ValidationError(f"Datoteka je prevelika (max {max_bytes} bajtova).")
        return value


def _mrz_block_public(mrz: dict[str, Any]) -> dict[str, Any]:
    return {
        "lines": mrz.get("lines"),
        "format": mrz.get("format"),
        "checksum_valid": mrz.get("checksum_valid"),
        "parsed": mrz.get("parsed"),
        "corrected": mrz.get("corrected"),
        "correction": mrz.get("correction"),
    }


class PaddleDocumentScanView(APIView):
    """
    POST /api/v1/scan/ — šalje sliku na PaddleOCR, validira MRZ (mrz lib), zapisuje audit
    bez ažuriranja Guest zapisa.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Sken dokumenta (PaddleOCR + MRZ)",
        description=(
            "Prima multipart `file`, `guest_id` i opcionalno `reservation_id`. "
            "Ne mijenja Guest; kreira DocumentScanLog. Za trajni upis koristite "
            "`POST /api/reception/reservations/.../document-scan/` nakon korisničke potvrde."
        ),
        request=PaddleScanSerializer,
        responses={
            200: OpenApiResponse(
                response={
                    "type": "object",
                    "properties": {
                        "scan_log_id": {"type": "integer"},
                        "scan_status": {"type": "string", "enum": ["ok", "failed"]},
                        "duration_ms": {"type": "integer"},
                        "ocr": {"type": "object"},
                        "mrz": {"type": "object"},
                        "suggested_fields": {"type": "object"},
                        "raw_payload": {"type": "object"},
                        "error": {"type": "string"},
                    },
                },
            ),
            400: OpenApiResponse(description="Nevaljan zahtjev"),
            404: OpenApiResponse(description="Gost nije pronađen"),
            503: OpenApiResponse(description="PaddleOCR nije dostupan ili nije konfiguriran"),
        },
    )
    def post(self, request):
        ser = PaddleScanSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        guest_id = ser.validated_data["guest_id"]
        reservation_id = ser.validated_data.get("reservation_id")
        upload = ser.validated_data["file"]

        guest = Guest.objects.select_related("reservation").filter(pk=guest_id).first()
        if guest is None:
            return Response({"detail": "Gost nije pronadjen."}, status=status.HTTP_404_NOT_FOUND)

        if reservation_id is not None and int(reservation_id) != int(guest.reservation_id):
            return Response(
                {"detail": "Rezervacija ne odgovara gostu."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        started = time.perf_counter()
        error_message = ""
        ocr_block: dict[str, Any] = {"items": [], "configured": False}
        mrz_block = _mrz_block_public(
            {
                "lines": [],
                "format": None,
                "checksum_valid": False,
                "parsed": None,
                "corrected": False,
                "correction": None,
            }
        )
        suggested_fields: dict[str, Any] = {}
        raw_payload: dict[str, Any] = {"provider": "paddleocr"}
        scan_status = DocumentScanStatus.FAILED

        ocr = OCRService()
        if not ocr.is_configured():
            error_message = "PaddleOCR URL nije konfiguriran (PADDLE_OCR_BASE_URL)."
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            log = DocumentScanLog.objects.create(
                reservation_id=guest.reservation_id,
                guest=guest,
                status=scan_status,
                method="OCR",
                device_id="paddleocr",
                scanned_at=None,
                duration_ms=elapsed_ms,
                raw_payload={**raw_payload, "error": error_message},
                suggested_fields={},
                corrected_fields={},
                error_message=error_message,
                created_by=request.user if request.user.is_authenticated else None,
            )
            return Response(
                {
                    "scan_log_id": log.id,
                    "scan_status": scan_status,
                    "duration_ms": elapsed_ms,
                    "ocr": ocr_block,
                    "mrz": mrz_block,
                    "suggested_fields": {},
                    "raw_payload": log.raw_payload,
                    "error": error_message,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        ocr_block["configured"] = True
        try:
            image_bytes = upload.read()
            paddle = ocr.predict(
                image_bytes=image_bytes,
                filename=getattr(upload, "name", None) or "upload.bin",
                content_type=getattr(upload, "content_type", None),
            )
        except OCRServiceError as exc:
            error_message = str(exc)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            raw_payload["paddle_error"] = error_message
            log = DocumentScanLog.objects.create(
                reservation_id=guest.reservation_id,
                guest=guest,
                status=DocumentScanStatus.FAILED,
                method="OCR",
                device_id="paddleocr",
                scanned_at=None,
                duration_ms=elapsed_ms,
                raw_payload=raw_payload,
                suggested_fields={},
                corrected_fields={},
                error_message=error_message,
                created_by=request.user if request.user.is_authenticated else None,
            )
            return Response(
                {
                    "scan_log_id": log.id,
                    "scan_status": DocumentScanStatus.FAILED,
                    "duration_ms": elapsed_ms,
                    "ocr": {"items": [], "raw": None, "error": error_message},
                    "mrz": mrz_block,
                    "suggested_fields": {},
                    "raw_payload": raw_payload,
                    "error": error_message,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        items = paddle.get("items") or []
        ocr_block = {
            "items": items,
            "http_status": paddle.get("http_status"),
            "configured": True,
        }
        raw_payload["paddle_response"] = paddle.get("raw")

        mrz_full = run_mrz_pipeline(items)
        mrz_block = _mrz_block_public(mrz_full)
        suggested_fields = dict(mrz_full.get("suggested_fields") or {})

        if mrz_full.get("checksum_valid"):
            scan_status = DocumentScanStatus.OK
        else:
            scan_status = DocumentScanStatus.FAILED
            error_message = "MRZ nije valjan ili nije prepoznat."

        raw_payload["mrz"] = {
            "lines": mrz_full.get("lines"),
            "format": mrz_full.get("format"),
            "checksum_valid": mrz_full.get("checksum_valid"),
            "corrected": mrz_full.get("corrected"),
            "correction": mrz_full.get("correction"),
        }

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log = DocumentScanLog.objects.create(
            reservation_id=guest.reservation_id,
            guest=guest,
            status=scan_status,
            method="OCR",
            device_id="paddleocr",
            scanned_at=None,
            duration_ms=elapsed_ms,
            raw_payload=raw_payload,
            suggested_fields=suggested_fields,
            corrected_fields={},
            error_message=error_message,
            created_by=request.user if request.user.is_authenticated else None,
        )

        return Response(
            {
                "scan_log_id": log.id,
                "scan_status": scan_status,
                "duration_ms": elapsed_ms,
                "ocr": ocr_block,
                "mrz": mrz_block,
                "suggested_fields": suggested_fields,
                "raw_payload": raw_payload,
                "error": error_message,
            },
            status=status.HTTP_200_OK,
        )
