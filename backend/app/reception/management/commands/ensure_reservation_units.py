from django.core.management.base import BaseCommand
from django.db.models import Count

from reception.models import Reservation
from reception.reservation_units import sync_reservation_units
from rooms.allocation import assign_rooms_for_reservation


class Command(BaseCommand):
    help = "Ensure every reservation has ReservationUnit rows derived from room_name."

    def add_arguments(self, parser):
        parser.add_argument(
            "--assign-rooms",
            action="store_true",
            help="Run room allocation for each reservation after syncing units",
        )
        parser.add_argument(
            "--external-id",
            type=str,
            default=None,
            help="Process only this booking external_id",
        )

    def handle(self, *args, **options):
        assign_rooms = options["assign_rooms"]
        external_id = (options.get("external_id") or "").strip()

        qs = Reservation.objects.annotate(_unit_count=Count("units")).order_by("id")
        if external_id:
            qs = qs.filter(external_id=external_id)

        created_units = 0
        assigned = 0
        warnings = 0

        for reservation in qs.iterator():
            if not (reservation.room_name or "").strip():
                self.stdout.write(
                    self.style.WARNING(f"skip {reservation.external_id}: empty room_name")
                )
                warnings += 1
                continue

            before = reservation.units.count()
            if before == 0:
                sync_reservation_units(reservation=reservation, room_name=reservation.room_name)
                created_units += 1

            if assign_rooms:
                assign_rooms_for_reservation(reservation_id=reservation.id)
                assigned += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"done: created_unit_sets={created_units} assigned={assigned} warnings={warnings}"
            )
        )
