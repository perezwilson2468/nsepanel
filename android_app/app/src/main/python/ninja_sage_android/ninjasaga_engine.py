import hashlib
import json
import os
import re
import time
import uuid
from http.cookies import SimpleCookie
from typing import Any, Callable

import pyamf
import requests
from pyamf import remoting
from . import storage
from .ninjasaga_core import (
    anti_detection as shared_anti_detection,
    easter as shared_easter,
    eudemon as shared_eudemon,
    leveling as shared_leveling,
    mission_policy as shared_mission_policy,
    progress_parser as shared_progress_parser,
    rate_control as shared_rate_control,
    recovery as shared_recovery,
)
from .ninjasaga_core.data_access import mission_data as shared_mission_data, enemy_data as shared_enemy_data
from .core import config as sage_core_config
from .core import utils as sage_core_utils
try:
    from Crypto.Cipher import AES  # type: ignore
except Exception:
    AES = None
try:
    import pyaes
except Exception:
    pyaes = None

BASE_GAME_ID = "ninjasaga"

AMF_PROFILES = {
    "official": {
        "label": "NinjaSaga.cc",
        "gateway": "https://amf.ninjasaga.cc/",
        "build_num": "latest",
        "clan_url": None,
    },
}

CHECK_VERSION_METHODS = ("SystemService.checkVersion", "SystemLogin.checkVersion")
REQUIRE_LOGIN_METHOD = "SystemService.requireLogin"
SNS_LOGIN_METHOD = "SystemService.snsLogin"
CHECK_AMF_METHOD = "SystemService.checkAmf"
GET_CHARACTERS_METHOD = "CharacterDAO.getCharactersList"
GET_CHARACTER_METHOD = "CharacterDAO.getCharacterById"
START_MISSION_METHOD = "CharacterService.startMission"
WATCH_SJE_NOTICE_METHOD = "CharacterDAO.watchSJENotice"
START_SJ_EXAM_METHOD = "CharacterService.startSJExam"
NT_EXAM_NOTICE_METHOD = "CharacterDAO.NTExamNotice"
START_NT_EXAM_METHOD = "CharacterService.startNTExam"
UPDATE_CHARACTER_METHOD = "CharacterService.updateCharacter"
GET_HUNTING_STATUS_METHOD = "EudemonGarden.getHuntingStatus"
START_HUNTING_METHOD = "EudemonGarden.startHunting"
FINISH_HUNTING_METHOD = "EudemonGarden.finishHunting"
EASTER_GET_BATTLE_STATUS_METHOD = "EasterFestival2015.getBattleStatus"
EASTER_START_BATTLE_METHOD = "EasterFestival2015.startBattle"
EASTER_OPEN_TREASURE_METHOD = "EasterFestival2015.openTreasure"
EASTER_GENERATE_NEW_MAP_METHOD = "EasterFestival2015.generateNewMap"
EASTER_BUY_BATTLE_HEART_METHOD = "EasterFestival2015.buyBattleHeart"
ITEM_GET_BOSS_REWARD_METHOD = "ItemDAO.getBossReward"
CHARACTER_BUY_ITEM_METHOD = "CharacterDAO.buyItem"
MOTHERDAY_GET_SPECIAL_BATTLE_STATUS_METHOD = "MothersDay2016.getSpecialBattleStatus"
SAKURA_GET_STATUS_METHOD = "SakuraEvent.getAnniChallengeStatus"
SAKURA_BUY_PETAL_METHOD = "SakuraEvent.buyPetal"
SAKURA_REFILL_ENERGY_METHOD = "SakuraEvent.refillChallengeEnergy"
SJ_CLASS_SELECT_METHOD = "CharacterDAO.SJClassSelect"
NT_CLASS_SELECT_METHOD = "CharacterDAO.NTClassSelect"

WEB_ORIGIN = "https://ninjasaga.cc"
WEB_API_ORIGIN = "https://api.ninjasaga.cc"
WEB_REFERER = "https://ninjasaga.cc/emulator.html"
WEB_HOME = "https://ninjasaga.cc/"
WEB_LOGIN_ENDPOINTS = (
    "https://api.ninjasaga.cc/login",
    "https://ninjasaga.cc/api.php/login",
    "https://ninjasaga.cc/api.php?action=login",
    "https://ninjasaga.cc/api.php?route=login",
    "https://ninjasaga.cc/api.php",
)
WEB_CUSTOM_CAPTCHA_GENERATE_ENDPOINT = "https://api.ninjasaga.cc/custom-captcha/generate"
WEB_CUSTOM_CAPTCHA_VERIFY_ENDPOINT = "https://api.ninjasaga.cc/verify-captcha"
WEB_XSOLLA_SESSION_ENDPOINTS = (
    "https://api.ninjasaga.cc/xsolla-session",
    "https://ninjasaga.cc/api.php/xsolla-session",
    "https://ninjasaga.cc/api.php?action=xsolla-session",
    "https://ninjasaga.cc/api.php?route=xsolla-session",
)

CLIENT_LIBRARY_SALT = "Vmn34aAciYK00Hen26nT01"
NINJASAGA_CODEC = "85224034668"
NINJASAGA_DEFAULT_CLS = "434106"

_PRIMARY_CONFIG = [75, 126, 53, 58, 71, 116, 50, 91, 46, 44, 115, 36]
_STREAM_IDENTIFIER = [61, 64, 56, 54, 87, 117, 116]
_ASSET_LOADER_DATA = [73, 110, 61, 90, 98, 68, 93, 79, 125, 89, 70, 104, 38, 103, 94, 89, 107, 118]
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")

_active_profile_id = "official"
_login_data: dict[str, Any] | None = None
_all_char_data: dict[str, Any] | None = None
_runtime_state: dict[str, Any] = {
    "cls": NINJASAGA_DEFAULT_CLS,
    "codec": NINJASAGA_CODEC,
    "client_uuid": "",
    "request_seq": 0,
    "last_service_debug": {},
    "login_trace": [],
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "leveling_action_delay_seconds": 10,
    "leveling_cycle_cooldown_seconds": 5,
    "leveling_rest_every_cycles": 40,
    "leveling_rest_duration_seconds": 60,
    "leveling_action_jitter_seconds": 2,
    "leveling_min_call_delay_seconds": 4,
    "leveling_start_retry_delay_seconds": 6,
    "leveling_start_max_retries": 3,
    "leveling_cloudflare_rest_seconds": 60,
    "leveling_cloudflare_backoff_steps_seconds": [60, 120, 240],
    "leveling_failure_window_seconds": 180,
    "leveling_max_failures_in_window": 6,
    "leveling_circuit_cooldown_seconds": 120,
    "eudemon_start_finish_delay_seconds": 25,
    "eudemon_cycle_cooldown_seconds": 5,
    "easter_battle_delay_seconds": 25,
    "easter_cycle_cooldown_seconds": 5,
    "sakura_battle_delay_seconds": 20,
    "easter_auto_spend_enabled": False,
    "easter_auto_spend_max_refills_per_run": 0,
    "easter_auto_spend_buy_amount": 3,
    "event_resource_mode": "wait",
    "event_wait_minutes": 30,
    "special_jounin_class_index": 3,
    "ss_training_abuse_loop": 1,
    "clan_war_auto_spend_token": False,
    "clan_war_stamina_refill_source": "auto",
    "clan_war_bleeding_mode": False,
    "clan_war_manual_recruit": False,
    "clan_war_manual_member_ids": [],
    "clan_war_target_clan_id": "",
    "clan_war_target_clan_name": "",
    "clan_war_battle_delay_seconds": 2,
    "clan_war_refresh_delay_seconds": 1,
    "clan_war_buy_stamina_delay_seconds": 2,
    "clan_war_amf_call_delay_seconds": 0,
    "clan_war_post_captcha_resume_delay_seconds": 0,
    "clan_war_low_stamina_wait_minutes": 30,
}

EUD_ROOM_BOSS_NAMES = {
    1: "Kamaitachi",
    2: "Hell Horse",
    3: "Kabutomushi Musha",
    4: "Kinkaku + Ginkaku",
    5: "Thunder Eagle",
    6: "Mammoth King",
    7: "Oceans Queen",
    8: "Ghost Soldier",
    9: "Battle Angel",
    10: "Infernal Chimera",
}

_settings: dict[str, Any] = dict(DEFAULT_SETTINGS)

RANK_CHUNIN = 2
RANK_JOUNIN = 4
RANK_SPECIAL_JOUNIN = 6
RANK_TUTOR = 8
GENIN_LEVEL_CAP = 20
CHUNIN_LEVEL_CAP = 40
JOUNIN_LEVEL_CAP = 60
SPECIAL_JOUNIN_LEVEL_CAP = 80
EXAM_FIXED_ACTION_DELAY_SECONDS = 30
EXAM_CHUNIN_ARR = ["msn55", "msn56", "msn57", "msn58", "msn59"]
EXAM_JOUNIN_ARR = ["msn132", "msn133", "msn134", "msn135", "msn136"]
EXAM_SPECIAL_JOUNIN_ARR_HARD = [
    "msn200", "msn205", "msn202", "msn206", "msn203", "msn207", "msn204",
    "msn208", "msn201", "msn209", "msn210", "msn211", "msn212",
]
EXAM_SPECIAL_JOUNIN_ARR_EASY = [
    "msn226", "msn227", "msn228", "msn229", "msn230", "msn231", "msn232",
    "msn233", "msn234", "msn235", "msn236", "msn237", "msn238",
]
EXAM_TUTOR_ARR_HARD = [
    "msn266", "msn259", "msn267", "msn260", "msn268", "msn261", "msn270",
    "msn262", "msn269", "msn263", "msn264", "msn265",
]
EXAM_TUTOR_ARR_EASY = [
    "msn250", "msn252", "msn249", "msn253", "msn248", "msn254", "msn247",
    "msn255", "msn251", "msn256", "msn257", "msn258",
]
TP_TRAINING_MISSIONS = ["msn170", "msn171", "msn172", "msn173", "msn174"]
SS_TRAINING_MISSIONS = ["msn279", "msn280", "msn281", "msn282", "msn283"]

_MISSION_DATA_CACHE: dict[str, dict[str, Any]] | None = None
_ENEMY_DATA_CACHE: dict[str, dict[str, Any]] | None = None


def _derive_zendamf_key() -> bytes:
    key_seed = (
        "".join(chr(v) for v in _PRIMARY_CONFIG)
        + "".join(chr(v) for v in _ASSET_LOADER_DATA)
        + "".join(chr(v) for v in reversed(_STREAM_IDENTIFIER))
    )
    return key_seed.encode("ascii")[:16]


