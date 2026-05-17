from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0015_roomtypepricingrule_children_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="propertyinfo",
            name="evisitor_facility_code",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Šifra objekta u sustavu eVisitor (Facility).",
                max_length=32,
            ),
        ),
    ]
