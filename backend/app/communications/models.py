from django.conf import settings
from django.db import models


class ParseStatus(models.TextChoices):
    PENDING = "pending", "Na cekanju"
    PARSED = "parsed", "Parsirano"
    PARTIAL = "partial", "Djelomicno"
    FAILED = "failed", "Neuspjelo"


class InboundEmail(models.Model):
    source = models.CharField(max_length=32, default="imap")
    message_id = models.CharField(max_length=500, unique=True)
    mailbox = models.EmailField()
    sender = models.CharField(max_length=500, blank=True)
    subject = models.CharField(max_length=998, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    raw_headers = models.TextField(blank=True)
    # Normalized parser output (Booking, etc.). Kept for audit/debugging.
    parsed_payload = models.JSONField(default=dict, blank=True)
    parse_status = models.CharField(
        max_length=16,
        choices=ParseStatus.choices,
        default=ParseStatus.PENDING,
    )
    parse_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at", "-id"]
        verbose_name = "Dolazni email"
        verbose_name_plural = "Dolazni emailovi"

    def __str__(self) -> str:
        return f"{self.subject or '(no subject)'} [{self.message_id}]"


class OutboundEmailStatus(models.TextChoices):
    QUEUED = "queued", "U redu"
    SENT = "sent", "Poslano"
    FAILED = "failed", "Neuspjelo"


class OutboundEmail(models.Model):
    reservation = models.ForeignKey(
        "reception.Reservation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="outbound_emails",
    )
    guest = models.ForeignKey(
        "reception.Guest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_emails",
    )
    conversation = models.ForeignKey(
        "communications.GuestConversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_emails",
    )
    to_email = models.CharField(max_length=1000)
    cc = models.CharField(max_length=1000, blank=True)
    bcc = models.CharField(max_length=1000, blank=True)
    subject = models.CharField(max_length=998)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    smtp_message_id = models.CharField(max_length=500, blank=True)
    in_reply_to = models.CharField(max_length=500, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_emails_sent",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=OutboundEmailStatus.choices,
        default=OutboundEmailStatus.QUEUED,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Odlazni email"
        verbose_name_plural = "Odlazni emailovi"

    def __str__(self) -> str:
        return f"{self.subject} -> {self.to_email}"


class GuestConversation(models.Model):
    reservation = models.OneToOneField(
        "reception.Reservation",
        on_delete=models.CASCADE,
        related_name="guest_conversation",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        verbose_name = "Razgovor s gostom"
        verbose_name_plural = "Razgovori s gostima"

    def __str__(self) -> str:
        return f"Razgovor #{self.pk} ({self.reservation.external_id})"


class GuestMessageDirection(models.TextChoices):
    INBOUND = "inbound", "Dolazna"
    OUTBOUND = "outbound", "Odlazna"


class GuestMessage(models.Model):
    conversation = models.ForeignKey(
        GuestConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    direction = models.CharField(
        max_length=16,
        choices=GuestMessageDirection.choices,
    )
    body_text = models.TextField()
    inbound_email = models.ForeignKey(
        InboundEmail,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guest_messages",
    )
    outbound_email = models.ForeignKey(
        OutboundEmail,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guest_messages",
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guest_messages_sent",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "Poruka gosta"
        verbose_name_plural = "Poruke gosta"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        direction=GuestMessageDirection.INBOUND,
                        inbound_email__isnull=False,
                        outbound_email__isnull=True,
                    )
                    | models.Q(
                        direction=GuestMessageDirection.OUTBOUND,
                        outbound_email__isnull=False,
                        inbound_email__isnull=True,
                    )
                ),
                name="guestmessage_direction_email_link",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_direction_display()} @ {self.created_at:%Y-%m-%d %H:%M}"


class EmailAttachment(models.Model):
    inbound_email = models.ForeignKey(
        InboundEmail,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    filename = models.CharField(max_length=500)
    content_type = models.CharField(max_length=255, blank=True)
    content = models.BinaryField(null=True, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["inbound_email_id", "id"]
        verbose_name = "Privitak emaila"
        verbose_name_plural = "Privitci emaila"

    def __str__(self) -> str:
        return self.filename


class ParseError(models.Model):
    inbound_email = models.ForeignKey(
        InboundEmail,
        on_delete=models.CASCADE,
        related_name="parse_errors",
    )
    code = models.CharField(max_length=64)
    message = models.TextField()
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Greska parsiranja"
        verbose_name_plural = "Greske parsiranja"

    def __str__(self) -> str:
        return f"{self.code}: {self.message[:60]}"
