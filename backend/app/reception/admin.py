from django.contrib import admin, messages

from .models import BookingIcalFeed, DocumentScanLog, Guest, IDDocument, Reservation, ReservationUnit


class ReservationUnitInline(admin.TabularInline):
    model = ReservationUnit
    extra = 0
    fields = ("sort_order", "room_name", "room_type", "room", "amount")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    inlines = [ReservationUnitInline]
    list_display = (
        "id",
        "external_id",
        "booker_name",
        "check_in_date",
        "check_out_date",
        "status",
        "booking_status",
        "units_count",
        "currency",
        "total_amount",
        "import_source",
    )
    list_filter = ("status", "booking_status", "import_source", "currency", "check_in_date")
    search_fields = ("external_id", "booker_name", "booker_phone", "units__room_name")


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reservation",
        "first_name",
        "last_name",
        "email",
        "is_primary",
        "nationality",
        "document_number",
        "personal_id_number",
        "date_of_expiry",
    )
    list_filter = ("is_primary", "nationality", "document_type")
    search_fields = (
        "first_name",
        "last_name",
        "email",
        "document_number",
        "personal_id_number",
        "reservation__external_id",
    )


@admin.register(IDDocument)
class IDDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "guest", "verified_at", "verified_by", "created_at")
    list_filter = ("verified_at",)
    search_fields = ("guest__first_name", "guest__last_name", "image_path")


@admin.register(BookingIcalFeed)
class BookingIcalFeedAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "booking_listing_name",
        "room_type",
        "is_active",
        "last_import_at",
        "min_occupied_units_to_block",
    )
    list_filter = ("is_active", "room_type")
    readonly_fields = ("export_token", "last_import_at", "last_import_etag", "created_at", "updated_at")
    actions = ["regenerate_export_token"]

    @admin.action(description="Regenerate export token (invalidates old Booking import URL)")
    def regenerate_export_token(self, request, queryset):
        count = 0
        for feed in queryset:
            feed.regenerate_export_token()
            count += 1
        self.message_user(request, f"Regenerated export token for {count} feed(s).", messages.SUCCESS)


@admin.register(DocumentScanLog)
class DocumentScanLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "method",
        "status",
        "reservation",
        "guest",
        "duration_ms",
        "created_at",
    )
    list_filter = ("status", "method", "created_at")
    search_fields = (
        "reservation__external_id",
        "guest__first_name",
        "guest__last_name",
        "error_message",
        "device_id",
    )
