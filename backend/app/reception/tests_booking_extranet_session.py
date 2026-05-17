import tempfile
from pathlib import Path

from cryptography.fernet import Fernet
from django.test import TestCase, override_settings

from reception.booking_extranet.session_store import (
    BookingExtranetSessionError,
    clear_storage_state,
    has_storage_state,
    load_storage_state,
    save_storage_state,
    validate_storage_state,
)

_SAMPLE_STATE = {
    "cookies": [
        {
            "name": "session",
            "value": "fake-value-not-logged",
            "domain": ".booking.com",
            "path": "/",
        }
    ],
    "origins": [],
}


class BookingExtranetSessionStoreTests(TestCase):
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

    def test_roundtrip_encrypt_decrypt(self):
        save_storage_state(_SAMPLE_STATE)
        loaded = load_storage_state()
        self.assertEqual(loaded, _SAMPLE_STATE)
        self.assertTrue(has_storage_state())

        raw = (Path(self._tmpdir.name) / "state.enc").read_bytes()
        self.assertNotIn(b"fake-value-not-logged", raw)

    def test_load_missing_returns_none(self):
        self.assertIsNone(load_storage_state())
        self.assertFalse(has_storage_state())

    def test_clear_removes_file(self):
        save_storage_state(_SAMPLE_STATE)
        clear_storage_state()
        self.assertIsNone(load_storage_state())
        self.assertFalse(has_storage_state())

    def test_wrong_key_raises(self):
        save_storage_state(_SAMPLE_STATE)
        with override_settings(BOOKING_EXTRANET_FERNET_KEY=Fernet.generate_key().decode()):
            with self.assertRaises(BookingExtranetSessionError):
                load_storage_state()

    def test_validate_rejects_invalid_shape(self):
        with self.assertRaises(BookingExtranetSessionError):
            validate_storage_state([])
        with self.assertRaises(BookingExtranetSessionError):
            validate_storage_state({"unexpected": True})

    def test_rejects_path_traversal(self):
        with self.assertRaises(BookingExtranetSessionError):
            save_storage_state(_SAMPLE_STATE, relative_path="../escape.enc")
