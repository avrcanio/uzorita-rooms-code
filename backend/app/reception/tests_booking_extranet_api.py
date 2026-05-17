import importlib.util
import json
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from reception.booking_extranet.outcomes import ConnectOutcome, ConnectResult, NEEDS_HUMAN_MESSAGE
from reception.booking_extranet.connection_service import import_storage_state
from reception.models import BookingExtranetConnection, BookingExtranetStatus

User = get_user_model()

_SAMPLE_STATE = {
    "cookies": [{"name": "s", "value": "v", "domain": ".booking.com", "path": "/"}],
    "origins": [],
}


@override_settings(
    BOOKING_EXTRANET_ENABLED=True,
    BOOKING_EXTRANET_CONNECT_MODE="human_assisted",
    BOOKING_EXTRANET_USERNAME="user",
    BOOKING_EXTRANET_PASSWORD="pass",
    BOOKING_EXTRANET_LOGIN_URL="https://account.booking.com/sign-in",
)
class BookingExtranetApiTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._fernet_key = Fernet.generate_key().decode()
        self.settings_override = override_settings(
            BOOKING_EXTRANET_STORAGE_DIR=self._tmpdir.name,
            BOOKING_EXTRANET_FERNET_KEY=self._fernet_key,
        )
        self.settings_override.enable()
        self.user = User.objects.create_user(username="recep", password="test-pass-123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        BookingExtranetConnection.get_solo()

    def tearDown(self):
        self.settings_override.disable()
        self._tmpdir.cleanup()

    def test_get_connection(self):
        response = self.client.get("/api/reception/booking-extranet/connection/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "disconnected")
        self.assertEqual(data["connect_mode"], "human_assisted")
        self.assertFalse(data["auto_connect_allowed"])
        self.assertIn("vnc_active", data)
        self.assertIn("vnc_url", data)

    def test_start_connect_rejected_in_human_assisted_mode(self):
        response = self.client.post("/api/reception/booking-extranet/connection/start/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("human_assisted", response.json()["detail"])

    @override_settings(BOOKING_EXTRANET_CONNECT_MODE="automatic")
    @patch("reception.booking_extranet.views.booking_extranet_start_connect_task")
    def test_start_connect_enqueues_task_when_automatic(self, mock_task):
        mock_task.delay.return_value.id = "task-abc"
        response = self.client.post("/api/reception/booking-extranet/connection/start/")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["task_id"], "task-abc")
        mock_task.delay.assert_called_once()

    def test_import_state_json(self):
        response = self.client.post(
            "/api/reception/booking-extranet/connection/import-state/",
            data={"storage_state": _SAMPLE_STATE},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "connected")
        conn = BookingExtranetConnection.get_solo()
        self.assertEqual(conn.status, BookingExtranetStatus.CONNECTED)

    def test_disconnect(self):
        import_storage_state(_SAMPLE_STATE)
        response = self.client.post("/api/reception/booking-extranet/connection/disconnect/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "disconnected")

    @override_settings(BOOKING_EXTRANET_VNC_ENABLED=True)
    def test_vnc_auth_requires_login(self):
        anon = APIClient()
        response = anon.get("/api/reception/booking-extranet/vnc/auth/")
        self.assertEqual(response.status_code, 401)

    @override_settings(BOOKING_EXTRANET_VNC_ENABLED=True)
    @patch("reception.booking_extranet.vnc._redis_client")
    def test_vnc_auth_allows_valid_token_without_session(self, mock_redis_factory):
        from reception.booking_extranet.vnc import issue_vnc_token

        mock_client = mock_redis_factory.return_value
        store: dict[str, str] = {}
        mock_client.setex.side_effect = lambda key, _ttl, value: store.__setitem__(key, value)
        mock_client.get.side_effect = lambda key: store.get(key)
        mock_client.delete.side_effect = lambda key: store.pop(key, None)

        token = issue_vnc_token(user_id=self.user.id)
        anon = APIClient()
        response = anon.get(f"/api/reception/booking-extranet/vnc/auth/?token={token}")
        self.assertEqual(response.status_code, 200)

    @override_settings(BOOKING_EXTRANET_VNC_ENABLED=True)
    @patch("reception.booking_extranet.vnc._redis_client")
    def test_vnc_auth_allows_authenticated_session_with_token(self, mock_redis_factory):
        from reception.booking_extranet.vnc import issue_vnc_token

        mock_client = mock_redis_factory.return_value
        store: dict[str, str] = {}
        mock_client.setex.side_effect = lambda key, _ttl, value: store.__setitem__(key, value)
        mock_client.get.side_effect = lambda key: store.get(key)
        mock_client.delete.side_effect = lambda key: store.pop(key, None)

        token = issue_vnc_token(user_id=self.user.id)
        response = self.client.get(
            f"/api/reception/booking-extranet/vnc/auth/?token={token}",
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(BOOKING_EXTRANET_VNC_ENABLED=True)
    def test_vnc_auth_rejects_missing_token(self):
        response = self.client.get("/api/reception/booking-extranet/vnc/auth/")
        self.assertEqual(response.status_code, 401)

    @override_settings(BOOKING_EXTRANET_VNC_ENABLED=False)
    def test_vnc_auth_disabled_returns_503(self):
        response = self.client.get("/api/reception/booking-extranet/vnc/auth/")
        self.assertEqual(response.status_code, 503)

    @override_settings(BOOKING_EXTRANET_VNC_ENABLED=True, BOOKING_EXTRANET_HEADED=True)
    @patch("reception.booking_extranet.tasks.booking_extranet_vnc_continue_task")
    def test_vnc_continue_dispatches_to_celery_worker(self, mock_task):
        mock_result = mock_task.delay.return_value
        mock_result.get.return_value = {
            "connection": {"status": "connected", "hotel_id": "4181954"},
        }
        response = self.client.post("/api/reception/booking-extranet/vnc/continue/")
        self.assertEqual(response.status_code, 200)
        mock_task.delay.assert_called_once_with(user_id=self.user.id)
        mock_result.get.assert_called_once()

    @override_settings(BOOKING_EXTRANET_CONNECT_MODE="automatic")
    def test_auto_connect_rate_limit(self):
        conn = BookingExtranetConnection.get_solo()
        conn.last_connect_at = timezone.now() - timedelta(hours=1)
        conn.save(update_fields=["last_connect_at"])
        response = self.client.post("/api/reception/booking-extranet/connection/start/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("24", response.json()["detail"])


@unittest.skipUnless(importlib.util.find_spec("playwright"), "playwright not installed")
@override_settings(
    BOOKING_EXTRANET_ENABLED=True,
    BOOKING_EXTRANET_USERNAME="user",
    BOOKING_EXTRANET_PASSWORD="pass",
    BOOKING_EXTRANET_LOGIN_URL="https://account.booking.com/sign-in",
)
class BookingExtranetConnectHumanTests(TestCase):
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

    @patch("reception.booking_extranet.connect.selectors")
    @patch("reception.booking_extranet.connect.detect_needs_human", return_value=True)
    def test_run_connect_on_page_needs_human(self, _mock_human, mock_selectors):
        import importlib
        from unittest.mock import MagicMock

        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        except ImportError:
            PlaywrightTimeoutError = Exception

        run_connect_on_page = importlib.import_module(
            "reception.booking_extranet.connect"
        ).run_connect_on_page

        page = MagicMock()
        page.url = "https://account.booking.com/challenge"
        page.wait_for_url.side_effect = PlaywrightTimeoutError("timeout")
        mock_selectors.username_input.return_value = MagicMock()
        mock_selectors.next_button.return_value = MagicMock()
        mock_selectors.password_input.return_value = MagicMock()
        mock_selectors.sign_in_button.return_value = MagicMock()
        mock_selectors.has_password_step_text.return_value = True
        mock_selectors.verification_code_input.return_value = None

        result = run_connect_on_page(page)
        self.assertEqual(result.outcome, ConnectOutcome.NEEDS_HUMAN)

    def test_apply_needs_human_sets_message(self):
        from reception.booking_extranet.connection_service import apply_connect_result

        conn = apply_connect_result(ConnectResult(outcome=ConnectOutcome.NEEDS_HUMAN))
        self.assertEqual(conn.status, BookingExtranetStatus.NEEDS_HUMAN)
        self.assertEqual(conn.last_error, NEEDS_HUMAN_MESSAGE)
