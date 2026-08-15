from __future__ import annotations

import time
from typing import Any

from . import rate_control


def build_anti_detection_profile(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_delay_seconds": max(0, rate_control.int_or_default(settings.get("leveling_action_delay_seconds"), 10)),
        "cycle_cooldown_seconds": max(0, rate_control.int_or_default(settings.get("leveling_cycle_cooldown_seconds"), 5)),
        "rest_every_cycles": max(0, rate_control.int_or_default(settings.get("leveling_rest_every_cycles"), 40)),
        "rest_duration_seconds": max(0, rate_control.int_or_default(settings.get("leveling_rest_duration_seconds"), 60)),
        "action_jitter_seconds": max(0, rate_control.int_or_default(settings.get("leveling_action_jitter_seconds"), 2)),
        "min_call_delay_seconds": max(0, rate_control.int_or_default(settings.get("leveling_min_call_delay_seconds"), 4)),
        "start_retry_delay_seconds": max(1, rate_control.int_or_default(settings.get("leveling_start_retry_delay_seconds"), 6)),
        "start_max_retries": max(1, rate_control.int_or_default(settings.get("leveling_start_max_retries"), 3)),
        "cloudflare_rest_seconds": max(1, rate_control.int_or_default(settings.get("leveling_cloudflare_rest_seconds"), 60)),
        "cloudflare_backoff_steps_seconds": settings.get("leveling_cloudflare_backoff_steps_seconds") or [60, 120, 240],
        "cloudflare_backoff_max_seconds": max(1, rate_control.int_or_default(settings.get("leveling_cloudflare_backoff_max_seconds"), 300)),
        "failure_window_seconds": max(30, rate_control.int_or_default(settings.get("leveling_failure_window_seconds"), 180)),
        "max_failures_in_window": max(1, rate_control.int_or_default(settings.get("leveling_max_failures_in_window"), 6)),
        "circuit_cooldown_seconds": max(10, rate_control.int_or_default(settings.get("leveling_circuit_cooldown_seconds"), 120)),
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
    stop_event: Any,
    failure_timestamps: list[float],
    profile: dict[str, Any],
    cycle: int,
    log,
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
    if log:
        log(
            f"[Cycle {cycle}] Too many failures ({len(failure_timestamps)}/{threshold}) in "
            f"{window_seconds}s. Let's take a rest for {cooldown_seconds}s...",
            "warning",
        )
    return rate_control.wait_with_stop(stop_event, cooldown_seconds)
