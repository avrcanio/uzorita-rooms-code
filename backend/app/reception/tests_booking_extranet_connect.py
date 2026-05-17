import importlib
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from django.test import TestCase, override_settings

from reception.booking_extranet.outcomes import ConnectOutcome
from reception.booking_extranet.urls import is_connected_url

try:
    importlib.import_module("playwright.sync_api")
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

_SAMPLE_STORAGE = {
    "cookies": [{"name": "s", "value": "v", "domain": ".booking.com", "path": "/"}],
    "origins": [],
}


@override_settings(
    BOOKING_EXTRANET_ENABLED=True,
    BOOKING_EXTRANET_USERNAME="hospira",
    BOOKING_EXTRANET_PASSWORD="secret",
    BOOKING_EXTRANET_LOGIN_URL="https://account.booking.com/sign-in",
    BOOKING_EXTRANET_SUCCESS_URL_CONTAINS="search_reservations.html",
)
class BookingExtranetUrlTests(TestCase):
    def test_is_connected_url(self):
        url = (
            "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/"
            "search_reservations.html?hotel_id=4181954"
        )
        self.assertTrue(is_connected_url(url))

    def test_is_connected_url_home_dashboard(self):
        url = (
            "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/"
            "home.html?hotel_id=4181954"
        )
        self.assertTrue(is_connected_url(url))


@unittest.skipUnless(HAS_PLAYWRIGHT, "playwright not installed")
@override_settings(
    BOOKING_EXTRANET_ENABLED=True,
    BOOKING_EXTRANET_USERNAME="hospira",
    BOOKING_EXTRANET_PASSWORD="secret",
    BOOKING_EXTRANET_LOGIN_URL="https://account.booking.com/sign-in",
    BOOKING_EXTRANET_SUCCESS_URL_CONTAINS="search_reservations.html",
)
class BookingExtranetConnectFlowTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._fernet_key = Fernet.generate_key().decode()
        self.settings_override = override_settings(
            BOOKING_EXTRANET_STORAGE_DIR=self._tmpdir.name,
            BOOKING_EXTRANET_FERNET_KEY=self._fernet_key,
        )
        self.settings_override.enable()
        self.connect = importlib.import_module("reception.booking_extranet.connect")
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        except ImportError:
            PlaywrightTimeoutError = Exception
        self.PlaywrightTimeoutError = PlaywrightTimeoutError

    def tearDown(self):
        self.settings_override.disable()
        self._tmpdir.cleanup()

    @patch("reception.booking_extranet.connect.save_storage_state")
    @patch("reception.booking_extranet.connect.selectors")
    def test_run_connect_on_page_connected(self, mock_selectors, mock_save):
        page = MagicMock()
        page.url = (
            "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/"
            "search_reservations.html"
        )
        page.context.storage_state.return_value = _SAMPLE_STORAGE

        mock_selectors.username_input.return_value = MagicMock()
        mock_selectors.next_button.return_value = MagicMock()
        mock_selectors.password_input.return_value = MagicMock()
        mock_selectors.sign_in_button.return_value = MagicMock()
        mock_selectors.has_password_step_text.return_value = True
        mock_selectors.verification_code_input.return_value = None

        result = self.connect.run_connect_on_page(page)

        self.assertEqual(result.outcome, ConnectOutcome.CONNECTED)
        page.goto.assert_called_once()
        mock_save.assert_called_once_with(_SAMPLE_STORAGE, relative_path="state.enc")

    @patch("reception.booking_extranet.connect.detect_needs_human", return_value=False)
    @patch("reception.booking_extranet.connect.selectors")
    def test_run_connect_on_page_needs_2fa(self, mock_selectors, _mock_human):
        page = MagicMock()
        page.url = "https://account.booking.com/sign-in/verify"
        page.wait_for_url.side_effect = self.PlaywrightTimeoutError("timeout")

        mock_selectors.username_input.return_value = MagicMock()
        mock_selectors.next_button.return_value = MagicMock()
        mock_selectors.password_input.return_value = MagicMock()
        mock_selectors.sign_in_button.return_value = MagicMock()
        mock_selectors.has_password_step_text.return_value = True
        mock_selectors.verification_code_input.return_value = MagicMock()

        result = self.connect.run_connect_on_page(page)

        self.assertEqual(result.outcome, ConnectOutcome.NEEDS_2FA)
        self.assertIsNone(result.storage_relative_path)
        page.context.storage_state.assert_not_called()

    @patch("reception.booking_extranet.connect.selectors")
    def test_detect_needs_human_recaptcha_iframe(self, mock_selectors):
        page = MagicMock()
        locator = MagicMock()
        locator.first.is_visible.return_value = True
        page.locator.return_value = locator
        self.assertTrue(self.connect.detect_needs_human(page))

    @override_settings(BOOKING_EXTRANET_USERNAME="")
    def test_missing_username_raises(self):
        page = MagicMock()
        from reception.booking_extranet.errors import BookingExtranetConnectError

        with self.assertRaises(BookingExtranetConnectError):
            self.connect.run_connect_on_page(page)