_ZENDAMF_AES_KEY = _derive_zendamf_key()


def get_amf_profiles() -> list[dict[str, Any]]:
    return [
        {
            "id": profile_id,
            "label": profile["label"],
            "gateway": profile["gateway"],
            "build_num": profile["build_num"],
            "clan_url": profile.get("clan_url"),
        }
        for profile_id, profile in AMF_PROFILES.items()
    ]


def get_current_amf_profile() -> dict[str, Any]:
    profile = AMF_PROFILES[_active_profile_id]
    return {
        "id": _active_profile_id,
        "label": profile["label"],
        "gateway": profile["gateway"],
        "build_num": profile["build_num"],
        "clan_url": profile.get("clan_url"),
    }


def set_amf_profile(profile_id: str) -> dict[str, Any]:
    global _active_profile_id, _login_data, _all_char_data
    if profile_id not in AMF_PROFILES:
        raise ValueError(f"Unknown AMF profile: {profile_id}")
    _active_profile_id = profile_id
    _login_data = None
    _all_char_data = None
    _runtime_state.pop("session_key", None)
    _runtime_state.pop("http_session", None)
    return get_current_amf_profile()


def reset_session() -> None:
    global _login_data, _all_char_data
    _login_data = None
    _all_char_data = None
    _runtime_state.pop("session_key", None)
    _runtime_state.pop("http_session", None)


def get_settings() -> dict[str, Any]:
    out = dict(DEFAULT_SETTINGS)
    out.update(_settings)
    return out


def update_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return get_settings()
    merged = get_settings()
    merged.update(raw)
    merged["leveling_action_delay_seconds"] = max(1, int(merged.get("leveling_action_delay_seconds", 10)))
    merged["leveling_cycle_cooldown_seconds"] = max(1, int(merged.get("leveling_cycle_cooldown_seconds", 5)))
    merged["leveling_rest_every_cycles"] = max(0, int(merged.get("leveling_rest_every_cycles", 40)))
    merged["leveling_rest_duration_seconds"] = max(0, int(merged.get("leveling_rest_duration_seconds", 60)))
    merged["leveling_action_jitter_seconds"] = max(0, int(merged.get("leveling_action_jitter_seconds", 2)))
    merged["leveling_min_call_delay_seconds"] = max(0, int(merged.get("leveling_min_call_delay_seconds", 4)))
    merged["leveling_start_retry_delay_seconds"] = max(1, int(merged.get("leveling_start_retry_delay_seconds", 6)))
    merged["leveling_start_max_retries"] = max(1, int(merged.get("leveling_start_max_retries", 3)))
    merged["leveling_cloudflare_rest_seconds"] = max(1, int(merged.get("leveling_cloudflare_rest_seconds", 60)))
    merged["leveling_failure_window_seconds"] = max(30, int(merged.get("leveling_failure_window_seconds", 180)))
    merged["leveling_max_failures_in_window"] = max(1, int(merged.get("leveling_max_failures_in_window", 6)))
    merged["leveling_circuit_cooldown_seconds"] = max(10, int(merged.get("leveling_circuit_cooldown_seconds", 120)))
    raw_steps = merged.get("leveling_cloudflare_backoff_steps_seconds", [60, 120, 240])
    if isinstance(raw_steps, str):
        parsed_steps = []
        for item in raw_steps.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                parsed_steps.append(max(1, int(item)))
            except Exception:
                continue
        merged["leveling_cloudflare_backoff_steps_seconds"] = parsed_steps or [60, 120, 240]
    elif isinstance(raw_steps, (list, tuple)):
        parsed_steps = []
        for item in raw_steps:
            try:
                parsed_steps.append(max(1, int(item)))
            except Exception:
                continue
        merged["leveling_cloudflare_backoff_steps_seconds"] = parsed_steps or [60, 120, 240]
    else:
        merged["leveling_cloudflare_backoff_steps_seconds"] = [60, 120, 240]
    merged["eudemon_start_finish_delay_seconds"] = max(1, int(merged.get("eudemon_start_finish_delay_seconds", 25)))
    merged["eudemon_cycle_cooldown_seconds"] = max(1, int(merged.get("eudemon_cycle_cooldown_seconds", 5)))
    merged["easter_battle_delay_seconds"] = max(1, int(merged.get("easter_battle_delay_seconds", 25)))
    merged["easter_cycle_cooldown_seconds"] = max(1, int(merged.get("easter_cycle_cooldown_seconds", 5)))
    merged["sakura_battle_delay_seconds"] = max(1, int(merged.get("sakura_battle_delay_seconds", 20)))
    merged["easter_auto_spend_enabled"] = bool(merged.get("easter_auto_spend_enabled"))
    merged["easter_auto_spend_max_refills_per_run"] = max(0, int(merged.get("easter_auto_spend_max_refills_per_run", 0)))
    merged["easter_auto_spend_buy_amount"] = max(1, int(merged.get("easter_auto_spend_buy_amount", 3)))
    merged["event_resource_mode"] = str(merged.get("event_resource_mode") or "wait").strip().lower()
    if merged["event_resource_mode"] not in {"buy", "wait", "stop"}:
        merged["event_resource_mode"] = "wait"
    merged["event_wait_minutes"] = max(0, int(merged.get("event_wait_minutes", 30)))
    merged["special_jounin_class_index"] = max(1, min(5, int(merged.get("special_jounin_class_index", 3))))
    merged["ss_training_abuse_loop"] = max(1, int(merged.get("ss_training_abuse_loop", 1)))
    merged["clan_war_auto_spend_token"] = bool(merged.get("clan_war_auto_spend_token"))
    refill_source = str(merged.get("clan_war_stamina_refill_source") or "token").strip().lower()
    merged["clan_war_stamina_refill_source"] = refill_source if refill_source in {"auto", "token", "roll"} else "auto"
    merged["clan_war_bleeding_mode"] = bool(merged.get("clan_war_bleeding_mode"))
    merged["clan_war_manual_recruit"] = bool(merged.get("clan_war_manual_recruit"))
    raw_member_ids = merged.get("clan_war_manual_member_ids")
    if isinstance(raw_member_ids, str):
        merged["clan_war_manual_member_ids"] = [
            item.strip() for item in raw_member_ids.split(",") if item.strip()
        ][:2]
    elif isinstance(raw_member_ids, (list, tuple)):
        merged["clan_war_manual_member_ids"] = [
            str(item).strip() for item in raw_member_ids if str(item).strip()
        ][:2]
    else:
        merged["clan_war_manual_member_ids"] = []
    merged["clan_war_target_clan_id"] = str(merged.get("clan_war_target_clan_id") or "").strip()
    merged["clan_war_target_clan_name"] = str(merged.get("clan_war_target_clan_name") or "").strip()
    merged["clan_war_battle_delay_seconds"] = max(1, int(merged.get("clan_war_battle_delay_seconds", 8)))
    merged["clan_war_refresh_delay_seconds"] = max(1, int(merged.get("clan_war_refresh_delay_seconds", 4)))
    merged["clan_war_buy_stamina_delay_seconds"] = max(1, int(merged.get("clan_war_buy_stamina_delay_seconds", 3)))
    merged["clan_war_amf_call_delay_seconds"] = max(0, int(merged.get("clan_war_amf_call_delay_seconds", 1)))
    merged["clan_war_post_captcha_resume_delay_seconds"] = max(
        0,
        int(merged.get("clan_war_post_captcha_resume_delay_seconds", 1)),
    )
    merged["clan_war_low_stamina_wait_minutes"] = max(
        0,
        int(merged.get("clan_war_low_stamina_wait_minutes", 30)),
    )
    _settings.clear()
    _settings.update(merged)
    return get_settings()


def get_login_data() -> dict[str, Any] | None:
    return _login_data


def get_all_char_data() -> dict[str, Any] | None:
    return _all_char_data


def get_last_web_auth() -> dict[str, Any] | None:
    value = _runtime_state.get("last_web_auth")
    return value if isinstance(value, dict) else None


def _sha1_hex(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".."))


def _load_repo_json(filename: str) -> dict[str, Any]:
    path = os.path.join(_repo_root(), "data", filename)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _mission_data() -> dict[str, dict[str, Any]]:
    global _MISSION_DATA_CACHE
    if _MISSION_DATA_CACHE is None:
        _MISSION_DATA_CACHE = shared_mission_data()
    return _MISSION_DATA_CACHE


def _enemy_data() -> dict[str, dict[str, Any]]:
    global _ENEMY_DATA_CACHE
    if _ENEMY_DATA_CACHE is None:
        _ENEMY_DATA_CACHE = shared_enemy_data()
    return _ENEMY_DATA_CACHE


def _mission_display_label(mission_id: Any) -> str:
    return shared_mission_policy.mission_display_label(mission_id, account_type=_account_type_from_login())


def _enemy_display_name(enemy_id: Any) -> str:
    enemy = str(enemy_id or "").strip().lower()
    if not enemy:
        return "Unknown"
    info = _enemy_data().get(enemy) or {}
    name = str(info.get("name") or "").strip()
    return name or enemy


def _enemy_list_display(enemy_ids: list[str]) -> str:
    labels = []
    for enemy_id in enemy_ids:
        label = _enemy_display_name(enemy_id)
        if label.lower() == str(enemy_id).lower():
            labels.append(label)
        else:
            labels.append(f"{label} ({enemy_id})")
    return ", ".join(labels) if labels else "Unknown"


def _eudemon_room_boss_name(room_index: int) -> str:
    return EUD_ROOM_BOSS_NAMES.get(int(room_index) + 1, "")


def _normalize_mission_id(value: Any) -> str | None:
    return shared_mission_policy.normalize_mission_id(value)


def _account_type_from_login() -> int | None:
    if not isinstance(_login_data, dict):
        return None
    try:
        return int(_login_data.get("account_type"))
    except Exception:
        return None


def _mission_pool_for_level(level: int) -> list[str]:
    return shared_mission_policy.mission_pool_for_level(level)


def _mission_numeric_id(mission_id: Any) -> int:
    return shared_mission_policy.mission_numeric_id(mission_id)


def _mission_required_level(mission_id: Any) -> int | None:
    return shared_mission_policy.mission_required_level(mission_id)


def _is_mission_account_eligible(mission_id: Any, account_type: int | None) -> bool:
    return shared_mission_policy.is_mission_account_eligible(mission_id, account_type)


def _is_mission_auto_eligible(mission_id: Any, account_type: int | None) -> bool:
    return shared_mission_policy.is_mission_auto_eligible(mission_id, account_type)


def _pick_auto_mission(level: int, account_type: int | None = None) -> str:
    return shared_mission_policy.pick_auto_mission(level, account_type)


