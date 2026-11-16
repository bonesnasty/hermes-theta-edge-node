"""Windows Theta Edge Node installer, launcher and log reader.

Downloads only from Theta's official endpoint, verifies the installer against a
pinned SHA-256 and the pinned Theta Labs Authenticode certificate, and never
installs at plugin import time.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
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
    "assets.thetatoken.org",
}
S3_HOST = "s3.us-east-2.amazonaws.com"
S3_PATH_PREFIX = "/assets.thetatoken.org/"
EXE_NAME = "Theta Edge Node.exe"
INSTALLER_NAME = "ThetaEdgeNodeSetup.exe"
SIGNATURE_SCRIPT = "verify_signature.ps1"

# Catalog bumps update this table. A build that is not pinned here is refused,
# so /node/update can only install a reviewed Theta release.
PINNED_INSTALLERS = {
    "5.2.26": "6acac6a905cdf74cce703d4b1ada0da18569b32781105ba1557003d10655f4eb",
}
SIGNER_SUBJECT = 'CN="Theta Labs, Inc.", O="Theta Labs, Inc.", L=San Jose, S=California, C=US'
SIGNER_THUMBPRINT = "D5A10D49B0D0CCC53CDA4F3883AD7E23DB107001"
VERSION_RE = re.compile(r"Setup[+ ](\d+(?:\.\d+)+)\.exe", re.IGNORECASE)

_PROGRESS: dict[str, Any] = {
    "phase": "idle",
    "version": "",
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


def valid_override_path(value: str) -> bool:
    if not value:
        return False
    path = Path(value)
    return path.name == EXE_NAME and path.is_file()


def find_exe(override: str = "") -> Path | None:
    if override and valid_override_path(override):
        return Path(override)
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
    path = Path(exe)
    if path.name != EXE_NAME or not path.is_file():
        raise ValueError(f"refusing to launch {path.name!r}; expected {EXE_NAME}")
    os.startfile(str(path))  # type: ignore[attr-defined]


def stop() -> None:
    subprocess.run(
        ["taskkill", "/IM", EXE_NAME, "/F"],
        capture_output=True,
        text=True,
        timeout=15,
    )


def verify_host(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if host in ALLOWED_HOSTS:
        return True
    if host == S3_HOST:
        return parsed.path.startswith(S3_PATH_PREFIX)
    return False


def installer_version(url: str) -> str:
    match = VERSION_RE.search(urllib.parse.unquote(url))
    return match.group(1) if match else ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def verify_installer(path: Path, version: str) -> tuple[bool, dict[str, Any], str]:
    actual = _sha256(path)
    info = authenticode(path)
    info.update({"sha256": actual, "version": version})

    expected = PINNED_INSTALLERS.get(version)
    if not expected:
        return False, info, f"installer version {version or 'unknown'} is not pinned"
    if actual != expected:
        return False, info, "SHA-256 does not match the pinned build"
    if info.get("status") != "Valid":
        return False, info, f"signature status: {info.get('status') or 'unknown'}"
    if str(info.get("thumbprint") or "").upper() != SIGNER_THUMBPRINT:
        return False, info, "signer thumbprint does not match the pinned Theta Labs certificate"
    if str(info.get("subject") or "").strip() != SIGNER_SUBJECT:
        return False, info, "signer subject does not match the pinned Theta Labs certificate"
    return True, info, ""


def download_and_install() -> None:
    _set(
        phase="downloading",
        version="",
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
            DOWNLOAD_URL, headers={"User-Agent": "hermes-theta-edge-node/0.3"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            final_url = response.geturl()
            if not verify_host(final_url):
                raise RuntimeError(f"unexpected download host: {urllib.parse.urlparse(final_url).hostname}")
            total = int(response.headers.get("Content-Length") or 0)
            version = installer_version(final_url)
            _set(total=total, version=version)
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
        _set(phase="verifying", sha256=digest.hexdigest(), version=version, path=str(destination))
        ok, info, error = verify_installer(destination, version)
        _set(signature=info)
        if not ok:
            destination.unlink(missing_ok=True)
            _set(phase="failed", error=f"Installer verification failed: {error}")
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
