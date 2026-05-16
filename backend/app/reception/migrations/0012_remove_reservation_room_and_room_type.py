from django.db import migrations


def copy_legacy_room_to_units(apps, schema_editor):
    Reservation = apps.get_model("reception", "Reservation")
    ReservationUnit = apps.get_model("reception", "ReservationUnit")

    for reservation in Reservation.objects.all().iterator():
        room_name = (reservation.room_name or "").strip()
        if not room_name:
            continue

        units = list(
            ReservationUnit.objects.filter(reservation_id=reservation.id).order_by("sort_order", "id")
        )
        if not units:
            segments = [p.strip() for p in room_name.split(",") if p.strip()]
            if not segments:
                segments = [room_name]
            for idx, segment in enumerate(segments):
                ReservationUnit.objects.create(
                    reservation_id=reservation.id,
                    sort_order=idx,
                    room_name=segment,
                    room_type_id=reservation.room_type_id,
                )
            units = list(
                ReservationUnit.objects.filter(reservation_id=reservation.id).order_by("sort_order", "id")
            )

        first = units[0] if units else None
        if first and reservation.room_id and not first.room_id:
            first.room_id = reservation.room_id
            if reservation.room_type_id:
                first.room_type_id = reservation.room_type_id
            first.save(update_fields=["room", "room_type"])

        joined = ", ".join(u.room_name for u in units) if units else room_name
        if reservation.room_name != joined:
            reservation.room_name = joined
            reservation.save(update_fields=["room_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("reception", "0011_reservationunit"),
    ]

    operations = [
        migrations.RunPython(copy_legacy_room_to_units, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="reservation",
            name="room",
        ),
        migrations.RemoveField(
            model_name="reservation",
            name="room_type",
        ),
    ]
