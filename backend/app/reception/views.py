from datetime import date as date_type
import json
import time

from django.db.models import Avg, Count, Prefetch, Q
from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Guest, OcrProvider, OcrScanLog, OcrScanStatus, Reservation
from .serializers import GuestDetailSerializer, OcrScanLogSerializer, ReservationTimelineSerializer


class ReceptionHealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"service": "reception", "status": "ok"})


class ReservationTimelineListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReservationTimelineSerializer

    def get_queryset(self):
        queryset = (
            Reservation.objects.all()
            .annotate(guests_count=Count("guests", distinct=True))
            .prefetch_related(Prefetch("guests", queryset=Guest.objects.order_by("-is_primary", "id")))
            .order_by("check_in_date", "room_name", "id")
        )

        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        day = self._parse_date("date")
        if day:
            queryset = queryset.filter(check_in_date__lte=day, check_out_date__gt=day)

        check_in_from = self._parse_date("check_in_from")
        if check_in_from:
            queryset = queryset.filter(check_in_date__gte=check_in_from)

        check_in_to = self._parse_date("check_in_to")
        if check_in_to:
            queryset = queryset.filter(check_in_date__lte=check_in_to)

        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(external_id__icontains=search)
                | Q(room_name__icontains=search)
                | Q(guests__first_name__icontains=search)
                | Q(guests__last_name__icontains=search)
            ).distinct()

        return queryset

    def _parse_date(self, key: str) -> date_type | None:
        raw_value = self.request.query_params.get(key)
        if not raw_value:
            return None
        return parse_date(raw_value)


class ReservationDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReservationTimelineSerializer

    def get_queryset(self):
        return (
            Reservation.objects.annotate(guests_count=Count("guests", distinct=True))
            .prefetch_related(Prefetch("guests", queryset=Guest.objects.order_by("-is_primary", "id")))
            .order_by("id")
        )


class ReservationGuestDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GuestDetailSerializer
    lookup_url_kwarg = "guest_id"

    def get_queryset(self):
        return Guest.objects.filter(reservation_id=self.kwargs["reservation_id"]).order_by("id")


