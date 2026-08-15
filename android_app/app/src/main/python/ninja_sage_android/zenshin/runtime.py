from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from ..core import config


def _ensure_zenshin_runtime_state() -> dict:
    state = getattr(config, "zenshin_state", None)
    if not isinstance(state, dict):
        state = {}
        config.zenshin_state = state
    return state


@contextmanager
def use_zenshin_shared_runtime() -> Iterator[dict]:
    zenshin_state = _ensure_zenshin_runtime_state()
    previous_state = getattr(config, "ninjasaga_state", None)
    config.ninjasaga_state = zenshin_state
    try:
        yield zenshin_state
    finally:
        config.zenshin_state = zenshin_state
        config.ninjasaga_state = previous_state
