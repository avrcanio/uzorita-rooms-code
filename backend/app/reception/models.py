import uuid

from django.db import models
from django.core.exceptions import ValidationError


class ReservationStatus(models.TextChoices):
    EXPECTED = "expected", "Ocekuje dolazak"
    CHECKED_IN = "checked_in", "Prijavljen"
    CHECKED_OUT = "checked_out", "Odjavljen"
    CANCELED = "canceled", "Otkazan"


class BookingChannelStatus(models.TextChoices):
    OK = "ok", "OK"
    CANCELLED_BY_GUEST = "cancelled_by_guest", "Otkazao gost"


class ImportSource(models.TextChoices):
    BOOKING_XLS = "booking_xls", "Booking XLS"
    BOOKING_EMAIL = "booking_email", "Booking email"
    BOOKING_ICAL = "booking_ical", "Booking iCal"


class Reservation(models.Model):
    external_id = models.CharField(max_length=128, unique=True)
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    status = models.CharField(
        max_length=32,
        choices=ReservationStatus.choices,
        default=ReservationStatus.EXPECTED,
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR")
    booker_name = models.CharField(max_length=255, blank=True)
    booked_at = models.DateTimeField(null=True, blank=True)
    booking_status = models.CharField(max_length=64, blank=True)
    units_count = models.PositiveSmallIntegerField(null=True, blank=True)
    persons_count = models.PositiveSmallIntegerField(null=True, blank=True)
    adults_count = models.PositiveSmallIntegerField(null=True, blank=True)
    children_count = models.PositiveSmallIntegerField(null=True, blank=True)
    children_ages = models.CharField(max_length=128, blank=True)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_status = models.CharField(max_length=128, blank=True)
    payment_provider = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    booker_country = models.CharField(max_length=8, blank=True)
    travel_purpose = models.CharField(max_length=128, blank=True)
    booking_device = models.CharField(max_length=64, blank=True)
    nights_count = models.PositiveSmallIntegerField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    booker_address = models.TextField(blank=True)
    booker_phone = models.CharField(max_length=64, blank=True)
    import_source = models.CharField(
        max_length=32,
        choices=ImportSource.choices,
        blank=True,
    )
    details_pending = models.BooleanField(
        default=False,
        verbose_name="Čeka detalje (XLS)",
        help_text="Email stub: samo Booking broj; puni podaci dolaze iz XLS/XML importa.",
    )
    imported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["check_in_date", "id"]
        verbose_name = "Rezervacija"
        verbose_name_plural = "Rezervacije"

    def __str__(self) -> str:
        from reception.reservation_units import joined_room_names

        label = joined_room_names(self)
        if label:
            return f"{self.external_id} ({label})"
        return str(self.external_id)

    def clean(self):
        super().clean()

        if self.check_in_date and self.check_out_date and self.check_in_date >= self.check_out_date:
            raise ValidationError({"check_out_date": "Check-out date must be after check-in date."})


class ReservationUnit(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="units",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    room_name = models.CharField(max_length=256)
    room_type = models.ForeignKey(
        "rooms.RoomType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservation_units",
    )
    room = models.ForeignKey(
        "rooms.Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservation_units",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["reservation_id", "sort_order", "id"]
        verbose_name = "Jedinica rezervacije"
        verbose_name_plural = "Jedinice rezervacije"
        constraints = [
            models.UniqueConstraint(
                fields=["reservation", "sort_order"],
                name="unique_unit_sort_order_per_reservation",
            )
        ]

    def __str__(self) -> str:
        return f"{self.reservation.external_id} #{self.sort_order}: {self.room_name}"

    def clean(self):
        super().clean()
        reservation = self.reservation

        if self.room_id and self.room_type_id and self.room.room_type_id != self.room_type_id:
            raise ValidationError({"room": "Selected room does not match selected room type."})

        if reservation.status == ReservationStatus.CANCELED:
            return
        if not self.room_id or not reservation.check_in_date or not reservation.check_out_date:
            return

        conflict = (
            ReservationUnit.objects.filter(room_id=self.room_id)
            .exclude(pk=self.pk)
            .exclude(reservation__status=ReservationStatus.CANCELED)
            .filter(
                reservation__check_in_date__lt=reservation.check_out_date,
                reservation__check_out_date__gt=reservation.check_in_date,
            )
            .select_related("reservation")
            .order_by("reservation__check_in_date", "id")
            .first()
        )
        if conflict:
            raise ValidationError(
                {
                    "room": (
                        f"Room {self.room} is already booked for an overlapping period "
                        f"({conflict.reservation.check_in_date} -> {conflict.reservation.check_out_date}, "
                        f"external_id={conflict.reservation.external_id})."
                    )
                }
            )


class Guest(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="guests",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
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
    evisitor_status = models.CharField(max_length=16, blank=True, default="")
    evisitor_registration_id = models.UUIDField(null=True, blank=True)
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
    face_photo = models.ImageField(upload_to="id_documents/faces/", null=True, blank=True)
    signature_photo = models.ImageField(upload_to="id_documents/signatures/", null=True, blank=True)
    front_photo = models.ImageField(upload_to="id_documents/front/", null=True, blank=True)
    back_photo = models.ImageField(upload_to="id_documents/back/", null=True, blank=True)
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


class EvisitorGuestStatus(models.TextChoices):
    NOT_SENT = "not_sent", "Nije poslano"
    PENDING = "pending", "U tijeku"
    SENT = "sent", "Poslano"
    CHECKED_OUT = "checked_out", "Odjavljeno"
    FAILED = "failed", "Neuspjesno"


class EvisitorSubmission(models.Model):
    guest = models.ForeignKey(
        Guest,
        on_delete=models.CASCADE,
        related_name="evisitor_submissions",
    )
    registration_id = models.UUIDField()
    status = models.CharField(max_length=16, choices=EvisitorGuestStatus.choices)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evisitor_submissions",
    )
    error_user_message = models.TextField(blank=True)
    error_system_message = models.TextField(blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "eVisitor prijava"
        verbose_name_plural = "eVisitor prijave"

    def __str__(self) -> str:
        return f"eVisitor {self.status} guest={self.guest_id} #{self.id}"


class DocumentScanStatus(models.TextChoices):
    OK = "ok", "Uspjesno"
    FAILED = "failed", "Neuspjesno"


class DocumentScanLog(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="document_scan_logs",
    )
    guest = models.ForeignKey(
        Guest,
        on_delete=models.CASCADE,
        related_name="document_scan_logs",
    )
    status = models.CharField(max_length=16, choices=DocumentScanStatus.choices)
    method = models.CharField(max_length=8, blank=True, default="")
    device_id = models.CharField(max_length=128, blank=True, default="")
    scanned_at = models.DateTimeField(null=True, blank=True)
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
        related_name="document_scan_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Document scan log"
        verbose_name_plural = "Document scan logs"

    def __str__(self) -> str:
        return f"Scan {self.method or '?'} {self.status} #{self.id}"


class BookingIcalFeed(models.Model):
    """Booking.com iCal feed configuration (one row per channel listing, e.g. R1)."""

    code = models.CharField(max_length=32, unique=True)
    room_type = models.ForeignKey(
        "rooms.RoomType",
        on_delete=models.PROTECT,
        related_name="booking_ical_feeds",
    )
    booking_listing_name = models.CharField(max_length=256)
    export_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    import_url = models.URLField(max_length=2048, blank=True)
    last_import_at = models.DateTimeField(null=True, blank=True)
    last_import_etag = models.CharField(max_length=256, blank=True)
    min_occupied_units_to_block = models.PositiveSmallIntegerField(
        default=2,
        help_text="Export blocks Booking when at least this many physical rooms are occupied (R1: 2 = K1+K2).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Booking iCal feed"
        verbose_name_plural = "Booking iCal feeds"

    def __str__(self) -> str:
        return f"{self.code} ({self.booking_listing_name})"

    def regenerate_export_token(self) -> None:
        self.export_token = uuid.uuid4()
        self.save(update_fields=["export_token", "updated_at"])


class BookingExtranetStatus(models.TextChoices):
    DISCONNECTED = "disconnected", "Nije povezano"
    CONNECTING = "connecting", "Povezivanje"
    NEEDS_2FA = "needs_2fa", "Potreban 2FA kod"
    NEEDS_HUMAN = "needs_human", "Potreban ručni korak (CAPTCHA)"
    CONNECTED = "connected", "Povezano"
    EXPIRED = "expired", "Sesija istekla"
    ERROR = "error", "Greška"


class BookingExtranetConnection(models.Model):
    """Singleton per deployment: Playwright storage_state session for Booking.com extranet."""

    SOLO_PK = 1

    status = models.CharField(
        max_length=32,
        choices=BookingExtranetStatus.choices,
        default=BookingExtranetStatus.DISCONNECTED,
    )
    hotel_id = models.CharField(max_length=32, blank=True, default="")
    storage_version = models.PositiveIntegerField(default=0)
    storage_path = models.CharField(
        max_length=256,
        default="state.enc",
        help_text="Relative path under BOOKING_EXTRANET_STORAGE_DIR.",
    )
    last_ok_at = models.DateTimeField(null=True, blank=True)
    last_connect_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    connected_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_extranet_connections",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Booking extranet veza"
        verbose_name_plural = "Booking extranet veza"

    def __str__(self) -> str:
        return f"Booking extranet ({self.get_status_display()})"

    @classmethod
    def get_solo(cls) -> "BookingExtranetConnection":
        obj, _created = cls.objects.get_or_create(
            pk=cls.SOLO_PK,
            defaults={
                "status": BookingExtranetStatus.DISCONNECTED,
                "storage_path": "state.enc",
            },
        )
        return obj

    def save(self, *args, **kwargs):
        self.pk = self.SOLO_PK
        super().save(*args, **kwargs)


class BookingExtranetJobKind(models.TextChoices):
    CONNECT = "connect", "Povezivanje"
    HEALTH = "health", "Health check"
    FETCH_RESERVATION = "fetch_reservation", "Dohvat rezervacije"


class BookingExtranetJobStatus(models.TextChoices):
    PENDING = "pending", "Na čekanju"
    NEEDS_HUMAN = "needs_human", "Potreban ručni korak"
    RUNNING = "running", "U tijeku"
    DONE = "done", "Završeno"
    FAILED = "failed", "Neuspjelo"


class BookingExtranetJob(models.Model):
    kind = models.CharField(max_length=32, choices=BookingExtranetJobKind.choices)
    status = models.CharField(
        max_length=32,
        choices=BookingExtranetJobStatus.choices,
        default=BookingExtranetJobStatus.PENDING,
    )
    inbound_email = models.ForeignKey(
        "communications.InboundEmail",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_extranet_jobs",
    )
    booking_number = models.CharField(max_length=32, blank=True, default="")
    target_url = models.TextField(blank=True, default="")
    result_payload = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    celery_task_id = models.CharField(max_length=64, blank=True, default="")
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_extranet_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Booking extranet zadatak"
        verbose_name_plural = "Booking extranet zadaci"

    def __str__(self) -> str:
        return f"{self.kind} ({self.status}) #{self.pk}"
