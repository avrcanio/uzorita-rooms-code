import base64
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mrz.generator.td1 import TD1CodeGenerator
from mrz.generator.td3 import TD3CodeGenerator

from reception.booking_xls_import import (
    BookingXlsRow,
    _split_guest_names,
    import_booking_xls_bytes,
    import_booking_xls_file,
    parse_booking_xls,
    parse_booking_xls_bytes,
    upsert_reservation_from_xls_row,
)
from reception.evisitor.mapper import build_check_in_payload
from reception.evisitor.summary import evisitor_summary_for_reservation
from reception.models import (
    DocumentScanLog,
    DocumentScanStatus,
    EvisitorGuestStatus,
    Guest,
    IDDocument,
    ImportSource,
    Reservation,
    ReservationStatus,
    ReservationUnit,
)
from reception.services.mrz_crop_postprocess import normalize_mrz_crop_paddle_items
from reception.services.mrz_image_crop import (
    build_mrz_crop_for_paddle_second_pass,
    crop_bottom_strip_jpeg,
    image_size_from_bytes,
    merge_fullframe_and_mrz_crop_items,
    preprocess_mrz_strip,
)
from reception.services.mrz_pipeline import run_mrz_pipeline
from reception.services.td1_mrz_extract import extract_td1_mrz_from_ocr
from reception.services.ocr_sample_store import (
    save_scan_debug_sidecar,
    save_scan_paddle_raw_sidecar,
    save_scan_upload_sample,
)
from reception.services.ocr_service import OCRService, normalize_paddle_response, prepare_image_bytes_for_paddle_ocr
from reception.statistics import aggregate_monthly_statistics
from rooms.models import Room, RoomType


class ReservationRoomOverlapValidationTests(TestCase):
    def setUp(self):
        self.rt = RoomType.objects.create(code="RTEST", name_i18n={"en": "Test Room"})
        self.room = Room.objects.create(code="T1", room_type=self.rt)

    def _reservation_with_unit(self, *, external_id: str, status: str, start: date, end: date) -> Reservation:
        reservation = Reservation.objects.create(
            external_id=external_id,
            check_in_date=start,
            check_out_date=end,
            status=status,
        )
        ReservationUnit.objects.create(
            reservation=reservation,
            sort_order=0,
            room_name="Test Room",
            room_type=self.rt,
            room=self.room,
        )
        return reservation

    def test_overlapping_units_on_same_room_are_blocked(self):
        self._reservation_with_unit(
            external_id="A",
            status=ReservationStatus.EXPECTED,
            start=date(2026, 6, 10),
            end=date(2026, 6, 12),
        )
        reservation_b = Reservation.objects.create(
            external_id="B",
            check_in_date=date(2026, 6, 11),
            check_out_date=date(2026, 6, 13),
            status=ReservationStatus.EXPECTED,
        )
        unit_b = ReservationUnit(
            reservation=reservation_b,
            sort_order=0,
            room_name="Test Room",
            room_type=self.rt,
            room=self.room,
        )
        with self.assertRaises(ValidationError):
            unit_b.full_clean()

    def test_canceled_reservation_does_not_block(self):
        self._reservation_with_unit(
            external_id="A",
            status=ReservationStatus.CANCELED,
            start=date(2026, 6, 10),
            end=date(2026, 6, 12),
        )
        reservation_b = Reservation.objects.create(
            external_id="B",
            check_in_date=date(2026, 6, 11),
            check_out_date=date(2026, 6, 13),
            status=ReservationStatus.EXPECTED,
        )
        unit_b = ReservationUnit(
            reservation=reservation_b,
            sort_order=0,
            room_name="Test Room",
            room_type=self.rt,
            room=self.room,
        )
        unit_b.full_clean()


class ReservationTimelineListViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("timeline_user", password="test-pass-123")
        self.client = APIClient()
        self.client.force_login(self.user)

    def _create(
        self,
        external_id: str,
        check_in: date,
        check_out: date,
        *,
        status: str = ReservationStatus.CHECKED_IN,
    ) -> Reservation:
        return Reservation.objects.create(
            external_id=external_id,
            check_in_date=check_in,
            check_out_date=check_out,
            status=status,
        )

    def test_period_from_to_includes_arrivals_and_departures(self):
        arrival = self._create("5307026805", date(2026, 5, 16), date(2026, 5, 17))
        departure = self._create("6368399004", date(2026, 5, 14), date(2026, 5, 16))
        outside = self._create(
            "9999999999",
            date(2026, 5, 10),
            date(2026, 5, 12),
            status=ReservationStatus.EXPECTED,
        )

        resp = self.client.get(
            "/api/reception/reservations/",
            {"period_from": "2026-05-16", "period_to": "2026-05-16"},
        )
        self.assertEqual(resp.status_code, 200)
        ids = {item["external_id"] for item in resp.data}
        self.assertIn(arrival.external_id, ids)
        self.assertIn(departure.external_id, ids)
        self.assertNotIn(outside.external_id, ids)

    def test_period_includes_checked_in_outside_date_range(self):
        in_period = self._create("5307026805", date(2026, 5, 16), date(2026, 5, 17))
        old_checked_in = self._create(
            "8888888888",
            date(2026, 1, 1),
            date(2026, 1, 5),
            status=ReservationStatus.CHECKED_IN,
        )
        outside_expected = self._create(
            "9999999999",
            date(2026, 5, 10),
            date(2026, 5, 12),
            status=ReservationStatus.EXPECTED,
        )

        resp = self.client.get(
            "/api/reception/reservations/",
            {"period_from": "2026-05-16", "period_to": "2026-05-16"},
        )
        self.assertEqual(resp.status_code, 200)
        ids = {item["external_id"] for item in resp.data}
        self.assertIn(in_period.external_id, ids)
        self.assertIn(old_checked_in.external_id, ids)
        self.assertNotIn(outside_expected.external_id, ids)

    def test_check_in_only_filter_still_excludes_departures(self):
        departure = self._create("6519718194", date(2026, 5, 13), date(2026, 5, 16))
        resp = self.client.get(
            "/api/reception/reservations/",
            {"check_in_from": "2026-05-16", "check_in_to": "2026-05-16"},
        )
        self.assertEqual(resp.status_code, 200)
        ids = {item["external_id"] for item in resp.data}
        self.assertNotIn(departure.external_id, ids)


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


