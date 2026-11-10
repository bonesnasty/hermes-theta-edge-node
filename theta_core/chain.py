"""Read-only Theta mainnet TFUEL balance and USD price."""

from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Any

ETH_RPC = "https://eth-rpc-api.thetatoken.org/rpc"
PRICE_URL = "https://api.coingecko.com/api/v3/simple/price?ids=theta-fuel&vs_currencies=usd"
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_CACHE: dict[str, Any] = {"at": 0.0, "usd": None}


def _post(url: str, payload: dict[str, Any], timeout: float = 8.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _price_json() -> dict[str, Any]:
    with urllib.request.urlopen(PRICE_URL, timeout=8.0) as response:
        return json.loads(response.read().decode("utf-8"))


def _require_address(address: str) -> str:
    if not ADDRESS_RE.match(address or ""):
        raise ValueError("invalid Theta address")
    return address


def tfuel_balance(address: str) -> float:
    address = _require_address(address)
    payload = _post(
        ETH_RPC,
        {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [address, "latest"], "id": 1},
    )
    if payload.get("error"):
        raise RuntimeError(str(payload["error"].get("message") or "eth_getBalance failed"))
    return int(payload["result"], 16) / 1e18


def tfuel_usd(force: bool = False) -> float:
    now = time.time()
    if not force and _CACHE["usd"] is not None and now - _CACHE["at"] < 60:
        return float(_CACHE["usd"])
    raw = _price_json()
    price = float((raw.get("theta-fuel") or {}).get("usd") or 0)
    _CACHE.update(at=now, usd=price)
    return price


def wallet_value(address: str) -> dict[str, Any]:
    address = _require_address(address)
    balance = tfuel_balance(address)
    try:
        price = tfuel_usd()
        error = ""
        source = "coingecko"
    except Exception as exc:  # noqa: BLE001 - the pane shows TFUEL without USD
        price = 0.0
        error = str(exc)
        source = "unavailable"
    return {
        "address": address,
        "tfuel": balance,
        "tfuel_usd": price,
        "total_usd": balance * price,
        "price_source": source,
        "price_error": error,
    }
