from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from theta_core import keystore

PK = bytes.fromhex("00" * 31 + "01")
ADDR = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"
PASSWORD = "testpassword"


def load_plugin_api():
    path = ROOT / "dashboard" / "plugin_api.py"
    spec = importlib.util.spec_from_file_location("theta_plugin_api_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.keystore_dir = root / "keystore"
        self.downloads_dir = root / "downloads"
        self.logs_dir = root / "logs"
        for directory in (self.keystore_dir, self.downloads_dir, self.logs_dir):
            directory.mkdir()
        self.env = patch.dict(
            os.environ,
            {
                "THETA_PLUGIN_DATA_DIR": str(root / "data"),
                "THETA_KEYSTORE_DIR": str(self.keystore_dir),
                "THETA_DOWNLOADS_DIR": str(self.downloads_dir),
                "THETA_LOGS_DIR": str(self.logs_dir),
            },
        )
        self.env.start()
        self.api = load_plugin_api()
        self.api._EXPORT_FAILURES.update(count=0, until=0.0)
        app = FastAPI()
        app.include_router(self.api.router, prefix="/api/plugins/theta-edge-node")
        self.client = TestClient(app)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def write_keystore(self, directory: Path, name: str = "node-keystore") -> Path:
        blob = keystore.encrypt_keystore(PK, PASSWORD, n=2**14)
        path = directory / name
        path.write_text(json.dumps(blob), encoding="utf-8")
        return path

    def test_health(self):
        response = self.client.get("/api/plugins/theta-edge-node/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_node_status_offline(self):
        with patch.object(
            self.api.edge_rpc, "node_status", return_value={"running": False, "error": "x"}
        ), patch.object(self.api.installer, "find_exe", return_value=None), patch.object(
            self.api.installer, "node_process_running", return_value=False
        ), patch.object(self.api.keystore, "latest_keystore", return_value=None):
            response = self.client.get("/api/plugins/theta-edge-node/node/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["running"])
        self.assertFalse(body["installed"])

    def test_settings_roundtrip(self):
        response = self.client.post(
            "/api/plugins/theta-edge-node/settings", json={"auto_launch": False}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["auto_launch"])

    def test_wallet_no_keystore(self):
        response = self.client.get("/api/plugins/theta-edge-node/wallet")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["exists"])

    def test_wallet_export_roundtrip(self):
        self.write_keystore(self.keystore_dir)
        wrong = self.client.post(
            "/api/plugins/theta-edge-node/wallet/export", json={"password": "wrong-password"}
        )
        self.assertEqual(wrong.status_code, 400)
        right = self.client.post(
            "/api/plugins/theta-edge-node/wallet/export", json={"password": PASSWORD}
        )
        self.assertEqual(right.status_code, 200)
        self.assertEqual(right.json()["address"], ADDR)
        self.assertEqual(right.json()["private_key"], "0x" + PK.hex())

    def test_export_remote_blocked(self):
        self.write_keystore(self.keystore_dir)
        with patch.object(self.api, "_client_is_local", return_value=False):
            response = self.client.post(
                "/api/plugins/theta-edge-node/wallet/export", json={"password": PASSWORD}
            )
        self.assertEqual(response.status_code, 403)

    def test_verify_export(self):
        self.write_keystore(self.keystore_dir)
        self.write_keystore(self.downloads_dir, name="exported-keystore")
        response = self.client.post("/api/plugins/theta-edge-node/wallet/verify-export")
        body = response.json()
        self.assertTrue(body["found"])
        self.assertTrue(body["matches_node_wallet"])

    def test_wallet_balances(self):
        self.write_keystore(self.keystore_dir)
        with patch.object(
            self.api.chain,
            "wallet_value",
            return_value={"address": ADDR, "tfuel": 1.0, "total_usd": 0.01},
        ):
            response = self.client.get("/api/plugins/theta-edge-node/wallet/balances")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["address"], ADDR)
        self.assertEqual(response.json()["tfuel"], 1.0)

    def test_install_start(self):
        with patch.object(self.api.installer, "download_and_install", return_value=None):
            response = self.client.post("/api/plugins/theta-edge-node/node/install")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["started"])

    def test_node_logs(self):
        Path(self.logs_dir, "node.log").write_text("hello\nworld\n", encoding="utf-8")
        response = self.client.get("/api/plugins/theta-edge-node/node/logs?lines=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lines"], ["world"])


if __name__ == "__main__":
    unittest.main()
