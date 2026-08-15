import time
import random
from typing import Any

from .. import config
from . import amf_req
from . import recovery, rate_control

EASTER_BATTLE_DELAY_SECONDS = 25
EASTER_CYCLE_COOLDOWN_MIN_SECONDS = 5
EASTER_CYCLE_COOLDOWN_MAX_SECONDS = 6
EASTER_MIN_CALL_DELAY_SECONDS = 1.2
EASTER_CALL_JITTER_SECONDS = 0.6
EASTER_RETRY_MAX = 3
EASTER_RETRY_DELAY_SECONDS = 2.0
EASTER_MAX_BUY_HEART_PER_CALL = 3

# Extracted from NinjaSaga Game Client/Panel/alldata.as enemy390..enemy419
EASTER_ENEMY_NAMES = {
    "enemy390": "Huffish Female Ninja",
    "enemy391": "Chocolate Evil Beast",
    "enemy392": "Chocolate Demon King",
    "enemy393": "Origami Devil Spider",
    "enemy394": "Ax Aboriginal",
    "enemy395": "Broadsword Aboriginal",
    "enemy396": "Spear Aboriginal",
    "enemy397": "Moai",
    "enemy398": "Moai Giant",
    "enemy399": "Frigga",
    "enemy400": "Odin",
    "enemy401": "Huginn",
    "enemy402": "Muninn",
    "enemy403": "Ebisu",
    "enemy404": "Ebisu",
    "enemy405": "Ebisu",
    "enemy406": "Ebisu",
    "enemy407": "Daikokuten",
    "enemy408": "Daikokuten",
    "enemy409": "Daikokuten",
    "enemy410": "Daikokuten",
    "enemy411": "Fukurokuju",
    "enemy412": "Fukurokuju",
    "enemy413": "Fukurokuju",
    "enemy414": "Fukurokuju",
    "enemy415": "Jurojin",
    "enemy416": "Jurojin",
    "enemy417": "Jurojin",
    "enemy418": "Jurojin",
    "enemy419": "Hotei",
}


def _stop_requested() -> bool:
    return rate_control.stop_requested()


def _wait_with_stop(seconds: int | float) -> bool:
    return rate_control.wait_with_stop(seconds, poll_seconds=0.2)


def _cycle_cooldown_seconds() -> float:
    return random.uniform(EASTER_CYCLE_COOLDOWN_MIN_SECONDS, EASTER_CYCLE_COOLDOWN_MAX_SECONDS)


def _jittered_seconds(base_seconds: float, jitter_seconds: float) -> float:
    return max(0.0, float(base_seconds)) + random.uniform(0.0, max(0.0, float(jitter_seconds)))


def _wait_for_next_call(last_call_at: float | None) -> tuple[bool, float]:
    if last_call_at is None:
        return True, time.time()
    target_gap = _jittered_seconds(EASTER_MIN_CALL_DELAY_SECONDS, EASTER_CALL_JITTER_SECONDS)
    elapsed = max(0.0, time.time() - last_call_at)
    wait_seconds = max(0.0, target_gap - elapsed)
    if wait_seconds <= 0:
        return True, time.time()
    if not _wait_with_stop(wait_seconds):
        return False, last_call_at
    return True, time.time()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _attempt_runtime_recovery(error_payload: Any, char_id: Any, context: str, cloudflare_rest_seconds: int) -> bool:
    error_text = ""
    if isinstance(error_payload, dict):
        error_text = str(error_payload.get("error") or error_payload.get("message") or error_payload)
    else:
        error_text = str(error_payload)
    return recovery.handle_runtime_exception(
        Exception(error_text),
        char_id,
        context,
        cloudflare_rest_seconds,
    )


def _is_success_response(response: Any) -> bool:
    if isinstance(response, dict):
        status = response.get("status")
        if status is not None:
            return str(status) == "1"
        error = response.get("error")
        if error is not None:
            return str(error) in {"0", "None", ""}
    return False


