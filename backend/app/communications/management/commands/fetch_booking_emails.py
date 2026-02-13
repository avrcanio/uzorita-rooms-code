import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from communications.models import EmailAttachment, InboundEmail


class Command(BaseCommand):
    help = "Fetch unread emails from IMAP mailbox and store them with Message-ID dedupe."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--mark-seen", action="store_true", default=False)

    def handle(self, *args, **options):
        limit = max(1, options["limit"])
        mark_seen = options["mark_seen"]

        self._validate_settings()

        imap = self._connect()
        try:
            imap.select(settings.IMAP_FOLDER)
            status, data = imap.search(None, "UNSEEN")
            if status != "OK":
                raise CommandError("IMAP search UNSEEN failed")

            ids = data[0].split()
            if not ids:
                self.stdout.write(self.style.SUCCESS("No unread emails."))
                return

            processed = 0
            created = 0
            skipped = 0

            for msg_id in ids[:limit]:
                processed += 1
                fetch_status, msg_data = imap.fetch(msg_id, "(RFC822)")
                if fetch_status != "OK" or not msg_data:
                    self.stdout.write(self.style.WARNING(f"Failed to fetch message {msg_id!r}"))
                    continue

                raw_bytes = msg_data[0][1]
                message = email.message_from_bytes(raw_bytes)

                normalized_message_id = (message.get("Message-ID") or "").strip()
                if not normalized_message_id:
                    # Fallback keeps dedupe stable enough for messages missing Message-ID.
                    normalized_message_id = f"missing:{msg_id.decode()}:{hash(raw_bytes)}"

                if InboundEmail.objects.filter(message_id=normalized_message_id).exists():
                    skipped += 1
                    continue

                subject = self._decode_header_value(message.get("Subject", ""))
                sender = self._decode_header_value(message.get("From", ""))
                received_at = self._parse_received_at(message.get("Date"))

                body_text, body_html, attachments = self._extract_parts(message)

                with transaction.atomic():
                    inbound = InboundEmail.objects.create(
                        source="imap",
                        message_id=normalized_message_id,
                        mailbox=settings.MAILBOX_EMAIL,
                        sender=sender,
                        subject=subject,
                        received_at=received_at,
                        body_text=body_text,
                        body_html=body_html,
                        raw_headers=str(message),
                    )
                    EmailAttachment.objects.bulk_create(
                        [
                            EmailAttachment(
                                inbound_email=inbound,
                                filename=a["filename"],
                                content_type=a["content_type"],
                                size_bytes=a["size_bytes"],
                            )
                            for a in attachments
                        ]
                    )

                created += 1

                if mark_seen:
                    imap.store(msg_id, "+FLAGS", "\\Seen")

            self.stdout.write(
                self.style.SUCCESS(
                    f"IMAP ingest done. processed={processed} created={created} skipped={skipped}"
                )
            )
        finally:
            try:
                imap.close()
            except Exception:
                pass
            imap.logout()

    def _validate_settings(self):
        required = [
            "MAILBOX_EMAIL",
            "MAILBOX_PASSWORD",
            "IMAP_HOST",
            "IMAP_PORT",
            "IMAP_FOLDER",
        ]
        missing = [name for name in required if not getattr(settings, name, None)]
        if missing:
            raise CommandError(f"Missing IMAP settings: {', '.join(missing)}")

    def _connect(self):
        if settings.IMAP_USE_SSL:
            imap = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        else:
            imap = imaplib.IMAP4(settings.IMAP_HOST, settings.IMAP_PORT)
        imap.login(settings.MAILBOX_EMAIL, settings.MAILBOX_PASSWORD)
        return imap

    def _decode_header_value(self, value: str) -> str:
        parts = decode_header(value)
        decoded = []
        for payload, encoding in parts:
            if isinstance(payload, bytes):
                decoded.append(payload.decode(encoding or "utf-8", errors="replace"))
            else:
                decoded.append(payload)
        return "".join(decoded).strip()

    def _parse_received_at(self, value: str | None):
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except Exception:
            return None

    def _extract_parts(self, message):
        body_text = ""
        body_html = ""
        attachments = []

        if message.is_multipart():
            for part in message.walk():
                content_disposition = (part.get("Content-Disposition") or "").lower()
                content_type = part.get_content_type()
                filename = part.get_filename()

                if filename:
                    payload = part.get_payload(decode=True) or b""
                    attachments.append(
                        {
                            "filename": self._decode_header_value(filename),
                            "content_type": content_type,
                            "size_bytes": len(payload),
                        }
                    )
                    continue

                if "attachment" in content_disposition:
                    continue

                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                decoded_payload = payload.decode(charset, errors="replace")

                if content_type == "text/plain" and not body_text:
                    body_text = decoded_payload
                elif content_type == "text/html" and not body_html:
                    body_html = decoded_payload
        else:
            payload = message.get_payload(decode=True) or b""
            charset = message.get_content_charset() or "utf-8"
            decoded_payload = payload.decode(charset, errors="replace")
            if message.get_content_type() == "text/html":
                body_html = decoded_payload
            else:
                body_text = decoded_payload

        return body_text, body_html, attachments
