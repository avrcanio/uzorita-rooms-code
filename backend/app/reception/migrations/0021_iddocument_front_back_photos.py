from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reception", "0020_bookingextranetjob"),
    ]

    operations = [
        migrations.AddField(
            model_name="iddocument",
            name="front_photo",
            field=models.ImageField(blank=True, null=True, upload_to="id_documents/front/"),
        ),
        migrations.AddField(
            model_name="iddocument",
            name="back_photo",
            field=models.ImageField(blank=True, null=True, upload_to="id_documents/back/"),
        ),
    ]
