import io
import json
import re
import threading
import time
import traceback
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict, Optional

from . import storage
from . import ninjasaga_engine
from .core import amf_req as sage_amf_req
from .core import config as sage_config
from .rift import amf_req as rift_amf_req
from .rift.actions import resolve_rift_action
from .zenshin import amf_req as zenshin_amf_req
from .zenshin.eudemon import eudemon_garden as zenshin_eudemon_garden
from .zenshin.leveling import zenshin_leveling
from .zenshin.ss import ss_training as zenshin_ss_training
from .zenshin.tp import tp_training as zenshin_tp_training
from .core.daily import daily
from .core.eudemon import fight_eudemon_boss
from .core.event import (
    fight_aniv_event,
    fight_aniv_special_mission,
    fight_cd_event,
    fight_easter_event,
    fight_phantom_event,
    fight_pumpkin_event,
    fight_sakura_event,
    fight_snow_event,
    fight_thanks_event,
    fight_worldcup_event,
    fight_yinyang_event,
)
from .core.leveling import start_leveling
from .core.mission_s import mission_s
from .core.minigames import fight_minigame_event
from .core.monster_hunting import MonsterHunt
from .core.shadow_war import shadow_war_event
from .core.clan_war import clan_war_event as sage_clan_war_event
from .ninjasaga_core.clan_war import (
    build_clan_war_snapshot as build_ninjasaga_clan_war_snapshot,
    clan_war_event as ninjasaga_clan_war_event,
)
from .ninjasaga_core.special_events import run_motherday_event, run_sakura_event

SAGE_ACTION_CATALOG = {
    "leveling": {"label": "Leveling"},
    "daily": {"label": "Daily Missions"},
    "mission_s": {"label": "Mission S"},
    "eudemon": {"label": "Eudemon Boss"},
    "monster_hunt": {"label": "Monster Hunt"},
    "minigame_event": {
        "label": "Minigames Event",
        "enemy_options": [
            {"id": "anniversary", "name": "Anniversary Event Minigame"},
            {"id": "worldcup", "name": "World Cup Event 2026 Minigame"},
        ],
    },
    "cd_event": {"label": "CD Event"},
    "aniv_event": {"label": "Anniversary Event"},
    "aniv_special": {"label": "Anniversary Special Mission"},
    "sakura_event": {"label": "Sakura Bloom Event"},
    "easter_event": {
        "label": "Easter Event 2026",
        "enemy_options": [
            {"id": "ene_2124", "name": "Berserk Hornbill"},
            {"id": "ene_2125", "name": "Panzer Bear"},
            {"id": "ene_2126", "name": "Crimson Thorn"},
            {"id": "ene_2127", "name": "Calamity Serpent"},
            {"id": "ene_2128", "name": "Crimson Demon"},
        ],
    },
    "worldcup_event": {
        "label": "World Cup Event 2026",
        "enemy_options": [
            {"id": "ene_2129", "name": "Spirit Team Captain"},
            {"id": "ene_2130", "name": "Spirit Goalkeeper"},
        ],
    },
    "phantom": {"label": "Phantom Kyunoki"},
    "shadow_war": {"label": "Shadow War"},
    "clan_war": {"label": "Clan War"},
    "pumpkin_event": {
        "label": "Pumpkin Event",
        "enemy_options": [
            {"id": "ene_2104", "name": "Pumpkin Minion"},
            {"id": "ene_2105", "name": "Skeleton Ninja"},
            {"id": "ene_2106", "name": "Zombie Samurai"},
            {"id": "ene_2103", "name": "Headless Pumpkin Horseman"},
            {"id": "ene_2102", "name": "Cursed Pumpkin King"},
        ],
    },
    "yinyang_event": {
        "label": "Yin Yang Event",
        "enemy_options": [
            {"id": "ene_2100", "name": "Yin Tiger"},
            {"id": "ene_2101", "name": "Yang Dragon"},
        ],
    },
    "thanks_event": {
        "label": "Thanksgiving Event",
        "enemy_options": [
            {"id": "ene_2113", "name": "Cornfield Bandit"},
            {"id": "ene_2114", "name": "Cranberry Mage"},
            {"id": "ene_2115", "name": "Grateful Farmer"},
            {"id": "ene_2116", "name": "Turkey Champ"},
        ],
    },
}

NINJASAGA_ACTION_CATALOG = {
    "leveling": {"label": "Leveling"},
    "tp_training": {"label": "TP Training"},
    "ss_training": {"label": "SS Training"},
    "eudemon_garden": {"label": "Eudemon Garden"},
    "motherday_event": {"label": "Mother Day"},
    "sakura_event": {
        "label": "Sakura Festival",
        "enemy_options": [
            {"id": "enemy289", "name": "Origami Deer"},
            {"id": "enemy290", "name": "Origami Crane"},
            {"id": "enemy291", "name": "Origami Dragon"},
            {"id": "enemy292", "name": "Origami Bear"},
            {"id": "enemy393", "name": "Origami Devil Spider"},
        ],
    },
    "clan_war": {"label": "Clan War"},
}

ZENSHIN_ACTION_CATALOG = {
    "leveling": {"label": "Leveling"},
    "tp_training": {"label": "TP Training"},
    "ss_training": {"label": "SS Training"},
    "eudemon_garden": {"label": "Eudemon Garden"},
}

RIFT_ACTION_CATALOG = {
    "finisher_action": {"label": "Finisher Action"},
    "leveling": {"label": "Start Leveling"},
    "daily_missions": {"label": "Daily Missions"},
    "eudemon_garden": {"label": "Eudemon Garden"},
    "hunting_house": {"label": "Hunting House"},
    "easter_event": {"label": "Easter Event 2026"},
    "refresh": {"label": "Refresh Character Info"},
}

BASE_GAMES = {
    "sage": {
        "id": "sage",
        "label": "Ninja Sage",
        "server_selection_note": "Choose the AMF server before login.",
    },
    "rift": {
        "id": "rift",
        "label": "Ninja Rift",
        "server_selection_note": "Choose the Ninja Rift server before login.",
    },
    "ninjasaga": {
        "id": "ninjasaga",
        "label": "Ninja Saga",
        "server_selection_note": "NinjaSaga uses a separate Android engine flow.",
    },
    "zenshin": {
        "id": "zenshin",
        "label": "Ninja Zenshin",
        "server_selection_note": "Ninja Zenshin uses a separate Android engine flow.",
    },
}


def _current_action_catalog() -> Dict[str, Dict[str, Any]]:
    if STATE.base_game_id == "ninjasaga":
        return NINJASAGA_ACTION_CATALOG
    if STATE.base_game_id == "zenshin":
        return ZENSHIN_ACTION_CATALOG
    if STATE.base_game_id == "rift":
        return RIFT_ACTION_CATALOG
    return SAGE_ACTION_CATALOG


def _current_config():
    if STATE.base_game_id == "ninjasaga":
        return None
    return sage_config


def _current_profiles():
    if STATE.base_game_id == "ninjasaga":
        return ninjasaga_engine.get_amf_profiles()
    return sage_config.get_amf_profiles()


def _current_profile():
    if STATE.base_game_id == "ninjasaga":
        return ninjasaga_engine.get_current_amf_profile()
    return sage_config.get_current_amf_profile()


def _current_amf_client():
    if STATE.base_game_id == "rift":
        return rift_amf_req
    if STATE.base_game_id == "zenshin":
        return zenshin_amf_req
    return sage_amf_req


class _BridgeState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.base_game_id = "sage"
        self.logs = []
        self.max_logs = 500
        self.action_thread: Optional[threading.Thread] = None
        self.running_action: Optional[str] = None
        self.username: Optional[str] = None
        self.characters = []
        self.current_character: Optional[Dict[str, Any]] = None
        self.reauth_required_reason: Optional[str] = None
        self.rift_pending_verification: Optional[Dict[str, Any]] = None
        self.clan_war_state: Dict[str, Any] = {}
        self.clan_war_captcha_resume = threading.Event()

    def add_log(self, message: str, level: str = "info") -> None:
        clean = str(message).strip()
        if not clean:
            return
        with self.lock:
            self.logs.append({"message": clean, "level": level})
            self.logs = self.logs[-self.max_logs :]


STATE = _BridgeState()
sage_config.stop_event = threading.Event()
sage_config.storage_dir = None


