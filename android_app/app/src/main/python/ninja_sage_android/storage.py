import json
import os
from typing import Any


PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_storage_dir = os.path.join(PACKAGE_DIR, "_state")


def set_storage_dir(path: str) -> str:
    global _storage_dir
    _storage_dir = path or _storage_dir
    os.makedirs(_storage_dir, exist_ok=True)
    return _storage_dir


def get_storage_dir() -> str:
    os.makedirs(_storage_dir, exist_ok=True)
    return _storage_dir


def state_path(name: str) -> str:
    return os.path.join(get_storage_dir(), name)


def save_json(name: str, data: Any) -> None:
    with open(state_path(name), "w", encoding="utf-8") as handle:
        json.dump(data, handle)


def load_json(name: str, default: Any = None) -> Any:
    path = state_path(name)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
