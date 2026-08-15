import random
import time
from typing import Any

from ..core import config
from . import amf_req
from .utils import CUCSG, flatten_json, save_fight_data, send_amf_request


RIFT_DEFAULT_SPECIAL_JOUNIN_SKILL = "skill_2002"


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(getattr(config, name, default))
    except Exception:
        return int(default)


def _cfg_text(name: str, default: str) -> str:
    value = getattr(config, name, default)
    text = str(value).strip()
    return text or default


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def get_rift_settings() -> dict:
    return config.get_rift_settings()


def check_stop_event() -> bool:
    if hasattr(config, "stop_event") and config.stop_event.is_set():
        print("Ninja Rift action stopped by user request")
        return True
    return False


def wait_with_stop(seconds: int) -> bool:
    for _ in range(max(0, int(seconds))):
        if check_stop_event():
            return False
        time.sleep(1)
    return True


def rift_delay(name: str, default: int) -> int:
    settings = get_rift_settings()
    try:
        return max(0, int(settings.get(name, default)))
    except Exception:
        return max(0, int(default))


def rift_random_wait(base_key: str, random_key: str, default_base: int, default_random: int) -> int:
    base_seconds = rift_delay(base_key, default_base)
    random_seconds = rift_delay(random_key, default_random)
    if random_seconds <= 0:
        return base_seconds
    return base_seconds + random.randint(0, random_seconds)


def rift_exam_wait(timer_range: tuple[int, int]) -> int:
    low, high = timer_range
    configured_min = rift_delay("rift_exam_wait_min_seconds", int(low))
    configured_max = rift_delay("rift_exam_wait_max_seconds", int(high))
    wait_min = max(0, min(int(low), configured_min))
    wait_max = max(wait_min, min(int(high), configured_max))
    return random.randint(wait_min, wait_max)


def get_character_snapshot() -> dict:
    if not isinstance(config.char_data, dict):
        raise ValueError("Character data is not loaded")

    snapshot = config.char_data.get("character_data", config.char_data)
    if not isinstance(snapshot, dict):
        raise ValueError("Character snapshot is missing")
    return snapshot


def get_char_id() -> Any:
    snapshot = get_character_snapshot()
    char_id = snapshot.get("character_id") or snapshot.get("char_id")
    if char_id in (None, ""):
        raise ValueError("Character ID is missing")
    return char_id


def get_session_key() -> str:
    if not isinstance(config.login_data, dict):
        raise ValueError("Login data is not loaded")
    session_key = str(config.login_data.get("sessionkey") or config.login_data.get("session_key") or "")
    if not session_key:
        raise ValueError("Session key is missing")
    return session_key


def get_level() -> int:
    snapshot = get_character_snapshot()
    return int(snapshot.get("character_level") or snapshot.get("level") or 0)


def get_rank() -> int:
    snapshot = get_character_snapshot()
    return int(snapshot.get("character_rank") or snapshot.get("rank") or 0)


def is_premium_user() -> bool:
    snapshot = get_character_snapshot()
    raw_type = (
        snapshot.get("account_type")
        or snapshot.get("character_account_type")
        or snapshot.get("premium")
        or snapshot.get("is_premium")
        or (config.login_data or {}).get("account_type")
        or (config.login_data or {}).get("premium")
    )
    if isinstance(raw_type, str):
        return raw_type.strip().lower() in {"premium", "vip", "2", "true"}
    try:
        return int(raw_type) == 2
    except Exception:
        return False


def get_village_type() -> str:
    snapshot = get_character_snapshot()
    village_id = snapshot.get("character_village_id") or snapshot.get("village_id") or 0
    try:
        village_id = int(village_id)
    except Exception:
        village_id = 0
    if village_id == 3:
        return "lightning"
    return "fire"


def get_agility() -> int:
    flattened = flatten_json(config.char_data)
    return int(amf_req.calculate_agility(flattened))