class MrzImageCropTests(TestCase):
    def test_merge_drops_fullframe_in_strip_and_offsets_boxes(self):
        full = [
            {
                "text": "TOPFIELD",
                "confidence": 0.9,
                "box": [[0.0, 50.0], [100.0, 50.0], [100.0, 80.0], [0.0, 80.0]],
            },
            {
                "text": "BADMRZ",
                "confidence": 0.3,
                "box": [[0.0, 950.0], [2000.0, 950.0], [2000.0, 980.0], [0.0, 980.0]],
            },
        ]
        crop = [
            {
                "text": "ROW1",
                "confidence": 0.95,
                "box": [[0.0, 5.0], [100.0, 5.0], [100.0, 20.0], [0.0, 20.0]],
            }
        ]
        merged = merge_fullframe_and_mrz_crop_items(
            full, crop, full_height=1000, crop_y0=900, margin_px=0.0
        )
        texts = [m["text"] for m in merged]
        self.assertEqual(texts, ["TOPFIELD", "ROW1"])
        box = merged[1]["box"]
        ys = [p[1] for p in box]
        self.assertGreater(min(ys), 900)

    def test_merge_keeps_full_strip_when_max_conf_beats_crop(self):
        """Kao stvarni sken: puni kadar bolje pročita MRZ nego ultra-široki crop."""
        strip_box = [[0.0, 1120.0], [2400.0, 1120.0], [2400.0, 1210.0], [0.0, 1210.0]]
        full = [
            {"text": "HEADER", "confidence": 0.99, "box": [[0.0, 50.0], [100.0, 50.0], [100.0, 70.0], [0.0, 70.0]]},
            {"text": "I0HRV11938408791528564544<<<<", "confidence": 0.96, "box": strip_box},
        ]
        crop = [{"text": "10HRV119384U89528564544<<<<", "confidence": 0.77, "box": [[0.0, 10.0], [400.0, 10.0], [400.0, 40.0], [0.0, 40.0]]}]
        merged = merge_fullframe_and_mrz_crop_items(
            full, crop, full_height=1666, crop_y0=1133, margin_px=8.0
        )
        texts = [m["text"] for m in merged]
        self.assertIn("I0HRV11938408791528564544<<<<", texts)
        self.assertNotIn("10HRV119384U89528564544<<<<", texts)

    def test_merge_uses_crop_when_strip_reading_is_weak(self):
        full = [
            {"text": "TOP", "confidence": 0.99, "box": [[0.0, 10.0], [50.0, 10.0], [50.0, 30.0], [0.0, 30.0]]},
            {"text": "GARBAGEINSTRIP", "confidence": 0.4, "box": [[0.0, 950.0], [500.0, 950.0], [500.0, 980.0], [0.0, 980.0]]},
        ]
        crop = [{"text": "CLEANMRZLINE", "confidence": 0.98, "box": [[0.0, 5.0], [200.0, 5.0], [200.0, 25.0], [0.0, 25.0]]}]
        merged = merge_fullframe_and_mrz_crop_items(
            full, crop, full_height=1000, crop_y0=900, margin_px=0.0
        )
        texts = [m["text"] for m in merged]
        self.assertEqual(texts, ["TOP", "CLEANMRZLINE"])

    def test_merge_keeps_full_when_line2_truncated_but_line1_good(self):
        """Puni kadar I0HRV + skraćen red 2; crop bez line1 — zadrži puni (ne 101R7)."""
        strip_y0 = 1132
        full = [
            {"text": "HEADER", "confidence": 0.99, "box": [[0.0, 50.0], [100.0, 50.0], [100.0, 70.0], [0.0, 70.0]]},
            {
                "text": "I0HRV119384087911528564544<<<<",
                "confidence": 0.97,
                "box": [[0.0, 1289.0], [2400.0, 1289.0], [2400.0, 1341.0], [0.0, 1341.0]],
            },
            {
                "text": "7604234M3005121HRV<Z9",
                "confidence": 0.95,
                "box": [[0.0, 1423.0], [2400.0, 1423.0], [2400.0, 1497.0], [0.0, 1497.0]],
            },
        ]
        crop = [
            {"text": "101R719384187915856454727", "confidence": 0.81, "box": [[0.0, 10.0], [400.0, 10.0], [400.0, 40.0], [0.0, 40.0]]},
        ]
        merged = merge_fullframe_and_mrz_crop_items(
            full, crop, full_height=1677, crop_y0=strip_y0, margin_px=8.0
        )
        texts = [m["text"] for m in merged]
        self.assertIn("I0HRV119384087911528564544<<<<", texts)
        self.assertNotIn("101R719384187915856454727", texts)

    def test_merge_keeps_full_when_crop_line1_is_t01_garbage(self):
        """CLAHE crop + custom rec: T01R4… vs puni kadar I0HRV — zadrži puni."""
        strip_y0 = 1211
        full = [
            {"text": "HEADER", "confidence": 0.99, "box": [[0.0, 50.0], [100.0, 50.0], [100.0, 70.0], [0.0, 70.0]]},
            {
                "text": "I0HRV119384087911528564544<<<<",
                "confidence": 0.97,
                "box": [[0.0, 1289.0], [2400.0, 1289.0], [2400.0, 1341.0], [0.0, 1341.0]],
            },
            {
                "text": "7604234M300511HRV<9",
                "confidence": 0.95,
                "box": [[0.0, 1423.0], [2400.0, 1423.0], [2400.0, 1497.0], [0.0, 1497.0]],
            },
        ]
        crop = [
            {"text": "T01R493840879585644422<<<<<<<<", "confidence": 0.81, "box": [[0.0, 10.0], [400.0, 10.0], [400.0, 40.0], [0.0, 40.0]]},
            {"text": "7604274M300511RV<<<<<<<<<<<<<<", "confidence": 0.90, "box": [[0.0, 50.0], [400.0, 50.0], [400.0, 80.0], [0.0, 80.0]]},
        ]
        merged = merge_fullframe_and_mrz_crop_items(
            full, crop, full_height=1794, crop_y0=strip_y0, margin_px=8.0
        )
        texts = [m["text"] for m in merged]
        self.assertIn("I0HRV119384087911528564544<<<<", texts)
        self.assertNotIn("T01R493840879585644422<<<<<<<<", texts)

    def test_merge_prefers_crop_when_fullframe_td1_line2_truncated(self):
        """Puni kadar prereže liniju 2 (visok conf); crop drugog prolaza ima punih 30 znakova."""
        strip_y0 = 1137
        full = [
            {"text": "HEADER", "confidence": 0.99, "box": [[0.0, 50.0], [100.0, 50.0], [100.0, 70.0], [0.0, 70.0]]},
            {
                "text": "I0HRV119384087911528564544<<<<",
                "confidence": 0.99,
                "box": [[0.0, 1144.0], [2400.0, 1144.0], [2400.0, 1233.0], [0.0, 1233.0]],
            },
            {
                "text": "7604234M3005121HRV<",
                "confidence": 0.97,
                "box": [[0.0, 1279.0], [1688.0, 1288.0], [1687.0, 1363.0], [0.0, 1354.0]],
            },
            {
                "text": "6>>>>>",
                "confidence": 0.91,
                "box": [[2020.0, 1291.0], [2527.0, 1291.0], [2527.0, 1365.0], [2020.0, 1365.0]],
            },
        ]
        crop = [
            {
                "text": "7604234M3005121HRV<<<<<<<<<<<9",
                "confidence": 0.93,
                "box": [[0.0, 200.0], [400.0, 200.0], [400.0, 320.0], [0.0, 320.0]],
            },
        ]
        merged = merge_fullframe_and_mrz_crop_items(
            full, crop, full_height=1684, crop_y0=strip_y0, margin_px=8.0
        )
        texts = [m["text"] for m in merged]
        self.assertIn("7604234M3005121HRV<<<<<<<<<<<9", texts)
        self.assertNotIn("7604234M3005121HRV<", texts)
        self.assertNotIn("6>>>>>", texts)

    def test_normalize_mrz_crop_hints_first_three_rows_by_y(self):
        """Četvrti bbox (šum) ispod MRZ — prva tri retka dobiju TD1 hintove za O/Z na liniji 2."""
        items = [
            {"text": "IOHRV119384087911528564544<<<<", "confidence": 0.98, "box": [[0, 10], [10, 10], [10, 20], [0, 20]]},
            {
                "text": "O604234M3005121HRV<<<<<<<<<<<<<",
                "confidence": 0.94,
                "box": [[0, 40], [10, 40], [10, 50], [0, 50]],
            },
            {"text": "VRCAN<<ANTE<<<<<<<<<<<<<<<<<<<", "confidence": 0.92, "box": [[0, 70], [10, 70], [10, 80], [0, 80]]},
            {"text": "<<<<X<<<<", "confidence": 0.77, "box": [[0, 100], [10, 100], [10, 110], [0, 110]]},
        ]
        out = normalize_mrz_crop_paddle_items(items)
        line2 = out[1]["text"]
        self.assertTrue(line2.startswith("0604234"), msg=line2)

    def test_crop_preprocess_and_size(self):
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (120, 220), (40, 60, 90)).save(buf, format="JPEG")
        raw = buf.getvalue()
        self.assertEqual(image_size_from_bytes(raw), (120, 220))
        crop_jpeg, w, h, y0 = crop_bottom_strip_jpeg(raw, 0.3)
        self.assertEqual((w, h), (120, 220))
        self.assertEqual(y0, int(220 * 0.7))
        proc = preprocess_mrz_strip(crop_jpeg)
        self.assertGreater(len(proc), 50)

    def test_mrz_second_pass_pipeline_returns_three_jpegs(self):
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (180, 360), (240, 240, 240)).save(buf, format="JPEG")
        raw = buf.getvalue()
        r = build_mrz_crop_for_paddle_second_pass(
            raw,
            height_ratio=0.33,
            ocr_items=[],
            full_height=None,
            upscale=2,
            use_otsu=False,
        )
        self.assertGreater(len(r.crop_raw_jpeg), 80)
        self.assertGreater(len(r.deskewed_jpeg), 80)
        self.assertGreater(len(r.preprocessed_jpeg), 80)
        self.assertGreater(r.crop_y0, 0)
        self.assertIn(r.skew_source, ("none", "hough", "ocr_boxes", "pil_fallback_no_cv2"))

    def test_mrz_crop_pil_fallback_when_cv2_disabled(self):
        from io import BytesIO
        from unittest.mock import patch

        from PIL import Image

        from reception.services import mrz_image_crop as mic

        buf = BytesIO()
        Image.new("RGB", (100, 200), (200, 200, 200)).save(buf, format="JPEG")
        raw = buf.getvalue()
        with patch.object(mic, "_CV2_AVAILABLE", False):
            r = mic.build_mrz_crop_for_paddle_second_pass(
                raw, height_ratio=0.3, ocr_items=[], full_height=None, upscale=2
            )
        self.assertEqual(r.skew_source, "pil_fallback_no_cv2")
        self.assertEqual(r.deskew_angle_deg, 0.0)


class OcrGrayscalePreprocessTests(TestCase):
    def test_grayscale_makes_uniform_rgb_channels(self):
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (20, 20), (200, 10, 30)).save(buf, format="JPEG", quality=95)
        raw = buf.getvalue()
        with override_settings(SCAN_OCR_GRAYSCALE_BEFORE_PREDICT=True):
            out = prepare_image_bytes_for_paddle_ocr(raw)
        self.assertNotEqual(out, raw)
        with Image.open(BytesIO(out)) as im:
            self.assertEqual(im.mode, "RGB")
            r, g, b = im.getpixel((10, 10))
            self.assertLess(abs(r - g), 3)
            self.assertLess(abs(g - b), 3)

    def test_grayscale_disabled_returns_same_bytes(self):
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (5, 5), (1, 2, 3)).save(buf, format="JPEG")
        raw = buf.getvalue()
        with override_settings(SCAN_OCR_GRAYSCALE_BEFORE_PREDICT=False):
            out = prepare_image_bytes_for_paddle_ocr(raw)
        self.assertEqual(out, raw)


class OcrSampleStoreTests(TestCase):
    def test_disabled_returns_none(self):
        with override_settings(SCAN_OCR_SAMPLE_DIR=""):
            p = save_scan_upload_sample(b"abc", guest_id=1, original_filename="x.jpg")
            self.assertIsNone(p)

    def test_writes_file_under_temp_dir(self):
        import tempfile

        from django.conf import settings as dj_settings

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(SCAN_OCR_SAMPLE_DIR=tmp, BASE_DIR=dj_settings.BASE_DIR):
                p = save_scan_upload_sample(b"hello-scan", guest_id=42, original_filename="doc.png")
            self.assertIsNotNone(p)
            base = Path(dj_settings.BASE_DIR)
            full = base / p if not Path(p).is_absolute() else Path(p)
            self.assertTrue(full.is_file())
            self.assertEqual(full.read_bytes(), b"hello-scan")
            self.assertIn("guest42", full.name)

    def test_debug_sidecar_writes_adjacent_json(self):
        import json
        import tempfile

        from django.conf import settings as dj_settings

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(
                SCAN_OCR_SAMPLE_DIR=tmp,
                SCAN_OCR_DEBUG_JSON=True,
                BASE_DIR=dj_settings.BASE_DIR,
            ):
                p = save_scan_upload_sample(b"fake-jpeg", guest_id=7, original_filename="doc.jpg")
                self.assertIsNotNone(p)
                q = save_scan_debug_sidecar(p, {"probe": True, "nested": {"a": 1}})
            self.assertIsNotNone(q)
            base = Path(dj_settings.BASE_DIR)
            jpath = base / q if not Path(q).is_absolute() else Path(q)
            self.assertTrue(jpath.is_file())
            self.assertEqual(jpath.suffix, ".json")
            self.assertEqual(jpath.with_suffix(".jpg").name, Path(p).name)
            self.assertEqual(json.loads(jpath.read_text(encoding="utf-8")), {"probe": True, "nested": {"a": 1}})

    def test_debug_sidecar_respects_disable_flag(self):
        import tempfile

        from django.conf import settings as dj_settings

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(
                SCAN_OCR_SAMPLE_DIR=tmp,
                SCAN_OCR_DEBUG_JSON=False,
                BASE_DIR=dj_settings.BASE_DIR,
            ):
                p = save_scan_upload_sample(b"x", guest_id=1, original_filename="z.jpg")
                self.assertIsNotNone(p)
                q = save_scan_debug_sidecar(p, {"x": 1})
            self.assertIsNone(q)
            base = Path(dj_settings.BASE_DIR)
            img = base / p if not Path(p).is_absolute() else Path(p)
            self.assertFalse(img.with_suffix(".json").exists())

    def test_paddle_raw_sidecar_writes_dot_paddle_json(self):
        import json
        import tempfile

        from django.conf import settings as dj_settings

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(
                SCAN_OCR_SAMPLE_DIR=tmp,
                SCAN_OCR_PADDLE_RAW_JSON=True,
                BASE_DIR=dj_settings.BASE_DIR,
            ):
                p = save_scan_upload_sample(b"x", guest_id=3, original_filename="id.jpg")
                self.assertIsNotNone(p)
                q = save_scan_paddle_raw_sidecar(
                    p,
                    paddle_response={"results": [[{"text": "A"}]]},
                    paddle_response_mrz_crop=None,
                    mrz_second_pass={"used": False},
                )
            self.assertIsNotNone(q)
            base = Path(dj_settings.BASE_DIR)
            jpath = base / q if not Path(q).is_absolute() else Path(q)
            self.assertTrue(jpath.name.endswith(".paddle.json"))
            data = json.loads(jpath.read_text(encoding="utf-8"))
            self.assertIn("paddle_response", data)
            self.assertIsNone(data.get("paddle_response_mrz_crop"))
            self.assertEqual(data.get("mrz_second_pass"), {"used": False})

    def test_paddle_raw_sidecar_respects_disable_flag(self):
        import tempfile

        from django.conf import settings as dj_settings

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(
                SCAN_OCR_SAMPLE_DIR=tmp,
                SCAN_OCR_PADDLE_RAW_JSON=False,
                BASE_DIR=dj_settings.BASE_DIR,
            ):
                p = save_scan_upload_sample(b"x", guest_id=1, original_filename="a.jpg")
                self.assertIsNotNone(p)
                q = save_scan_paddle_raw_sidecar(
                    p, paddle_response={}, paddle_response_mrz_crop=None, mrz_second_pass=None
                )
            self.assertIsNone(q)


