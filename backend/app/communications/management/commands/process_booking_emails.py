from django.core.management.base import BaseCommand, CommandError

from communications.models import InboundEmail, ParseStatus
from communications.services import process_booking_inbound_email


class Command(BaseCommand):
    help = "Parse stored Booking.com emails and upsert reservations/guests (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, help="Process a single InboundEmail id.")
        parser.add_argument("--limit", type=int, default=50, help="Max emails to process (batch mode).")
        parser.add_argument(
            "--only-pending",
            action="store_true",
            default=False,
            help="Only process emails with parse_status=pending.",
        )
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        inbound_id = options.get("id")
        limit = max(1, int(options.get("limit") or 50))
        only_pending = bool(options.get("only_pending"))
        dry_run = bool(options.get("dry_run"))

        if inbound_id:
            try:
                InboundEmail.objects.get(id=inbound_id)
            except InboundEmail.DoesNotExist:
                raise CommandError(f"InboundEmail id={inbound_id} not found")
            result = process_booking_inbound_email(inbound_email_id=inbound_id, dry_run=dry_run)
            self.stdout.write(self.style.SUCCESS(f"Processed id={inbound_id}: {result}"))
            return

        qs = InboundEmail.objects.all().order_by("id")
        if only_pending:
            qs = qs.filter(parse_status=ParseStatus.PENDING)

        processed = 0
        parsed = 0
        partial = 0
        failed = 0

        for inbound in qs[:limit]:
            processed += 1
            result = process_booking_inbound_email(inbound_email_id=inbound.id, dry_run=dry_run)
            status = result.get("status")
            if status in {"parsed", "dry_run"}:
                parsed += 1
            elif status == "partial":
                partial += 1
            else:
                failed += 1
            self.stdout.write(f"id={inbound.id} status={status} subject={inbound.subject!r}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. processed={processed} parsed={parsed} partial={partial} failed={failed}"
            )
        )

