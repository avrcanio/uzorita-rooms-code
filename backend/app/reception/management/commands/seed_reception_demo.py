from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from reception.models import Guest, IDDocument, Reservation, ReservationStatus


class Command(BaseCommand):
    help = "Popunjava reception modele test podacima za razvoj i QA."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Obrisi postojece DEMO-RES-* podatke prije seed-a.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            demo_reservations = Reservation.objects.filter(external_id__startswith="DEMO-RES-")
            deleted_count, _ = demo_reservations.delete()
            self.stdout.write(self.style.WARNING(f"Obrisano zapisa: {deleted_count}"))

        today = date.today()
        verifier = (
            get_user_model().objects.filter(is_superuser=True).order_by("id").first()
        )

        seed_data = [
            {
                "external_id": "DEMO-RES-001",
                "room_name": "Soba 101",
                "check_in_offset": 0,
                "nights": 2,
                "status": ReservationStatus.EXPECTED,
                "total": Decimal("189.00"),
                "guests": [
                    ("Marko", "Horvat", "HR", True),
                    ("Ana", "Horvat", "HR", False),
                ],
            },
            {
                "external_id": "DEMO-RES-002",
                "room_name": "Soba 102",
                "check_in_offset": -1,
                "nights": 3,
                "status": ReservationStatus.CHECKED_IN,
                "total": Decimal("276.50"),
                "guests": [
                    ("Ivana", "Kovacic", "HR", True),
                ],
            },
            {
                "external_id": "DEMO-RES-003",
                "room_name": "Soba 103",
                "check_in_offset": 1,
                "nights": 1,
                "status": ReservationStatus.EXPECTED,
                "total": Decimal("99.00"),
                "guests": [
                    ("Luka", "Babic", "HR", True),
                ],
            },
            {
                "external_id": "DEMO-RES-004",
                "room_name": "Soba 104",
                "check_in_offset": -3,
                "nights": 2,
                "status": ReservationStatus.CHECKED_OUT,
                "total": Decimal("154.00"),
                "guests": [
                    ("Petra", "Novak", "SI", True),
                    ("Nika", "Novak", "SI", False),
                ],
            },
            {
                "external_id": "DEMO-RES-005",
                "room_name": "Soba 201",
                "check_in_offset": 2,
                "nights": 4,
                "status": ReservationStatus.EXPECTED,
                "total": Decimal("420.00"),
                "guests": [
                    ("Ivan", "Maric", "DE", True),
                ],
            },
            {
                "external_id": "DEMO-RES-006",
                "room_name": "Soba 202",
                "check_in_offset": 0,
                "nights": 1,
                "status": ReservationStatus.CANCELED,
                "total": Decimal("0.00"),
                "guests": [
                    ("Mia", "Jovic", "HR", True),
                ],
            },
            {
                "external_id": "DEMO-RES-007",
                "room_name": "Soba 203",
                "check_in_offset": 3,
                "nights": 2,
                "status": ReservationStatus.EXPECTED,
                "total": Decimal("210.00"),
                "guests": [
                    ("Filip", "Matic", "AT", True),
                    ("Lea", "Matic", "AT", False),
                ],
            },
            {
                "external_id": "DEMO-RES-008",
                "room_name": "Soba 204",
                "check_in_offset": -2,
                "nights": 2,
                "status": ReservationStatus.CHECKED_IN,
                "total": Decimal("180.00"),
                "guests": [
                    ("Sara", "Radic", "HR", True),
                ],
            },
            {
                "external_id": "DEMO-RES-009",
                "room_name": "Soba 301",
                "check_in_offset": 4,
                "nights": 5,
                "status": ReservationStatus.EXPECTED,
                "total": Decimal("599.99"),
                "guests": [
                    ("Tomislav", "Peric", "HR", True),
                    ("Iva", "Peric", "HR", False),
                ],
            },
            {
                "external_id": "DEMO-RES-010",
                "room_name": "Soba 302",
                "check_in_offset": -5,
                "nights": 2,
                "status": ReservationStatus.CHECKED_OUT,
                "total": Decimal("160.00"),
                "guests": [
                    ("Nikola", "Zoric", "BA", True),
                ],
            },
            {
                "external_id": "DEMO-RES-011",
                "room_name": "Soba 303",
                "check_in_offset": 6,
                "nights": 3,
                "status": ReservationStatus.EXPECTED,
                "total": Decimal("333.00"),
                "guests": [
                    ("Marija", "Vukovic", "RS", True),
                ],
            },
            {
                "external_id": "DEMO-RES-012",
                "room_name": "Soba 304",
                "check_in_offset": 1,
                "nights": 2,
                "status": ReservationStatus.EXPECTED,
                "total": Decimal("188.00"),
                "guests": [
                    ("Karlo", "Bilinic", "HR", True),
                    ("Lucija", "Bilinic", "HR", False),
                ],
            },
        ]

        reservations_created = 0
        guests_created = 0
        id_documents_created = 0

        for index, item in enumerate(seed_data, start=1):
            check_in = today + timedelta(days=item["check_in_offset"])
            check_out = check_in + timedelta(days=item["nights"])

            reservation, created = Reservation.objects.update_or_create(
                external_id=item["external_id"],
                defaults={
                    "room_name": item["room_name"],
                    "check_in_date": check_in,
                    "check_out_date": check_out,
                    "status": item["status"],
                    "total_amount": item["total"],
                    "currency": "EUR",
                },
            )
            reservations_created += int(created)

            reservation.guests.all().delete()

            for guest_idx, (first_name, last_name, nationality, is_primary) in enumerate(
                item["guests"], start=1
            ):
                guest = Guest.objects.create(
                    reservation=reservation,
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=date(1988, 1, min(guest_idx + index, 28)),
                    document_number=f"DOC-{item['external_id']}-{guest_idx}",
                    nationality=nationality,
                    is_primary=is_primary,
                )
                guests_created += 1

                if is_primary:
                    IDDocument.objects.create(
                        guest=guest,
                        image_path=f"/demo/id/{item['external_id'].lower()}-{guest_idx}.jpg",
                        extracted_payload={
                            "first_name": first_name,
                            "last_name": last_name,
                            "document_number": guest.document_number,
                            "nationality": nationality,
                        },
                        verified_by=verifier,
                    )
                    id_documents_created += 1

        self.stdout.write(self.style.SUCCESS("Seed uspjesno zavrsen."))
        self.stdout.write(
            f"Rezervacije ukupno (DEMO-RES-*): "
            f"{Reservation.objects.filter(external_id__startswith='DEMO-RES-').count()}"
        )
        self.stdout.write(f"Novo kreiranih rezervacija: {reservations_created}")
        self.stdout.write(f"Kreiranih gostiju: {guests_created}")
        self.stdout.write(f"Kreiranih ID dokumenata: {id_documents_created}")