def update_runtime_character_stats(*, level: int | None = None, xp: int | None = None, gold: int | None = None):
    if not isinstance(config.char_data, dict):
        return

    snapshot = config.char_data.get("character_data", config.char_data)
    if not isinstance(snapshot, dict):
        return

    if level is not None:
        snapshot["character_level"] = level
        snapshot["level"] = level
    if xp is not None:
        snapshot["character_xp"] = xp
        snapshot["xp"] = xp
    if gold is not None:
        snapshot["character_gold"] = gold
        snapshot["gold"] = gold

    if callable(getattr(config, "character_update_callback", None)):
        config.character_update_callback(
            {
                "level": snapshot.get("character_level") or snapshot.get("level"),
                "xp": snapshot.get("character_xp") or snapshot.get("xp"),
                "gold": snapshot.get("character_gold") or snapshot.get("gold"),
            }
        )


def current_gold() -> int:
    snapshot = get_character_snapshot()
    return int(snapshot.get("character_gold") or snapshot.get("gold") or 0)


def current_xp() -> int:
    snapshot = get_character_snapshot()
    return int(snapshot.get("character_xp") or snapshot.get("xp") or 0)


def response_message(response) -> str:
    if response is None:
        return "No response"
    if isinstance(response, dict):
        return str(response.get("result") or response.get("error") or response.get("message") or response)
    for attr in ("description", "message", "details", "faultString"):
        value = getattr(response, attr, None)
        if value:
            return str(value)
    return str(response)


def _notify_rift_reauth_required(reason: str):
    callback = getattr(config, "session_reauth_required_callback", None)
    if callable(callback):
        try:
            callback(reason)
        except Exception:
            pass


def _rift_relogin_wait_seconds() -> int:
    return max(0, rift_delay("rift_auto_relogin_wait_seconds", 15))


def _current_char_id_for_relogin():
    try:
        return get_char_id()
    except Exception:
        return None


def _looks_like_rift_session_problem(result) -> bool:
    if result is None:
        return False
    message = response_message(result).strip().lower()
    if not message:
        return False
    session_markers = (
        "invalid session",
        "session expired",
        "session key",
        "session is invalid",
        "not logged in",
        "please login",
        "please log in",
        "login required",
        "auth failed",
        "login again",
        "re-login",
        "relogin",
        "disconnected",
        "connection lost",
    )
    return any(marker in message for marker in session_markers)


def _looks_like_rift_transport_problem(exc: Exception) -> bool:
    message = str(exc).strip().lower()
    if not message:
        return False
    markers = (
        "connection aborted",
        "connection reset",
        "connection refused",
        "connection broken",
        "connection pool",
        "remote disconnected",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "name or service not known",
        "failed to establish a new connection",
        "network is unreachable",
        "internet",
    )
    return any(marker in message for marker in markers)


def _rift_retry_delay_seconds(attempt: int) -> int:
    base_wait = _rift_relogin_wait_seconds()
    if attempt <= 1:
        return base_wait
    return base_wait + ((attempt - 1) * 5)


def _rift_relogin_and_reselect_character(*, attempt: int = 1) -> bool:
    profile_id = config.get_current_amf_profile().get("id")
    credentials, _ = config.get_quick_login_credentials(profile_id)
    if not credentials:
        print("No quick login data found for Ninja Rift. Cannot auto relogin.")
        return False

    username = credentials.get("username")
    password = credentials.get("password")
    if not username or not password:
        print("Invalid quick login credentials for Ninja Rift auto relogin.")
        return False

    char_id = _current_char_id_for_relogin()
    wait_seconds = _rift_retry_delay_seconds(attempt)
    if wait_seconds > 0:
        print(f"Ninja Rift session problem detected. Waiting {wait_seconds} seconds before auto relogin...")
        if not wait_with_stop(wait_seconds):
            return False

    try:
        config.game_data = None
        config.rift_bootstrap = None
        version_result = amf_req.check_version()
        if not isinstance(version_result, dict) or version_result.get("status") != 1:
            print(f"Ninja Rift version check failed during auto relogin: {response_message(version_result)}")
            return False

        login_result = amf_req.login(username, password, "", "")
        if not isinstance(login_result, dict) or login_result.get("status") != 1:
            print(f"Ninja Rift auto relogin failed: {response_message(login_result)}")
            return False
        if _as_int(login_result.get("verified", 1), 1) == 0:
            print("Ninja Rift auto relogin requires verification code. Sending user back to login.")
            _notify_rift_reauth_required("Ninja Rift verification is required again. Please log in and enter the code.")
            return False

        config.login_data = login_result
        try:
            all_characters = amf_req.get_all_characters()
            if isinstance(all_characters, dict):
                config.all_char = all_characters
        except Exception as exc:
            print(f"Ninja Rift auto relogin character list refresh warning: {exc}")
        if char_id not in (None, ""):
            refreshed_char = amf_req.get_character_data(char_id)
            if isinstance(refreshed_char, dict):
                config.char_data = refreshed_char
        print("Ninja Rift auto relogin successful.")
        return True
    except Exception as exc:
        print(f"Ninja Rift auto relogin error: {exc}")
        return False