def _default_ninjasaga_clan_war_state() -> Dict[str, Any]:
    settings = ninjasaga_engine.get_settings()
    return {
        "settings": {
            "auto_spend_token": bool(settings.get("clan_war_auto_spend_token")),
            "stamina_refill_source": str(settings.get("clan_war_stamina_refill_source") or "auto"),
            "bleeding_mode": bool(settings.get("clan_war_bleeding_mode")),
            "manual_recruit": bool(settings.get("clan_war_manual_recruit")),
            "manual_member_ids": list(settings.get("clan_war_manual_member_ids") or []),
            "target_clan_id": str(settings.get("clan_war_target_clan_id") or ""),
            "target_clan_name": str(settings.get("clan_war_target_clan_name") or ""),
            "settings": {
                "battle_delay_seconds": int(settings.get("clan_war_battle_delay_seconds", 8)),
                "refresh_delay_seconds": int(settings.get("clan_war_refresh_delay_seconds", 4)),
                "buy_stamina_delay_seconds": int(settings.get("clan_war_buy_stamina_delay_seconds", 3)),
                "amf_call_delay_seconds": int(settings.get("clan_war_amf_call_delay_seconds", 1)),
                "post_captcha_resume_delay_seconds": int(settings.get("clan_war_post_captcha_resume_delay_seconds", 4)),
                "low_stamina_wait_minutes": int(settings.get("clan_war_low_stamina_wait_minutes", 30)),
            },
        },
        "snapshot": None,
        "running": False,
        "captcha_required": False,
        "captcha_message": "",
        "captcha_challenge": None,
        "captcha_debug": None,
        "current_target": {
            "id": str(settings.get("clan_war_target_clan_id") or ""),
            "name": str(settings.get("clan_war_target_clan_name") or ""),
        },
    }


def _get_clan_war_state() -> Dict[str, Any]:
    if not isinstance(STATE.clan_war_state, dict) or not STATE.clan_war_state:
        STATE.clan_war_state = _default_ninjasaga_clan_war_state()
    return STATE.clan_war_state


def _clear_clan_war_state() -> None:
    with STATE.lock:
        STATE.clan_war_state = {}
    STATE.clan_war_captcha_resume.clear()


def _should_skip_log_line(message: str) -> bool:
    stripped = str(message).strip()
    if len(stripped) < 6:
        return False
    if len(set(stripped)) != 1:
        return False
    return stripped[0] in {"=", "-", "_"}


class LogCapture(io.TextIOBase):
    def __init__(self, level: str = "info") -> None:
        self.level = level
        self._buffer = ""

    def write(self, value: str) -> int:
        self._buffer += value
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if not _should_skip_log_line(line):
                STATE.add_log(line, self.level)
        return len(value)

    def flush(self) -> None:
        if self._buffer.strip() and not _should_skip_log_line(self._buffer):
            STATE.add_log(self._buffer, self.level)
        self._buffer = ""


def _result(payload: Dict[str, Any]) -> str:
    return json.dumps(payload)


def _safe_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _safe_json_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json_value(item) for item in value]
    return str(value)


def _send_quick_login_to_hosting(username: str, password: str, user_id: str, amf_label: str) -> None:
    pass



def _serialize_characters(characters) -> list:
    serialized = []
    for index, char in enumerate(characters or []):
        if isinstance(char, dict):
            char_id = char.get("char_id") or char.get("character_id") or char.get("id")
            char_name = char.get("character_name") or char.get("name") or f"Character {index + 1}"
            char_level = char.get("character_level") or char.get("level") or 0
            char_xp = char.get("character_xp") or char.get("xp") or 0
            serialized.append(
                {
                    "index": index,
                    "character_id": char_id,
                    "character_name": char_name,
                    "character_level": char_level,
                    "xp": char_xp,
                }
            )
            continue

        # NinjaSaga may return row arrays: [char_id, name, level, ...]
        if isinstance(char, (list, tuple)):
            char_id = char[0] if len(char) > 0 else None
            char_name = char[1] if len(char) > 1 else f"Character {index + 1}"
            char_level = char[2] if len(char) > 2 else 0
            try:
                level_value = int(char_level)
            except Exception:
                level_value = 0
            serialized.append(
                {
                    "index": index,
                    "character_id": char_id,
                    "character_name": str(char_name),
                    "character_level": level_value,
                    "xp": 0,
                }
            )
            continue

        if char is not None:
            serialized.append(
                {
                    "index": index,
                    "character_id": str(char),
                    "character_name": f"Character {index + 1}",
                    "character_level": 0,
                    "xp": 0,
                }
            )
    return serialized


