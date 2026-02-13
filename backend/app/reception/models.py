from django.db import models


class ReservationStatus(models.TextChoices):
    EXPECTED = "expected", "Ocekuje dolazak"
    CHECKED_IN = "checked_in", "Prijavljen"
    CHECKED_OUT = "checked_out", "Odjavljen"
    CANCELED = "canceled", "Otkazan"


class Reservation(models.Model):
    external_id = models.CharField(max_length=128, unique=True)
    room_name = models.CharField(max_length=128)
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    status = models.CharField(
        max_length=32,
        choices=ReservationStatus.choices,
        default=ReservationStatus.EXPECTED,
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["check_in_date", "id"]
        verbose_name = "Rezervacija"
        verbose_name_plural = "Rezervacije"

    def __str__(self) -> str:
        return f"{self.external_id} ({self.room_name})"


class Guest(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="guests",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    document_number = models.CharField(max_length=64, blank=True)
    nationality = models.CharField(max_length=2, blank=True)
    sex = models.CharField(max_length=16, blank=True)
    address = models.TextField(blank=True)
    date_of_issue = models.DateField(null=True, blank=True)
    date_of_expiry = models.DateField(null=True, blank=True)
    issuing_authority = models.CharField(max_length=255, blank=True)
    personal_id_number = models.CharField(max_length=64, blank=True)
    document_additional_number = models.CharField(max_length=64, blank=True)
    additional_personal_id_number = models.CharField(max_length=64, blank=True)
    document_code = models.CharField(max_length=16, blank=True)
    document_type = models.CharField(max_length=64, blank=True)
    document_country = models.CharField(max_length=64, blank=True)
    document_country_iso2 = models.CharField(max_length=2, blank=True)
    document_country_iso3 = models.CharField(max_length=3, blank=True)
    document_country_numeric = models.CharField(max_length=8, blank=True)
    mrz_raw_text = models.TextField(blank=True)
    mrz_verified = models.BooleanField(null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["reservation_id", "-is_primary", "last_name", "first_name"]
        verbose_name = "Gost"
        verbose_name_plural = "Gosti"
        constraints = [
            models.UniqueConstraint(
                fields=["reservation"],
                condition=models.Q(is_primary=True),
                name="unique_primary_guest_per_reservation",
            )
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class IDDocument(models.Model):
    guest = models.ForeignKey(
        Guest,
        on_delete=models.CASCADE,
        related_name="id_documents",
    )
    image_path = models.CharField(max_length=500)
    extracted_payload = models.JSONField(default=dict, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        verbose_name = "Identifikacijski dokument"
        verbose_name_plural = "Identifikacijski dokumenti"

    def __str__(self) -> str:
        return f"IDDocument #{self.id} for guest {self.guest_id}"


class OcrProvider(models.TextChoices):
    MICROBLINK = "microblink", "Microblink"


class OcrScanStatus(models.TextChoices):
    OK = "ok", "Uspjesno"
    FAILED = "failed", "Neuspjesno"


class OcrScanLog(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="ocr_scan_logs",
    )
    guest = models.ForeignKey(
        Guest,
        on_delete=models.CASCADE,
        related_name="ocr_scan_logs",
    )
    provider = models.CharField(max_length=32, choices=OcrProvider.choices)
    status = models.CharField(max_length=16, choices=OcrScanStatus.choices)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    suggested_fields = models.JSONField(default=dict, blank=True)
    corrected_fields = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocr_scan_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "OCR scan log"
        verbose_name_plural = "OCR scan logs"

    def __str__(self) -> str:
        return f"OCR {self.provider} {self.status} #{self.id}"