class MrzPipelineTests(TestCase):
    def test_single_char_confusion_restores_valid_td3(self):
        code = str(TD3CodeGenerator("P", "UTO", "ERIKSSON", "ANNA MARIA", "X12345678", "UTO", "760813", "F", "260203"))
        l1, l2 = code.split("\n")
        bad_l2 = l2[:3] + "O" + l2[4:]
        r = run_mrz_pipeline([{"text": l1}, {"text": bad_l2}])
        self.assertTrue(r["checksum_valid"])
        self.assertEqual(r["suggested_fields"].get("document_number"), "X12345678")

    def test_td1_icao_each_row_exactly_thirty_chars(self):
        from mrz.generator.td1 import TD1CodeGenerator

        from reception.services.mrz_pipeline import (
            TD1_LINE_CHAR_COUNT,
            _td1_row_icao_width,
        )

        self.assertEqual(TD1_LINE_CHAR_COUNT, 30)
        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        for row in code.strip().splitlines():
            self.assertEqual(len(row), TD1_LINE_CHAR_COUNT)
        short = "I0HRV11938408791152856454<<<<"  # 29 znakova — mora postati 30
        fixed = _td1_row_icao_width(short)
        self.assertEqual(len(fixed), 30)

    def test_smart_padding_fix_pads_to_nearest_width(self):
        from reception.services.mrz_pipeline import smart_padding_fix

        self.assertEqual(len(smart_padding_fix("A" * 25)), 30)
        self.assertEqual(smart_padding_fix("A" * 25), "A" * 25 + "<" * 5)

    def test_smart_padding_fix_end_suspicious_to_chevron(self):
        from reception.services.mrz_pipeline import smart_padding_fix

        line = "A" * 29 + "Z"
        self.assertEqual(len(line), 30)
        out = smart_padding_fix(line)
        self.assertEqual(len(out), 30)
        self.assertTrue(out.endswith("<"), out)

    def test_td1_hrv_padding_z_read_as_chevron(self):
        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        l1, l2, l3 = code.strip().split("\n")
        self.assertEqual(len(l1), 30)
        self.assertEqual(len(l2), 30)
        idx = l2.rfind("HRV")
        tail = l2[idx + 3 :]
        bad_tail = tail[:7] + "ZZ" + tail[9:]
        bad_l2 = l2[: idx + 3] + bad_tail
        r = run_mrz_pipeline([{"text": l1}, {"text": bad_l2}, {"text": l3}])
        self.assertTrue(r["checksum_valid"])
        self.assertEqual(r.get("format"), "TD1")

    def test_td1_three_lines_in_one_ocr_blob(self):
        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        l1, l2, l3 = code.strip().split("\n")
        blob = l1 + l2 + l3
        r = run_mrz_pipeline([{"text": blob}])
        self.assertTrue(r["checksum_valid"])
        self.assertEqual(r.get("format"), "TD1")

    def test_td1_embedded_after_digit_prefix(self):
        """OIB/MBO spojeni s MRZ u jednoj OCR regiji (dugačak niz)."""
        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        l1, l2, l3 = code.strip().split("\n")
        noise = "18528564544128905240"
        blob = noise + l1 + l2 + l3
        r = run_mrz_pipeline([{"text": blob}])
        self.assertTrue(r["checksum_valid"], r)
        self.assertEqual(r.get("format"), "TD1")

    def test_td1_bottom_ocr_tail_processed_before_address_lines(self):
        """MRZ na dnu kadra: kandidati iz zadnje tri stavke (Y) moraju biti prije adresnih paddinga."""
        from reception.services.mrz_pipeline import _candidate_strings

        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        l1, l2, l3 = code.strip().split("\n")

        def box(y0: float) -> list[list[float]]:
            return [[0.0, y0], [400.0, y0], [400.0, y0 + 40.0], [0.0, y0 + 40.0]]

        items: list[dict[str, object]] = [
            {"text": "PREBIVALISTEIRESIDENCE", "confidence": 0.99, "box": box(50.0)},
            {"text": "NJEMACKAHANAU", "confidence": 0.98, "box": box(120.0)},
            {"text": "GARTNERSTRABE44", "confidence": 0.97, "box": box(200.0)},
            {"text": l1, "confidence": 0.96, "box": box(1100.0)},
            {"text": l2, "confidence": 0.95, "box": box(1240.0)},
            {"text": l3, "confidence": 0.94, "box": box(1380.0)},
        ]
        cands = _candidate_strings(items)
        self.assertGreaterEqual(len(cands), 3)
        self.assertEqual(cands[0], l1)
        self.assertEqual(cands[1], l2)
        self.assertEqual(cands[2], l3)
        r = run_mrz_pipeline(items)
        self.assertTrue(r["checksum_valid"], r)

    def test_td1_paddle_i_zero_and_filler_noise_canonicalizes_to_valid_mrz(self):
        """Stvarni Paddle izlaz: I0 umjesto I<, Z/X u ispuni — checksum mora proći."""
        from reception.services.mrz_pipeline import _try_td1_from_extracted_three

        three = [
            "I0HRV119384087911528564544<<<<",
            "7604234M3005121HRV<<<<<<<<Z<9<",
            "VRCAN<<ANTE<<<<<<<<<X<<X<<<<<<",
        ]
        hit, _raw, _last = _try_td1_from_extracted_three(three, max_brute=4000)
        self.assertIsNotNone(hit, "TD1 attempt expected")
        assert hit is not None
        self.assertTrue(bool(hit.checker))
        self.assertEqual(hit.lines[0][:5], "I<HRV")

    def test_td1_multiline_bfs_restores_padding_and_separator(self):
        """Više jednostavnih zamjena (Z, K, C) koje MRZ_SUBSTITUTIONS pokriva + smart_padding."""
        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        l1, l2, l3 = code.strip().split("\n")
        idx = l2.rfind("HRV")
        tail = l2[idx + 3 :]
        bad_tail = tail[:7] + "ZZ" + tail[9:]
        bad_l2 = l2[: idx + 3] + bad_tail
        bad_l3 = "VRCANKCANTE<<<<<<<<<<<<<<<<<<<"
        r = run_mrz_pipeline([{"text": l1}, {"text": bad_l2}, {"text": bad_l3}])
        self.assertTrue(r["checksum_valid"], r)
        self.assertEqual(r.get("format"), "TD1")


class Td1MrzExtractTests(TestCase):
    """TD1 MRZ izdvajanje iz OCR-a (bez adresnih redaka); crop merge prioritet."""

    @staticmethod
    def _box(y0: float) -> list[list[float]]:
        return [[0.0, y0], [400.0, y0], [400.0, y0 + 40.0], [0.0, y0 + 40.0]]

    def test_extract_eight_ocr_lines_returns_only_three_mrz_rows(self):
        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        l1, l2, l3 = code.strip().split("\n")
        items: list[dict[str, object]] = [
            {"text": "PREBIVALISTERESIDENCE", "confidence": 0.99, "box": self._box(50.0)},
            {"text": "NJEMACKAHANAU", "confidence": 0.98, "box": self._box(120.0)},
            {"text": "GARTNERSTRASE44", "confidence": 0.97, "box": self._box(200.0)},
            {"text": "IZDALAISSUEDBY", "confidence": 0.96, "box": self._box(260.0)},
            {"text": "OIB12345678901", "confidence": 0.95, "box": self._box(320.0)},
            {"text": l1, "confidence": 0.94, "box": self._box(1100.0)},
            {"text": l2, "confidence": 0.93, "box": self._box(1240.0)},
            {"text": l3, "confidence": 0.92, "box": self._box(1380.0)},
        ]
        lines, meta = extract_td1_mrz_from_ocr(items, image_height=1600)
        self.assertEqual(len(lines), 3, meta)
        joined = "\n".join(lines)
        self.assertNotIn("PREBIVALISTE", joined)
        self.assertNotIn("IZDALAISSUEDBY", joined)
        self.assertNotIn("GARTNERSTRASE", joined)
        r = run_mrz_pipeline(items, image_height=1600)
        self.assertEqual(len(r.get("lines") or []), 3)
        self.assertTrue(r.get("checksum_valid"))

    def test_extract_each_line_length_thirty(self):
        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        l1, l2, l3 = code.strip().split("\n")
        self.assertEqual(len(l1), 30)
        short_l1 = l1.rstrip("<")  # kraće od 30, još uvijek MRZ-like
        self.assertLess(len(short_l1), 30)
        items = [
            {"text": short_l1, "confidence": 0.9, "box": self._box(900.0)},
            {"text": l2, "confidence": 0.9, "box": self._box(1000.0)},
            {"text": l3, "confidence": 0.9, "box": self._box(1100.0)},
        ]
        lines, _ = extract_td1_mrz_from_ocr(items, image_height=1200)
        self.assertEqual(len(lines), 3)
        for ln in lines:
            self.assertEqual(len(ln), 30, ln)

    def test_bad_third_ocr_line_without_chevron_still_returns_td1_partial(self):
        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        l1, l2, _l3 = code.strip().split("\n")
        bad_l3 = "VRCANKANTEKWKEEKAAAKK"
        items: list[dict[str, object]] = [
            {"text": l1, "confidence": 0.96, "box": self._box(900.0)},
            {"text": l2, "confidence": 0.95, "box": self._box(1000.0)},
            {"text": bad_l3, "confidence": 0.5, "box": self._box(1100.0)},
        ]
        r = run_mrz_pipeline(items, image_height=1200)
        self.assertEqual(r.get("format"), "TD1")
        parsed = r.get("parsed") or {}
        self.assertEqual(parsed.get("document_number"), "119384087")
        self.assertEqual(parsed.get("issuing_state"), "HRV")
        self.assertEqual(parsed.get("birth_date"), "1976-04-23")
        # Ne smije pasti bez TD1 strukture; BFS može ispraviti ime ili ostaviti checksum nevaljan
        self.assertIsNotNone(r.get("lines"))
        self.assertEqual(len(r.get("lines") or []), 3)

    def test_merged_crop_three_mrz_preferred_over_noisy_full_strip(self):
        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        l1, l2, l3 = code.strip().split("\n")
        full_h = 500
        crop_y0 = 340
        full_items: list[dict[str, object]] = [
            {"text": "HEADER", "confidence": 0.99, "box": self._box(40.0)},
            {
                "text": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                "confidence": 0.5,
                "box": self._box(450.0),
            },
        ]
        crop_items: list[dict[str, object]] = [
            {"text": l1, "confidence": 0.95, "box": self._box(10.0)},
            {"text": l2, "confidence": 0.94, "box": self._box(40.0)},
            {"text": l3, "confidence": 0.93, "box": self._box(70.0)},
        ]
        merged = merge_fullframe_and_mrz_crop_items(
            full_items,
            crop_items,
            full_height=full_h,
            crop_y0=crop_y0,
            margin_px=8.0,
        )
        r = run_mrz_pipeline(merged, image_height=full_h, mrz_strip_y0=float(crop_y0))
        self.assertTrue(r["checksum_valid"], r)
        self.assertEqual(r.get("format"), "TD1")


