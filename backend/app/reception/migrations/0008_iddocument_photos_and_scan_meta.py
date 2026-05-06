from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reception", "0007_reservation_room_reservation_room_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="iddocument",
            name="face_photo",
            field=models.ImageField(blank=True, null=True, upload_to="id_documents/faces/"),
        ),
        migrations.AddField(
            model_name="iddocument",
            name="signature_photo",
            field=models.ImageField(blank=True, null=True, upload_to="id_documents/signatures/"),
        ),
        migrations.AddField(
            model_name="ocrscanlog",
            name="device_id",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="ocrscanlog",
            name="method",
            field=models.CharField(blank=True, default="", max_length=8),
        ),
        migrations.AddField(
            model_name="ocrscanlog",
            name="scanned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

