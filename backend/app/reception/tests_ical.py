from datetime import date
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from reception.ical.export import blocked_date_ranges_for_feed, build_export_ics
from reception.ical.import_sync import extract_external_id, is_availability_block, sync_feed
from reception.models import BookingIcalFeed, ImportSource, Reservation, ReservationStatus, ReservationUnit
from rooms.models import Room, RoomType


class BookingIcalExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rt_r1 = RoomType.objects.create(code="R1", name_i18n={"en": "Deluxe King"})
        cls.k1 = Room.objects.create(code="K1", room_type=cls.rt_r1, is_active=True)
        cls.k2 = Room.objects.create(code="K2", room_type=cls.rt_r1, is_active=True)
        cls.feed = BookingIcalFeed.objects.create(
            code="r1-test",
            room_type=cls.rt_r1,
            booking_listing_name="Luxury Room Uzorita - R1",
            export_token=uuid4(),
            min_occupied_units_to_block=2,
            is_active=True,
        )

    def _reserve(
        self,
        external_id: str,
        room: Room,
        check_in: date,
        check_out: date,
        *,
        import_source: str = "",
    ) -> None:
        res = Reservation.objects.create(
            external_id=external_id,
            check_in_date=check_in,
            check_out_date=check_out,
            status=ReservationStatus.EXPECTED,
            import_source=import_source,
        )
        ReservationUnit.objects.create(
            reservation=res,
            sort_order=0,
            room_name="Luxury Room Uzorita - R1",
            room_type=self.rt_r1,
            room=room,
        )

    def test_no_reservations_no_blocked_ranges(self):
        ranges = blocked_date_ranges_for_feed(self.feed, horizon_days=30)
        self.assertEqual(ranges, [])

    def test_only_k1_occupied_does_not_block(self):
        self._reserve("only-k1", self.k1, date(2026, 6, 10), date(2026, 6, 12))
        ranges = blocked_date_ranges_for_feed(self.feed, horizon_days=400)
        june_10 = date(2026, 6, 10)
        june_11 = date(2026, 6, 11)
        blocked = {d for start, end in ranges for d in _days(start, end)}
        self.assertNotIn(june_10, blocked)
        self.assertNotIn(june_11, blocked)

    def test_k1_and_k2_overlap_blocks_for_non_booking_source(self):
        self._reserve("k1-busy", self.k1, date(2026, 6, 10), date(2026, 6, 12))
        self._reserve("k2-busy", self.k2, date(2026, 6, 10), date(2026, 6, 12))
        ranges = blocked_date_ranges_for_feed(self.feed, horizon_days=400)
        self.assertEqual(ranges, [(date(2026, 6, 10), date(2026, 6, 12))])

    def test_booking_xls_reservations_do_not_export_blocks(self):
        self._reserve(
            "bk-1",
            self.k1,
            date(2026, 6, 10),
            date(2026, 6, 12),
            import_source=ImportSource.BOOKING_XLS,
        )
        self._reserve(
            "bk-2",
            self.k2,
            date(2026, 6, 10),
            date(2026, 6, 12),
            import_source=ImportSource.BOOKING_XLS,
        )
        ranges = blocked_date_ranges_for_feed(self.feed, horizon_days=400)
        self.assertEqual(ranges, [])

    def test_export_endpoint_returns_ics(self):
        self._reserve("k1-busy", self.k1, date(2026, 7, 1), date(2026, 7, 3))
        self._reserve("k2-busy", self.k2, date(2026, 7, 1), date(2026, 7, 3))
        url = reverse(
            "public-booking-ical-export",
            kwargs={"feed_code": self.feed.code, "export_token": self.feed.export_token},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/calendar", response["Content-Type"])
        body = response.content.decode("utf-8")
        self.assertIn("BEGIN:VCALENDAR", body)
        self.assertIn("BEGIN:VEVENT", body)
        self.assertIn("20260701", body)

    def test_invalid_token_returns_404(self):
        url = reverse(
            "public-booking-ical-export",
            kwargs={"feed_code": "r1-test", "export_token": uuid4()},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class BookingIcalImportTests(TestCase):
    SAMPLE_ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Booking.com//EN
BEGIN:VEVENT
UID:booking-5307026805@booking.com
DTSTART;VALUE=DATE:20260615
DTEND;VALUE=DATE:20260618
SUMMARY:John Doe
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
"""

    @classmethod
    def setUpTestData(cls):
        cls.rt_r1 = RoomType.objects.create(code="R1", name_i18n={"en": "Deluxe King"})
        cls.k1 = Room.objects.create(code="K1", room_type=cls.rt_r1, is_active=True)
        cls.feed = BookingIcalFeed.objects.create(
            code="r1-import",
            room_type=cls.rt_r1,
            booking_listing_name="Luxury Room Uzorita - R1",
            export_token=uuid4(),
            import_url="https://admin.booking.com/hotel/hoteladmin/ical.html?example=1",
            is_active=True,
        )

    def test_skips_closed_availability_blocks(self):
        self.assertTrue(is_availability_block("CLOSED - Not available"))

    @patch("reception.ical.import_sync.httpx.get")
    def test_import_skips_booking_closed_feed(self, mock_get):
        closed_ics = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:abc@booking.com
DTSTART;VALUE=DATE:20260601
DTEND;VALUE=DATE:20260603
SUMMARY:CLOSED - Not available
END:VEVENT
END:VCALENDAR
"""
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.content = closed_ics
        mock_response.headers = {}

        result = sync_feed(self.feed)
        self.assertEqual(result.skipped_blocks, 1)
        self.assertEqual(result.upserted, 0)
        self.assertEqual(Reservation.objects.filter(import_source=ImportSource.BOOKING_ICAL).count(), 0)

    def test_extract_external_id_from_uid(self):
        self.assertEqual(
            extract_external_id(uid="booking-5307026805@booking.com", summary="", description=""),
            "5307026805",
        )

    def test_extract_external_id_fallback(self):
        self.assertEqual(
            extract_external_id(uid="opaque-uid-xyz", summary="", description=""),
            "ical-opaque-uid-xyz",
        )

    @patch("reception.ical.import_sync.httpx.get")
    def test_import_creates_reservation_and_unit(self, mock_get):
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.content = self.SAMPLE_ICS
        mock_response.headers = {"ETag": '"abc123"'}

        result = sync_feed(self.feed)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.upserted, 1)

        res = Reservation.objects.get(external_id="5307026805")
        self.assertEqual(res.check_in_date, date(2026, 6, 15))
        self.assertEqual(res.check_out_date, date(2026, 6, 18))
        self.assertEqual(res.import_source, ImportSource.BOOKING_ICAL)
        unit = res.units.get()
        self.assertEqual(unit.room_type_id, self.rt_r1.id)
        self.assertEqual(unit.room_id, self.k1.id)

    @patch("reception.ical.import_sync.httpx.get")
    def test_import_dedupes_with_existing_email_reservation(self, mock_get):
        Reservation.objects.create(
            external_id="5307026805",
            check_in_date=date(2026, 6, 10),
            check_out_date=date(2026, 6, 12),
            status=ReservationStatus.EXPECTED,
            import_source=ImportSource.BOOKING_EMAIL,
        )
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.content = self.SAMPLE_ICS
        mock_response.headers = {}

        sync_feed(self.feed)
        self.assertEqual(Reservation.objects.filter(external_id="5307026805").count(), 1)
        res = Reservation.objects.get(external_id="5307026805")
        self.assertEqual(res.check_in_date, date(2026, 6, 15))
        self.assertEqual(res.check_out_date, date(2026, 6, 18))


def _days(start: date, end: date) -> list[date]:
    from datetime import timedelta

    out = []
    d = start
    while d < end:
        out.append(d)
        d += timedelta(days=1)
    return out
