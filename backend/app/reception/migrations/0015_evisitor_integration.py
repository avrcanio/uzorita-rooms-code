import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reception", "0014_booking_ical_feed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="guest",
            name="evisitor_registration_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="guest",
            name="evisitor_status",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.CreateModel(
            name="EvisitorSubmission",
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
                ("registration_id", models.UUIDField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("not_sent", "Nije poslano"),
                            ("pending", "U tijeku"),
                            ("sent", "Poslano"),
                            ("failed", "Neuspjesno"),
                        ],
                        max_length=16,
                    ),
                ),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("error_user_message", models.TextField(blank=True)),
                ("error_system_message", models.TextField(blank=True)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("response_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "guest",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evisitor_submissions",
                        to="reception.guest",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="evisitor_submissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "eVisitor prijava",
                "verbose_name_plural": "eVisitor prijave",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
