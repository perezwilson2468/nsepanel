from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from typing import Any

from Crypto.Cipher import AES

from .. import config
from ..zenshin import amf_req as zenshin_amf_req
from ..zenshin import mission as zenshin_mission
import pyamf
import requests
from pyamf import remoting

from ..shared.utils import send_amf_request

logger = logging.getLogger(__name__)


def _is_zenshin_profile() -> bool:
    return config.get_current_base_game().get("id") == "zenshin"


CHECK_VERSION_METHODS = (
    "SystemService.checkVersion",
    "SystemLogin.checkVersion",
)
LOGIN_METHOD = "SystemService.login"
REQUIRE_LOGIN_METHOD = "SystemService.requireLogin"
SNS_LOGIN_METHOD = "SystemService.snsLogin"
GET_CHARACTERS_METHOD = "CharacterDAO.getCharactersList"
GET_CHARACTER_METHOD = "CharacterDAO.getCharacterById"
GET_EXTRA_DATA_METHOD = "CharacterDAO.getExtraData"
GET_SYSTEM_DATA_METHOD = "SystemData.get"
CHECK_AMF_METHOD = "SystemService.checkAmf"
START_MISSION_METHOD = "CharacterService.startMission"
WATCH_SJE_NOTICE_METHOD = "CharacterDAO.watchSJENotice"
START_SJ_EXAM_METHOD = "CharacterService.startSJExam"
NT_EXAM_NOTICE_METHOD = "CharacterDAO.NTExamNotice"
START_NT_EXAM_METHOD = "CharacterService.startNTExam"
UPDATE_CHARACTER_METHOD = "CharacterService.updateCharacter"
GET_HUNTING_STATUS_METHOD = "EudemonGarden.getHuntingStatus"
START_HUNTING_METHOD = "EudemonGarden.startHunting"
FINISH_HUNTING_METHOD = "EudemonGarden.finishHunting"
BUY_HUNTING_TIME_METHOD = "EudemonGarden.buyHuntingTime"
EASTER_GET_BATTLE_STATUS_METHOD = "EasterFestival2015.getBattleStatus"
EASTER_START_BATTLE_METHOD = "EasterFestival2015.startBattle"
EASTER_OPEN_TREASURE_METHOD = "EasterFestival2015.openTreasure"
EASTER_GENERATE_NEW_MAP_METHOD = "EasterFestival2015.generateNewMap"
EASTER_BUY_BATTLE_HEART_METHOD = "EasterFestival2015.buyBattleHeart"
EASTER_RECORD_POSITION_METHOD = "EasterFestival2015.recordNowPostion"
ITEM_GET_BOSS_REWARD_METHOD = "ItemDAO.getBossReward"
CHARACTER_BUY_ITEM_METHOD = "CharacterDAO.buyItem"
MOTHERDAY_GET_SPECIAL_BATTLE_STATUS_METHOD = "MothersDay2016.getSpecialBattleStatus"
SAKURA_GET_STATUS_METHOD = "SakuraEvent.getAnniChallengeStatus"
SAKURA_BUY_PETAL_METHOD = "SakuraEvent.buyPetal"
SAKURA_REFILL_ENERGY_METHOD = "SakuraEvent.refillChallengeEnergy"
SJ_CLASS_SELECT_METHOD = "CharacterDAO.SJClassSelect"
NT_CLASS_SELECT_METHOD = "CharacterDAO.NTClassSelect"

# Extracted from NinjaSaga code library/linkage/CodeLibrary.as
NINJASAGA_CODEC = "85224034668"

# Extracted from client_library.swf string table (ClientLibrary class)
CLIENT_LIBRARY_SALT = "Vmn34aAciYK00Hen26nT01"
NINJASAGA_DEFAULT_CLS = "434106"
WEB_ORIGIN = "https://ninjasaga.cc"
WEB_API_ORIGIN = "https://api.ninjasaga.cc"
WEB_LOGIN_ENDPOINT = f"{WEB_API_ORIGIN}/login"
WEB_REFERER = "https://ninjasaga.cc/emulator.html"
WEB_HOME = "https://ninjasaga.cc/"
WEB_AIR_SHELL_URL = "https://ninjasaga.cc/?minimal&air&noreauth=1"
WEB_CUSTOM_CAPTCHA_GENERATE_ENDPOINT = f"{WEB_API_ORIGIN}/custom-captcha/generate"
WEB_CUSTOM_CAPTCHA_VERIFY_ENDPOINT = f"{WEB_API_ORIGIN}/verify-captcha"
WEB_LOGIN_ENDPOINTS = (
    WEB_LOGIN_ENDPOINT,
    "https://ninjasaga.cc/api.php/login",
    "https://ninjasaga.cc/api.php?action=login",
    "https://ninjasaga.cc/api.php?route=login",
    "https://ninjasaga.cc/api.php",
)

_PRIMARY_CONFIG = [75, 126, 53, 58, 71, 116, 50, 91, 46, 44, 115, 36]
_STREAM_IDENTIFIER = [61, 64, 56, 54, 87, 117, 116]
_ASSET_LOADER_DATA = [73, 110, 61, 90, 98, 68, 93, 79, 125, 89, 70, 104, 38, 103, 94, 89, 107, 118]

_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")
_SESSION_TOKEN_RE = re.compile(r"sid_ns_[A-Za-z0-9_]+")

_SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "signature",
    "fb_sig",
    "fb_at",
    "sessionkey",
    "session_key",
    "session",
}


