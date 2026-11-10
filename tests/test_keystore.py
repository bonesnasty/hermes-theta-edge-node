from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from theta_core import keystore

PK = bytes.fromhex("00" * 31 + "01")
ADDR = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"
PASSWORD = "testpassword"


class KeystoreTests(unittest.TestCase):
    def test_private_key_one_has_known_address(self):
        self.assertEqual(keystore.private_key_to_address(PK), ADDR)

    def test_encrypt_decrypt_roundtrip(self):
        blob = keystore.encrypt_keystore(PK, PASSWORD, n=2**14)
        self.assertEqual(blob["address"], ADDR[2:])
        self.assertEqual(keystore.decrypt_keystore(blob, PASSWORD), PK)

    def test_wrong_password_is_rejected(self):
        blob = keystore.encrypt_keystore(PK, PASSWORD, n=2**14)
        with self.assertRaises(keystore.KeystoreError):
            keystore.decrypt_keystore(blob, "wrong-password")

    def test_tampered_ciphertext_is_rejected(self):
        blob = keystore.encrypt_keystore(PK, PASSWORD, n=2**14)
        raw = bytearray(bytes.fromhex(blob["crypto"]["ciphertext"]))
        raw[0] ^= 0xFF
        blob["crypto"]["ciphertext"] = bytes(raw).hex()
        with self.assertRaises(keystore.KeystoreError):
            keystore.decrypt_keystore(blob, PASSWORD)

    def test_keystore_address_from_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wallet.json"
            path.write_text(json.dumps(keystore.encrypt_keystore(PK, PASSWORD, n=2**14)))
            self.assertEqual(keystore.keystore_address(path), ADDR)

    def test_latest_keystore_picks_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.json"
            second = Path(tmp) / "second.json"
            first.write_text(json.dumps(keystore.encrypt_keystore(PK, PASSWORD, n=2**14)))
            second.write_text(json.dumps(keystore.encrypt_keystore(PK, PASSWORD, n=2**14)))
            os.utime(first, (1000, 1000))
            os.utime(second, (2000, 2000))
            with patch.dict(os.environ, {"THETA_KEYSTORE_DIR": tmp}):
                self.assertEqual(keystore.latest_keystore(), second)

    def test_scan_downloads_finds_keystore(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "theta-keystore"
            path.write_text(json.dumps(keystore.encrypt_keystore(PK, PASSWORD, n=2**14)))
            with patch.dict(os.environ, {"THETA_DOWNLOADS_DIR": tmp}):
                found = keystore.scan_downloads()
            self.assertIsNotNone(found)
            self.assertEqual(found["address"], ADDR)

    def test_scan_downloads_ignores_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "notes.txt").write_text("not a keystore")
            with patch.dict(os.environ, {"THETA_DOWNLOADS_DIR": tmp}):
                self.assertIsNone(keystore.scan_downloads())


if __name__ == "__main__":
    unittest.main()
