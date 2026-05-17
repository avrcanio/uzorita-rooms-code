from __future__ import annotations

import json

from celery.result import AsyncResult
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework.views import APIView

from reception.booking_extranet.connection_service import (
    can_start_auto_connect,
    can_start_vnc_connect,
    can_verify_2fa,
    connect_mode,
    disconnect_session,
    import_storage_state,
    mark_connecting,
    serialize_connection,
)
from reception.booking_extranet.session_store import BookingExtranetSessionError, validate_storage_state
from reception.booking_extranet.tasks import (
    booking_extranet_start_connect_task,
    booking_extranet_verify_2fa_task,
    check_booking_extranet_session_task,
)
from reception.models import BookingExtranetConnection, BookingExtranetStatus


class BookingExtranetConnectionSerializer(serializers.Serializer):
    status = serializers.CharField()
    hotel_id = serializers.CharField()
    storage_version = serializers.IntegerField()
    last_ok_at = serializers.CharField(allow_null=True)
    last_connect_at = serializers.CharField(allow_null=True)
    last_error = serializers.CharField()
    connected_by = serializers.CharField(allow_null=True)
    updated_at = serializers.CharField(allow_null=True)
    enabled = serializers.BooleanField()
    connect_mode = serializers.CharField()
    has_session = serializers.BooleanField()
    auto_connect_allowed = serializers.BooleanField()
    auto_connect_message = serializers.CharField()
    login_url_configured = serializers.BooleanField()
    vnc_active = serializers.BooleanField()
    vnc_url = serializers.CharField(allow_null=True)
    active_job_id = serializers.IntegerField(allow_null=True)
    vnc_enabled = serializers.BooleanField()


class BookingExtranetFetchReservationSerializer(serializers.Serializer):
    inbound_email_id = serializers.IntegerField(required=False)
    booking_number = serializers.CharField(required=False, allow_blank=True)
    booking_url = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not any(
            [
                attrs.get("inbound_email_id"),
                (attrs.get("booking_number") or "").strip(),
                (attrs.get("booking_url") or "").strip(),
            ]
        ):
            raise serializers.ValidationError(
                "Pošaljite inbound_email_id, booking_number ili booking_url."
            )
        return attrs


class BookingExtranetVerify2faSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)


class BookingExtranetImportStateSerializer(serializers.Serializer):
    storage_state = serializers.JSONField(required=False)
    hotel_id = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField(required=False)

    def validate(self, attrs):
        if not attrs.get("storage_state") and not attrs.get("file"):
            raise serializers.ValidationError(
                "Pošaljite storage_state JSON ili datoteku (file)."
            )
        return attrs


def _connection_payload() -> dict:
    return serialize_connection(BookingExtranetConnection.get_solo())


def _task_poll_payload(task_id: str) -> dict:
    result = AsyncResult(task_id)
    payload: dict = {
        "task_id": task_id,
        "state": result.state,
        "ready": result.ready(),
    }
    if result.ready():
        if result.successful():
            payload["result"] = result.result
            if isinstance(result.result, dict) and "connection" in result.result:
                payload["connection"] = result.result["connection"]
            else:
                payload["connection"] = _connection_payload()
        else:
            payload["error"] = str(result.result) if result.result else "Task failed"
            payload["connection"] = _connection_payload()
    else:
        payload["connection"] = _connection_payload()
    return payload


