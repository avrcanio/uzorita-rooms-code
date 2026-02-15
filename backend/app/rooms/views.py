from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from reception.models import Reservation, ReservationStatus
from rooms.models import Room, RoomType
from rooms.serializers import RoomReservationSerializer, RoomSerializer, RoomTypeSerializer


def _pick_lang(request) -> str:
    # Priority: ?lang= -> Accept-Language -> default en
    raw = (request.query_params.get("lang") or "").strip()
    if raw:
        return raw
    header = (request.headers.get("Accept-Language") or "").strip()
    if not header:
        return "en"
    # Take first language tag.
    return header.split(",")[0].strip() or "en"


class RoomTypeListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RoomTypeSerializer

    def get_queryset(self):
        return RoomType.objects.filter(is_active=True).order_by("code")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = _pick_lang(self.request)
        return ctx


class RoomListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RoomSerializer

    def get_queryset(self):
        return Room.objects.filter(is_active=True).select_related("room_type").order_by("code")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = _pick_lang(self.request)
        return ctx


class RoomCalendarView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RoomReservationSerializer

    def get_queryset(self):
        room_id = self.kwargs["room_id"]
        qs = (
            Reservation.objects.filter(room_id=room_id)
            .exclude(status=ReservationStatus.CANCELED)
            .prefetch_related("guests")
            .order_by("check_in_date", "id")
        )

        from_raw = (self.request.query_params.get("from") or "").strip()
        to_raw = (self.request.query_params.get("to") or "").strip()
        date_from = parse_date(from_raw) if from_raw else None
        date_to = parse_date(to_raw) if to_raw else None
        if date_from:
            qs = qs.filter(check_out_date__gt=date_from)
        if date_to:
            qs = qs.filter(check_in_date__lt=date_to)
        return qs