def _sanitize_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    cleaned = _CONTROL_CHARS_RE.sub("", value).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1]
    return cleaned


def _is_encrypted_hex_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) < 32 or len(value) % 32 != 0:
        return False
    return _HEX_RE.fullmatch(value) is not None


def _aes_decrypt_hex(hex_ciphertext: str) -> str | None:
    try:
        data = bytes.fromhex(hex_ciphertext)
        if AES is not None:
            cipher = AES.new(_ZENDAMF_AES_KEY, AES.MODE_ECB)
            decrypted = cipher.decrypt(data)
        elif pyaes is not None:
            aes = pyaes.AESModeOfOperationECB(_ZENDAMF_AES_KEY)
            decrypted = b"".join(aes.decrypt(data[i : i + 16]) for i in range(0, len(data), 16))
        else:
            return None
        null_index = decrypted.find(b"\x00")
        if null_index >= 0:
            decrypted = decrypted[:null_index]
        return decrypted.decode("latin-1")
    except Exception:
        return None


def _decrypt_amf_response(value: Any) -> Any:
    if isinstance(value, str):
        if _is_encrypted_hex_string(value):
            decrypted = _aes_decrypt_hex(value)
            if decrypted:
                return _sanitize_text(decrypted)
        return _sanitize_text(value)
    if isinstance(value, list):
        return [_decrypt_amf_response(item) for item in value]
    if isinstance(value, dict):
        decrypted: dict[Any, Any] = {}
        for key, item_value in value.items():
            key_name = _sanitize_text(key)
            if _is_encrypted_hex_string(key):
                maybe_key = _aes_decrypt_hex(key)
                if maybe_key:
                    key_name = _sanitize_text(maybe_key)
            decrypted[key_name] = _decrypt_amf_response(item_value)
        return decrypted if decrypted else []
    return value


def _http_session() -> requests.Session:
    session = _runtime_state.get("http_session")
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
    _runtime_state["http_session"] = session
    return session


def import_webview_cookies(cookie_header: str) -> dict[str, Any]:
    header = str(cookie_header or "").strip()
    if not header:
        return {"success": False, "message": "Cookie header is empty", "count": 0}
    session = _http_session()
    parsed = SimpleCookie()
    try:
        parsed.load(header)
    except Exception:
        return {"success": False, "message": "Cookie header parse failed", "count": 0}

    imported = 0
    for morsel in parsed.values():
        name = str(morsel.key or "").strip()
        value = str(morsel.value or "")
        if not name:
            continue
        session.cookies.set(name, value, domain="ninjasaga.cc", path="/")
        session.cookies.set(name, value, domain=".ninjasaga.cc", path="/")
        imported += 1
    _runtime_state["imported_webview_cookie_count"] = imported
    return {"success": imported > 0, "count": imported}


def get_login_data() -> dict[str, Any] | None:
    return _login_data


def _client_uuid() -> str:
    cached = str(_runtime_state.get("client_uuid") or "").strip()
    if cached:
        return cached
    saved = storage.load_json("ninjasaga_client.json", default={})
    if isinstance(saved, dict):
        existing = str(saved.get("uuid") or "").strip()
        if existing:
            _runtime_state["client_uuid"] = existing
            return existing
    generated = str(uuid.uuid4())
    _runtime_state["client_uuid"] = generated
    storage.save_json("ninjasaga_client.json", {"uuid": generated})
    return generated


def _trace_login(step: str, detail: str = "") -> None:
    trace = _runtime_state.get("login_trace")
    if not isinstance(trace, list):
        trace = []
        _runtime_state["login_trace"] = trace
    line = f"{step}: {detail}".strip(": ")
    trace.append(line)
    if len(trace) > 120:
        del trace[: len(trace) - 120]


def _mask_sensitive_text(value: str) -> str:
    text = str(value or "")
    if not text:
        return text
    if text.startswith("sid_ns_"):
        if len(text) <= 18:
            return text[:6] + "***"
        return f"{text[:10]}...{text[-6:]}"
    if len(text) > 24:
        return f"{text[:6]}...{text[-4:]}"
    return text


def _sanitize_request_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _sanitize_request_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_request_value(v) for v in value]
    if isinstance(value, str):
        lower = value.lower()
        if lower.startswith("sid_ns_"):
            return _mask_sensitive_text(value)
        if len(value) >= 30 and re.fullmatch(r"[0-9a-fA-F]+", value):
            return _mask_sensitive_text(value)
        return value
    return value


def _looks_player_not_found(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    text = str(
        payload.get("error")
        or payload.get("message")
        or payload.get("result")
        or ""
    ).lower()
    return "player not found" in text


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


def reset_login_trace() -> None:
    _runtime_state["login_trace"] = []


def get_login_trace() -> list[str]:
    trace = _runtime_state.get("login_trace")
    if not isinstance(trace, list):
        return []
    return [str(x) for x in trace]


def _post_amf(service: str, params: list[Any]) -> Any:
    session = _http_session()
    req = remoting.Request(service, list(params))
    env = remoting.Envelope(pyamf.AMF3)
    env["/0"] = req
    payload = remoting.encode(env).getvalue()

    headers = {
        "Content-Type": "application/x-amf",
        "Origin": WEB_ORIGIN,
        "Referer": _runtime_state.get("emulator_referer", WEB_REFERER),
    }
    gateway = get_current_amf_profile()["gateway"]
    resp = session.post(gateway, data=payload, headers=headers, timeout=25)

    content_type = (resp.headers.get("Content-Type") or "").lower()
    if resp.status_code >= 400 or "text/html" in content_type:
        raise ValueError(f"NinjaSaga AMF failed HTTP {resp.status_code} content-type {content_type or 'unknown'}")

    try:
        resp_env = remoting.decode(resp.content)
    except Exception as exc:
        raise ValueError(f"NinjaSaga decode AMF response failed: {exc}") from exc

    _, message = resp_env.bodies[0]
    return message.body


def _call_service(method: str, args: list[Any]) -> Any:
    sanitized_args = _sanitize_request_value(args)
    _trace_login("service.request", f"{method} args={_preview(sanitized_args, limit=500)}")
    try:
        raw = _post_amf(method, args)
        transport = "direct"
    except Exception as exc:
        # Mirror the working desktop flow: if the direct NinjaSaga transport
        # is not accepted cleanly, retry once through the shared AMF sender.
        _trace_login("amf.fallback", f"{method}: {exc}")
        sage_core_config.GATEWAY = get_current_amf_profile()["gateway"]
        raw = sage_core_utils.send_amf_request(method, args)
        transport = "shared_fallback"
    decrypted = _decrypt_amf_response(raw)
    debug_store = _runtime_state.get("last_service_debug")
    if not isinstance(debug_store, dict):
        debug_store = {}
        _runtime_state["last_service_debug"] = debug_store
    debug_store[method] = {
        "args": sanitized_args,
        "raw": raw,
        "decrypted": decrypted,
        "transport": transport,
        "timestamp": int(time.time()),
    }
    _trace_login(
        "service.response",
        f"{method} transport={transport} decrypted={_preview(_sanitize_request_value(decrypted), limit=900)}",
    )
    return decrypted


def _preview(value: Any, limit: int = 1800) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) > limit:
        return text[:limit] + f"...(truncated {len(text) - limit} chars)"
    return text


def get_last_service_debug(method: str | None = None) -> dict[str, Any]:
    store = _runtime_state.get("last_service_debug")
    if not isinstance(store, dict):
        return {"method": method or "", "raw_preview": "", "decrypted_preview": "", "timestamp": 0}
    if method and method in store and isinstance(store[method], dict):
        item = store[method]
        return {
            "method": method,
            "args_preview": _preview(item.get("args")),
            "raw_preview": _preview(item.get("raw")),
            "decrypted_preview": _preview(item.get("decrypted")),
            "transport": str(item.get("transport") or ""),
            "timestamp": int(item.get("timestamp") or 0),
        }
    if not store:
        return {"method": method or "", "args_preview": "", "raw_preview": "", "decrypted_preview": "", "transport": "", "timestamp": 0}
    # fallback latest item
    latest_method = ""
    latest_item = None
    latest_ts = 0
    for key, item in store.items():
        if not isinstance(item, dict):
            continue
        ts = int(item.get("timestamp") or 0)
        if ts >= latest_ts:
            latest_ts = ts
            latest_method = str(key)
            latest_item = item
    if not isinstance(latest_item, dict):
        return {"method": method or "", "args_preview": "", "raw_preview": "", "decrypted_preview": "", "transport": "", "timestamp": 0}
    return {
        "method": latest_method,
        "args_preview": _preview(latest_item.get("args")),
        "raw_preview": _preview(latest_item.get("raw")),
        "decrypted_preview": _preview(latest_item.get("decrypted")),
        "transport": str(latest_item.get("transport") or ""),
        "timestamp": latest_ts,
    }


def _session_key() -> str:
    if not isinstance(_login_data, dict):
        return ""
    value = _login_data.get("sessionkey") or _login_data.get("session_key") or _login_data.get("session")
    if value:
        return str(value)
    result = _login_data.get("result")
    if isinstance(result, (list, tuple)) and len(result) > 3:
        return str(result[3] or "")
    return ""


def _amf_scalar_id(value: Any) -> Any:
    if isinstance(value, (list, tuple)) and value:
        value = value[0]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            try:
                return int(stripped)
            except Exception:
                return stripped
        return stripped
    return value


def get_hash(seed: str, payload: str | None) -> str:
    return _sha1_hex(f"{payload or ''}{CLIENT_LIBRARY_SALT}{seed or ''}")


def _next_sequence_value() -> str:
    _runtime_state["request_seq"] = int(_runtime_state.get("request_seq", 0) or 0) + 1
    return str(_runtime_state["request_seq"])


