import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0015_roomtypepricingrule_children_count"),
        ("reception", "0010_reservation_booking_xls_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReservationUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("room_name", models.CharField(max_length=256)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reservation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="units",
                        to="reception.reservation",
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reservation_units",
                        to="rooms.room",
                    ),
                ),
                (
                    "room_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reservation_units",
                        to="rooms.roomtype",
                    ),
                ),
            ],
            options={
                "verbose_name": "Jedinica rezervacije",
                "verbose_name_plural": "Jedinice rezervacije",
                "ordering": ["reservation_id", "sort_order", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="reservationunit",
            constraint=models.UniqueConstraint(
                fields=("reservation", "sort_order"),
                name="unique_unit_sort_order_per_reservation",
            ),
        ),
    ]
