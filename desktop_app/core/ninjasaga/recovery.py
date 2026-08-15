from __future__ import annotations

import random
from typing import Any

from .. import config, amf_req
from .rate_control import wait_with_stop


def is_gateway_blocked_error(exc: Exception | str) -> bool:
    text = str(exc or "").lower()
    return "cloudflare" in text or "http 403" in text or "gateway is blocked" in text


def is_transient_connection_error(exc: Exception | str) -> bool:
    text = str(exc or "").lower()
    markers = (
        "remotedisconnected",
        "remote end closed connection without response",
        "connection aborted",
        "connection reset by peer",
        "read timed out",
        "connect timeout",
        "temporarily unavailable",
    )
    return any(marker in text for marker in markers)


def is_rate_limited_error(exc: Exception | str) -> bool:
    text = str(exc or "").lower()
    return "rate_limited" in text or "rate limited" in text


def _transient_retry_wait_seconds() -> int:
    current = config.get_current_base_game()
    if str(current.get("id") or "") == "zenshin":
        return 3
    return 2


def _rate_limited_retry_wait_seconds() -> int:
    current = config.get_current_base_game()
    if str(current.get("id") or "") == "zenshin":
        return random.randint(10, 15)
    return 6


def relogin_and_reselect_character(char_id: Any) -> bool:
    profile_id = config.get_current_amf_profile()["id"]
    credentials, _ = config.get_quick_login_credentials(profile_id)
    if not credentials:
        print("Relogin skipped: no quick login credentials available")
        return False

    username = credentials.get("username")
    password = credentials.get("password")
    if not username or not password:
        print("Relogin skipped: invalid quick login credentials")
        return False

    try:
        game_data = amf_req.check_version()
        version_hash = game_data.get("__", "") if isinstance(game_data, dict) else ""
        raw_build = game_data.get("_", config.BUILD_NUM) if isinstance(game_data, dict) else config.BUILD_NUM
        build_marker = str(raw_build)

        print("Relogin in progress...")
        login_result = amf_req.login(username, password, version_hash, build_marker)
        if not isinstance(login_result, dict) or str(login_result.get("status")) != "1":
            print(f"Relogin failed: {login_result}")
            return False
        config.login_data = login_result

        if char_id is None:
            print("Relogin success (no character reselection requested)")
            return True

        selected = amf_req.get_character_data(
            char_id,
            include_system_data=False,
            include_extra_data=False,
        )
        if not isinstance(selected, dict):
            print(f"Reselect failed: {selected}")
            return False
        config.char_data = selected
        print(f"Relogin success and character reselected: {char_id}")
        return True
    except Exception as exc:
        print(f"Relogin/reselect error: {exc}")
        return False


def handle_runtime_exception(
    exc: Exception,
    char_id: Any,
    context: str,
    cloudflare_rest_seconds: int,
) -> bool:
    if is_gateway_blocked_error(exc):
        print(f"{context} failed: {exc}")
        print(
            "NinjaSaga official gateway is currently blocked by Cloudflare for direct AMF panel traffic."
        )
        print(
            f"Let's take rest for a moment ({cloudflare_rest_seconds}s), then retry automatically..."
        )
        if not wait_with_stop(cloudflare_rest_seconds):
            return False
        return True

    if is_transient_connection_error(exc):
        retry_wait = _transient_retry_wait_seconds()
        print(f"{context} transient connection error: {exc}")
        print(f"Retrying current action in {retry_wait}s without relogin...")
        return wait_with_stop(retry_wait)

    if is_rate_limited_error(exc):
        retry_wait = _rate_limited_retry_wait_seconds()
        print(f"{context} rate limited: {exc}")
        print(f"Cooling down for {retry_wait}s, then retrying without relogin...")
        return wait_with_stop(retry_wait)

    print(f"{context} error: {exc}")
    print("Attempting recovery: relogin + reselect current character...")
    return relogin_and_reselect_character(char_id)
