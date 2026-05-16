from django.core.management.base import BaseCommand

from reception.ical.import_sync import sync_feed
from reception.models import BookingIcalFeed


class Command(BaseCommand):
    help = "Fetch Booking.com iCal export URL and upsert reservations for configured feeds."

    def add_arguments(self, parser):
        parser.add_argument(
            "--feed",
            default="r1",
            help="Feed code to sync (default: r1). Use 'all' for every active feed with import_url.",
        )
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        feed_code = (options.get("feed") or "r1").strip().lower()
        dry_run = bool(options.get("dry_run"))

        if feed_code == "all":
            feeds = BookingIcalFeed.objects.filter(is_active=True).exclude(import_url="").order_by("code")
        else:
            feeds = BookingIcalFeed.objects.filter(code=feed_code, is_active=True)

        if not feeds.exists():
            self.stderr.write(self.style.ERROR(f"No active feed found for code={feed_code!r}"))
            return

        for feed in feeds:
            result = sync_feed(feed, dry_run=dry_run)
            msg = (
                f"{result.feed_code}: status={result.status} "
                f"events={result.events_seen} skipped_blocks={result.skipped_blocks} "
                f"upserted={result.upserted} canceled={result.canceled}"
            )
            if result.errors:
                msg += f" errors={len(result.errors)}"
                for err in result.errors[:5]:
                    self.stderr.write(f"  {err}")
            if result.status in {"fetch_error", "partial"}:
                self.stderr.write(self.style.WARNING(msg))
            else:
                self.stdout.write(self.style.SUCCESS(msg))
