from __future__ import annotations

import json
from typing import Any, Callable

from .. import ninjasaga_engine
from . import progress_parser, rate_control

MOTHERDAY_BOSS_ID = "enemy531"
SAKURA_ENEMIES = {
    "enemy289": "Origami Deer",
    "enemy290": "Origami Crane",
    "enemy291": "Origami Dragon",
    "enemy292": "Origami Bear",
    "enemy393": "Origami Devil Spider",
}
SAKURA_PETAL_COST = 10


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _is_success(response: Any) -> bool:
    return isinstance(response, dict) and str(response.get("status")) == "1"


def _response_message(response: Any) -> str:
    if isinstance(response, dict):
        return str(response.get("result") or response.get("message") or response.get("error") or response)
    return str(response)


def _wait_for_event_resource(stop_event: Any, runtime_settings: dict[str, Any], label: str, log: Callable[[str, str], None]) -> bool:
    wait_minutes = max(0, int(runtime_settings.get("event_wait_minutes", 30)))
    if wait_minutes <= 0:
        log(f"{label}: wait policy is 0 minutes, stopping.", "warning")
        return False
    log(f"{label}: waiting {wait_minutes} minute(s) for resource to recover...", "info")
    return rate_control.wait_with_stop(stop_event, wait_minutes * 60)


def _claim_event_boss_reward(boss_id: str, event_mode: str, seal_flag: int = 0) -> dict[str, Any]:
    event_payload = [event_mode, int(seal_flag)]
    result = ninjasaga_engine.get_boss_reward_event(boss_id, 0, event_payload)
    if _is_success(result):
        return result
    return ninjasaga_engine.get_boss_reward_event(boss_id, 1, event_payload)


def _motherday_attempts_remaining(payload: dict[str, Any]) -> int:
    result = payload.get("result") if isinstance(payload, dict) and isinstance(payload.get("result"), dict) else {}
    daily = result.get("daily_battle_data")
    if isinstance(daily, bool):
        return 1 if daily else 0
    if isinstance(daily, str):
        normalized = daily.strip().lower()
        if normalized in {"", "0", "false", "none", "null", "no"}:
            return 0
        if normalized in {"1", "true", "yes"}:
            return 1
        try:
            parsed = json.loads(daily)
            if isinstance(parsed, bool):
                return 1 if parsed else 0
            return max(0, int(parsed))
        except Exception:
            pass
    try:
        return max(0, int(daily))
    except Exception:
        return 1 if daily else 0


def _push_progress(char_id: str, on_update: Callable[[dict[str, Any]], None] | None, log: Callable[[str, str], None]) -> None:
    try:
        updated = ninjasaga_engine.get_character_data(char_id)
        _, level, xp, gold, _, _ = progress_parser.extract_progress_snapshot(updated, default_level=1)
        if on_update:
            on_update({"level": level, "xp": xp, "gold": gold})
    except Exception as exc:
        log(f"Progress refresh failed: {exc}", "warning")


def run_motherday_event(
    *,
    stop_event: Any,
    char_id: str,
    runtime_settings: dict[str, Any],
    on_update: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str, str], None] | None = None,
) -> None:
    logger = log or (lambda msg, lvl="info": None)
    logger("Loading Mother Day special battle status...", "info")
    while not rate_control.stop_requested(stop_event):
        status = ninjasaga_engine.motherday_get_special_battle_status()
        if not _is_success(status):
            logger(f"Mother Day status failed: {_response_message(status)}", "warning")
            return
        attempts = _motherday_attempts_remaining(status)
        if attempts <= 0:
            result_payload = status.get("result") if isinstance(status.get("result"), dict) else {}
            logger(
                f"Mother Day daily limit reached. daily_battle_data={result_payload.get('daily_battle_data')!r}",
                "info",
            )
            return
        logger(f"Mother Day attempts remaining: {attempts}", "info")
        if not rate_control.wait_with_stop(stop_event, 20):
            return
        result = _claim_event_boss_reward(MOTHERDAY_BOSS_ID, "token")
        if not _is_success(result):
            logger(f"Mother Day reward failed: {_response_message(result)}", "warning")
            return
        logger("Mother Day battle finished successfully.", "success")
        _push_progress(char_id, on_update, logger)
        if attempts <= 1:
            return
        if not rate_control.wait_with_stop(stop_event, 5):
            return


