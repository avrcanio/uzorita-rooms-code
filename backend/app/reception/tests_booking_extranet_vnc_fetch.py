import tempfile
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from reception.booking_extranet.browser_session import detect_needs_human
from reception.booking_extranet.fetch_reservation import FetchOutcome, FetchResult, resolve_target_url
from reception.booking_extranet.session_store import load_storage_state, save_storage_state
from reception.booking_extranet.url_extract import extract_booking_url_from_text, extract_res_id_from_url
from reception.booking_extranet.vnc import issue_vnc_token, validate_vnc_token
from reception.models import BookingExtranetConnection, BookingExtranetStatus

User = get_user_model()

_SAMPLE_HTML = """
<a href="https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/booking.html?res_id=5581435138&amp;hotel_id=4181954">View</a>
"""

_STATE_WITH_OPTANON = {
    "cookies": [
        {"name": "session", "value": "ok", "domain": ".booking.com", "path": "/"},
        {"name": "OptanonConsent", "value": "bad", "domain": ".booking.com", "path": "/"},
        {"name": "expires_cookie", "value": "x", "domain": ".booking.com", "path": "/", "expires": "1735689600"},
    ],
    "origins": [],
}


@override_settings(
    BOOKING_EXTRANET_ENABLED=True,
    BOOKING_EXTRANET_HOTEL_ID="4181954",
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class BookingExtranetUrlExtractTests(TestCase):
    def test_extract_booking_url_from_html(self):
        url = extract_booking_url_from_text(_SAMPLE_HTML)
        self.assertIn("booking.html", url or "")
        self.assertEqual(extract_res_id_from_url(url or ""), "5581435138")

    def test_resolve_target_url_from_booking_number(self):
        url = resolve_target_url(booking_number="5581435138")
        self.assertIn("res_id=5581435138", url or "")


class BookingExtranetVncTokenTests(TestCase):
    @patch("reception.booking_extranet.vnc._redis_client")
    def test_issue_and_validate_token(self, mock_redis_factory):
        mock_client = mock_redis_factory.return_value
        store: dict[str, str] = {}

        def setex(key, _ttl, value):
            store[key] = value

        def get(key):
            return store.get(key)

        mock_client.setex.side_effect = setex
        mock_client.get.side_effect = get
        mock_client.delete.side_effect = lambda key: store.pop(key, None)

        user = User.objects.create_user(username="vncuser", password="pass")
        token = issue_vnc_token(user_id=user.id, job_id=42)
        self.assertTrue(validate_vnc_token(token, user_id=user.id))
        self.assertFalse(validate_vnc_token(token, user_id=user.id + 1))


class BookingExtranetSanitizeTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._fernet_key = Fernet.generate_key().decode()
        self.settings_override = override_settings(
            BOOKING_EXTRANET_STORAGE_DIR=self._tmpdir.name,
            BOOKING_EXTRANET_FERNET_KEY=self._fernet_key,
        )
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self._tmpdir.cleanup()

    def test_optanon_consent_stripped_on_save(self):
        save_storage_state(_STATE_WITH_OPTANON)
        loaded = load_storage_state()
        names = {c["name"] for c in loaded["cookies"]}
        self.assertNotIn("OptanonConsent", names)
        self.assertIn("session", names)
        expires_cookie = next(c for c in loaded["cookies"] if c["name"] == "expires_cookie")
        self.assertIsInstance(expires_cookie["expires"], int)


class BookingExtranetDetectHumanTests(TestCase):
    def test_detect_aws_waf_title(self):
        page = MagicMock()
        page.title.return_value = "Human Verification"
        page.url = "https://admin.booking.com/"
        page.locator.return_value.first.wait_for.side_effect = Exception("timeout")
        page.get_by_text.return_value.first.wait_for.side_effect = Exception("timeout")
        self.assertTrue(detect_needs_human(page))


@override_settings(
    BOOKING_EXTRANET_ENABLED=True,
    BOOKING_EXTRANET_VNC_ENABLED=True,
    BOOKING_EXTRANET_FERNET_KEY=Fernet.generate_key().decode(),
    BOOKING_EXTRANET_STORAGE_DIR="/tmp/booking-test-unused",
)
class BookingExtranetFetchApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="fetchuser", password="pass")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        conn = BookingExtranetConnection.get_solo()
        conn.status = BookingExtranetStatus.CONNECTED
        conn.save()

    @patch("reception.booking_extranet.tasks.booking_extranet_fetch_reservation_task")
    def test_fetch_reservation_enqueue(self, mock_task):
        mock_task.delay.return_value.id = "task-fetch-1"
        response = self.client.post(
            "/api/reception/booking-extranet/fetch-reservation/",
            data={"booking_number": "5581435138"},
            format="json",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["task_id"], "task-fetch-1")
        mock_task.delay.assert_called_once()


@override_settings(BOOKING_EXTRANET_VNC_ENABLED=True)
class BookingExtranetFetchTaskStateTests(TestCase):
    @patch("reception.booking_extranet.fetch_reservation.run_fetch_reservation")
    def test_fetch_task_needs_human(self, mock_run):
        from reception.booking_extranet.job_service import create_job
        from reception.booking_extranet.tasks import booking_extranet_fetch_reservation_task
        from reception.models import BookingExtranetJobKind, BookingExtranetJobStatus

        mock_run.return_value = FetchResult(outcome=FetchOutcome.NEEDS_HUMAN)
        job = create_job(
            kind=BookingExtranetJobKind.FETCH_RESERVATION,
            booking_number="5581435138",
            target_url="https://admin.booking.com/.../booking.html?res_id=5581435138",
        )
        with patch(
            "reception.booking_extranet.lock.booking_extranet_connect_lock"
        ) as mock_lock:
            mock_lock.return_value.__enter__.return_value = True
            result = booking_extranet_fetch_reservation_task(job_id=job.id, user_id=1)
        job.refresh_from_db()
        self.assertEqual(job.status, BookingExtranetJobStatus.NEEDS_HUMAN)
        self.assertEqual(result["status"], BookingExtranetJobStatus.NEEDS_HUMAN)
