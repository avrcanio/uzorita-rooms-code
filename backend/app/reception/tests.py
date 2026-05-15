from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mrz.generator.td1 import TD1CodeGenerator
from mrz.generator.td3 import TD3CodeGenerator

from reception.models import DocumentScanLog, DocumentScanStatus, Guest, Reservation, ReservationStatus
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
            room_name="Other",
            room_type=self.rt,
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
            room_name="R1",
            room_type=self.rt,
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
