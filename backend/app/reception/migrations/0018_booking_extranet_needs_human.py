from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reception", "0017_booking_extranet_connection"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookingextranetconnection",
            name="status",
            field=models.CharField(
                choices=[
                    ("disconnected", "Nije povezano"),
                    ("connecting", "Povezivanje"),
                    ("needs_2fa", "Potreban 2FA kod"),
                    ("needs_human", "Potreban ručni korak (CAPTCHA)"),
                    ("connected", "Povezano"),
                    ("expired", "Sesija istekla"),
                    ("error", "Greška"),
                ],
                default="disconnected",
                max_length=32,
            ),
        ),
    ]