def _ensure_sakura_resources(
    *,
    stop_event: Any,
    runtime_settings: dict[str, Any],
    status: dict[str, Any],
    selected_enemy_id: str,
    log: Callable[[str, str], None],
) -> tuple[bool, dict[str, Any]]:
    mode = str(runtime_settings.get("event_resource_mode") or "wait").strip().lower()
    enemy_cost = SAKURA_PETAL_COST
    petals = _safe_int(status.get("petal_count"), 0)

    while petals < enemy_cost:
        if mode == "stop":
            log(f"Sakura Festival stopped: petals={petals}/{enemy_cost}.", "warning")
            return False, status
        if mode == "wait":
            if not _wait_for_event_resource(stop_event, runtime_settings, "Sakura Festival", log):
                return False, status
            refreshed = ninjasaga_engine.sakura_get_challenge_status()
            if not _is_success(refreshed):
                log(f"Sakura Festival refresh failed: {_response_message(refreshed)}", "warning")
                return False, status
            status = refreshed
            petals = _safe_int(status.get("petal_count"), 0)
            continue

        buy_amount = max(1, enemy_cost - petals)
        log(f"Sakura Festival: buying {buy_amount} petal(s)...", "info")
        buy_res = ninjasaga_engine.sakura_buy_petal(buy_amount)
        if not _is_success(buy_res):
            log(f"Sakura Festival buyPetal failed: {_response_message(buy_res)}", "warning")
            return False, status

        refreshed = ninjasaga_engine.sakura_get_challenge_status()
        if not _is_success(refreshed):
            log(f"Sakura Festival refresh failed: {_response_message(refreshed)}", "warning")
            return False, status
        status = refreshed
        petals = _safe_int(status.get("petal_count"), 0)
    return True, status


def run_sakura_event(
    *,
    stop_event: Any,
    char_id: str,
    runtime_settings: dict[str, Any],
    selected_enemy_id: str | None = None,
    selected_enemy_name: str | None = None,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str, str], None] | None = None,
) -> None:
    logger = log or (lambda msg, lvl="info": None)
    enemy_id = str(selected_enemy_id or "enemy289").strip().lower()
    if enemy_id not in SAKURA_ENEMIES:
        raise ValueError(f"Unsupported Sakura Festival enemy: {selected_enemy_id}")
    enemy_name = selected_enemy_name or SAKURA_ENEMIES[enemy_id]

    logger(f"Starting Sakura Festival against {enemy_name}...", "info")
    while not rate_control.stop_requested(stop_event):
        status = ninjasaga_engine.sakura_get_challenge_status()
        if not _is_success(status):
            logger(f"Sakura Festival status failed: {_response_message(status)}", "warning")
            return
        ready, status = _ensure_sakura_resources(
            stop_event=stop_event,
            runtime_settings=runtime_settings,
            status=status,
            selected_enemy_id=enemy_id,
            log=logger,
        )
        if not ready:
            return
        logger(
            f"Sakura Festival ready: petals={_safe_int(status.get('petal_count'), 0)} "
            f"enemy={enemy_name}",
            "info",
        )
        battle_delay_seconds = max(1, _safe_int(runtime_settings.get("sakura_battle_delay_seconds"), 20))
        logger("Sakura Festival: Will Capture without using Seal!", "info")
        logger(
            "Sakura Festival: waiting "
            f"{battle_delay_seconds} seconds for battle duration and Capture...",
            "info",
        )
        if not rate_control.wait_with_stop(stop_event, battle_delay_seconds):
            return
        result = _claim_event_boss_reward(enemy_id, "", seal_flag=1)
        if not _is_success(result):
            logger(f"Sakura Festival reward failed: {_response_message(result)}", "warning")
            return
        logger(f"Sakura Festival capture finished: {enemy_name}", "success")
        _push_progress(char_id, on_update, logger)
        if not rate_control.wait_with_stop(stop_event, 5):
            return
