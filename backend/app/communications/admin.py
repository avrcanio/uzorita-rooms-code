from django.contrib import admin

from .models import (
    EmailAttachment,
    GuestConversation,
    GuestMessage,
    InboundEmail,
    OutboundEmail,
    ParseError,
)


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
        "reservation",
        "message_id",
    )
    raw_id_fields = ("reservation",)
    list_filter = ("parse_status", "source", "received_at")
    search_fields = ("message_id", "sender", "subject")
    readonly_fields = ("created_at", "updated_at")
    inlines = [EmailAttachmentInline, ParseErrorInline]


@admin.register(OutboundEmail)
class OutboundEmailAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "to_email",
        "subject",
        "status",
        "sent_at",
        "reservation",
        "guest",
    )
    list_filter = ("status", "created_at")
    search_fields = ("to_email", "subject", "smtp_message_id")
    raw_id_fields = ("reservation", "guest", "conversation", "sent_by")
    readonly_fields = ("created_at", "updated_at")


class GuestMessageInline(admin.TabularInline):
    model = GuestMessage
    extra = 0
    readonly_fields = (
        "direction",
        "body_text",
        "inbound_email",
        "outbound_email",
        "sent_by",
        "created_at",
    )
    fields = readonly_fields
    can_delete = False


@admin.register(GuestConversation)
class GuestConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "reservation", "updated_at", "created_at")
    search_fields = ("reservation__external_id",)
    raw_id_fields = ("reservation",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [GuestMessageInline]


@admin.register(GuestMessage)
class GuestMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "direction",
        "created_at",
        "sent_by",
    )
    list_filter = ("direction", "created_at")
    search_fields = (
        "body_text",
        "conversation__reservation__external_id",
    )
    raw_id_fields = ("conversation", "inbound_email", "outbound_email", "sent_by")


@admin.register(ParseError)
class ParseErrorAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "code", "inbound_email")
    list_filter = ("code", "created_at")
    search_fields = (
        "message",
        "inbound_email__subject",
        "inbound_email__message_id",
    )
