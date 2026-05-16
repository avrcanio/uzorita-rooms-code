from django.test import TestCase

from communications.booking_parser import _is_blocked_guest_email, _parse_guest_email, parse_booking_email
from reception.booking_import import _should_update_guest_email
from reception.models import Guest, Reservation, ReservationStatus


class GuestEmailParserTests(TestCase):
    def test_prefers_guest_booking_alias(self):
        lines = [
            "room_reservations@uzorita.hr",
            "avrcan.794657@guest.booking.com",
        ]
        self.assertEqual(_parse_guest_email(lines), "avrcan.794657@guest.booking.com")

    def test_blocks_property_mailbox(self):
        self.assertTrue(_is_blocked_guest_email("room_reservations@uzorita.hr"))
        lines = ["room_reservations@uzorita.hr"]
        self.assertIsNone(_parse_guest_email(lines))

    def test_does_not_downgrade_guest_booking_email(self):
        self.assertFalse(
            _should_update_guest_email(
                "avrcan.794657@guest.booking.com",
                "room_reservations@uzorita.hr",
            )
        )
        self.assertTrue(
            _should_update_guest_email(
                "",
                "avrcan.794657@guest.booking.com",
            )
        )


class BookingImportGuestEmailTests(TestCase):
    def test_existing_guest_booking_email_not_overwritten_by_property_mailbox(self):
        reservation = Reservation.objects.create(
            external_id="email-protect-1",
            check_in_date="2027-01-11",
            check_out_date="2027-01-12",
            status=ReservationStatus.EXPECTED,
        )
        guest = Guest.objects.create(
            reservation=reservation,
            first_name="Ante",
            last_name="Vrcan",
            email="avrcan.794657@guest.booking.com",
            is_primary=True,
        )
        from reception.booking_import import upsert_reservation_from_booking_payload

        upsert_reservation_from_booking_payload(
            external_id="email-protect-1",
            room_name="Deluxe Triple Room",
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
            status=ReservationStatus.EXPECTED,
            guest_full_name="Ante Vrcan",
            guest_email="room_reservations@uzorita.hr",
            total_amount=None,
            currency=None,
        )
        guest.refresh_from_db()
        self.assertEqual(guest.email, "avrcan.794657@guest.booking.com")
