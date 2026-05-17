from datetime import date as date_type
import base64
import json
import time

from django.db.models import Count, Prefetch, Q
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reception.ical.placeholders import exclude_ical_placeholder_reservations

from .models import DocumentScanLog, DocumentScanStatus, Guest, IDDocument, Reservation, ReservationUnit
from rest_framework.exceptions import NotFound

from .serializers import (
    GuestCreateSerializer,
    GuestDetailSerializer,
    ReservationTimelineSerializer,
    ReservationUpdateSerializer,
)


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
            exclude_ical_placeholder_reservations(Reservation.objects.all())
            .annotate(guests_count=Count("guests", distinct=True))
            .prefetch_related(
                Prefetch("guests", queryset=Guest.objects.order_by("-is_primary", "id")),
                Prefetch(
                    "units",
                    queryset=ReservationUnit.objects.order_by("sort_order", "id"),
                ),
                "units__room",
                "units__room_type",
            )
            .order_by("check_in_date", "id")
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

        period_from = self._parse_date("period_from")
        period_to = self._parse_date("period_to")
        if period_from and period_to:
            queryset = queryset.filter(
                Q(check_in_date__gte=period_from, check_in_date__lte=period_to)
                | Q(check_out_date__gte=period_from, check_out_date__lte=period_to)
            )

        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(external_id__icontains=search)
                | Q(units__room_name__icontains=search)
                | Q(guests__first_name__icontains=search)
                | Q(guests__last_name__icontains=search)
            ).distinct()

        return queryset

    def _parse_date(self, key: str) -> date_type | None:
        raw_value = self.request.query_params.get(key)
        if not raw_value:
            return None
        return parse_date(raw_value)


class ReservationDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return ReservationUpdateSerializer
        return ReservationTimelineSerializer

    def get_queryset(self):
        return (
            Reservation.objects.annotate(guests_count=Count("guests", distinct=True))
            .prefetch_related(
                Prefetch("guests", queryset=Guest.objects.order_by("-is_primary", "id")),
                Prefetch(
                    "units",
                    queryset=ReservationUnit.objects.order_by("sort_order", "id"),
                ),
                "units__room",
                "units__room_type",
            )
            .order_by("id")
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        update_serializer = self.get_serializer(instance, data=request.data, partial=partial)
        update_serializer.is_valid(raise_exception=True)
        self.perform_update(update_serializer)
        detail = self.get_queryset().get(pk=instance.pk)
        output = ReservationTimelineSerializer(detail, context=self.get_serializer_context())
        return Response(output.data)


class ReservationGuestListCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GuestCreateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        reservation = Reservation.objects.filter(pk=self.kwargs["reservation_id"]).first()
        if reservation is None:
            raise NotFound("Rezervacija nije pronadena.")
        context["reservation"] = reservation
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guest = serializer.save()
        output = GuestDetailSerializer(guest, context=self.get_serializer_context())
        return Response(output.data, status=201)


class ReservationGuestDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GuestDetailSerializer
    lookup_url_kwarg = "guest_id"

    def get_queryset(self):
        return Guest.objects.filter(reservation_id=self.kwargs["reservation_id"]).order_by("id")


class DocumentScanIngestView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, reservation_id: int, guest_id: int):
        guest = Guest.objects.filter(pk=guest_id, reservation_id=reservation_id).first()
        if guest is None:
            return Response({"detail": "Gost nije pronadjen."}, status=404)

        started = time.perf_counter()
        status_value = DocumentScanStatus.FAILED
        error_message = ""
        raw_payload = self._parse_json_field(request.data)
        normalized_suggested, guest_updates, face_photo_b64, signature_b64, scanned_at, method, device_id = (
            self._build_guest_updates_from_document_scan_payload(raw_payload=raw_payload)
        )

        suggested_fields = normalized_suggested
        corrected_fields: dict = {}

        if guest_updates:
            status_value = DocumentScanStatus.OK
        else:
            status_value = DocumentScanStatus.FAILED
            error_message = "Ne mogu mapirati payload u polja gosta."

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        duration_ms = self._parse_int(request.data.get("duration_ms")) or elapsed_ms

        scan_log = DocumentScanLog.objects.create(
            reservation_id=reservation_id,
            guest=guest,
            status=status_value,
            method=method,
            device_id=device_id,
            scanned_at=scanned_at,
            duration_ms=duration_ms,
            raw_payload=raw_payload,
            suggested_fields=suggested_fields,
            corrected_fields=corrected_fields,
            error_message=error_message,
            created_by=request.user if request.user.is_authenticated else None,
        )

        if status_value == DocumentScanStatus.OK and guest_updates:
            for field, value in guest_updates.items():
                setattr(guest, field, value)
            guest.save(update_fields=list(guest_updates.keys()) + ["updated_at"])

        id_document_id = None
        if status_value == DocumentScanStatus.OK and (face_photo_b64 or signature_b64):
            id_document = IDDocument.objects.create(guest=guest, image_path="", extracted_payload={})
            id_document_id = id_document.id

            if face_photo_b64:
                content = self._decode_b64_image(face_photo_b64)
                if content:
                    id_document.face_photo.save(f"guest_{guest_id}_face.jpg", content, save=True)

            if signature_b64:
                content = self._decode_b64_image(signature_b64)
                if content:
                    id_document.signature_photo.save(
                        f"guest_{guest_id}_signature.jpg", content, save=True
                    )

        return Response(
            {
                "scan_log_id": scan_log.id,
                "scan_status": status_value,
                "duration_ms": duration_ms,
                "id_document_id": id_document_id,
                "suggested_fields": suggested_fields,
                "raw_payload": raw_payload,
                "error": error_message,
            }
        )

    def _decode_b64_image(self, value: str):
        try:
            raw = (value or "").strip()
            if not raw:
                return None
            if raw.startswith("data:"):
                raw = raw.split(",", 1)[1]
            decoded = base64.b64decode(raw, validate=False)
            if not decoded:
                return None
            return ContentFile(decoded)
        except Exception:
            return None

    def _build_guest_updates_from_document_scan_payload(self, raw_payload: dict):
        meta = raw_payload.get("metapodaci") if isinstance(raw_payload.get("metapodaci"), dict) else {}
        guest = raw_payload.get("podaci_gosta") if isinstance(raw_payload.get("podaci_gosta"), dict) else {}
        biom = raw_payload.get("biometrija") if isinstance(raw_payload.get("biometrija"), dict) else {}

        method = str(meta.get("metoda_ocitanja", "")).strip().upper()
        if method not in {"OCR", "NFC"}:
            method = ""

        device_id = str(meta.get("uredaj_id", "")).strip()

        scanned_at = timezone.now()
        scanned_raw = str(meta.get("vrijeme_skeniranja", "")).strip()
        if scanned_raw:
            try:
                scanned_at = timezone.datetime.fromisoformat(scanned_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        def as_str(key: str) -> str:
            val = guest.get(key)
            return str(val).strip() if val is not None else ""

        updates = {}
        first_name = as_str("ime")
        last_name = as_str("prezime")
        if first_name:
            updates["first_name"] = first_name
        if last_name:
            updates["last_name"] = last_name

        doc_no = as_str("broj_dokumenta")
        if doc_no:
            updates["document_number"] = doc_no

        sex = as_str("spol")
        if sex:
            updates["sex"] = sex

        oib = as_str("oib")
        if oib:
            updates["personal_id_number"] = oib

        dob = as_str("datum_rodenja")
        if dob:
            parsed = parse_date(dob)
            if parsed:
                updates["date_of_birth"] = parsed

        doe = as_str("datum_isteka")
        if doe:
            parsed = parse_date(doe)
            if parsed:
                updates["date_of_expiry"] = parsed

        nat = as_str("drzavljanstvo").upper()
        if nat == "HRV":
            nat = "HR"
        if len(nat) > 2:
            nat = nat[:2]
        if nat:
            updates["nationality"] = nat

        issue_iso3 = as_str("drzava_izdavanja").upper()
        if issue_iso3:
            updates["document_country_iso3"] = issue_iso3[:3]
            if issue_iso3[:3] == "HRV":
                updates["document_country_iso2"] = "HR"

        adresa = as_str("adresa")
        if adresa:
            updates["address"] = adresa

        tip = str(meta.get("tip_dokumenta", "")).strip().lower()
        if tip == "passport":
            updates["document_type"] = "Putovnica"
        elif tip == "national_id":
            updates["document_type"] = "Osobna iskaznica"

        mrz = str(raw_payload.get("sirovi_mrz", "")).strip()
        if mrz:
            updates["mrz_raw_text"] = mrz
            updates["mrz_verified"] = True

        face_photo_b64 = str(biom.get("fotografija_b64", "")).strip()
        signature_b64 = str(biom.get("potpis_b64", "")).strip()

        suggested_fields = {
            "first_name": first_name,
            "last_name": last_name,
            "document_number": doc_no,
            "nationality": nat,
            "date_of_birth": dob,
            "address": adresa,
        }
        suggested_fields = {k: v for k, v in suggested_fields.items() if v}

        return suggested_fields, updates, face_photo_b64, signature_b64, scanned_at, method, device_id

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


## NOTE:
## Legacy OCR log/stats endpoints removed. The app now ingests scans via
## `DocumentScanIngestView` and stores a single scan log record per request.
