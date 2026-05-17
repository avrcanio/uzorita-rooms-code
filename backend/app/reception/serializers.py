from rest_framework import serializers

from reception.reservation_units import joined_room_names

from .models import Guest, Reservation, ReservationStatus, ReservationUnit


def payment_status_key(raw: str) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return "unknown"
    if "booking" in value:
        return "booking"
    if any(token in value for token in ("plać", "plac", "paid", "naplać", "naplac")):
        return "paid"
    if any(token in value for token in ("neplać", "neplac", "unpaid", "duguje")):
        return "unpaid"
    if "kartic" in value or "card" in value:
        return "card"
    if "gotov" in value or "cash" in value:
        return "cash"
    return "other"


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
    room_name = serializers.SerializerMethodField()
    effective_units_count = serializers.SerializerMethodField()
    payment_status_key = serializers.SerializerMethodField()

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
            "booker_address",
            "booker_country",
            "payment_provider",
            "commission_percent",
            "commission_amount",
            "travel_purpose",
            "booking_device",
            "units_count",
            "effective_units_count",
            "persons_count",
            "adults_count",
            "children_count",
            "children_ages",
            "notes",
            "payment_status",
            "payment_status_key",
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

    def get_room_name(self, obj) -> str:
        return joined_room_names(obj)

    def get_effective_units_count(self, obj) -> int:
        unit_list = list(obj.units.all())
        from_units = len(unit_list)
        from_field = obj.units_count or 0
        return max(from_field, from_units)

    def get_payment_status_key(self, obj) -> str:
        return payment_status_key(obj.payment_status)


_ALLOWED_STATUS_TRANSITIONS = {
    ReservationStatus.EXPECTED: {
        ReservationStatus.CHECKED_IN,
        ReservationStatus.CANCELED,
    },
    ReservationStatus.CHECKED_IN: {ReservationStatus.CHECKED_OUT},
    ReservationStatus.CHECKED_OUT: set(),
    ReservationStatus.CANCELED: set(),
}


class ReservationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = ("status",)

    def validate_status(self, value):
        allowed = {choice[0] for choice in ReservationStatus.choices}
        if value not in allowed:
            raise serializers.ValidationError("Nepoznat status rezervacije.")

        instance = getattr(self, "instance", None)
        if instance is not None:
            current = instance.status
            if value == current:
                return value
            next_allowed = _ALLOWED_STATUS_TRANSITIONS.get(current, set())
            if value not in next_allowed:
                raise serializers.ValidationError(
                    "Nedozvoljen prijelaz statusa rezervacije."
                )
        return value


_GUEST_WRITABLE_FIELDS = (
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


class GuestDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = ("id", "reservation", *_GUEST_WRITABLE_FIELDS)
        read_only_fields = ("id", "reservation")

    def update(self, instance, validated_data):
        if validated_data.get("is_primary", False):
            (
                Guest.objects.filter(reservation=instance.reservation)
                .exclude(pk=instance.pk)
                .update(is_primary=False)
            )
        return super().update(instance, validated_data)


class GuestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = _GUEST_WRITABLE_FIELDS
        extra_kwargs = {
            "first_name": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        first_name = (attrs.get("first_name") or "").strip()
        last_name = (attrs.get("last_name") or "").strip()
        if not first_name:
            attrs["first_name"] = "Novi"
        else:
            attrs["first_name"] = first_name
        if not last_name:
            attrs["last_name"] = "gost"
        else:
            attrs["last_name"] = last_name
        return attrs

    def create(self, validated_data):
        reservation = self.context["reservation"]
        if "is_primary" not in validated_data:
            validated_data["is_primary"] = not Guest.objects.filter(
                reservation=reservation
            ).exists()
        if validated_data.get("is_primary", False):
            Guest.objects.filter(reservation=reservation).update(is_primary=False)
        return Guest.objects.create(reservation=reservation, **validated_data)


# Legacy OcrScanLogSerializer removed (old web scanning flow).