def _is_error_100(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    status_code = str(response.get("status") or "")
    error_code = str(response.get("error") or "")
    return status_code == "100" or error_code == "100"


def _call_amf_with_retry(
    label: str,
    fn,
    last_call_at: float | None,
) -> tuple[bool, Any, float | None]:
    response = None
    for attempt in range(1, EASTER_RETRY_MAX + 1):
        ok_to_call, last_call_at = _wait_for_next_call(last_call_at)
        if not ok_to_call:
            return False, {"status": 0, "error": "stopped"}, last_call_at
        try:
            response = fn()
            last_call_at = time.time()
        except Exception as exc:
            if attempt < EASTER_RETRY_MAX:
                retry_wait = _jittered_seconds(EASTER_RETRY_DELAY_SECONDS, EASTER_CALL_JITTER_SECONDS)
                print(
                    f"{label} error on attempt {attempt}/{EASTER_RETRY_MAX}: {exc}. "
                    f"retry in {retry_wait:.1f}s..."
                )
                if not _wait_with_stop(retry_wait):
                    return False, {"status": 0, "error": "stopped"}, last_call_at
                continue
            return False, {"status": 0, "error": str(exc)}, last_call_at

        if _is_error_100(response) and attempt < EASTER_RETRY_MAX:
            retry_wait = _jittered_seconds(EASTER_RETRY_DELAY_SECONDS, EASTER_CALL_JITTER_SECONDS)
            print(
                f"{label} locked (error 100) {attempt}/{EASTER_RETRY_MAX}, retry in {retry_wait:.1f}s..."
            )
            if not _wait_with_stop(retry_wait):
                return False, {"status": 0, "error": "stopped"}, last_call_at
            continue
        return True, response, last_call_at
    return False, response, last_call_at


def _collect_reward_values(node: Any, sink: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key).strip().lower()
            if key_text in {"status", "error"}:
                continue
            _collect_reward_values(value, sink)
        return
    if isinstance(node, list):
        for item in node:
            _collect_reward_values(item, sink)
        return
    if node is None:
        return
    text = str(node).strip()
    if not text:
        return
    sink.append(text)


def _extract_treasure_reward_summary(response: Any) -> str:
    if not isinstance(response, dict):
        return "reward: unknown"
    # First, try explicit reward-ish fields if server returns readable keys.
    direct_values: list[str] = []
    for key in ("reward", "rewards", "item", "items", "gold", "xp", "token", "event_point"):
        value = response.get(key)
        if value is not None:
            direct_values.append(f"{key}={value}")
    result = response.get("result")
    if isinstance(result, dict):
        for key in ("reward", "rewards", "item", "items", "gold", "xp", "token", "event_point"):
            value = result.get(key)
            if value is not None:
                direct_values.append(f"{key}={value}")
    if direct_values:
        return " | ".join(direct_values[:4])

    # Fallback: compact leaf-token summary for obfuscated payloads.
    leaves: list[str] = []
    _collect_reward_values(response, leaves)
    if not leaves:
        return "reward: none"
    unique: list[str] = []
    seen: set[str] = set()
    for token in leaves:
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)
        if len(unique) >= 4:
            break
    return "reward tokens: " + ", ".join(unique)


def _adjacent_indices(pos: int) -> list[int]:
    x = pos % 5
    y = pos // 5
    neighbors: list[int] = []
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if 0 <= nx < 5 and 0 <= ny < 4:
            neighbors.append(ny * 5 + nx)
    return neighbors


def _tile_distance(a: int, b: int) -> int:
    ax, ay = a % 5, a // 5
    bx, by = b % 5, b // 5
    return abs(ax - bx) + abs(ay - by)


def _find_treasure_tiles(enemy_ids: list[str]) -> list[int]:
    return [idx for idx, token in enumerate(enemy_ids) if _token_kind(str(token)) == "treasure"]


