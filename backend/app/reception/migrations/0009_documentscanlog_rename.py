from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("reception", "0008_iddocument_photos_and_scan_meta"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ocrscanlog",
            name="provider",
        ),
        migrations.RenameModel(
            old_name="OcrScanLog",
            new_name="DocumentScanLog",
        ),
        migrations.AlterField(
            model_name="documentscanlog",
            name="guest",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="document_scan_logs",
                to="reception.guest",
            ),
        ),
        migrations.AlterField(
            model_name="documentscanlog",
            name="reservation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="document_scan_logs",
                to="reception.reservation",
            ),
        ),
        migrations.AlterField(
            model_name="documentscanlog",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="document_scan_logs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name="documentscanlog",
            options={
                "ordering": ["-created_at", "-id"],
                "verbose_name": "Document scan log",
                "verbose_name_plural": "Document scan logs",
            },
        ),
    ]
