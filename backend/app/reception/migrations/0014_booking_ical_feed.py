import uuid

import django.db.models.deletion
from django.db import migrations, models


def seed_r1_feed(apps, schema_editor):
    RoomType = apps.get_model("rooms", "RoomType")
    BookingIcalFeed = apps.get_model("reception", "BookingIcalFeed")
    seeds = [
        ("r1", "R1", "Luxury Room Uzorita - R1", 2),
        ("r2", "R2", "Luxury Room Uzorita - R2", 1),
        ("r3", "R3", "Luxury Room Uzorita - R3", 1),
        ("r6", "R1", "R-6 DELUXE KING", 1),
    ]
    for code, rt_code, listing_name, min_units in seeds:
        rt = RoomType.objects.filter(code=rt_code).first()
        if not rt:
            continue
        BookingIcalFeed.objects.get_or_create(
            code=code,
            defaults={
                "room_type": rt,
                "booking_listing_name": listing_name,
                "export_token": uuid.uuid4(),
                "is_active": True,
                "min_occupied_units_to_block": min_units,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0013_room_pricing_per_room"),
        ("reception", "0013_remove_reservation_room_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingIcalFeed",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True)),
                ("booking_listing_name", models.CharField(max_length=256)),
                ("export_token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("import_url", models.URLField(blank=True, max_length=2048)),
                ("last_import_at", models.DateTimeField(blank=True, null=True)),
                ("last_import_etag", models.CharField(blank=True, max_length=256)),
                (
                    "min_occupied_units_to_block",
                    models.PositiveSmallIntegerField(
                        default=2,
                        help_text="Export blocks Booking when at least this many physical rooms are occupied (R1: 2 = K1+K2).",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "room_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="booking_ical_feeds",
                        to="rooms.roomtype",
                    ),
                ),
            ],
            options={
                "verbose_name": "Booking iCal feed",
                "verbose_name_plural": "Booking iCal feeds",
            },
        ),
        migrations.RunPython(seed_r1_feed, migrations.RunPython.noop),
    ]
