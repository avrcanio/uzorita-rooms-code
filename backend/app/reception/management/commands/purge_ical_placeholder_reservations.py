from django.core.management.base import BaseCommand
from django.db import transaction
from reception.ical.placeholders import is_ical_placeholder_external_id
from reception.models import ImportSource, Reservation


class Command(BaseCommand):
    help = (
        "Delete iCal placeholder reservations (external_id ical-… without Booking number). "
        "These are availability/export noise, not guest bookings."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print how many rows would be deleted.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        qs = Reservation.objects.filter(
            import_source=ImportSource.BOOKING_ICAL,
            external_id__startswith="ical-",
        )
        placeholders = [r for r in qs.only("id", "external_id") if is_ical_placeholder_external_id(r.external_id)]
        count = len(placeholders)

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No iCal placeholder reservations found."))
            return

        sample = ", ".join(r.external_id for r in placeholders[:5])
        if count > 5:
            sample += f", … (+{count - 5} more)"

        if dry_run:
            self.stdout.write(f"Would delete {count} placeholder reservation(s): {sample}")
            return

        with transaction.atomic():
            deleted, _ = Reservation.objects.filter(
                pk__in=[r.id for r in placeholders]
            ).delete()

        remaining = Reservation.objects.filter(
            import_source=ImportSource.BOOKING_ICAL,
            external_id__startswith="ical-",
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} placeholder reservation(s) "
                f"(cascade rows: {deleted}; remaining ical- prefix: {remaining})."
            )
        )
        self.stdout.write(f"Sample: {sample}")
