import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communications", "0003_inboundemail_parsed_payload"),
        ("reception", "0015_evisitor_integration"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GuestConversation",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reservation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="guest_conversation",
                        to="reception.reservation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Razgovor s gostom",
                "verbose_name_plural": "Razgovori s gostima",
                "ordering": ["-updated_at", "-id"],
            },
        ),
        migrations.AddField(
            model_name="outboundemail",
            name="reservation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="outbound_emails",
                to="reception.reservation",
            ),
        ),
        migrations.AddField(
            model_name="outboundemail",
            name="guest",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="outbound_emails",
                to="reception.guest",
            ),
        ),
        migrations.AddField(
            model_name="outboundemail",
            name="conversation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="outbound_emails",
                to="communications.guestconversation",
            ),
        ),
        migrations.AddField(
            model_name="outboundemail",
            name="smtp_message_id",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="outboundemail",
            name="in_reply_to",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="outboundemail",
            name="sent_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="outbound_emails_sent",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="outboundemail",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "U redu"),
                    ("sent", "Poslano"),
                    ("failed", "Neuspjelo"),
                ],
                default="queued",
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="GuestMessage",
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
                    "direction",
                    models.CharField(
                        choices=[
                            ("inbound", "Dolazna"),
                            ("outbound", "Odlazna"),
                        ],
                        max_length=16,
                    ),
                ),
                ("body_text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="communications.guestconversation",
                    ),
                ),
                (
                    "inbound_email",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guest_messages",
                        to="communications.inboundemail",
                    ),
                ),
                (
                    "outbound_email",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guest_messages",
                        to="communications.outboundemail",
                    ),
                ),
                (
                    "sent_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guest_messages_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Poruka gosta",
                "verbose_name_plural": "Poruke gosta",
                "ordering": ["created_at", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="guestmessage",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        direction="inbound",
                        inbound_email__isnull=False,
                        outbound_email__isnull=True,
                    )
                    | models.Q(
                        direction="outbound",
                        outbound_email__isnull=False,
                        inbound_email__isnull=True,
                    )
                ),
                name="guestmessage_direction_email_link",
            ),
        ),
    ]
