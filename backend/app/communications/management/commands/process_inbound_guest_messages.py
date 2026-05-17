from django.core.management.base import BaseCommand, CommandError

from communications.guest_messaging import link_inbound_to_conversation, process_inbound_guest_messages
from communications.models import InboundEmail


class Command(BaseCommand):
    help = "Link stored inbound emails to reservation guest message threads."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, help="Process a single InboundEmail id.")
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Max emails to process in batch mode (default: 50).",
        )

    def handle(self, *args, **options):
        inbound_id = options.get("id")
        limit = max(1, int(options.get("limit") or 50))

        if inbound_id:
            try:
                inbound = InboundEmail.objects.get(id=inbound_id)
            except InboundEmail.DoesNotExist as exc:
                raise CommandError(f"InboundEmail id={inbound_id} not found") from exc
            message = link_inbound_to_conversation(inbound)
            if message:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Linked id={inbound_id} -> GuestMessage id={message.id} "
                        f"reservation={inbound.reservation_id}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"No conversation match for InboundEmail id={inbound_id}")
                )
            return

        result = process_inbound_guest_messages(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                "Done. "
                f"processed={result['processed']} "
                f"linked={result['linked']} "
                f"skipped={result['skipped']}"
            )
        )
