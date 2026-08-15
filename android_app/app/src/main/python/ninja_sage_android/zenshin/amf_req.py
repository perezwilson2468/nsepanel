from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, quote, urljoin, urlparse

import pyamf
from pyamf import remoting

from ..core import config
from ..core.utils import _get_http_session


WEB_ORIGIN = "https://ninjazenshin.online"
WEB_LOGIN_URL = f"{WEB_ORIGIN}/login"
WEB_GAME_URL = f"{WEB_ORIGIN}/game"

FRAME_PATH_RE = re.compile(r"""(?P<url>(?:https?://ninjazenshin\.online)?/game/frame\?[^"'<>\s]+)""")
CSRF_INPUT_RE = re.compile(
    r"""<input[^>]+name=["']_token["'][^>]+value=["'](?P<token>[^"']+)["']""",
    re.IGNORECASE,
)
CSRF_META_RE = re.compile(
    r"""<meta[^>]+name=["']csrf-token["'][^>]+content=["'](?P<token>[^"']+)["']""",
    re.IGNORECASE,
)
JS_ENCODED_VAR_RE = re.compile(
    r"""(?:var|let|const)\s+(?P<name>sk|uid|uname|v)\s*=\s*encodeURIComponent\(["'](?P<value>[^"']*)["']\)""",
    re.IGNORECASE,
)


def _success(payload: Any) -> bool:
    return isinstance(payload, dict) and str(payload.get("status")) == "1"


def _normalize_login_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result")
    if isinstance(result, (list, tuple)):
        if len(result) > 0 and not payload.get("uid"):
            payload["uid"] = result[0]
        if len(result) > 1 and not payload.get("account_type"):
            payload["account_type"] = result[1]
        if len(result) > 2 and not payload.get("account_balance"):
            payload["account_balance"] = result[2]
        if len(result) > 3 and not payload.get("sessionkey"):
            payload["sessionkey"] = result[3]

    session_key = (
        payload.get("sessionkey")
        or payload.get("session_key")
        or payload.get("sk")
        or payload.get("token")
        or payload.get("result")
    )
    uid = payload.get("uid") or payload.get("user_id") or payload.get("account_id")
    if session_key:
        payload["sessionkey"] = str(session_key)
    if uid:
        payload["uid"] = str(uid)
    return payload


def _parse_frame_url(frame_url: str) -> dict[str, str]:
    query = parse_qs(urlparse(frame_url).query)
    return {
        "uid": (query.get("uid") or [""])[0],
        "uname": (query.get("uname") or [""])[0],
        "sk": (query.get("sk") or [""])[0],
        "v": (query.get("v") or [""])[0],
        "frame_url": frame_url,
    }


def _parse_login_input(username: str, password: str) -> dict[str, str]:
    raw_username = str(username or "").strip()
    raw_password = str(password or "").strip()

    if raw_username.startswith(("http://", "https://")):
        return _parse_frame_url(raw_username)

    return _web_login(raw_username, raw_password)


def _browser_headers(referer: str = WEB_ORIGIN) -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": referer,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        ),
    }


def _safe_preview(text: str, limit: int = 180) -> str:
    return " ".join(str(text or "").split())[:limit]


def _extract_csrf_token(html: str) -> str:
    match = CSRF_INPUT_RE.search(html or "") or CSRF_META_RE.search(html or "")
    return unescape(match.group("token")) if match else ""


def _extract_frame_login_data(text: str, final_url: str = "") -> dict[str, str]:
    candidates = [final_url]
    candidates.extend(unescape(match.group("url")) for match in FRAME_PATH_RE.finditer(text or ""))

    for candidate in candidates:
        if not candidate or "/game/frame?" not in candidate:
            continue
        frame_url = urljoin(WEB_ORIGIN, candidate)
        data = _parse_frame_url(frame_url)
        if data.get("uid") and data.get("sk"):
            return data

    js_values = {
        match.group("name").lower(): unescape(match.group("value"))
        for match in JS_ENCODED_VAR_RE.finditer(text or "")
    }
    if js_values.get("uid") and js_values.get("sk"):
        frame_url = (
            f"{WEB_ORIGIN}/game/frame?sk={quote(js_values.get('sk', ''))}"
            f"&uid={quote(js_values.get('uid', ''))}"
            f"&uname={quote(js_values.get('uname', ''))}"
            f"&v={quote(js_values.get('v', ''))}"
        )
        return {
            "uid": js_values.get("uid", ""),
            "uname": js_values.get("uname", ""),
            "sk": js_values.get("sk", ""),
            "v": js_values.get("v", ""),
            "frame_url": frame_url,
        }

    return {}


