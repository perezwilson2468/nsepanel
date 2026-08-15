from __future__ import annotations

import json
import os
from typing import Any

_MISSION_DATA_CACHE: dict[str, dict[str, Any]] | None = None
_ENEMY_DATA_CACHE: dict[str, dict[str, Any]] | None = None


def package_data_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..", ".."))


def _load_json_file(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_json(filename: str) -> dict[str, Any]:
    packaged_path = os.path.join(package_data_root(), filename)
    if os.path.exists(packaged_path):
        payload = _load_json_file(packaged_path)
        if payload:
            return payload

    repo_path = os.path.join(repo_root(), "data", filename)
    if os.path.exists(repo_path):
        payload = _load_json_file(repo_path)
        if payload:
            return payload

    return {}


def mission_data() -> dict[str, dict[str, Any]]:
    global _MISSION_DATA_CACHE
    if _MISSION_DATA_CACHE is None:
        raw = _load_json("ninjasaga-mission-data.json")
        _MISSION_DATA_CACHE = {str(key).lower(): value for key, value in raw.items() if isinstance(value, dict)}
    return _MISSION_DATA_CACHE


def enemy_data() -> dict[str, dict[str, Any]]:
    global _ENEMY_DATA_CACHE
    if _ENEMY_DATA_CACHE is None:
        raw = _load_json("ninjasaga-enemy-data.json")
        _ENEMY_DATA_CACHE = {str(key).lower(): value for key, value in raw.items() if isinstance(value, dict)}
    return _ENEMY_DATA_CACHE
