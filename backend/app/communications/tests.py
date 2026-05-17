from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from communications.booking_parser import _is_blocked_guest_email, _parse_guest_email, parse_booking_email
from communications.guest_messaging import (
    deliver_outbound_guest_email,
    guest_message_subject,
    send_guest_message,
)
from communications.models import GuestMessage, InboundEmail, OutboundEmail, OutboundEmailStatus, ParseStatus
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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class GuestMessagingSendTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reception-msg",
            password="test-pass-123",
        )
        self.reservation = Reservation.objects.create(
            external_id="BK-MSG-001",
            check_in_date="2027-06-01",
            check_out_date="2027-06-05",
            status=ReservationStatus.EXPECTED,
        )

    def test_send_guest_message_requires_primary_guest_email(self):
        Guest.objects.create(
            reservation=self.reservation,
            first_name="Ana",
            last_name="Test",
            email="",
            is_primary=True,
        )
        with self.assertRaises(ValidationError):
            send_guest_message(
                reservation_id=self.reservation.pk,
                body_text="Pozdrav",
                user=self.user,
            )
        self.assertEqual(GuestMessage.objects.count(), 0)

    @patch("communications.guest_messaging._enqueue_send_guest_email")
    def test_send_guest_message_creates_outbound_and_message(self, enqueue_mock):
        Guest.objects.create(
            reservation=self.reservation,
            first_name="Ana",
            last_name="Test",
            email="guest@example.com",
            is_primary=True,
        )
        message = send_guest_message(
            reservation_id=self.reservation.pk,
            body_text="  Dobro jutro  ",
            user=self.user,
        )
        self.assertEqual(message.body_text, "Dobro jutro")
        self.assertEqual(message.direction, "outbound")
        outbound = OutboundEmail.objects.get()
        self.assertEqual(outbound.status, OutboundEmailStatus.QUEUED)
        self.assertEqual(outbound.to_email, "guest@example.com")
        self.assertEqual(outbound.subject, guest_message_subject(self.reservation))
        self.assertTrue(outbound.smtp_message_id.startswith("<"))
        self.assertTrue(outbound.smtp_message_id.endswith("@uzorita.hr>"))
        enqueue_mock.assert_called_once_with(outbound.pk)

    def test_deliver_outbound_guest_email_sends_via_smtp(self):
        guest = Guest.objects.create(
            reservation=self.reservation,
            first_name="Ana",
            last_name="Test",
            email="relay@guest.booking.com",
            is_primary=True,
        )
        outbound = OutboundEmail.objects.create(
            reservation=self.reservation,
            guest=guest,
            to_email=guest.email,
            subject=guest_message_subject(self.reservation),
            body_text="Test poruka",
            smtp_message_id="<test-msg-id@uzorita.hr>",
            sent_by=self.user,
            status=OutboundEmailStatus.QUEUED,
        )
        deliver_outbound_guest_email(outbound.pk)

        outbound.refresh_from_db()
        self.assertEqual(outbound.status, OutboundEmailStatus.SENT)
        self.assertIsNotNone(outbound.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["relay@guest.booking.com"])
        self.assertEqual(sent.extra_headers["Message-ID"], "<test-msg-id@uzorita.hr>")
        self.assertEqual(sent.body, "Test poruka")


class ReservationGuestMessageApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reception-msg-api",
            password="test-pass-123",
            first_name="Recepcija",
            last_name="Test",
        )
        self.client = APIClient()
        self.client.force_login(self.user)
        self.reservation = Reservation.objects.create(
            external_id="BK-MSG-API",
            check_in_date="2027-06-01",
            check_out_date="2027-06-05",
            status=ReservationStatus.EXPECTED,
        )

    def _url(self, reservation_id: int | None = None) -> str:
        rid = reservation_id if reservation_id is not None else self.reservation.pk
        return f"/api/reception/reservations/{rid}/messages/"

    def test_get_messages_empty_without_conversation(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_get_messages_unknown_reservation_404(self):
        response = self.client.get(self._url(reservation_id=999999))
        self.assertEqual(response.status_code, 404)

    def test_post_requires_authentication(self):
        client = APIClient()
        response = client.post(self._url(), {"body_text": "Pozdrav"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_post_requires_primary_guest_email(self):
        Guest.objects.create(
            reservation=self.reservation,
            first_name="Ana",
            last_name="Test",
            email="",
            is_primary=True,
        )
        response = self.client.post(self._url(), {"body_text": "Pozdrav"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("guest", response.data)

    def test_post_unknown_reservation_404(self):
        response = self.client.post(
            self._url(reservation_id=999999),
            {"body_text": "Pozdrav"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    @patch("communications.guest_messaging._enqueue_send_guest_email")
    def test_post_and_get_messages(self, enqueue_mock):
        Guest.objects.create(
            reservation=self.reservation,
            first_name="Ana",
            last_name="Test",
            email="guest@example.com",
            is_primary=True,
        )
        post_response = self.client.post(
            self._url(),
            {"body_text": "  Dobro jutro  "},
            format="json",
        )
        self.assertEqual(post_response.status_code, 201)
        self.assertEqual(post_response.data["direction"], "outbound")
        self.assertEqual(post_response.data["body_text"], "Dobro jutro")
        self.assertEqual(post_response.data["status"], OutboundEmailStatus.QUEUED)
        self.assertEqual(post_response.data["sent_by_name"], "Recepcija Test")
        self.assertIsNone(post_response.data["from_email"])
        enqueue_mock.assert_called_once()

        get_response = self.client.get(self._url())
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(len(get_response.data), 1)
        self.assertEqual(get_response.data[0]["id"], post_response.data["id"])
        self.assertEqual(get_response.data[0]["body_text"], "Dobro jutro")
