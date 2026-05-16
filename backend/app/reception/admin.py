from django.contrib import admin

from .models import DocumentScanLog, Guest, IDDocument, Reservation, ReservationUnit


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
        "room_name",
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
    search_fields = ("external_id", "room_name", "booker_name", "booker_phone")


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
