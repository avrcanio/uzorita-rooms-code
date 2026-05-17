import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communications", "0004_guest_messaging_models"),
        ("reception", "0015_evisitor_integration"),
    ]

    operations = [
        migrations.AddField(
            model_name="inboundemail",
            name="reservation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="inbound_emails",
                to="reception.reservation",
            ),
        ),
    ]
