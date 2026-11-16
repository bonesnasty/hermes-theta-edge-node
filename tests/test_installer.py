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

    def test_find_exe_ignores_invalid_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "cmd.exe"
            bad.write_bytes(b"stub")
            with patch.object(installer, "_candidate_paths", return_value=[]), patch.object(
                installer, "_registry_paths", return_value=[]
            ):
                self.assertIsNone(installer.find_exe(str(bad)))

    def test_verify_host(self):
        self.assertTrue(installer.verify_host("https://theta-mkt-api.thetatoken.org/x"))
        self.assertTrue(
            installer.verify_host(
                "https://s3.us-east-2.amazonaws.com/assets.thetatoken.org/apps/Theta+Edge+Node+Setup+5.2.26.exe"
            )
        )
        self.assertFalse(installer.verify_host("http://theta-mkt-api.thetatoken.org/x"))
        self.assertFalse(installer.verify_host("https://evil.example.com/x"))
        self.assertFalse(
            installer.verify_host(
                "https://s3.us-east-2.amazonaws.com/evil-bucket/Theta+Edge+Node+Setup+5.2.26.exe"
            )
        )

    def test_installer_version_parses_redirect(self):
        self.assertEqual(
            installer.installer_version(
                "https://s3.us-east-2.amazonaws.com/assets.thetatoken.org/apps/Theta+Edge+Node+Setup+5.2.26.exe"
            ),
            "5.2.26",
        )
        self.assertEqual(installer.installer_version("https://x/no-version.exe"), "")

    def test_verify_installer_accepts_pinned_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "setup.exe"
            path.write_bytes(b"stub")
            with patch.object(
                installer,
                "_sha256",
                return_value=installer.PINNED_INSTALLERS["5.2.26"],
            ), patch.object(
                installer,
                "authenticode",
                return_value={
                    "status": "Valid",
                    "subject": installer.SIGNER_SUBJECT,
                    "thumbprint": installer.SIGNER_THUMBPRINT,
                },
            ):
                ok, info, error = installer.verify_installer(path, "5.2.26")
        self.assertTrue(ok, error)
        self.assertEqual(info["version"], "5.2.26")

    def test_verify_installer_rejects_unpinned_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "setup.exe"
            path.write_bytes(b"stub")
            with patch.object(
                installer,
                "authenticode",
                return_value={
                    "status": "Valid",
                    "subject": installer.SIGNER_SUBJECT,
                    "thumbprint": installer.SIGNER_THUMBPRINT,
                },
            ):
                ok, _info, error = installer.verify_installer(path, "9.9.9")
        self.assertFalse(ok)
        self.assertIn("not pinned", error)

    def test_verify_installer_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "setup.exe"
            path.write_bytes(b"stub")
            with patch.object(
                installer,
                "authenticode",
                return_value={
                    "status": "Valid",
                    "subject": installer.SIGNER_SUBJECT,
                    "thumbprint": installer.SIGNER_THUMBPRINT,
                },
            ):
                ok, _info, error = installer.verify_installer(path, "5.2.26")
        self.assertFalse(ok)
        self.assertIn("SHA-256", error)

    def test_verify_installer_rejects_wrong_signer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "setup.exe"
            path.write_bytes(b"stub")
            with patch.object(
                installer,
                "_sha256",
                return_value=installer.PINNED_INSTALLERS["5.2.26"],
            ), patch.object(
                installer,
                "authenticode",
                return_value={
                    "status": "Valid",
                    "subject": installer.SIGNER_SUBJECT,
                    "thumbprint": "0" * 40,
                },
            ):
                ok, _info, error = installer.verify_installer(path, "5.2.26")
        self.assertFalse(ok)
        self.assertIn("thumbprint", error)

    def test_valid_override_path_requires_exact_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / installer.EXE_NAME
            bad = Path(tmp) / "cmd.exe"
            good.write_bytes(b"stub")
            bad.write_bytes(b"stub")
            self.assertTrue(installer.valid_override_path(str(good)))
            self.assertFalse(installer.valid_override_path(str(bad)))
            self.assertFalse(installer.valid_override_path(""))

    def test_launch_refuses_wrong_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "cmd.exe"
            bad.write_bytes(b"stub")
            with self.assertRaises(ValueError):
                installer.launch(bad)

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