def _web_login(username: str, password: str) -> dict[str, str]:
    if not username or not password:
        raise ValueError("Ninja Zenshin login needs username and password, or paste the full /game/frame URL.")

    session = _get_http_session()
    login_page = session.get(WEB_LOGIN_URL, headers=_browser_headers(WEB_ORIGIN), timeout=25)
    login_page.raise_for_status()

    csrf_token = _extract_csrf_token(login_page.text)
    if not csrf_token:
        raise ValueError("Ninja Zenshin login page did not expose a CSRF token.")

    response = session.post(
        WEB_LOGIN_URL,
        data={
            "_token": csrf_token,
            "username": username,
            "password": password,
        },
        headers={
            **_browser_headers(WEB_LOGIN_URL),
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": WEB_ORIGIN,
        },
        timeout=25,
        allow_redirects=True,
    )
    response.raise_for_status()

    data = _extract_frame_login_data(response.text, response.url)
    if not data:
        game_page = session.get(WEB_GAME_URL, headers=_browser_headers(response.url), timeout=25)
        game_page.raise_for_status()
        data = _extract_frame_login_data(game_page.text, game_page.url)

    if data.get("uid") and data.get("sk"):
        data.setdefault("uname", username)
        data.setdefault("v", str(config.BUILD_NUM or ""))
        return data

    raise ValueError(
        "Ninja Zenshin web login succeeded but no /game/frame session was found. "
        f"Last page: {_safe_preview(response.url)}"
    )


def _amf_headers(referer: str = "") -> dict[str, str]:
    return {
        "Content-Type": "application/x-amf",
        "Accept": "application/x-amf, application/octet-stream, */*",
        "Origin": WEB_ORIGIN,
        "Referer": referer or WEB_GAME_URL,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) AdobeAIR/51.0"
        ),
        "X-Flash-Version": "32,0,0,465",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def _send_zenshin_amf(service: str, params: list[Any], referer: str = "") -> Any:
    env = remoting.Envelope(pyamf.AMF0)
    env["/0"] = remoting.Request(service, list(params or []))
    data = remoting.encode(env).getvalue()

    session = _get_http_session()
    resp = session.post(
        config.GATEWAY,
        data=data,
        headers=_amf_headers(referer),
        timeout=20,
    )
    content_type = (resp.headers.get("Content-Type") or "").lower()
    if resp.status_code >= 400 or "application/x-amf" not in content_type:
        raise ValueError(
            f"Ninja Zenshin AMF returned HTTP {resp.status_code} "
            f"with content-type {content_type or 'unknown'} for {service}"
        )

    try:
        resp_env = remoting.decode(resp.content)
    except Exception as exc:
        raise ValueError(f"Ninja Zenshin AMF decode failed for {service}: {exc}") from exc
    _, message = resp_env.bodies[0]
    return message.body


def reset_web_session() -> None:
    try:
        session = _get_http_session()
        session.cookies.clear()
        session.headers.pop("X-Rift-Warm", None)
    except Exception:
        pass


def check_version():
    try:
        return _send_zenshin_amf("SystemService.checkAmf", [config.BUILD_NUM])
    except Exception:
        return {"status": 1, "result": "Ninja Zenshin experimental profile skips checkVersion"}


def login(username, password, char_dot__="", char_dot__underscore=""):
    data = _parse_login_input(username, password)
    uid = data.get("uid") or data.get("uname") or username
    uname = data.get("uname") or uid
    sk = data.get("sk") or password
    version = data.get("v") or char_dot__underscore or config.BUILD_NUM

    require_response: Any = None
    try:
        require_response = _send_zenshin_amf(
            "SystemService.requireLogin",
            [None, None, str(uid or "")],
            data.get("frame_url", ""),
        )
        if isinstance(require_response, dict):
            normalized_require = _normalize_login_payload(dict(require_response))
            if normalized_require.get("uid") and not uid:
                uid = str(normalized_require["uid"])
            challenge = str(normalized_require.get("result") or "")
        else:
            challenge = ""
    except Exception:
        challenge = ""

    attempts = [[uid, "facebook", version, challenge, "", "", sk, "en"]]

    last_response: Any = require_response
    for params in attempts:
        try:
            response = _send_zenshin_amf("SystemService.snsLogin", params, data.get("frame_url", ""))
        except Exception as exc:
            last_response = exc
            continue

        last_response = response
        if _success(response):
            payload = _normalize_login_payload(dict(response))
            payload.setdefault("uid", str(uid or ""))
            payload.setdefault("uname", str(uname or ""))
            payload.setdefault("sessionkey", str(sk or ""))
            payload.setdefault("sk", str(sk or ""))
            payload.setdefault("build", str(version or ""))
            payload.setdefault("frame_url", data.get("frame_url", ""))
            return payload

    return {"status": 0, "message": f"Ninja Zenshin experimental login failed: {last_response}"}


