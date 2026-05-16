from rest_framework import serializers

from .models import Guest, Reservation, ReservationUnit


class GuestLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = (
            "id",
            "first_name",
            "last_name",
            "email",
            "is_primary",
            "nationality",
            "document_number",
            "date_of_expiry",
        )


class ReservationUnitSerializer(serializers.ModelSerializer):
    room_code = serializers.CharField(source="room.code", read_only=True, default=None)

    class Meta:
        model = ReservationUnit
        fields = (
            "id",
            "sort_order",
            "room_name",
            "room_type",
            "room",
            "room_code",
            "amount",
        )


class ReservationTimelineSerializer(serializers.ModelSerializer):
    guests = GuestLiteSerializer(many=True, read_only=True)
    units = ReservationUnitSerializer(many=True, read_only=True)
    guests_count = serializers.IntegerField(read_only=True)
    primary_guest_name = serializers.SerializerMethodField()
    primary_guest_nationality_iso2 = serializers.SerializerMethodField()
    room_codes = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = (
            "id",
            "external_id",
            "room_name",
            "units",
            "room_codes",
            "check_in_date",
            "check_out_date",
            "status",
            "booking_status",
            "total_amount",
            "currency",
            "booker_name",
            "booker_phone",
            "booker_country",
            "units_count",
            "persons_count",
            "adults_count",
            "children_count",
            "notes",
            "payment_status",
            "nights_count",
            "booked_at",
            "import_source",
            "guests_count",
            "primary_guest_name",
            "primary_guest_nationality_iso2",
            "guests",
        )

    def get_primary_guest_name(self, obj):
        primary_guest = next(
            (g for g in obj.guests.all() if g.is_primary),
            None,
        )
        if primary_guest:
            return f"{primary_guest.first_name} {primary_guest.last_name}".strip()
        return ""

    def get_primary_guest_nationality_iso2(self, obj):
        primary_guest = next(
            (g for g in obj.guests.all() if g.is_primary),
            None,
        )
        if not primary_guest:
            return ""
        return (primary_guest.nationality or "").strip().upper()

    def get_room_codes(self, obj):
        codes = []
        for unit in obj.units.all():
            if unit.room_id and unit.room:
                codes.append(unit.room.code)
        return codes


class GuestDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = (
            "id",
            "reservation",
            "first_name",
            "last_name",
            "email",
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
            (
                Guest.objects.filter(reservation=instance.reservation)
                .exclude(pk=instance.pk)
                .update(is_primary=False)
            )
        return super().update(instance, validated_data)


# Legacy OcrScanLogSerializer removed (old web scanning flow).
