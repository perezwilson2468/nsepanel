from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .. import config
from . import amf_req, mission_policy


CLIENT_LIBRARY_SALT = "Vmn34aAciYK00Hen26nT01"
START_MISSION_METHOD = "CharacterService.startMission"
UPDATE_CHARACTER_METHOD = "CharacterService.updateCharacter"
_MISSION_ID_RE = re.compile(r"^msn(\d+)$", re.IGNORECASE)


def _ensure_state() -> dict[str, Any]:
    state = getattr(config, "zenshin_state", None)
    if not isinstance(state, dict):
        state = {}
        config.zenshin_state = state
    state.setdefault("battle_flow_logver", "1")
    state.setdefault("start_battle_id", "1")
    return state


def _session_key() -> str:
    if not isinstance(getattr(config, "login_data", None), dict):
        raise ValueError("Ninja Zenshin login data is not loaded in memory")
    session_key = str(config.login_data.get("sessionkey") or config.login_data.get("sk") or "")
    if not session_key:
        raise ValueError("Ninja Zenshin session key is missing")
    return session_key


def _sha1_hex(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _effective_session_key() -> str:
    state = _ensure_state()
    session_key = str(state.get("mission_session_key") or "")
    if session_key:
        return session_key
    return _session_key()


def _mission_session_candidates() -> list[str]:
    if not isinstance(getattr(config, "login_data", None), dict):
        raise ValueError("Ninja Zenshin login data is not loaded in memory")

    candidates: list[str] = []
    for key in (
        "mission_session_key",
        "frame_sk",
        "sk",
        "sessionkey",
        "session_key",
    ):
        value = str(config.login_data.get(key) or "").strip()
        if value and value not in candidates:
            candidates.append(value)
    if not candidates:
        candidates.append(_session_key())
    return candidates


def _full_hash(payload: str, session_key: str | None = None) -> str:
    session_key = str(session_key or _effective_session_key())
    return _sha1_hex(f"{payload}{CLIENT_LIBRARY_SALT}{session_key}")


def _hash_slice_offset(session_key: str | None = None) -> int:
    active_session_key = str(session_key or _effective_session_key()).strip().lower()
    if len(active_session_key) >= 2:
        try:
            # Captured Zenshin mission packets derive the 12-char slice offset
            # from the low nibble of the first session-key byte.
            return int(active_session_key[1], 16)
        except ValueError:
            pass
    return 0


def short_hash(payload: str | None, session_key: str | None = None) -> str:
    # Zenshin mission packets use a 12-char slice of the standard salted SHA1.
    # The slice offset depends on the active mission session key.
    full_hash = _full_hash(str(payload or ""), session_key=session_key)
    offset = _hash_slice_offset(session_key=session_key)
    return full_hash[offset:offset + 12]


def short_array_hash(values: list[Any], session_key: str | None = None) -> str:
    serialized = ",".join("" if value is None else str(value) for value in values)
    return short_hash(serialized, session_key=session_key)


def _next_sequence_value() -> str:
    config.CLASSIC_REQUEST_SEQ = int(getattr(config, "CLASSIC_REQUEST_SEQ", 0) or 0) + 1
    return str(config.CLASSIC_REQUEST_SEQ)


def _next_sequence_hash() -> str:
    return short_hash(_next_sequence_value())


def _default_mission_clip_string(mission_id: str) -> str:
    match = _MISSION_ID_RE.match(str(mission_id or "").strip())
    if match:
        return f"[object Mission_{int(match.group(1))}]"
    return "[object MovieClip]"


def _resolve_mission_clip_string(mission_id: str) -> str:
    state = _ensure_state()
    stored = str(state.get("mission_clip_string") or "").strip()
    if stored:
        return stored
    return _default_mission_clip_string(mission_id)


def _set_mission_state(mission_id: str) -> str:
    state = _ensure_state()
    clip_string = _resolve_mission_clip_string(mission_id)
    previous_hash = state.get("mission_state_hash")
    if previous_hash is None:
        previous_hash = "null"
    state["mission_id"] = mission_id
    state["mission_state"] = 1
    state["mission_clip_string"] = clip_string
    state_hash = short_hash(f"1_setMission_{clip_string}_{previous_hash}")
    state["mission_state_hash"] = state_hash
    return state_hash


def _advance_to_first_event() -> str:
    state = _ensure_state()
    current_hash = str(state.get("mission_state_hash") or "")
    state["mission_state"] = 2
    state_hash = short_hash(f"2_setEventData_{current_hash}")
    state["mission_state_hash"] = state_hash
    return state_hash


def _complete_mission_state() -> str:
    state = _ensure_state()
    current_hash = str(state.get("mission_state_hash") or "")
    mission_state = int(state.get("mission_state") or 2)
    state_hash = short_hash(f"{mission_state}_completeMission_{current_hash}")
    state["mission_state_hash"] = state_hash
    return state_hash


def _resolve_mission_rewards(mission_id: str, xp_gain: int, gold_gain: int) -> tuple[int, int]:
    xp_value = int(xp_gain or 0)
    gold_value = int(gold_gain or 0)
    if xp_value <= 0:
        xp_value = mission_policy.mission_reward_value(mission_id, "xp")
    if gold_value <= 0:
        gold_value = mission_policy.mission_reward_value(mission_id, "gold")
    return xp_value, gold_value


def start_mission(mission_id: str) -> Any:
    normalized_mission_id = str(mission_id or "").strip().lower()
    if not normalized_mission_id:
        raise ValueError("Mission ID is required for CharacterService.startMission")

    state = _ensure_state()
    last_response: Any = {"status": "0", "error": "startMission not attempted"}
    for candidate_session_key in _mission_session_candidates():
        state["mission_session_key"] = candidate_session_key
        _set_mission_state(normalized_mission_id)
        response = amf_req._send_zenshin_amf(
            START_MISSION_METHOD,
            [
                candidate_session_key,
                normalized_mission_id,
                short_hash(normalized_mission_id, session_key=candidate_session_key),
            ],
        )
        last_response = response
        if isinstance(response, dict) and str(response.get("status")) == "1":
            start_battle_id = response.get("startBattleId") or response.get("start_battle_id")
            if start_battle_id is not None:
                state["start_battle_id"] = str(start_battle_id)
            _advance_to_first_event()
            return response
        if not (isinstance(response, dict) and str(response.get("error") or "").lower() == "invalid_hash"):
            return response
    return last_response


def update_character_progress(
    char_id: Any,
    char_level: Any,
    mission_id: str,
    xp_gain: int = 0,
    gold_gain: int = 0,
    item_used: list[Any] | None = None,
    pet_id: Any = 0,
    pet_level: Any = 0,
    datafile_hack: str = "",
    battle_log: dict[str, Any] | None = None,
) -> Any:
    session_key = _effective_session_key()
    state = _ensure_state()
    normalized_items = item_used if isinstance(item_used, list) else []
    normalized_mission_id = str(mission_id or "").strip().lower()
    xp_value, gold_value = _resolve_mission_rewards(
        normalized_mission_id,
        int(xp_gain or 0),
        int(gold_gain or 0),
    )
    result_flag = 0
    mission_state_hash = _complete_mission_state()
    sequence_hash = _next_sequence_hash()
    array_hash = short_array_hash(
        [
            session_key,
            char_id,
            char_level,
            xp_value,
            gold_value,
            normalized_items,
            pet_id,
            pet_level,
            normalized_mission_id,
            result_flag,
            mission_state_hash,
        ],
        session_key=session_key,
    )

    battle_flow_logver = str(state.get("battle_flow_logver") or "1")
    start_battle_id = str(state.get("start_battle_id") or "1")
    normalized_battle_log = battle_log if isinstance(battle_log, dict) else {"battles": []}
    battle_log_json = json.dumps(normalized_battle_log, separators=(",", ":"))
    battle_log_hash = short_hash(
        f"{battle_flow_logver}{start_battle_id}{battle_log_json}",
        session_key=session_key,
    )

    args = [
        session_key,
        char_id,
        char_level,
        xp_value,
        gold_value,
        normalized_items,
        pet_id,
        pet_level,
        normalized_mission_id,
        array_hash,
        sequence_hash,
        result_flag,
        mission_state_hash,
        battle_flow_logver,
        start_battle_id,
        battle_log_json,
        battle_log_hash,
    ]
    response = amf_req._send_zenshin_amf(UPDATE_CHARACTER_METHOD, args)
    if isinstance(response, dict) and str(response.get("status")) == "1":
        state["last_completed_mission_id"] = normalized_mission_id
    return response
