from django.contrib import admin

from .models import Guest, IDDocument, OcrScanLog, Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "external_id",
        "room_name",
        "check_in_date",
        "check_out_date",
        "status",
        "currency",
        "total_amount",
    )
    list_filter = ("status", "currency", "check_in_date")
    search_fields = ("external_id", "room_name")


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reservation",
        "first_name",
        "last_name",
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
        "document_number",
        "personal_id_number",
        "reservation__external_id",
    )


@admin.register(IDDocument)
class IDDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "guest", "verified_at", "verified_by", "created_at")
    list_filter = ("verified_at",)
    search_fields = ("guest__first_name", "guest__last_name", "image_path")


@admin.register(OcrScanLog)
class OcrScanLogAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "status", "reservation", "guest", "duration_ms", "created_at")
    list_filter = ("provider", "status", "created_at")
    search_fields = (
        "reservation__external_id",
        "guest__first_name",
        "guest__last_name",
        "error_message",
    )
