"""REST namespace for theta-edge-node, mounted at /api/plugins/theta-edge-node/.

Imported by path by the gateway, so shared modules are loaded through sys.path.
No secret is ever logged here.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theta_core import chain, diagnostics, edge_rpc, installer, keystore, state  # noqa: E402

router = APIRouter()
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
_EXPORT_LOCK = threading.Lock()
_EXPORT_FAILURES = {"count": 0, "until": 0.0}


def _client_is_local(request: Request) -> bool:
    host = getattr(request.client, "host", "") if request.client else ""
    return host in LOCAL_HOSTS


def _error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status_code)


def _wallet_address() -> tuple[str, str]:
    path = keystore.latest_keystore()
    if not path:
        return "", ""
    try:
        return keystore.keystore_address(path), str(path)
    except keystore.KeystoreError:
        return "", str(path)


@router.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "plugin": "theta-edge-node", "version": "0.2.0"}


@router.get("/node/status")
def node_status() -> dict[str, Any]:
    settings = state.load_settings()
    exe = installer.find_exe(settings.get("edge_node_path", ""))
    status = edge_rpc.node_status()
    wallet_address, wallet_path = _wallet_address()
    status.update(
        {
            "installed": bool(exe),
            "exe_path": str(exe) if exe else "",
            "process_running": installer.node_process_running(),
            "keystore_path": wallet_path,
            "wallet_address": wallet_address,
            "settings": settings,
        }
    )
    return status


@router.post("/node/install")
def node_install() -> dict[str, Any]:
    phase = installer.progress().get("phase")
    if phase in {"downloading", "verifying", "installing"}:
        return {"started": False, "reason": "install already running"}
    threading.Thread(target=installer.download_and_install, daemon=True).start()
    return {"started": True}


@router.post("/node/update")
def node_update() -> dict[str, Any]:
    return node_install()


@router.get("/node/install/status")
def node_install_status() -> dict[str, Any]:
    return installer.progress()


@router.post("/node/launch")
def node_launch() -> Any:
    exe = installer.find_exe(state.load_settings().get("edge_node_path", ""))
    if not exe:
        return _error("Theta Edge Node is not installed", 409)
    installer.launch(exe)
    state.save_settings({"last_running": True})
    return {"ok": True, "exe_path": str(exe)}


@router.post("/node/stop")
def node_stop() -> dict[str, Any]:
    installer.stop()
    state.save_settings({"last_running": False})
    return {"ok": True}


@router.get("/node/logs")
def node_logs(lines: int = 200) -> dict[str, Any]:
    return installer.read_logs(lines)


@router.get("/diagnostics")
def get_diagnostics() -> dict[str, Any]:
    return diagnostics.collect()


@router.get("/wallet")
def get_wallet() -> dict[str, Any]:
    address, path = _wallet_address()
    return {
        "exists": bool(address),
        "address": address,
        "keystore_path": path,
        "keystore_dir": str(keystore.keystore_dir()),
        "downloads_dir": str(keystore.downloads_dir()),
    }


@router.get("/wallet/balances")
def wallet_balances() -> Any:
    address, _path = _wallet_address()
    if not address:
        return {"exists": False}
    try:
        return {"exists": True, **chain.wallet_value(address)}
    except Exception as exc:  # noqa: BLE001 - network failure is a pane state
        return _error(f"balance lookup failed: {exc}", 502)


@router.post("/wallet/verify-export")
def verify_export() -> dict[str, Any]:
    exported = keystore.scan_downloads()
    node_address, _path = _wallet_address()
    if not exported:
        return {"found": False, "matches_node_wallet": False, "node_address": node_address}
    return {
        "found": True,
        **exported,
        "node_address": node_address,
        "matches_node_wallet": bool(node_address)
        and exported["address"].lower() == node_address.lower(),
    }


@router.post("/wallet/export")
async def export_wallet(request: Request) -> Any:
    if not _client_is_local(request):
        return _error("private-key export is available only from a local desktop connection", 403)
    now = time.time()
    with _EXPORT_LOCK:
        if _EXPORT_FAILURES["until"] > now:
            return _error("too many failed attempts; wait a minute", 429)
    body = await request.json()
    password = str(body.get("password") or "")
    path = keystore.latest_keystore()
    if not path:
        return _error("no Edge Node keystore found", 404)
    try:
        private_key = keystore.decrypt_keystore(keystore.read_keystore(path), password)
    except keystore.KeystoreError:
        await asyncio.sleep(0.4)
        with _EXPORT_LOCK:
            _EXPORT_FAILURES["count"] += 1
            if _EXPORT_FAILURES["count"] >= 5:
                _EXPORT_FAILURES["count"] = 0
                _EXPORT_FAILURES["until"] = time.time() + 60
        return _error("wrong password or corrupt keystore", 400)
    with _EXPORT_LOCK:
        _EXPORT_FAILURES["count"] = 0
        _EXPORT_FAILURES["until"] = 0.0
    return {
        "ok": True,
        "private_key": "0x" + private_key.hex(),
        "address": keystore.private_key_to_address(private_key),
        "keystore_path": str(path),
    }


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    return state.load_settings()


@router.post("/settings")
async def set_settings(request: Request) -> Any:
    body = await request.json()
    if not isinstance(body, dict):
        return _error("settings body must be an object")
    return state.save_settings(body)
