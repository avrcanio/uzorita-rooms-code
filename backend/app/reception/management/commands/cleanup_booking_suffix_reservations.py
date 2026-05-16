from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from reception.models import Guest, IDDocument, Reservation, ReservationStatus
from reception.reservation_units import sync_reservation_units
from rooms.allocation import assign_rooms_for_reservation


class Command(BaseCommand):
    help = (
        "Cancel legacy email suffix reservations (BOOKING-2, BOOKING-3) when base booking exists. "
        "Optionally delete suffix rows without check-in data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--external-id",
            type=str,
            default=None,
            help="Process only this booking number (e.g. 6566035917)",
        )
        parser.add_argument(
            "--delete-empty",
            action="store_true",
            help="Delete suffix reservation if it has no guests with documents and is not checked in",
        )
        parser.add_argument(
            "--delete-suffix",
            action="store_true",
            help="Delete all suffix reservations (BOOKING-2, -3, …) when base booking exists",
        )
        parser.add_argument(
            "--sync-units",
            action="store_true",
            help="Rebuild ReservationUnit rows for base reservations after cleanup",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        only_id = (options.get("external_id") or "").strip()
        delete_empty = options["delete_empty"]
        delete_suffix = options["delete_suffix"]
        sync_units = options["sync_units"]

        suffix_qs = Reservation.objects.filter(external_id__regex=r"^.+-\d+$")
        if only_id:
            suffix_qs = suffix_qs.filter(external_id__startswith=f"{only_id}-")

        canceled = 0
        deleted = 0
        synced = 0

        for suffix in suffix_qs.select_related().order_by("external_id"):
            base_id = suffix.external_id.rsplit("-", 1)[0]
            base = Reservation.objects.filter(external_id=base_id).first()
            if base is None:
                self.stdout.write(self.style.WARNING(f"skip {suffix.external_id}: base {base_id} missing"))
                continue

            has_docs = IDDocument.objects.filter(guest__reservation=suffix).exists()
            if suffix.status in (ReservationStatus.CHECKED_IN, ReservationStatus.CHECKED_OUT) or has_docs:
                if suffix.status != ReservationStatus.CANCELED:
                    suffix.status = ReservationStatus.CANCELED
                    suffix.save(update_fields=["status", "updated_at"])
                    canceled += 1
                    self.stdout.write(f"canceled {suffix.external_id} (has check-in/documents)")
                continue

            if delete_suffix:
                suffix.delete()
                deleted += 1
                self.stdout.write(f"deleted {suffix.external_id}")
                continue

            if delete_empty and not Guest.objects.filter(reservation=suffix).exists():
                suffix.delete()
                deleted += 1
                self.stdout.write(f"deleted empty {suffix.external_id}")
                continue

            if suffix.status != ReservationStatus.CANCELED:
                suffix.status = ReservationStatus.CANCELED
                suffix.save(update_fields=["status", "updated_at"])
                canceled += 1
                self.stdout.write(f"canceled {suffix.external_id}")

        if sync_units:
            base_qs = Reservation.objects.all()
            if only_id:
                base_qs = base_qs.filter(Q(external_id=only_id) | Q(external_id__startswith=f"{only_id}-"))
            base_qs = base_qs.exclude(external_id__regex=r"^.+-\d+$")
            for reservation in base_qs.prefetch_related("units"):
                unit_count = reservation.units.count()
                expected = reservation.units_count or 1
                if expected <= 1 or unit_count >= expected:
                    continue
                joined = ", ".join(
                    u.room_name for u in reservation.units.order_by("sort_order", "id") if u.room_name
                )
                if not joined:
                    continue
                sync_reservation_units(reservation=reservation, room_name=joined)
                assign_rooms_for_reservation(reservation_id=reservation.id)
                synced += 1
                self.stdout.write(f"synced units for {reservation.external_id}")

        self.stdout.write(
            self.style.SUCCESS(f"done: canceled={canceled} deleted={deleted} units_synced={synced}")
        )