def _derive_zendamf_key() -> bytes:
    # Mirrors NinjaSaga `ZendAMFClient` key schedule in ActionScript.
    key_seed = (
        "".join(chr(v) for v in _PRIMARY_CONFIG)
        + "".join(chr(v) for v in _ASSET_LOADER_DATA)
        + "".join(chr(v) for v in reversed(_STREAM_IDENTIFIER))
    )
    return key_seed.encode("ascii")[:16]


_ZENDAMF_AES_KEY = _derive_zendamf_key()


def _ensure_ninjasaga_state() -> dict:
    state = getattr(config, "ninjasaga_state", None)
    if not isinstance(state, dict):
        state = {}
        config.ninjasaga_state = state
    state.setdefault("codec", NINJASAGA_CODEC)
    state.setdefault("client_uuid", str(uuid.uuid4()))
    state.setdefault("cls", NINJASAGA_DEFAULT_CLS)
    return state


def _sha1_hex(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _encrypt_client_value(value: str) -> str:
    # ClientLibrary.encrypt(...) hashes with an internal salt suffix.
    return _sha1_hex(f"{value}{CLIENT_LIBRARY_SALT}")


def generate_hash(seed: str, payload: str) -> str:
    # Based on captured packets (e.g. CharacterService.startMission), the
    # ClientLibrary hash order is payload + SALT + seed.
    return _sha1_hex(f"{payload}{CLIENT_LIBRARY_SALT}{seed}")


def get_login_hash(challenge: str, source: str) -> str:
    return generate_hash(challenge, source)


def get_hash(session_key: str, payload: str | None) -> str:
    return generate_hash(session_key or "", payload or "")


def get_array_hash(session_key: str, values: list[Any]) -> str:
    serialized = ",".join("" if v is None else str(v) for v in values)
    return get_hash(session_key, serialized)


def _next_sequence_hash() -> str:
    next_value = _next_sequence_value()
    return get_hash(_session_key(), next_value)


def _next_sequence_value() -> str:
    config.CLASSIC_REQUEST_SEQ = int(getattr(config, "CLASSIC_REQUEST_SEQ", 0)) + 1
    return str(config.CLASSIC_REQUEST_SEQ)


def _next_sequence_state() -> tuple[int, str, str]:
    next_value = _next_sequence_value()
    return int(getattr(config, "CLASSIC_REQUEST_SEQ", 0) or 0), next_value, get_hash(_session_key(), next_value)


def _is_encrypted_hex_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) < 32 or len(value) % 32 != 0:
        return False
    return _HEX_RE.fullmatch(value) is not None


def _aes_decrypt_hex(hex_ciphertext: str) -> str | None:
    try:
        data = bytes.fromhex(hex_ciphertext)
        cipher = AES.new(_ZENDAMF_AES_KEY, AES.MODE_ECB)
        decrypted = cipher.decrypt(data)
        null_index = decrypted.find(b"\x00")
        if null_index >= 0:
            decrypted = decrypted[:null_index]
        return decrypted.decode("latin-1")
    except Exception:
        return None


def _sanitize_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    cleaned = _CONTROL_CHARS_RE.sub("", value)
    return cleaned.strip()


def _sanitize_structure(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_structure(item) for item in value]
    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for key, item in value.items():
            sanitized[_sanitize_text(key)] = _sanitize_structure(item)
        return sanitized
    return value


def _is_debug_enabled() -> bool:
    return bool(getattr(config, "ninjasaga_debug", False))


def _mask_secret(value: Any) -> str:
    raw = str(value or "")
    if len(raw) <= 8:
        return "***"
    return f"{raw[:4]}...{raw[-4:]}"


def _redact_string(value: str) -> str:
    masked = _SESSION_TOKEN_RE.sub(lambda m: _mask_secret(m.group(0)), value)
    if len(masked) > 260:
        return f"{masked[:200]}...(truncated {len(masked) - 200} chars)"
    return masked


def _redact_for_debug(value: Any, key_hint: str | None = None) -> Any:
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            redacted[key_str] = _redact_for_debug(item, key_str.lower())
        return redacted
    if isinstance(value, list):
        return [_redact_for_debug(item, key_hint) for item in value]
    if isinstance(value, str):
        if key_hint in _SENSITIVE_KEYS:
            return _mask_secret(value)
        return _redact_string(value)
    return value


def _debug_log(event: str, payload: Any) -> None:
    if not _is_debug_enabled():
        return
    try:
        safe_payload = _redact_for_debug(payload)
        message = f"[NinjaSaga debug] {event} | {json.dumps(safe_payload, ensure_ascii=True, default=str)}"
        logger.info(message)
        # Print so action-run stdout redirect can stream this to the Web UI console.
        print(message)
        state = _ensure_ninjasaga_state()
        events = state.setdefault("debug_events", [])
        if isinstance(events, list):
            events.append(message)
            if len(events) > 200:
                del events[:-200]
    except Exception:
        fallback_message = f"[NinjaSaga debug] {event} | <unserializable>"
        logger.info(fallback_message)
        print(fallback_message)


def _decrypt_value_and_restore_type(hex_ciphertext: str) -> Any:
    decrypted_text = _aes_decrypt_hex(hex_ciphertext)
    if decrypted_text is None:
        return "[DECRYPTION_FAILED]"
    decrypted_text = _sanitize_text(decrypted_text)
    try:
        return _sanitize_structure(json.loads(decrypted_text))
    except Exception:
        return decrypted_text


