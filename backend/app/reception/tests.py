from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from reception.models import Reservation, ReservationStatus
from rooms.models import Room, RoomType


class ReservationRoomOverlapValidationTests(TestCase):
    def setUp(self):
        self.rt = RoomType.objects.create(code="RTEST", name_i18n={"en": "Test Room"})
        self.room = Room.objects.create(code="T1", room_type=self.rt)

    def test_overlapping_reservations_on_same_room_are_blocked(self):
        Reservation.objects.create(
            external_id="A",
            room_name="Test Room",
            room_type=self.rt,
            room=self.room,
            check_in_date=date(2026, 6, 10),
            check_out_date=date(2026, 6, 12),
            status=ReservationStatus.EXPECTED,
        )

        r2 = Reservation(
            external_id="B",
            room_name="Test Room",
            room_type=self.rt,
            room=self.room,
            check_in_date=date(2026, 6, 11),
            check_out_date=date(2026, 6, 13),
            status=ReservationStatus.EXPECTED,
        )
        with self.assertRaises(ValidationError):
            r2.full_clean()

    def test_canceled_reservation_does_not_block(self):
        Reservation.objects.create(
            external_id="A",
            room_name="Test Room",
            room_type=self.rt,
            room=self.room,
            check_in_date=date(2026, 6, 10),
            check_out_date=date(2026, 6, 12),
            status=ReservationStatus.CANCELED,
        )

        r2 = Reservation(
            external_id="B",
            room_name="Test Room",
            room_type=self.rt,
            room=self.room,
            check_in_date=date(2026, 6, 11),
            check_out_date=date(2026, 6, 13),
            status=ReservationStatus.EXPECTED,
        )
        r2.full_clean()  # should not raise