def _find_enemy_tiles(enemy_ids: list[str]) -> list[int]:
    return [idx for idx, token in enumerate(enemy_ids) if _token_kind(str(token)) == "enemy"]


def _choose_target_tile(current_pos: int, enemy_ids: list[str], boss_tile: int = 19) -> tuple[str, int]:
    treasure_tiles = _find_treasure_tiles(enemy_ids)
    if treasure_tiles:
        nearest_treasure = min(treasure_tiles, key=lambda idx: (_tile_distance(current_pos, idx), _tile_distance(idx, boss_tile), idx))
        return "chest", nearest_treasure
    return "final_boss", boss_tile


def _describe_target_hint(current_pos: int, enemy_ids: list[str], boss_tile: int = 19) -> str:
    treasure_tiles = _find_treasure_tiles(enemy_ids)
    enemy_tiles = [idx for idx in _find_enemy_tiles(enemy_ids) if idx != boss_tile]
    target_kind, target_tile = _choose_target_tile(current_pos, enemy_ids, boss_tile)
    chest_text = ",".join(str(idx) for idx in treasure_tiles) if treasure_tiles else "-"
    enemy_text = ",".join(str(idx) for idx in enemy_tiles) if enemy_tiles else "-"
    return (
        f"chests=[{chest_text}] | mini_bosses=[{enemy_text}] | "
        f"target_{target_kind}={target_tile} (distance={_tile_distance(current_pos, target_tile)}) | "
        f"final boss tile={boss_tile} (distance={_tile_distance(current_pos, boss_tile)})"
    )


def _pick_empty_move(
    current_pos: int,
    enemy_ids: list[str],
    previous_pos: int | None = None,
    boss_tile: int = 19,
) -> int | None:
    neighbors = _adjacent_indices(current_pos)
    empty_neighbors = [idx for idx in neighbors if idx < len(enemy_ids) and _token_kind(enemy_ids[idx]) == "empty"]
    if not empty_neighbors:
        return None
    _, target_tile = _choose_target_tile(current_pos, enemy_ids, boss_tile)
    preferred = sorted(
        empty_neighbors,
        key=lambda idx: (
            idx == previous_pos,
            _tile_distance(idx, target_tile),
            _tile_distance(idx, boss_tile),
            idx,
        ),
    )
    return preferred[0] if preferred else None


def _should_fight_adjacent_enemy(
    current_pos: int,
    enemy_pos: int,
    enemy_ids: list[str],
    boss_tile: int = 19,
) -> bool:
    if enemy_pos == boss_tile:
        return True
    _, target_tile = _choose_target_tile(current_pos, enemy_ids, boss_tile)
    current_distance = _tile_distance(current_pos, target_tile)
    enemy_distance = _tile_distance(enemy_pos, target_tile)
    return enemy_distance < current_distance