class AddressFromOcrTests(TestCase):
    """Prebivalište iz OCR stavki iznad MRZ trake → suggested_fields.address."""

    @staticmethod
    def _box(y0: float, y1: float | None = None) -> list[list[float]]:
        if y1 is None:
            y1 = y0 + 40.0
        return [[0.0, y0], [400.0, y0], [400.0, y1], [0.0, y1]]

    def test_residence_block_below_mrz_strip(self):
        from reception.services.address_from_ocr import suggest_residence_address_from_items

        items: list[dict[str, object]] = [
            {"text": "PREBIVALISTE/RESIDENCE", "confidence": 0.993, "box": self._box(100.0, 140.0)},
            {"text": "NJEMACKA, HANAU", "confidence": 0.971, "box": self._box(154.0, 225.0)},
            {"text": "GARTNERSTRABE 44", "confidence": 0.954, "box": self._box(237.0, 308.0)},
            {"text": "IZDALA/ISSUED BY", "confidence": 0.94, "box": self._box(414.0, 462.0)},
            {"text": "PP VODICE", "confidence": 0.99, "box": self._box(471.0, 539.0)},
        ]
        r = suggest_residence_address_from_items(items, mrz_strip_y0=900.0)
        self.assertEqual(r["address_lines"], ["NJEMAČKA, HANAU", "GÄRTNERSTRAẞE 44"])
        self.assertEqual(r["address"], "NJEMAČKA, HANAU, GÄRTNERSTRAẞE 44")

    def test_ntemackashanau_ocr_prefix_split(self):
        from reception.services.address_from_ocr import suggest_residence_address_from_items

        items: list[dict[str, object]] = [
            {"text": "NTEMACKASHANAU", "confidence": 0.93, "box": self._box(154.0, 225.0)},
        ]
        r = suggest_residence_address_from_items(items, mrz_strip_y0=900.0)
        self.assertEqual(r["address_lines"], ["NJEMAČKA, HANAU"])

    def test_gartnerstrasew_street_fix(self):
        from reception.services.address_from_ocr import suggest_residence_address_from_items

        items: list[dict[str, object]] = [
            {"text": "GARTNERSTRASEW44", "confidence": 0.92, "box": self._box(237.0, 308.0)},
        ]
        r = suggest_residence_address_from_items(items, mrz_strip_y0=900.0)
        self.assertEqual(r["address_lines"], ["GÄRTNERSTRAẞE 44"])

    def test_njemackamhanau_split_country_city(self):
        from reception.services.address_from_ocr import suggest_residence_address_from_items

        items: list[dict[str, object]] = [
            {"text": "NJEMACKAMHANAU", "confidence": 0.93, "box": self._box(154.0, 225.0)},
        ]
        r = suggest_residence_address_from_items(items, mrz_strip_y0=900.0)
        self.assertEqual(r["address_lines"], ["NJEMAČKA, HANAU"])

    def test_strabe_suffix_normalized_to_strasse(self):
        from reception.services.address_from_ocr import suggest_residence_address_from_items

        items: list[dict[str, object]] = [
            {"text": "HAUPTSTRABE 12", "confidence": 0.92, "box": self._box(100.0, 140.0)},
        ]
        r = suggest_residence_address_from_items(items, mrz_strip_y0=500.0)
        self.assertEqual(r["address_lines"], ["HAUPTSTRAẞE 12"])

    def test_mrz_like_row_in_address_zone_excluded(self):
        from reception.services.address_from_ocr import suggest_residence_address_from_items

        items: list[dict[str, object]] = [
            {
                "text": "I<HRV1193840879<<<<<<<<<<<<<<<",
                "confidence": 0.96,
                "box": self._box(400.0, 440.0),
            },
        ]
        r = suggest_residence_address_from_items(items, mrz_strip_y0=600.0)
        self.assertEqual(r, {})

    def test_concatenated_paddle_blob_like_mobile_ocr_sample(self):
        """Jedan dugačak OCR redak (label + adresa + IZDALA) — tipično na uređaju."""
        from reception.services.address_from_ocr import suggest_residence_address_from_items

        blob = (
            "PREBIVALISTE/RESIDENCE KCard NSJEMACKAHANAU GARTNERSTRABE4A "
            "2304-1976 IZDALA/ISSUEDBY PPEVODICE DATUMIZDAVANJA/DATEOF-ISSUE "
            "12052025 OIB/PIN 11528564544"
        )
        items: list[dict[str, object]] = [
            {"text": blob, "confidence": 0.91},
        ]
        r = suggest_residence_address_from_items(items, mrz_strip_y0=900.0)
        self.assertIn("NJEMAČKA", r.get("address", ""))
        self.assertTrue(
            any("GÄRTNERSTRA" in ln or "GARTNERSTR" in ln for ln in r.get("address_lines", [])),
            r,
        )


class PaddleDocumentScanViewTests(TestCase):
    def setUp(self):
        self.rt = RoomType.objects.create(code="OCR", name_i18n={"en": "OCR Room"})
        self.res = Reservation.objects.create(
            external_id="paddle-scan-1",
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

    @override_settings(PADDLE_OCR_BASE_URL="http://paddle.test", MRZ_OCR_SECOND_PASS=False)
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

    @override_settings(PADDLE_OCR_BASE_URL="http://paddle.test", MRZ_OCR_SECOND_PASS=True)
    def test_scan_mrz_second_pass_merge(self):
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (300, 500), (240, 240, 230)).save(buf, format="JPEG")
        img = buf.getvalue()

        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                "119384087",
                "760423",
                "M",
                "300512",
                "HRV",
                "VRCAN",
                "ANTE",
            )
        )
        l1, l2, l3 = code.strip().split("\n")
        crop_items = [
            {"text": l1, "confidence": 0.95, "box": [[0.0, 10.0], [200.0, 10.0], [200.0, 35.0], [0.0, 35.0]]},
            {"text": l2, "confidence": 0.94, "box": [[0.0, 40.0], [200.0, 40.0], [200.0, 65.0], [0.0, 65.0]]},
            {"text": l3, "confidence": 0.93, "box": [[0.0, 70.0], [200.0, 70.0], [200.0, 95.0], [0.0, 95.0]]},
        ]

        def predict_side_effect(*, image_bytes, filename, content_type, skip_input_grayscale=False, mrz_crop_pass=False):
            if filename == "mrz_crop.jpg":
                return {"items": crop_items, "raw": {"pass": "crop"}, "http_status": 200}
            return {
                "items": [
                    {
                        "text": "BADWIDEMRZ",
                        "confidence": 0.5,
                        "box": [[0.0, 450.0], [280.0, 450.0], [280.0, 480.0], [0.0, 480.0]],
                    }
                ],
                "raw": {"pass": "full"},
                "http_status": 200,
            }

        client = APIClient()
        client.force_login(self.user)
        with patch.object(OCRService, "predict", side_effect=predict_side_effect):
            resp = client.post(
                "/api/v1/scan/",
                data={
                    "guest_id": self.guest.id,
                    "file": SimpleUploadedFile("id.jpg", img, content_type="image/jpeg"),
                },
                format="multipart",
            )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("mrz", {}).get("checksum_valid"))
        raw = resp.data.get("raw_payload") or {}
        self.assertTrue((raw.get("mrz_second_pass") or {}).get("used"))

    def test_reservation_mismatch_returns_400(self):
        other = Reservation.objects.create(
            external_id="paddle-scan-2",
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 3),
            status=ReservationStatus.EXPECTED,
        )
        client = APIClient()
        client.force_login(self.user)
        with override_settings(PADDLE_OCR_BASE_URL="http://paddle.test", MRZ_OCR_SECOND_PASS=False):
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


class VizIdExtractTests(TestCase):
    def test_build_expected_td1_from_vrcan_sample(self):
        from reception.services.viz_id_extract import build_expected_td1_lines

        lines = build_expected_td1_lines(
            {
                "surname": "VRCAN",
                "given_names": "ANTE",
                "document_number": "119384087",
                "birth_yymmdd": "760423",
                "expiry_yymmdd": "300512",
                "sex": "M",
                "nationality": "HRV",
            }
        )
        self.assertIsNotNone(lines)
        assert lines is not None
        self.assertEqual(len(lines[0]), 30)
        self.assertIn("119384087", lines[0])
        self.assertIn("VRCAN", lines[2])
        self.assertIn("ANTE", lines[2])

    def test_extract_viz_from_front_like_ocr(self):
        from reception.services.viz_id_extract import extract_viz_fields_from_ocr, viz_fields_sufficient

        items = [
            {"text": "PREZIME/SURNAME", "box": [[100, 50], [200, 50], [200, 70], [100, 70]]},
            {"text": "VRCAN", "box": [[220, 50], [300, 50], [300, 70], [220, 70]]},
            {"text": "IME/NAME", "box": [[100, 90], [180, 90], [180, 110], [100, 110]]},
            {"text": "ANTE", "box": [[220, 90], [280, 90], [280, 110], [220, 110]]},
            {"text": "BROJ OSOBNE ISKAZNICE", "box": [[100, 200], [280, 200], [280, 220], [100, 220]]},
            {"text": "119384087", "box": [[300, 200], [420, 200], [420, 220], [300, 220]]},
            {"text": "DATUM RODENJA", "box": [[100, 150], [220, 150], [220, 170], [100, 170]]},
            {"text": "23 04 1976", "box": [[240, 150], [340, 150], [340, 170], [240, 170]]},
            {"text": "VRIJEDI DO", "box": [[100, 240], [200, 240], [200, 260], [100, 260]]},
            {"text": "12 05 2030", "box": [[220, 240], [320, 240], [320, 260], [220, 260]]},
        ]
        viz = extract_viz_fields_from_ocr(items)
        self.assertEqual(viz.get("surname"), "VRCAN")
        self.assertEqual(viz.get("given_names"), "ANTE")
        self.assertEqual(viz.get("document_number"), "119384087")
        self.assertEqual(viz.get("birth_yymmdd"), "760423")
        self.assertEqual(viz.get("expiry_yymmdd"), "300512")
        self.assertTrue(viz_fields_sufficient(viz))

    def test_mrz_pipeline_uses_viz_hints_when_ocr_corrupt(self):
        from reception.services.viz_id_extract import build_expected_td1_lines

        viz_lines = build_expected_td1_lines(
            {
                "surname": "VRCAN",
                "given_names": "ANTE",
                "document_number": "119384087",
                "birth_yymmdd": "760423",
                "expiry_yymmdd": "300512",
                "sex": "M",
            }
        )
        self.assertIsNotNone(viz_lines)
        l1, l2, l3 = viz_lines
        bad_l2 = l2[:8] + "O" + l2[9:]  # corrupt expiry digit
        r = run_mrz_pipeline(
            [{"text": l1}, {"text": bad_l2}, {"text": l3}],
            viz_hint_lines=viz_lines,
        )
        self.assertTrue(r["checksum_valid"])
        self.assertEqual(r["suggested_fields"].get("document_number"), "119384087")

    def test_cross_check_warnings_on_mismatch(self):
        from reception.services.viz_id_extract import cross_check_mrz_vs_viz

        warnings = cross_check_mrz_vs_viz(
            {
                "document_number": "000000000",
                "last_name": "VRCAN",
                "first_name": "ANTE",
            },
            {"document_number": "119384087", "surname": "VRCAN", "given_names": "ANTE"},
        )
        self.assertTrue(any("dokumenta" in w.lower() for w in warnings))