@method_decorator(xframe_options_exempt, name="dispatch")
class BookingExtranetVncAuthView(APIView):
    """Traefik ForwardAuth: 2xx allows WebSocket/noVNC, 401 denies."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        from reception.booking_extranet.vnc import extract_vnc_token_from_request, validate_vnc_token

        if not settings.BOOKING_EXTRANET_VNC_ENABLED:
            return HttpResponse(status=503)

        token = extract_vnc_token_from_request(request)
        if not token:
            return HttpResponse(status=401)

        if validate_vnc_token(token):
            return HttpResponse(status=200)

        if request.user.is_authenticated and validate_vnc_token(
            token, user_id=request.user.id
        ):
            return HttpResponse(status=200)

        return HttpResponse(status=401)


class BookingExtranetVncPrepareView(APIView):
    """Issue a fresh VNC token (iframe) without starting full connect."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reception"])
    def post(self, request):
        from reception.booking_extranet.vnc import issue_vnc_token

        if not settings.BOOKING_EXTRANET_VNC_ENABLED:
            return Response(
                {"detail": "VNC nije omogućen."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue_vnc_token(user_id=request.user.id)
        return Response(_connection_payload())


class BookingExtranetVncContinueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reception"])
    def post(self, request):
        from celery.exceptions import TimeoutError as CeleryTimeoutError
        from reception.booking_extranet.tasks import booking_extranet_vnc_continue_task

        if not settings.BOOKING_EXTRANET_VNC_ENABLED:
            return Response(
                {"detail": "VNC nije omogućen."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        async_result = booking_extranet_vnc_continue_task.delay(user_id=request.user.id)
        try:
            payload = async_result.get(timeout=60)
        except CeleryTimeoutError:
            return Response(
                {"detail": "Provjera na workeru traje predugo — osvježite status za nekoliko sekundi."},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )

        if payload.get("error"):
            return Response(
                {"detail": payload["error"], "connection": payload.get("connection")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(payload.get("connection", _connection_payload()))


class BookingExtranetConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reception"], responses={200: BookingExtranetConnectionSerializer})
    def get(self, request):
        return Response(_connection_payload())


class BookingExtranetStartConnectView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reception"])
    def post(self, request):
        if not settings.BOOKING_EXTRANET_ENABLED:
            return Response(
                {"detail": "BOOKING_EXTRANET_ENABLED nije true."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        auto_ok, auto_reason = can_start_auto_connect()
        vnc_ok, vnc_reason = can_start_vnc_connect()
        if not auto_ok and not vnc_ok:
            return Response(
                {"detail": vnc_reason or auto_reason},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mark_connecting(user=request.user)
        async_result = booking_extranet_start_connect_task.delay(user_id=request.user.id)
        return Response(
            {"task_id": async_result.id, "connection": _connection_payload()},
            status=status.HTTP_202_ACCEPTED,
        )


class BookingExtranetStartConnectPollView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reception"])
    def get(self, request, task_id: str):
        return Response(_task_poll_payload(task_id))


class BookingExtranetVerify2faView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(tags=["Reception"], request=BookingExtranetVerify2faSerializer)
    def post(self, request):
        if not settings.BOOKING_EXTRANET_ENABLED:
            return Response(
                {"detail": "BOOKING_EXTRANET_ENABLED nije true."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conn = BookingExtranetConnection.get_solo()
        verify_ok, verify_reason = can_verify_2fa(conn)
        if not verify_ok:
            return Response(
                {"detail": verify_reason, "connection": serialize_connection(conn)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BookingExtranetVerify2faSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"].strip()

        mark_connecting(user=request.user)
        async_result = booking_extranet_verify_2fa_task.delay(
            code=code,
            user_id=request.user.id,
        )
        return Response(
            {"task_id": async_result.id, "connection": _connection_payload()},
            status=status.HTTP_202_ACCEPTED,
        )


class BookingExtranetDisconnectView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reception"])
    def post(self, request):
        disconnect_session(user=request.user)
        return Response(_connection_payload())


class BookingExtranetCheckView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reception"])
    def post(self, request):
        if not settings.BOOKING_EXTRANET_ENABLED:
            return Response(
                {"detail": "BOOKING_EXTRANET_ENABLED nije true."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        async_result = check_booking_extranet_session_task.delay()
        return Response(
            {"task_id": async_result.id, "connection": _connection_payload()},
            status=status.HTTP_202_ACCEPTED,
        )


class BookingExtranetCheckPollView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reception"])
    def get(self, request, task_id: str):
        return Response(_task_poll_payload(task_id))


class BookingExtranetFetchReservationView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(tags=["Reception"], request=BookingExtranetFetchReservationSerializer)
    def post(self, request):
        from communications.models import InboundEmail
        from reception.booking_extranet.fetch_reservation import resolve_target_url
        from reception.booking_extranet.job_service import create_job
        from reception.booking_extranet.tasks import booking_extranet_fetch_reservation_task
        from reception.models import BookingExtranetJobKind, BookingExtranetStatus

        if not settings.BOOKING_EXTRANET_ENABLED:
            return Response(
                {"detail": "BOOKING_EXTRANET_ENABLED nije true."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conn = BookingExtranetConnection.get_solo()
        if conn.status != BookingExtranetStatus.CONNECTED:
            return Response(
                {"detail": "Extranet sesija nije povezana."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BookingExtranetFetchReservationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        inbound = None
        email_html = ""
        email_text = ""
        booking_number = (data.get("booking_number") or "").strip()
        if data.get("inbound_email_id"):
            inbound = InboundEmail.objects.filter(pk=data["inbound_email_id"]).first()
            if inbound is None:
                return Response(
                    {"detail": "InboundEmail nije pronađen."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            email_html = getattr(inbound, "body_html", "") or ""
            email_text = inbound.body_text or ""
            if not booking_number:
                booking_number = str((inbound.parsed_payload or {}).get("booking_number") or "")

        target_url = resolve_target_url(
            booking_url=(data.get("booking_url") or "").strip() or None,
            booking_number=booking_number or None,
            email_html=email_html,
            email_text=email_text,
        )
        if not target_url:
            return Response(
                {"detail": "Nije moguće sastaviti booking.html URL."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job = create_job(
            kind=BookingExtranetJobKind.FETCH_RESERVATION,
            booking_number=booking_number,
            target_url=target_url,
            inbound_email_id=inbound.id if inbound else None,
            user=request.user,
        )
        async_result = booking_extranet_fetch_reservation_task.delay(
            job_id=job.id,
            user_id=request.user.id,
        )
        job.celery_task_id = async_result.id
        job.save(update_fields=["celery_task_id", "updated_at"])

        return Response(
            {
                "task_id": async_result.id,
                "job_id": job.id,
                "connection": _connection_payload(),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class BookingExtranetFetchReservationPollView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reception"])
    def get(self, request, task_id: str):
        from reception.models import BookingExtranetJob

        payload = _task_poll_payload(task_id)
        job = (
            BookingExtranetJob.objects.filter(celery_task_id=task_id)
            .order_by("-created_at")
            .first()
        )
        if job:
            payload["job_id"] = job.id
            payload["job_status"] = job.status
            if job.result_payload:
                payload["result"] = job.result_payload
        return Response(payload)


class BookingExtranetImportStateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(tags=["Reception"], request=BookingExtranetImportStateSerializer)
    def post(self, request):
        if not settings.BOOKING_EXTRANET_ENABLED:
            return Response(
                {"detail": "BOOKING_EXTRANET_ENABLED nije true."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BookingExtranetImportStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        raw_state = data.get("storage_state")
        if raw_state is None and data.get("file"):
            try:
                raw_state = json.loads(data["file"].read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                return Response(
                    {"detail": f"Nevaljan JSON u datoteci: {exc}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            validate_storage_state(raw_state)
        except BookingExtranetSessionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        hotel_id = (data.get("hotel_id") or "").strip() or None
        conn = import_storage_state(raw_state, user=request.user, hotel_id=hotel_id)
        return Response(serialize_connection(conn))
