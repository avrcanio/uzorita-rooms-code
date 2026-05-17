import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from reception.booking_extranet.connection_service import import_storage_state
from reception.booking_extranet.session_store import (
    BookingExtranetSessionError,
    ensure_configured,
    validate_storage_state,
)
from reception.models import BookingExtranetConnection


class Command(BaseCommand):
    help = (
        "Upload Playwright storage_state.json (nakon ručne prijave u browseru) "
        "u enkriptirani state.enc i označi vezu kao connected."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            type=str,
            help="Putanja do storage_state.json (Playwright context.storage_state).",
        )
        parser.add_argument(
            "--hotel-id",
            type=str,
            default="",
            help="Hotel ID (default: BOOKING_EXTRANET_HOTEL_ID iz settings).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Samo validiraj JSON; ne piši na disk niti ažuriraj model.",
        )

    def handle(self, *args, **options):
        if not settings.BOOKING_EXTRANET_ENABLED:
            raise CommandError("BOOKING_EXTRANET_ENABLED nije true.")

        json_path = Path(options["json_path"]).expanduser()
        if not json_path.is_file():
            raise CommandError(f"Datoteka ne postoji: {json_path}")

        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Nevaljan JSON: {exc}") from exc

        hotel_id = (options["hotel_id"] or settings.BOOKING_EXTRANET_HOTEL_ID or "").strip()
        if not hotel_id:
            raise CommandError(
                "Hotel ID nije postavljen (--hotel-id ili BOOKING_EXTRANET_HOTEL_ID)."
            )

        conn = BookingExtranetConnection.get_solo()
        relative_path = conn.storage_path or "state.enc"

        if options["dry_run"]:
            try:
                validate_storage_state(raw)
                ensure_configured()
            except BookingExtranetSessionError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry-run OK: JSON valjan ({len(raw.get('cookies') or [])} cookies)."
                )
            )
            return

        try:
            conn = import_storage_state(raw, hotel_id=hotel_id)
        except BookingExtranetSessionError as exc:
            raise CommandError(str(exc)) from exc

        cookie_count = len(raw.get("cookies") or [])
        self.stdout.write(self.style.SUCCESS(f"Spremljeno: {relative_path} (storage_version={conn.storage_version})"))
        self.stdout.write(f"Status: {conn.status}, cookies: {cookie_count}, hotel_id: {hotel_id}")
