from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mrz.generator.td3 import TD3CodeGenerator

from reception.models import DocumentScanLog, DocumentScanStatus, Guest, Reservation, ReservationStatus
from reception.services.mrz_pipeline import run_mrz_pipeline
from reception.services.ocr_service import OCRService, normalize_paddle_response
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


class NormalizePaddleResponseTests(TestCase):
    def test_fastapi_local_service_shape(self):
        """Fixture matches code/ocr_service FastAPI POST /predict JSON."""
        payload = {
            "results": [
                [
                    {
                        "text": "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
                        "confidence": 0.91,
                        "text_region": [
                            [100.0, 200.0],
                            [400.0, 200.0],
                            [400.0, 240.0],
                            [100.0, 240.0],
                        ],
                    },
                    {
                        "text": "X12345678UTO7608134F2602034<<<<<<<<<<<<<<<4",
                        "confidence": 0.88,
                        "text_region": [
                            [100.0, 250.0],
                            [400.0, 250.0],
                            [400.0, 290.0],
                            [100.0, 290.0],
                        ],
                    },
                ]
            ]
        }
        items, raw = normalize_paddle_response(payload)
        self.assertEqual(raw, payload)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["text"], payload["results"][0][0]["text"])
        self.assertAlmostEqual(items[0]["confidence"], 0.91)
        self.assertEqual(len(items[0]["box"]), 4)
        self.assertAlmostEqual(items[0]["box"][0][0], 100.0)
        self.assertEqual(items[1]["text"], payload["results"][0][1]["text"])


class MrzPipelineTests(TestCase):
    def test_single_char_confusion_restores_valid_td3(self):
        code = str(TD3CodeGenerator("P", "UTO", "ERIKSSON", "ANNA MARIA", "X12345678", "UTO", "760813", "F", "260203"))
        l1, l2 = code.split("\n")
        bad_l2 = l2[:3] + "O" + l2[4:]
        r = run_mrz_pipeline([{"text": l1}, {"text": bad_l2}])
        self.assertTrue(r["checksum_valid"])
        self.assertEqual(r["suggested_fields"].get("document_number"), "X12345678")


class PaddleDocumentScanViewTests(TestCase):
    def setUp(self):
        self.rt = RoomType.objects.create(code="OCR", name_i18n={"en": "OCR Room"})
        self.res = Reservation.objects.create(
            external_id="paddle-scan-1",
            room_name="Room OCR",
            room_type=self.rt,
            check_in_date=date(2026, 8, 1),
            check_out_date=date(2026, 8, 5),
            status=ReservationStatus.EXPECTED,
        )
        self.guest = Guest.objects.create(
            reservation=self.res,
            first_name="Ana",
            last_name="Test",
            document_number="",
        )
        self.user = User.objects.create_user("paddle_tester", password="test-pass-123")

    def test_scan_without_paddle_url_returns_503(self):
        client = APIClient()
        client.force_login(self.user)
        with override_settings(PADDLE_OCR_BASE_URL=""):
            resp = client.post(
                "/api/v1/scan/",
                data={
                    "guest_id": self.guest.id,
                    "file": SimpleUploadedFile("x.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
                },
                format="multipart",
            )
        self.assertEqual(resp.status_code, 503)
        self.assertTrue(DocumentScanLog.objects.filter(guest=self.guest).exists())

    @override_settings(PADDLE_OCR_BASE_URL="http://paddle.test")
    def test_scan_ok_does_not_update_guest(self):
        code = str(TD3CodeGenerator("P", "UTO", "ERIKSSON", "ANNA MARIA", "X12345678", "UTO", "760813", "F", "260203"))
        l1, l2 = code.split("\n")
        items = [{"text": l1, "confidence": 0.99}, {"text": l2, "confidence": 0.99}]

        client = APIClient()
        client.force_login(self.user)

        with patch.object(OCRService, "predict", return_value={"items": items, "raw": {"stub": True}, "http_status": 200}):
            resp = client.post(
                "/api/v1/scan/",
                data={
                    "guest_id": self.guest.id,
                    "file": SimpleUploadedFile("doc.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
                },
                format="multipart",
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.get("scan_status"), DocumentScanStatus.OK)
        self.assertTrue(resp.data.get("mrz", {}).get("checksum_valid"))

        self.guest.refresh_from_db()
        self.assertEqual(self.guest.first_name, "Ana")
        self.assertEqual(self.guest.document_number, "")

    def test_reservation_mismatch_returns_400(self):
        other = Reservation.objects.create(
            external_id="paddle-scan-2",
            room_name="Other",
            room_type=self.rt,
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 3),
            status=ReservationStatus.EXPECTED,
        )
        client = APIClient()
        client.force_login(self.user)
        with override_settings(PADDLE_OCR_BASE_URL="http://paddle.test"):
            with patch.object(OCRService, "predict", return_value={"items": [], "raw": {}, "http_status": 200}):
                resp = client.post(
                    "/api/v1/scan/",
                    data={
                        "guest_id": self.guest.id,
                        "reservation_id": other.id,
                        "file": SimpleUploadedFile("doc.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
                    },
                    format="multipart",
                )
        self.assertEqual(resp.status_code, 400)
