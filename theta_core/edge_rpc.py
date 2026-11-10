"""Local Theta Edge Node RPC client. Read-only; never signs anything."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

LAUNCHER_URL = "http://127.0.0.1:15888/rpc"
EDGECORE_URL = "http://127.0.0.1:17888/rpc"
JOBS_PER_PAGE = 100
MAX_PAGES = 10
_CACHE: dict[str, Any] = {"at": 0.0, "data": None}


class EdgeRpcError(RuntimeError):
    """The local node did not answer, or answered with an error."""


def rpc(url: str, method: str, params: list[Any] | None = None, timeout: float = 2.5) -> Any:
    body = json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}
    ).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EdgeRpcError(f"{method}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EdgeRpcError(f"{method}: invalid JSON-RPC response")
    if payload.get("error"):
        error = payload["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise EdgeRpcError(f"{method}: {message}")
    return payload.get("result")


def _version_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("version", "Version"):
            value = result.get(key)
            if isinstance(value, str):
                return value
    return ""


def _bool_field(result: Any, keys: tuple[str, ...]) -> bool | None:
    if not isinstance(result, dict):
        return None
    for key in keys:
        if key in result:
            return bool(result[key])
    return None


def _int_field(result: Any, keys: tuple[str, ...]) -> int | None:
    if not isinstance(result, dict):
        return None
    for key in keys:
        try:
            return int(result[key])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def summary() -> str:
    result = rpc(EDGECORE_URL, "edgecore.GetEdgeNodeSummary")
    if isinstance(result, dict):
        for key in ("Summary", "summary"):
            value = result.get(key)
            if isinstance(value, str) and value.startswith("0x"):
                return value
    return ""


def _jobs_page(kind: str, page: int) -> list[dict[str, Any]]:
    result = rpc(
        LAUNCHER_URL,
        "edgelauncher.GetPastJobs",
        [{"type": kind, "page": page, "num": JOBS_PER_PAGE}],
        timeout=3.0,
    )
    body = result.get("body") if isinstance(result, dict) else None
    return [row for row in body if isinstance(row, dict)] if isinstance(body, list) else []


def rewards_summary(max_pages: int = 2, force: bool = False) -> dict[str, Any]:
    now = time.time()
    if not force and _CACHE["data"] and now - _CACHE["at"] < 30:
        return _CACHE["data"]

    jobs: list[dict[str, Any]] = []
    for kind in ("lavita", "fedml"):
        for page in range(max(1, min(max_pages, MAX_PAGES))):
            batch = _jobs_page(kind, page)
            jobs.extend(batch)
            if len(batch) < JOBS_PER_PAGE:
                break

    pending = 0
    paid = 0
    errored = 0
    daily: dict[str, float] = {}
    recent: list[dict[str, Any]] = []
    for row in jobs:
        try:
            amount = int(str(row.get("reward_amount") or "0"))
        except (TypeError, ValueError):
            amount = 0
        status = str(row.get("status") or "").lower()
        if status == "completed":
            pending += amount
        elif status == "rewarded":
            paid += amount
        elif status == "errored":
            errored += 1
        stamp = row.get("end_time") or row.get("start_time")
        date = ""
        try:
            date = datetime.fromtimestamp(int(stamp) / 1000, timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            date = ""
        if date and amount:
            daily[date] = daily.get(date, 0.0) + amount / 1e18
        recent.append(
            {
                "id": str(row.get("id") or ""),
                "status": status,
                "tfuel": amount / 1e18,
                "date": date,
            }
        )

    today = datetime.now(timezone.utc).date()
    days = []
    for offset in range(6, -1, -1):
        key = (today - timedelta(days=offset)).isoformat()
        days.append({"date": key, "tfuel": round(daily.get(key, 0.0), 6)})

    result = {
        "pending_tfuel": pending / 1e18,
        "paid_tfuel": paid / 1e18,
        "jobs": len(jobs),
        "errored": errored,
        "daily": days,
        "recent": recent[:20],
    }
    _CACHE.update(at=now, data=result)
    return result


def node_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "running": False,
        "version": "",
        "holder_address": "",
        "synced": None,
        "peers": None,
        "rewards": None,
        "error": "",
    }
    try:
        status["version"] = _version_text(rpc(EDGECORE_URL, "edgecore.GetVersion", timeout=1.5))
        status["holder_address"] = summary()
        status["running"] = True
        status["rewards"] = rewards_summary()
        try:
            core = rpc(EDGECORE_URL, "edgecore.GetStatus", timeout=1.5)
            status["synced"] = _bool_field(core, ("synced", "Synced"))
            status["peers"] = _int_field(core, ("peers", "Peers"))
        except EdgeRpcError:
            pass
        try:
            peers = rpc(EDGECORE_URL, "edgecore.GetPeers", timeout=1.5)
            if isinstance(peers, list):
                status["peers"] = len(peers)
            elif isinstance(peers, dict):
                status["peers"] = _int_field(peers, ("peers", "Peers"))
        except EdgeRpcError:
            pass
    except EdgeRpcError as exc:
        status["error"] = str(exc)
    return status
