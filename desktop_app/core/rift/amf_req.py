import uuid
from typing import Any

from .. import config
from ..shared.utils import fetch_json_url
from .utils import StatManager, flatten_json, send_amf_request


RIFT_METHODS = {
    "checkVersion": "SystemLogin.checkVersion",
    "loginUser": "SystemLogin.loginUser",
    "verifyCode": "Account.verifyCode",
    "getAllCharacters": "SystemLogin.getAllCharacters",
    "getCharacterData": "SystemLogin.getCharacterData",
    "verifyFiles": "AC.verifyFiles",
    "checkClearCache": "FilesManager.checkClearCache",
    "setCacheCleared": "FilesManager.setCacheCleared",
}

_LIBRARY_CACHE: dict[str, Any] = {}


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def fetch_bootstrap(force: bool = False):
    if not force and isinstance(getattr(config, "rift_bootstrap", None), dict):
        return config.rift_bootstrap

    current_profile = config.get_current_amf_profile()
    bootstrap = {
        "server": current_profile.get("gateway"),
        "version": current_profile.get("build_num"),
        "amf": dict(RIFT_METHODS),
    }
    config.rift_bootstrap = bootstrap
    config.set_runtime_connection(
        current_profile.get("gateway"),
        current_profile.get("build_num"),
    )
    return bootstrap


def _rift_amf_method(name: str) -> str:
    method = RIFT_METHODS.get(name)
    if not method:
        raise ValueError(f"Ninja Rift AMF method missing for {name}")
    return method


def load_library_json(filename: str, force: bool = False):
    cache_key = filename.lower()
    if not force and cache_key in _LIBRARY_CACHE:
        return _LIBRARY_CACHE[cache_key]

    current_base_game = config.get_current_base_game()
    library_url = current_base_game.get("library_url")
    if not library_url:
        raise ValueError("Ninja Rift library URL is not configured")

    if not library_url.endswith("/"):
        library_url += "/"

    data = fetch_json_url(f"{library_url}{filename}", timeout=15)

    _LIBRARY_CACHE[cache_key] = data
    return data


def get_talent_skill_verification_hash(force: bool = False) -> str:
    payload = load_library_json("talentSkillLevel", force=force)
    enc_data = payload.get("enc_data")
    if isinstance(enc_data, dict):
        verification_hash = enc_data.get("encryptedData")
        if verification_hash:
            return str(verification_hash)

    for value in payload.values():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "iv" in item and item.get("encryptedData"):
                    return str(item["encryptedData"])

    raise ValueError("Could not find Ninja Rift talent verification hash")


def calculate_agility(flattened_character: dict) -> int:
    return StatManager.calculate_stats_with_data("agility", flattened_character)


def _normalize_characters_payload(result):
    if not isinstance(result, dict):
        return result

    if isinstance(result.get("account_data"), list):
        result.setdefault("characters", result["account_data"])
        return result

    if isinstance(result.get("characters"), list):
        result.setdefault("account_data", result["characters"])
        return result

    if isinstance(result.get("data"), list):
        result["account_data"] = result["data"]
        result["characters"] = result["data"]
        result.setdefault("total_characters", len(result["data"]))
        return result

    return result


def check_version():
    bootstrap = fetch_bootstrap()
    version = bootstrap.get("version") or config.BUILD_NUM
    result = send_amf_request(_rift_amf_method("checkVersion"), [version])

    if not isinstance(result, dict):
        result = {
            "status": 0,
            "error": result,
            "_": version,
            "__": "",
            "rift_bootstrap": bootstrap,
        }
    else:
        result.setdefault("_", version)
        result.setdefault("__", "")
        result.setdefault("rift_bootstrap", bootstrap)

    config.game_data = result
    return result


