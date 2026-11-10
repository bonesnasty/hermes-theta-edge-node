from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from theta_core import installer


class InstallerTests(unittest.TestCase):
    def test_find_exe_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / installer.EXE_NAME
            exe.write_bytes(b"stub")
            self.assertEqual(installer.find_exe(str(exe)), exe)

    def test_find_exe_searches_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / installer.EXE_NAME
            exe.write_bytes(b"stub")
            with patch.object(installer, "_candidate_paths", return_value=[exe]), patch.object(
                installer, "_registry_paths", return_value=[]
            ):
                self.assertEqual(installer.find_exe(""), exe)

    def test_find_exe_returns_none(self):
        with patch.object(installer, "_candidate_paths", return_value=[]), patch.object(
            installer, "_registry_paths", return_value=[]
        ):
            self.assertIsNone(installer.find_exe(""))

    def test_verify_host(self):
        self.assertTrue(installer.verify_host("https://theta-mkt-api.thetatoken.org/x"))
        self.assertTrue(installer.verify_host("https://s3.us-east-2.amazonaws.com/x"))
        self.assertFalse(installer.verify_host("http://theta-mkt-api.thetatoken.org/x"))
        self.assertFalse(installer.verify_host("https://evil.example.com/x"))

    def test_authenticode_parses_json(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"THETA_PLUGIN_DATA_DIR": tmp}
        ), patch.object(
            installer.subprocess,
            "run",
            return_value=SimpleNamespace(
                stdout='{"Status":"Valid","Subject":"CN=Theta Labs, Inc.","Thumbprint":"ABC"}',
                stderr="",
                returncode=0,
            ),
        ):
            info = installer.authenticode(Path(tmp) / "setup.exe")
        self.assertEqual(info["status"], "Valid")
        self.assertIn("Theta Labs", info["subject"])

    def test_authenticode_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"THETA_PLUGIN_DATA_DIR": tmp}
        ), patch.object(installer.subprocess, "run", side_effect=OSError("no powershell")):
            info = installer.authenticode(Path(tmp) / "setup.exe")
        self.assertEqual(info["status"], "Unavailable")

    def test_node_process_running_failure(self):
        with patch.object(installer.subprocess, "run", side_effect=OSError("no tasklist")):
            self.assertFalse(installer.node_process_running())

    def test_read_logs(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"THETA_LOGS_DIR": tmp}):
            Path(tmp, "node.log").write_text("one\ntwo\nthree\n", encoding="utf-8")
            result = installer.read_logs(lines=2)
        self.assertTrue(result["path"].endswith("node.log"))
        self.assertEqual(result["lines"], ["two", "three"])

    def test_progress_starts_idle(self):
        self.assertIn("phase", installer.progress())


if __name__ == "__main__":
    unittest.main()