def _decrypt_amf_response(value: Any) -> Any:
    if isinstance(value, str):
        if _is_encrypted_hex_string(value):
            return _decrypt_value_and_restore_type(value)
        return _sanitize_text(value)

    if isinstance(value, list):
        return [_decrypt_amf_response(item) for item in value]

    if isinstance(value, dict):
        decrypted: dict[str, Any] = {}
        for key, item_value in value.items():
            key_name = _sanitize_text(key)
            if _is_encrypted_hex_string(key):
                decrypted_key = _aes_decrypt_hex(key)
                if decrypted_key:
                    key_name = _sanitize_text(decrypted_key)
            decrypted[key_name] = _decrypt_amf_response(item_value)
        if not decrypted:
            return []
        return decrypted

    return value


def _ninjasaga_http_session() -> requests.Session:
    state = _ensure_ninjasaga_state()
    session = state.get("http_session")
    if isinstance(session, requests.Session):
        return session
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
        }
    )
    state["http_session"] = session
    return session


def _post_amf_ninjasaga(service: str, params: list[Any]) -> Any:
    state = _ensure_ninjasaga_state()
    session = _ninjasaga_http_session()
    prepared = list(params) if isinstance(params, list) else [params]

    # NinjaSaga gateway expects plain positional AMF args, not nested array args.
    req = remoting.Request(service, prepared)
    env = remoting.Envelope(pyamf.AMF3)
    env["/0"] = req
    payload = remoting.encode(env).getvalue()

    headers = {
        "Content-Type": "application/x-amf",
        "Origin": WEB_ORIGIN,
        "Referer": state.get("emulator_referer", WEB_REFERER),
    }
    gateway = config.GATEWAY
    resp = session.post(gateway, data=payload, headers=headers, timeout=25)

    content_type = (resp.headers.get("Content-Type") or "").lower()
    body_prefix = resp.content[:120]
    if resp.status_code >= 400 or "text/html" in content_type or body_prefix.lstrip().startswith(b"<!DOCTYPE html"):
        raise ValueError(
            f"AMF gateway returned HTTP {resp.status_code} with content-type {content_type or 'unknown'}"
        )

    try:
        resp_env = remoting.decode(resp.content)
    except Exception as exc:
        raise ValueError(f"Failed to decode NinjaSaga AMF response: {exc}") from exc

    _, message = resp_env.bodies[0]
    return message.body


def _looks_like_fault(obj: Any) -> bool:
    if obj is None:
        return False
    cls_name = obj.__class__.__name__.lower()
    return "fault" in cls_name or "errorfault" in cls_name


def _fault_to_text(fault_obj: Any) -> str:
    parts = []
    for attr in ("level", "code", "description", "faultString", "details", "message"):
        value = getattr(fault_obj, attr, None)
        if value:
            parts.append(f"{attr}={value}")
    if not parts:
        return str(fault_obj)
    return ", ".join(parts)


def _web_login_payload(username: str, password: str) -> dict[str, Any]:
    state = _ensure_ninjasaga_state()
    return {
        "username": username,
        "password": password,
        "minimal": "0",
        "air": "0",
        "w": "1920",
        "h": "1080",
        "tz": "Asia/Makassar",
        "cpu": "12",
        "ram": "8",
        "browser_ver": "Chrome 146",
        "uuid": state.get("client_uuid"),
        "gpu": "ANGLE (AMD, AMD Radeon Graphics, D3D11)",
    }


