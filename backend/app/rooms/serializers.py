from rest_framework import serializers

from reception.models import Reservation
from rooms.models import Room, RoomType, RoomTypePhoto


class RoomTypePhotoSerializer(serializers.ModelSerializer):
    caption = serializers.SerializerMethodField()

    class Meta:
        model = RoomTypePhoto
        fields = ("id", "image", "caption", "sort_order")

    def _lang(self) -> str | None:
        return (self.context or {}).get("lang")

    def get_caption(self, obj):
        return obj.get_i18n_text("caption_i18n", self._lang())


class RoomTypeSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    subtitle = serializers.SerializerMethodField()
    beds = serializers.SerializerMethodField()
    highlights = serializers.SerializerMethodField()
    views = serializers.SerializerMethodField()
    amenities = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()

    class Meta:
        model = RoomType
        fields = (
            "id",
            "code",
            "name",
            "subtitle",
            "beds",
            "highlights",
            "views",
            "amenities",
            "photos",
            "size_m2",
            "is_active",
        )

    def _lang(self) -> str | None:
        return (self.context or {}).get("lang")

    def get_name(self, obj):
        return obj.get_i18n_text("name_i18n", self._lang())

    def get_subtitle(self, obj):
        return obj.get_i18n_text("subtitle_i18n", self._lang())

    def get_beds(self, obj):
        return obj.get_i18n_text("beds_i18n", self._lang())

    def get_highlights(self, obj):
        return obj.get_i18n_list("highlights_i18n", self._lang())

    def get_views(self, obj):
        return obj.get_i18n_list("views_i18n", self._lang())

    def get_amenities(self, obj):
        return obj.get_i18n_list("amenities_i18n", self._lang())

    def get_photos(self, obj):
        qs = obj.photos.filter(is_active=True).order_by("sort_order", "id")
        return RoomTypePhotoSerializer(qs, many=True, context=self.context).data


class RoomSerializer(serializers.ModelSerializer):
    room_type_name = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = ("id", "code", "room_type", "room_type_name", "is_active")

    def _lang(self) -> str | None:
        return (self.context or {}).get("lang")

    def get_room_type_name(self, obj):
        return obj.room_type.get_i18n_text("name_i18n", self._lang())


class RoomReservationSerializer(serializers.ModelSerializer):
    primary_guest_name = serializers.SerializerMethodField()
    primary_guest_nationality_iso2 = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = (
            "id",
            "external_id",
            "check_in_date",
            "check_out_date",
            "status",
            "room_name",
            "primary_guest_name",
            "primary_guest_nationality_iso2",
        )

    def get_primary_guest_name(self, obj):
        primary = next((g for g in obj.guests.all() if g.is_primary), None)
        if not primary:
            return ""
        return f"{primary.first_name} {primary.last_name}".strip()

    def get_primary_guest_nationality_iso2(self, obj):
        primary = next((g for g in obj.guests.all() if g.is_primary), None)
        if not primary:
            return ""
        return (primary.nationality or "").strip().upper()
