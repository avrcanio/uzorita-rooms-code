from __future__ import annotations

import json
import logging
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
from .services.mrz_crop_postprocess import normalize_mrz_crop_paddle_items
from .services.mrz_image_crop import (
    build_mrz_crop_for_paddle_second_pass,
    crop_bottom_strip_jpeg,
    image_size_from_bytes,
    merge_fullframe_and_mrz_crop_items,
)
from .services.address_from_ocr import suggest_residence_address_from_items
from .services.mrz_pipeline import run_mrz_pipeline
from .services.viz_id_extract import (
    build_expected_td1_lines,
    cross_check_mrz_vs_viz,
    extract_viz_fields_from_ocr,
    normalize_viz_hints,
    viz_fields_sufficient,
)
from .services.ocr_sample_store import (
    save_mrz_crop_debug_stages,
    save_scan_debug_sidecar,
    save_scan_paddle_raw_sidecar,
    save_scan_upload_sample,
)
from .services.ocr_service import OCRService, OCRServiceError

logger = logging.getLogger(__name__)


class PaddleScanSerializer(serializers.Serializer):
    file = serializers.FileField()
    guest_id = serializers.IntegerField(min_value=1)
    reservation_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    document_side = serializers.ChoiceField(
        choices=["front", "back"],
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    viz_hints = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_file(self, value):
        max_bytes = int(getattr(settings, "PADDLE_OCR_SCAN_MAX_BYTES", 8 * 1024 * 1024))
        if value.size > max_bytes:
            raise serializers.ValidationError(f"Datoteka je prevelika (max {max_bytes} bajtova).")
        return value

    def validate_viz_hints(self, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        try:
            parsed = json.loads(value) if isinstance(value, str) else value
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError("viz_hints mora biti valjan JSON objekt.") from exc
        if not isinstance(parsed, dict):
            raise serializers.ValidationError("viz_hints mora biti JSON objekt.")
        return normalize_viz_hints(parsed)

    def validate(self, attrs):
        side = (attrs.get("document_side") or "back").strip().lower()
        if side not in ("front", "back"):
            side = "back"
        attrs["document_side"] = side
        return attrs


def _scan_debug_payload(
    *,
    guest_id: int,
    reservation_id: int | None,
    scan_log_id: int | None,
    scan_status: str,
    duration_ms: int,
    error_message: str,
    ocr_sample_path: str | None,
    ocr_block: dict[str, Any],
    mrz_public: dict[str, Any],
    mrz_pipeline_full: dict[str, Any] | None,
    suggested_fields: dict[str, Any],
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    """Snapshot for sidecar JSON (mirrors API-ish response + full MRZ pipeline dict)."""
    return {
        "guest_id": guest_id,
        "reservation_id": reservation_id,
        "scan_log_id": scan_log_id,
        "scan_status": scan_status,
        "duration_ms": duration_ms,
        "error": error_message,
        "ocr_sample_path": ocr_sample_path,
        "ocr": ocr_block,
        "mrz": mrz_public,
        "mrz_pipeline": mrz_pipeline_full,
        "suggested_fields": suggested_fields,
        "raw_payload": raw_payload,
    }


def _mrz_block_public(mrz: dict[str, Any]) -> dict[str, Any]:
    out = {
        "lines": mrz.get("lines"),
        "format": mrz.get("format"),
        "checksum_valid": mrz.get("checksum_valid"),
        "parsed": mrz.get("parsed"),
        "corrected": mrz.get("corrected"),
        "correction": mrz.get("correction"),
    }
    for k in ("extracted_mrz_candidates", "final_td1_lines", "td1_extraction_meta"):
        if mrz.get(k) is not None:
            out[k] = mrz[k]
    return out


def _raw_payload_json_safe(payload: dict[str, Any]) -> dict[str, Any]:
    """PostgreSQL JSONField mora dobiti JSON-serijalizabilan dict (bez numpy, bytes, …)."""
    try:
        json.dumps(payload, default=str)
        return payload
    except (TypeError, ValueError) as exc:
        logger.warning("scan: raw_payload not JSON-safe, pruning: %s", exc)
        return {
            "provider": payload.get("provider", "paddleocr"),
            "ocr_sample_path": payload.get("ocr_sample_path"),
            "error": "raw_payload_sanitized_for_db",
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
                        "suggested_fields": {
                            "type": "object",
                            "description": (
                                "Polja predložena iz MRZ-a; opcionalno ``address`` i "
                                "``address_lines`` (prebivalište iz OCR iznad MRZ trake)."
                            ),
                            "additionalProperties": True,
                        },
                        "raw_payload": {"type": "object"},
                        "error": {"type": "string"},
                        "ocr_debug_json_path": {"type": "string", "nullable": True},
                        "ocr_paddle_json_path": {"type": "string", "nullable": True},
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
        document_side = ser.validated_data.get("document_side") or "back"
        viz_hints = ser.validated_data.get("viz_hints") or {}
        viz_hint_lines = build_expected_td1_lines(viz_hints) if viz_hints else None

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
        trace = getattr(settings, "SCAN_OCR_TRACE_LOG", False)
        if trace:
            logger.info(
                "scan: start guest_id=%s reservation_id=%s user=%s trace=on",
                guest_id,
                reservation_id,
                getattr(request.user, "pk", None),
            )
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
        raw_payload: dict[str, Any] = {"provider": "paddleocr", "document_side": document_side}
        scan_status = DocumentScanStatus.FAILED
        warnings: list[str] = []

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
        sample_path: str | None = None
        try:
            image_bytes = upload.read()
            if trace:
                logger.info(
                    "scan: upload name=%r content_type=%r bytes=%d",
                    getattr(upload, "name", None),
                    getattr(upload, "content_type", None),
                    len(image_bytes),
                )
            sample_path = save_scan_upload_sample(
                image_bytes,
                guest_id=int(guest_id),
                original_filename=getattr(upload, "name", None),
            )
            if sample_path:
                raw_payload["ocr_sample_path"] = sample_path
                if trace:
                    logger.info("scan: ocr_sample_saved path=%s", sample_path)
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
            debug_json_path = save_scan_debug_sidecar(
                sample_path,
                _scan_debug_payload(
                    guest_id=guest_id,
                    reservation_id=reservation_id,
                    scan_log_id=log.id,
                    scan_status=DocumentScanStatus.FAILED,
                    duration_ms=elapsed_ms,
                    error_message=error_message,
                    ocr_sample_path=raw_payload.get("ocr_sample_path"),
                    ocr_block={**ocr_block, "error": error_message},
                    mrz_public=mrz_block,
                    mrz_pipeline_full=None,
                    suggested_fields={},
                    raw_payload=raw_payload,
                ),
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
                    "ocr_debug_json_path": debug_json_path,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        items: list[dict[str, Any]] = list(paddle.get("items") or [])
        raw_payload["paddle_response"] = paddle.get("raw")
        paddle_http = paddle.get("http_status")

        try:
            second_meta: dict[str, Any] = {"used": False}
            full_w: int | None = None
            full_h: int | None = None
            try:
                full_w, full_h = image_size_from_bytes(image_bytes)
            except Exception:
                full_w, full_h = None, None
            mrz_strip_y0: float | None = None

            if document_side == "front":
                viz_fields = extract_viz_fields_from_ocr(items)
                suggested_fields = {"viz_fields": viz_fields}
                raw_payload["viz_fields"] = viz_fields
                if viz_fields_sufficient(viz_fields):
                    scan_status = DocumentScanStatus.OK
                    error_message = ""
                else:
                    scan_status = DocumentScanStatus.FAILED
                    error_message = (
                        "Prednja strana: nije prepoznat broj dokumenta niti ime i prezime. "
                        "Ponovite sken ili nastavite na stražnju stranu."
                    )
                ocr_block = {
                    "items": items,
                    "http_status": paddle_http,
                    "configured": True,
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
                    raw_payload=_raw_payload_json_safe(raw_payload),
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
                        "raw_payload": log.raw_payload,
                        "error": error_message,
                        "warnings": warnings,
                    },
                    status=status.HTTP_200_OK,
                )

            if getattr(settings, "MRZ_OCR_SECOND_PASS", True) and items:
                try:
                    ratio = float(getattr(settings, "MRZ_CROP_HEIGHT_RATIO", "0.325"))
                    dbg_paths: dict[str, str | None] = {}
                    if getattr(settings, "MRZ_CROP_PREPROCESS", True):
                        up = int(getattr(settings, "MRZ_CROP_UPSCALE", 2))
                        otsu = bool(getattr(settings, "MRZ_CROP_USE_OTSU", False))
                        proc = build_mrz_crop_for_paddle_second_pass(
                            image_bytes,
                            height_ratio=ratio,
                            ocr_items=items,
                            full_height=full_h,
                            upscale=up if up in (2, 3) else 2,
                            use_otsu=otsu,
                        )
                        crop_bytes = proc.preprocessed_jpeg
                        y0 = proc.crop_y0
                        dbg_paths = save_mrz_crop_debug_stages(
                            sample_path,
                            full_original_bytes=image_bytes,
                            crop_raw_jpeg=proc.crop_raw_jpeg,
                            deskewed_jpeg=proc.deskewed_jpeg,
                            preprocessed_jpeg=proc.preprocessed_jpeg,
                        )
                    else:
                        crop_bytes, _fw, _fh, y0 = crop_bottom_strip_jpeg(image_bytes, ratio)
                        dbg_paths = save_mrz_crop_debug_stages(
                            sample_path,
                            full_original_bytes=image_bytes,
                            crop_raw_jpeg=crop_bytes,
                            deskewed_jpeg=crop_bytes,
                            preprocessed_jpeg=crop_bytes,
                        )
                    paddle2 = ocr.predict(
                        image_bytes=crop_bytes,
                        filename="mrz_crop.jpg",
                        content_type="image/jpeg",
                        skip_input_grayscale=bool(getattr(settings, "MRZ_CROP_PREPROCESS", True)),
                        mrz_crop_pass=getattr(settings, "PADDLE_OCR_REQUEST_FORMAT", "multipart").lower()
                        == "json_images",
                    )
                    crop_items = normalize_mrz_crop_paddle_items(paddle2.get("items") or [])
                    items = merge_fullframe_and_mrz_crop_items(
                        items,
                        crop_items,
                        full_height=int(full_h or 1),
                        crop_y0=y0,
                        margin_px=float(getattr(settings, "MRZ_CROP_MERGE_MARGIN_PX", "8.0")),
                    )
                    mrz_strip_y0 = float(y0)
                    second_meta = {
                        "used": True,
                        "crop_height_ratio": ratio,
                        "full_image_size": [full_w or 0, full_h or 0],
                        "crop_y0": y0,
                        "crop_item_count": len(crop_items),
                        "paddle_response_crop": paddle2.get("raw"),
                        "mrz_crop_debug_paths": dbg_paths,
                    }
                    if getattr(settings, "MRZ_CROP_PREPROCESS", True):
                        second_meta["deskew_angle_deg"] = proc.deskew_angle_deg
                        second_meta["skew_source"] = proc.skew_source
                        second_meta["mrz_crop_upscale"] = int(getattr(settings, "MRZ_CROP_UPSCALE", 2))
                    raw_payload["paddle_response_mrz_crop"] = paddle2.get("raw")
                    if trace:
                        logger.info(
                            "scan: mrz_second_pass merged_total=%d crop_items=%d y0=%s",
                            len(items),
                            len(crop_items),
                            y0,
                        )
                except Exception as exc:
                    second_meta = {"used": False, "error": str(exc)}
                    if trace:
                        logger.warning("scan: mrz_second_pass skipped: %s", exc)

            raw_payload["mrz_second_pass"] = second_meta
            raw_payload["timing_ms"] = {"total_after_first_ocr": int((time.perf_counter() - started) * 1000)}
            ocr_block = {
                "items": items,
                "http_status": paddle_http,
                "configured": True,
            }

            t_mrz = time.perf_counter()
            if viz_hints:
                raw_payload["viz_hints"] = viz_hints
            if viz_hint_lines:
                raw_payload["viz_hint_lines"] = list(viz_hint_lines)

            mrz_full = run_mrz_pipeline(
                items,
                image_height=full_h,
                mrz_strip_y0=mrz_strip_y0,
                viz_hint_lines=viz_hint_lines,
            )
            raw_payload["timing_ms"]["mrz_pipeline"] = int((time.perf_counter() - t_mrz) * 1000)
            mrz_block = _mrz_block_public(mrz_full)
            suggested_fields = dict(mrz_full.get("suggested_fields") or {})
            addr_hint = suggest_residence_address_from_items(
                items,
                mrz_strip_y0=mrz_strip_y0,
                image_height=full_h,
            )
            if addr_hint.get("address_lines"):
                suggested_fields["address_lines"] = addr_hint["address_lines"]
            if addr_hint.get("address"):
                suggested_fields["address"] = addr_hint["address"]

            if viz_hints and mrz_full.get("checksum_valid"):
                warnings = cross_check_mrz_vs_viz(suggested_fields, viz_hints)

            if mrz_full.get("checksum_valid"):
                scan_status = DocumentScanStatus.OK
                error_message = ""
            else:
                scan_status = DocumentScanStatus.FAILED
                error_message = "MRZ nije valjan ili nije prepoznat."

            raw_payload["mrz"] = {
                "lines": mrz_full.get("lines"),
                "format": mrz_full.get("format"),
                "checksum_valid": mrz_full.get("checksum_valid"),
                "corrected": mrz_full.get("corrected"),
                "correction": mrz_full.get("correction"),
                "extracted_mrz_candidates": mrz_full.get("extracted_mrz_candidates"),
                "final_td1_lines": mrz_full.get("final_td1_lines"),
                "td1_extraction_meta": mrz_full.get("td1_extraction_meta"),
            }

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            raw_payload["timing_ms"]["total"] = elapsed_ms
            log = DocumentScanLog.objects.create(
                reservation_id=guest.reservation_id,
                guest=guest,
                status=scan_status,
                method="OCR",
                device_id="paddleocr",
                scanned_at=None,
                duration_ms=elapsed_ms,
                raw_payload=_raw_payload_json_safe(raw_payload),
                suggested_fields=suggested_fields,
                corrected_fields={},
                error_message=error_message,
                created_by=request.user if request.user.is_authenticated else None,
            )

            if trace:
                logger.info(
                    "scan: done scan_log_id=%s status=%s ms=%s mrz_checksum_valid=%s err=%r",
                    log.id,
                    scan_status,
                    elapsed_ms,
                    mrz_full.get("checksum_valid"),
                    error_message,
                )

            debug_json_path = save_scan_debug_sidecar(
                sample_path,
                _scan_debug_payload(
                    guest_id=guest_id,
                    reservation_id=reservation_id,
                    scan_log_id=log.id,
                    scan_status=scan_status,
                    duration_ms=elapsed_ms,
                    error_message=error_message,
                    ocr_sample_path=raw_payload.get("ocr_sample_path"),
                    ocr_block=ocr_block,
                    mrz_public=mrz_block,
                    mrz_pipeline_full=mrz_full,
                    suggested_fields=suggested_fields,
                    raw_payload=raw_payload,
                ),
            )
            paddle_json_path = save_scan_paddle_raw_sidecar(
                sample_path,
                paddle_response=raw_payload.get("paddle_response"),
                paddle_response_mrz_crop=raw_payload.get("paddle_response_mrz_crop"),
                mrz_second_pass=raw_payload.get("mrz_second_pass")
                if isinstance(raw_payload.get("mrz_second_pass"), dict)
                else None,
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
                    "warnings": warnings,
                    "ocr_debug_json_path": debug_json_path,
                    "ocr_paddle_json_path": paddle_json_path,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.exception("scan: fatal error after first OCR guest_id=%s", guest_id)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            err = str(exc)[:2000]
            raw_payload_err: dict[str, Any] = {
                "provider": "paddleocr",
                "ocr_sample_path": raw_payload.get("ocr_sample_path"),
                "fatal_error": err,
            }
            log_id: int | None = None
            try:
                log = DocumentScanLog.objects.create(
                    reservation_id=guest.reservation_id,
                    guest=guest,
                    status=DocumentScanStatus.FAILED,
                    method="OCR",
                    device_id="paddleocr",
                    scanned_at=None,
                    duration_ms=elapsed_ms,
                    raw_payload=_raw_payload_json_safe(raw_payload_err),
                    suggested_fields={},
                    corrected_fields={},
                    error_message=err[:500],
                    created_by=request.user if request.user.is_authenticated else None,
                )
                log_id = log.id
            except Exception:
                logger.exception("scan: could not persist DocumentScanLog after fatal error")
            return Response(
                {
                    "scan_log_id": log_id,
                    "scan_status": DocumentScanStatus.FAILED,
                    "duration_ms": elapsed_ms,
                    "ocr": {
                        "items": items,
                        "http_status": paddle_http,
                        "configured": True,
                    },
                    "mrz": _mrz_block_public(
                        {
                            "lines": [],
                            "format": None,
                            "checksum_valid": False,
                            "parsed": None,
                            "corrected": False,
                            "correction": None,
                        }
                    ),
                    "suggested_fields": {},
                    "raw_payload": raw_payload_err,
                    "error": err[:500],
                    "ocr_debug_json_path": None,
                    "ocr_paddle_json_path": None,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