def _normalize_state_characters(serialized_characters: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return [
        {
            "char_id": item.get("character_id"),
            "character_id": item.get("character_id"),
            "character_name": item.get("character_name"),
            "name": item.get("character_name"),
            "character_level": item.get("character_level"),
            "level": item.get("character_level"),
            "character_xp": item.get("xp") or 0,
            "xp": item.get("xp") or 0,
        }
        for item in (serialized_characters or [])
        if isinstance(item, dict)
    ]


def _build_login_version_args() -> tuple[str, str]:
    game_data = sage_config.game_data if isinstance(sage_config.game_data, dict) else {}
    token_value = str(game_data.get("__", ""))
    raw_build_value = game_data.get("_", 0)

    if STATE.base_game_id == "rift":
        return token_value, str(raw_build_value or "")

    try:
        build_value = str(int(raw_build_value))
    except Exception:
        build_value = "0"
    return token_value, build_value


def _extract_character_rows(payload: Any) -> list:
    def _rows_from_map_dict(value: dict[str, Any]) -> list:
        # AMF can decode array-like structures as dicts with numeric keys:
        # {"0": [...], "1": [...], "length": 2}
        indexed: list[tuple[int, Any]] = []
        for key, row in value.items():
            raw_key = str(key)
            digits = re.findall(r"\d+", raw_key)
            if not digits:
                continue
            try:
                idx = int(digits[-1])
            except Exception:
                continue
            indexed.append((idx, row))
        if indexed:
            indexed.sort(key=lambda x: x[0])
            out = [row for _, row in indexed if isinstance(row, (dict, list, tuple))]
            if out:
                return out
        # fallback: values can already contain rows, but keys are non-numeric
        out = [row for row in value.values() if isinstance(row, (dict, list, tuple))]
        if out:
            return out
        return []

    def _get_first_list_by_alias(obj: dict[str, Any], aliases: list[str]) -> list | None:
        for key in aliases:
            value = obj.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                mapped_rows = _rows_from_map_dict(value)
                if mapped_rows:
                    return mapped_rows
        # Also tolerate key formatting variants (spaces/underscore/hyphen/case)
        for raw_key, value in obj.items():
            norm = str(raw_key).strip().lower().replace("_", " ").replace("-", " ")
            if norm in aliases and isinstance(value, list):
                return value
            if norm in aliases and isinstance(value, dict):
                mapped_rows = _rows_from_map_dict(value)
                if mapped_rows:
                    return mapped_rows
        return None

    def _chunk_flat_rows(values: list[Any]) -> list:
        if not values:
            return []
        if any(isinstance(v, (dict, list, tuple)) for v in values):
            return []
        # Observed row shape usually [char_id, name, level, slot]
        chunk = 4 if len(values) >= 4 and len(values) % 4 == 0 else 3
        if len(values) < chunk:
            return []
        rows: list[list[Any]] = []
        for i in range(0, len(values), chunk):
            part = values[i : i + chunk]
            if len(part) < 3:
                continue
            rows.append(part)
        return rows

    if isinstance(payload, list):
        if payload and isinstance(payload[0], (dict, list, tuple)):
            return payload
        flat_rows = _chunk_flat_rows(payload)
        if flat_rows:
            return flat_rows
        return []
    if not isinstance(payload, dict):
        return []

    direct = _get_first_list_by_alias(payload, ["account data", "characters", "character"])
    if isinstance(direct, list):
        return direct

    result = payload.get("result")
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        mapped_rows = _rows_from_map_dict(result)
        if mapped_rows:
            return mapped_rows
        nested = _get_first_list_by_alias(result, ["account data", "characters", "character"])
        if isinstance(nested, list):
            return nested

    # Fallback: scan nested dict/list for first list of character-like rows.
    queue = [payload]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            for value in current.values():
                if isinstance(value, list) and value:
                    first = value[0]
                    if isinstance(first, dict):
                        keys = set(first.keys())
                        if {"character_id", "char_id", "character_name", "name"} & keys:
                            return value
                    elif isinstance(first, (list, tuple)) and len(first) >= 2:
                        return value
                    else:
                        flat_rows = _chunk_flat_rows(value)
                        if flat_rows:
                            return flat_rows
                elif isinstance(value, (dict, list)):
                    queue.append(value)
        elif isinstance(current, list):
            for item in current:
                if isinstance(item, (dict, list)):
                    queue.append(item)
    return []


def _extract_character(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if isinstance(response, (list, tuple)):
        char_id = response[0] if len(response) > 0 else None
        char_name = response[1] if len(response) > 1 else "Unknown"
        char_level = response[2] if len(response) > 2 else 0
        return {
            "character_id": char_id,
            "char_id": char_id,
            "character_name": char_name,
            "name": char_name,
            "character_level": char_level,
            "level": char_level,
        }

    if not isinstance(response, dict):
        return None

    if isinstance(response.get("character_data"), dict):
        return response["character_data"]

    if response.get("character_name") or response.get("name"):
        return response

    for key in ("data", "result", "character"):
        value = response.get(key)
        if isinstance(value, dict) and (value.get("character_name") or value.get("name")):
            return value
        if isinstance(value, (list, tuple)):
            char_id = value[0] if len(value) > 0 else None
            char_name = value[1] if len(value) > 1 else "Unknown"
            char_level = value[2] if len(value) > 2 else 0
            merged = dict(response)
            merged.update(
                {
                    "character_id": char_id,
                    "char_id": char_id,
                    "character_name": char_name,
                    "name": char_name,
                    "character_level": char_level,
                    "level": char_level,
                }
            )
            return merged

    return None


def _character_summary() -> Optional[Dict[str, Any]]:
    char = STATE.current_character
    if not char:
        return None
    if STATE.base_game_id == "ninjasaga":
        raw_tokens = None
        all_char = ninjasaga_engine.get_all_char_data()
        if isinstance(all_char, dict):
            raw_tokens = (
                all_char.get("tokens")
                or all_char.get("account_tokens")
                or all_char.get("account_balance")
            )
        if raw_tokens is None:
            login_data = ninjasaga_engine.get_login_data()
            if isinstance(login_data, dict):
                raw_tokens = (
                    login_data.get("tokens")
                    or login_data.get("account_tokens")
                    or login_data.get("account_balance")
                )
        if raw_tokens is None and isinstance(char, dict):
            raw_tokens = (
                char.get("tokens")
                or char.get("account_tokens")
                or char.get("account_balance")
            )
        if raw_tokens is None:
            raw_tokens = 0
    else:
        raw_tokens = None
        if isinstance(sage_config.all_char, dict):
            raw_tokens = (
                sage_config.all_char.get("tokens")
                or sage_config.all_char.get("account_tokens")
                or sage_config.all_char.get("account_balance")
            )
        if raw_tokens is None and isinstance(sage_config.login_data, dict):
            raw_tokens = (
                sage_config.login_data.get("tokens")
                or sage_config.login_data.get("account_tokens")
                or sage_config.login_data.get("account_balance")
            )
        if raw_tokens is None and isinstance(char, dict):
            raw_tokens = (
                char.get("tokens")
                or char.get("account_tokens")
                or char.get("account_balance")
            )
        if raw_tokens is None:
            raw_tokens = 0
    try:
        tokens = int(raw_tokens or 0)
    except Exception:
        tokens = 0
    return {
        "name": char.get("character_name") or char.get("name") or "Unknown",
        "level": char.get("character_level") or char.get("level") or 0,
        "xp": char.get("character_xp") or char.get("xp") or 0,
        "gold": char.get("character_gold") or char.get("gold") or 0,
        "tokens": tokens,
        "character_id": char.get("character_id") or char.get("char_id"),
    }


def sync_ninjasaga_web_cookies(cookie_header: str = "") -> str:
    try:
        result = ninjasaga_engine.import_webview_cookies(cookie_header)
        return _result(result)
    except Exception as exc:
        return _result({"success": False, "message": str(exc), "count": 0})


def get_ninjasaga_captcha_web_context() -> str:
    try:
        web_auth = ninjasaga_engine.get_last_web_auth() or {}
        return _result(
            {
                "success": True,
                "uuid": ninjasaga_engine._client_uuid(),
                "web_auth": web_auth,
                "user_session_key": "L9i3H4Q4ye",
                "working_cdn": "https://cdn.ninjasaga.cc/",
                "show_emulator_badge": False,
            }
        )
    except Exception as exc:
        return _result({"success": False, "message": str(exc)})


def _refresh_account_snapshot() -> None:
    try:
        if STATE.base_game_id == "ninjasaga":
            characters = ninjasaga_engine.get_all_characters()
        else:
            sage_config.set_base_game(STATE.base_game_id)
            amf_client = _current_amf_client()
            characters = amf_client.get_all_characters()
    except Exception as exc:
        STATE.add_log(f"Account refresh failed: {exc}", "warning")
        return

    if isinstance(characters, dict) and "account_data" in characters:
        if STATE.base_game_id != "ninjasaga":
            sage_config.all_char = characters
        characters = characters["account_data"]
    elif isinstance(characters, list):
        if STATE.base_game_id != "ninjasaga" and not isinstance(sage_config.all_char, dict):
            sage_config.all_char = {}
    else:
        return

    serialized = _serialize_characters(characters)
    with STATE.lock:
        STATE.characters = _normalize_state_characters(serialized)


def _clear_rift_pending_verification() -> None:
    with STATE.lock:
        STATE.rift_pending_verification = None


def _apply_character_updates(updates: Dict[str, Any]) -> None:
    if not isinstance(updates, dict):
        return

    with STATE.lock:
        current = STATE.current_character
        if not current:
            return

        if "level" in updates and updates["level"] is not None:
            current["character_level"] = updates["level"]
            current["level"] = updates["level"]
        if "xp" in updates and updates["xp"] is not None:
            current["character_xp"] = updates["xp"]
            current["xp"] = updates["xp"]
        if "gold" in updates and updates["gold"] is not None:
            current["character_gold"] = updates["gold"]
            current["gold"] = updates["gold"]
        if "tokens" in updates and updates["tokens"] is not None:
            if not isinstance(sage_config.all_char, dict):
                sage_config.all_char = {}
            sage_config.all_char["tokens"] = updates["tokens"]
            sage_config.all_char["account_tokens"] = updates["tokens"]
            if isinstance(sage_config.login_data, dict):
                sage_config.login_data["tokens"] = updates["tokens"]
                sage_config.login_data["account_tokens"] = updates["tokens"]
            current["tokens"] = updates["tokens"]
            current["account_tokens"] = updates["tokens"]


def _handle_reauth_required(reason: str) -> None:
    message = str(reason or "Session expired")
    with STATE.lock:
        STATE.reauth_required_reason = message
        STATE.running_action = None
        STATE.action_thread = None
    STATE.add_log(f"Reauthentication required: {message}", "warning")


def _current_clan_war_params() -> Dict[str, Any]:
    state = _get_clan_war_state()
    return dict(state.get("settings") or {})


def _handle_clan_war_state_update(updates: Dict[str, Any]) -> None:
    state = _get_clan_war_state()
    with STATE.lock:
        if "snapshot" in updates:
            state["snapshot"] = updates["snapshot"]
        if "running" in updates:
            state["running"] = bool(updates["running"])
        if "captcha_required" in updates:
            state["captcha_required"] = bool(updates["captcha_required"])
        if "captcha_message" in updates:
            state["captcha_message"] = str(updates["captcha_message"] or "")
        current_target = state.get("current_target") if isinstance(state.get("current_target"), dict) else {}
        snapshot = state.get("snapshot") if isinstance(state.get("snapshot"), dict) else {}
        if isinstance(snapshot, dict):
            war_list = snapshot.get("war_list") if isinstance(snapshot.get("war_list"), list) else []
            target_id = str(current_target.get("id") or "")
            if target_id:
                for item in war_list:
                    if isinstance(item, dict) and str(item.get("id") or "") == target_id:
                        current_target = {
                            "id": target_id,
                            "name": str(item.get("name") or current_target.get("name") or ""),
                        }
                        break
        state["current_target"] = current_target


def _action_runner(action_key: str, params: Optional[Dict[str, Any]]) -> None:
    stdout_capture = LogCapture("info")
    stderr_capture = LogCapture("error")
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            if STATE.base_game_id != "ninjasaga":
                sage_config.stop_event.clear()
                sage_config.character_update_callback = _apply_character_updates
                sage_config.session_reauth_required_callback = _handle_reauth_required

            if STATE.base_game_id == "ninjasaga" and action_key == "leveling":
                current = STATE.current_character or {}
                char_id = current.get("character_id") or current.get("char_id")
                ninjasaga_engine.run_leveling(
                    stop_event=sage_config.stop_event,
                    char_id=str(char_id or ""),
                    on_update=_apply_character_updates,
                    log=lambda msg, lvl="info": STATE.add_log(msg, lvl),
                )
            elif STATE.base_game_id == "ninjasaga" and action_key == "tp_training":
                current = STATE.current_character or {}
                char_id = current.get("character_id") or current.get("char_id")
                ninjasaga_engine.run_tp_training(
                    stop_event=sage_config.stop_event,
                    char_id=str(char_id or ""),
                    on_update=_apply_character_updates,
                    log=lambda msg, lvl="info": STATE.add_log(msg, lvl),
                )
            elif STATE.base_game_id == "ninjasaga" and action_key == "ss_training":
                current = STATE.current_character or {}
                char_id = current.get("character_id") or current.get("char_id")
                ninjasaga_engine.run_ss_training(
                    stop_event=sage_config.stop_event,
                    char_id=str(char_id or ""),
                    on_update=_apply_character_updates,
                    log=lambda msg, lvl="info": STATE.add_log(msg, lvl),
                )
            elif STATE.base_game_id == "ninjasaga" and action_key == "eudemon_garden":
                current = STATE.current_character or {}
                char_id = current.get("character_id") or current.get("char_id")
                ninjasaga_engine.run_eudemon_garden(
                    stop_event=sage_config.stop_event,
                    char_id=str(char_id or ""),
                    on_update=_apply_character_updates,
                    log=lambda msg, lvl="info": STATE.add_log(msg, lvl),
                )
            elif STATE.base_game_id == "ninjasaga" and action_key == "motherday_event":
                current = STATE.current_character or {}
                char_id = current.get("character_id") or current.get("char_id")
                run_motherday_event(
                    stop_event=sage_config.stop_event,
                    char_id=str(char_id or ""),
                    runtime_settings=ninjasaga_engine.get_settings(),
                    on_update=_apply_character_updates,
                    log=lambda msg, lvl="info": STATE.add_log(msg, lvl),
                )
            elif STATE.base_game_id == "ninjasaga" and action_key == "sakura_event":
                current = STATE.current_character or {}
                char_id = current.get("character_id") or current.get("char_id")
                run_sakura_event(
                    stop_event=sage_config.stop_event,
                    char_id=str(char_id or ""),
                    runtime_settings=ninjasaga_engine.get_settings(),
                    selected_enemy_id=(params or {}).get("enemy_id"),
                    selected_enemy_name=(params or {}).get("enemy_name"),
                    on_update=_apply_character_updates,
                    log=lambda msg, lvl="info": STATE.add_log(msg, lvl),
                )
            elif STATE.base_game_id == "ninjasaga" and action_key == "clan_war":
                ninjasaga_clan_war_event(
                    params=_current_clan_war_params(),
                    state_callback=_handle_clan_war_state_update,
                    captcha_resume_event=STATE.clan_war_captcha_resume,
                )
            elif STATE.base_game_id == "zenshin" and action_key == "leveling":
                sage_config.set_base_game("zenshin")
                zenshin_leveling()
            elif STATE.base_game_id == "zenshin" and action_key == "tp_training":
                sage_config.set_base_game("zenshin")
                zenshin_tp_training()
            elif STATE.base_game_id == "zenshin" and action_key == "ss_training":
                sage_config.set_base_game("zenshin")
                zenshin_ss_training()
            elif STATE.base_game_id == "zenshin" and action_key == "eudemon_garden":
                sage_config.set_base_game("zenshin")
                zenshin_eudemon_garden()
            elif STATE.base_game_id == "rift":
                sage_config.set_base_game("rift")
                spec = resolve_rift_action(
                    action_key,
                    params,
                    refresh_factory=lambda: refresh_character,
                    current_base_game=sage_config.get_current_base_game(),
                )
                spec.func()
            elif action_key == "leveling":
                start_leveling()
            elif action_key == "daily":
                daily()
            elif action_key == "mission_s":
                mission_s()
            elif action_key == "eudemon":
                fight_eudemon_boss()
            elif action_key == "monster_hunt":
                MonsterHunt().run()
            elif action_key == "minigame_event":
                minigame_type = (params or {}).get("enemy_id") or (params or {}).get("minigame_type")
                if not minigame_type:
                    raise ValueError("This action requires a minigame selection")
                fight_minigame_event(minigame_type)
            elif action_key == "cd_event":
                fight_cd_event()
            elif action_key == "aniv_event":
                fight_aniv_event()
            elif action_key == "aniv_special":
                fight_aniv_special_mission()
            elif action_key == "sakura_event":
                fight_sakura_event()
            elif action_key == "easter_event":
                fight_easter_event((params or {}).get("enemy_id"))
            elif action_key == "worldcup_event":
                fight_worldcup_event((params or {}).get("enemy_id"))
            elif action_key == "phantom":
                fight_phantom_event()
            elif action_key == "shadow_war":
                shadow_war_event()
            elif action_key == "clan_war":
                settings = sage_config.get_sage_global_settings({
                    "global_settings": storage.load_json("sage_settings.json", default=None),
                })
                sage_clan_war_event({
                    "auto_spend_token": bool(settings.get("clan_war_auto_spend_token")),
                    "settings": {
                        "battle_delay_seconds": int(settings.get("clan_war_battle_delay_seconds", 8)),
                        "buy_stamina_delay_seconds": int(settings.get("clan_war_buy_stamina_delay_seconds", 3)),
                        "stamina_refill_source": str(settings.get("clan_war_stamina_refill_source") or "auto"),
                    },
                })
            elif action_key == "pumpkin_event":
                fight_pumpkin_event((params or {}).get("enemy_id"))
            elif action_key == "yinyang_event":
                fight_yinyang_event((params or {}).get("enemy_id"))
            elif action_key == "snow_event":
                fight_snow_event((params or {}).get("enemy_id"))
            elif action_key == "thanks_event":
                fight_thanks_event((params or {}).get("enemy_id"))
            else:
                raise ValueError(f"Unsupported action: {action_key}")

        if action_key != "clan_war":
            STATE.add_log(f"Finished action: {_current_action_catalog()[action_key]['label']}", "success")
    except Exception as exc:
        STATE.add_log(f"Action failed: {exc}", "error")
        STATE.add_log(traceback.format_exc(), "error")
    finally:
        stdout_capture.flush()
        stderr_capture.flush()
        try:
            if STATE.base_game_id != "ninjasaga":
                refresh_character()
        except Exception as exc:
            STATE.add_log(f"Refresh after action failed: {exc}", "warning")
        with STATE.lock:
            STATE.running_action = None
            STATE.action_thread = None
            if action_key == "clan_war" and isinstance(STATE.clan_war_state, dict):
                STATE.clan_war_state["running"] = False
        sage_config.stop_event.clear()
        sage_config.character_update_callback = None
        sage_config.session_reauth_required_callback = None


def initialize(storage_dir: str, disable_remote_save: bool = False) -> str:
    actual_storage = storage.set_storage_dir(storage_dir)
    sage_config.set_base_game("sage")
    sage_config.storage_dir = actual_storage
    sage_config.quick_login_data = None
    sage_config.REMOTE_SAVE_ENABLED = not bool(disable_remote_save)
    saved_sage_settings = storage.load_json("sage_settings.json", default=None)
    if isinstance(saved_sage_settings, dict):
        for key, value in sage_config.get_sage_global_settings({"global_settings": saved_sage_settings}).items():
            setattr(sage_config, key, value)
    saved_rift_settings = storage.load_json("rift_settings.json", default=None)
    if isinstance(saved_rift_settings, dict):
        for key, value in sage_config.get_rift_settings({"global_settings": saved_rift_settings}).items():
            setattr(sage_config, key, value)
    saved_ns_settings = storage.load_json("ninjasaga_settings.json", default=None)
    ninjasaga_engine.update_settings(saved_ns_settings)
    saved_zen_settings = storage.load_json("zenshin_settings.json", default=None)
    sage_config.zenshin_state = sage_config.get_zenshin_settings({"settings": saved_zen_settings} if isinstance(saved_zen_settings, dict) else None)
    return _result(
        {
            "success": True,
            "storage_dir": actual_storage,
            "base_games": list(BASE_GAMES.values()),
            "current_base_game": BASE_GAMES[STATE.base_game_id],
            "actions": _current_action_catalog(),
            "amf_profiles": _current_profiles(),
            "current_amf_profile": _current_profile(),
        }
    )


def get_base_games() -> str:
    return _result(
        {
            "success": True,
            "games": list(BASE_GAMES.values()),
            "current": BASE_GAMES[STATE.base_game_id],
        }
    )


def get_ninjasaga_settings() -> str:
    return _result(
        {
            "success": True,
            "settings": ninjasaga_engine.get_settings(),
        }
    )


def get_zenshin_settings() -> str:
    state = {"settings": storage.load_json("zenshin_settings.json", default=None)}
    settings = sage_config.get_zenshin_settings(state)
    sage_config.zenshin_state = dict(settings)
    return _result(
        {
            "success": True,
            "settings": settings,
        }
    )


def get_sage_settings() -> str:
    state = {"global_settings": storage.load_json("sage_settings.json", default=None)}
    settings = sage_config.get_sage_global_settings(state)
    for key, value in settings.items():
        setattr(sage_config, key, value)
    return _result(
        {
            "success": True,
            "settings": settings,
        }
    )


def get_rift_settings() -> str:
    state = {"global_settings": storage.load_json("rift_settings.json", default=None)}
    settings = sage_config.get_rift_settings(state)
    for key, value in settings.items():
        setattr(sage_config, key, value)
    return _result(
        {
            "success": True,
            "settings": settings,
            "special_jounin_skill_options": sage_config.get_rift_special_jounin_skill_options(),
        }
    )


def set_sage_settings(settings_json: str = "{}") -> str:
    try:
        raw = json.loads(settings_json or "{}")
    except Exception as exc:
        return _result({"success": False, "message": f"Invalid settings JSON: {exc}"})
    try:
        settings = sage_config.get_sage_global_settings({"global_settings": raw if isinstance(raw, dict) else {}})
        storage.save_json("sage_settings.json", settings)
        for key, value in settings.items():
            setattr(sage_config, key, value)
        return _result({"success": True, "settings": settings})
    except Exception as exc:
        return _result({"success": False, "message": str(exc)})


def set_rift_settings(settings_json: str = "{}") -> str:
    try:
        raw = json.loads(settings_json or "{}")
    except Exception as exc:
        return _result({"success": False, "message": f"Invalid settings JSON: {exc}"})
    try:
        settings = sage_config.get_rift_settings({"global_settings": raw if isinstance(raw, dict) else {}})
        allowed_skills = {
            option.get("id")
            for option in sage_config.get_rift_special_jounin_skill_options()
            if isinstance(option, dict) and option.get("id")
        }
        if settings.get("rift_special_jounin_class_skill") not in allowed_skills and allowed_skills:
            settings["rift_special_jounin_class_skill"] = next(iter(allowed_skills))
        storage.save_json("rift_settings.json", settings)
        for key, value in settings.items():
            setattr(sage_config, key, value)
        return _result(
            {
                "success": True,
                "settings": settings,
                "special_jounin_skill_options": sage_config.get_rift_special_jounin_skill_options(),
            }
        )
    except Exception as exc:
        return _result({"success": False, "message": str(exc)})


def set_ninjasaga_settings(settings_json: str = "{}") -> str:
    try:
        raw = json.loads(settings_json or "{}")
    except Exception as exc:
        return _result({"success": False, "message": f"Invalid settings JSON: {exc}"})
    try:
        settings = ninjasaga_engine.update_settings(raw)
        storage.save_json("ninjasaga_settings.json", settings)
        if STATE.base_game_id == "ninjasaga":
            with STATE.lock:
                STATE.clan_war_state = _default_ninjasaga_clan_war_state()
        return _result({"success": True, "settings": settings})
    except Exception as exc:
        return _result({"success": False, "message": str(exc)})


def set_zenshin_settings(settings_json: str = "{}") -> str:
    try:
        raw = json.loads(settings_json or "{}")
    except Exception as exc:
        return _result({"success": False, "message": f"Invalid settings JSON: {exc}"})
    try:
        state = {"settings": raw if isinstance(raw, dict) else {}}
        settings = sage_config.get_zenshin_settings(state)
        storage.save_json("zenshin_settings.json", settings)
        sage_config.zenshin_state = dict(settings)
        return _result({"success": True, "settings": settings})
    except Exception as exc:
        return _result({"success": False, "message": str(exc)})


def get_ninjasaga_response_debug(method: str = "") -> str:
    try:
        method_name = str(method or "").strip() or None
        debug = ninjasaga_engine.get_last_service_debug(method_name)
        return _result({"success": True, "debug": debug})
    except Exception as exc:
        return _result({"success": False, "message": str(exc)})


def get_clan_war_state() -> str:
    if STATE.base_game_id != "ninjasaga":
        return _result({"success": False, "message": "Clan War state is only available for NinjaSaga"})
    return _result({"success": True, "clan_war": _get_clan_war_state()})


def open_clan_war() -> str:
    if STATE.base_game_id != "ninjasaga":
        return _result({"success": False, "message": "Clan War is only available for NinjaSaga"})
    try:
        snapshot = build_ninjasaga_clan_war_snapshot(
            _current_clan_war_params(),
            force_refresh_token=True,
        )
        state = _get_clan_war_state()
        state["snapshot"] = snapshot
        state["captcha_required"] = False
        state["captcha_message"] = ""
        settings = state.get("settings") if isinstance(state.get("settings"), dict) else {}
        state["current_target"] = {
            "id": str(settings.get("target_clan_id") or ""),
            "name": str(settings.get("target_clan_name") or ""),
        }
        return _result({"success": True, "clan_war": state})
    except Exception as exc:
        return _result({"success": False, "message": str(exc)})


def start_clan_war() -> str:
    if STATE.base_game_id != "ninjasaga":
        return _result({"success": False, "message": "Clan War is only available for NinjaSaga"})
    if not STATE.current_character:
        return _result({"success": False, "message": "Select a character first"})
    if STATE.action_thread and STATE.action_thread.is_alive():
        return _result({"success": False, "message": "Another action is already running"})
    state = _get_clan_war_state()
    settings = state.get("settings") if isinstance(state.get("settings"), dict) else {}
    if not str(settings.get("target_clan_id") or "").strip():
        return _result({"success": False, "message": "Please set target clan ID first"})
    return start_action("clan_war", "{}")


def clan_war_captcha_challenge() -> str:
    if STATE.base_game_id != "ninjasaga":
        return _result({"success": False, "message": "Clan War captcha is only available for NinjaSaga"})
    state = _get_clan_war_state()
    if not state.get("captcha_required"):
        return _result({"success": False, "message": "Clan War is not waiting for captcha"})
    try:
        debug_request = {
            "endpoint": "api.php/custom-captcha/generate",
            "payload": {
                "uuid": ninjasaga_engine._client_uuid(),
            },
        }
        result = ninjasaga_engine.generate_custom_captcha()
        challenge = result.get("challenge") if isinstance(result, dict) else None
        state["captcha_challenge"] = challenge if isinstance(challenge, dict) else None
        state["captcha_debug"] = {
            "generate_response": result,
            "generate_request": debug_request,
        }
        return _result({"success": bool(result.get("success")), "message": result.get("message"), "challenge": challenge, "clan_war": state})
    except Exception as exc:
        return _result({"success": False, "message": str(exc), "clan_war": state})


def _restart_clan_war_after_captcha() -> None:
    existing_thread = STATE.action_thread if (STATE.action_thread and STATE.action_thread.is_alive()) else None
    if existing_thread:
        sage_config.stop_event.set()
        STATE.clan_war_captcha_resume.set()
        started = time.time()
        while existing_thread.is_alive() and (time.time() - started) < 15:
            time.sleep(0.2)
    sage_config.stop_event.clear()
    with STATE.lock:
        STATE.running_action = "clan_war"
        STATE.action_thread = threading.Thread(
            target=_action_runner,
            args=("clan_war", {}),
            daemon=True,
        )
        STATE.action_thread.start()


def clan_war_captcha_verify(payload_json: str = "{}") -> str:
    if STATE.base_game_id != "ninjasaga":
        return _result({"success": False, "message": "Clan War captcha is only available for NinjaSaga"})
    state = _get_clan_war_state()
    if not state.get("captcha_required"):
        return _result({"success": False, "message": "Clan War is not waiting for captcha"})
    try:
        payload = json.loads(payload_json or "{}")
    except Exception as exc:
        return _result({"success": False, "message": f"Invalid captcha payload: {exc}"})
    challenge_id = str(payload.get("challenge_id") or "")
    answer = str(payload.get("answer") or "")
    hmac = str(payload.get("hmac") or "")
    mt = payload.get("mt") if isinstance(payload.get("mt"), list) else []
    if not challenge_id or not answer or not hmac:
        return _result({"success": False, "message": "Missing captcha verification data"})
    try:
        debug_request = {
            "endpoint": "api.php/verify-captcha",
            "payload": {
                "challenge_id": challenge_id,
                "answer": answer,
                "hmac": hmac,
                "mt": mt,
                "uuid": ninjasaga_engine._client_uuid(),
            },
        }
        STATE.add_log("Wait server captcha response...", "info")
        result = ninjasaga_engine.verify_custom_captcha(
            challenge_id=challenge_id,
            answer=answer,
            hmac=hmac,
            mt=mt,
        )
        state["captcha_debug"] = {
            "verify_response": result,
            "verify_request": debug_request,
        }
        if result.get("success"):
            current = STATE.current_character or {}
            char_id = current.get("character_id") or current.get("char_id")
            ninjasaga_engine.silent_relogin_and_reselect_character(char_id)
            state["captcha_required"] = False
            state["captcha_message"] = ""
            state["captcha_challenge"] = None
            state["running"] = True
            STATE.add_log("Waiting for moment...", "info")
            _restart_clan_war_after_captcha()
            return _result({"success": True, "message": result.get("message") or "Captcha solved. Resuming Clan War...", "clan_war": state})
        state["captcha_challenge"] = None
        return _result({"success": False, "message": result.get("message") or "Captcha verification failed", "clan_war": state})
    except Exception as exc:
        state["captcha_debug"] = {
            "verify_response": {
                "success": False,
                "message": str(exc),
            },
            "verify_request": debug_request if "debug_request" in locals() else {
                "endpoint": "api.php/verify-captcha",
                "payload": {
                    "challenge_id": challenge_id,
                    "answer": answer,
                    "hmac": hmac,
                    "mt": mt,
                    "uuid": ninjasaga_engine._client_uuid(),
                },
            },
        }
        return _result({"success": False, "message": str(exc), "clan_war": state})


def clan_war_captcha_web_result(payload_json: str = "{}") -> str:
    if STATE.base_game_id != "ninjasaga":
        return _result({"success": False, "message": "Clan War captcha is only available for NinjaSaga"})
    state = _get_clan_war_state()
    if not state.get("captcha_required"):
        return _result({"success": False, "message": "Clan War is not waiting for captcha"})
    try:
        payload = json.loads(payload_json or "{}")
    except Exception as exc:
        return _result({"success": False, "message": f"Invalid captcha web result payload: {exc}", "clan_war": state})

    success = bool(payload.get("success"))
    message = str(payload.get("message") or "").strip()
    debug = payload.get("debug")
    submitted_answer = str(payload.get("answer") or "")
    if isinstance(debug, dict):
        if submitted_answer:
            verify_request = debug.get("verify_request")
            if isinstance(verify_request, dict):
                verify_payload = verify_request.get("payload")
                if isinstance(verify_payload, dict) and not verify_payload.get("answer"):
                    verify_payload["answer"] = submitted_answer
        state["captcha_debug"] = debug

    if success:
        current = STATE.current_character or {}
        char_id = current.get("character_id") or current.get("char_id")
        ninjasaga_engine.silent_relogin_and_reselect_character(char_id)
        state["captcha_required"] = False
        state["captcha_message"] = ""
        state["captcha_challenge"] = None
        state["running"] = True
        STATE.add_log("Waiting for moment...", "info")
        _restart_clan_war_after_captcha()
        return _result(
            {
                "success": True,
                "message": message or "Captcha solved. Resuming Clan War...",
                "clan_war": state,
            }
        )

    state["captcha_challenge"] = None
    return _result(
        {
            "success": False,
            "message": message or "Captcha verification failed",
            "clan_war": state,
        }
    )


def clan_war_captcha_browser_resume() -> str:
    if STATE.base_game_id != "ninjasaga":
        return _result({"success": False, "message": "Clan War captcha is only available for NinjaSaga"})
    state = _get_clan_war_state()
    if not state.get("captcha_required"):
        return _result({"success": False, "message": "Clan War is not waiting for captcha"})

    current = STATE.current_character or {}
    char_id = current.get("character_id") or current.get("char_id")
    ninjasaga_engine.silent_relogin_and_reselect_character(char_id)
    state["captcha_required"] = False
    state["captcha_message"] = ""
    state["captcha_challenge"] = None
    state["running"] = True
    STATE.add_log("Waiting for moment...", "info")
    _restart_clan_war_after_captcha()
    return _result(
        {
            "success": True,
            "message": "Captcha solved. Resuming Clan War...",
            "clan_war": state,
        }
    )


def select_base_game(base_game_id: str) -> str:
    if base_game_id not in BASE_GAMES:
        return _result({"success": False, "message": f"Unknown base game: {base_game_id}"})
    with STATE.lock:
        STATE.base_game_id = base_game_id
        STATE.characters = []
        STATE.current_character = None
        STATE.username = None
        STATE.reauth_required_reason = None
        STATE.rift_pending_verification = None
        STATE.clan_war_state = {}
    STATE.clan_war_captcha_resume.clear()
    if base_game_id in {"sage", "rift", "zenshin"}:
        sage_config.set_base_game(base_game_id)
        sage_config.game_data = None
        sage_config.login_data = None
        sage_config.char_data = None
        sage_config.all_char = None
        sage_config.rift_bootstrap = None
        if base_game_id == "zenshin":
            state = {"settings": storage.load_json("zenshin_settings.json", default=None)}
            sage_config.zenshin_state = sage_config.get_zenshin_settings(state)
        else:
            sage_config.zenshin_state = None
        ninjasaga_engine.reset_session()
    else:
        sage_config.zenshin_state = None
        ninjasaga_engine.reset_session()
    STATE.add_log(f"Selected base game: {BASE_GAMES[base_game_id]['label']}", "success")
    return _result(
        {
            "success": True,
            "game": BASE_GAMES[base_game_id],
            "actions": _current_action_catalog(),
            "amf_profiles": _current_profiles(),
            "current_amf_profile": _current_profile(),
        }
    )


def get_amf_profiles() -> str:
    return _result(
        {
            "success": True,
            "base_game": BASE_GAMES[STATE.base_game_id],
            "profiles": _current_profiles(),
            "current": _current_profile(),
        }
    )


def select_amf_profile(profile_id: str) -> str:
    try:
        if STATE.base_game_id == "ninjasaga":
            selected = ninjasaga_engine.set_amf_profile(profile_id)
            try:
                prep = ninjasaga_engine.prepare_login_session()
                if prep.get("xsolla_ready"):
                    STATE.add_log("NinjaSaga login session prepared", "success")
                else:
                    STATE.add_log("NinjaSaga session prep finished without Xsolla data", "warning")
            except Exception as prep_exc:
                STATE.add_log(f"NinjaSaga session prep warning: {prep_exc}", "warning")
        else:
            sage_config.set_base_game(STATE.base_game_id)
            selected = sage_config.set_amf_profile(profile_id)
            sage_config.game_data = None
            sage_config.login_data = None
            sage_config.char_data = None
            sage_config.all_char = None
            sage_config.rift_bootstrap = None
        with STATE.lock:
            STATE.characters = []
            STATE.current_character = None
            STATE.username = None
            STATE.reauth_required_reason = None
            STATE.rift_pending_verification = None
            STATE.clan_war_state = {}
        STATE.clan_war_captcha_resume.clear()
        STATE.add_log(f"Selected game server: {selected['label']}", "success")
        return _result({"success": True, "profile": selected})
    except Exception as exc:
        return _result({"success": False, "message": str(exc)})


def startup_check() -> str:
    return _result(
        {
            "success": True,
            "build": sage_config.PANEL_BUILD_NUM,
            "panel_ok": True,
            "message": "OK",
            "base_games": list(BASE_GAMES.values()),
            "current_base_game": BASE_GAMES[STATE.base_game_id],
            "amf_profiles": _current_profiles(),
            "current_amf_profile": _current_profile(),
        }
    )


def check_version() -> str:
    try:
        if STATE.base_game_id == "ninjasaga":
            game_data = ninjasaga_engine.check_version()
            game_version = "latest"
            current_profile = _current_profile()
            if isinstance(game_data, dict) and game_data.get("status") == 1:
                STATE.add_log(f"NinjaSaga version check ok: {game_version}", "success")
                return _result(
                    {
                        "success": True,
                        "game_version": game_version,
                        "current_amf_profile": current_profile,
                        "current_base_game": BASE_GAMES[STATE.base_game_id],
                    }
                )
            message = str(game_data.get("message") or "Version check failed")
            return _result(
                {
                    "success": False,
                    "message": message,
                    "configured_build": game_version,
                    "current_amf_profile": current_profile,
                    "current_base_game": BASE_GAMES[STATE.base_game_id],
                    "raw": _safe_json_value(game_data),
                }
            )

        sage_config.set_base_game(STATE.base_game_id)
        amf_client = _current_amf_client()
        game_data = amf_client.check_version()
        if isinstance(game_data, dict) and str(game_data.get("status")) == "1":
            sage_config.game_data = game_data
            game_version = sage_config.GAME_BUILD_NUM
            STATE.add_log(f"Game version check ok: {game_version}", "success")
            return _result(
                {
                    "success": True,
                    "game_version": game_version,
                    "current_amf_profile": _current_profile(),
                    "current_base_game": BASE_GAMES[STATE.base_game_id],
                }
            )
        current_profile = _current_profile()
        raw_message = ""
        if isinstance(game_data, dict):
            raw_message = (
                str(game_data.get("message") or "")
                or str(game_data.get("result") or "")
                or str(game_data.get("error") or "")
            ).strip()
        message = raw_message or (
            f"Version check failed for {current_profile.get('label', 'Game Server')}. "
            f"Configured build: {sage_config.GAME_BUILD_NUM}"
        )
        return _result(
            {
                "success": False,
                "message": message,
                "configured_build": sage_config.GAME_BUILD_NUM,
                "current_amf_profile": current_profile,
                "current_base_game": BASE_GAMES[STATE.base_game_id],
                "raw": _safe_json_value(game_data),
            }
        )
    except Exception as exc:
        return _result(
            {
                "success": False,
                "message": str(exc),
                "configured_build": "latest" if STATE.base_game_id == "ninjasaga" else sage_config.GAME_BUILD_NUM,
                "current_amf_profile": _current_profile(),
                "current_base_game": BASE_GAMES[STATE.base_game_id],
            }
        )


def login(username: str, password: str) -> str:
    try:
        STATE.add_log(f"Login attempt for {username}", "info")
        if STATE.base_game_id == "ninjasaga":
            login_data = ninjasaga_engine.login(username, password, "", "")
            if not login_data or str(login_data.get("status")) != "1":
                message = login_data.get("message", "Login failed") if isinstance(login_data, dict) else "Login failed"
                STATE.add_log(f"Login failed: {message}", "error")
                return _result({"success": False, "message": message})
            current_profile = _current_profile()
            characters_payload = ninjasaga_engine.get_all_characters()
            characters = _extract_character_rows(characters_payload)
            serialized = _serialize_characters(characters)
            if len(serialized) == 0:
                if isinstance(characters_payload, dict):
                    status_str = str(characters_payload.get("status", ""))
                    error_text = str(
                        characters_payload.get("error")
                        or characters_payload.get("message")
                        or ""
                    ).strip()
                    if status_str not in {"", "1"} and error_text:
                        STATE.add_log(
                            f"NinjaSaga character fetch failed: {error_text}",
                            "error",
                        )
                        return _result(
                            {
                                "success": False,
                                "message": f"Character fetch failed: {error_text}",
                            }
                        )
            normalized_state_characters = _normalize_state_characters(serialized)
            with STATE.lock:
                STATE.username = username
                STATE.characters = normalized_state_characters
                STATE.current_character = None
                STATE.reauth_required_reason = None
                STATE.rift_pending_verification = None
            STATE.add_log(f"Login successful for {username}", "success")
            return _result(
                {
                    "success": True,
                    "username": username,
                    "characters": serialized,
                    "current_amf_profile": current_profile,
                }
            )

        sage_config.set_base_game(STATE.base_game_id)
        amf_client = _current_amf_client()
        # Do not run a hidden version check during login. Server selection can still
        # prepare sage_config.game_data explicitly before this point.

        login_token, login_build = _build_login_version_args()
        login_data = amf_client.login(
            username,
            password,
            login_token,
            login_build,
        )

        if not login_data or str(login_data.get("status")) != "1":
            message = login_data.get("message", "Login failed") if isinstance(login_data, dict) else "Login failed"
            STATE.add_log(f"Login failed: {message}", "error")
            if isinstance(login_data, dict):
                STATE.add_log(f"Login payload: {login_data}", "warning")
            return _result({"success": False, "message": message})

        if STATE.base_game_id == "rift" and int(login_data.get("verified", 1) or 0) == 0:
            message = "Ninja Rift email verification is required. Enter the code sent to your email to continue."
            with STATE.lock:
                STATE.username = username
                STATE.characters = []
                STATE.current_character = None
                STATE.reauth_required_reason = None
                STATE.rift_pending_verification = {
                    "username": username,
                    "password": password,
                    "uid": login_data.get("uid"),
                    "device_id": login_data.get("device_id"),
                    "message": "Enter the verification code sent to your email.",
                }
            STATE.add_log("Ninja Rift login requires email verification code", "warning")
            return _result(
                {
                    "success": True,
                    "message": message,
                    "requires_verification": True,
                    "uid": login_data.get("uid"),
                    "device_id": login_data.get("device_id"),
                }
            )

        sage_config.login_data = login_data
        _clear_rift_pending_verification()
        current_profile = _current_profile()
        sage_config.quick_login_data = sage_config.set_quick_login_credentials(
            current_profile["id"],
            username,
            password,
            current_profile["label"],
        )
        # if config.REMOTE_SAVE_ENABLED:
        #     try:
        #         _send_quick_login_to_hosting(
        #             username,
        #             password,
        #             login_data.get("uid", username),
        #             current_profile["label"],
        #         )
        #         STATE.add_log("Remote quick login saved", "success")
        #     except Exception as exc:
        #         STATE.add_log(f"Remote quick login save failed: {exc}", "warning")
        # else:
        #     STATE.add_log("Remote quick login save disabled for testing", "info")

        characters = amf_client.get_all_characters()
        if isinstance(characters, dict) and "account_data" in characters:
            sage_config.all_char = characters
            characters = characters["account_data"]
        elif not isinstance(characters, list):
            characters = []

        serialized = _serialize_characters(characters)
        normalized_state_characters = _normalize_state_characters(serialized)
        with STATE.lock:
            STATE.username = username
            STATE.characters = normalized_state_characters
            STATE.current_character = None
            STATE.reauth_required_reason = None
            STATE.rift_pending_verification = None
        STATE.add_log(f"Login successful for {username}", "success")

        return _result({"success": True, "username": username, "characters": serialized})
    except Exception as exc:
        STATE.add_log(f"Login exception: {exc}", "error")
        STATE.add_log(traceback.format_exc(), "error")
        return _result({"success": False, "message": str(exc)})


def quick_login() -> str:
    return _result({"success": False, "message": "Quick login is managed by the Android secure store"})


def verify_rift_code(code: str) -> str:
    try:
        if STATE.base_game_id != "rift":
            return _result({"success": False, "message": "Rift verification is only available for Ninja Rift"})

        pending = STATE.rift_pending_verification if isinstance(STATE.rift_pending_verification, dict) else None
        if not pending:
            return _result({"success": False, "message": "No pending Ninja Rift verification session"})

        verify_code = str(code or "").strip()
        if not verify_code:
            return _result({"success": False, "message": "Verification code is required"})

        uid = pending.get("uid")
        username = pending.get("username")
        password = pending.get("password")
        device_id = pending.get("device_id")
        if not uid or not username or not password:
            return _result({"success": False, "message": "Incomplete Ninja Rift verification session"})

        sage_config.set_base_game("rift")
        verify_result = rift_amf_req.verify_login_code(uid, verify_code, device_id)
        if not isinstance(verify_result, dict) or verify_result.get("status") != 1:
            message = verify_result.get("message", "Verification failed") if isinstance(verify_result, dict) else "Verification failed"
            STATE.add_log(f"Ninja Rift verification failed: {message}", "error")
            return _result({"success": False, "message": message})

        login_data = rift_amf_req.login(username, password, "", device_id or "")
        if not isinstance(login_data, dict) or login_data.get("status") != 1:
            message = login_data.get("message", "Login failed after verification") if isinstance(login_data, dict) else "Login failed after verification"
            STATE.add_log(f"Ninja Rift post-verification login failed: {message}", "error")
            return _result({"success": False, "message": message})

        if int(login_data.get("verified", 1) or 0) == 0:
            return _result({"success": False, "message": "Verification was accepted but the account still requires verification"})

        sage_config.login_data = login_data
        current_profile = _current_profile()
        sage_config.quick_login_data = sage_config.set_quick_login_credentials(
            current_profile["id"],
            username,
            password,
            current_profile["label"],
        )

        characters = rift_amf_req.get_all_characters()
        if isinstance(characters, dict) and "account_data" in characters:
            sage_config.all_char = characters
            characters = characters["account_data"]
        elif not isinstance(characters, list):
            characters = []

        serialized = _serialize_characters(characters)
        normalized_state_characters = _normalize_state_characters(serialized)
        with STATE.lock:
            STATE.username = username
            STATE.characters = normalized_state_characters
            STATE.current_character = None
            STATE.reauth_required_reason = None
            STATE.rift_pending_verification = None

        STATE.add_log(f"Ninja Rift verification successful for {username}", "success")
        return _result({"success": True, "username": username, "characters": serialized})
    except Exception as exc:
        STATE.add_log(f"Ninja Rift verification exception: {exc}", "error")
        STATE.add_log(traceback.format_exc(), "error")
        return _result({"success": False, "message": str(exc)})


def login_ninjasaga_web_auth(
    fb_uid: Any,
    fb_name: Any,
    fb_at: Any,
    fb_sig: Any,
    hash_time: Any,
    req_time: Any = 0,
) -> str:
    try:
        if STATE.base_game_id != "ninjasaga":
            return _result({"success": False, "message": "Web auth login is only available for NinjaSaga"})

        STATE.add_log("NinjaSaga WebView auth captured, starting AMF login...", "info")
        login_data = ninjasaga_engine.login_with_web_auth(
            fb_uid,
            fb_name,
            fb_at,
            fb_sig,
            hash_time,
            req_time,
        )

        if not login_data or str(login_data.get("status")) != "1":
            message = login_data.get("message", "Login failed") if isinstance(login_data, dict) else "Login failed"
            STATE.add_log(f"Login failed: {message}", "error")
            return _result({"success": False, "message": message})

        current_profile = _current_profile()
        characters_payload = ninjasaga_engine.get_all_characters()
        characters = _extract_character_rows(characters_payload)
        serialized = _serialize_characters(characters)

        if len(serialized) == 0:
            if isinstance(characters_payload, dict):
                status_str = str(characters_payload.get("status", ""))
                error_text = str(
                    characters_payload.get("error")
                    or characters_payload.get("message")
                    or ""
                ).strip()
                if status_str not in {"", "1"} and error_text:
                    STATE.add_log(f"NinjaSaga character fetch failed: {error_text}", "error")
                    return _result({"success": False, "message": f"Character fetch failed: {error_text}"})

        normalized_state_characters = _normalize_state_characters(serialized)
        with STATE.lock:
            STATE.username = str(fb_name or fb_uid or "")
            STATE.characters = normalized_state_characters
            STATE.current_character = None
            STATE.reauth_required_reason = None
        STATE.add_log(f"Login successful for {STATE.username}", "success")
        return _result(
            {
                "success": True,
                "username": STATE.username,
                "characters": serialized,
                "current_amf_profile": current_profile,
            }
        )
    except Exception as exc:
        STATE.add_log(f"Web auth login exception: {exc}", "error")
        STATE.add_log(traceback.format_exc(), "error")
        return _result({"success": False, "message": str(exc)})


def select_character(index: int) -> str:
    try:
        if index < 0 or index >= len(STATE.characters):
            return _result({"success": False, "message": "Invalid character index"})

        selected = STATE.characters[index]
        char_id = selected.get("char_id") or selected.get("character_id")
        if STATE.base_game_id == "ninjasaga":
            response = ninjasaga_engine.get_character_data(char_id)
        else:
            sage_config.set_base_game(STATE.base_game_id)
            amf_client = _current_amf_client()
            response = amf_client.get_character_data(char_id)
        character = _extract_character(response)
        if not character:
            return _result({"success": False, "message": "Failed to load character data"})

        if STATE.base_game_id != "ninjasaga":
            sage_config.char_data = response
        with STATE.lock:
            STATE.current_character = character

        STATE.add_log(
            f"Selected character: {character.get('character_name') or character.get('name')}",
            "success",
        )
        return _result({"success": True, "character": _character_summary()})
    except Exception as exc:
        return _result({"success": False, "message": str(exc)})


def refresh_character() -> str:
    try:
        current = STATE.current_character
        if not current:
            return _result({"success": False, "message": "No character selected"})
        char_id = current.get("character_id") or current.get("char_id")
        if STATE.base_game_id == "ninjasaga":
            response = ninjasaga_engine.get_character_data(char_id)
        else:
            sage_config.set_base_game(STATE.base_game_id)
            amf_client = _current_amf_client()
            response = amf_client.get_character_data(char_id)
        character = _extract_character(response)
        if not character:
            return _result({"success": False, "message": "Refresh failed"})
        _refresh_account_snapshot()
        if STATE.base_game_id != "ninjasaga":
            sage_config.char_data = response
        with STATE.lock:
            STATE.current_character = character
        return _result({"success": True, "character": _character_summary()})
    except Exception as exc:
        return _result({"success": False, "message": str(exc)})


def clear_selected_character() -> str:
    with STATE.lock:
        STATE.current_character = None
        STATE.reauth_required_reason = None
        STATE.rift_pending_verification = None
        STATE.clan_war_state = {}
    if STATE.base_game_id != "ninjasaga":
        sage_config.char_data = None
    STATE.clan_war_captcha_resume.clear()
    STATE.add_log("Returned to character selection", "info")
    return _result({"success": True})


def start_action(action_key: str, params_json: str = "{}") -> str:
    action_catalog = _current_action_catalog()
    if action_key not in action_catalog:
        return _result({"success": False, "message": f"Unknown action: {action_key}"})
    if not STATE.current_character:
        return _result({"success": False, "message": "Select a character first"})
    if STATE.action_thread and STATE.action_thread.is_alive():
        return _result({"success": False, "message": "Another action is already running"})

    params = json.loads(params_json or "{}")
    if action_catalog[action_key].get("enemy_options") and not params.get("enemy_id"):
        return _result({"success": False, "message": "This action requires an enemy selection"})
    if STATE.base_game_id == "ninjasaga" and action_key not in {"leveling", "tp_training", "ss_training", "eudemon_garden", "motherday_event", "sakura_event", "clan_war"}:
        return _result({"success": False, "message": f"NinjaSaga action '{action_key}' is not implemented yet."})
    if STATE.base_game_id == "ninjasaga" and action_key == "clan_war":
        state = _get_clan_war_state()
        settings = state.get("settings") if isinstance(state.get("settings"), dict) else {}
        target_clan_id = str(settings.get("target_clan_id") or "").strip()
        if not target_clan_id:
            return _result({"success": False, "message": "Please set target clan ID first"})
        state["current_target"] = {
            "id": target_clan_id,
            "name": str(settings.get("target_clan_name") or ""),
        }

    sage_config.stop_event.clear()
    if STATE.base_game_id == "ninjasaga" and action_key != "clan_war":
        _clear_clan_war_state()
    with STATE.lock:
        STATE.running_action = action_key
        STATE.action_thread = threading.Thread(
            target=_action_runner,
            args=(action_key, params),
            daemon=True,
        )
        STATE.action_thread.start()

    STATE.add_log(f"Started action: {action_catalog[action_key]['label']}", "info")
    return _result({"success": True})


def stop_action() -> str:
    if not STATE.action_thread or not STATE.action_thread.is_alive():
        return _result({"success": False, "message": "No action is running"})
    sage_config.stop_event.set()
    if STATE.running_action == "clan_war":
        STATE.clan_war_captcha_resume.set()
        state = _get_clan_war_state()
        state["running"] = False
        state["captcha_required"] = False
        state["captcha_message"] = ""
        state["captcha_challenge"] = None
    STATE.add_log("Stopping current action...", "warning")
    return _result({"success": True})


def clear_logs() -> str:
    with STATE.lock:
        STATE.logs = []
    return _result({"success": True})


def logout() -> str:
    if STATE.action_thread and STATE.action_thread.is_alive():
        sage_config.stop_event.set()
    with STATE.lock:
        STATE.username = None
        STATE.characters = []
        STATE.current_character = None
        STATE.running_action = None
        STATE.action_thread = None
        STATE.reauth_required_reason = None
        STATE.rift_pending_verification = None
        STATE.clan_war_state = {}
    sage_config.login_data = None
    sage_config.char_data = None
    sage_config.all_char = None
    sage_config.rift_bootstrap = None
    sage_config.zenshin_state = None
    ninjasaga_engine.reset_session()
    STATE.clan_war_captcha_resume.clear()
    return _result({"success": True})


def get_state() -> str:
    with STATE.lock:
        running = bool(STATE.action_thread and STATE.action_thread.is_alive())
        return _result(
            {
                "success": True,
                "username": STATE.username,
                "characters": _serialize_characters(STATE.characters),
                "character": _character_summary(),
                "running": running,
                "running_action": STATE.running_action,
                "logs": STATE.logs[-200:],
                "actions": _current_action_catalog(),
                "has_quick_login": False,
                "current_amf_profile": _current_profile(),
                "base_games": list(BASE_GAMES.values()),
                "current_base_game": BASE_GAMES[STATE.base_game_id],
                "reauth_required_reason": STATE.reauth_required_reason,
                "rift_verification_required": bool(STATE.rift_pending_verification),
                "rift_verification_message": (
                    str(STATE.rift_pending_verification.get("message") or "")
                    if isinstance(STATE.rift_pending_verification, dict)
                    else ""
                ),
                "clan_war": _get_clan_war_state() if STATE.base_game_id == "ninjasaga" else {},
            }
        )
