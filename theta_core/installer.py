"""Windows Theta Edge Node installer, launcher and log reader.

Downloads only from Theta's official endpoint, verifies the Authenticode
signature before executing, and never installs at plugin import time.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import keystore, state

DOWNLOAD_URL = "https://theta-mkt-api.thetatoken.org/v1/downloads/edge-node/windows"
ALLOWED_HOSTS = {
    "theta-mkt-api.thetatoken.org",
    "s3.us-east-2.amazonaws.com",
    "assets.thetatoken.org",
}
EXE_NAME = "Theta Edge Node.exe"
INSTALLER_NAME = "ThetaEdgeNodeSetup.exe"
SIGNATURE_SCRIPT = "verify_signature.ps1"

_PROGRESS: dict[str, Any] = {
    "phase": "idle",
    "downloaded": 0,
    "total": 0,
    "sha256": "",
    "signature": {},
    "path": "",
    "error": "",
    "installed_path": "",
}
_LOCK = threading.Lock()


def progress() -> dict[str, Any]:
    with _LOCK:
        return dict(_PROGRESS)


def _set(**values: Any) -> None:
    with _LOCK:
        _PROGRESS.update(values)


def _candidate_paths() -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    user = Path(os.environ.get("USERPROFILE", ""))
    return [
        local / "Programs" / "Theta Edge Node" / EXE_NAME,
        local / "Programs" / "theta-edge-node" / EXE_NAME,
        program_files / "Theta Edge Node" / EXE_NAME,
        user / "AppData" / "Local" / "Programs" / "Theta Edge Node" / EXE_NAME,
    ]


def _registry_paths() -> list[Path]:
    try:
        import winreg
    except ImportError:
        return []
    found: list[Path] = []
    roots = [
        (winreg.HKEY_CURRENT_USER, winreg.KEY_READ),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
    ]
    for root, flags in roots:
        try:
            base = winreg.OpenKey(root, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", 0, flags)
        except OSError:
            continue
        for index in range(winreg.QueryInfoKey(base)[0]):
            try:
                subkey = winreg.OpenKey(base, winreg.EnumKey(base, index))
                display = str(winreg.QueryValueEx(subkey, "DisplayName")[0])
                if "theta" not in display.lower() or "edge node" not in display.lower():
                    continue
                location = str(winreg.QueryValueEx(subkey, "InstallLocation")[0])
                if location:
                    found.append(Path(location) / EXE_NAME)
            except OSError:
                continue
    return found


def find_exe(override: str = "") -> Path | None:
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate
    for candidate in [*_candidate_paths(), *_registry_paths()]:
        if candidate.is_file():
            return candidate
    return None


def keystore_path() -> Path | None:
    return keystore.latest_keystore()


def node_process_running() -> bool:
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return EXE_NAME.lower() in (completed.stdout or "").lower()
    except Exception:
        return False


def launch(exe: Path) -> None:
    os.startfile(str(exe))  # type: ignore[attr-defined]


def stop() -> None:
    subprocess.run(
        ["taskkill", "/IM", EXE_NAME, "/F"],
        capture_output=True,
        text=True,
        timeout=15,
    )


def verify_host(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS


def authenticode(path: Path) -> dict[str, Any]:
    """Return the Authenticode status and signer for a downloaded installer."""
    script = state.data_dir() / SIGNATURE_SCRIPT
    script.write_text(
        "param([string]$Path)\n"
        "$sig = Get-AuthenticodeSignature -LiteralPath $Path\n"
        "$cert = $sig.SignerCertificate\n"
        "[pscustomobject]@{\n"
        "  Status = $sig.Status.ToString()\n"
        "  Subject = if ($cert) { $cert.Subject } else { '' }\n"
        "  Thumbprint = if ($cert) { $cert.Thumbprint } else { '' }\n"
        "} | ConvertTo-Json -Compress\n",
        encoding="utf-8",
    )
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as exc:  # noqa: BLE001 - signature check is best effort at the edge
        return {"status": "Unavailable", "subject": "", "thumbprint": "", "error": str(exc)}
    output = (completed.stdout or "").strip().lstrip("\ufeff")
    try:
        payload = json.loads(output) if output else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "status": str(payload.get("Status") or "Unknown"),
        "subject": str(payload.get("Subject") or ""),
        "thumbprint": str(payload.get("Thumbprint") or ""),
        "error": (completed.stderr or "").strip() if completed.returncode else "",
    }


def verify_installer(path: Path) -> tuple[bool, dict[str, Any], str]:
    info = authenticode(path)
    if info.get("status") != "Valid":
        return False, info, f"signature status: {info.get('status') or 'unknown'}"
    subject = str(info.get("subject") or "")
    if "theta" not in subject.lower():
        return False, info, f"signer does not look like Theta Labs: {subject or 'unknown signer'}"
    return True, info, ""


def download_and_install() -> None:
    _set(
        phase="downloading",
        downloaded=0,
        total=0,
        sha256="",
        signature={},
        path="",
        error="",
        installed_path="",
    )
    destination = state.data_dir() / "downloads" / INSTALLER_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        request = urllib.request.Request(
            DOWNLOAD_URL, headers={"User-Agent": "hermes-theta-edge-node/0.2"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            final_url = response.geturl()
            if not verify_host(final_url):
                raise RuntimeError(f"unexpected download host: {urllib.parse.urlparse(final_url).hostname}")
            total = int(response.headers.get("Content-Length") or 0)
            _set(total=total)
            digest = hashlib.sha256()
            with open(destination, "wb") as handle:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
                    with _LOCK:
                        _PROGRESS["downloaded"] += len(chunk)
        _set(phase="verifying", sha256=digest.hexdigest(), path=str(destination))
        ok, info, error = verify_installer(destination)
        _set(signature=info)
        if not ok:
            _set(phase="failed", error=f"Installer signature check failed: {error}")
            return
        _set(phase="installing")
        subprocess.run(
            [str(destination), "/S"],
            capture_output=True,
            text=True,
            timeout=900,
        )
        exe = find_exe(state.load_settings().get("edge_node_path", ""))
        if exe:
            _set(phase="done", installed_path=str(exe))
        else:
            os.startfile(str(destination))  # type: ignore[attr-defined]
            _set(
                phase="manual",
                error="Silent install did not finish; the installer is open for a manual click-through.",
            )
    except Exception as exc:  # noqa: BLE001 - surfaced in the pane
        _set(phase="failed", error=str(exc))


def logs_dir() -> Path | None:
    override = os.environ.get("THETA_LOGS_DIR")
    if override:
        path = Path(override)
        return path if path.is_dir() else None
    appdata = Path(os.environ.get("APPDATA", ""))
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    profile = Path(os.environ.get("USERPROFILE", ""))
    candidates = [
        appdata / "Theta Edge Node" / "ThetaEdgeNode" / "logs",
        appdata / "Theta Edge Node" / "logs",
        local / "Theta Edge Node" / "logs",
        profile / ".edgelauncher" / "logs",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _tail(path: Path, lines: int) -> str:
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        block = min(size, 128 * 1024)
        handle.seek(size - block)
        raw = handle.read()
    return raw.decode("utf-8", errors="replace")


def read_logs(lines: int = 200) -> dict[str, Any]:
    directory = logs_dir()
    if not directory:
        return {"path": "", "lines": []}
    files = [
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in {".log", ".txt"}
    ]
    if not files:
        return {"path": str(directory), "lines": []}
    newest = max(files, key=lambda path: path.stat().st_mtime)
    text = _tail(newest, lines)
    return {"path": str(newest), "lines": text.splitlines()[-max(1, min(lines, 1000)):]}


def downloads_dir() -> Path:
    return keystore.downloads_dir()
