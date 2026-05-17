import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_solo_connection(apps, schema_editor):
    BookingExtranetConnection = apps.get_model("reception", "BookingExtranetConnection")
    BookingExtranetConnection.objects.get_or_create(
        pk=1,
        defaults={
            "status": "disconnected",
            "storage_path": "state.enc",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("reception", "0016_reservation_details_pending"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingExtranetConnection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("disconnected", "Nije povezano"),
                            ("connecting", "Povezivanje"),
                            ("needs_2fa", "Potreban 2FA kod"),
                            ("connected", "Povezano"),
                            ("expired", "Sesija istekla"),
                            ("error", "Greška"),
                        ],
                        default="disconnected",
                        max_length=32,
                    ),
                ),
                ("hotel_id", models.CharField(blank=True, default="", max_length=32)),
                ("storage_version", models.PositiveIntegerField(default=0)),
                (
                    "storage_path",
                    models.CharField(
                        default="state.enc",
                        help_text="Relative path under BOOKING_EXTRANET_STORAGE_DIR.",
                        max_length=256,
                    ),
                ),
                ("last_ok_at", models.DateTimeField(blank=True, null=True)),
                ("last_connect_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connected_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="booking_extranet_connections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Booking extranet veza",
                "verbose_name_plural": "Booking extranet veza",
            },
        ),
        migrations.RunPython(create_solo_connection, migrations.RunPython.noop),
    ]
