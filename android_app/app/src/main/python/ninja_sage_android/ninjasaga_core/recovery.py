from __future__ import annotations

from typing import Any, Callable

from . import rate_control


def is_gateway_blocked_error(exc: Exception | str) -> bool:
    text = str(exc or "").lower()
    return "cloudflare" in text or "http 403" in text or "gateway is blocked" in text


def handle_runtime_exception(
    stop_event: Any,
    exc: Exception | str,
    char_id: Any,
    context: str,
    cloudflare_rest_seconds: int,
    relogin_and_reselect_character: Callable[[Any], bool] | None,
    log,
) -> bool:
    if is_gateway_blocked_error(exc):
        if log:
            log(f"{context} failed: {exc}", "warning")
            log(
                "NinjaSaga official gateway is currently blocked by Cloudflare for direct AMF panel traffic.",
                "warning",
            )
            log(
                f"Let's take rest for a moment ({cloudflare_rest_seconds}s), then retry automatically...",
                "warning",
            )
        return rate_control.wait_with_stop(stop_event, cloudflare_rest_seconds)

    if log:
        log(f"{context} error: {exc}", "warning")
        log("Attempting recovery: relogin + reselect current character...", "info")
    if not relogin_and_reselect_character:
        return False
    return bool(relogin_and_reselect_character(char_id))
