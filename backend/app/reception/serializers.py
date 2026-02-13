from rest_framework import serializers

from .models import Guest, OcrScanLog, Reservation


class GuestLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = (
            "id",
            "first_name",
            "last_name",
            "is_primary",
            "nationality",
            "document_number",
            "date_of_expiry",
        )


class ReservationTimelineSerializer(serializers.ModelSerializer):
    guests = GuestLiteSerializer(many=True, read_only=True)
    guests_count = serializers.IntegerField(read_only=True)
    primary_guest_name = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = (
            "id",
            "external_id",
            "room_name",
            "check_in_date",
            "check_out_date",
            "status",
            "total_amount",
            "currency",
            "guests_count",
            "primary_guest_name",
            "guests",
        )

    def get_primary_guest_name(self, obj):
        primary_guest = next((g for g in obj.guests.all() if g.is_primary), None)
        if primary_guest:
            return f"{primary_guest.first_name} {primary_guest.last_name}".strip()
        return ""


class GuestDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = (
            "id",
            "reservation",
            "first_name",
            "last_name",
            "date_of_birth",
            "document_number",
            "nationality",
            "sex",
            "address",
            "date_of_issue",
            "date_of_expiry",
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
            "mrz_verified",
            "is_primary",
        )
        read_only_fields = ("id", "reservation")

    def update(self, instance, validated_data):
        if validated_data.get("is_primary", False):
            Guest.objects.filter(reservation=instance.reservation).exclude(pk=instance.pk).update(
                is_primary=False
            )
        return super().update(instance, validated_data)


class OcrScanLogSerializer(serializers.ModelSerializer):
    reservation_external_id = serializers.CharField(source="reservation.external_id", read_only=True)
    guest_name = serializers.SerializerMethodField()

    class Meta:
        model = OcrScanLog
        fields = (
            "id",
            "provider",
            "status",
            "duration_ms",
            "reservation",
            "reservation_external_id",
            "guest",
            "guest_name",
            "error_message",
            "suggested_fields",
            "corrected_fields",
            "created_at",
        )

    def get_guest_name(self, obj):
        return f"{obj.guest.first_name} {obj.guest.last_name}".strip()
