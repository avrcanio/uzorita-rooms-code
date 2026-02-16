from __future__ import annotations

from rest_framework import serializers


class PublicAvailabilityQuerySerializer(serializers.Serializer):
    checkin = serializers.DateField()
    checkout = serializers.DateField()
    adults = serializers.IntegerField(min_value=1)
    children = serializers.IntegerField(min_value=0, required=False, default=0)

    def validate(self, attrs):
        if attrs["checkout"] <= attrs["checkin"]:
            raise serializers.ValidationError({"checkout": "Checkout mora biti nakon checkin datuma."})
        return attrs


class PublicRoomCalendarQuerySerializer(serializers.Serializer):
    month = serializers.RegexField(
        regex=r"^\d{4}-\d{2}$",
        help_text="Format: YYYY-MM",
    )
    adults = serializers.IntegerField(min_value=1, required=False, default=2)
    children = serializers.IntegerField(min_value=0, required=False, default=0)


class PublicPricingSerializer(serializers.Serializer):
    currency = serializers.CharField()
    accommodation_total = serializers.CharField(allow_null=True, required=False)
    accommodation_nightly = serializers.CharField(allow_null=True, required=False)


class PublicAvailabilityRoomSerializer(serializers.Serializer):
    room_id = serializers.IntegerField()
    room_code = serializers.CharField()
    room_type_id = serializers.IntegerField()
    room_type_code = serializers.CharField()
    available = serializers.BooleanField()
    capacity = serializers.IntegerField()
    can_host_party = serializers.BooleanField()
    pricing = PublicPricingSerializer()


class PublicComboAllocationSerializer(serializers.Serializer):
    room_id = serializers.IntegerField()
    room_code = serializers.CharField()
    adults = serializers.IntegerField()
    children = serializers.IntegerField()


class PublicAvailabilityComboSerializer(serializers.Serializer):
    code = serializers.CharField()
    rooms_count = serializers.IntegerField()
    allocation = PublicComboAllocationSerializer(many=True)
    pricing = PublicPricingSerializer()


class PublicAvailabilityResponseSerializer(serializers.Serializer):
    checkin = serializers.DateField()
    checkout = serializers.DateField()
    nights = serializers.IntegerField()
    adults = serializers.IntegerField()
    children = serializers.IntegerField()
    rooms = PublicAvailabilityRoomSerializer(many=True)
    combos = PublicAvailabilityComboSerializer(many=True)


class PublicRoomCalendarDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    available = serializers.BooleanField()
    pricing = PublicPricingSerializer()


class PublicRoomCalendarResponseSerializer(serializers.Serializer):
    room_id = serializers.IntegerField()
    room_code = serializers.CharField()
    month = serializers.CharField()
    adults = serializers.IntegerField()
    children = serializers.IntegerField()
    days = PublicRoomCalendarDaySerializer(many=True)
