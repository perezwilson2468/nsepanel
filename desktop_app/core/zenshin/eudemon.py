from __future__ import annotations

import json
import os
import random
import re
from typing import Any

from .. import config
from . import amf_req, mission, rate_control, recovery
from .leveling import _cooldown_seconds

ZenshinEnemyDataPath = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "ninjasaga-enemy-data.json")
)

GET_HUNTING_STATUS_METHOD = "EudemonGarden.getHuntingStatus"
START_HUNTING_METHOD = "EudemonGarden.startHunting"
FINISH_HUNTING_METHOD = "EudemonGarden.finishHunting"

EUD_START_FINISH_DELAY_SECONDS = 25
EUD_CYCLE_COOLDOWN_SECONDS = 5

_ENEMY_META_CACHE: dict[str, dict[str, Any]] | None = None
_SKILL_TOKEN_RE = re.compile(r"skill\d+", re.IGNORECASE)
_WEAPON_TOKEN_RE = re.compile(r"wpn\d+", re.IGNORECASE)
_BACK_TOKEN_RE = re.compile(r"back\d+", re.IGNORECASE)


def _ensure_state() -> dict[str, Any]:
    state = getattr(config, "zenshin_state", None)
    if not isinstance(state, dict):
        state = {}
        config.zenshin_state = state
    state.setdefault("battle_flow_logver", "1")
    state.setdefault("start_battle_id", "1")
    return state


def _session_key() -> str:
    login_data = getattr(config, "login_data", None)
    if not isinstance(login_data, dict):
        raise ValueError("Ninja Zenshin login data is not loaded in memory")
    session_key = str(login_data.get("sessionkey") or login_data.get("sk") or "").strip()
    if not session_key:
        raise ValueError("Ninja Zenshin session key is missing")
    return session_key


def _stop_requested() -> bool:
    return rate_control.stop_requested()


def _wait_with_stop(seconds: int | float) -> bool:
    return rate_control.wait_with_stop(seconds, poll_seconds=0.2)


def _is_debug_enabled() -> bool:
    return bool(getattr(config, "ninjasaga_debug", False))


