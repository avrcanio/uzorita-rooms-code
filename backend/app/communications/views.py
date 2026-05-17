from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from communications.guest_messaging import send_guest_message
from communications.models import GuestMessage
from communications.serializers import (
    GuestMessageCreateSerializer,
    GuestMessageSerializer,
)
from reception.models import Reservation


class ReservationGuestMessageListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_reservation(self) -> Reservation:
        reservation = Reservation.objects.filter(pk=self.kwargs["pk"]).first()
        if reservation is None:
            raise NotFound("Rezervacija nije pronadena.")
        return reservation

    def get_queryset(self):
        self.get_reservation()
        reservation_id = self.kwargs["pk"]
        return (
            GuestMessage.objects.filter(
                conversation__reservation_id=reservation_id,
            )
            .select_related("outbound_email", "inbound_email", "sent_by")
            .order_by("created_at", "id")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return GuestMessageCreateSerializer
        return GuestMessageSerializer

    def create(self, request, *args, **kwargs):
        self.get_reservation()
        serializer = GuestMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = send_guest_message(
                reservation_id=self.kwargs["pk"],
                body_text=serializer.validated_data["body_text"],
                user=request.user,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "error_dict") and exc.error_dict:
                raise DRFValidationError(exc.error_dict) from exc
            raise DRFValidationError(exc.messages) from exc

        message = GuestMessage.objects.select_related(
            "outbound_email",
            "inbound_email",
            "sent_by",
        ).get(pk=message.pk)
        output = GuestMessageSerializer(
            message,
            context=self.get_serializer_context(),
        )
        return Response(output.data, status=201)