def _next_sequence_hash() -> str:
    next_value = _next_sequence_value()
    return get_hash(_session_key(), next_value)


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
        char_name = item[1] if len(item) > 1 else f"Character {index + 1}"
        char_level = item[2] if len(item) > 2 else 0
        return {
            "character_id": char_id,
            "char_id": char_id,
            "character_name": char_name,
            "name": char_name,
            "character_level": char_level,
            "level": char_level,
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
    def _rows_from_map_dict(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if not isinstance(value, dict):
            return []
        indexed: list[tuple[int, Any]] = []
        for key, row in value.items():
            raw_key = str(key)
            # tolerate control/padded keys like "0\\n\\n" or "idx_0"
            digits = re.findall(r"\d+", raw_key)
            if not digits:
                continue
            try:
                idx = int(digits[-1])
            except Exception:
                continue
            indexed.append((idx, row))
        if not indexed:
            # fallback: dict values may already be row-like objects
            rows = []
            for row in value.values():
                if isinstance(row, (dict, list, tuple)):
                    rows.append(row)
            return rows
        indexed.sort(key=lambda x: x[0])
        return [row for _, row in indexed]

    if isinstance(result, dict):
        rows = _rows_from_map_dict(result.get("account_data"))
        if not rows:
            rows = _rows_from_map_dict(result.get("characters"))
        if not rows:
            rows = _rows_from_map_dict(result.get("result"))
        if not rows and isinstance(result.get("result"), dict):
            nested_result = result.get("result") or {}
            rows = _rows_from_map_dict(nested_result.get("account_data"))
            if not rows:
                rows = _rows_from_map_dict(nested_result.get("characters"))
        normalized = [_normalize_character_entry(row, idx) for idx, row in enumerate(rows or [])]
        result["account_data"] = normalized
        result["characters"] = normalized
        if "result" not in result:
            result["result"] = normalized
        if "status" not in result:
            result["status"] = 1 if normalized else 0
        return result
    if isinstance(result, list):
        normalized = [_normalize_character_entry(row, idx) for idx, row in enumerate(result)]
        return {"account_data": normalized, "characters": normalized, "status": 1}
    return {"account_data": [], "characters": [], "status": 0, "error": result}


def _extract_character(response: dict[str, Any] | Any) -> dict[str, Any]:
    if isinstance(response, dict):
        if isinstance(response.get("character_data"), dict):
            return response["character_data"]
        if response.get("character_name") or response.get("name"):
            return response
        if isinstance(response.get("result"), dict):
            nested = response.get("result") or {}
            if nested.get("character_name") or nested.get("name") or nested.get("character_id") or nested.get("char_id"):
                merged = dict(nested)
                merged.setdefault("status", response.get("status", 1))
                return merged
        if isinstance(response.get("result"), (list, tuple)):
            merged = _normalize_character_entry(response.get("result"), 0)
            merged.update(response)
            return merged
    if isinstance(response, (list, tuple)):
        payload = _normalize_character_entry(response, 0)
        payload["status"] = 1
        return payload
    raise ValueError(f"Failed to parse character data: {response}")


def _warmup_web_session(session: requests.Session) -> None:
    warm_headers = {
        "Origin": WEB_ORIGIN,
        "Referer": WEB_HOME,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        session.get(WEB_HOME, headers=warm_headers, timeout=25)
    except Exception:
        pass
    try:
        session.get(f"{WEB_ORIGIN}/emulator.html", headers=warm_headers, timeout=25)
    except Exception:
        pass


def prepare_login_session() -> dict[str, Any]:
    reset_login_trace()
    session = _http_session()
    _trace_login("prepare.start", f"profile={get_current_amf_profile()['id']}")
    _warmup_web_session(session)
    xsolla = _warmup_xsolla_session()
    return {
        "success": True,
        "xsolla_ready": isinstance(xsolla, dict),
        "current_amf_profile": get_current_amf_profile(),
    }


def _post_login_browser_warmup(web_auth: dict[str, Any]) -> None:
    session = _http_session()
    player_id = str(web_auth.get("player_id") or "")
    username = str(web_auth.get("username") or "")
    fb_at = str(web_auth.get("token") or "")
    fb_sig = str(web_auth.get("signature") or "")
    hash_time = str(web_auth.get("hash_time") or "")
    emulator_url = (
        f"{WEB_REFERER}?fb_uid={player_id}&fb_name={username}"
        f"&fb_at={fb_at}&fb_sig={fb_sig}&time=0&hash_time={hash_time}"
    )
    _runtime_state["emulator_referer"] = emulator_url

    emulator_headers = {
        "Origin": WEB_ORIGIN,
        "Referer": WEB_HOME,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = session.get(emulator_url, headers=emulator_headers, timeout=25)
        _trace_login("post_login.emulator", f"status={resp.status_code}")
    except Exception as exc:
        _trace_login("post_login.emulator_fail", str(exc))

    swf_url = (
        "https://cdn.ninjasaga.cc/cdn/swf/latest/ninja_saga.swf"
        f"?fb_uid={player_id}&fb_name={username}"
        f"&fb_at={fb_at}&fb_sig={fb_sig}&time=0&hash_time={hash_time}"
        "&cdn=https://cdn.ninjasaga.cc/cdn/&emulator=true&minimal=false&quality=high&font=false"
    )
    swf_headers = {
        "Origin": WEB_ORIGIN,
        "Referer": emulator_url,
        "Accept": "*/*",
    }
    try:
        resp = session.get(swf_url, headers=swf_headers, timeout=25, stream=True)
        _trace_login("post_login.swf", f"status={resp.status_code}")
        resp.close()
    except Exception as exc:
        _trace_login("post_login.swf_fail", str(exc))


def _warmup_xsolla_session() -> dict[str, Any] | None:
    session = _http_session()
    payload = {"uuid": _client_uuid()}
    last_error = None
    for endpoint in WEB_XSOLLA_SESSION_ENDPOINTS:
        _trace_login("xsolla.endpoint", endpoint)
        attempts = (
            (
                {"Content-Type": "application/json", "Accept": "application/json, text/plain, */*", "Origin": WEB_ORIGIN, "Referer": WEB_HOME, "X-Requested-With": "XMLHttpRequest"},
                {"json": payload},
            ),
            (
                {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Accept": "application/json, text/plain, */*", "Origin": WEB_ORIGIN, "Referer": WEB_HOME, "X-Requested-With": "XMLHttpRequest"},
                {"data": payload},
            ),
        )
        for headers, kwargs in attempts:
            req_mode = "json" if "json" in kwargs else "form"
            try:
                resp = session.post(endpoint, headers=headers, timeout=25, **kwargs)
            except Exception as exc:
                last_error = str(exc)
                _trace_login("xsolla.http_fail", f"{req_mode} {exc}")
                continue
            content_type = (resp.headers.get("Content-Type") or "").lower()
            _trace_login("xsolla.http", f"{req_mode} status={resp.status_code} content_type={content_type or 'unknown'}")
            if resp.status_code >= 400:
                last_error = f"HTTP {resp.status_code}: {_safe_body_snippet(resp)}"
                continue
            try:
                result = resp.json()
            except Exception:
                last_error = f"non-json: {_safe_body_snippet(resp)}"
                continue
            if isinstance(result, dict):
                _runtime_state["xsolla_session"] = result
                _trace_login("xsolla.ok", f"keys={list(result.keys())[:6]}")
                return result
            last_error = f"invalid xsolla payload type={type(result).__name__}"
    if last_error:
        _trace_login("xsolla.skip", last_error)
    return None


def _safe_body_snippet(resp: requests.Response, limit: int = 220) -> str:
    try:
        text = resp.text or ""
    except Exception:
        text = ""
    return " ".join(text.split())[:limit]


def _web_api_call(endpoint: str, payload: dict[str, Any], username: str = "", password: str = "") -> dict[str, Any]:
    session = _http_session()
    if username and password:
        _web_login(username, password)
    else:
        _warmup_web_session(session)

    request_payload = dict(payload or {})
    request_payload.setdefault("uuid", _client_uuid())
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": WEB_ORIGIN,
        "Referer": WEB_HOME,
        "X-Requested-With": "XMLHttpRequest",
    }
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


def _web_login(username: str, password: str) -> dict[str, Any]:
    session = _http_session()
    _warmup_web_session(session)
    _trace_login("web_login.start", f"user={username}")

    payload = {
        "username": username,
        "password": password,
        "minimal": 0,
        "air": 0,
        "w": 1920,
        "h": 1080,
        "tz": "Asia/Makassar",
        "cpu": 12,
        "ram": 8,
        "browser_ver": "Chrome 146",
        "uuid": _client_uuid(),
        "gpu": "ANGLE (AMD, AMD Radeon(TM) Graphics (0x00001638) Direct3D11 vs_5_0 ps_5_0, D3D11)",
    }

    last_error = None
    for endpoint in WEB_LOGIN_ENDPOINTS:
        _trace_login("web_login.endpoint", endpoint)
        attempts = (
            (
                {"Content-Type": "application/json", "Accept": "application/json, text/plain, */*", "Origin": WEB_ORIGIN, "Referer": WEB_HOME, "X-Requested-With": "XMLHttpRequest"},
                {"json": payload},
            ),
            (
                {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Accept": "application/json, text/plain, */*", "Origin": WEB_ORIGIN, "Referer": WEB_HOME, "X-Requested-With": "XMLHttpRequest"},
                {"data": payload},
            ),
        )
        for headers, kwargs in attempts:
            req_mode = "json" if "json" in kwargs else "form"
            try:
                resp = session.post(endpoint, headers=headers, timeout=25, **kwargs)
            except Exception as exc:
                last_error = f"Web login request failed on {endpoint}: {exc}"
                _trace_login("web_login.http_fail", f"{req_mode} {exc}")
                continue
            content_type = (resp.headers.get("Content-Type") or "").lower()
            _trace_login("web_login.http", f"{req_mode} status={resp.status_code} content_type={content_type or 'unknown'}")
            if resp.status_code >= 400:
                last_error = f"Web login HTTP {resp.status_code}: {_safe_body_snippet(resp)}"
                continue
            if "application/json" not in content_type and not _safe_body_snippet(resp).startswith("{"):
                last_error = f"Web login non-JSON: {_safe_body_snippet(resp)}"
                continue
            try:
                result = resp.json()
            except Exception:
                last_error = f"Web login parse JSON failed: {_safe_body_snippet(resp)}"
                continue
            if not isinstance(result, dict) or not result.get("success"):
                last_error = f"Web login rejected: {result}"
                _trace_login("web_login.rejected", _safe_body_snippet(resp))
                continue

            player_id = str(result.get("player_id") or "")
            fb_at = str(result.get("token") or "")
            fb_sig = str(result.get("signature") or "")
            hash_time = str(result.get("hash_time") or "")
            _runtime_state["emulator_referer"] = (
                f"{WEB_REFERER}?fb_uid={player_id}&fb_name={result.get('username','')}"
                f"&fb_at={fb_at}&fb_sig={fb_sig}&time=0&hash_time={hash_time}"
            )
            _trace_login("web_login.ok", f"player_id={player_id} hash_time_len={len(hash_time)}")
            return result

    _trace_login("web_login.fail", last_error or "unknown")
    raise ValueError(last_error or "NinjaSaga web login failed")


def _login_with_web_auth(web_auth: dict[str, Any], username_hint: str = "") -> dict[str, Any]:
    global _login_data

    fb_uid = str(web_auth.get("player_id") or web_auth.get("fb_uid") or "")
    fb_at = str(web_auth.get("token") or web_auth.get("fb_at") or "")
    fb_sig = str(web_auth.get("signature") or web_auth.get("fb_sig") or "")
    hash_time = str(web_auth.get("hash_time") or "")
    username = str(
        web_auth.get("username")
        or web_auth.get("fb_name")
        or username_hint
        or ""
    )
    req_time = web_auth.get("time", 0)
    try:
        req_time = int(req_time)
    except Exception:
        req_time = 0

    if not fb_uid or not fb_at or not fb_sig or not hash_time:
        raise ValueError(
            "Incomplete NinjaSaga web auth payload. Need fb_uid, fb_at, fb_sig, and hash_time."
        )

    _post_login_browser_warmup(
        {
            "player_id": fb_uid,
            "username": username,
            "token": fb_at,
            "signature": fb_sig,
            "hash_time": hash_time,
        }
    )

    app_type = "facebook"
    lang = "en"
    build_no = str(get_current_amf_profile()["build_num"])
    fb_uid_arg: Any = int(fb_uid) if fb_uid.isdigit() else fb_uid

    require_login = _call_service(REQUIRE_LOGIN_METHOD, [req_time, hash_time, fb_uid_arg])
    _trace_login("requireLogin.response", f"type={type(require_login).__name__}")
    if not isinstance(require_login, dict) or str(require_login.get("status")) != "1":
        _trace_login("requireLogin.fail", str(require_login))
        raise ValueError(f"NinjaSaga requireLogin failed: {require_login}")

    challenge = str(require_login.get("result") or require_login.get("challenge") or "")
    login_source = f"{challenge}{fb_uid}{app_type}{build_no}{NINJASAGA_CODEC}"
    login_hash = get_hash(challenge, login_source)

    result = _call_service(
        SNS_LOGIN_METHOD,
        [fb_uid_arg, app_type, build_no, challenge, login_hash, fb_sig, fb_at, lang],
    )
    _trace_login("snsLogin.response", f"type={type(result).__name__}")
    if not isinstance(result, dict):
        _trace_login("snsLogin.fail", f"invalid_type={type(result).__name__}")
        raise ValueError(f"NinjaSaga snsLogin invalid response: {result}")

    result = _normalize_login_payload(result)
    result.setdefault("status", 1)
    if str(result.get("status")) != "1":
        _trace_login("snsLogin.fail", str(result))
        raise ValueError(f"NinjaSaga snsLogin failed: {result}")

    result.setdefault("uid", fb_uid_arg)
    result.setdefault("access_token", fb_at)
    result.setdefault("fb_sig", fb_sig)

    _login_data = result
    session_key = _session_key()
    _runtime_state["session_key"] = session_key
    _runtime_state["last_login_username"] = username
    _runtime_state["last_login_password"] = ""
    _runtime_state["last_web_auth"] = {
        "player_id": fb_uid,
        "username": username,
        "token": fb_at,
        "signature": fb_sig,
        "hash_time": hash_time,
        "time": req_time,
    }

    cls = str(_runtime_state.get("cls") or NINJASAGA_DEFAULT_CLS)
    cls_hash = get_hash(session_key, cls)
    try:
        _call_service(CHECK_AMF_METHOD, [build_no, cls, cls_hash, session_key])
        _trace_login("checkAmf.ok", f"cls={cls}")
    except Exception:
        _trace_login("checkAmf.skip", "exception ignored")
    _trace_login("login.ok", f"uid={result.get('uid')} sessionkey_len={len(session_key)}")
    return result


def check_version() -> dict[str, Any]:
    for method in CHECK_VERSION_METHODS:
        try:
            result = _call_service(method, [get_current_amf_profile()["build_num"]])
        except Exception:
            continue
        if isinstance(result, dict):
            result.setdefault("_", get_current_amf_profile()["build_num"])
            result.setdefault("__", "")
            result.setdefault("codec", NINJASAGA_CODEC)
            result.setdefault("status", 1)
            return result
    return {"status": 1, "_": get_current_amf_profile()["build_num"], "__": "", "codec": NINJASAGA_CODEC}


def login(username: str, password: str, *_args) -> dict[str, Any]:
    reset_login_trace()
    _trace_login("login.start", f"user={username} build={get_current_amf_profile()['build_num']}")
    _warmup_xsolla_session()
    web_auth = _web_login(username, password)
    result = _login_with_web_auth(web_auth, username_hint=username)
    _runtime_state["last_login_username"] = username
    _runtime_state["last_login_password"] = password
    return result


def login_with_web_auth(
    fb_uid: Any,
    fb_name: Any,
    fb_at: Any,
    fb_sig: Any,
    hash_time: Any,
    req_time: Any = 0,
) -> dict[str, Any]:
    reset_login_trace()
    _trace_login(
        "login.web_auth",
        f"uid={fb_uid} hash_time_len={len(str(hash_time or ''))}",
    )
    _warmup_xsolla_session()
    return _login_with_web_auth(
        {
            "player_id": fb_uid,
            "fb_uid": fb_uid,
            "username": fb_name,
            "fb_name": fb_name,
            "token": fb_at,
            "fb_at": fb_at,
            "signature": fb_sig,
            "fb_sig": fb_sig,
            "hash_time": hash_time,
            "time": req_time,
        },
        username_hint=str(fb_name or ""),
    )


def get_all_characters() -> dict[str, Any]:
    global _all_char_data
    profile_build = str(get_current_amf_profile()["build_num"])
    last_payload: dict[str, Any] = {"status": 0, "error": "Unknown"}
    max_attempts = 4
    did_relogin = False
    preferred_args_variant = str(_runtime_state.get("get_characters_args_variant") or "session_only")

    for attempt in range(1, max_attempts + 1):
        session_key = _session_key()
        uid = None
        if isinstance(_login_data, dict):
            uid = _login_data.get("uid")
        access_token = None
        if isinstance(_login_data, dict):
            access_token = _login_data.get("access_token")

        variants: list[tuple[str, list[Any]]] = []
        # Match desktop flow first: CharacterDAO.getCharactersList([session_key]).
        # Extra variants are only tried later and only when args are valid.
        variants.append(("session_only", [session_key]))
        if attempt >= 2:
            if uid not in (None, ""):
                variants.append(("uid_session", [uid, session_key]))
                variants.append(("session_uid", [session_key, uid]))
            if access_token not in (None, ""):
                variants.append(("session_token", [session_key, access_token]))

        seen_signatures: set[str] = set()
        variant_payload: dict[str, Any] | None = None
        used_variant = "session_only"
        for variant_name, args in variants:
            signature = f"{variant_name}:{json.dumps(args, default=str)}"
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            try:
                result = _call_service(GET_CHARACTERS_METHOD, args)
            except Exception as exc:
                _trace_login("getCharacters.variant_error", f"{variant_name}: {exc}")
                continue
            if _looks_like_fault(result):
                fault_text = _fault_to_text(result)
                _trace_login("getCharacters.variant_fault", f"{variant_name}: {fault_text}")
                normalized_try = {"status": 0, "error": fault_text, "account_data": [], "characters": []}
            else:
                normalized_try = _normalize_characters_payload(result)
            rows_try = normalized_try.get("account_data") or normalized_try.get("characters") or []
            count_try = len(rows_try) if isinstance(rows_try, list) else 0
            status_try = str(normalized_try.get("status"))
            _trace_login("getCharacters.variant", f"{variant_name} status={status_try} rows={count_try}")
            if status_try == "1" and count_try > 0:
                variant_payload = normalized_try
                used_variant = variant_name
                break
            if variant_payload is None:
                variant_payload = normalized_try
                used_variant = variant_name

        normalized = variant_payload or {"status": 0, "error": "No getCharacters variant succeeded", "account_data": [], "characters": []}
        last_payload = normalized
        rows = normalized.get("account_data") or normalized.get("characters") or []
        row_count = len(rows) if isinstance(rows, list) else 0
        status_str = str(normalized.get("status"))
        _trace_login("getCharacters.attempt", f"{attempt}/{max_attempts} variant={used_variant} status={status_str} rows={row_count}")

        if status_str == "1" and row_count >= 0:
            _runtime_state["get_characters_args_variant"] = used_variant
            _all_char_data = normalized
            return normalized

        if _looks_player_not_found(normalized):
            _trace_login("getCharacters.player_not_found", f"attempt={attempt}")
            cls = str(_runtime_state.get("cls") or NINJASAGA_DEFAULT_CLS)
            cls_hash = get_hash(session_key, cls)
            try:
                _call_service(CHECK_AMF_METHOD, [profile_build, cls, cls_hash, session_key])
                _trace_login("getCharacters.checkAmf", "ok")
            except Exception as exc:
                _trace_login("getCharacters.checkAmf", f"fail={exc}")

            if attempt >= 2 and not did_relogin:
                username = str(_runtime_state.get("last_login_username") or "")
                password = str(_runtime_state.get("last_login_password") or "")
                if username and password:
                    try:
                        _trace_login("getCharacters.relogin", f"user={username}")
                        login(username, password)
                        did_relogin = True
                    except Exception as exc:
                        _trace_login("getCharacters.relogin_fail", str(exc))
                elif isinstance(_runtime_state.get("last_web_auth"), dict):
                    try:
                        _trace_login("getCharacters.relogin", "using cached web auth")
                        _login_with_web_auth(_runtime_state.get("last_web_auth") or {}, username_hint=username)
                        did_relogin = True
                    except Exception as exc:
                        _trace_login("getCharacters.relogin_fail", str(exc))
            time.sleep(1.2)
            continue

        if "fault" in str(normalized.get("error", "")).lower() and attempt < max_attempts:
            time.sleep(1.2)
            continue

        # non-player-not-found failure: short retry once/twice
        if attempt < max_attempts:
            time.sleep(0.8)
            continue

    _all_char_data = last_payload
    return last_payload


def get_character_data(char_id: Any) -> dict[str, Any]:
    session_key = _session_key()
    normalized_char_id = _amf_scalar_id(char_id)
    try:
        result = _call_service(GET_CHARACTER_METHOD, [session_key, normalized_char_id])
    except Exception:
        result = _call_service(GET_CHARACTER_METHOD, [normalized_char_id, session_key])
    payload = _extract_character(result)
    return payload


def _runtime_relogin_and_reselect_character(char_id: Any) -> bool:
    username = str(_runtime_state.get("last_login_username") or "").strip()
    password = str(_runtime_state.get("last_login_password") or "").strip()
    if not username or not password:
        return False
    try:
        login(username, password)
        if char_id is None:
            return True
        refreshed = get_character_data(char_id)
        return isinstance(refreshed, dict) and bool(refreshed)
    except Exception:
        return False


def silent_relogin_and_reselect_character(char_id: Any) -> bool:
    return _runtime_relogin_and_reselect_character(char_id)


def start_mission(mission_id: str) -> dict[str, Any]:
    session_key = _session_key()
    mission = str(mission_id or "").strip().lower()
    if not mission:
        raise ValueError("Mission ID is required")
    mission_hash = get_hash(session_key, mission)
    result = _call_service(START_MISSION_METHOD, [session_key, mission, mission_hash])
    if isinstance(result, dict):
        start_battle_id = result.get("startBattleId") or result.get("start_battle_id") or result.get("code")
        if start_battle_id is not None:
            _runtime_state["start_battle_id"] = str(start_battle_id)
    return result


def start_special_jounin_exam() -> dict[str, Any]:
    session_key = _session_key()
    result = _call_service(START_SJ_EXAM_METHOD, [session_key])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def watch_special_jounin_notice() -> dict[str, Any]:
    session_key = _session_key()
    result = _call_service(WATCH_SJE_NOTICE_METHOD, [session_key])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def get_tutor_exam_notice() -> dict[str, Any]:
    session_key = _session_key()
    result = _call_service(NT_EXAM_NOTICE_METHOD, [session_key])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def start_tutor_exam() -> dict[str, Any]:
    session_key = _session_key()
    result = _call_service(START_NT_EXAM_METHOD, [session_key])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def select_tutor_class() -> dict[str, Any]:
    session_key = _session_key()
    result = _call_service(NT_CLASS_SELECT_METHOD, [session_key])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def get_ss_training_mission_status() -> dict[str, Any]:
    session_key = _session_key()
    result = _call_service("SSTraining.getMissionStatus", [session_key])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def update_character_progress(
    char_id: Any,
    char_level: Any,
    mission_id: str,
    xp_gain: int = 0,
    gold_gain: int = 0,
) -> dict[str, Any]:
    session_key = _session_key()
    sequence_hash = _next_sequence_hash()
    xp_value = int(xp_gain or 0)
    gold_value = int(gold_gain or 0)
    array_hash = get_hash(
        session_key,
        ",".join(
            str(x)
            for x in [
                session_key,
                char_id,
                char_level,
                xp_value,
                gold_value,
                [],
                0,
                0,
                mission_id,
                0,
                "",
            ]
        ),
    )
    flow_ver = "1"
    start_battle_id = str(_runtime_state.get("start_battle_id") or "1")
    battle_log_json = '{"battles":{"prototype":[],"length":1}}'
    battle_log_hash = get_hash(session_key, f"{flow_ver}{start_battle_id}{battle_log_json}")
    args = [
        session_key,
        char_id,
        char_level,
        xp_value,
        gold_value,
        [],
        0,
        0,
        mission_id,
        array_hash,
        sequence_hash,
        0,
        "",
        flow_ver,
        start_battle_id,
        battle_log_json,
        battle_log_hash,
    ]
    result = _call_service(UPDATE_CHARACTER_METHOD, args)
    return result if isinstance(result, dict) else {"status": 1, "raw": result}


def get_hunting_status() -> dict[str, Any]:
    result = _call_service(GET_HUNTING_STATUS_METHOD, [_session_key()])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def start_hunting(room_index: int, enemy_ids: list[Any] | None = None) -> dict[str, Any]:
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
    if isinstance(result, dict):
        start_battle_id = result.get("startBattleId") or result.get("start_battle_id") or result.get("code")
        if start_battle_id is not None:
            _runtime_state["start_battle_id"] = str(start_battle_id)
        return result
    return {"status": 0, "result": result}


def finish_hunting(room_index: int, battle_log_json: str | None = None) -> dict[str, Any]:
    session_key = _session_key()
    room_value = int(room_index)
    normalized_items: list[Any] = []
    result_value = 0
    flow_ver = "1"
    start_id = str(_runtime_state.get("start_battle_id") or "1")
    battle_log = battle_log_json or '{"battles":{"prototype":[],"length":1}}'
    hunting_hash = get_hash(session_key, f"{room_value}{result_value}")
    battle_log_hash = get_hash(session_key, f"{flow_ver}{start_id}{battle_log}")
    args = [session_key, room_value, normalized_items, result_value, hunting_hash, flow_ver, start_id, battle_log, battle_log_hash]
    result = _call_service(FINISH_HUNTING_METHOD, args)
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def easter_get_battle_status() -> dict[str, Any]:
    result = _call_service(EASTER_GET_BATTLE_STATUS_METHOD, [_session_key()])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def easter_open_treasure(position_index: int) -> dict[str, Any]:
    session_key = _session_key()
    pos = str(int(position_index))
    result = _call_service(EASTER_OPEN_TREASURE_METHOD, [session_key, pos, get_hash(session_key, pos)])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def easter_start_battle(enemy_id: str, enemy_position_index: int, current_position_index: int) -> dict[str, Any]:
    session_key = _session_key()
    enemy = str(enemy_id or "").strip()
    enemy_pos = str(int(enemy_position_index))
    current_pos = str(int(current_position_index))
    req_hash = get_hash(session_key, f"{enemy}{enemy_pos}{current_pos}")
    result = _call_service(EASTER_START_BATTLE_METHOD, [session_key, enemy, enemy_pos, current_pos, req_hash])
    if isinstance(result, dict):
        start_battle_id = result.get("startBattleId") or result.get("start_battle_id") or result.get("code")
        if start_battle_id is not None:
            _runtime_state["start_battle_id"] = str(start_battle_id)
        return result
    return {"status": 0, "result": result}


def easter_generate_new_map() -> dict[str, Any]:
    result = _call_service(EASTER_GENERATE_NEW_MAP_METHOD, [_session_key()])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def easter_buy_battle_heart(amount: int) -> dict[str, Any]:
    session_key = _session_key()
    amount_value = max(1, int(amount))
    result = _call_service(EASTER_BUY_BATTLE_HEART_METHOD, [session_key, amount_value, get_hash(session_key, str(amount_value))])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def buy_item(item_id: str, amount: int = 1) -> dict[str, Any]:
    session_key = _session_key()
    result = _call_service(
        CHARACTER_BUY_ITEM_METHOD,
        [session_key, str(item_id or "").strip(), max(1, int(amount))],
    )
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def motherday_get_special_battle_status() -> dict[str, Any]:
    result = _call_service(MOTHERDAY_GET_SPECIAL_BATTLE_STATUS_METHOD, [_session_key()])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def sakura_get_challenge_status() -> dict[str, Any]:
    result = _call_service(SAKURA_GET_STATUS_METHOD, [_session_key()])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def sakura_buy_petal(amount: int) -> dict[str, Any]:
    result = _call_service(SAKURA_BUY_PETAL_METHOD, [_session_key(), max(1, int(amount))])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def sakura_refill_challenge_energy() -> dict[str, Any]:
    result = _call_service(SAKURA_REFILL_ENERGY_METHOD, [_session_key()])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def get_boss_reward_event(
    boss_id: str,
    result_flag: int = 0,
    event_array: list[Any] | None = None,
    battle_log_json: str | None = None,
) -> dict[str, Any]:
    session_key = _session_key()
    enemy = str(boss_id or "").strip()
    result_value = int(result_flag)
    event_payload = event_array if isinstance(event_array, list) else ["token", 0]
    flow_ver = "1"
    start_id = str(_runtime_state.get("start_battle_id") or "1")
    battle_log = battle_log_json or '{"battles":{"prototype":[],"length":1}}'
    event_signature_data = ",".join(str(value) for value in event_payload)
    reward_hash = get_hash(session_key, f"{enemy}|{result_value}|{event_signature_data}")
    battle_log_hash = get_hash(session_key, f"{flow_ver}{start_id}{battle_log}")
    args = [session_key, reward_hash, enemy, result_value, event_payload, flow_ver, start_id, battle_log, battle_log_hash]
    result = _call_service(ITEM_GET_BOSS_REWARD_METHOD, args)
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def select_special_jounin_class(class_index: int) -> dict[str, Any]:
    session_key = _session_key()
    class_value = max(1, min(5, int(class_index)))
    result = _call_service(SJ_CLASS_SELECT_METHOD, [session_key, class_value])
    return result if isinstance(result, dict) else {"status": 0, "result": result}


def _extract_rank(value: dict[str, Any]) -> int:
    if not isinstance(value, dict):
        return 0
    candidates = [value]
    for key in ("character_data", "data", "character", "result"):
        nested = value.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    for item in candidates:
        try:
            raw = item.get("character_rank") or item.get("rank") or item.get("rank_id")
            if raw is not None:
                return int(raw)
        except Exception:
            continue
    return 0


def _extract_control(value: dict[str, Any]) -> int:
    if not isinstance(value, dict):
        return 0
    candidates = [value]
    for key in ("character_data", "data", "character", "result"):
        nested = value.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    for item in candidates:
        try:
            raw = item.get("character_control") or item.get("control") or item.get("class_control") or item.get("class_id")
            if raw is not None:
                return int(raw)
        except Exception:
            continue
    return 0


def _is_success_response_dict(response: Any) -> bool:
    if isinstance(response, dict):
        status = response.get("status")
        if status is not None:
            return str(status) == "1"
        error = response.get("error")
        if error is not None:
            return str(error) in {"0", "None", ""}
    return False


def _extract_training_reward(response: dict[str, Any], reward_kind: str) -> int:
    reward_name = str(reward_kind or "").strip().lower()
    direct_key_map = {
        "tp": ("tp_reward",),
        "ss": ("ss_reward",),
    }
    for key in direct_key_map.get(reward_name, ()):
        try:
            value = int(response.get(key) or 0)
        except Exception:
            value = 0
        if value > 0:
            return value

    result = response.get("result")
    if isinstance(result, (list, tuple)) and len(result) >= 3:
        drops = result[2]
        if isinstance(drops, (list, tuple)):
            prefix = "ss_" if reward_name == "ss" else f"{reward_name}_"
            for item in drops:
                text = str(item or "").strip().lower()
                if not text.startswith(prefix):
                    continue
                try:
                    return int(text[len(prefix):])
                except Exception:
                    continue
    return 0


def _is_exam_already_completed_error(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    code = str(response.get("error") or response.get("status") or "").strip()
    text = str(
        response.get("error_message")
        or response.get("message")
        or response.get("result")
        or response.get("error")
        or ""
    ).lower()
    return code == "104" or "already complete" in text or "already completed" in text


def _run_rank_exam_hard(
    stop_event,
    char_id: str,
    exam_name: str,
    exam_missions: list[str],
    cycle_cooldown_seconds: int,
    log: Callable[[str, str], None] | None = None,
) -> bool:
    def _run_stage_list(stage_name: str, mission_list: list[str]) -> tuple[bool, bool]:
        any_started = False
        for index, mission_id in enumerate(mission_list, start=1):
            if stop_event.is_set():
                return False, any_started
            if log:
                log(
                    f"[Exam {stage_name} {index}/{len(mission_list)}] start mission {_mission_display_label(mission_id)}",
                    "info",
                )
            start_res = start_mission(mission_id)
            if not _is_success_response_dict(start_res):
                if _is_exam_already_completed_error(start_res):
                    if log:
                        log(
                            f"[Exam {stage_name}] mission {mission_id} already completed (error 104). Relogin and try next stage...",
                            "warning",
                        )
                    _runtime_relogin_and_reselect_character(char_id)
                    resume_wait = max(2, int(cycle_cooldown_seconds))
                    if log:
                        log(
                            f"[Exam {stage_name}] waiting {resume_wait}s before checking the next stage...",
                            "info",
                        )
                    waited = 0
                    while waited < resume_wait and not stop_event.is_set():
                        time.sleep(1)
                        waited += 1
                    if stop_event.is_set():
                        return False, any_started
                    continue
                if log:
                    log(f"[Exam {stage_name}] startMission failed: {start_res}", "warning")
                return False, any_started

            any_started = True
            waited = 0
            while waited < EXAM_FIXED_ACTION_DELAY_SECONDS and not stop_event.is_set():
                time.sleep(1)
                waited += 1
            if stop_event.is_set():
                return False, any_started

            char = get_character_data(char_id)
            char_level = _extract_char_level(char)
            update_res = update_character_progress(
                char_id=char_id,
                char_level=char_level,
                mission_id=mission_id,
                xp_gain=0,
                gold_gain=0,
            )
            if not _is_success_response_dict(update_res):
                if log:
                    log(f"[Exam {stage_name}] updateCharacter failed: {update_res}", "warning")
                return False, any_started
            if log:
                log(f"[Exam {stage_name} {index}/{len(mission_list)}] completed", "success")
            waited = 0
            cooldown = max(1, int(cycle_cooldown_seconds))
            while waited < cooldown and not stop_event.is_set():
                time.sleep(1)
                waited += 1
        return not stop_event.is_set(), any_started

    if exam_name == "Special Jounin":
        if log:
            log("[Exam Special Jounin] watching exam notice...", "info")
        notice_res = watch_special_jounin_notice()
        if not _is_success_response_dict(notice_res):
            if log:
                log(f"[Exam Special Jounin] watchSJENotice failed: {notice_res}", "warning")
            return False
        if log:
            log("[Exam Special Jounin] starting exam countdown...", "info")
        start_exam_res = start_special_jounin_exam()
        if not _is_success_response_dict(start_exam_res):
            if log:
                log(f"[Exam Special Jounin] startSJExam failed: {start_exam_res}", "warning")
            return False
        if log:
            log("[Exam Special Jounin] countdown started", "success")
    elif exam_name == "Tutor":
        if log:
            log("[Exam Tutor] checking exam notice...", "info")
        notice_res = get_tutor_exam_notice()
        if not _is_success_response_dict(notice_res):
            if log:
                log(f"[Exam Tutor] NTExamNotice failed: {notice_res}", "warning")
            return False
        if log:
            log("[Exam Tutor] starting exam countdown...", "info")
        start_exam_res = start_tutor_exam()
        if not _is_success_response_dict(start_exam_res):
            if log:
                log(f"[Exam Tutor] startNTExam failed: {start_exam_res}", "warning")
            return False
        if log:
            log("[Exam Tutor] countdown started", "success")

    ok, any_started = _run_stage_list(exam_name, exam_missions)
    if not ok:
        if exam_name == "Special Jounin":
            if log:
                log("[Exam Special Jounin] hard path did not match, trying easy path...", "warning")
            ok, _ = _run_stage_list("Special Jounin easy", EXAM_SPECIAL_JOUNIN_ARR_EASY)
        elif exam_name == "Tutor":
            if log:
                log("[Exam Tutor] hard path did not match, trying easy path...", "warning")
            ok, _ = _run_stage_list("Tutor easy", EXAM_TUTOR_ARR_EASY)
    elif not any_started and exam_name == "Special Jounin":
        if log:
            log("[Exam Special Jounin] hard path already cleared or unavailable, trying easy path...", "warning")
        ok, _ = _run_stage_list("Special Jounin easy", EXAM_SPECIAL_JOUNIN_ARR_EASY)
    elif not any_started and exam_name == "Tutor":
        if log:
            log("[Exam Tutor] hard path already cleared or unavailable, trying easy path...", "warning")
        ok, _ = _run_stage_list("Tutor easy", EXAM_TUTOR_ARR_EASY)
    if not ok:
        return False
    if exam_name == "Tutor" and not stop_event.is_set():
        if log:
            log("[Exam Tutor] claiming reward/class...", "info")
        class_res = select_tutor_class()
        if not _is_success_response_dict(class_res):
            if log:
                log(f"[Exam Tutor] NTClassSelect failed: {class_res}", "warning")
            return False
        if log:
            log("[Exam Tutor] reward claimed", "success")
    return not stop_event.is_set()


def run_leveling(
    stop_event,
    char_id: str,
    mission_id: str = "auto",
    xp_gain: int = 0,
    gold_gain: int = 0,
    action_delay_seconds: int = 6,
    cycle_cooldown_seconds: int = 5,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str, str], None] | None = None,
) -> None:
    return shared_leveling.run_leveling(
        stop_event=stop_event,
        char_id=char_id,
        runtime_settings=get_settings(),
        mission_id=mission_id,
        xp_gain=xp_gain,
        gold_gain=gold_gain,
        action_delay_seconds=action_delay_seconds,
        cycle_cooldown_seconds=cycle_cooldown_seconds,
        on_update=on_update,
        log=log,
        get_character_data=get_character_data,
        start_mission=start_mission,
        update_character_progress=update_character_progress,
        pick_auto_mission=_pick_auto_mission,
        mission_display_label=_mission_display_label,
        account_type_from_login=_account_type_from_login,
        runtime_relogin_and_reselect_character=_runtime_relogin_and_reselect_character,
        get_rank=_extract_rank,
        get_control=_extract_control,
        is_success_response_dict=_is_success_response_dict,
        select_special_jounin_class=select_special_jounin_class,
        run_rank_exam_hard=_run_rank_exam_hard,
        genin_level_cap=GENIN_LEVEL_CAP,
        chunin_level_cap=CHUNIN_LEVEL_CAP,
        jounin_level_cap=JOUNIN_LEVEL_CAP,
        special_jounin_level_cap=SPECIAL_JOUNIN_LEVEL_CAP,
        rank_chunin=RANK_CHUNIN,
        rank_jounin=RANK_JOUNIN,
        rank_special_jounin=RANK_SPECIAL_JOUNIN,
        rank_tutor=RANK_TUTOR,
        exam_chunin_arr=EXAM_CHUNIN_ARR,
        exam_jounin_arr=EXAM_JOUNIN_ARR,
        exam_special_jounin_arr_hard=EXAM_SPECIAL_JOUNIN_ARR_HARD,
        exam_tutor_arr_hard=EXAM_TUTOR_ARR_HARD,
    )


def run_tp_training(
    stop_event,
    char_id: str,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str, str], None] | None = None,
) -> None:
    settings = get_settings()
    anti = shared_anti_detection.build_anti_detection_profile(settings)
    action_delay_seconds = int(anti.get("action_delay_seconds", 10))
    cycle_cooldown_seconds = int(anti.get("cycle_cooldown_seconds", 5))
    action_jitter_seconds = int(anti.get("action_jitter_seconds", 2))
    min_call_delay_seconds = int(anti.get("min_call_delay_seconds", 4))
    start_retry_delay_seconds = int(anti.get("start_retry_delay_seconds", 6))
    start_max_retries = max(1, int(anti.get("start_max_retries", 3)))

    char = get_character_data(char_id)
    _, char_level, _, _, char_rank, _ = shared_progress_parser.extract_progress_snapshot(char, default_level=1, default_rank=_extract_rank(char))
    if char_level < 40:
        if log:
            log(f"TP Training requires level 40+. Current level: {char_level}.", "warning")
        return
    if (char_rank or -1) < RANK_JOUNIN:
        if log:
            log(f"TP Training requires rank Jounin. Current rank: {char_rank}.", "warning")
        return

    pending = [mid for mid in TP_TRAINING_MISSIONS if (_mission_required_level(mid) or 0) <= char_level]
    if log:
        labels = ", ".join(_mission_display_label(mid) for mid in pending) or "-"
        log(f"TP Training daily mission queue: {labels}", "info")
    last_call = None
    cycle = 0

    while pending and not shared_rate_control.stop_requested(stop_event):
        cycle += 1
        mission_id = pending[0]
        mission_label = _mission_display_label(mission_id)
        if log:
            log(f"[TP Cycle {cycle}] try mission {mission_label}", "info")
        started = False
        start_result: Any = None
        for attempt in range(1, start_max_retries + 1):
            start_result = start_mission(mission_id)
            if _is_success_response_dict(start_result):
                started = True
                break
            code = str((start_result or {}).get("status") or (start_result or {}).get("error") or "")
            if code == "100" and attempt < start_max_retries:
                retry_wait = max(1, int(start_retry_delay_seconds))
                if log:
                    log(f"[TP Cycle {cycle}] {mission_id} locked, retry {attempt}/{start_max_retries} in {retry_wait}s...", "warning")
                if not shared_rate_control.wait_with_stop(stop_event, retry_wait):
                    return
                continue
            break
        if not started:
            code = str((start_result or {}).get("status") or (start_result or {}).get("error") or "")
            cooldown_value = 0
            try:
                cooldown_value = int((start_result or {}).get("cooldown") or 0)
            except Exception:
                cooldown_value = 0
            if code in {"104", "109"} or cooldown_value > 0:
                pending.pop(0)
                if log:
                    log(f"[TP Cycle {cycle}] {mission_id} already consumed/locked today. Trying the next TP mission...", "warning")
                continue
            if log:
                log(f"[TP Cycle {cycle}] {mission_id} unavailable: {start_result}", "warning")
            pending.pop(0)
            continue

        pending.pop(0)
        wait_seconds = shared_rate_control.jittered_wait_seconds(action_delay_seconds, action_jitter_seconds)
        if not shared_rate_control.wait_with_stop(stop_event, wait_seconds):
            return
        current = get_character_data(char_id)
        _, current_level, _, _, current_rank, _ = shared_progress_parser.extract_progress_snapshot(current, default_level=char_level, default_rank=char_rank)
        update_result = update_character_progress(char_id=char_id, char_level=current_level, mission_id=mission_id, xp_gain=0, gold_gain=0)
        if not _is_success_response_dict(update_result):
            if log:
                log(f"[TP Cycle {cycle}] updateCharacter failed: {update_result}", "warning")
            continue
        name, level, xp, gold, rank, energy = shared_progress_parser.extract_progress_snapshot(update_result, default_level=current_level, default_rank=current_rank)
        tp_reward = _extract_training_reward(update_result, "tp") or 10
        if on_update:
            on_update({"level": level, "xp": xp, "gold": gold})
        if log:
            rank_suffix = f" Rank {rank}" if rank is not None else ""
            energy_suffix = f" Energy {energy}" if energy is not None else ""
            log(f"[TP Cycle {cycle}] ok -> {name} Lv {level}{rank_suffix} XP {xp} Gold {gold}{energy_suffix} TP +{tp_reward}", "success")
        if not shared_rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
            return


def run_ss_training(
    stop_event,
    char_id: str,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str, str], None] | None = None,
) -> None:
    settings = get_settings()
    anti = shared_anti_detection.build_anti_detection_profile(settings)
    action_delay_seconds = int(anti.get("action_delay_seconds", 10))
    cycle_cooldown_seconds = int(anti.get("cycle_cooldown_seconds", 5))
    action_jitter_seconds = int(anti.get("action_jitter_seconds", 2))
    start_retry_delay_seconds = int(anti.get("start_retry_delay_seconds", 6))
    start_max_retries = max(1, int(anti.get("start_max_retries", 3)))
    abuse_loops = max(1, int(settings.get("ss_training_abuse_loop", 1)))

    char = get_character_data(char_id)
    _, char_level, _, _, char_rank, _ = shared_progress_parser.extract_progress_snapshot(char, default_level=1, default_rank=_extract_rank(char))
    if char_level < 80:
        if log:
            log(f"SS Training requires level 80+. Current level: {char_level}.", "warning")
        return
    if (char_rank or -1) < RANK_TUTOR:
        if log:
            log(f"SS Training requires rank Tutor. Current rank: {char_rank}.", "warning")
        return

    if log:
        log(
            f"Starting SS Training | level={char_level} | rank={char_rank} | abuse_loops={abuse_loops}",
            "info",
        )

    for pass_index in range(1, abuse_loops + 1):
        if shared_rate_control.stop_requested(stop_event):
            return
        try:
            status_payload = get_ss_training_mission_status()
            if log:
                if isinstance(status_payload, dict):
                    result = status_payload.get("result")
                    if isinstance(result, list):
                        log(f"[SS Pass {pass_index}] getMissionStatus -> result_len={len(result)}", "info")
                    else:
                        log(f"[SS Pass {pass_index}] getMissionStatus -> keys={','.join(list(status_payload.keys())[:6])}", "info")
                else:
                    log(f"[SS Pass {pass_index}] getMissionStatus -> {type(status_payload).__name__}", "info")
        except Exception as exc:
            if log:
                log(f"[SS Pass {pass_index}] getMissionStatus failed: {exc}", "warning")

        any_started = False
        for mission_id in SS_TRAINING_MISSIONS:
            if shared_rate_control.stop_requested(stop_event):
                return
            if log:
                log(f"[SS Pass {pass_index}] try mission {_mission_display_label(mission_id)}", "info")
            started = False
            start_result: Any = None
            for attempt in range(1, start_max_retries + 1):
                start_result = start_mission(mission_id)
                if _is_success_response_dict(start_result):
                    started = True
                    any_started = True
                    break
                code = str((start_result or {}).get("status") or (start_result or {}).get("error") or "")
                if code == "100" and attempt < start_max_retries:
                    retry_wait = max(1, int(start_retry_delay_seconds))
                    if log:
                        log(f"[SS Pass {pass_index}] {mission_id} locked, retry {attempt}/{start_max_retries} in {retry_wait}s...", "warning")
                    if not shared_rate_control.wait_with_stop(stop_event, retry_wait):
                        return
                    continue
                break
            if not started:
                if log:
                    log(f"[SS Pass {pass_index}] {mission_id} unavailable: {start_result}", "warning")
                continue

            wait_seconds = shared_rate_control.jittered_wait_seconds(action_delay_seconds, action_jitter_seconds)
            if not shared_rate_control.wait_with_stop(stop_event, wait_seconds):
                return
            current = get_character_data(char_id)
            _, current_level, _, _, current_rank, _ = shared_progress_parser.extract_progress_snapshot(current, default_level=char_level, default_rank=char_rank)
            update_result = update_character_progress(char_id=char_id, char_level=current_level, mission_id=mission_id, xp_gain=0, gold_gain=0)
            if not _is_success_response_dict(update_result):
                if log:
                    log(f"[SS Pass {pass_index}] updateCharacter failed for {mission_id}: {update_result}", "warning")
                continue
            name, level, xp, gold, rank, energy = shared_progress_parser.extract_progress_snapshot(update_result, default_level=current_level, default_rank=current_rank)
            ss_reward = _extract_training_reward(update_result, "ss") or 30
            if on_update:
                on_update({"level": level, "xp": xp, "gold": gold})
            if log:
                rank_suffix = f" Rank {rank}" if rank is not None else ""
                energy_suffix = f" Energy {energy}" if energy is not None else ""
                log(f"[SS Pass {pass_index}] ok -> {name} Lv {level}{rank_suffix} XP {xp} Gold {gold}{energy_suffix} SS +{ss_reward}", "success")
            if not shared_rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                return
        if not any_started and log:
            log(f"[SS Pass {pass_index}] No SS mission was available in this pass.", "warning")


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


def _extract_char_level(char_data: dict[str, Any]) -> int:
    return _safe_int(char_data.get("character_level") or char_data.get("level"), 1)


def _extract_rooms(payload: Any) -> list[dict[str, Any]]:
    # Accept both flattened and nested room payloads from decrypted responses.
    out: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("room"), list):
                for item in node["room"]:
                    if isinstance(item, dict):
                        out.append(item)
                return
            keys = {"boss", "enemyId", "enemy_id", "time", "rank", "rewards", "status", "xp", "gold"}
            if set(node.keys()) & keys:
                out.append(node)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)
    dedup: list[dict[str, Any]] = []
    seen: set[str] = set()
    for room in out:
        marker = json.dumps(room, sort_keys=True, default=str)
        if marker in seen:
            continue
        seen.add(marker)
        dedup.append(room)
    return dedup


def _extract_enemy_ids(room: dict[str, Any]) -> list[str]:
    raw_boss = room.get("boss") or room.get("enemyId") or room.get("enemy_id") or []
    ids: list[str] = []
    if isinstance(raw_boss, list):
        for item in raw_boss:
            value = str(item or "").strip().lower()
            if value:
                ids.append(value)
        return ids
    if isinstance(raw_boss, str):
        for part in raw_boss.split(","):
            value = str(part or "").strip().lower()
            if value:
                ids.append(value)
        return ids
    value = str(raw_boss or "").strip().lower()
    return [value] if value else []


def run_eudemon_garden(
    stop_event,
    char_id: str,
    start_finish_delay_seconds: int = 5,
    cycle_cooldown_seconds: int = 5,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str, str], None] | None = None,
) -> None:
    return shared_eudemon.run_eudemon_garden(
        stop_event=stop_event,
        char_id=char_id,
        runtime_settings=get_settings(),
        start_finish_delay_seconds=start_finish_delay_seconds,
        cycle_cooldown_seconds=cycle_cooldown_seconds,
        on_update=on_update,
        log=log,
        get_hunting_status=get_hunting_status,
        extract_rooms=_extract_rooms,
        get_character_data=get_character_data,
        enemy_data=_enemy_data,
        extract_enemy_ids=_extract_enemy_ids,
        enemy_list_display=_enemy_list_display,
        room_boss_name=_eudemon_room_boss_name,
        start_hunting=start_hunting,
        finish_hunting=finish_hunting,
        is_success_response=_is_success_response,
        runtime_relogin_and_reselect_character=_runtime_relogin_and_reselect_character,
    )


def _adjacent_indices(pos: int) -> list[int]:
    x = pos % 5
    y = pos // 5
    out: list[int] = []
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if 0 <= nx < 5 and 0 <= ny < 4:
            out.append(ny * 5 + nx)
    return out


def _parse_battle_status(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    if str(payload.get("status")) != "1" or not isinstance(result, dict):
        candidates = [payload]
        candidates.extend(v for v in payload.values() if isinstance(v, dict))
        result = None
        for candidate in candidates:
            possible = candidate.get("result") if isinstance(candidate, dict) else None
            if isinstance(possible, dict) and ("enemy_id" in possible or "remain_heart" in possible):
                result = possible
                break
            if isinstance(candidate, dict) and ("enemy_id" in candidate or "remain_heart" in candidate):
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
        "event_point": _safe_int(result.get("event_point"), 0),
        "enemy_id": [str(v) for v in enemy_ids],
    }


def _easter_token_kind(token: str) -> str:
    text = str(token or "").strip().lower()
    if text == "1":
        return "empty"
    if text.startswith("enemy"):
        return "enemy"
    return "treasure"


def _easter_enemy_label(enemy_id: str, slot_index: int) -> str:
    if int(slot_index) == 19:
        return f"Stone Giant ({enemy_id})"
    return enemy_id


def run_easter_event(
    stop_event,
    char_id: str,
    battle_delay_seconds: int = 25,
    cycle_cooldown_seconds: int = 5,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str, str], None] | None = None,
) -> None:
    return shared_easter.run_easter_event(
        stop_event=stop_event,
        char_id=char_id,
        runtime_settings=get_settings(),
        battle_delay_seconds=battle_delay_seconds,
        cycle_cooldown_seconds=cycle_cooldown_seconds,
        on_update=on_update,
        log=log,
        easter_get_battle_status=easter_get_battle_status,
        parse_battle_status=_parse_battle_status,
        easter_buy_battle_heart=easter_buy_battle_heart,
        adjacent_indices=_adjacent_indices,
        token_kind=_easter_token_kind,
        easter_open_treasure=easter_open_treasure,
        easter_start_battle=easter_start_battle,
        boss_reward_event=get_boss_reward_event,
        get_character_data=get_character_data,
        easter_enemy_label=_easter_enemy_label,
        easter_generate_new_map=easter_generate_new_map,
        is_success_response=_is_success_response,
        runtime_relogin_and_reselect_character=_runtime_relogin_and_reselect_character,
    )
