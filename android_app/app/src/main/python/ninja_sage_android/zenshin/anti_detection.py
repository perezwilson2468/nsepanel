from __future__ import annotations

import time
from typing import Any

from ..core import config
from . import rate_control


def build_anti_detection_profile(state: dict[str, Any]) -> dict[str, Any]:
    profile = config.get_ninjasaga_anti_detection_profile(state)
    return {
        "action_delay_seconds": max(0, rate_control.int_or_default(profile.get("action_delay_seconds"), 8)),
        "cycle_cooldown_seconds": max(0, rate_control.int_or_default(profile.get("cycle_cooldown_seconds"), 3)),
        "rest_every_cycles": max(0, rate_control.int_or_default(profile.get("rest_every_cycles"), 50)),
        "rest_duration_seconds": max(0, rate_control.int_or_default(profile.get("rest_duration_seconds"), 60)),
        "action_jitter_seconds": max(0, rate_control.int_or_default(profile.get("action_jitter_seconds"), 5)),
        "min_call_delay_seconds": max(0, rate_control.int_or_default(profile.get("min_call_delay_seconds"), 4)),
        "start_retry_delay_seconds": max(1, rate_control.int_or_default(profile.get("start_retry_delay_seconds"), 6)),
        "start_max_retries": max(1, rate_control.int_or_default(profile.get("start_max_retries"), 3)),
        "cloudflare_rest_seconds": max(1, rate_control.int_or_default(profile.get("cloudflare_rest_seconds"), 120)),
        "cloudflare_backoff_steps_seconds": profile.get("cloudflare_backoff_steps_seconds") or [60, 120, 240],
        "cloudflare_backoff_max_seconds": max(1, rate_control.int_or_default(profile.get("cloudflare_backoff_max_seconds"), 300)),
        "failure_window_seconds": max(30, rate_control.int_or_default(profile.get("failure_window_seconds"), 180)),
        "max_failures_in_window": max(1, rate_control.int_or_default(profile.get("max_failures_in_window"), 6)),
        "circuit_cooldown_seconds": max(10, rate_control.int_or_default(profile.get("circuit_cooldown_seconds"), 120)),
    }


def next_cloudflare_wait(profile: dict[str, Any], backoff_index: int) -> tuple[int, int]:
    max_wait = rate_control.int_or_default(profile.get("cloudflare_backoff_max_seconds"), 300)
    steps = profile.get("cloudflare_backoff_steps_seconds") or [60, 120, 240]
    try:
        step_values = [max(1, int(v)) for v in steps]
    except Exception:
        step_values = [60, 120, 240]
    if not step_values:
        step_values = [60, 120, 240]
    idx = min(max(0, int(backoff_index)), len(step_values) - 1)
    wait_seconds = min(step_values[idx], max_wait)
    next_idx = min(idx + 1, len(step_values) - 1)
    return wait_seconds, next_idx


def register_failure_and_maybe_circuit(
    failure_timestamps: list[float],
    profile: dict[str, Any],
    cycle: int,
) -> bool:
    now = time.time()
    failure_timestamps.append(now)
    window_seconds = max(1, int(profile["failure_window_seconds"]))
    threshold = max(1, int(profile["max_failures_in_window"]))
    cutoff = now - window_seconds
    while failure_timestamps and failure_timestamps[0] < cutoff:
        failure_timestamps.pop(0)
    if len(failure_timestamps) < threshold:
        return True
    cooldown_seconds = int(profile["circuit_cooldown_seconds"])
    print(
        f"[Cycle {cycle}] Too many failures ({len(failure_timestamps)}/{threshold}) in "
        f"{window_seconds}s. Let's take a rest for {cooldown_seconds}s..."
    )
    return rate_control.wait_with_stop(cooldown_seconds)
