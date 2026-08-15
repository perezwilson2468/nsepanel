import base64
import hashlib
import json
import random
import re
import string
import time

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from .. import config


SHINOBI_AES_KEY_HEX = "9a0b6443925dab25f2c98e7af1c27b057dd0e6517ee8f0dcc4ca71e628d38f9d"
SHINOBI_TIMEOUT_SECONDS = 20
SHINOBI_DEBUG_HTTP = True


def get_shinobi_state() -> dict:
    state = getattr(config, "shinobi_state", None)
    if not isinstance(state, dict):
        state = {}
        config.shinobi_state = state
    return state


def get_device_id() -> str:
    state = get_shinobi_state()
    device_id = state.get("device_id")
    if device_id:
        return device_id

    suffix = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
    build_digits = "".join(re.findall(r"\d+", str(config.BUILD_NUM or "")))
    build_prefix = build_digits or str(config.BUILD_NUM)
    device_id = f"{build_prefix}pc{suffix}"
    state["device_id"] = device_id
    return device_id


def _get_server_url() -> str:
    state = get_shinobi_state()
    return state.get("server_url") or config.get_current_amf_profile()["gateway"]


def _headers(access_token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _settings() -> dict:
    try:
        return config.get_shinobi_settings()
    except Exception:
        return {}


def _preview_text(value, limit: int = 220) -> str:
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _preview_json(value, limit: int = 420) -> str:
    try:
        text = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    except Exception:
        text = str(value)
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _safe_decode_base64_response(content):
    try:
        return decode_base64_json(content)
    except Exception as exc:
        return {"_decode_error": str(exc)}


def _safe_decode_encrypted_response(content):
    try:
        salt = get_shinobi_state().get("salt")
        return decode_encrypted_json(content, salt=salt)
    except Exception as exc:
        return {"_decode_error": str(exc)}


def _debug_http(message: str):
    callback = getattr(config, "action_log_callback", None)
    if callable(callback):
        try:
            callback(message, "info")
        except Exception:
            pass
    debug_enabled = _settings().get("debug_http", SHINOBI_DEBUG_HTTP)
    if debug_enabled:
        print(message)


def _request_delay():
    delay_seconds = int(_settings().get("request_delay_seconds", 0) or 0)
    if delay_seconds > 0:
        time.sleep(delay_seconds)


def _timeout_seconds() -> int:
    configured = _settings().get("timeout_seconds", SHINOBI_TIMEOUT_SECONDS)
    try:
        return max(1, int(configured))
    except Exception:
        return SHINOBI_TIMEOUT_SECONDS


def _md5_string(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _constant_key(time_value, key_value) -> str:
    return _md5_string(str(int(int(time_value) / 9) + int(key_value) * 9))


def _private_key(time_value, key_value) -> str:
    return _md5_string(str((int(int(time_value) / 654) - int(key_value)) * 3 + int(key_value)))


def apply_shinobi_response_state(response: dict) -> None:
    if not isinstance(response, dict):
        return

    state = get_shinobi_state()

    access_token = response.get("access_token")
    if access_token and access_token != state.get("access_token"):
        state["access_token"] = access_token

    server = response.get("server")
    if isinstance(server, dict):
        server_url = server.get("url")
        if server_url and server_url != state.get("server_url"):
            state["server_url"] = server_url
            _debug_http(f"[Shinobi HTTP] server_url updated to {server_url}")

    payload = response.get("payload")
    if isinstance(payload, dict):
        jwt = payload.get("jwt")
        if jwt:
            state["user_key"] = jwt

        if payload.get("time") is not None and payload.get("key") is not None:
            state["constant_key"] = _constant_key(payload["time"], payload["key"])
            state["private_key"] = _private_key(payload["time"], payload["key"])

        if payload.get("salt") is not None:
            state["salt"] = _md5_string(str(payload["salt"]))


def encode_base64_json(payload: dict | None) -> str:
    payload = payload or {}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def decode_base64_json(payload: bytes | str) -> dict:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    decoded = base64.b64decode(payload)
    return json.loads(decoded.decode("utf-8"))


def encode_encrypted_json(payload: dict | None) -> str:
    payload = payload or {}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    key = bytes.fromhex(SHINOBI_AES_KEY_HEX)
    iv = bytes(random.getrandbits(8) for _ in range(16))
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(raw, AES.block_size))
    return base64.b64encode(iv + encrypted).decode("utf-8")


def decode_encrypted_json(payload: bytes | str, salt: str | None = None) -> dict:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if salt:
        payload = payload.replace(salt, "")
    data = base64.b64decode(payload)
    iv = data[:16]
    encrypted = data[16:]
    key = bytes.fromhex(SHINOBI_AES_KEY_HEX)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
    return json.loads(decrypted.decode("utf-8"))


def post_base64_json(route: str, payload: dict | None = None, access_token: str | None = None) -> dict:
    payload = payload or {}
    url = _get_server_url() + route
    body = encode_base64_json(payload)
    _request_delay()
    _debug_http(
        f"[Shinobi HTTP] POST {url} | access_token={'yes' if access_token else 'no'} "
        f"| mode=base64 | payload={_preview_text(payload)}"
    )
    response = requests.post(
        url,
        data=body,
        headers=_headers(access_token),
        timeout=_timeout_seconds(),
    )
    _debug_http(
        f"[Shinobi HTTP] RESPONSE {response.status_code} {url} | body={_preview_text(response.text)}"
    )
    response.raise_for_status()
    decoded = _safe_decode_base64_response(response.content)
    apply_shinobi_response_state(decoded)
    _debug_http(
        f"[Shinobi HTTP] DECODED {response.status_code} {url} | json={_preview_json(decoded)}"
    )
    return decoded


def post_encrypted_json(route: str, payload: dict | None = None, access_token: str | None = None) -> dict:
    payload = payload or {}
    url = _get_server_url() + route
    body = encode_encrypted_json(payload)
    _request_delay()
    _debug_http(
        f"[Shinobi HTTP] POST {url} | access_token={'yes' if access_token else 'no'} "
        f"| mode=encrypted | payload={_preview_text(payload)}"
    )
    response = requests.post(
        url,
        data=body,
        headers=_headers(access_token),
        timeout=_timeout_seconds(),
    )
    _debug_http(
        f"[Shinobi HTTP] RESPONSE {response.status_code} {url} | body={_preview_text(response.text)}"
    )
    response.raise_for_status()
    decoded = _safe_decode_encrypted_response(response.content)
    apply_shinobi_response_state(decoded)
    _debug_http(
        f"[Shinobi HTTP] DECODED {response.status_code} {url} | json={_preview_json(decoded)}"
    )
    return decoded
