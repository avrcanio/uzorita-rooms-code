from rest_framework import serializers

from communications.models import GuestMessage


class GuestMessageSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    sent_by_name = serializers.SerializerMethodField()
    from_email = serializers.SerializerMethodField()

    class Meta:
        model = GuestMessage
        fields = (
            "id",
            "direction",
            "body_text",
            "created_at",
            "status",
            "sent_by_name",
            "from_email",
        )
        read_only_fields = fields

    def get_status(self, obj) -> str | None:
        if obj.outbound_email_id:
            return obj.outbound_email.status
        return None

    def get_sent_by_name(self, obj) -> str | None:
        user = obj.sent_by
        if user is None:
            return None
        full_name = f"{user.first_name} {user.last_name}".strip()
        return full_name or user.get_username()

    def get_from_email(self, obj) -> str | None:
        if obj.inbound_email_id:
            return (obj.inbound_email.sender or "").strip() or None
        return None


class GuestMessageCreateSerializer(serializers.Serializer):
    body_text = serializers.CharField(trim_whitespace=True, allow_blank=False)
