from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from communications.booking_parser import _is_blocked_guest_email, _parse_guest_email, parse_booking_email
from communications.guest_messaging import (
    deliver_outbound_guest_email,
    guest_message_subject,
    send_guest_message,
)
from communications.models import GuestMessage, OutboundEmail, OutboundEmailStatus
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
