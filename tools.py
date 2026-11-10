"""Handlers for the agent half. Public data only; no key material."""

from __future__ import annotations

import json
from typing import Any

from .theta_core import chain, edge_rpc, installer, keystore, state


def _wallet() -> dict[str, Any] | None:
    path = keystore.latest_keystore()
    if not path:
        return None
    try:
        return {"address": keystore.keystore_address(path), "path": str(path)}
    except keystore.KeystoreError:
        return None


def theta_node_status(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    status = edge_rpc.node_status()
    status["process_running"] = installer.node_process_running()
    settings = state.load_settings()
    exe = installer.find_exe(settings.get("edge_node_path", ""))
    status["installed"] = bool(exe)
    wallet = _wallet()
    if wallet:
        try:
            prices = chain.tfuel_usd()
            balance = chain.tfuel_balance(wallet["address"])
            status["wallet"] = {
                "address": wallet["address"],
                "tfuel": balance,
                "total_usd": balance * prices,
            }
        except Exception as exc:  # noqa: BLE001
            status["wallet"] = {"address": wallet["address"], "error": str(exc)}
    return json.dumps(status, indent=2)


def theta_wallet_address(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    wallet = _wallet()
    if not wallet:
        return json.dumps({"exists": False})
    result: dict[str, Any] = {"exists": True, "address": wallet["address"]}
    try:
        result["tfuel"] = chain.tfuel_balance(wallet["address"])
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    return json.dumps(result)