def _verify_login_session(result: dict):
    session_key = result.get("sessionkey") or result.get("session_key")
    account_id = result.get("uid") or result.get("account_id") or result.get("user_id")

    if not session_key:
        return result

    verification_hash = get_talent_skill_verification_hash()
    verify_result = send_amf_request(
        _rift_amf_method("verifyFiles"),
        [session_key, verification_hash],
    )
    result["verify_files_result"] = verify_result
    result["talent_hash"] = verification_hash

    if not account_id:
        return result

    cache_check_result = send_amf_request(
        _rift_amf_method("checkClearCache"),
        [account_id],
    )
    result["check_clear_cache_result"] = cache_check_result

    if isinstance(cache_check_result, list) and cache_check_result:
        cache_cleared_result = send_amf_request(
            _rift_amf_method("setCacheCleared"),
            [account_id, cache_check_result],
        )
        result["set_cache_cleared_result"] = cache_cleared_result

    return result


def login(username, password, *args):
    fetch_bootstrap()
    method = _rift_amf_method("loginUser")
    provided_device_id = ""
    if args:
        candidate = args[-1]
        if candidate is not None:
            provided_device_id = str(candidate).strip()
    device_id = provided_device_id or f"NR_{uuid.uuid4().hex[:17]}"
    result = send_amf_request(method, [username, password, device_id])

    if isinstance(result, dict) and result.get("status") != 1:
        fallback_result = send_amf_request(method, [username, password])
        if isinstance(fallback_result, dict) and fallback_result.get("status") == 1:
            result = fallback_result
            device_id = ""

    if not isinstance(result, dict):
        return result

    result.setdefault("device_id", device_id)
    if result.get("status") != 1:
        return result

    if _as_int(result.get("verified", 1), 1) == 0:
        result["error"] = result.get("error") or "Account verification is required"
        return result

    return _verify_login_session(result)


def verify_login_code(uid, code: str, device_id: str | None = None):
    params = ["login", uid, code]
    if device_id:
        params.append(device_id)
    return send_amf_request(_rift_amf_method("verifyCode"), params)


def get_all_characters():
    method = _rift_amf_method("getAllCharacters")
    account_id = (
        config.login_data.get("uid")
        or config.login_data.get("account_id")
        or config.login_data.get("user_id")
    )
    session_key = config.login_data.get("sessionkey") or config.login_data.get("session_key")
    result = send_amf_request(method, [account_id, session_key])
    result = _normalize_characters_payload(result)
    config.all_char = result
    return result


def get_character_data(char_id):
    method = _rift_amf_method("getCharacterData")
    session_key = config.login_data.get("sessionkey") or config.login_data.get("session_key")
    result = send_amf_request(method, [char_id, session_key])
    if isinstance(result, dict):
        if isinstance(result.get("character_data"), dict):
            result["character_data"].setdefault("character_id", char_id)
        else:
            result.setdefault("character_id", char_id)
    config.char_data = result
    return result


def get_mission_library(force: bool = False):
    payload = load_library_json("missionLibrary", force=force)
    mission_map: dict[str, dict] = {}
    for value in payload.values():
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                item_id = item.get("item_id")
                effects = item.get("effects")
                if item_id and isinstance(effects, dict):
                    mission_map[str(item_id)] = effects
    return mission_map


def get_mission_librarry(force: bool = False):
    return get_mission_library(force=force)


def get_enemy_library(force: bool = False):
    payload = load_library_json("enemyInfo", force=force)
    enemy_map: dict[str, dict] = {}
    for value in payload.values():
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                item_id = item.get("item_id")
                effects = item.get("effects")
                if item_id and isinstance(effects, dict):
                    enemy_map[str(item_id)] = effects
    return enemy_map


def get_enemy_librarry(force: bool = False):
    return get_enemy_library(force=force)


def get_character_level_and_rank() -> tuple[int, int]:
    if not isinstance(config.char_data, dict):
        return 0, 0
    snapshot = config.char_data.get("character_data", config.char_data)
    if not isinstance(snapshot, dict):
        return 0, 0
    level = int(snapshot.get("character_level") or snapshot.get("level") or 0)
    rank = int(snapshot.get("character_rank") or snapshot.get("rank") or 0)
    return level, rank


def current_character_flattened() -> dict:
    if not isinstance(config.char_data, dict):
        return {}
    return flatten_json(config.char_data)
