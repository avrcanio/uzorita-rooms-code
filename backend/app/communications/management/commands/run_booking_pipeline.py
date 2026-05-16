import time

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Periodically fetch Booking emails (IMAP) and process stored emails into reservations/guests."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=60, help="Seconds between runs.")
        parser.add_argument("--fetch-limit", type=int, default=50)
        parser.add_argument("--process-limit", type=int, default=50)
        parser.add_argument("--mark-seen", action="store_true", default=False)
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument(
            "--include-non-pending",
            action="store_true",
            default=False,
            help="By default only pending emails are processed. Set this to re-process everything.",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            default=False,
            help="Run a single iteration and exit (useful for cron).",
        )
        parser.add_argument(
            "--ical-interval",
            type=int,
            default=1800,
            help="Seconds between Booking iCal sync runs (default: 1800 = 30 min).",
        )
        parser.add_argument(
            "--skip-ical",
            action="store_true",
            default=False,
            help="Disable periodic sync_booking_ical in the worker loop.",
        )

    def handle(self, *args, **options):
        interval = max(5, int(options["interval"] or 60))
        fetch_limit = max(1, int(options["fetch_limit"] or 50))
        process_limit = max(1, int(options["process_limit"] or 50))
        mark_seen = bool(options["mark_seen"])
        dry_run = bool(options["dry_run"])
        once = bool(options["once"])
        only_pending = not bool(options["include_non_pending"])
        skip_ical = bool(options["skip_ical"])
        ical_interval = max(60, int(options["ical_interval"] or 1800))
        last_ical_sync = 0.0

        while True:
            try:
                self.stdout.write("booking-pipeline: fetch_booking_emails ...")
                call_command("fetch_booking_emails", limit=fetch_limit, mark_seen=mark_seen)
            except Exception as e:
                # Keep the loop alive; IMAP issues shouldn't kill the worker.
                self.stderr.write(f"booking-pipeline: fetch failed: {e}")

            try:
                self.stdout.write("booking-pipeline: process_booking_emails ...")
                cmd_args = ["process_booking_emails", "--limit", str(process_limit)]
                if only_pending:
                    cmd_args.append("--only-pending")
                if dry_run:
                    cmd_args.append("--dry-run")
                call_command(*cmd_args)
            except Exception as e:
                self.stderr.write(f"booking-pipeline: process failed: {e}")

            if not skip_ical:
                now = time.time()
                if now - last_ical_sync >= ical_interval:
                    try:
                        self.stdout.write("booking-pipeline: sync_booking_ical ...")
                        call_command("sync_booking_ical", feed="all")
                        last_ical_sync = now
                    except Exception as e:
                        self.stderr.write(f"booking-pipeline: ical sync failed: {e}")

            if once:
                return

            time.sleep(interval)

