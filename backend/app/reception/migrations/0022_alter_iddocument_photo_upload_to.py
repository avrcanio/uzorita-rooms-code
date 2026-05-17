import reception.document_photo_storage
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reception", "0021_iddocument_front_back_photos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="iddocument",
            name="front_photo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=reception.document_photo_storage.id_document_front_upload_to,
            ),
        ),
        migrations.AlterField(
            model_name="iddocument",
            name="back_photo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=reception.document_photo_storage.id_document_back_upload_to,
            ),
        ),
    ]
