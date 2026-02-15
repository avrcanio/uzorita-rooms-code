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


class OutboundEmail(models.Model):
    to_email = models.CharField(max_length=1000)
    cc = models.CharField(max_length=1000, blank=True)
    bcc = models.CharField(max_length=1000, blank=True)
    subject = models.CharField(max_length=998)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, default="queued")
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Odlazni email"
        verbose_name_plural = "Odlazni emailovi"

    def __str__(self) -> str:
        return f"{self.subject} -> {self.to_email}"


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
