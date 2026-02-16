from __future__ import annotations

import datetime

from django.core.exceptions import ValidationError
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
    is_primary = models.BooleanField(default=False, help_text="Oznaci fotografiju kao glavnu.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["room_type"],
                condition=models.Q(is_primary=True),
                name="unique_primary_photo_per_room_type",
            )
        ]
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


class RoomTypePricingPlan(models.Model):
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="pricing_plans",
    )
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=128)
    currency = models.CharField(max_length=3, default="EUR")
    base_price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["room__code", "-is_default", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["room"],
                condition=models.Q(is_default=True),
                name="unique_default_pricing_plan_per_room",
            ),
            models.UniqueConstraint(
                fields=["room", "code"],
                name="unique_pricing_plan_code_per_room",
            ),
        ]
        verbose_name = "Cjenik sobe"
        verbose_name_plural = "Cjenici soba"

    def __str__(self) -> str:
        return f"{self.room.code} / {self.code}"

    def clean(self) -> None:
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValidationError({"valid_to": "Datum završetka mora biti nakon datuma početka."})
        if self.currency:
            self.currency = self.currency.upper()


class RoomTypePricingRule(models.Model):
    TYPE_SEASON = "season"
    TYPE_MONTH = "month"
    TYPE_WEEK = "week"
    TYPE_DAY = "day"
    TYPE_CHOICES = (
        (TYPE_SEASON, "Sezona"),
        (TYPE_MONTH, "Mjesec"),
        (TYPE_WEEK, "Tjedan"),
        (TYPE_DAY, "Dan"),
    )
    WEEKDAY_CHOICES = (
        (1, "Ponedjeljak"),
        (2, "Utorak"),
        (3, "Srijeda"),
        (4, "Četvrtak"),
        (5, "Petak"),
        (6, "Subota"),
        (7, "Nedjelja"),
    )

    pricing_plan = models.ForeignKey(
        RoomTypePricingPlan,
        on_delete=models.CASCADE,
        related_name="rules",
    )
    name = models.CharField(max_length=128, blank=True, default="")
    rule_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    adults_count = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Ako je postavljeno, pravilo vrijedi samo za točan broj odraslih.",
    )
    children_count = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Ako je postavljeno, pravilo vrijedi samo za točan broj djece.",
    )
    min_stay_nights = models.PositiveIntegerField(null=True, blank=True)

    # Shared optional range filter for any rule type.
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    # Month rule.
    month = models.PositiveSmallIntegerField(null=True, blank=True)

    # Week rule (ISO week: 1-53).
    iso_week = models.PositiveSmallIntegerField(null=True, blank=True)

    # Day rule can target weekday and/or a specific date.
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES, null=True, blank=True)
    specific_date = models.DateField(null=True, blank=True)

    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pricing_plan__room__code", "sort_order", "id"]
        verbose_name = "Pravilo cijene"
        verbose_name_plural = "Pravila cijena"

    def __str__(self) -> str:
        label = self.name or self.get_rule_type_display()
        return f"{self.pricing_plan} / {label}"

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            errors["valid_to"] = "Datum završetka mora biti nakon datuma početka."
        if self.adults_count is not None and self.adults_count < 1:
            errors["adults_count"] = "Broj odraslih mora biti 1 ili više."
        if self.children_count is not None and self.children_count < 0:
            errors["children_count"] = "Broj djece ne može biti negativan."
        if self.month is not None and not 1 <= self.month <= 12:
            errors["month"] = "Mjesec mora biti između 1 i 12."
        if self.iso_week is not None and not 1 <= self.iso_week <= 53:
            errors["iso_week"] = "Tjedan mora biti između 1 i 53."

        if self.rule_type == self.TYPE_SEASON:
            if not self.valid_from or not self.valid_to:
                errors["valid_from"] = "Sezonsko pravilo mora imati valid_from i valid_to."
        elif self.rule_type == self.TYPE_MONTH:
            if self.month is None:
                errors["month"] = "Mjesečno pravilo mora imati month."
            if self.iso_week is not None or self.weekday is not None or self.specific_date is not None:
                errors["rule_type"] = "Mjesečno pravilo ne može imati tjedan/dan/specifični datum."
        elif self.rule_type == self.TYPE_WEEK:
            if self.iso_week is None:
                errors["iso_week"] = "Tjedno pravilo mora imati iso_week."
            if self.month is not None or self.weekday is not None or self.specific_date is not None:
                errors["rule_type"] = "Tjedno pravilo ne može imati month/dan/specifični datum."
        elif self.rule_type == self.TYPE_DAY:
            if self.weekday is None and self.specific_date is None:
                errors["weekday"] = "Dnevno pravilo mora imati weekday ili specific_date."
            if self.month is not None or self.iso_week is not None:
                errors["rule_type"] = "Dnevno pravilo ne može imati month ili iso_week."

        if errors:
            raise ValidationError(errors)

    @property
    def priority(self) -> int:
        # Dan > Tjedan > Mjesec > Sezona
        if self.rule_type == self.TYPE_DAY:
            return 4
        if self.rule_type == self.TYPE_WEEK:
            return 3
        if self.rule_type == self.TYPE_MONTH:
            return 2
        return 1

    def matches_date(self, target_date: datetime.date) -> bool:
        if not self.is_active:
            return False
        if self.valid_from and target_date < self.valid_from:
            return False
        if self.valid_to and target_date > self.valid_to:
            return False

        if self.rule_type == self.TYPE_SEASON:
            return True
        if self.rule_type == self.TYPE_MONTH:
            return self.month == target_date.month
        if self.rule_type == self.TYPE_WEEK:
            return self.iso_week == target_date.isocalendar().week
        if self.rule_type == self.TYPE_DAY:
            if self.specific_date and target_date == self.specific_date:
                return True
            if self.weekday and self.weekday == target_date.isoweekday():
                return True
        return False

    def matches_occupancy(self, adults: int | None) -> bool:
        return self.matches_occupancy_with_children(adults=adults, children=None)

    def matches_occupancy_with_children(self, adults: int | None, children: int | None) -> bool:
        if self.adults_count is not None:
            if adults is None or self.adults_count != adults:
                return False
        if self.children_count is not None:
            if children is None or self.children_count != children:
                return False
        return True


