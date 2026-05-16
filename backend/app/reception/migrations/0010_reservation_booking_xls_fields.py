from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reception", "0009_documentscanlog_rename"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reservation",
            name="room_name",
            field=models.CharField(max_length=512),
        ),
        migrations.AddField(
            model_name="reservation",
            name="booker_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="reservation",
            name="booked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="booking_status",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="reservation",
            name="units_count",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="persons_count",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="adults_count",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="children_count",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="children_ages",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="reservation",
            name="commission_percent",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="commission_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="payment_status",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="reservation",
            name="payment_provider",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="reservation",
            name="notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="booker_country",
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name="reservation",
            name="travel_purpose",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="reservation",
            name="booking_device",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="reservation",
            name="nights_count",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="canceled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="booker_address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="booker_phone",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="reservation",
            name="import_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("booking_xls", "Booking XLS"),
                    ("booking_email", "Booking email"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="imported_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