def _is_success_response(response: Any) -> bool:
    if isinstance(response, dict):
        status = response.get("status")
        if status is not None:
            return str(status) == "1"
        error = response.get("error")
        if error is not None:
            return str(error) in {"0", "None", ""}
    return False


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_enemy_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _load_enemy_meta() -> dict[str, dict[str, Any]]:
    global _ENEMY_META_CACHE
    if isinstance(_ENEMY_META_CACHE, dict):
        return _ENEMY_META_CACHE
    try:
        with open(ZenshinEnemyDataPath, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            _ENEMY_META_CACHE = {
                str(enemy_id).strip().lower(): value
                for enemy_id, value in payload.items()
                if isinstance(value, dict)
            }
            return _ENEMY_META_CACHE
    except Exception:
        pass
    _ENEMY_META_CACHE = {}
    return _ENEMY_META_CACHE


def _extract_enemy_ids(room: dict[str, Any]) -> list[str]:
    raw_boss = room.get("boss") or room.get("enemyId") or room.get("enemy_id") or []
    ids: list[str] = []
    if isinstance(raw_boss, list):
        for item in raw_boss:
            enemy_id = _normalize_enemy_id(item)
            if enemy_id:
                ids.append(enemy_id)
        return ids
    if isinstance(raw_boss, str):
        for part in raw_boss.split(","):
            enemy_id = _normalize_enemy_id(part)
            if enemy_id:
                ids.append(enemy_id)
        return ids
    enemy_id = _normalize_enemy_id(raw_boss)
    return [enemy_id] if enemy_id else []


def _looks_like_room(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    if "room" in node and isinstance(node.get("room"), list):
        return False
    keys = {"boss", "enemyId", "enemy_id", "time", "rank", "rewards", "status", "xp", "gold"}
    return bool(set(node.keys()) & keys)


def _find_room_list(node: Any) -> list[dict[str, Any]] | None:
    if isinstance(node, dict):
        room_value = node.get("room")
        if isinstance(room_value, list):
            exact_rooms: list[dict[str, Any]] = []
            for item in room_value:
                exact_rooms.append(item if isinstance(item, dict) else {})
            return exact_rooms
        for value in node.values():
            found = _find_room_list(value)
            if found is not None:
                return found
        return None
    if isinstance(node, list):
        for item in node:
            found = _find_room_list(item)
            if found is not None:
                return found
    return None


def _collect_room_candidates(node: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        if _looks_like_room(node):
            out.append(node)
        for value in node.values():
            _collect_room_candidates(value, out)
        return
    if isinstance(node, list):
        for item in node:
            _collect_room_candidates(item, out)


def _extract_rooms(payload: Any) -> list[dict[str, Any]]:
    exact_room_list = _find_room_list(payload)
    if exact_room_list is not None:
        return exact_room_list

    candidates: list[dict[str, Any]] = []
    _collect_room_candidates(payload, candidates)
    return candidates


def _extract_char_level() -> int:
    char_data = getattr(config, "char_data", None)
    if isinstance(char_data, dict):
        for key in ("character_level", "level"):
            if char_data.get(key) is not None:
                return _safe_int(char_data.get(key), 1)
        for container_key in ("character_data", "data", "character", "result"):
            nested = char_data.get(container_key)
            if isinstance(nested, dict):
                for key in ("character_level", "level"):
                    if nested.get(key) is not None:
                        return _safe_int(nested.get(key), 1)
    return 1


def _extract_char_id() -> Any:
    char_data = getattr(config, "char_data", None)
    if isinstance(char_data, dict):
        for key in ("character_id", "char_id", "id"):
            if char_data.get(key) is not None:
                return char_data.get(key)
        for container_key in ("character_data", "data", "character"):
            nested = char_data.get(container_key)
            if isinstance(nested, dict):
                for key in ("character_id", "char_id", "id"):
                    if nested.get(key) is not None:
                        return nested.get(key)
    return None


def _extract_char_xp_gold_level(snapshot: Any) -> tuple[int | None, int | None, int | None]:
    if not isinstance(snapshot, dict):
        return None, None, None

    containers = [
        snapshot,
        snapshot.get("character_data") if isinstance(snapshot.get("character_data"), dict) else None,
        snapshot.get("data") if isinstance(snapshot.get("data"), dict) else None,
        snapshot.get("character") if isinstance(snapshot.get("character"), dict) else None,
        snapshot.get("result") if isinstance(snapshot.get("result"), dict) else None,
    ]
    for target in containers:
        if not isinstance(target, dict):
            continue
        xp = target.get("character_xp")
        gold = target.get("character_gold")
        level = target.get("character_level") or target.get("level")
        if xp is None and gold is None and level is None:
            continue
        return (
            _safe_int(xp, 0) if xp is not None else None,
            _safe_int(gold, 0) if gold is not None else None,
            _safe_int(level, 0) if level is not None else None,
        )
    return None, None, None


def _account_type_name() -> str:
    login_data = getattr(config, "login_data", None)
    if not isinstance(login_data, dict):
        return "Unknown"
    raw = login_data.get("account_type")
    try:
        if int(raw) == 2:
            return "Premium"
    except Exception:
        pass
    return "Free User"


def _room_summary(room: dict[str, Any], room_index: int, enemy_meta: dict[str, dict[str, Any]]) -> tuple[str, list[str], int | None]:
    enemy_ids = _extract_enemy_ids(room)
    enemy_labels: list[str] = []
    min_req_values: list[int] = []
    for enemy_id in enemy_ids:
        meta = enemy_meta.get(enemy_id)
        if isinstance(meta, dict):
            enemy_name = str(meta.get("name") or enemy_id).strip() or enemy_id
            min_level = meta.get("min_level")
            if isinstance(min_level, int):
                min_req_values.append(min_level)
                enemy_labels.append(f"{enemy_name}({enemy_id}, minLv={min_level})")
            else:
                enemy_labels.append(f"{enemy_name}({enemy_id})")
        else:
            enemy_labels.append(enemy_id)

    room_min_req = max(min_req_values) if min_req_values else None
    prefix = (
        f"[Room {room_index}] tries={room.get('time')} rank={room.get('rank')} "
        f"status={room.get('status')}"
    )
    if room_min_req is not None:
        prefix += f" minLvReq={room_min_req}"
    if room.get("xp") is not None or room.get("gold") is not None:
        prefix += f" xp={room.get('xp')} gold={room.get('gold')}"
    return prefix, enemy_labels, room_min_req


def _print_status_overview(rooms: list[dict[str, Any]], enemy_meta: dict[str, dict[str, Any]]) -> None:
    for idx, room in enumerate(rooms):
        prefix, enemy_labels, _ = _room_summary(room, idx, enemy_meta)
        print(prefix)
        if enemy_labels:
            print("  Enemies: " + ", ".join(enemy_labels))
        rewards = room.get("rewards")
        if rewards:
            print(f"  Rewards: {rewards}")


def _collect_tokens_from_value(value: Any, sink: list[str]) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _collect_tokens_from_value(nested, sink)
        return
    if isinstance(value, list):
        for nested in value:
            _collect_tokens_from_value(nested, sink)
        return
    if not isinstance(value, str):
        return

    lowered = value.lower()
    sink.extend(_SKILL_TOKEN_RE.findall(lowered))
    sink.extend(_WEAPON_TOKEN_RE.findall(lowered))
    sink.extend(_BACK_TOKEN_RE.findall(lowered))


def _extract_battle_actions_from_character() -> tuple[list[str], str]:
    char_data = getattr(config, "char_data", None)
    tokens: list[str] = []
    _collect_tokens_from_value(char_data, tokens)
    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        normalized = token.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    skills = [t for t in deduped if t.startswith("skill")]
    weapon = next((t for t in deduped if t.startswith("wpn")), "wpn1")
    back = next((t for t in deduped if t.startswith("back")), "")
    start_log = f"{weapon},{back}," if back else f"{weapon},"

    if not skills:
        skills = ["skill1", "skill2", "skill3"]

    return [weapon] + skills, start_log


def _random_step_log(actions_pool: list[str], max_step: int = 8) -> list[dict[str, Any]]:
    steps = random.randint(5, max(5, int(max_step)))
    out: list[dict[str, Any]] = []
    for _ in range(steps):
        action = random.choice(actions_pool)
        dmg = 0 if random.random() < 0.15 else -random.randint(120, 24000)
        out.append({"action": action, "dmg": dmg})
    return out


def _build_battle_log_json(enemy_ids: list[str]) -> str:
    actions_pool, start_log = _extract_battle_actions_from_character()
    step_log = _random_step_log(actions_pool)
    payload = {
        "battles": [
            {
                "start_log": start_log,
                "step_log": step_log,
                "step": len(step_log),
                "enemyid": [str(enemy_id) for enemy_id in enemy_ids if str(enemy_id).strip()],
            }
        ]
    }
    return json.dumps(payload, separators=(",", ":"))


def _extract_xp_gold(finish_result: Any, selected_room: dict[str, Any]) -> tuple[Any, Any]:
    xp_gain = None
    gold_gain = None
    if isinstance(finish_result, dict):
        result_payload = finish_result.get("result")
        if isinstance(result_payload, (list, tuple)):
            if len(result_payload) > 0:
                xp_gain = result_payload[0]
            if len(result_payload) > 1:
                gold_gain = result_payload[1]
        elif isinstance(result_payload, dict):
            xp_gain = result_payload.get("xp") or result_payload.get("character_xp")
            gold_gain = result_payload.get("gold") or result_payload.get("character_gold")
        if xp_gain is None:
            xp_gain = finish_result.get("xp") or finish_result.get("character_xp")
        if gold_gain is None:
            gold_gain = finish_result.get("gold") or finish_result.get("character_gold")
    if xp_gain is None:
        xp_gain = selected_room.get("xp")
    if gold_gain is None:
        gold_gain = selected_room.get("gold")
    return xp_gain, gold_gain


def _get_hunting_status() -> Any:
    return amf_req._send_zenshin_amf(GET_HUNTING_STATUS_METHOD, [_session_key()])


def _start_hunting(room_index: int, enemy_ids: list[str]) -> Any:
    session_key = _session_key()
    room_value = int(room_index)
    enemy_list_string = ",".join(str(enemy_id).strip() for enemy_id in enemy_ids if str(enemy_id).strip())
    request_hash = mission.short_hash(f"{room_value}{enemy_list_string}", session_key=session_key)
    response = amf_req._send_zenshin_amf(
        START_HUNTING_METHOD,
        [session_key, room_value, request_hash],
    )
    state = _ensure_state()
    if isinstance(response, dict):
        start_battle_id = response.get("startBattleId") or response.get("start_battle_id")
        if start_battle_id is not None:
            state["start_battle_id"] = str(start_battle_id)
    return response


def _finish_hunting(
    room_index: int,
    item_used: list[Any] | None = None,
    result_flag: int = 0,
    battle_log_json: str | None = None,
) -> Any:
    session_key = _session_key()
    room_value = int(room_index)
    normalized_items = item_used if isinstance(item_used, list) else []
    result_value = int(result_flag)
    state = _ensure_state()
    start_battle_id = str(state.get("start_battle_id") or "1")
    battle_flow_logver = str(state.get("battle_flow_logver") or "1")
    battle_log = battle_log_json or '{"battles":{"prototype":[],"length":1}}'
    hunting_hash = mission.short_hash(f"{room_value}{result_value}", session_key=session_key)
    battle_log_hash = mission.short_hash(
        f"{battle_flow_logver}{start_battle_id}{battle_log}",
        session_key=session_key,
    )
    return amf_req._send_zenshin_amf(
        FINISH_HUNTING_METHOD,
        [
            session_key,
            room_value,
            normalized_items,
            result_value,
            hunting_hash,
            battle_flow_logver,
            start_battle_id,
            battle_log,
            battle_log_hash,
        ],
    )


def _refresh_character_cache() -> None:
    char_id = _extract_char_id()
    if char_id is None:
        return
    refreshed = amf_req.get_character_data(
        char_id,
        include_system_data=False,
        include_extra_data=False,
    )
    if isinstance(refreshed, dict):
        config.char_data = refreshed


def _resolve_reward_delta(
    before_snapshot: Any,
    after_snapshot: Any,
    finish_result: Any,
    selected_room: dict[str, Any],
) -> tuple[Any, Any]:
    xp_gain, gold_gain = _extract_xp_gold(finish_result, selected_room)
    if xp_gain is not None and gold_gain is not None:
        return xp_gain, gold_gain

    before_xp, before_gold, _ = _extract_char_xp_gold_level(before_snapshot)
    after_xp, after_gold, _ = _extract_char_xp_gold_level(after_snapshot)

    resolved_xp = xp_gain
    resolved_gold = gold_gain
    if resolved_xp is None and before_xp is not None and after_xp is not None:
        resolved_xp = max(0, after_xp - before_xp)
    if resolved_gold is None and before_gold is not None and after_gold is not None:
        resolved_gold = max(0, after_gold - before_gold)
    return resolved_xp, resolved_gold


def eudemon_garden():
    if _stop_requested():
        print("Ninja Zenshin Eudemon Garden stopped by user request")
        return

    print("Loading Ninja Zenshin Eudemon Garden hunting status...")
    state = _ensure_state()
    anti_profile = config.get_ninjasaga_anti_detection_profile(state)
    cloudflare_rest_seconds = int(anti_profile.get("cloudflare_rest_seconds") or 60)

    try:
        payload = _get_hunting_status()
    except Exception as exc:
        if recovery.handle_runtime_exception(exc, _extract_char_id(), "getHuntingStatus", cloudflare_rest_seconds):
            try:
                payload = _get_hunting_status()
            except Exception as exc2:
                print(f"Ninja Zenshin Eudemon Garden stopped: getHuntingStatus retry failed: {exc2}")
                return
        else:
            return

    if _is_debug_enabled():
        try:
            raw = json.dumps(payload, ensure_ascii=True, default=str)
        except Exception:
            raw = str(payload)
        if len(raw) > 2200:
            raw = f"{raw[:2200]}...(truncated {len(raw) - 2200} chars)"
        print(f"[Eudemon debug] getHuntingStatus raw: {raw}")

    rooms = _extract_rooms(payload)
    if not rooms:
        print(f"Ninja Zenshin Eudemon Garden status response has no room data: {payload}")
        return

    enemy_meta = _load_enemy_meta()
    print(
        f"Ninja Zenshin Eudemon Garden started | account={_account_type_name()} | rooms={len(rooms)} | "
        f"delay={EUD_START_FINISH_DELAY_SECONDS}s"
    )
    _print_status_overview(rooms, enemy_meta)

    cycle = 0
    while True:
        if _stop_requested():
            print("Ninja Zenshin Eudemon Garden stopped by user request")
            return

        cycle += 1
        try:
            payload = _get_hunting_status()
        except Exception as exc:
            if recovery.handle_runtime_exception(exc, _extract_char_id(), "getHuntingStatus", cloudflare_rest_seconds):
                continue
            return
        rooms = _extract_rooms(payload)
        if not rooms:
            print("Ninja Zenshin Eudemon Garden stopped: room data is empty.")
            return

        char_level = _extract_char_level()
        candidates: list[tuple[int, int, dict[str, Any]]] = []
        for raw_room_index, room in enumerate(rooms):
            tries = _safe_int(room.get("time"), 0)
            enemy_ids = _extract_enemy_ids(room)
            if tries <= 0 or not enemy_ids:
                continue
            _, _, min_req = _room_summary(room, raw_room_index, enemy_meta)
            required_level = min_req if isinstance(min_req, int) else 0
            if char_level < required_level:
                continue
            candidates.append((required_level, raw_room_index, room))

        if not candidates:
            print(f"[Cycle {cycle}] No eligible Ninja Zenshin Eudemon room (tries finished or level too low).")
            return

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _, selected_room_index, selected_room = candidates[0]
        enemy_ids = _extract_enemy_ids(selected_room)
        prefix, enemy_labels, _ = _room_summary(selected_room, selected_room_index, enemy_meta)

        print(f"[Cycle {cycle}] selected -> {prefix}")
        if enemy_labels:
            print(f"[Cycle {cycle}] enemies -> " + ", ".join(enemy_labels))

        print(f"[Cycle {cycle}] startHunting room={selected_room_index}")
        try:
            start_result = _start_hunting(selected_room_index, enemy_ids=enemy_ids)
        except Exception as exc:
            if recovery.handle_runtime_exception(exc, _extract_char_id(), "startHunting", cloudflare_rest_seconds):
                continue
            return
        if not _is_success_response(start_result):
            cooldown = _cooldown_seconds(start_result)
            if cooldown > 0:
                print(f"[Cycle {cycle}] startHunting rate-limited/cooldown detected, waiting {cooldown}s before retry...")
                if not _wait_with_stop(cooldown):
                    print("Ninja Zenshin Eudemon Garden stopped by user request")
                    return
                continue
            print(f"[Cycle {cycle}] startHunting failed: {start_result}")
            return

        print(f"[Cycle {cycle}] waiting fixed {EUD_START_FINISH_DELAY_SECONDS}s before finishHunting...")
        if not _wait_with_stop(EUD_START_FINISH_DELAY_SECONDS):
            print("Ninja Zenshin Eudemon Garden stopped by user request")
            return

        print(f"[Cycle {cycle}] finishHunting room={selected_room_index}")
        battle_log_json = _build_battle_log_json(enemy_ids)
        if _is_debug_enabled():
            print(f"[Eudemon debug] finish battle_log={battle_log_json}")
        before_snapshot = getattr(config, "char_data", None)
        try:
            finish_result = _finish_hunting(
                room_index=selected_room_index,
                item_used=[],
                result_flag=0,
                battle_log_json=battle_log_json,
            )
        except Exception as exc:
            if recovery.handle_runtime_exception(exc, _extract_char_id(), "finishHunting", cloudflare_rest_seconds):
                continue
            return
        if not _is_success_response(finish_result):
            cooldown = _cooldown_seconds(finish_result)
            if cooldown > 0:
                print(f"[Cycle {cycle}] finishHunting rate-limited/cooldown detected, waiting {cooldown}s before retry...")
                if not _wait_with_stop(cooldown):
                    print("Ninja Zenshin Eudemon Garden stopped by user request")
                    return
                continue
            print(f"[Cycle {cycle}] finishHunting failed: {finish_result}")
            return

        try:
            _refresh_character_cache()
        except Exception as exc:
            recovery.handle_runtime_exception(exc, _extract_char_id(), "refresh character data", cloudflare_rest_seconds)
        xp_gain, gold_gain = _resolve_reward_delta(
            before_snapshot,
            getattr(config, "char_data", None),
            finish_result,
            selected_room,
        )
        print(f"[Cycle {cycle}] ok -> finishHunting success | XP {xp_gain} | Gold {gold_gain}")

        print(f"[Cycle {cycle}] cooldown {EUD_CYCLE_COOLDOWN_SECONDS}s before next hunt...")
        if not _wait_with_stop(EUD_CYCLE_COOLDOWN_SECONDS):
            print("Ninja Zenshin Eudemon Garden stopped by user request")
            return