def get_all_characters():
    session_key = str(config.login_data.get("sessionkey") or config.login_data.get("sk") or "")
    uid = str(config.login_data.get("uid") or config.login_data.get("user_id") or "")
    attempts = [
        [session_key],
        [session_key, uid],
        [session_key, uid, 0],
        [uid, session_key],
        [],
    ]
    last_response: Any = None
    for params in attempts:
        try:
            response = _send_zenshin_amf("CharacterDAO.getCharactersList", params)
        except Exception as exc:
            last_response = exc
            continue
        last_response = response
        characters = _normalize_characters(response)
        if characters:
            config.all_char = response
            return characters
    print(f"Ninja Zenshin character list failed: {last_response}")
    return []


def _normalize_characters(response: Any) -> list[dict[str, Any]]:
    raw_items: Any = None
    if isinstance(response, dict):
        for key in ("characters", "character_list", "account_data", "result"):
            value = response.get(key)
            if isinstance(value, list):
                raw_items = value
                break
            if isinstance(value, dict):
                raw_items = list(value.values())
                break
    elif isinstance(response, list):
        raw_items = response

    if not isinstance(raw_items, list):
        return []

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items):
        if isinstance(item, (list, tuple)):
            char_id = item[0] if len(item) > 0 else None
            name = item[1] if len(item) > 1 and item[1] is not None else f"Character {index + 1}"
            level = item[2] if len(item) > 2 and item[2] is not None else 0
            normalized.append({
                "char_id": char_id,
                "character_id": char_id,
                "character_name": str(name),
                "name": str(name),
                "character_level": level,
                "level": level,
                "index": index,
                "raw": list(item),
            })
            continue
        if not isinstance(item, dict):
            continue
        char_id = item.get("char_id") or item.get("character_id") or item.get("id")
        name = item.get("character_name") or item.get("name") or f"Character {index + 1}"
        level = item.get("character_level") or item.get("level") or 0
        normalized.append({
            "char_id": char_id,
            "character_id": char_id,
            "character_name": name,
            "name": name,
            "character_level": level,
            "level": level,
            "index": index,
            "raw": item,
        })
    return normalized


def get_character_data(char_id, **kwargs):
    session_key = str(config.login_data.get("sessionkey") or config.login_data.get("sk") or "")
    attempts = [
        [session_key, char_id],
        [session_key, char_id, 0],
        [char_id, session_key],
        [char_id],
    ]
    last_response: Any = None
    for params in attempts:
        try:
            response = _send_zenshin_amf("CharacterDAO.getCharacterById", params)
        except Exception as exc:
            last_response = exc
            continue
        last_response = response
        if isinstance(response, dict):
            payload = response.get("result") if isinstance(response.get("result"), dict) else response
            config.char_data = payload
            return payload
    raise ValueError(f"Ninja Zenshin character data failed: {last_response}")


def _session_key() -> str:
    if not isinstance(getattr(config, "login_data", None), dict):
        raise ValueError("Ninja Zenshin login data is not loaded in memory")
    session_key = str(config.login_data.get("sessionkey") or config.login_data.get("sk") or "").strip()
    if not session_key:
        raise ValueError("Ninja Zenshin session key is missing")
    return session_key


def _dict_result(response: Any) -> dict[str, Any]:
    return response if isinstance(response, dict) else {"status": 0, "result": response}


def watch_special_jounin_notice():
    return _dict_result(_send_zenshin_amf("CharacterDAO.watchSJENotice", [_session_key()]))


def start_special_jounin_exam():
    return _dict_result(_send_zenshin_amf("CharacterService.startSJExam", [_session_key()]))


def get_tutor_exam_notice():
    return _dict_result(_send_zenshin_amf("CharacterDAO.NTExamNotice", [_session_key()]))


def start_tutor_exam():
    return _dict_result(_send_zenshin_amf("CharacterService.startNTExam", [_session_key()]))


def select_tutor_class():
    return _dict_result(_send_zenshin_amf("CharacterDAO.NTClassSelect", [_session_key()]))


def select_special_jounin_class(class_index: int):
    return _dict_result(_send_zenshin_amf("CharacterDAO.SJClassSelect", [_session_key(), int(class_index)]))


def get_ss_training_mission_status():
    return _dict_result(_send_zenshin_amf("SSTraining.getMissionStatus", [_session_key()]))


def start_mission(mission_id: str):
    from . import mission

    return mission.start_mission(mission_id)


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
    from . import mission

    return mission.update_character_progress(
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
