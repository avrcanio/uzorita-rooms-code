from datetime import date

from django.test import TestCase

from communications.booking_parser import _is_blocked_guest_email, _parse_guest_email, parse_booking_email
from communications.models import InboundEmail, ParseStatus
from communications.services import process_booking_inbound_email
from reception.booking_import import _should_update_guest_email
from reception.models import Guest, Reservation, ReservationStatus


class DirectBookingConfirmationParserTests(TestCase):
  """Booking.com direct confirmation (no Rentlio forward)."""

  SUBJECT = "Booking.com - New booking! (5581435138, Sunday, 28 June 2026)"
  BODY_HTML = """<!DOCTYPE html><html><body>
  <p>Luxury Room Uzorita B&amp;B</p>
  <p>Booking confirmation</p>
  <p>5581435138</p>
  <p><a href="https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/booking.html?res_id=5581435138&amp;hotel_id=4181954">View</a></p>
  </body></html>"""

  def test_parses_booking_number_from_subject_and_body(self):
    payload = parse_booking_email(
      subject=self.SUBJECT,
      body_text="",
      body_html=self.BODY_HTML,
    )
    self.assertEqual(payload.booking_number, "5581435138")
    self.assertEqual(payload.kind, "new")
    self.assertEqual(payload.check_in_date, date(2026, 6, 28))
    self.assertIsNone(payload.check_out_date)
    self.assertEqual(payload.property_name, "Luxury Room Uzorita B&B")
    self.assertIsNone(payload.guest_full_name)
    self.assertIsNone(payload.guest_email)

  def test_parses_booking_number_from_plain_text_body(self):
    body = """Booking confirmation — 5581435138
Luxury Room Uzorita B&B
https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/booking.html?res_id=5581435138&hotel_id=4181954
"""
    payload = parse_booking_email(subject=self.SUBJECT, body_text=body, body_html="")
    self.assertEqual(payload.booking_number, "5581435138")


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


class BookingCancelEmailTests(TestCase):
    SUBJECT = "Booking.com - Cancelled booking! (5808815673, Monday, 11 January 2027)"
    BODY_HTML = """<!DOCTYPE html><html><body>
  <p>Luxury Room Uzorita B&amp;B</p>
  <p>Cancellation</p>
  <p>5808815673</p>
  </body></html>"""

    def test_cancel_email_marks_existing_xls_reservation_canceled(self):
        Reservation.objects.create(
            external_id="5808815673",
            check_in_date="2027-01-11",
            check_out_date="2027-01-12",
            status=ReservationStatus.EXPECTED,
            details_pending=False,
        )
        inbound = InboundEmail.objects.create(
            message_id="test-cancel-5808815673",
            mailbox="room_reservations@uzorita.hr",
            subject=self.SUBJECT,
            body_html=self.BODY_HTML,
        )
        result = process_booking_inbound_email(inbound_email_id=inbound.id)
        self.assertEqual(result["status"], "parsed")
        self.assertTrue(result.get("canceled"))
        reservation = Reservation.objects.get(external_id="5808815673")
        self.assertEqual(reservation.status, ReservationStatus.CANCELED)


class BookingEmailStubTests(TestCase):
    SUBJECT = "Booking.com - New booking! (5581435138, Sunday, 28 June 2026)"
    BODY_HTML = """<!DOCTYPE html><html><body>
  <p>Luxury Room Uzorita B&amp;B</p>
  <p>Booking confirmation</p>
  <p>5581435138</p>
  </body></html>"""

    def test_partial_direct_booking_email_creates_stub_reservation(self):
        inbound = InboundEmail.objects.create(
            message_id="test-stub-5581435138",
            mailbox="room_reservations@uzorita.hr",
            subject=self.SUBJECT,
            body_html=self.BODY_HTML,
        )
        result = process_booking_inbound_email(inbound_email_id=inbound.id)
        self.assertEqual(result["status"], "parsed")
        self.assertTrue(result.get("stub"))

        reservation = Reservation.objects.get(external_id="5581435138")
        self.assertTrue(reservation.details_pending)
        self.assertEqual(reservation.check_in_date, date(2026, 6, 28))
        self.assertEqual(reservation.check_out_date, date(2026, 6, 29))

        inbound.refresh_from_db()
        self.assertEqual(inbound.parse_status, ParseStatus.PARSED)


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
