from django.contrib import admin

from .models import EmailAttachment, InboundEmail, OutboundEmail, ParseError


class EmailAttachmentInline(admin.TabularInline):
    model = EmailAttachment
    extra = 0
    readonly_fields = ("filename", "content_type", "size_bytes", "created_at")
    fields = ("filename", "content_type", "size_bytes", "created_at")


class ParseErrorInline(admin.TabularInline):
    model = ParseError
    extra = 0
    readonly_fields = ("code", "message", "context", "created_at")
    fields = ("code", "message", "context", "created_at")


@admin.register(InboundEmail)
class InboundEmailAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "received_at",
        "sender",
        "subject",
        "parse_status",
        "message_id",
    )
    list_filter = ("parse_status", "source", "received_at")
    search_fields = ("message_id", "sender", "subject")
    readonly_fields = ("created_at", "updated_at")
    inlines = [EmailAttachmentInline, ParseErrorInline]


@admin.register(OutboundEmail)
class OutboundEmailAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "to_email", "subject", "status", "sent_at")
    list_filter = ("status", "created_at")
    search_fields = ("to_email", "subject")


@admin.register(ParseError)
class ParseErrorAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "code", "inbound_email")
    list_filter = ("code", "created_at")
    search_fields = ("message", "inbound_email__subject", "inbound_email__message_id")
