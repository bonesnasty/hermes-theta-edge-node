"""Read-only diagnostics for the pane's Copy diagnostics button. No secrets."""

from __future__ import annotations

import platform
import sys
from typing import Any

from . import edge_rpc, installer, keystore, state


def collect() -> dict[str, Any]:
    settings = state.load_settings()
    exe = installer.find_exe(settings.get("edge_node_path", ""))
    blob = keystore.latest_keystore()
    address = ""
    if blob:
        try:
            address = keystore.keystore_address(blob)
        except keystore.KeystoreError:
            address = ""
    return {
        "plugin": "theta-edge-node",
        "version": "0.2.0",
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "node": edge_rpc.node_status(),
        "install": installer.progress(),
        "exe_path": str(exe) if exe else "",
        "keystore_path": str(blob) if blob else "",
        "wallet_address": address,
        "logs_dir": str(installer.logs_dir() or ""),
        "settings": settings,
    }