class PropertyInfo(models.Model):
    """
    Singleton-ish model for global property data used by the public booking web.

    Keep this small and i18n-friendly. The booking frontend can render it under
    "About this property" and show a Google Maps link/embed.
    """

    # Use a stable code so we can keep multiple properties later if needed.
    code = models.CharField(max_length=64, unique=True, default="default")

    name_i18n = models.JSONField(default=dict, blank=True)
    about_i18n = models.JSONField(default=dict, blank=True)  # long text / paragraphs
    company_info_i18n = models.JSONField(default=dict, blank=True)  # managed-by text
    neighborhood_i18n = models.JSONField(default=dict, blank=True)

    most_popular_facilities_i18n = models.JSONField(default=dict, blank=True)  # dict[str, list[str]]

    # Property surroundings data (nearby attractions, transport, airports, beaches, etc.).
    # Structure: dict[str, dict[str, list[dict]]] e.g. {"en": {"top_attractions":[{"name":"...", "distance_m":800}]}}
    surroundings_i18n = models.JSONField(default=dict, blank=True)

    address_i18n = models.JSONField(default=dict, blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Contact
    whatsapp_phone = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="WhatsApp broj u E.164 formatu, npr. +385998388513",
    )
    google_analytics_measurement_id = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Google Analytics 4 Measurement ID, npr. G-PXHBKJD09B",
    )

    google_maps_place_id = models.CharField(max_length=255, blank=True, default="")
    # Google Maps URLs can be very long; keep generous max_length.
    google_maps_url = models.URLField(blank=True, default="", max_length=2000)
    google_maps_embed_url = models.URLField(blank=True, default="", max_length=2000)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Objekt"
        verbose_name_plural = "Objekt"

    def __str__(self) -> str:
        return self.code

    def get_i18n_text(self, field: str, lang: str | None) -> str:
        # Same semantics as RoomType; duplicated to keep model independent.
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
