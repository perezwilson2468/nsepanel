from .. import config
from .utils import (
    apply_shinobi_response_state,
    get_device_id,
    get_shinobi_state,
    post_base64_json,
    post_encrypted_json,
)


SHINOBI_VERSION_INT = 1070


def _get_nested(data, *path):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _auth_payload(include_auth: bool = True) -> dict:
    state = get_shinobi_state()
    payload = {
        "user_key": state.get("user_key"),
    }
    if include_auth:
        payload["auth"] = get_device_id()
    return {key: value for key, value in payload.items() if value is not None}


def _character_request_payload(extra: dict | None = None, include_auth: bool = True) -> dict:
    payload = _auth_payload(include_auth=include_auth)
    if extra:
        payload.update(extra)
    return {key: value for key, value in payload.items() if value is not None}


def _extract_character_list(response: dict):
    if not isinstance(response, dict):
        return []

    candidates = [
        response.get("characters"),
        _get_nested(response, "payload", "characters"),
        _get_nested(response, "data", "characters"),
        _get_nested(response, "result", "characters"),
        response.get("players"),
        _get_nested(response, "payload", "players"),
        _get_nested(response, "data", "players"),
        _get_nested(response, "result", "players"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate

    return []


def _normalize_character_list(characters):
    normalized = []
    for index, char in enumerate(characters or []):
        if not isinstance(char, dict):
            continue
        char_id = (
            char.get("id")
            or char.get("player_id")
            or char.get("character_id")
            or char.get("char_id")
        )
        char_name = (
            char.get("name")
            or char.get("character_name")
            or char.get("player_name")
            or f"Character {index + 1}"
        )
        char_level = (
            char.get("level")
            or char.get("character_level")
            or char.get("player_level")
            or 0
        )
        normalized.append(
            {
                "char_id": char_id,
                "character_id": char_id,
                "character_name": char_name,
                "name": char_name,
                "character_level": char_level,
                "level": char_level,
                "status": char.get("status", 0),
                "gender": char.get("gender", 0),
                "namecolor": char.get("namecolor", 0),
                "index": index,
                "raw": char,
            }
        )
    return normalized


def _normalize_user_data(response: dict) -> dict:
    user_data = {}
    candidates = [
        response.get("user_data"),
        _get_nested(response, "payload", "user_data"),
        _get_nested(response, "data", "user_data"),
        _get_nested(response, "result", "user_data"),
        response.get("character_data"),
        _get_nested(response, "payload", "character_data"),
        _get_nested(response, "data", "character_data"),
        _get_nested(response, "result", "character_data"),
        response.get("player_data"),
        _get_nested(response, "payload", "player_data"),
        _get_nested(response, "data", "player_data"),
        _get_nested(response, "result", "player_data"),
        response if isinstance(response, dict) and (
            response.get("name") is not None
            or response.get("level") is not None
            or response.get("gold") is not None
            or response.get("xp") is not None
        ) else None,
    ]

    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            user_data = candidate
            break

    xp_value = user_data.get("xp", 0)
    max_xp_value = user_data.get("max_xp", 0)
    if isinstance(xp_value, (list, tuple)):
        if xp_value:
            max_xp_value = xp_value[1] if len(xp_value) > 1 else max_xp_value
            xp_value = xp_value[0]
        else:
            xp_value = 0

    return {
        "character_id": user_data.get("id") or user_data.get("char_id") or user_data.get("character_id"),
        "char_id": user_data.get("id") or user_data.get("char_id") or user_data.get("character_id"),
        "character_name": user_data.get("name", "Unknown"),
        "name": user_data.get("name", "Unknown"),
        "character_level": user_data.get("level", 0),
        "level": user_data.get("level", 0),
        "character_xp": xp_value,
        "xp": xp_value,
        "character_max_xp": max_xp_value,
        "max_xp": max_xp_value,
        "character_gold": user_data.get("gold", 0),
        "gold": user_data.get("gold", 0),
        "character_credit": user_data.get("credit", 0),
        "credit": user_data.get("credit", 0),
        "character_gems": user_data.get("gem", user_data.get("gems", 0)),
        "gems": user_data.get("gem", user_data.get("gems", 0)),
        "character_tp": user_data.get("talent_points", 0),
        "tp": user_data.get("talent_points", 0),
        "character_rank": user_data.get("status", 0),
        "rank": user_data.get("status", 0),
        "tokens": user_data.get("token", 0),
        "premium": user_data.get("premium"),
        "equipped": user_data.get("equipped", {}),
        "inventory": user_data.get("inventory", {}),
        "equipped_skills": _get_nested(user_data, "equipped", "skills"),
        "equipped_talent": _get_nested(user_data, "equipped", "talent"),
        "inventory_skills": _get_nested(user_data, "inventory", "skills"),
        "raw_user_data": user_data,
    }


def check_version():
    state = get_shinobi_state()
    state["server_url"] = config.get_current_amf_profile()["gateway"]

    initialize_result = post_base64_json(
        "system/process_initialize.php",
        {},
        access_token=get_device_id(),
    )
    apply_shinobi_response_state(initialize_result)

    access_token = initialize_result.get("access_token") or state.get("access_token")
    if access_token:
        state["access_token"] = access_token

    system_data_result = post_base64_json(
        "system/process_load_system_data.php",
        {},
        access_token=state.get("access_token"),
    )
    apply_shinobi_response_state(system_data_result)

    result = {
        "status": 1,
        "_": SHINOBI_VERSION_INT,
        "__": "",
        "version_string": config.BUILD_NUM,
        "initialize": initialize_result,
        "system_data": system_data_result,
    }
    config.game_data = result
    return result


def login(username, password, *_args):
    state = get_shinobi_state()
    if not state.get("access_token"):
        check_version()

    response = post_encrypted_json(
        "process_login.php",
        {
            "username": username,
            "password": password,
            "version": SHINOBI_VERSION_INT,
            # XTRA sends null here and only adopts payload.jwt after login succeeds.
            "user_key": None,
            "auth": get_device_id(),
        },
        access_token=state.get("access_token"),
    )
    apply_shinobi_response_state(response)

    connected = bool(response.get("connection", {}).get("connected"))
    result = {
        "status": 1 if connected else 0,
        "uid": username,
        "sessionkey": state.get("user_key"),
        "user_key": state.get("user_key"),
        "access_token": state.get("access_token"),
        "server_url": state.get("server_url"),
        "private_key": state.get("private_key"),
        "constant_key": state.get("constant_key"),
        "salt": state.get("salt"),
        "raw": response,
    }
    config.login_data = result
    return result


def get_all_characters():
    state = get_shinobi_state()
    response = post_encrypted_json(
        "process_load_characters.php",
        _character_request_payload(),
        access_token=state.get("access_token"),
    )
    apply_shinobi_response_state(response)
    raw_characters = _extract_character_list(response)
    normalized = _normalize_character_list(raw_characters)
    premium = (
        response.get("premium")
        if isinstance(response, dict)
        else None
    )
    if premium is None:
        premium = _get_nested(response, "payload", "premium")
    if premium is None:
        premium = _get_nested(response, "data", "premium")
    result = {
        "status": response.get("status", 1),
        "total_characters": len(normalized),
        "characters": normalized,
        "account_data": normalized,
        "premium": premium,
        "tokens": 0,
        "raw": response,
    }
    config.all_char = result
    return result


def get_character_data(char_id, select_first=True):
    state = get_shinobi_state()
    if char_id and select_first:
        select_response = post_encrypted_json(
            "process_select_character.php",
            _character_request_payload({"player_id": char_id}),
            access_token=state.get("access_token"),
        )
        apply_shinobi_response_state(select_response)
        if not isinstance(select_response, dict) or select_response.get("status", 1) != 1:
            return {
                "status": select_response.get("status", 0) if isinstance(select_response, dict) else 0,
                "error": select_response.get("error", "Character select failed") if isinstance(select_response, dict) else str(select_response),
                "raw": select_response,
            }

    response = post_encrypted_json(
        "process_load_character.php",
        _character_request_payload(),
        access_token=state.get("access_token"),
    )
    apply_shinobi_response_state(response)
    if not isinstance(response, dict) or response.get("status", 1) != 1:
        return {
            "status": response.get("status", 0) if isinstance(response, dict) else 0,
            "error": response.get("error", "Character load failed") if isinstance(response, dict) else str(response),
            "raw": response,
        }
    character_data = _normalize_user_data(response)
    if char_id and not character_data.get("character_id"):
        character_data["character_id"] = char_id
        character_data["char_id"] = char_id
    result = {
        "status": response.get("status", 1),
        "character_data": character_data,
        "system_data": response.get("system_data"),
        "raw": response,
    }
    config.char_data = result
    return result
