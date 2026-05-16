from django.core.management.base import BaseCommand, CommandError

from reception.booking_xls_import import import_booking_xls_file


class Command(BaseCommand):
    help = "Import Booking.com XLS export into Reservation (upsert by Broj rezervacije / external_id)."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Path to .xls export file")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report create/update counts without writing to the database",
        )
        parser.add_argument(
            "--only-status",
            type=str,
            default=None,
            help="Import only rows with this Booking status (e.g. ok)",
        )

    def handle(self, *args, **options):
        path = options["path"]
        dry_run = options["dry_run"]
        only_status = options.get("only_status")

        try:
            stats = import_booking_xls_file(
                path,
                dry_run=dry_run,
                only_status=only_status,
            )
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Import failed: {exc}") from exc

        mode = "DRY RUN" if dry_run else "IMPORT"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: total={stats.get('total', 0)} "
                f"created={stats.get('created', 0)} "
                f"updated={stats.get('updated', 0)} "
                f"skipped={stats.get('skipped', 0)} "
                f"errors={len(stats.get('errors', []))}"
            )
        )
        for err in stats.get("errors", []):
            self.stdout.write(self.style.ERROR(f"  {err['external_id']}: {err['error']}"))
