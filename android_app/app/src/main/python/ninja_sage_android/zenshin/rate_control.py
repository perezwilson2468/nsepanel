import random
import time
from typing import Any

from ..core import config

DEFAULT_STOP_POLL_SECONDS = 0.2


def stop_requested() -> bool:
    stop_event = getattr(config, "stop_event", None)
    return bool(stop_event and stop_event.is_set())


def wait_with_stop(seconds: int | float, poll_seconds: float = DEFAULT_STOP_POLL_SECONDS) -> bool:
    remaining = float(seconds or 0)
    while remaining > 0:
        if stop_requested():
            return False
        sleep_slice = min(float(poll_seconds), remaining)
        time.sleep(sleep_slice)
        remaining -= sleep_slice
    return not stop_requested()


def jittered_wait_seconds(base_seconds: int | float, jitter_seconds: int | float) -> float:
    base = max(0.0, float(base_seconds or 0))
    jitter = max(0.0, float(jitter_seconds or 0))
    if jitter <= 0:
        return base
    return base + random.uniform(0.0, jitter)


def wait_min_call_interval(
    last_call_at: float | None,
    min_call_delay_seconds: int,
    action_jitter_seconds: int,
    poll_seconds: float = DEFAULT_STOP_POLL_SECONDS,
) -> tuple[bool, float]:
    if last_call_at is None:
        return True, time.time()
    wait_target = jittered_wait_seconds(min_call_delay_seconds, action_jitter_seconds)
    elapsed = max(0.0, time.time() - last_call_at)
    wait_seconds = max(0.0, wait_target - elapsed)
    if wait_seconds <= 0:
        return True, time.time()
    if not wait_with_stop(wait_seconds, poll_seconds=poll_seconds):
        return False, last_call_at
    return True, time.time()


def int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)