class PaddleDocumentScanFrontTests(TestCase):
    def setUp(self):
        self.rt = RoomType.objects.create(code="OCR-F", name_i18n={"en": "OCR"})
        self.res = Reservation.objects.create(
            external_id="paddle-front-1",
            check_in_date=date(2026, 8, 1),
            check_out_date=date(2026, 8, 5),
            status=ReservationStatus.EXPECTED,
        )
        self.guest = Guest.objects.create(
            reservation=self.res,
            first_name="Ana",
            last_name="Test",
        )
        self.user = User.objects.create_user("paddle_front", password="test-pass-123")

    @override_settings(PADDLE_OCR_BASE_URL="http://paddle.test", MRZ_OCR_SECOND_PASS=True)
    def test_front_scan_returns_viz_fields_without_mrz(self):
        items = [
            {"text": "PREZIME/SURNAME VRCAN", "confidence": 0.95},
            {"text": "IME/NAME ANTE", "confidence": 0.95},
            {"text": "119384087", "confidence": 0.99},
        ]
        client = APIClient()
        client.force_login(self.user)
        with patch.object(OCRService, "predict", return_value={"items": items, "raw": {}, "http_status": 200}):
            resp = client.post(
                "/api/v1/scan/",
                data={
                    "guest_id": self.guest.id,
                    "document_side": "front",
                    "file": SimpleUploadedFile("front.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
                },
                format="multipart",
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.get("scan_status"), DocumentScanStatus.OK)
        viz = (resp.data.get("suggested_fields") or {}).get("viz_fields") or {}
        self.assertTrue(viz.get("document_number") or (viz.get("surname") and viz.get("given_names")))
        self.assertFalse(resp.data.get("mrz", {}).get("checksum_valid"))


class BookingXlsImportTests(TestCase):
    def _sample_row(self, **overrides) -> BookingXlsRow:
        base = dict(
            external_id="5307026805",
            booker_name="Kumar, Jayachandar",
            guest_names=["Jayachandar Kumar"],
            check_in_date=date(2026, 5, 16),
            check_out_date=date(2026, 5, 17),
            booked_at=datetime(2026, 5, 3, 20, 34, 55),
            booking_status="ok",
            units_count=1,
            persons_count=4,
            adults_count=2,
            children_count=2,
            children_ages="0, 6",
            total_amount=Decimal("92.65"),
            currency="EUR",
            commission_percent=Decimal("18"),
            commission_amount=Decimal("16.677"),
            payment_status="Naplata putem Booking.com-a",
            payment_provider="",
            notes="Quiet room please",
            booker_country="CH",
            travel_purpose="Razonoda",
            booking_device="Mobitel",
            room_name="Luxury Room Uzorita - R3",
            nights_count=1,
            canceled_at=None,
            booker_address="",
            booker_phone="",
        )
        base.update(overrides)
        return BookingXlsRow(**base)

    def test_upsert_creates_reservation_with_all_booking_fields(self):
        row = self._sample_row()
        result = upsert_reservation_from_xls_row(row)
        self.assertTrue(result.created)
        res = Reservation.objects.get(external_id="5307026805")
        self.assertEqual(res.booker_name, "Kumar, Jayachandar")
        self.assertEqual(res.booking_status, "ok")
        self.assertEqual(res.status, ReservationStatus.EXPECTED)
        self.assertEqual(res.total_amount, Decimal("92.65"))
        self.assertEqual(res.units_count, 1)
        self.assertEqual(res.notes, "Quiet room please")
        self.assertEqual(res.import_source, ImportSource.BOOKING_XLS)
        self.assertIsNotNone(res.imported_at)
        primary = Guest.objects.get(reservation=res, is_primary=True)
        self.assertEqual(primary.first_name, "Jayachandar")
        self.assertEqual(primary.last_name, "Kumar")

    def test_upsert_updates_same_external_id_without_duplicate(self):
        row = self._sample_row()
        upsert_reservation_from_xls_row(row)
        row2 = self._sample_row(notes="Updated note")
        result = upsert_reservation_from_xls_row(row2)
        self.assertFalse(result.created)
        self.assertTrue(result.updated)
        self.assertFalse(result.skipped)
        self.assertEqual(Reservation.objects.filter(external_id="5307026805").count(), 1)
        self.assertEqual(Reservation.objects.get(external_id="5307026805").notes, "Updated note")

    def test_extra_guests_are_not_removed_on_reimport(self):
        row = self._sample_row()
        upsert_reservation_from_xls_row(row)
        res = Reservation.objects.get(external_id="5307026805")
        extra = Guest.objects.create(
            reservation=res,
            first_name="Manual",
            last_name="Guest",
            is_primary=False,
        )
        upsert_reservation_from_xls_row(row)
        self.assertTrue(Guest.objects.filter(pk=extra.pk).exists())
        self.assertEqual(res.guests.count(), 2)

    def test_identical_reimport_is_skipped(self):
        row = self._sample_row()
        first = upsert_reservation_from_xls_row(row)
        res = Reservation.objects.get(external_id="5307026805")
        imported_at = res.imported_at
        second = upsert_reservation_from_xls_row(row)
        res.refresh_from_db()
        self.assertTrue(first.created)
        self.assertTrue(second.skipped)
        self.assertFalse(second.updated)
        self.assertEqual(res.imported_at, imported_at)

    def test_cancelled_by_guest_sets_canceled_status(self):
        row = self._sample_row(booking_status="cancelled_by_guest")
        upsert_reservation_from_xls_row(row)
        res = Reservation.objects.get(external_id="5307026805")
        self.assertEqual(res.status, ReservationStatus.CANCELED)

    def test_checked_in_status_not_overwritten_on_reimport(self):
        row = self._sample_row()
        upsert_reservation_from_xls_row(row)
        res = Reservation.objects.get(external_id="5307026805")
        res.status = ReservationStatus.CHECKED_IN
        res.save(update_fields=["status", "updated_at"])
        row2 = self._sample_row(booking_status="cancelled_by_guest")
        upsert_reservation_from_xls_row(row2)
        res.refresh_from_db()
        self.assertEqual(res.status, ReservationStatus.CHECKED_IN)
        self.assertEqual(res.booking_status, "cancelled_by_guest")

    def test_split_guest_names_by_comma_for_two_full_names(self):
        names = _split_guest_names("SLADANA SKORIC,MARKO SKORIC")
        self.assertEqual(len(names), 2)

    def test_split_guest_names_keeps_last_first_format(self):
        names = _split_guest_names("Kumar, Jayachandar")
        self.assertEqual(names, ["Kumar, Jayachandar"])

    def test_multi_guest_names_create_multiple_guests(self):
        row = self._sample_row(
            guest_names=["Chananya Sripongphichit", "Khanitha Poonowvarat"],
            external_id="5192121426",
        )
        upsert_reservation_from_xls_row(row)
        guests = Guest.objects.filter(reservation__external_id="5192121426").order_by("-is_primary")
        self.assertEqual(guests.count(), 2)
        self.assertTrue(guests.first().is_primary)

    def test_multi_room_row_keeps_joined_room_names(self):
        from reception.reservation_units import joined_room_names

        row = self._sample_row(
            external_id="5029796224",
            units_count=3,
            room_name="Luxury Room Uzorita - R3, Luxury Room Uzorita - R2, Luxury Room Uzorita - R1",
        )
        upsert_reservation_from_xls_row(row)
        res = Reservation.objects.get(external_id="5029796224")
        joined = joined_room_names(res)
        self.assertIn("R3", joined)
        self.assertIn("R1", joined)

    def test_multi_room_creates_reservation_units(self):
        from reception.models import ReservationUnit

        row = self._sample_row(
            external_id="6566035917",
            units_count=2,
            room_name="Luxury Room Uzorita - R2, Luxury Room Uzorita - R1",
        )
        upsert_reservation_from_xls_row(row)
        res = Reservation.objects.get(external_id="6566035917")
        units = list(ReservationUnit.objects.filter(reservation=res).order_by("sort_order"))
        self.assertEqual(len(units), 2)
        self.assertIn("R2", units[0].room_name)
        self.assertIn("R1", units[1].room_name)

    def test_multi_room_sets_room_type_and_split_amount(self):
        from reception.models import ReservationUnit
        from rooms.models import Room, RoomType

        rt_r1 = RoomType.objects.create(code="R1", name_i18n={"en": "King"})
        rt_r3 = RoomType.objects.create(code="R3", name_i18n={"en": "Triple"})
        Room.objects.create(code="K1", room_type=rt_r1, is_active=True)
        Room.objects.create(code="T1", room_type=rt_r3, is_active=True)

        row = self._sample_row(
            external_id="6748210815-test",
            units_count=2,
            room_name="Luxury Room Uzorita - R1, Luxury Room Uzorita - R3",
            total_amount=Decimal("159.80"),
        )
        upsert_reservation_from_xls_row(row)
        res = Reservation.objects.get(external_id="6748210815-test")
        units = list(ReservationUnit.objects.filter(reservation=res).order_by("sort_order"))
        self.assertEqual(units[0].room_type_id, rt_r1.id)
        self.assertEqual(units[1].room_type_id, rt_r3.id)
        self.assertEqual(units[0].room_id, Room.objects.get(code="K1").id)
        self.assertEqual(units[0].amount, Decimal("79.90"))
        self.assertEqual(units[1].amount, Decimal("79.90"))

    def test_parse_english_header_xls_export(self):
        """Booking.com EN export uses 'Book number' instead of 'Broj rezervacije'."""
        from reception.booking_xls_import import XLS_HEADER_ALIASES, _normalize_header

        self.assertEqual(XLS_HEADER_ALIASES.get(_normalize_header("Book number")), "external_id")
        self.assertEqual(XLS_HEADER_ALIASES.get(_normalize_header("Check-in")), "check_in_date")
        self.assertEqual(XLS_HEADER_ALIASES.get(_normalize_header("Unit type")), "room_name")

        path = Path("/opt/stacks/uzorita/Reservation 2026-05-17 to 2026-05-18.xls")
        if not path.is_file():
            self.skipTest("EN xls fixture not available")
        rows = parse_booking_xls_bytes(path.read_bytes())
        self.assertGreaterEqual(len(rows), 1)
        patricia = next((r for r in rows if r.external_id == "5581435138"), None)
        self.assertIsNotNone(patricia)
        self.assertEqual(patricia.check_in_date, date(2026, 6, 28))
        self.assertEqual(patricia.check_out_date, date(2026, 7, 1))
        self.assertIn("R3", patricia.room_name)

    def test_parse_real_prijava_file_if_present(self):
        path = Path("/opt/stacks/uzorita/Prijava")
        if not path.is_file():
            self.skipTest("Prijava xls fixture not available")
        rows = parse_booking_xls(str(path))
        self.assertGreaterEqual(len(rows), 20)
        first = rows[0]
        self.assertEqual(first.external_id, "5307026805")
        self.assertEqual(first.currency, "EUR")

    def test_dry_run_import_counts(self):
        path = Path("/opt/stacks/uzorita/Prijava")
        if not path.is_file():
            self.skipTest("Prijava xls fixture not available")
        stats = import_booking_xls_file(str(path), dry_run=True)
        self.assertEqual(
            stats["total"],
            stats["created"] + stats["updated"] + stats["skipped"],
        )


class EnsureReservationUnitsCommandTests(TestCase):
    def test_skips_reservation_without_units(self):
        reservation = Reservation.objects.create(
            external_id="ensure-units-1",
            check_in_date=date(2026, 7, 1),
            check_out_date=date(2026, 7, 3),
            status=ReservationStatus.EXPECTED,
        )
        from django.core.management import call_command

        call_command("ensure_reservation_units", external_id="ensure-units-1")
        self.assertEqual(reservation.units.count(), 0)


class BookingXlsImportApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("xls_import_api", password="test-pass-123")
        self.client = APIClient()
        self.client.force_login(self.user)

    def _prijava_bytes(self) -> bytes | None:
        path = Path("/opt/stacks/uzorita/Prijava")
        if not path.is_file():
            return None
        return path.read_bytes()

    def test_requires_authentication(self):
        client = APIClient()
        response = client.post("/api/reception/booking-xls-import/")
        self.assertIn(response.status_code, (401, 403))

    def test_rejects_empty_upload(self):
        response = self.client.post("/api/reception/booking-xls-import/", {}, format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_rejects_non_xls_extension(self):
        response = self.client.post(
            "/api/reception/booking-xls-import/",
            {
                "files": SimpleUploadedFile("notes.txt", b"not xls", content_type="text/plain"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_dry_run_does_not_change_database(self):
        content = self._prijava_bytes()
        if content is None:
            self.skipTest("Prijava xls fixture not available")

        before = Reservation.objects.count()
        response = self.client.post(
            "/api/reception/booking-xls-import/",
            {
                "files": SimpleUploadedFile(
                    "Prijava.xls",
                    content,
                    content_type="application/vnd.ms-excel",
                ),
                "dry_run": "true",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), before)
        self.assertIn("summary", response.data)
        self.assertIn("files", response.data)
        self.assertTrue(response.data["dry_run"])
        self.assertGreater(response.data["summary"]["total"], 0)

    def test_import_returns_per_file_stats(self):
        content = self._prijava_bytes()
        if content is None:
            self.skipTest("Prijava xls fixture not available")

        response = self.client.post(
            "/api/reception/booking-xls-import/",
            {
                "files": SimpleUploadedFile(
                    "Prijava.xls",
                    content,
                    content_type="application/vnd.ms-excel",
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["dry_run"])
        self.assertEqual(len(response.data["files"]), 1)
        self.assertGreater(
            response.data["summary"]["created"]
            + response.data["summary"]["updated"]
            + response.data["summary"]["skipped"],
            0,
        )

    def test_parse_booking_xls_bytes_matches_file_parser(self):
        content = self._prijava_bytes()
        if content is None:
            self.skipTest("Prijava xls fixture not available")

        from_path = parse_booking_xls("/opt/stacks/uzorita/Prijava")
        from_bytes = parse_booking_xls_bytes(content)
        self.assertEqual(len(from_path), len(from_bytes))
        self.assertEqual(from_path[0].external_id, from_bytes[0].external_id)


class ReservationDetailApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("reservation_detail_api", password="test-pass-123")
        self.client = APIClient()
        self.client.force_login(self.user)
        self.rt = RoomType.objects.create(code="RDET", name_i18n={"en": "Detail Room"})
        self.room = Room.objects.create(code="D1", room_type=self.rt)
        self.reservation = Reservation.objects.create(
            external_id="detail-patch-1",
            check_in_date=date(2026, 8, 1),
            check_out_date=date(2026, 8, 3),
            status=ReservationStatus.EXPECTED,
        )
        ReservationUnit.objects.create(
            reservation=self.reservation,
            sort_order=0,
            room_name="Detail Room",
            room_type=self.rt,
            room=self.room,
        )

    def test_patch_updates_status(self):
        url = f"/api/reception/reservations/{self.reservation.id}/"
        response = self.client.patch(url, {"status": ReservationStatus.CHECKED_IN}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], ReservationStatus.CHECKED_IN)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, ReservationStatus.CHECKED_IN)

    def test_patch_rejects_invalid_status(self):
        url = f"/api/reception/reservations/{self.reservation.id}/"
        response = self.client.patch(url, {"status": "invalid_status"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_patch_allows_expected_to_checked_in(self):
        url = f"/api/reception/reservations/{self.reservation.id}/"
        response = self.client.patch(url, {"status": ReservationStatus.CHECKED_IN}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_patch_rejects_expected_to_checked_out(self):
        url = f"/api/reception/reservations/{self.reservation.id}/"
        response = self.client.patch(url, {"status": ReservationStatus.CHECKED_OUT}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_patch_rejects_checked_out_to_expected(self):
        self.reservation.status = ReservationStatus.CHECKED_OUT
        self.reservation.save(update_fields=["status", "updated_at"])
        url = f"/api/reception/reservations/{self.reservation.id}/"
        response = self.client.patch(url, {"status": ReservationStatus.EXPECTED}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_patch_rejects_checked_out_when_evisitor_incomplete(self):
        self.reservation.status = ReservationStatus.CHECKED_IN
        self.reservation.save(update_fields=["status", "updated_at"])
        Guest.objects.create(
            reservation=self.reservation,
            first_name="Ana",
            last_name="Test",
            is_primary=True,
            nationality="HR",
            sex="ženski",
            date_of_birth=date(1990, 1, 1),
            document_number="HR123",
            document_type="osobna",
        )
        url = f"/api/reception/reservations/{self.reservation.id}/"
        response = self.client.patch(url, {"status": ReservationStatus.CHECKED_OUT}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("reception.serializers.checkout_reservation_guests_in_evisitor")
    def test_patch_allows_checked_out_when_evisitor_complete(self, mock_checkout):
        self.reservation.status = ReservationStatus.CHECKED_IN
        self.reservation.save(update_fields=["status", "updated_at"])
        guest = Guest.objects.create(
            reservation=self.reservation,
            first_name="Ana",
            last_name="Test",
            is_primary=True,
            nationality="HR",
            sex="ženski",
            date_of_birth=date(1990, 1, 1),
            document_number="HR123",
            document_type="osobna",
            evisitor_status=EvisitorGuestStatus.SENT,
        )
        url = f"/api/reception/reservations/{self.reservation.id}/"
        response = self.client.patch(url, {"status": ReservationStatus.CHECKED_OUT}, format="json")
        self.assertEqual(response.status_code, 200)
        mock_checkout.assert_called_once()
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, ReservationStatus.CHECKED_OUT)

    @override_settings(
        EVISITOR_ENABLED=True,
        EVISITOR_ENV="test",
        EVISITOR_BASE_URL="https://www.evisitor.hr/testApi",
        EVISITOR_USERNAME="testuser",
        EVISITOR_PASSWORD="testpass",
        EVISITOR_API_KEY="testkey",
        EVISITOR_FACILITY_CODE="0000022",
    )
    @patch("reception.evisitor.service.EvisitorClient")
    def test_patch_checkout_updates_guest_evisitor_status(self, mock_client_cls):
        self.reservation.check_in_date = date(2026, 5, 15)
        self.reservation.check_out_date = date(2026, 5, 17)
        self.reservation.status = ReservationStatus.CHECKED_IN
        self.reservation.save(update_fields=["status", "check_in_date", "check_out_date", "updated_at"])
        reg_id = uuid.uuid4()
        guest = Guest.objects.create(
            reservation=self.reservation,
            first_name="Ana",
            last_name="Test",
            is_primary=True,
            nationality="HR",
            sex="ženski",
            date_of_birth=date(1990, 1, 1),
            document_number="HR123",
            document_type="osobna",
            evisitor_status=EvisitorGuestStatus.SENT,
            evisitor_registration_id=reg_id,
        )
        mock_client = mock_client_cls.return_value
        url = f"/api/reception/reservations/{self.reservation.id}/"
        response = self.client.patch(url, {"status": ReservationStatus.CHECKED_OUT}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        mock_client.login.assert_called_once()
        mock_client.execute_action.assert_called_once()
        self.assertEqual(mock_client.execute_action.call_args[0][0], "CheckOutTourist")
        guest.refresh_from_db()
        self.assertEqual(guest.evisitor_status, EvisitorGuestStatus.CHECKED_OUT)

    @override_settings(
        EVISITOR_ENABLED=True,
        EVISITOR_ENV="test",
        EVISITOR_BASE_URL="https://www.evisitor.hr/testApi",
        EVISITOR_USERNAME="testuser",
        EVISITOR_PASSWORD="testpass",
        EVISITOR_API_KEY="testkey",
        EVISITOR_FACILITY_CODE="0000022",
    )
    @patch("reception.evisitor.service.EvisitorClient")
    def test_patch_checkout_api_error_blocks_reservation_status(self, mock_client_cls):
        from reception.evisitor.exceptions import EvisitorApiError

        self.reservation.check_in_date = date(2026, 5, 15)
        self.reservation.check_out_date = date(2026, 5, 17)
        self.reservation.status = ReservationStatus.CHECKED_IN
        self.reservation.save(update_fields=["status", "check_in_date", "check_out_date", "updated_at"])
        Guest.objects.create(
            reservation=self.reservation,
            first_name="Ana",
            last_name="Test",
            is_primary=True,
            nationality="HR",
            sex="ženski",
            date_of_birth=date(1990, 1, 1),
            document_number="HR123",
            document_type="osobna",
            evisitor_status=EvisitorGuestStatus.SENT,
            evisitor_registration_id=uuid.uuid4(),
        )
        mock_client = mock_client_cls.return_value
        mock_client.execute_action.side_effect = EvisitorApiError("API greška")

        url = f"/api/reception/reservations/{self.reservation.id}/"
        response = self.client.patch(url, {"status": ReservationStatus.CHECKED_OUT}, format="json")
        self.assertEqual(response.status_code, 400)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, ReservationStatus.CHECKED_IN)


@override_settings(
    EVISITOR_ENABLED=True,
    EVISITOR_ENV="test",
    EVISITOR_BASE_URL="https://www.evisitor.hr/testApi",
    EVISITOR_USERNAME="testuser",
    EVISITOR_PASSWORD="testpass",
    EVISITOR_API_KEY="testkey",
    EVISITOR_FACILITY_CODE="0000022",
)
class EvisitorSubmitViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("evisitor_user", password="test-pass-123")
        self.client = APIClient()
        self.client.force_login(self.user)
        self.reservation = Reservation.objects.create(
            external_id="ev-1",
            check_in_date=date(2026, 6, 1),
            check_out_date=date(2026, 6, 5),
            status=ReservationStatus.CHECKED_IN,
        )
        self.guest = Guest.objects.create(
            reservation=self.reservation,
            first_name="Ivan",
            last_name="Horvat",
            is_primary=True,
            nationality="HR",
            sex="muški",
            date_of_birth=date(1985, 3, 15),
            document_number="123456789",
            document_type="osobna",
        )

    @patch("reception.evisitor.service.EvisitorClient")
    def test_submit_success(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.login.return_value = True
        mock_client.execute_action.return_value = None

        url = f"/api/reception/reservations/{self.reservation.id}/guests/{self.guest.id}/evisitor-submit/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], EvisitorGuestStatus.SENT)
        self.guest.refresh_from_db()
        self.assertEqual(self.guest.evisitor_status, EvisitorGuestStatus.SENT)

    def test_submit_validation_error_when_incomplete_guest(self):
        self.guest.document_number = ""
        self.guest.save(update_fields=["document_number", "updated_at"])
        url = f"/api/reception/reservations/{self.reservation.id}/guests/{self.guest.id}/evisitor-submit/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "validation_failed")
        self.assertIn("document_number", response.data["field_errors"])
        self.assertIn("Broj dokumenta", response.data["message"])


class EvisitorMapperTests(TestCase):
    @override_settings(EVISITOR_FACILITY_CODE="0000022")
    def test_build_check_in_payload_maps_belgian_citizenship(self):
        reservation = Reservation.objects.create(
            external_id="map-be-1",
            check_in_date=date(2026, 6, 1),
            check_out_date=date(2026, 6, 5),
        )
        guest = Guest.objects.create(
            reservation=reservation,
            first_name="Vincent",
            last_name="Bourgois",
            nationality="BE",
            sex="M",
            date_of_birth=date(1960, 8, 15),
            document_number="595524357867",
            document_type="osobna iskaznica",
        )
        payload = build_check_in_payload(guest)
        self.assertEqual(payload["Citizenship"], "BEL")
        self.assertEqual(payload["DocumentType"], "027")

    @override_settings(EVISITOR_FACILITY_CODE="0000022")
    def test_build_check_in_payload_maps_core_fields(self):
        reservation = Reservation.objects.create(
            external_id="map-1",
            check_in_date=date(2026, 6, 1),
            check_out_date=date(2026, 6, 5),
        )
        guest = Guest.objects.create(
            reservation=reservation,
            first_name="Ivan",
            last_name="Horvat",
            nationality="HR",
            sex="M",
            date_of_birth=date(1985, 3, 15),
            document_number="ABC123",
            document_type="putovnica",
        )
        payload = build_check_in_payload(guest)
        self.assertEqual(payload["TouristName"], "Ivan")
        self.assertEqual(payload["Citizenship"], "HRV")
        self.assertEqual(payload["Facility"], "0000022")
        self.assertEqual(payload["DocumentType"], "008")


class EvisitorSummaryTests(TestCase):
    def test_summary_complete_when_all_sent(self):
        reservation = Reservation.objects.create(
            external_id="sum-1",
            check_in_date=date(2026, 6, 1),
            check_out_date=date(2026, 6, 3),
        )
        Guest.objects.create(
            reservation=reservation,
            first_name="A",
            last_name="B",
            evisitor_status=EvisitorGuestStatus.SENT,
        )
        self.assertEqual(evisitor_summary_for_reservation(reservation), "complete")

    def test_summary_incomplete_when_guest_not_sent(self):
        reservation = Reservation.objects.create(
            external_id="sum-2",
            check_in_date=date(2026, 6, 1),
            check_out_date=date(2026, 6, 3),
        )
        Guest.objects.create(
            reservation=reservation,
            first_name="A",
            last_name="B",
            evisitor_status=EvisitorGuestStatus.NOT_SENT,
        )
        self.assertEqual(evisitor_summary_for_reservation(reservation), "incomplete")

    def test_summary_checked_out_when_all_checked_out(self):
        reservation = Reservation.objects.create(
            external_id="sum-3",
            check_in_date=date(2026, 6, 1),
            check_out_date=date(2026, 6, 3),
        )
        Guest.objects.create(
            reservation=reservation,
            first_name="A",
            last_name="B",
            evisitor_status=EvisitorGuestStatus.CHECKED_OUT,
        )
        self.assertEqual(evisitor_summary_for_reservation(reservation), "checked_out")


class DocumentScanIngestViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("doc_scan_ingest", password="test-pass-123")
        self.client = APIClient()
        self.client.force_login(self.user)
        self.rt = RoomType.objects.create(code="SCAN", name_i18n={"en": "Scan Room"})
        self.room = Room.objects.create(code="S1", room_type=self.rt)
        self.reservation = Reservation.objects.create(
            external_id="scan-ingest-1",
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 3),
            status=ReservationStatus.EXPECTED,
        )
        ReservationUnit.objects.create(
            reservation=self.reservation,
            sort_order=0,
            room_name="Scan Room",
            room_type=self.rt,
            room=self.room,
        )
        self.guest = Guest.objects.create(
            reservation=self.reservation,
            first_name="Prije",
            last_name="Skena",
            is_primary=True,
            mrz_verified=False,
        )

    def _scan_url(self):
        return (
            f"/api/reception/reservations/{self.reservation.id}/"
            f"guests/{self.guest.id}/document-scan/"
        )

    def _minimal_payload(self, method: str):
        return {
            "metapodaci": {
                "metoda_ocitanja": method,
                "uredaj_id": "test-device",
            },
            "podaci_gosta": {
                "ime": "Ante",
                "prezime": "Testic",
                "broj_dokumenta": "119384087",
            },
            "sirovi_mrz": "IOHRV119384087911528564544<<<<\n7604234M3005121HRV<<<<<<<<<<<9",
        }

    def test_ocr_scan_sets_mrz_verified(self):
        response = self.client.post(self._scan_url(), self._minimal_payload("OCR"), format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("scan_status"), DocumentScanStatus.OK)
        self.guest.refresh_from_db()
        self.assertTrue(self.guest.mrz_verified)
        self.assertIn("IOHRV", self.guest.mrz_raw_text)

    def test_nfc_scan_sets_mrz_verified(self):
        response = self.client.post(self._scan_url(), self._minimal_payload("NFC"), format="json")
        self.assertEqual(response.status_code, 200)
        self.guest.refresh_from_db()
        self.assertTrue(self.guest.mrz_verified)

    def test_patch_guest_mrz_verified_only(self):
        url = (
            f"/api/reception/reservations/{self.reservation.id}/"
            f"guests/{self.guest.id}/"
        )
        response = self.client.patch(url, {"mrz_verified": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["mrz_verified"])
        self.guest.refresh_from_db()
        self.assertTrue(self.guest.mrz_verified)

    def _face_jpeg_b64(self) -> str:
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (8, 8), (200, 100, 50)).save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def _face_photo_url(self):
        return reverse(
            "api-reception-guest-face-photo",
            kwargs={
                "reservation_id": self.reservation.id,
                "guest_id": self.guest.id,
            },
        )

    def test_nfc_scan_with_face_photo_stores_id_document(self):
        payload = self._minimal_payload("NFC")
        payload["biometrija"] = {"fotografija_b64": self._face_jpeg_b64()}
        response = self.client.post(self._scan_url(), payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("scan_status"), DocumentScanStatus.OK)
        doc = IDDocument.objects.filter(guest=self.guest).first()
        self.assertIsNotNone(doc)
        self.assertTrue(doc.face_photo)

    def test_get_face_photo_returns_jpeg_bytes(self):
        payload = self._minimal_payload("NFC")
        payload["biometrija"] = {"fotografija_b64": self._face_jpeg_b64()}
        self.client.post(self._scan_url(), payload, format="json")
        response = self.client.get(self._face_photo_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("image/jpeg", response["Content-Type"])
        body = b"".join(response.streaming_content)
        self.assertGreater(len(body), 0)

    def test_get_face_photo_404_when_missing(self):
        response = self.client.get(self._face_photo_url())
        self.assertEqual(response.status_code, 404)

    def test_guest_detail_includes_face_photo_url(self):
        payload = self._minimal_payload("NFC")
        payload["biometrija"] = {"fotografija_b64": self._face_jpeg_b64()}
        self.client.post(self._scan_url(), payload, format="json")
        guest_url = (
            f"/api/reception/reservations/{self.reservation.id}/"
            f"guests/{self.guest.id}/"
        )
        response = self.client.get(guest_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("/face-photo/", response.data["face_photo_url"])

    def test_reservation_detail_includes_guest_face_photo_url(self):
        payload = self._minimal_payload("NFC")
        payload["biometrija"] = {"fotografija_b64": self._face_jpeg_b64()}
        self.client.post(self._scan_url(), payload, format="json")
        reservation_url = f"/api/reception/reservations/{self.reservation.id}/"
        response = self.client.get(reservation_url)
        self.assertEqual(response.status_code, 200)
        guests = response.data.get("guests") or []
        self.assertEqual(len(guests), 1)
        self.assertIn("/face-photo/", guests[0]["face_photo_url"])

    def test_e2e_nfc_send_face_photo_visible_on_reservation_and_guest_detail(self):
        """NFC Pošalji → spremljen portret → vidljiv na detalju gosta i rezervacije."""
        payload = self._minimal_payload("NFC")
        payload["biometrija"] = {"fotografija_b64": self._face_jpeg_b64()}
        scan = self.client.post(self._scan_url(), payload, format="json")
        self.assertEqual(scan.status_code, 200)
        self.assertEqual(scan.data.get("scan_status"), DocumentScanStatus.OK)

        guest_url = (
            f"/api/reception/reservations/{self.reservation.id}/"
            f"guests/{self.guest.id}/"
        )
        guest_resp = self.client.get(guest_url)
        self.assertEqual(guest_resp.status_code, 200)
        face_url = guest_resp.data["face_photo_url"]
        self.assertIn("/face-photo/", face_url)

        photo_resp = self.client.get(self._face_photo_url())
        self.assertEqual(photo_resp.status_code, 200)
        self.assertIn("image/jpeg", photo_resp["Content-Type"])
        photo_bytes = b"".join(photo_resp.streaming_content)
        self.assertGreater(len(photo_bytes), 0)

        reservation_resp = self.client.get(
            f"/api/reception/reservations/{self.reservation.id}/"
        )
        self.assertEqual(reservation_resp.status_code, 200)
        guests = reservation_resp.data.get("guests") or []
        self.assertEqual(len(guests), 1)
        self.assertEqual(guests[0]["face_photo_url"], face_url)

        self.guest.refresh_from_db()
        self.assertTrue(self.guest.mrz_verified)
        doc = IDDocument.objects.filter(guest=self.guest).first()
        self.assertIsNotNone(doc)
        self.assertTrue(doc.face_photo)


class DocumentPhotosUploadViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("doc_photos_upload", password="test-pass-123")
        self.client = APIClient()
        self.client.force_login(self.user)
        self.rt = RoomType.objects.create(code="PHOTO", name_i18n={"en": "Photo Room"})
        self.room = Room.objects.create(code="P1", room_type=self.rt)
        self.reservation = Reservation.objects.create(
            external_id="doc-photos-1",
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 3),
            status=ReservationStatus.EXPECTED,
        )
        ReservationUnit.objects.create(
            reservation=self.reservation,
            sort_order=0,
            room_name="Photo Room",
            room_type=self.rt,
            room=self.room,
        )
        self.guest = Guest.objects.create(
            reservation=self.reservation,
            first_name="Foto",
            last_name="Gost",
            is_primary=True,
        )

    @staticmethod
    def _jpeg(name: str = "front.jpg") -> SimpleUploadedFile:
        return SimpleUploadedFile(name, b"\xff\xd8\xff\xe0\x00\x10JFIF", content_type="image/jpeg")

    def _url(self, reservation_id=None, guest_id=None):
        return (
            f"/api/reception/reservations/{reservation_id or self.reservation.id}/"
            f"guests/{guest_id if guest_id is not None else self.guest.id}/document-photos/"
        )

    @staticmethod
    def _basename(storage_name: str) -> str:
        return storage_name.rsplit("/", 1)[-1]

    def test_document_photos_passport_single_front(self):
        response = self.client.post(
            self._url(),
            {
                "document_type": "passport",
                "front": self._jpeg("passport_front.jpg"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["front_saved"])
        self.assertFalse(response.data["back_saved"])
        self.assertEqual(response.data["document_type"], "passport")

        doc = IDDocument.objects.get(pk=response.data["id_document_id"])
        self.assertTrue(doc.front_photo)
        self.assertFalse(doc.back_photo)
        self.assertIn("id_documents/passports/", doc.front_photo.name)
        self.assertNotIn("/front/", doc.front_photo.name)
        self.assertNotIn("/back/", doc.front_photo.name)
        front_base = self._basename(doc.front_photo.name)
        self.assertRegex(front_base, rf"^\d{{10}}_{self.guest.id}_pass\.jpg$")

        self.guest.refresh_from_db()
        self.assertEqual(self.guest.document_type, "Putovnica")

    def test_document_photos_national_id_requires_back(self):
        response = self.client.post(
            self._url(),
            {
                "document_type": "national_id",
                "front": self._jpeg("id_front.jpg"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("back", response.data)

    def test_document_photos_national_id_front_and_back(self):
        response = self.client.post(
            self._url(),
            {
                "document_type": "national_id",
                "front": self._jpeg("id_front.jpg"),
                "back": self._jpeg("id_back.jpg"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["front_saved"])
        self.assertTrue(response.data["back_saved"])

        doc = IDDocument.objects.get(pk=response.data["id_document_id"])
        self.assertTrue(doc.front_photo)
        self.assertTrue(doc.back_photo)
        self.assertIn("id_documents/", doc.front_photo.name)
        self.assertIn("id_documents/", doc.back_photo.name)
        self.assertNotIn("passports/", doc.front_photo.name)
        self.assertNotIn("passports/", doc.back_photo.name)
        self.assertNotIn("/front/", doc.front_photo.name)
        self.assertNotIn("/back/", doc.back_photo.name)
        front_base = self._basename(doc.front_photo.name)
        back_base = self._basename(doc.back_photo.name)
        self.assertRegex(front_base, rf"^\d{{10}}_{self.guest.id}_frontID\.jpg$")
        self.assertRegex(back_base, rf"^\d{{10}}_{self.guest.id}_backID\.jpg$")

        self.guest.refresh_from_db()
        self.assertEqual(self.guest.document_type, "Osobna iskaznica")

    def test_document_photos_guest_not_found(self):
        response = self.client.post(
            self._url(guest_id=99999),
            {
                "document_type": "passport",
                "front": self._jpeg(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)


class ReservationGuestCreateApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("guest_create_api", password="test-pass-123")
        self.client = APIClient()
        self.client.force_login(self.user)
        self.reservation = Reservation.objects.create(
            external_id="guest-create-1",
            check_in_date=date(2026, 5, 17),
            check_out_date=date(2026, 5, 18),
            status=ReservationStatus.EXPECTED,
        )

    def _url(self, reservation_id: int | None = None) -> str:
        rid = reservation_id if reservation_id is not None else self.reservation.id
        return f"/api/reception/reservations/{rid}/guests/"

    def test_create_first_guest_is_primary(self):
        response = self.client.post(
            self._url(),
            {"first_name": "Ana", "last_name": "Test"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_primary"])
        guest = Guest.objects.get(pk=response.data["id"])
        self.assertEqual(guest.first_name, "Ana")

    def test_create_second_guest_not_primary(self):
        Guest.objects.create(
            reservation=self.reservation,
            first_name="Prvi",
            last_name="Gost",
            is_primary=True,
        )
        response = self.client.post(
            self._url(),
            {"first_name": "Drugi", "last_name": "Gost"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["is_primary"])

    def test_create_unknown_reservation_404(self):
        response = self.client.post(
            self._url(reservation_id=999999),
            {"first_name": "X", "last_name": "Y"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_create_empty_names_uses_placeholders_for_mrz_flow(self):
        response = self.client.post(self._url(), {}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["first_name"], "Novi")
        self.assertEqual(response.data["last_name"], "gost")

    def test_create_blank_names_uses_placeholders(self):
        response = self.client.post(
            self._url(),
            {"first_name": "  ", "last_name": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["first_name"], "Novi")
        self.assertEqual(response.data["last_name"], "gost")


class RoomCalendarViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("room_calendar_api", password="test-pass-123")
        self.client = APIClient()
        self.client.force_login(self.user)
        self.rt = RoomType.objects.create(code="RCAL", name_i18n={"en": "Cal Room"})
        self.room = Room.objects.create(code="RC1", room_type=self.rt)
        self.reservation_canceled = Reservation.objects.create(
            external_id="cal-canceled-1",
            check_in_date=date(2026, 3, 10),
            check_out_date=date(2026, 3, 12),
            status=ReservationStatus.CANCELED,
        )
        ReservationUnit.objects.create(
            reservation=self.reservation_canceled,
            sort_order=0,
            room_name="Cal Room",
            room_type=self.rt,
            room=self.room,
        )
        self.reservation_active = Reservation.objects.create(
            external_id="cal-active-1",
            check_in_date=date(2026, 3, 15),
            check_out_date=date(2026, 3, 17),
            status=ReservationStatus.EXPECTED,
        )
        ReservationUnit.objects.create(
            reservation=self.reservation_active,
            sort_order=0,
            room_name="Cal Room",
            room_type=self.rt,
            room=self.room,
        )

    def _calendar_url(self, include_canceled: bool = False):
        base = f"/api/rooms/rooms/{self.room.id}/calendar/?from=2026-03-01&to=2026-04-01&lang=hr"
        if include_canceled:
            return f"{base}&include_canceled=1"
        return base

    def test_excludes_canceled_by_default(self):
        response = self.client.get(self._calendar_url())
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data}
        self.assertIn(self.reservation_active.id, ids)
        self.assertNotIn(self.reservation_canceled.id, ids)

    def test_includes_canceled_when_requested(self):
        response = self.client.get(self._calendar_url(include_canceled=True))
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data}
        self.assertIn(self.reservation_active.id, ids)
        self.assertIn(self.reservation_canceled.id, ids)


class ReceptionMonthlyStatisticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("stats_user", password="test-pass-123")
        self.client = APIClient()
        self.client.force_login(self.user)

    def _create(
        self,
        external_id: str,
        check_in: date,
        check_out: date,
        *,
        status: str = ReservationStatus.CHECKED_IN,
        total_amount: Decimal | None = None,
        commission_amount: Decimal | None = None,
        nights_count: int | None = None,
    ) -> Reservation:
        return Reservation.objects.create(
            external_id=external_id,
            check_in_date=check_in,
            check_out_date=check_out,
            status=status,
            total_amount=total_amount,
            commission_amount=commission_amount,
            nights_count=nights_count,
        )

    def test_aggregate_includes_checked_in_and_out_excludes_expected_canceled(self):
        self._create(
            "stats-in-1",
            date(2026, 3, 10),
            date(2026, 3, 12),
            status=ReservationStatus.CHECKED_IN,
            total_amount=Decimal("100.00"),
            commission_amount=Decimal("15.00"),
            nights_count=2,
        )
        self._create(
            "stats-out-1",
            date(2026, 3, 20),
            date(2026, 3, 22),
            status=ReservationStatus.CHECKED_OUT,
            total_amount=Decimal("200.00"),
            commission_amount=Decimal("20.00"),
            nights_count=2,
        )
        self._create(
            "stats-prev-1",
            date(2025, 3, 15),
            date(2025, 3, 17),
            status=ReservationStatus.CHECKED_OUT,
            total_amount=Decimal("50.00"),
            commission_amount=Decimal("5.00"),
            nights_count=2,
        )
        self._create(
            "stats-expected",
            date(2026, 3, 5),
            date(2026, 3, 7),
            status=ReservationStatus.EXPECTED,
            total_amount=Decimal("999.00"),
        )
        self._create(
            "stats-canceled",
            date(2026, 3, 6),
            date(2026, 3, 8),
            status=ReservationStatus.CANCELED,
            total_amount=Decimal("888.00"),
        )

        data = aggregate_monthly_statistics(2026)
        march_current = data["months"][2]["current"]
        march_previous = data["months"][2]["previous"]

        self.assertEqual(march_current["revenue"], "300.00")
        self.assertEqual(march_current["commission"], "35.00")
        self.assertEqual(march_current["nights"], 4)
        self.assertEqual(march_previous["revenue"], "50.00")
        self.assertEqual(march_previous["commission"], "5.00")
        self.assertEqual(march_previous["nights"], 2)

    def test_nights_fallback_from_dates_when_count_missing(self):
        self._create(
            "stats-nights-fallback",
            date(2026, 4, 1),
            date(2026, 4, 4),
            status=ReservationStatus.CHECKED_IN,
            total_amount=Decimal("10.00"),
            nights_count=None,
        )
        data = aggregate_monthly_statistics(2026)
        april = data["months"][3]["current"]
        self.assertEqual(april["nights"], 3)

    def test_api_endpoint_returns_monthly_payload(self):
        self._create(
            "stats-api-1",
            date(2026, 5, 1),
            date(2026, 5, 2),
            status=ReservationStatus.CHECKED_IN,
            total_amount=Decimal("75.50"),
            commission_amount=Decimal("7.50"),
            nights_count=1,
        )
        resp = self.client.get("/api/reception/statistics/monthly/", {"year": "2026"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["year"], 2026)
        self.assertEqual(resp.data["comparison_year"], 2025)
        may = resp.data["months"][4]["current"]
        self.assertEqual(may["revenue"], "75.50")
        self.assertEqual(may["commission"], "7.50")
        self.assertEqual(may["nights"], 1)
