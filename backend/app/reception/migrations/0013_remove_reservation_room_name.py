from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("reception", "0012_remove_reservation_room_and_room_type"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="reservation",
            name="room_name",
        ),
    ]
