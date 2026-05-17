from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("communications", "0005_inboundemail_reservation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("reception", "0019_alter_evisitorsubmission_status_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingExtranetJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("connect", "Povezivanje"),
                            ("health", "Health check"),
                            ("fetch_reservation", "Dohvat rezervacije"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Na čekanju"),
                            ("needs_human", "Potreban ručni korak"),
                            ("running", "U tijeku"),
                            ("done", "Završeno"),
                            ("failed", "Neuspjelo"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("booking_number", models.CharField(blank=True, default="", max_length=32)),
                ("target_url", models.TextField(blank=True, default="")),
                ("result_payload", models.JSONField(blank=True, null=True)),
                ("error", models.TextField(blank=True, default="")),
                ("celery_task_id", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="booking_extranet_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "inbound_email",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="booking_extranet_jobs",
                        to="communications.inboundemail",
                    ),
                ),
            ],
            options={
                "verbose_name": "Booking extranet zadatak",
                "verbose_name_plural": "Booking extranet zadaci",
                "ordering": ["-created_at"],
            },
        ),
    ]