class ReservationGuestOcrView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, reservation_id: int, guest_id: int):
        guest = Guest.objects.filter(pk=guest_id, reservation_id=reservation_id).first()
        if guest is None:
            return Response({"detail": "Gost nije pronadjen."}, status=404)

        provider = str(request.data.get("provider", OcrProvider.MICROBLINK)).strip().lower()
        if provider != OcrProvider.MICROBLINK:
            return Response({"detail": "Nepodrzani provider."}, status=400)

        started = time.perf_counter()
        status_value = OcrScanStatus.FAILED
        error_message = ""
        raw_payload: dict = {}
        suggested_fields: dict = {}
        corrected_fields: dict = {}
        raw_payload = self._parse_json_field(request.data.get("raw_payload", {}))
        suggested_fields = self._parse_json_field(request.data.get("suggested_fields", {}))
        corrected_fields = self._parse_json_field(request.data.get("corrected_fields", {}))

        normalized_suggested, guest_updates = self._build_guest_updates_from_ocr_payload(
            raw_payload=raw_payload,
            suggested_fields=suggested_fields,
        )
        suggested_fields = normalized_suggested

        if suggested_fields:
            status_value = OcrScanStatus.OK
        else:
            status_value = OcrScanStatus.FAILED
            error_message = "Microblink payload nema suggested_fields."

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        duration_ms = self._parse_int(request.data.get("duration_ms")) or elapsed_ms

        ocr_log = OcrScanLog.objects.create(
            reservation_id=reservation_id,
            guest=guest,
            provider=provider,
            status=status_value,
            duration_ms=duration_ms,
            raw_payload=raw_payload,
            suggested_fields=suggested_fields,
            corrected_fields=corrected_fields,
            error_message=error_message,
            created_by=request.user if request.user.is_authenticated else None,
        )

        if status_value == OcrScanStatus.OK and guest_updates:
            for field, value in guest_updates.items():
                setattr(guest, field, value)
            guest.save(update_fields=list(guest_updates.keys()) + ["updated_at"])

        return Response(
            {
                "ocr_log_id": ocr_log.id,
                "provider": provider,
                "ocr_status": status_value,
                "duration_ms": duration_ms,
                "id_document_id": None,
                "id_document_ids": [],
                "image_path": "",
                "suggested_fields": suggested_fields,
                "raw_payload": raw_payload,
                "error": error_message,
            }
        )

    def _build_guest_updates_from_ocr_payload(self, raw_payload: dict, suggested_fields: dict):
        root = raw_payload
        if isinstance(raw_payload.get("raw_payload"), dict):
            root = raw_payload["raw_payload"]

        def deep_find(node, keys, depth=7):
            if depth < 0 or node is None:
                return None
            if isinstance(node, list):
                for item in node:
                    value = deep_find(item, keys, depth - 1)
                    if value not in (None, "", {}):
                        return value
                return None
            if isinstance(node, dict):
                for key in keys:
                    if key in node and node[key] not in (None, "", {}):
                        return node[key]
                for nested in node.values():
                    value = deep_find(nested, keys, depth - 1)
                    if value not in (None, "", {}):
                        return value
            return None

        def text_value(value):
            if value is None:
                return ""
            if isinstance(value, str):
                return value.strip()
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, dict):
                if "value" in value:
                    return text_value(value.get("value"))
                for lang_key in ("latin", "cyrillic", "arabic", "greek"):
                    lang_value = value.get(lang_key)
                    if isinstance(lang_value, dict) and lang_value.get("value"):
                        return text_value(lang_value.get("value"))
                return ""
            return ""

        def clean_string(value):
            if not isinstance(value, str):
                return ""
            cleaned = value.strip()
            if not cleaned:
                return ""
            lowered = cleaned.lower()
            if lowered in {"[object object]", "object object"}:
                return ""
            if cleaned.startswith("[") and len(cleaned) <= 4:
                return ""
            return cleaned

        def prefer_value(primary, fallback):
            primary_clean = clean_string(primary) if isinstance(primary, str) else primary
            if isinstance(primary_clean, str):
                return primary_clean if primary_clean else fallback
            return primary if primary not in (None, "", {}) else fallback

        def date_to_iso(value):
            if isinstance(value, str):
                parsed = parse_date(value)
                return parsed.isoformat() if parsed else ""
            if isinstance(value, dict):
                year = int(value.get("year") or 0)
                month = int(value.get("month") or 0)
                day = int(value.get("day") or 0)
                if year and month and day:
                    return f"{year:04d}-{month:02d}-{day:02d}"
            return ""

        merged = {}
        merged.update(suggested_fields if isinstance(suggested_fields, dict) else {})

        merged["first_name"] = prefer_value(
            merged.get("first_name"),
            text_value(deep_find(root, ["firstName", "secondaryId"])),
        )
        merged["last_name"] = prefer_value(
            merged.get("last_name"),
            text_value(deep_find(root, ["lastName", "primaryId"])),
        )
        merged["document_number"] = prefer_value(
            merged.get("document_number"),
            text_value(deep_find(root, ["documentNumber", "idNumber"])),
        )
        merged["nationality"] = prefer_value(
            merged.get("nationality"),
            text_value(deep_find(root, ["isoAlpha2CountryCode", "nationality", "citizenship"])),
        )
        merged["date_of_birth"] = prefer_value(
            merged.get("date_of_birth"),
            date_to_iso(deep_find(root, ["dateOfBirth", "birthDate"])),
        )

        merged["sex"] = text_value(deep_find(root, ["sex"]))
        merged["address"] = text_value(deep_find(root, ["address"]))
        merged["date_of_issue"] = date_to_iso(deep_find(root, ["dateOfIssue"]))
        merged["date_of_expiry"] = date_to_iso(deep_find(root, ["dateOfExpiry"]))
        merged["issuing_authority"] = text_value(deep_find(root, ["issuingAuthority"]))
        merged["personal_id_number"] = text_value(deep_find(root, ["personalIdNumber", "oib"]))
        merged["document_additional_number"] = text_value(deep_find(root, ["documentAdditionalNumber"]))
        merged["additional_personal_id_number"] = text_value(deep_find(root, ["additionalPersonalIdNumber"]))
        merged["document_code"] = text_value(deep_find(root, ["documentCode"]))
        merged["document_type"] = text_value(deep_find(root, ["documentType", "type"]))
        merged["document_country"] = text_value(deep_find(root, ["countryName", "country"]))
        merged["document_country_iso2"] = text_value(deep_find(root, ["isoAlpha2CountryCode"]))
        merged["document_country_iso3"] = text_value(deep_find(root, ["isoAlpha3CountryCode"]))
        merged["document_country_numeric"] = text_value(deep_find(root, ["isoNumericCountryCode"]))
        merged["mrz_raw_text"] = text_value(deep_find(root, ["rawMrzString"]))

        mrz_verified_raw = deep_find(root, ["verified"])
        merged["mrz_verified"] = bool(mrz_verified_raw) if mrz_verified_raw is not None else None

        # Normalize common OCR artifacts.
        for key, value in list(merged.items()):
            if isinstance(value, str) and value.strip() == "[object Object]":
                merged[key] = ""

        if isinstance(merged.get("nationality"), str):
            nationality = merged["nationality"].strip().upper()
            if len(nationality) == 3 and nationality == "HRV":
                nationality = "HR"
            elif len(nationality) > 2:
                nationality = nationality[:2]
            merged["nationality"] = nationality

        json_fields = {}
        for key, value in merged.items():
            if value is None:
                continue
            if isinstance(value, str):
                trimmed = value.strip()
                if trimmed:
                    json_fields[key] = trimmed
            elif isinstance(value, bool):
                json_fields[key] = value

        guest_updates = {}
        string_fields = [
            "first_name",
            "last_name",
            "document_number",
            "nationality",
            "sex",
            "address",
            "issuing_authority",
            "personal_id_number",
            "document_additional_number",
            "additional_personal_id_number",
            "document_code",
            "document_type",
            "document_country",
            "document_country_iso2",
            "document_country_iso3",
            "document_country_numeric",
            "mrz_raw_text",
        ]
        date_fields = ["date_of_birth", "date_of_issue", "date_of_expiry"]
        bool_fields = ["mrz_verified"]

        for field in string_fields:
            value = json_fields.get(field)
            if isinstance(value, str) and value:
                guest_updates[field] = value

        for field in date_fields:
            value = json_fields.get(field)
            if isinstance(value, str):
                parsed = parse_date(value)
                if parsed:
                    guest_updates[field] = parsed

        for field in bool_fields:
            if field in json_fields and isinstance(json_fields[field], bool):
                guest_updates[field] = json_fields[field]

        return json_fields, guest_updates

    def _parse_json_field(self, value):
        if isinstance(value, dict):
            return value
        if value is None or value == "":
            return {}
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    def _parse_int(self, value):
        try:
            if value in (None, ""):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None


class OcrScanLogListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OcrScanLogSerializer

    def get_queryset(self):
        queryset = OcrScanLog.objects.select_related("reservation", "guest").order_by("-created_at")

        provider = self.request.query_params.get("provider")
        if provider:
            queryset = queryset.filter(provider=provider)

        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        reservation_id = self.request.query_params.get("reservation_id")
        if reservation_id:
            queryset = queryset.filter(reservation_id=reservation_id)

        guest_id = self.request.query_params.get("guest_id")
        if guest_id:
            queryset = queryset.filter(guest_id=guest_id)

        limit = self.request.query_params.get("limit")
        if limit:
            try:
                queryset = queryset[: max(1, min(500, int(limit)))]
            except ValueError:
                pass

        return queryset


class OcrScanStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = OcrScanLog.objects.all()

        date_from = parse_date(request.query_params.get("date_from", ""))
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        date_to = parse_date(request.query_params.get("date_to", ""))
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        providers = [OcrProvider.MICROBLINK]
        by_provider = {}
        total_count = queryset.count()

        for provider in providers:
            provider_qs = queryset.filter(provider=provider)
            total = provider_qs.count()
            success = provider_qs.filter(status=OcrScanStatus.OK).count()
            failed = provider_qs.filter(status=OcrScanStatus.FAILED).count()
            avg_duration = provider_qs.aggregate(value=Avg("duration_ms"))["value"]

            by_provider[provider] = {
                "total": total,
                "success": success,
                "failed": failed,
                "success_rate": round((success / total) * 100, 2) if total else 0.0,
                "avg_duration_ms": int(avg_duration) if avg_duration is not None else None,
            }

        return Response(
            {
                "total_scans": total_count,
                "by_provider": by_provider,
            }
        )
