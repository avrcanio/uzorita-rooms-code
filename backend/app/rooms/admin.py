from django.contrib import admin
from django.utils.html import format_html

from .models import (
    PropertyInfo,
    Room,
    RoomType,
    RoomTypePhoto,
    RoomTypePricingPlan,
    RoomTypePricingRule,
)


class RoomTypePhotoInline(admin.TabularInline):
    model = RoomTypePhoto
    extra = 1
    readonly_fields = ("preview",)
    fields = ("preview", "image", "is_primary", "sort_order", "is_active")
    ordering = ("sort_order", "id")

    @admin.display(description="Preview")
    def preview(self, obj: RoomTypePhoto) -> str:
        if not obj or not getattr(obj, "image", None):
            return ""
        try:
            url = obj.image.url
        except Exception:
            return ""
        return format_html(
            '<a href="{}" target="_blank" rel="noreferrer">'
            '<img src="{}" style="height:48px;width:auto;border-radius:6px;object-fit:cover;" />'
            "</a>",
            url,
            url,
        )


class RoomTypePricingPlanInline(admin.TabularInline):
    model = RoomTypePricingPlan
    extra = 0
    fields = (
        "code",
        "name",
        "currency",
        "base_price_per_night",
        "valid_from",
        "valid_to",
        "is_default",
        "is_active",
    )
    ordering = ("-is_default", "code")


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "is_active", "size_m2", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (RoomTypePhotoInline,)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "room_type", "is_active", "updated_at")
    list_filter = ("is_active", "room_type")
    search_fields = ("code", "room_type__code")
    readonly_fields = ("created_at", "updated_at")
    inlines = (RoomTypePricingPlanInline,)


class RoomTypePricingRuleInline(admin.TabularInline):
    model = RoomTypePricingRule
    extra = 1
    fields = (
        "sort_order",
        "name",
        "rule_type",
        "price_per_night",
        "adults_count",
        "children_count",
        "min_stay_nights",
        "valid_from",
        "valid_to",
        "month",
        "iso_week",
        "weekday",
        "specific_date",
        "is_active",
    )
    ordering = ("sort_order", "id")


@admin.register(RoomTypePricingPlan)
class RoomTypePricingPlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room",
        "code",
        "name",
        "currency",
        "base_price_per_night",
        "is_default",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "is_default", "currency", "room")
    search_fields = ("code", "name", "room__code", "room__room_type__code")
    readonly_fields = ("created_at", "updated_at")
    inlines = (RoomTypePricingRuleInline,)


@admin.register(RoomTypePricingRule)
class RoomTypePricingRuleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pricing_plan",
        "rule_type",
        "name",
        "price_per_night",
        "adults_count",
        "children_count",
        "min_stay_nights",
        "is_active",
        "sort_order",
        "updated_at",
    )
    list_filter = ("rule_type", "is_active", "pricing_plan__room")
    search_fields = ("name", "pricing_plan__code", "pricing_plan__room__code", "pricing_plan__room__room_type__code")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PropertyInfo)
class PropertyInfoAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code",)
    readonly_fields = ("created_at", "updated_at")
