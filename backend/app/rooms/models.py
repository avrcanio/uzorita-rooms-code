from __future__ import annotations

from django.db import models


LANG_FALLBACK = "en"


class RoomType(models.Model):
    # Stable identifier for integrations/parsers, e.g. "R1_DELUXE_KING".
    code = models.CharField(max_length=64, unique=True)

    # Multi-language text blobs; keys are BCP-47-ish short codes ("en", "hr", ...).
    name_i18n = models.JSONField(default=dict, blank=True)
    subtitle_i18n = models.JSONField(default=dict, blank=True)
    beds_i18n = models.JSONField(default=dict, blank=True)
    highlights_i18n = models.JSONField(default=dict, blank=True)  # dict[str, list[str]]
    views_i18n = models.JSONField(default=dict, blank=True)  # dict[str, list[str]]
    amenities_i18n = models.JSONField(default=dict, blank=True)  # dict[str, list[str]]

    size_m2 = models.PositiveIntegerField(null=True, blank=True)

    # Matching helpers for email parsing ("R1 deluxe king", etc.).
    match_aliases = models.JSONField(default=list, blank=True)  # list[str]

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Vrsta sobe"
        verbose_name_plural = "Vrste soba"

    def __str__(self) -> str:
        return self.code

    def get_i18n_text(self, field: str, lang: str | None) -> str:
        data = getattr(self, field) or {}
        if not isinstance(data, dict):
            return ""
        if lang:
            lang_key = lang.lower()
            if lang_key in data and data[lang_key]:
                return str(data[lang_key])
            lang_short = lang_key.split("-", 1)[0]
            if lang_short in data and data[lang_short]:
                return str(data[lang_short])
        if LANG_FALLBACK in data and data[LANG_FALLBACK]:
            return str(data[LANG_FALLBACK])
        # Last resort: first non-empty value.
        for v in data.values():
            if v:
                return str(v)
        return ""

    def get_i18n_list(self, field: str, lang: str | None) -> list[str]:
        data = getattr(self, field) or {}
        if not isinstance(data, dict):
            return []

        def _value_for(key: str) -> list[str]:
            v = data.get(key)
            if not v:
                return []
            if isinstance(v, list):
                return [str(x) for x in v if str(x).strip()]
            return []

        if lang:
            lang_key = lang.lower()
            val = _value_for(lang_key)
            if val:
                return val
            short = lang_key.split("-", 1)[0]
            val = _value_for(short)
            if val:
                return val

        val = _value_for(LANG_FALLBACK)
        if val:
            return val

        for v in data.values():
            if isinstance(v, list) and v:
                return [str(x) for x in v if str(x).strip()]
        return []


class RoomTypePhoto(models.Model):
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to="room_types/photos/%Y/%m/%d/")
    caption_i18n = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Fotografija vrste sobe"
        verbose_name_plural = "Fotografije vrste sobe"

    def __str__(self) -> str:
        return f"{self.room_type.code} photo #{self.id}"

    def get_i18n_text(self, field: str, lang: str | None) -> str:
        # Mirror RoomType i18n helpers for captions.
        data = getattr(self, field) or {}
        if not isinstance(data, dict):
            return ""
        if lang:
            lang_key = lang.lower()
            if lang_key in data and data[lang_key]:
                return str(data[lang_key])
            lang_short = lang_key.split("-", 1)[0]
            if lang_short in data and data[lang_short]:
                return str(data[lang_short])
        if LANG_FALLBACK in data and data[LANG_FALLBACK]:
            return str(data[LANG_FALLBACK])
        for v in data.values():
            if v:
                return str(v)
        return ""


class Room(models.Model):
    # Physical room/unit, e.g. "K1", "K2", "D1", "T1"
    code = models.CharField(max_length=16, unique=True)
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,
        related_name="rooms",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Soba"
        verbose_name_plural = "Sobe"

    def __str__(self) -> str:
        return self.code