def _parse_battle_status(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    result = payload.get("result")
    if str(payload.get("status")) != "1" or not isinstance(result, dict):
        # Some servers return nested wrappers after decrypt;
        # detect the first object that looks like Easter map payload.
        candidates = [payload]
        candidates.extend(v for v in payload.values() if isinstance(v, dict))
        result = None
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            possible = candidate.get("result")
            if isinstance(possible, dict) and ("enemy_id" in possible or "remain_heart" in possible):
                result = possible
                break
            if "enemy_id" in candidate or "remain_heart" in candidate:
                result = candidate
                break
        if not isinstance(result, dict):
            return None

    enemy_ids = result.get("enemy_id")
    if not isinstance(enemy_ids, list):
        enemy_ids = []
    return {
        "start_position": _safe_int(result.get("start_position"), 0),
        "remain_heart": _safe_int(result.get("remain_heart"), 0),
        "heart_refill_remain": _safe_int(result.get("heart_refill_remain"), 0),
        "event_point": _safe_int(result.get("event_point"), 0),
        "enemy_id": enemy_ids,
        "enemy_reward": result.get("enemy_reward") or {},
    }


def _token_kind(token: str) -> str:
    if token == "1":
        return "empty"
    if token in {"enemy397", "enemy398"}:
        return "enemy"
    if token.startswith("enemy"):
        return "enemy"
    return "treasure"


def _enemy_label(enemy_id: str, slot_index: int) -> str:
    enemy_name = EASTER_ENEMY_NAMES.get(str(enemy_id).strip().lower())
    # Easter board has 20 tiles (0..19); tile 20 in UI equals index 19.
    if int(slot_index) == 19:
        if enemy_name:
            return f"Stone Giant (tile 20, {enemy_name}, {enemy_id})"
        return f"Stone Giant (tile 20, {enemy_id})"
    if enemy_name:
        return f"{enemy_name} ({enemy_id})"
    return enemy_id


def _log_map(enemy_ids: list[str], current_pos: int) -> None:
    print("Easter map slots:")
    for idx, token in enumerate(enemy_ids):
        marker = "*" if idx == current_pos else " "
        kind = _token_kind(str(token))
        print(f"  {marker}[{idx}] {kind}: {token}")


def _battle_log_json_for_enemy(enemy_id: str) -> str:
    # Match observed win packet shape for Easter event.
    return '{"battles":{"prototype":[],"length":1}}'


def _extract_char_id() -> Any:
    char_data = getattr(config, "char_data", None)
    if isinstance(char_data, dict):
        for key in ("character_id", "char_id", "id"):
            value = char_data.get(key)
            if value is not None:
                return value
        for container_key in ("character_data", "data", "character", "result"):
            nested = char_data.get(container_key)
            if isinstance(nested, dict):
                for key in ("character_id", "char_id", "id"):
                    value = nested.get(key)
                    if value is not None:
                        return value
    return None


def _extract_progress_snapshot(response: Any) -> tuple[str, int | None, int | None, int | None]:
    if not isinstance(response, dict):
        return "Unknown", None, None, None
    data = response
    nested = None
    for key in ("character_data", "data", "character", "result"):
        value = data.get(key)
        if isinstance(value, dict):
            nested = value
            break
    merged = dict(nested or {})
    merged.update(data)

    name = merged.get("character_name") or merged.get("name") or "Unknown"
    try:
        level = int(merged.get("character_level") or merged.get("level"))
    except Exception:
        level = None
    try:
        xp = int(merged.get("character_xp") or merged.get("xp"))
    except Exception:
        xp = None
    try:
        gold = int(merged.get("character_gold") or merged.get("gold"))
    except Exception:
        gold = None
    return str(name), level, xp, gold


def _finish_easter_boss(enemy_id: str) -> Any:
    battle_log_json = _battle_log_json_for_enemy(enemy_id)
    event_array = ["token", 0]
    # Use observed winning packet first: result=0 + default battle log.
    result = amf_req.get_boss_reward_event(
        boss_id=enemy_id,
        result_flag=0,
        event_array=event_array,
        battle_log_json=battle_log_json,
    )
    if _is_success_response(result):
        return result
    # Fallback for edge servers that expect result=1.
    fallback = amf_req.get_boss_reward_event(
        boss_id=enemy_id,
        result_flag=1,
        event_array=event_array,
        battle_log_json=battle_log_json,
    )
    return fallback


def easter_event():
    if _stop_requested():
        print("Easter event stopped by user request")
        return

    print("Starting NinjaSaga Easter 2015 automation...")
    current_pos: int | None = None
    cycle = 0
    last_amf_call_at = None
    cached_enemy_ids: list[str] = []
    cached_remain_heart = 0
    cached_refill_remain = 0
    cached_event_point = 0
    status_refresh_needed = True
    observed_max_heart = 0
    state = getattr(config, "ninjasaga_state", None) if isinstance(getattr(config, "ninjasaga_state", None), dict) else {}
    auto_spend_profile = config.get_ninjasaga_auto_spend_profile(state)
    anti_profile = config.get_ninjasaga_anti_detection_profile(state)
    cloudflare_rest_seconds = int(anti_profile.get("cloudflare_rest_seconds") or 60)
    auto_spend_enabled = bool(auto_spend_profile.get("enabled"))
    auto_spend_limit = max(0, _safe_int(auto_spend_profile.get("max_refills_per_run"), 0))
    auto_spend_used = 0
    if auto_spend_enabled and auto_spend_limit > 0:
        print(f"Easter auto-spend enabled | max_refills_per_run={auto_spend_limit}")
        print(f"[AutoSpend] {auto_spend_used}/{auto_spend_limit} used")
    else:
        print("Easter auto-spend disabled")

    while True:
        if _stop_requested():
            print("Easter event stopped by user request")
            return

        cycle += 1
        if status_refresh_needed or not cached_enemy_ids:
            ok, payload, last_amf_call_at = _call_amf_with_retry(
                f"[Cycle {cycle}] getBattleStatus",
                lambda: amf_req.easter_get_battle_status(),
                last_amf_call_at,
            )
            if not ok:
                if _attempt_runtime_recovery(payload, _extract_char_id(), "getBattleStatus", cloudflare_rest_seconds):
                    status_refresh_needed = True
                    continue
                print(f"[Cycle {cycle}] getBattleStatus failed: {payload}")
                return
            status = _parse_battle_status(payload)
            if not status:
                print(f"[Cycle {cycle}] getBattleStatus failed: {payload}")
                return
            cached_remain_heart = int(status["remain_heart"])
            cached_refill_remain = int(status["heart_refill_remain"])
            cached_event_point = int(status["event_point"])
            cached_enemy_ids = [str(v) for v in status["enemy_id"]]
            if current_pos is None:
                current_pos = status["start_position"]
            status_refresh_needed = False

        remain_heart = cached_remain_heart
        refill_remain = cached_refill_remain
        event_point = cached_event_point
        enemy_ids = list(cached_enemy_ids)
        observed_max_heart = max(observed_max_heart, int(remain_heart))
        current_pos = int(current_pos)
        print(
            f"[Cycle {cycle}] hearts={remain_heart} refill={refill_remain}s "
            f"points={event_point} pos={current_pos}"
        )
        _log_map(enemy_ids, current_pos)
        print(f"[Cycle {cycle}] board -> {_describe_target_hint(current_pos, enemy_ids)}")

        boss_missing = len(enemy_ids) <= 19 or _token_kind(str(enemy_ids[19])) != "enemy"
        if boss_missing:
            print(f"[Cycle {cycle}] final boss tile 19 is gone, generating new map...")
            ok, map_res, last_amf_call_at = _call_amf_with_retry(
                f"[Cycle {cycle}] generateNewMap(final boss gone)",
                lambda: amf_req.easter_generate_new_map(),
                last_amf_call_at,
            )
            if not ok:
                if _attempt_runtime_recovery(map_res, _extract_char_id(), "generateNewMap(final boss gone)", cloudflare_rest_seconds):
                    status_refresh_needed = True
                    continue
                print(f"[Cycle {cycle}] generateNewMap failed: {map_res}")
                return
            if not _is_success_response(map_res):
                if _attempt_runtime_recovery(map_res, _extract_char_id(), "generateNewMap(final boss gone)", cloudflare_rest_seconds):
                    status_refresh_needed = True
                    continue
                print(f"[Cycle {cycle}] generateNewMap failed: {map_res}")
                return
            current_pos = 0
            setattr(config, "_easter_previous_pos", None)
            status_refresh_needed = True
            cooldown = _cycle_cooldown_seconds()
            print(f"[Cycle {cycle}] cooldown {cooldown:.1f}s before next action...")
            if not _wait_with_stop(cooldown):
                print("Easter event stopped by user request")
                return
            continue

        if remain_heart <= 0 and auto_spend_enabled:
            if auto_spend_used >= auto_spend_limit:
                print(
                    f"[Cycle {cycle}] [AutoSpend] {auto_spend_used}/{auto_spend_limit} completed. "
                    "hearts=0, stopping Easter automation."
                )
                return
            else:
                refill_target = max(1, int(observed_max_heart))
                print(
                    f"[Cycle {cycle}] hearts=0, auto-spend refill "
                    f"{auto_spend_used + 1}/{auto_spend_limit} -> target {refill_target} hearts..."
                )
                refill_success = False
                while True:
                    if _stop_requested():
                        print("Easter event stopped by user request")
                        return
                    missing = max(0, refill_target - int(cached_remain_heart))
                    if missing <= 0:
                        refill_success = True
                        break
                    buy_amount = min(EASTER_MAX_BUY_HEART_PER_CALL, missing)
                    ok, buy_res, last_amf_call_at = _call_amf_with_retry(
                        f"[Cycle {cycle}] buyBattleHeart x{buy_amount}",
                        lambda amount=buy_amount: amf_req.easter_buy_battle_heart(amount),
                        last_amf_call_at,
                    )
                    if not ok or not _is_success_response(buy_res):
                        if _attempt_runtime_recovery(
                            buy_res, _extract_char_id(), "buyBattleHeart", cloudflare_rest_seconds
                        ):
                            status_refresh_needed = True
                            break
                        print(f"[Cycle {cycle}] buyBattleHeart failed: {buy_res}")
                        break
                    print(f"[Cycle {cycle}] buyBattleHeart success: +{buy_amount} requested")

                    ok, payload, last_amf_call_at = _call_amf_with_retry(
                        f"[Cycle {cycle}] getBattleStatus(after refill)",
                        lambda: amf_req.easter_get_battle_status(),
                        last_amf_call_at,
                    )
                    if not ok:
                        if _attempt_runtime_recovery(
                            payload, _extract_char_id(), "getBattleStatus(after refill)", cloudflare_rest_seconds
                        ):
                            status_refresh_needed = True
                            break
                        print(f"[Cycle {cycle}] getBattleStatus(after refill) failed: {payload}")
                        break
                    refreshed_status = _parse_battle_status(payload)
                    if not refreshed_status:
                        print(f"[Cycle {cycle}] parse getBattleStatus(after refill) failed: {payload}")
                        break
                    cached_remain_heart = int(refreshed_status["remain_heart"])
                    cached_refill_remain = int(refreshed_status["heart_refill_remain"])
                    cached_event_point = int(refreshed_status["event_point"])
                    cached_enemy_ids = [str(v) for v in refreshed_status["enemy_id"]]
                    observed_max_heart = max(observed_max_heart, int(cached_remain_heart))
                    print(
                        f"[Cycle {cycle}] refill status -> hearts={cached_remain_heart}, "
                        f"target={refill_target}"
                    )
                    if cached_remain_heart >= refill_target:
                        refill_success = True
                        break
                auto_spend_used += 1
                if refill_success:
                    remain_heart = cached_remain_heart
                    refill_remain = cached_refill_remain
                    event_point = cached_event_point
                    enemy_ids = list(cached_enemy_ids)
                    print(
                        f"[Cycle {cycle}] auto-spend complete | hearts={remain_heart} "
                        f"| used={auto_spend_used}/{auto_spend_limit}"
                    )
                    print(f"[AutoSpend] {auto_spend_used}/{auto_spend_limit} used")
                else:
                    print(
                        f"[Cycle {cycle}] auto-spend could not refill hearts. "
                        f"used={auto_spend_used}/{auto_spend_limit}"
                    )

        neighbors = _adjacent_indices(current_pos)

        # 1) Open adjacent treasure first.
        treasure_target = None
        for idx in neighbors:
            if idx < len(enemy_ids) and _token_kind(enemy_ids[idx]) == "treasure":
                treasure_target = idx
                break

        if treasure_target is not None:
            print(f"[Cycle {cycle}] openTreasure at slot {treasure_target}")
            ok, open_res, last_amf_call_at = _call_amf_with_retry(
                f"[Cycle {cycle}] openTreasure",
                lambda: amf_req.easter_open_treasure(treasure_target),
                last_amf_call_at,
            )
            if not ok:
                if _attempt_runtime_recovery(open_res, _extract_char_id(), "openTreasure", cloudflare_rest_seconds):
                    status_refresh_needed = True
                    continue
                print(f"[Cycle {cycle}] openTreasure failed: {open_res}")
                return
            if not _is_success_response(open_res):
                if _attempt_runtime_recovery(open_res, _extract_char_id(), "openTreasure", cloudflare_rest_seconds):
                    status_refresh_needed = True
                    continue
                print(f"[Cycle {cycle}] openTreasure failed: {open_res}")
                return
            print(f"[Cycle {cycle}] chest -> {_extract_treasure_reward_summary(open_res)}")
            if treasure_target < len(enemy_ids):
                enemy_ids[treasure_target] = "1"
                cached_enemy_ids = list(enemy_ids)
            cooldown = _cycle_cooldown_seconds()
            print(f"[Cycle {cycle}] cooldown {cooldown:.1f}s before next action...")
            if not _wait_with_stop(cooldown):
                print("Easter event stopped by user request")
                return
            continue

        if remain_heart <= 0:
            print(
                f"[Cycle {cycle}] hearts=0 and no adjacent treasure. "
                "Cannot start battle; stopping to avoid pointless movement."
            )
            return

        # 2) Fight adjacent enemy only if it is on the way to the current target.
        enemy_target = None
        for idx in neighbors:
            if (
                idx < len(enemy_ids)
                and _token_kind(enemy_ids[idx]) == "enemy"
                and _should_fight_adjacent_enemy(current_pos, idx, enemy_ids)
            ):
                enemy_target = idx
                break

        if enemy_target is not None:
            enemy_id = enemy_ids[enemy_target]
            boss_label = _enemy_label(enemy_id, enemy_target)
            print(f"[Cycle {cycle}] startBattle {boss_label} at slot {enemy_target} from {current_pos}")
            ok, start_res, last_amf_call_at = _call_amf_with_retry(
                f"[Cycle {cycle}] startBattle",
                lambda: amf_req.easter_start_battle(enemy_id, enemy_target, current_pos),
                last_amf_call_at,
            )
            if not ok:
                if _attempt_runtime_recovery(start_res, _extract_char_id(), "startBattle", cloudflare_rest_seconds):
                    status_refresh_needed = True
                    continue
                print(f"[Cycle {cycle}] startBattle failed: {start_res}")
                return
            if not _is_success_response(start_res):
                if _attempt_runtime_recovery(start_res, _extract_char_id(), "startBattle", cloudflare_rest_seconds):
                    status_refresh_needed = True
                    continue
                print(f"[Cycle {cycle}] startBattle failed: {start_res}")
                return

            print(f"[Cycle {cycle}] waiting fixed {EASTER_BATTLE_DELAY_SECONDS}s before boss finish...")
            if not _wait_with_stop(EASTER_BATTLE_DELAY_SECONDS):
                print("Easter event stopped by user request")
                return

            ok, finish_res, last_amf_call_at = _call_amf_with_retry(
                f"[Cycle {cycle}] finishBossReward",
                lambda: _finish_easter_boss(enemy_id),
                last_amf_call_at,
            )
            if not ok:
                if _attempt_runtime_recovery(finish_res, _extract_char_id(), "finishBossReward", cloudflare_rest_seconds):
                    status_refresh_needed = True
                    continue
                print(f"[Cycle {cycle}] finish boss failed: {finish_res}")
                return
            if not _is_success_response(finish_res):
                if _attempt_runtime_recovery(finish_res, _extract_char_id(), "finishBossReward", cloudflare_rest_seconds):
                    status_refresh_needed = True
                    continue
                print(f"[Cycle {cycle}] finish boss failed: {finish_res}")
                return
            print(f"[Cycle {cycle}] boss finished: {boss_label}")
            setattr(config, "_easter_previous_pos", current_pos)
            current_pos = enemy_target
            # Refresh board/heart state after battle resolution.
            status_refresh_needed = True

            char_id = _extract_char_id()
            if char_id is not None:
                try:
                    ok, refreshed, last_amf_call_at = _call_amf_with_retry(
                        f"[Cycle {cycle}] getCharacterData",
                        lambda: amf_req.get_character_data(
                            char_id,
                            include_system_data=False,
                            include_extra_data=False,
                        ),
                        last_amf_call_at,
                    )
                    if ok and isinstance(refreshed, dict):
                        config.char_data = refreshed
                        char_name, lv, xp, gold = _extract_progress_snapshot(refreshed)
                        print(
                            f"[Cycle {cycle}] character -> {char_name} | Lv {lv} | XP {xp} | Gold {gold} "
                            f"| moved to tile {current_pos}"
                        )
                    elif not ok:
                        print(f"[Cycle {cycle}] character refresh skipped: {refreshed}")
                except Exception as exc:
                    print(f"[Cycle {cycle}] character refresh skipped: {exc}")

            cooldown = _cycle_cooldown_seconds()
            print(f"[Cycle {cycle}] cooldown {cooldown:.1f}s before next action...")
            if not _wait_with_stop(cooldown):
                print("Easter event stopped by user request")
                return
            continue

        # 3) Move to adjacent empty tile (local cursor move, as in panel map click).
        previous_pos = None
        if cycle > 1:
            previous_pos = getattr(config, "_easter_previous_pos", None)
        empty_target = _pick_empty_move(current_pos, enemy_ids, previous_pos=previous_pos)

        if empty_target is not None:
            print(
                f"[Cycle {cycle}] move from {current_pos} -> {empty_target} "
                f"| {_describe_target_hint(empty_target, enemy_ids)}"
            )
            setattr(config, "_easter_previous_pos", current_pos)
            current_pos = empty_target
            # No AMF needed for empty move; keep cached board and continue.
            if not _wait_with_stop(1):
                print("Easter event stopped by user request")
                return
            continue

        # 4) If stuck and map complete gate is open, request new map.
        print(f"[Cycle {cycle}] no adjacent action available, generating new map...")
        ok, map_res, last_amf_call_at = _call_amf_with_retry(
            f"[Cycle {cycle}] generateNewMap",
            lambda: amf_req.easter_generate_new_map(),
            last_amf_call_at,
        )
        if not ok:
            if _attempt_runtime_recovery(map_res, _extract_char_id(), "generateNewMap", cloudflare_rest_seconds):
                status_refresh_needed = True
                continue
            print(f"[Cycle {cycle}] generateNewMap failed: {map_res}")
            return
        if not _is_success_response(map_res):
            if _attempt_runtime_recovery(map_res, _extract_char_id(), "generateNewMap", cloudflare_rest_seconds):
                status_refresh_needed = True
                continue
            print(f"[Cycle {cycle}] generateNewMap failed: {map_res}")
            return
        # Reset local position as UI does after generateNewMap.
        current_pos = 0
        setattr(config, "_easter_previous_pos", None)
        status_refresh_needed = True
        cooldown = _cycle_cooldown_seconds()
        print(f"[Cycle {cycle}] cooldown {cooldown:.1f}s before next action...")
        if not _wait_with_stop(cooldown):
            print("Easter event stopped by user request")
            return
