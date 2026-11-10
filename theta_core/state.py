"""Plugin-owned state under <hermes home>/plugin-data/theta-edge-node/."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

PLUGIN_ID = "theta-edge-node"
DEFAULT_SETTINGS: dict[str, Any] = {
    "auto_launch": True,
    "last_running": False,
    "edge_node_path": "",
}

_LOCK = threading.RLock()


def data_dir() -> Path:
    override = os.environ.get("THETA_PLUGIN_DATA_DIR")
    if override:
        root = Path(override)
        root.mkdir(parents=True, exist_ok=True)
        return root
    from plugins.plugin_storage import plugin_data_dir

    return plugin_data_dir(PLUGIN_ID)


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def load_settings() -> dict[str, Any]:
    with _LOCK:
        stored = _read(data_dir() / "settings.json", {})
    result = dict(DEFAULT_SETTINGS)
    if isinstance(stored, dict):
        result.update({key: stored[key] for key in DEFAULT_SETTINGS if key in stored})
    return result


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        current = load_settings()
        current.update({key: patch[key] for key in DEFAULT_SETTINGS if key in patch})
        _write(data_dir() / "settings.json", current)
    return current
