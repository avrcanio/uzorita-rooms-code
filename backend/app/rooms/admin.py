from django.contrib import admin
from django.utils.html import format_html

from .models import Room, RoomType, RoomTypePhoto


class RoomTypePhotoInline(admin.TabularInline):
    model = RoomTypePhoto
    extra = 1
    readonly_fields = ("preview",)
    fields = ("preview", "image", "sort_order", "is_active")
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