def send_rift_request(service: str, params: list[Any], *, _allow_recovery: bool = True, _attempt: int = 1):
    if check_stop_event():
        return None
    min_delay = rift_delay("rift_min_call_delay_seconds", 2)
    if min_delay > 0:
        if not wait_with_stop(min_delay):
            return None
    try:
        result = send_amf_request(service, params)
    except Exception as exc:
        if not _allow_recovery or not _looks_like_rift_transport_problem(exc):
            raise
        print(f"Ninja Rift request failed on {service}: {exc}")
        if _attempt < 3 and _rift_relogin_and_reselect_character(attempt=_attempt):
            print(f"Retrying Ninja Rift request after auto relogin: {service}")
            return send_rift_request(service, params, _allow_recovery=True, _attempt=_attempt + 1)
        raise

    if _allow_recovery and _looks_like_rift_session_problem(result):
        print(f"Ninja Rift session error on {service}: {response_message(result)}")
        if _attempt < 3 and _rift_relogin_and_reselect_character(attempt=_attempt):
            print(f"Retrying Ninja Rift request after session recovery: {service}")
            return send_rift_request(service, params, _allow_recovery=True, _attempt=_attempt + 1)
        _notify_rift_reauth_required("Ninja Rift session expired and auto relogin could not recover it.")
    return result


def mission_damage(enemy_ids: list[str], enemy_stats: list[dict]) -> int:
    total_hp = 0
    for enemy_id, enemy_data in zip(enemy_ids, enemy_stats):
        hp = enemy_data.get("enemy_hp") or enemy_data.get("hp") or 0
        try:
            total_hp += int(hp)
        except Exception:
            continue

    if total_hp <= 0:
        return 0

    upper = max(total_hp, int(total_hp * 1.2))
    return random.randint(total_hp, upper)


def finish_mission(mission_id: str, battle_code: str, damage: int):
    char_id = get_char_id()
    session_key = get_session_key()
    finish_hash = CUCSG.hash(f"{mission_id}{char_id}{battle_code}{damage}")
    result = send_rift_request(
        "BattleSystem.finishMission",
        [char_id, mission_id, battle_code, finish_hash, damage, session_key],
    )
    if result is not None:
        save_fight_data(result)
    return result


def finish_eudemon(boss_num: int, battle_code: str):
    char_id = get_char_id()
    session_key = get_session_key()
    finish_hash = CUCSG.hash(f"{boss_num}{char_id}{battle_code}")
    result = send_rift_request(
        "EudemonGarden.finishHunting",
        [char_id, boss_num, battle_code, finish_hash, session_key],
    )
    if result is not None:
        save_fight_data(result)
    return result


def finish_hunting_house(boss_num: int, battle_code: str):
    char_id = get_char_id()
    session_key = get_session_key()
    finish_hash = CUCSG.hash(f"{boss_num}{char_id}{battle_code}")
    result = send_rift_request(
        "HuntingHouse.finishHunting",
        [char_id, boss_num, battle_code, finish_hash, session_key],
    )
    if result is not None:
        save_fight_data(result)
    return result


def enemy_name(enemy_id: str, fallback: str | None = None) -> str:
    enemy = amf_req.get_enemy_library().get(str(enemy_id)) or {}
    name = enemy.get("enemy_name") or enemy.get("name") or fallback or str(enemy_id)
    return str(name)
