from __future__ import annotations

from rest_framework import serializers

from rooms.models import PropertyInfo, RoomTypePhoto
from rooms.public_serializers import _slugify


class PublicPropertySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    about = serializers.SerializerMethodField()
    company_info = serializers.SerializerMethodField()
    neighborhood = serializers.SerializerMethodField()
    most_popular_facilities = serializers.SerializerMethodField()
    surroundings = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    primary_room_photos = serializers.SerializerMethodField()

    class Meta:
        model = PropertyInfo
        fields = (
            "id",
            "code",
            "name",
            "about",
            "company_info",
            "neighborhood",
            "most_popular_facilities",
            "surroundings",
            "address",
            "primary_room_photos",
            "latitude",
            "longitude",
            "whatsapp_phone",
            "google_analytics_measurement_id",
            "google_maps_place_id",
            "google_maps_url",
            "google_maps_embed_url",
        )

    def _lang(self) -> str | None:
        return (self.context or {}).get("lang")

    def get_name(self, obj) -> str:
        return obj.get_i18n_text("name_i18n", self._lang())

    def get_about(self, obj) -> str:
        return obj.get_i18n_text("about_i18n", self._lang())

    def get_company_info(self, obj) -> str:
        return obj.get_i18n_text("company_info_i18n", self._lang())

    def get_neighborhood(self, obj) -> str:
        return obj.get_i18n_text("neighborhood_i18n", self._lang())

    def get_most_popular_facilities(self, obj) -> list[str]:
        return obj.get_i18n_list("most_popular_facilities_i18n", self._lang())

    def get_surroundings(self, obj) -> dict:
        data = obj.surroundings_i18n or {}
        lang = (self._lang() or "").strip().lower()
        if isinstance(data, dict):
            # Prefer exact tag, then short tag, then fallback.
            if lang and lang in data and isinstance(data.get(lang), dict):
                return data.get(lang) or {}
            if lang:
                short = lang.split("-", 1)[0]
                if short in data and isinstance(data.get(short), dict):
                    return data.get(short) or {}
            if "en" in data and isinstance(data.get("en"), dict):
                return data.get("en") or {}
            for v in data.values():
                if isinstance(v, dict):
                    return v
        return {}

    def get_address(self, obj) -> str:
        return obj.get_i18n_text("address_i18n", self._lang())

    def get_primary_room_photos(self, obj) -> list[dict]:
        req = (self.context or {}).get("request")
        qs = (
            RoomTypePhoto.objects.filter(
                is_active=True,
                is_primary=True,
                room_type__is_active=True,
            )
            .select_related("room_type")
            .order_by("room_type__code", "sort_order", "id")
        )
        out: list[dict] = []
        for p in qs:
            try:
                url = p.image.url if p.image else ""
            except Exception:
                url = ""
            if req and url:
                url = req.build_absolute_uri(url)
            out.append(
                {
                    "room_type_id": p.room_type_id,
                    "room_type_code": p.room_type.code,
                    "room_type_slug": _slugify(p.room_type.code),
                    "url": url,
                }
            )
        return out