def _warmup_web_session(session: requests.Session):
    # Prime cookies/csrf/session similarly to browser flow before hitting api.php.
    warmup_headers = {
        "Origin": WEB_ORIGIN,
        "Referer": WEB_HOME,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        session.get(WEB_HOME, headers=warmup_headers, timeout=25)
    except Exception:
        pass
    try:
        session.get(f"{WEB_ORIGIN}/emulator.html", headers=warmup_headers, timeout=25)
    except Exception:
        pass


def sync_air_shell_after_captcha() -> dict[str, Any]:
    state = _ensure_ninjasaga_state()
    session = _ninjasaga_http_session()
    headers = {
        "Origin": WEB_ORIGIN,
        "Referer": WEB_HOME,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    results: list[dict[str, Any]] = []
    for idx in range(2):
        resp = session.get(WEB_AIR_SHELL_URL, headers=headers, timeout=25)
        result = {
            "step": idx + 1,
            "status_code": resp.status_code,
            "url": resp.url,
            "content_type": (resp.headers.get("Content-Type") or "").lower(),
            "body_preview": _safe_body_snippet(resp),
        }
        results.append(result)
    state["last_air_shell_sync"] = results
    _debug_log("air_shell.sync", results)
    return {"success": True, "results": results}


def _safe_body_snippet(resp: requests.Response, limit: int = 220) -> str:
    try:
        text = resp.text or ""
    except Exception:
        text = ""
    text = " ".join(text.split())
    return text[:limit]


def _web_login(username: str, password: str) -> dict[str, Any]:
    state = _ensure_ninjasaga_state()
    session = _ninjasaga_http_session()
    _warmup_web_session(session)

    payload = _web_login_payload(username, password)
    _debug_log("web_login.request_payload", payload)

    attempts = []
    for endpoint in WEB_LOGIN_ENDPOINTS:
        attempts.append(
            (
                endpoint,
                {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "Origin": WEB_ORIGIN,
                    "Referer": WEB_HOME,
                    "X-Requested-With": "XMLHttpRequest",
                },
                {"json": payload},
            )
        )
        attempts.append(
            (
                endpoint,
                {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json, text/plain, */*",
                    "Origin": WEB_ORIGIN,
                    "Referer": WEB_HOME,
                    "X-Requested-With": "XMLHttpRequest",
                },
                {"data": payload},
            )
        )

    last_error = None
    for endpoint, headers, kwargs in attempts:
        try:
            resp = session.post(endpoint, headers=headers, timeout=25, **kwargs)
        except Exception as exc:
            last_error = f"NinjaSaga web login request failed on {endpoint}: {exc}"
            _debug_log(
                "web_login.attempt_error",
                {
                    "endpoint": endpoint,
                    "error": str(exc),
                },
            )
            continue
        content_type = (resp.headers.get("Content-Type") or "").lower()
        body_preview = _safe_body_snippet(resp)
        _debug_log(
            "web_login.attempt_result",
            {
                "endpoint": endpoint,
                "status_code": resp.status_code,
                "content_type": content_type,
                "body_preview": body_preview,
            },
        )

        if resp.status_code >= 400:
            last_error = (
                f"NinjaSaga web login failed on {endpoint} with HTTP {resp.status_code} "
                f"(content-type {content_type or 'unknown'}) body: {body_preview}"
            )
            continue

        if "application/json" not in content_type and not body_preview.startswith("{"):
            last_error = (
                f"NinjaSaga web login returned non-JSON response on {endpoint} "
                f"({content_type or 'unknown'}) "
                f"body: {body_preview}"
            )
            continue

        try:
            result = resp.json()
        except Exception:
            last_error = (
                f"NinjaSaga web login JSON parse failed on {endpoint} "
                f"(content-type {content_type or 'unknown'}) "
                f"body: {body_preview}"
            )
            continue

        if not isinstance(result, dict) or not result.get("success"):
            last_error = f"NinjaSaga web login rejected credentials/request on {endpoint}: {result}"
            continue

        state["web_login_endpoint"] = endpoint
        break
    else:
        raise ValueError(last_error or "NinjaSaga web login failed for unknown reason")

    state["web_login"] = result
    state["web_auth_token"] = str(result.get("token") or "")
    _debug_log("web_login.success", result)
    player_id = str(result.get("player_id") or "")
    fb_at = str(result.get("token") or "")
    fb_sig = str(result.get("signature") or "")
    hash_time = str(result.get("hash_time") or "")
    emulator_referer = (
        f"{WEB_REFERER}?fb_uid={player_id}&fb_name={result.get('username','')}"
        f"&fb_at={fb_at}&fb_sig={fb_sig}&time=0&hash_time={hash_time}"
    )
    state["emulator_referer"] = emulator_referer
    return result


def _web_api_headers() -> dict[str, str]:
    state = _ensure_ninjasaga_state()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": WEB_ORIGIN,
        "Referer": WEB_HOME,
        "X-Requested-With": "XMLHttpRequest",
    }
    auth_token = str(state.get("web_auth_token") or "")
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


def _web_api_call(endpoint: str, payload: dict[str, Any], username: str = "", password: str = "") -> dict[str, Any]:
    state = _ensure_ninjasaga_state()
    session = _ninjasaga_http_session()

    if username and password:
        _web_login(username, password)
    else:
        _warmup_web_session(session)

    request_payload = dict(payload or {})
    request_payload.setdefault("uuid", state.get("client_uuid"))
    headers = _web_api_headers()
    _debug_log("web_api.request", {"endpoint": endpoint, "payload": request_payload})
    resp = session.post(endpoint, json=request_payload, headers=headers, timeout=30)
    content_type = (resp.headers.get("Content-Type") or "").lower()
    body_preview = _safe_body_snippet(resp)

    try:
        result = resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"NinjaSaga web API JSON parse failed on {endpoint} "
            f"(status={resp.status_code} content-type={content_type or 'unknown'}) body: {body_preview}"
        ) from exc

    if resp.status_code >= 400:
        raise RuntimeError(
            f"NinjaSaga web API failed on {endpoint} "
            f"(status={resp.status_code}) message: {result.get('message') or body_preview}"
        )

    if not isinstance(result, dict):
        raise RuntimeError(f"NinjaSaga web API returned unexpected payload on {endpoint}: {result}")
    return result


def generate_custom_captcha(username: str = "", password: str = "") -> dict[str, Any]:
    return _web_api_call(
        WEB_CUSTOM_CAPTCHA_GENERATE_ENDPOINT,
        {},
        username=username,
        password=password,
    )


def verify_custom_captcha(
    challenge_id: str,
    answer: str,
    hmac: str,
    mt: list[str] | None = None,
    username: str = "",
    password: str = "",
) -> dict[str, Any]:
    return _web_api_call(
        WEB_CUSTOM_CAPTCHA_VERIFY_ENDPOINT,
        {
            "challenge_id": str(challenge_id or ""),
            "answer": str(answer or ""),
            "hmac": str(hmac or ""),
            "mt": list(mt or []),
        },
        username=username,
        password=password,
    )


def _call_service(method: str, args: list[Any]) -> Any:
    _debug_log("amf.request", {"method": method, "args": args})
    if _is_zenshin_profile():
        referer = ""
        if isinstance(getattr(config, "login_data", None), dict):
            referer = str(config.login_data.get("frame_url") or "")
        response = zenshin_amf_req._send_zenshin_amf(method, args, referer)
        _debug_log("amf.transport_zenshin", {"method": method, "referer": referer})
        _debug_log("amf.response.raw", {"method": method, "response": response})
        return response
    try:
        response = _post_amf_ninjasaga(method, args)
    except Exception:
        # Keep shared transport as fallback for private servers that behave differently.
        response = send_amf_request(method, args)
        _debug_log("amf.transport_fallback", {"method": method})
    _debug_log("amf.response.raw", {"method": method, "response": response})
    decrypted = _decrypt_amf_response(response)
    _debug_log("amf.response.decrypted", {"method": method, "response": decrypted})
    return decrypted


def _session_key() -> str:
    if not isinstance(getattr(config, "login_data", None), dict):
        return ""

    login_data = config.login_data
    value = (
        login_data.get("sessionkey")
        or login_data.get("session_key")
        or login_data.get("session")
    )
    if value:
        return str(value)

    result = login_data.get("result")
    if isinstance(result, (list, tuple)) and len(result) > 3:
        return str(result[3] or "")
    return ""


def _normalize_login_payload(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    if isinstance(result, (list, tuple)):
        if len(result) > 0 and response.get("uid") is None:
            response["uid"] = result[0]
        if len(result) > 1 and response.get("account_type") is None:
            response["account_type"] = result[1]
        if len(result) > 2 and response.get("account_balance") is None:
            response["account_balance"] = result[2]
        if len(result) > 3 and response.get("sessionkey") is None:
            response["sessionkey"] = result[3]
    return response


def _normalize_character_entry(item: Any, index: int = 0) -> dict[str, Any]:
    if isinstance(item, (list, tuple)):
        char_id = item[0] if len(item) > 0 else None
        char_name = item[1] if len(item) > 1 and item[1] is not None else f"Character {index + 1}"
        char_level = item[2] if len(item) > 2 and item[2] is not None else 0
        return {
            "character_id": char_id,
            "char_id": char_id,
            "character_name": str(char_name),
            "name": str(char_name),
            "character_level": char_level,
            "level": char_level,
            "raw": list(item),
        }

    if not isinstance(item, dict):
        return {
            "character_id": item,
            "char_id": item,
            "character_name": f"Character {index + 1}",
            "name": f"Character {index + 1}",
            "character_level": 0,
            "level": 0,
        }

    char_id = item.get("character_id") or item.get("char_id") or item.get("id")
    if isinstance(char_id, (list, tuple)):
        char_id = char_id[0] if char_id else None
    char_name = item.get("character_name") or item.get("name") or f"Character {index + 1}"
    char_level = item.get("character_level") or item.get("level") or 0
    normalized = dict(item)
    normalized.setdefault("character_id", char_id)
    normalized.setdefault("char_id", char_id)
    normalized.setdefault("character_name", char_name)
    normalized.setdefault("name", char_name)
    normalized.setdefault("character_level", char_level)
    normalized.setdefault("level", char_level)
    return normalized


def _normalize_characters_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        rows = result.get("account_data")
        if not isinstance(rows, list):
            rows = result.get("characters")
        if not isinstance(rows, list):
            rows = result.get("result") if isinstance(result.get("result"), list) else []
        normalized = [_normalize_character_entry(row, idx) for idx, row in enumerate(rows or [])]
        result.setdefault("account_data", normalized)
        result.setdefault("characters", normalized)
        return result

    if isinstance(result, list):
        normalized = [_normalize_character_entry(row, idx) for idx, row in enumerate(result)]
        return {"account_data": normalized, "characters": normalized, "status": 1}

    return {"account_data": [], "characters": [], "status": 0, "error": result}


def check_version():
    if _is_zenshin_profile():
        return zenshin_amf_req.check_version()
    state = _ensure_ninjasaga_state()
    for method in CHECK_VERSION_METHODS:
        try:
            result = _call_service(method, [config.BUILD_NUM])
        except Exception:
            continue
        if isinstance(result, dict):
            result.setdefault("_", config.BUILD_NUM)
            result.setdefault("__", "")
            result.setdefault("codec", NINJASAGA_CODEC)
            if "status" not in result:
                result["status"] = 1
            config.game_data = result
            state["build_num"] = result.get("_", config.BUILD_NUM)
            return result

    result = {
        "status": 1,
        "_": config.BUILD_NUM,
        "__": "",
        "codec": NINJASAGA_CODEC,
        "warning": "NinjaSaga checkVersion endpoint/codec is not fully mapped yet.",
    }
    config.game_data = result
    state["build_num"] = config.BUILD_NUM
    return result


def _run_post_login_bootstrap(login_data: dict[str, Any]) -> None:
    state = _ensure_ninjasaga_state()
    session_key = (
        login_data.get("sessionkey")
        or login_data.get("session_key")
        or login_data.get("session")
    )
    if session_key:
        state["session_key"] = str(session_key)

    # checkAmf in official flow: [build_no, cls, hash(cls), session_key]
    # Capture shows cls around "434106" for official web flow.
    cls = str(state.get("cls") or NINJASAGA_DEFAULT_CLS)
    cls_hash = get_hash(str(session_key or ""), cls)
    state["cls_hash"] = cls_hash
    state["salt"] = CLIENT_LIBRARY_SALT

    try:
        check_amf_result = _call_service(
            CHECK_AMF_METHOD,
            [config.BUILD_NUM, cls, cls_hash, str(session_key or "")],
        )
        state["check_amf_result"] = check_amf_result
        _debug_log(
            "check_amf.completed",
            {"build_no": config.BUILD_NUM, "cls": cls, "cls_hash": cls_hash, "result": check_amf_result},
        )
    except Exception as exc:
        state["check_amf_error"] = str(exc)
        _debug_log("check_amf.error", {"error": str(exc)})


def login(username, password, *_args):
    if _is_zenshin_profile():
        return zenshin_amf_req.login(username, password, *_args)
    state = _ensure_ninjasaga_state()
    web_auth = _web_login(username, password)

    fb_uid = str(web_auth.get("player_id") or "")
    fb_at = str(web_auth.get("token") or "")
    fb_sig = str(web_auth.get("signature") or "")
    hash_time = str(web_auth.get("hash_time") or "")
    app_type = "facebook"
    lang = str((web_auth.get("session") or {}).get("language") or "en")
    build_no = str(config.BUILD_NUM)
    req_time = 0
    fb_uid_arg: Any = int(fb_uid) if fb_uid.isdigit() else fb_uid

    state["access_token"] = fb_at
    state["fb_uid"] = fb_uid
    state["fb_sig"] = fb_sig
    state["hash_time"] = hash_time
    state["app_type"] = app_type
    state["lang"] = lang

    require_login_args = [req_time, hash_time, fb_uid_arg]
    require_login = _call_service(REQUIRE_LOGIN_METHOD, require_login_args)
    if _looks_like_fault(require_login):
        raise ValueError(f"NinjaSaga requireLogin fault: {_fault_to_text(require_login)}")
    if not isinstance(require_login, dict) or str(require_login.get("status")) != "1":
        raise ValueError(f"NinjaSaga requireLogin failed: {require_login}")

    challenge = str(require_login.get("result") or require_login.get("challenge") or "")
    login_source = f"{challenge}{fb_uid}{app_type}{build_no}{state.get('codec', NINJASAGA_CODEC)}"
    login_hash = get_login_hash(challenge, login_source)
    _debug_log(
        "login.require_login",
        {"args": require_login_args, "response": require_login, "challenge": challenge, "login_hash": login_hash},
    )

    result = _call_service(
        SNS_LOGIN_METHOD,
        [fb_uid_arg, app_type, build_no, challenge, login_hash, fb_sig, fb_at, lang],
    )
    _debug_log("login.sns_login_result", result)
    if _looks_like_fault(result):
        raise ValueError(f"NinjaSaga snsLogin fault: {_fault_to_text(result)}")
    if isinstance(result, dict):
        result = _normalize_login_payload(result)
        if "status" not in result:
            result["status"] = 1
        if str(result.get("status")) == "1":
            result.setdefault("uid", fb_uid)
            result.setdefault("access_token", fb_at)
            result.setdefault("fb_sig", fb_sig)
            _run_post_login_bootstrap(result)
    return result


def get_all_characters():
    if _is_zenshin_profile():
        normalized = _normalize_characters_payload(zenshin_amf_req.get_all_characters())
        config.all_char = normalized
        return normalized
    session_key = _session_key()
    result = _call_service(GET_CHARACTERS_METHOD, [session_key])
    normalized = _normalize_characters_payload(result)
    config.all_char = normalized
    return normalized


def get_system_data(test_version: bool = False):
    session_key = _session_key()
    return _call_service(GET_SYSTEM_DATA_METHOD, [session_key, bool(test_version)])


def get_extra_data(char_id: Any):
    session_key = _session_key()
    state = _ensure_ninjasaga_state()
    access_token = state.get("access_token") or ""
    try:
        return _call_service(GET_EXTRA_DATA_METHOD, [session_key, char_id, access_token])
    except Exception:
        return _call_service(GET_EXTRA_DATA_METHOD, [session_key, char_id])


def get_character_data(char_id, include_system_data: bool = True, include_extra_data: bool = True):
    if _is_zenshin_profile():
        payload = zenshin_amf_req.get_character_data(char_id)
        if include_system_data:
            try:
                payload["system_data"] = get_system_data(False)
            except Exception as exc:
                payload["system_data_error"] = str(exc)
        if include_extra_data:
            try:
                payload["extra_data"] = get_extra_data(char_id)
            except Exception as exc:
                payload["extra_data_error"] = str(exc)
        config.char_data = payload
        return payload
    session_key = _session_key()
    normalized_char_id = char_id
    if isinstance(normalized_char_id, (list, tuple)):
        normalized_char_id = normalized_char_id[0] if normalized_char_id else None

    # Client path is [session_key, char_id], keep fallback for compatibility.
    try:
        result = _call_service(GET_CHARACTER_METHOD, [session_key, normalized_char_id])
    except Exception:
        result = _call_service(GET_CHARACTER_METHOD, [normalized_char_id, session_key])

    payload: dict[str, Any]
    if isinstance(result, dict):
        payload = dict(result)
        if not (payload.get("character_name") or payload.get("name")) and isinstance(payload.get("result"), (list, tuple)):
            merged = _normalize_character_entry(payload.get("result"), 0)
            merged.update(payload)
            payload = merged
    elif isinstance(result, (list, tuple)):
        payload = _normalize_character_entry(result, 0)
        payload["status"] = 1
        payload["result"] = list(result)
    else:
        payload = {"status": 0, "error": result}

    if include_system_data:
        try:
            payload["system_data"] = get_system_data(False)
        except Exception as exc:
            payload["system_data_error"] = str(exc)

    if include_extra_data:
        try:
            payload["extra_data"] = get_extra_data(normalized_char_id)
        except Exception as exc:
            payload["extra_data_error"] = str(exc)

    config.char_data = payload
    return payload


def start_mission(mission_id: str):
    if _is_zenshin_profile():
        return zenshin_mission.start_mission(mission_id)
    session_key = _session_key()
    normalized_mission_id = str(mission_id or "").strip().lower()
    if not normalized_mission_id:
        raise ValueError("Mission ID is required for CharacterService.startMission")
    mission_hash = get_hash(session_key, normalized_mission_id)
    _debug_log(
        "mission.start.request",
        {
            "session_key": session_key,
            "mission_id": normalized_mission_id,
            "mission_hash": mission_hash,
        },
    )
    response = _call_service(
        START_MISSION_METHOD,
        [session_key, normalized_mission_id, mission_hash],
    )
    state = _ensure_ninjasaga_state()
    if isinstance(response, dict):
        start_battle_id = response.get("startBattleId") or response.get("start_battle_id")
        if start_battle_id is not None:
            state["start_battle_id"] = str(start_battle_id)
    return response


def start_special_jounin_exam():
    session_key = _session_key()
    response = _call_service(START_SJ_EXAM_METHOD, [session_key])
    return response if isinstance(response, dict) else {"status": 0, "result": response}


def watch_special_jounin_notice():
    session_key = _session_key()
    response = _call_service(WATCH_SJE_NOTICE_METHOD, [session_key])
    return response if isinstance(response, dict) else {"status": 0, "result": response}


def get_tutor_exam_notice():
    session_key = _session_key()
    response = _call_service(NT_EXAM_NOTICE_METHOD, [session_key])
    return response if isinstance(response, dict) else {"status": 0, "result": response}


def start_tutor_exam():
    session_key = _session_key()
    response = _call_service(START_NT_EXAM_METHOD, [session_key])
    return response if isinstance(response, dict) else {"status": 0, "result": response}


def select_tutor_class():
    session_key = _session_key()
    response = _call_service(NT_CLASS_SELECT_METHOD, [session_key])
    return response if isinstance(response, dict) else {"status": 0, "result": response}


def get_ss_training_mission_status():
    session_key = _session_key()
    response = _call_service("SSTraining.getMissionStatus", [session_key])
    return response if isinstance(response, dict) else {"status": 0, "result": response}


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
):
    if _is_zenshin_profile():
        return zenshin_mission.update_character_progress(
            char_id=char_id,
            char_level=char_level,
            mission_id=mission_id,
            xp_gain=xp_gain,
            gold_gain=gold_gain,
            item_used=item_used,
            pet_id=pet_id,
            pet_level=pet_level,
            datafile_hack=datafile_hack,
        )
    session_key = _session_key()
    state = _ensure_ninjasaga_state()
    normalized_items = item_used if isinstance(item_used, list) else []
    xp_value = int(xp_gain or 0)
    gold_value = int(gold_gain or 0)
    sequence_hash = _next_sequence_hash()

    array_hash = get_array_hash(
        session_key,
        [
            session_key,
            char_id,
            char_level,
            xp_value,
            gold_value,
            normalized_items,
            pet_id,
            pet_level,
            mission_id,
            0,
            datafile_hack,
        ],
    )

    battle_flow_logver = str(state.get("battle_flow_logver") or "1")
    start_battle_id = str(state.get("start_battle_id") or "1")
    battle_log = {"battles": []}
    battle_log_json = json.dumps(battle_log, separators=(",", ":"))
    battle_log_hash = get_hash(session_key, f"{battle_flow_logver}{start_battle_id}{battle_log_json}")

    args = [
        session_key,
        char_id,
        char_level,
        xp_value,
        gold_value,
        normalized_items,
        pet_id,
        pet_level,
        mission_id,
        array_hash,
        sequence_hash,
        0,
        datafile_hack,
        battle_flow_logver,
        start_battle_id,
        battle_log_json,
        battle_log_hash,
    ]
    return _call_service(UPDATE_CHARACTER_METHOD, args)


def get_hunting_status():
    session_key = _session_key()
    return _call_service(GET_HUNTING_STATUS_METHOD, [session_key])


def start_hunting(room_index: int, enemy_ids: list[Any] | None = None):
    session_key = _session_key()
    room_value = int(room_index)
    payload = str(room_value)
    normalized_enemy_ids = []
    if isinstance(enemy_ids, list):
        for enemy_id in enemy_ids:
            value = str(enemy_id or "").strip()
            if value:
                normalized_enemy_ids.append(value)
    if normalized_enemy_ids:
        payload = f"{payload}{','.join(normalized_enemy_ids)}"
    request_hash = get_hash(session_key, payload)
    result = _call_service(START_HUNTING_METHOD, [session_key, room_value, request_hash])
    state = _ensure_ninjasaga_state()
    if isinstance(result, dict):
        start_battle_id = result.get("startBattleId") or result.get("start_battle_id") or result.get("code")
        if start_battle_id is not None:
            state["start_battle_id"] = str(start_battle_id)
    return result


def finish_hunting(
    room_index: int,
    item_used: list[Any] | None = None,
    result_flag: int = 0,
    battle_flow_logver: str = "1",
    start_battle_id: str | None = None,
    battle_log_json: str | None = None,
):
    session_key = _session_key()
    room_value = int(room_index)
    normalized_items = item_used if isinstance(item_used, list) else []
    result_value = int(result_flag)

    state = _ensure_ninjasaga_state()
    start_id = str(start_battle_id or state.get("start_battle_id") or "1")
    flow_ver = str(battle_flow_logver or state.get("battle_flow_logver") or "1")
    battle_log = battle_log_json or '{"battles":{"prototype":[],"length":1}}'

    # Battle.as:
    # huntingHash = Main.getHash(String(roomId) + result)
    # hash = Main.getHash(battleFlowLogver + startBattleId + jsonStr2)
    hunting_hash = get_hash(session_key, f"{room_value}{result_value}")
    battle_log_hash = get_hash(session_key, f"{flow_ver}{start_id}{battle_log}")

    args = [
        session_key,
        room_value,
        normalized_items,
        result_value,
        hunting_hash,
        flow_ver,
        start_id,
        battle_log,
        battle_log_hash,
    ]
    return _call_service(FINISH_HUNTING_METHOD, args)


def buy_hunting_time(room_index: int):
    session_key = _session_key()
    room_value = int(room_index)
    request_hash = get_hash(session_key, str(room_value))
    return _call_service(BUY_HUNTING_TIME_METHOD, [session_key, room_value, request_hash])


def easter_get_battle_status():
    session_key = _session_key()
    return _call_service(EASTER_GET_BATTLE_STATUS_METHOD, [session_key])


def easter_record_position(position_index: int):
    session_key = _session_key()
    pos = str(int(position_index))
    return _call_service(EASTER_RECORD_POSITION_METHOD, [session_key, pos, get_hash(session_key, pos)])


def easter_open_treasure(position_index: int):
    session_key = _session_key()
    pos = str(int(position_index))
    return _call_service(EASTER_OPEN_TREASURE_METHOD, [session_key, pos, get_hash(session_key, pos)])


def easter_start_battle(enemy_id: str, enemy_position_index: int, current_position_index: int):
    session_key = _session_key()
    enemy = str(enemy_id or "").strip()
    enemy_pos = str(int(enemy_position_index))
    current_pos = str(int(current_position_index))
    req_hash = get_hash(session_key, f"{enemy}{enemy_pos}{current_pos}")
    result = _call_service(
        EASTER_START_BATTLE_METHOD,
        [session_key, enemy, enemy_pos, current_pos, req_hash],
    )
    state = _ensure_ninjasaga_state()
    if isinstance(result, dict):
        start_battle_id = result.get("startBattleId") or result.get("start_battle_id") or result.get("code")
        if start_battle_id is not None:
            state["start_battle_id"] = str(start_battle_id)
    return result


def easter_generate_new_map():
    session_key = _session_key()
    return _call_service(EASTER_GENERATE_NEW_MAP_METHOD, [session_key])


def easter_buy_battle_heart(amount: int):
    session_key = _session_key()
    amount_value = int(amount)
    return _call_service(
        EASTER_BUY_BATTLE_HEART_METHOD,
        [session_key, amount_value, get_hash(session_key, str(amount_value))],
    )


def buy_item(item_id: str, amount: int = 1):
    session_key = _session_key()
    return _call_service(
        CHARACTER_BUY_ITEM_METHOD,
        [session_key, str(item_id or "").strip(), max(1, int(amount))],
    )


def motherday_get_special_battle_status():
    return _call_service(MOTHERDAY_GET_SPECIAL_BATTLE_STATUS_METHOD, [_session_key()])


def sakura_get_challenge_status():
    return _call_service(SAKURA_GET_STATUS_METHOD, [_session_key()])


def sakura_buy_petal(amount: int):
    return _call_service(SAKURA_BUY_PETAL_METHOD, [_session_key(), max(1, int(amount))])


def sakura_refill_challenge_energy():
    return _call_service(SAKURA_REFILL_ENERGY_METHOD, [_session_key()])


def get_boss_reward_event(
    boss_id: str,
    result_flag: int = 1,
    event_array: list[Any] | None = None,
    battle_flow_logver: str = "1",
    start_battle_id: str | None = None,
    battle_log_json: str | None = None,
):
    session_key = _session_key()
    state = _ensure_ninjasaga_state()

    boss = str(boss_id or "").strip()
    result_value = int(result_flag)
    flow_ver = str(battle_flow_logver or state.get("battle_flow_logver") or "1")
    start_id = str(start_battle_id or state.get("start_battle_id") or "1")
    event_values = event_array if isinstance(event_array, list) else ["token", 0]
    event_signature_data = ",".join(str(v) for v in event_values)
    signature = get_hash(session_key, f"{boss}|{result_value}|{event_signature_data}")

    battle_log = battle_log_json or '{"battles":{"prototype":[],"length":1}}'
    battle_log_hash = get_hash(session_key, f"{flow_ver}{start_id}{battle_log}")

    args = [
        session_key,
        signature,
        boss,
        result_value,
        event_values,
        flow_ver,
        start_id,
        battle_log,
        battle_log_hash,
    ]
    return _call_service(ITEM_GET_BOSS_REWARD_METHOD, args)


def select_special_jounin_class(class_index: int):
    session_key = _session_key()
    class_value = max(1, min(5, int(class_index)))
    return _call_service(SJ_CLASS_SELECT_METHOD, [session_key, class_value])
