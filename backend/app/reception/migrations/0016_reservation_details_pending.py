from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reception", "0015_evisitor_integration"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="details_pending",
            field=models.BooleanField(
                default=False,
                help_text="Email stub: samo Booking broj; puni podaci dolaze iz XLS/XML importa.",
                verbose_name="Čeka detalje (XLS)",
            ),
        ),
    ]
