from __future__ import annotations

import json
import random
import re
import struct
import threading
import time
import zlib
from typing import Any, Callable, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from .. import config
from . import amf_req

CLAN_BATTLE_STAMINA_COST = 10
CLAN_STAMINA_POLL_SECONDS = 5
CLAN_IDLE_SECONDS = 10 * 60
NINJASAGA_CLAN_WAR_DEFAULT_SETTINGS = {
    "battle_delay_seconds": 6,
    "refresh_delay_seconds": 3,
    "buy_stamina_delay_seconds": 3,
    "amf_call_delay_seconds": 0,
    "post_captcha_resume_delay_seconds": 1,
}

CLAN_PANEL_SWF_URL = "https://cdn.ninjasaga.cc/cdn/swf/latest/swf/panels/clan_panel.swf"
DEFAULT_CLAN_BATTLE_KEY = [75, 126, 53, 58, 71, 116, 50, 91, 46, 44, 115, 36, 73, 110, 61, 90]
DEFAULT_CLAN_STAMINA_KEY = [116, 46, 75, 91, 61, 53, 73, 126, 36, 90, 50, 58, 44, 71, 110, 115]
CLAN_BATTLE_DEFENDER_STRATEGIES = (
    "as_seqhash",
    "as_rawseq",
    "legacy_inner_seqhash",
    "legacy_inner_rawseq",
)
_clan_token_uniq_id_cache: Optional[str] = None
_clan_battle_key_cache: Optional[list[int]] = None
_clan_stamina_key_cache: Optional[list[int]] = None
_clan_token_uniq_id_lock = threading.Lock()


def _inflate_swf_bytes(data: bytes) -> bytes:
    if data[:3] == b"CWS":
        return b"FWS" + data[3:8] + zlib.decompress(data[8:])
    if data[:3] != b"FWS":
        return b""
    return data


def _extract_clan_token_uniq_id_from_swf_bytes(data: bytes) -> str:
    data = _inflate_swf_bytes(data)
    if not data:
        return ""

    marker = b"parent.postMessage({action: 'show_captcha'}, '*');"
    idx = data.find(marker)
    if idx == -1:
        idx = data.find(b"show_captcha")
    if idx == -1:
        return ""

    window = data[max(0, idx - 256): min(len(data), idx + 512)]
    numbers = [
        match.decode("ascii", errors="ignore")
        for match in re.findall(rb"\d{14,20}", window)
        if match != b"123123123123412"
    ]
    if numbers:
        return numbers[-1]
    return ""


def _extract_clan_battle_key_from_swf_bytes(data: bytes) -> list[int]:
    data = _inflate_swf_bytes(data)
    if not data:
        return []

    marker_positions = []
    for marker in (b"ClanWar.getBattleDefender", b"getBattleDefender"):
        idx = data.find(marker)
        if idx != -1:
            marker_positions.append(idx)
    if not marker_positions:
        marker_positions.append(len(data) // 2)

    patterns = (
        re.compile(r"_k[^[]*\[\s*((?:\d+\s*,\s*){15}\d+)\s*\]"),
        re.compile(r"\[\s*((?:\d+\s*,\s*){15}\d+)\s*\]"),
    )
    for idx in marker_positions:
        window = data[max(0, idx - 8192): min(len(data), idx + 8192)]
        text = window.decode("latin1", errors="ignore")
        for pattern in patterns:
            for match in pattern.finditer(text):
                try:
                    values = [int(part.strip()) for part in match.group(1).split(",")]
                except Exception:
                    continue
                if len(values) == 16 and all(0 <= value <= 255 for value in values):
                    return values

    abc = _extract_first_doabc_bytes(data)
    if abc:
        code = _find_named_method_body_in_doabc(
            abc,
            class_name="ninjasaga.linkage::ClanPanel",
            method_name="getDefender",
        )
        values = _extract_literal_push_int_array_from_code(code, expected_count=16) if code else []
        if len(values) == 16 and all(0 <= value <= 255 for value in values):
            return values
    return []


def _read_u30(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        value = data[pos]
        pos += 1
        result |= (value & 0x7F) << shift
        if not (value & 0x80):
            return result, pos
        shift += 7


def _extract_first_doabc_bytes(data: bytes) -> bytes:
    swf = _inflate_swf_bytes(data)
    if not swf:
        return b""
    pos = 8
    nbits = swf[pos] >> 3
    pos += (5 + nbits * 4 + 7) // 8
    pos += 4
    while pos + 2 <= len(swf):
        header = struct.unpack_from("<H", swf, pos)[0]
        pos += 2
        tag_code = header >> 6
        length = header & 0x3F
        if length == 0x3F:
            length = struct.unpack_from("<I", swf, pos)[0]
            pos += 4
        body = swf[pos: pos + length]
        pos += length
        if tag_code == 82:
            name_end = body.find(b"\x00", 4)
            if name_end != -1:
                return body[name_end + 1:]
    return b""


def _skip_abc_trait(data: bytes, pos: int) -> int:
    _, pos = _read_u30(data, pos)
    kind_attr = data[pos]
    pos += 1
    kind = kind_attr & 0x0F
    attrs = kind_attr >> 4
    if kind in (0, 6):
        _, pos = _read_u30(data, pos)
        _, pos = _read_u30(data, pos)
        value_index, pos = _read_u30(data, pos)
        if value_index != 0:
            pos += 1
    elif kind in (1, 2, 3, 4, 5):
        _, pos = _read_u30(data, pos)
        _, pos = _read_u30(data, pos)
    if attrs & 0x04:
        metadata_count, pos = _read_u30(data, pos)
        for _ in range(metadata_count):
            _, pos = _read_u30(data, pos)
    return pos


def _find_named_method_body_in_doabc(abc: bytes, class_name: str, method_name: str) -> bytes:
    pos = 0
    if len(abc) < 4:
        return b""
    pos += 4

    for _ in range(2):
        count, pos = _read_u30(abc, pos)
        for _ in range(1, count):
            _, pos = _read_u30(abc, pos)

    count, pos = _read_u30(abc, pos)
    pos += max(0, count - 1) * 8

    string_count, pos = _read_u30(abc, pos)
    strings = [""]
    for _ in range(1, string_count):
        length, pos = _read_u30(abc, pos)
        strings.append(abc[pos: pos + length].decode("utf-8", errors="ignore"))
        pos += length

    namespace_count, pos = _read_u30(abc, pos)
    namespaces: list[tuple[int, int] | None] = [None]
    for _ in range(1, namespace_count):
        kind = abc[pos]
        pos += 1
        name_index, pos = _read_u30(abc, pos)
        namespaces.append((kind, name_index))

    ns_set_count, pos = _read_u30(abc, pos)
    for _ in range(1, ns_set_count):
        count, pos = _read_u30(abc, pos)
        for _ in range(count):
            _, pos = _read_u30(abc, pos)

    multiname_count, pos = _read_u30(abc, pos)
    multinames: list[dict[str, Any] | None] = [None]
    for _ in range(1, multiname_count):
        kind = abc[pos]
        pos += 1
        item: dict[str, Any] = {"kind": kind}
        if kind in (0x07, 0x0D):
            item["ns"], pos = _read_u30(abc, pos)
            item["name"], pos = _read_u30(abc, pos)
        elif kind in (0x0F, 0x10):
            item["name"], pos = _read_u30(abc, pos)
        elif kind in (0x11, 0x12):
            pass
        elif kind in (0x09, 0x0E):
            item["name"], pos = _read_u30(abc, pos)
            item["ns_set"], pos = _read_u30(abc, pos)
        elif kind in (0x1B, 0x1C):
            item["ns_set"], pos = _read_u30(abc, pos)
        elif kind == 0x1D:
            item["qname"], pos = _read_u30(abc, pos)
            count, pos = _read_u30(abc, pos)
            params: list[int] = []
            for _ in range(count):
                param, pos = _read_u30(abc, pos)
                params.append(param)
            item["params"] = params
        else:
            return b""
        multinames.append(item)

    def resolve_multiname(index: int) -> str:
        if not index or index >= len(multinames) or multinames[index] is None:
            return ""
        item = multinames[index] or {}
        kind = int(item.get("kind", 0))
        if kind in (0x07, 0x0D):
            namespace = namespaces[int(item.get("ns", 0))] if int(item.get("ns", 0)) < len(namespaces) else None
            namespace_name = strings[namespace[1]] if namespace and namespace[1] < len(strings) else ""
            local_name = strings[int(item.get("name", 0))] if int(item.get("name", 0)) < len(strings) else ""
            return f"{namespace_name}::{local_name}" if namespace_name else local_name
        if kind in (0x0F, 0x10, 0x09, 0x0E):
            name_index = int(item.get("name", 0))
            return strings[name_index] if name_index < len(strings) else ""
        if kind == 0x1D:
            return resolve_multiname(int(item.get("qname", 0)))
        return ""

    method_count, pos = _read_u30(abc, pos)
    for _ in range(method_count):
        param_count, pos = _read_u30(abc, pos)
        _, pos = _read_u30(abc, pos)
        for _ in range(param_count):
            _, pos = _read_u30(abc, pos)
        _, pos = _read_u30(abc, pos)
        flags = abc[pos]
        pos += 1
        if flags & 0x08:
            option_count, pos = _read_u30(abc, pos)
            for _ in range(option_count):
                _, pos = _read_u30(abc, pos)
                pos += 1
        if flags & 0x80:
            for _ in range(param_count):
                _, pos = _read_u30(abc, pos)

    metadata_count, pos = _read_u30(abc, pos)
    for _ in range(metadata_count):
        _, pos = _read_u30(abc, pos)
        item_count, pos = _read_u30(abc, pos)
        for _ in range(item_count):
            _, pos = _read_u30(abc, pos)
        for _ in range(item_count):
            _, pos = _read_u30(abc, pos)

    target_method_index: Optional[int] = None
    instance_count, pos = _read_u30(abc, pos)
    for _ in range(instance_count):
        name_index, pos = _read_u30(abc, pos)
        _, pos = _read_u30(abc, pos)
        flags = abc[pos]
        pos += 1
        if flags & 0x08:
            _, pos = _read_u30(abc, pos)
        interface_count, pos = _read_u30(abc, pos)
        for _ in range(interface_count):
            _, pos = _read_u30(abc, pos)
        _, pos = _read_u30(abc, pos)
        trait_count, pos = _read_u30(abc, pos)
        current_class_name = resolve_multiname(name_index)
        for _ in range(trait_count):
            trait_name_index, next_pos = _read_u30(abc, pos)
            kind_attr = abc[next_pos]
            kind = kind_attr & 0x0F
            trait_name = resolve_multiname(trait_name_index)
            working_pos = next_pos + 1
            if kind in (0, 6):
                _, working_pos = _read_u30(abc, working_pos)
                _, working_pos = _read_u30(abc, working_pos)
                value_index, working_pos = _read_u30(abc, working_pos)
                if value_index != 0:
                    working_pos += 1
            elif kind in (1, 2, 3):
                _, working_pos = _read_u30(abc, working_pos)
                method_index, working_pos = _read_u30(abc, working_pos)
                if current_class_name == class_name and trait_name.endswith(f"::{method_name}"):
                    target_method_index = method_index
            elif kind == 4:
                _, working_pos = _read_u30(abc, working_pos)
                _, working_pos = _read_u30(abc, working_pos)
            elif kind == 5:
                _, working_pos = _read_u30(abc, working_pos)
                _, working_pos = _read_u30(abc, working_pos)
            attrs = kind_attr >> 4
            if attrs & 0x04:
                metadata_items, working_pos = _read_u30(abc, working_pos)
                for _ in range(metadata_items):
                    _, working_pos = _read_u30(abc, working_pos)
            pos = working_pos

    for _ in range(instance_count):
        _, pos = _read_u30(abc, pos)
        trait_count, pos = _read_u30(abc, pos)
        for _ in range(trait_count):
            pos = _skip_abc_trait(abc, pos)

    script_count, pos = _read_u30(abc, pos)
    for _ in range(script_count):
        _, pos = _read_u30(abc, pos)
        trait_count, pos = _read_u30(abc, pos)
        for _ in range(trait_count):
            pos = _skip_abc_trait(abc, pos)

    if target_method_index is None:
        return b""

    body_count, pos = _read_u30(abc, pos)
    for _ in range(body_count):
        method_index, pos = _read_u30(abc, pos)
        _, pos = _read_u30(abc, pos)
        _, pos = _read_u30(abc, pos)
        _, pos = _read_u30(abc, pos)
        _, pos = _read_u30(abc, pos)
        code_length, pos = _read_u30(abc, pos)
        code = abc[pos: pos + code_length]
        pos += code_length
        exception_count, pos = _read_u30(abc, pos)
        for _ in range(exception_count):
            for _ in range(5):
                _, pos = _read_u30(abc, pos)
        trait_count, pos = _read_u30(abc, pos)
        for _ in range(trait_count):
            pos = _skip_abc_trait(abc, pos)
        if method_index == target_method_index:
            return code
    return b""


def _extract_literal_push_int_array_from_code(code: bytes, expected_count: int) -> list[int]:
    for index, opcode in enumerate(code):
        if opcode != 0x56 or index + 1 >= len(code):
            continue
        if code[index + 1] != expected_count:
            continue
        values: list[int] = []
        cursor = index - 1
        while cursor >= 1 and len(values) < expected_count:
            if code[cursor - 1] == 0x24:
                values.append(code[cursor])
                cursor -= 2
                continue
            if code[cursor - 1] == 0x25:
                values.append(code[cursor])
                cursor -= 2
                continue
            break
        if len(values) == expected_count:
            values.reverse()
            return values
    return []


def _extract_clan_stamina_key_from_swf_bytes(data: bytes) -> list[int]:
    abc = _extract_first_doabc_bytes(data)
    if not abc:
        return []
    code = _find_named_method_body_in_doabc(
        abc,
        class_name="ninjasaga.linkage::ClanPanel",
        method_name="ConfirmRestoreStamina",
    )
    if not code:
        return []
    values = _extract_literal_push_int_array_from_code(code, expected_count=16)
    if len(values) == 16 and all(0 <= value <= 255 for value in values):
        return values
    return []


def _fetch_clan_panel_swf_bytes() -> bytes:
    req = urllib_request.Request(
        CLAN_PANEL_SWF_URL,
        headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"},
    )
    with urllib_request.urlopen(req, timeout=12) as resp:
        return resp.read()


def _get_clan_panel_runtime_config(force_refresh: bool = False) -> tuple[str, list[int], list[int]]:
    global _clan_token_uniq_id_cache
    global _clan_battle_key_cache
    global _clan_stamina_key_cache
    if force_refresh:
        _clan_token_uniq_id_cache = None
        _clan_battle_key_cache = None
        _clan_stamina_key_cache = None
    if _clan_token_uniq_id_cache and _clan_battle_key_cache and _clan_stamina_key_cache:
        return (
            _clan_token_uniq_id_cache,
            list(_clan_battle_key_cache),
            list(_clan_stamina_key_cache),
        )
    with _clan_token_uniq_id_lock:
        if force_refresh:
            _clan_token_uniq_id_cache = None
            _clan_battle_key_cache = None
            _clan_stamina_key_cache = None
        if _clan_token_uniq_id_cache and _clan_battle_key_cache and _clan_stamina_key_cache:
            return (
                _clan_token_uniq_id_cache,
                list(_clan_battle_key_cache),
                list(_clan_stamina_key_cache),
            )
        try:
            raw = _fetch_clan_panel_swf_bytes()
            token = _extract_clan_token_uniq_id_from_swf_bytes(raw)
            battle_key = _extract_clan_battle_key_from_swf_bytes(raw)
            stamina_key = _extract_clan_stamina_key_from_swf_bytes(raw)
            if token:
                _clan_token_uniq_id_cache = token
            if battle_key:
                _clan_battle_key_cache = battle_key
            if stamina_key:
                _clan_stamina_key_cache = stamina_key
        except (urllib_error.URLError, TimeoutError, ValueError, OSError, zlib.error):
            pass
        token = _clan_token_uniq_id_cache or ""
        battle_key = list(_clan_battle_key_cache or DEFAULT_CLAN_BATTLE_KEY)
        stamina_key = list(_clan_stamina_key_cache or DEFAULT_CLAN_STAMINA_KEY)
        return token, battle_key, stamina_key


def _get_clan_token_uniq_id(force_refresh: bool = False) -> str:
    token, _, _ = _get_clan_panel_runtime_config(force_refresh=force_refresh)
    return token


def _get_clan_battle_key(force_refresh: bool = False) -> list[int]:
    _, battle_key, _ = _get_clan_panel_runtime_config(force_refresh=force_refresh)
    return list(battle_key or DEFAULT_CLAN_BATTLE_KEY)


def _get_clan_stamina_key(force_refresh: bool = False) -> list[int]:
    _, _, stamina_key = _get_clan_panel_runtime_config(force_refresh=force_refresh)
    return list(stamina_key or DEFAULT_CLAN_STAMINA_KEY)


class NinjaSagaClanWarEvent:
    def __init__(
        self,
        *,
        target_clan_id: Any | None = None,
        target_clan_name: str = "",
        auto_spend_token: bool = False,
        bleeding_mode: bool = False,
        manual_recruit: bool = False,
        manual_member_ids: Optional[list[Any]] = None,
        settings: Optional[dict[str, Any]] = None,
        force_refresh_token: bool = False,
        state_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        captcha_resume_event: Optional[threading.Event] = None,
        start_from_war_list_only: bool = False,
    ) -> None:
        if not isinstance(getattr(config, "login_data", None), dict):
            raise ValueError("NinjaSaga login data is missing")
        self.session_key = str(config.login_data.get("sessionkey") or "")
        if not self.session_key:
            raise ValueError("NinjaSaga session key is missing")
        merged = dict(NINJASAGA_CLAN_WAR_DEFAULT_SETTINGS)
        if isinstance(settings, dict):
            merged.update(settings)
        self.settings = merged
        self.target_clan_id = str(target_clan_id or "").strip()
        self.target_clan_name = str(target_clan_name or "").strip()
        self.auto_spend_token = bool(auto_spend_token)
        self.bleeding_mode = bool(bleeding_mode)
        self.manual_recruit = bool(manual_recruit)
        self.manual_member_ids = [str(item).strip() for item in (manual_member_ids or []) if str(item).strip()][:2]
        self.selected_recruiters: list[str] = []
        self.bleeding_reputation_gained = False
        self._battle_defender_strategy_index = 0
        self.state_callback = state_callback
        self.captcha_resume_event = captcha_resume_event
        self._awaiting_first_post_captcha_response = False
        self._resume_from_war_list_only = bool(start_from_war_list_only)
        self._cached_snapshot: dict[str, Any] | None = None
        token, battle_key, stamina_key = _get_clan_panel_runtime_config(force_refresh=force_refresh_token)
        self.clan_token_id = str(token or "").strip()
        self.clan_battle_key = list(battle_key or DEFAULT_CLAN_BATTLE_KEY)
        self.clan_stamina_key = list(stamina_key or DEFAULT_CLAN_STAMINA_KEY)
        if not self.clan_token_id:
            raise ValueError("clan_token_uniq_id not found")

    def _refresh_session_key(self) -> bool:
        latest = ""
        if isinstance(getattr(config, "login_data", None), dict):
            latest = str(
                config.login_data.get("sessionkey")
                or config.login_data.get("session_key")
                or config.login_data.get("session")
                or ""
            )
        if not latest:
            return False
        changed = latest != self.session_key
        self.session_key = latest
        if changed:
            print("Clan War session key refreshed after captcha")
        return True

    @staticmethod
    def _check_stop_event() -> bool:
        if hasattr(config, "stop_event") and config.stop_event.is_set():
            print("NinjaSaga Clan War worker loading...")
            return True
        return False

    def _wait_with_stop_check(self, seconds: int) -> bool:
        for _ in range(max(0, int(seconds))):
            if self._check_stop_event():
                return False
            time.sleep(1)
        return True

    def _wait_amf_delay(self) -> bool:
        delay = max(0, int(self.settings.get("amf_call_delay_seconds", 1)))
        if delay <= 0:
            return True
        return self._wait_with_stop_check(delay)

    def _emit_state(self, **updates: Any) -> None:
        if not self.state_callback:
            return
        try:
            self.state_callback(updates)
        except Exception:
            pass

    @staticmethod
    def _format_debug_payload(payload: Any, limit: int = 2500) -> str:
        try:
            import json

            text = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
        except Exception:
            text = repr(payload)
        if len(text) > limit:
            return text[:limit] + "... [truncated]"
        return text

    def _wait_for_captcha_resolution(self, message: str) -> bool:
        print(message)
        self._emit_state(captcha_required=True, captcha_message=message, running=True)
        if self.captcha_resume_event:
            self.captcha_resume_event.clear()

        while True:
            if self._check_stop_event():
                self._emit_state(captcha_required=False, captcha_message="", running=False)
                return False
            if self.captcha_resume_event and self.captcha_resume_event.is_set():
                self.captcha_resume_event.clear()
                self._awaiting_first_post_captcha_response = True
                self._resume_from_war_list_only = False
                self.settings["amf_call_delay_seconds"] = 2
                self._emit_state(captcha_required=False, captcha_message="", running=True)
                post_captcha_delay = max(0, int(self.settings.get("post_captcha_resume_delay_seconds", self.settings.get("refresh_delay_seconds", 4))))
                if not self._wait_with_stop_check(post_captcha_delay):
                    return False
                return True
            time.sleep(1)

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _prefer_numeric_or_text(value: Any, default: Any = 0) -> Any:
        if value in (None, ""):
            return default
        try:
            return int(value)
        except Exception:
            return str(value)

    def _extract_first(self, payload: Any, *names: str, default: Any = None) -> Any:
        queue = [payload]
        seen: set[int] = set()
        lowered = tuple(name.lower() for name in names)
        while queue:
            current = queue.pop(0)
            obj_id = id(current)
            if obj_id in seen:
                continue
            seen.add(obj_id)
            if isinstance(current, dict):
                for key, value in current.items():
                    key_str = str(key).lower()
                    if key_str in lowered:
                        return value
                queue.extend(current.values())
            elif isinstance(current, list):
                queue.extend(current)
        return default

    def _extract_list_of_dicts(self, payload: Any, preferred_keys: tuple[str, ...]) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            for key in preferred_keys:
                value = payload.get(key)
                if isinstance(value, dict):
                    value = list(value.values())
                if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                    return value
            for value in payload.values():
                result = self._extract_list_of_dicts(value, preferred_keys)
                if result:
                    return result
        elif isinstance(payload, list):
            if payload and all(isinstance(item, dict) for item in payload):
                return payload
            for item in payload:
                result = self._extract_list_of_dicts(item, preferred_keys)
                if result:
                    return result
        return []

    def _extract_candidate_dict_lists(self, payload: Any) -> list[list[dict[str, Any]]]:
        candidates: list[list[dict[str, Any]]] = []

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for item in value.values():
                    visit(item)
                return
            if isinstance(value, list):
                dict_items = [item for item in value if isinstance(item, dict)]
                if dict_items:
                    candidates.append(dict_items)
                for item in value:
                    visit(item)

        visit(payload)
        return candidates

    def get_clan_status(self) -> Any:
        if not self._wait_amf_delay():
            raise RuntimeError("Clan War stopped before ClanService.getClanStatus")
        return amf_req._call_service("ClanService.getClanStatus", [self.session_key])

    def get_clan(self) -> Any:
        if not self._wait_amf_delay():
            raise RuntimeError("Clan War stopped before ClanService.getClan")
        return amf_req._call_service("ClanService.getClan", [self.session_key])

    def get_war_list(self) -> Any:
        if not self._wait_amf_delay():
            raise RuntimeError("Clan War stopped before ClanService.getWarList")
        return amf_req._call_service("ClanService.getWarList", [self.session_key])

    def get_member_list_raw(self) -> Any:
        if not self._wait_amf_delay():
            raise RuntimeError("Clan War stopped before ClanWar.getMemberList")
        return amf_req._call_service("ClanWar.getMemberList", [self.session_key])

    @staticmethod
    def _bool_to_actionscript(value: bool) -> str:
        return "true" if bool(value) else "false"

    def _log_battle_defender_debug(
        self,
        *,
        strategy: str,
        sequence_counter: int,
        seq: str,
        inner_hash: str,
        request_hash: str,
        encrypted: str,
        fk: str,
        clan_id: Any,
        clan_name: str,
        selected_member_str: str,
        quick_battle: bool,
    ) -> None:
        payload = {
            "service": "ClanWar.getBattleDefender",
            "strategy": strategy,
            "session_key_prefix": self.session_key[:16],
            "sequence_counter": sequence_counter,
            "seq": seq,
            "inner_hash": inner_hash,
            "request_hash": request_hash,
            "encrypted_nonce": encrypted[:32],
            "encrypted_body": encrypted[32:],
            "encrypted": encrypted,
            "fk": fk,
            "clan_id": int(clan_id),
            "clan_name": str(clan_name or ""),
            "selected_member_str": str(selected_member_str or ""),
            "quick_battle": bool(quick_battle),
        }
        print("Clan War debug | getBattleDefender request:")
        print(self._format_debug_payload(payload, limit=6000))

    def _log_battle_defender_response_debug(self, response: Any) -> None:
        print("Clan War debug | getBattleDefender response:")
        print(self._format_debug_payload(response, limit=6000))

    def _log_post_battle_status_debug(self, status_snapshot: dict[str, Any]) -> None:
        print("Clan War debug | post-battle clan status:")
        print(self._format_debug_payload(status_snapshot, limit=6000))

    @staticmethod
    def _battle_defender_strategies_for_cycle(start_index: int) -> list[str]:
        strategies = list(CLAN_BATTLE_DEFENDER_STRATEGIES)
        if not strategies:
            return []
        normalized_index = max(0, int(start_index)) % len(strategies)
        return strategies[normalized_index:] + strategies[:normalized_index]

    def _build_buy_stamina_security_values(self) -> tuple[str, int]:
        timestamp = int(time.time())
        source = f"{self.session_key[:8]};{timestamp}"
        source_bytes = source.encode("utf-8")
        salt = bytes(random.randint(0, 255) for _ in range(11))
        payload = bytearray(salt + source_bytes)
        rolling = 0
        key = list(self.clan_stamina_key or DEFAULT_CLAN_STAMINA_KEY)
        for idx in range(len(payload)):
            rolling = (rolling + payload[idx]) & 0xFF
            payload[idx] ^= key[(idx + rolling) % 16]
        return payload.hex(), timestamp

    def _build_battle_defender_security_values(
        self,
        clan_id: Any,
        selected_member_str: str,
        quick_battle: bool,
        strategy: str,
    ) -> tuple[int, str, str, str, str, str, str]:
        clan_id_text = str(clan_id or "")
        member_text = str(selected_member_str or "")
        quick_battle_text = self._bool_to_actionscript(bool(quick_battle))
        sequence_counter, seq_value, seq = amf_req._next_sequence_state()
        if strategy.startswith("legacy_inner"):
            inner_source = f"{clan_id_text}{member_text}{self.session_key}"
        else:
            inner_source = f"{clan_id_text}{member_text}{quick_battle_text}"
        inner_hash = amf_req.get_hash(self.session_key, inner_source)
        request_suffix = seq_value if strategy.endswith("rawseq") else seq
        request_hash = amf_req.get_hash(self.session_key, f"{inner_hash}{request_suffix}")
        payload = f"{request_hash}|{clan_id_text}|{member_text}|{quick_battle_text}"
        nonce = [random.randint(0, 255) for _ in range(16)]
        state = list(range(256))
        key = list(self.clan_battle_key or DEFAULT_CLAN_BATTLE_KEY)
        j = 0
        for idx in range(256):
            j = (j + state[idx] + key[idx % 16] + nonce[idx % 16]) % 256
            state[idx], state[j] = state[j], state[idx]

        encrypted_bytes = bytearray(payload.encode("utf-8"))
        i = 0
        j = 0
        for idx in range(len(encrypted_bytes)):
            i = (i + 1) % 256
            j = (j + state[i]) % 256
            state[i], state[j] = state[j], state[i]
            encrypted_bytes[idx] ^= state[(state[i] + state[j]) % 256]

        encrypted = "".join(f"{value:02x}" for value in nonce) + "".join(f"{value:02x}" for value in encrypted_bytes)

        key_stream = bytearray("".join(chr(value) for value in key).encode("utf-8"))
        for idx in range(len(key_stream)):
            i = (i + 1) % 256
            j = (j + state[i]) % 256
            state[i], state[j] = state[j], state[i]
            key_stream[idx] ^= state[(state[i] + state[j]) % 256]
        fk = "".join(f"{value:02x}" for value in key_stream)
        return sequence_counter, seq, inner_hash, request_hash, encrypted, fk, strategy

    def buy_stamina(self) -> Any:
        if not self._wait_amf_delay():
            raise RuntimeError("Clan War stopped before ClanService.buyStamina")
        encrypted, timestamp = self._build_buy_stamina_security_values()
        return amf_req._call_service("ClanService.buyStamina", [self.session_key, encrypted, timestamp])

    def get_battle_defender(
        self,
        clan_id: Any,
        clan_name: str,
        selected_member_str: str,
        quick_battle: bool = True,
        strategy: Optional[str] = None,
    ) -> Any:
        if not self._wait_amf_delay():
            raise RuntimeError("Clan War stopped before ClanWar.getBattleDefender")
        strategy_name = str(strategy or CLAN_BATTLE_DEFENDER_STRATEGIES[self._battle_defender_strategy_index])
        sequence_counter, seq, inner_hash, request_hash, encrypted, fk, strategy_name = self._build_battle_defender_security_values(
            clan_id,
            selected_member_str,
            quick_battle,
            strategy_name,
        )
        self._log_battle_defender_debug(
            strategy=strategy_name,
            sequence_counter=sequence_counter,
            seq=seq,
            inner_hash=inner_hash,
            request_hash=request_hash,
            encrypted=encrypted,
            fk=fk,
            clan_id=clan_id,
            clan_name=clan_name,
            selected_member_str=selected_member_str,
            quick_battle=quick_battle,
        )
        return amf_req._call_service(
            "ClanWar.getBattleDefender",
            [
                self.session_key,
                seq,
                encrypted,
                int(clan_id),
                str(clan_name or ""),
                selected_member_str,
                bool(quick_battle),
                fk,
            ],
        )

    def _sanitize_war_item(self, item: dict[str, Any]) -> dict[str, Any]:
        clan_id = self._extract_first(item, "id", "clan_id", default="")
        return {
            "id": str(clan_id or "").strip(),
            "name": str(self._extract_first(item, "name", "clan_name", default="Unknown Clan") or "Unknown Clan"),
            "reputation": self._prefer_numeric_or_text(self._extract_first(item, "reputation", default=0), 0),
            "master": str(self._extract_first(item, "master", "master_name", default="-") or "-"),
            "members": self._prefer_numeric_or_text(self._extract_first(item, "member", "member_total", "members", default="?"), "?"),
            "raw": item,
        }

    def _sanitize_member_item(self, item: dict[str, Any]) -> dict[str, Any]:
        member_id = self._extract_first(item, "id", "char_id", "uid", default="")
        return {
            "id": str(member_id or "").strip(),
            "name": str(self._extract_first(item, "name", "character_name", default="Unknown") or "Unknown"),
            "level": self._safe_int(self._extract_first(item, "level", "character_level", default=0)),
            "stamina": self._safe_int(self._extract_first(item, "stamina", default=0)),
            "reputation_gain": self._safe_int(self._extract_first(item, "reputation_gain", default=0)),
            "raw": item,
        }

    def parse_status_snapshot(self, payload: Any) -> dict[str, Any]:
        clan_name = self._extract_first(payload, "name", "clan_name", default="Unknown Clan")
        clan_id = self._extract_first(payload, "id", "clan_id", default="")
        reputation = self._safe_int(self._extract_first(payload, "reputation", default=0))
        stamina = self._safe_int(self._extract_first(payload, "character_stamina", "stamina", default=0))
        max_stamina = self._safe_int(self._extract_first(payload, "character_max_stamina", "max_stamina", default=0))
        prestige = self._prefer_numeric_or_text(self._extract_first(payload, "prestige", default="n/a"), "n/a")
        return {
            "clan": {
                "id": str(clan_id or "").strip(),
                "name": str(clan_name or "Unknown Clan"),
                "reputation": reputation,
            },
            "char": {
                "stamina": stamina,
                "max_stamina": max_stamina,
                "prestige": prestige,
            },
        }

    def parse_war_list(self, payload: Any) -> list[dict[str, Any]]:
        items = self._extract_list_of_dicts(payload, ("war_list",))
        if not items:
            for candidate in self._extract_candidate_dict_lists(payload):
                parsed = [self._sanitize_war_item(item) for item in candidate]
                parsed = [item for item in parsed if item.get("id") or item.get("name") != "Unknown Clan"]
                if parsed:
                    return parsed
        return [self._sanitize_war_item(item) for item in items]

    def parse_member_list(self, payload: Any) -> list[dict[str, Any]]:
        items = self._extract_list_of_dicts(payload, ("clan_members", "member_list"))
        if not items:
            for candidate in self._extract_candidate_dict_lists(payload):
                parsed = [self._sanitize_member_item(item) for item in candidate]
                parsed = [item for item in parsed if item.get("id") or item.get("name") != "Unknown"]
                if parsed:
                    return parsed
        return [self._sanitize_member_item(item) for item in items]

    def choose_recruiters(self, members: list[dict[str, Any]]) -> list[str]:
        if not self.bleeding_mode or self.bleeding_reputation_gained:
            self.selected_recruiters = []
            return []
        if self.manual_recruit and self.manual_member_ids:
            chosen = self.manual_member_ids[:2]
        else:
            sorted_members = sorted(
                members,
                key=lambda member: (self._safe_int(member.get("stamina")), self._safe_int(member.get("reputation_gain")), str(member.get("name") or "")),
                reverse=True,
            )
            chosen = [member["id"] for member in sorted_members if member.get("id")][:2]
        self.selected_recruiters = chosen
        return chosen

    def snapshot(self) -> dict[str, Any]:
        status_payload = self.get_clan_status()
        clan_payload = self.get_clan()
        status = self.parse_status_snapshot({"status": status_payload, "clan": clan_payload})
        war_list = self.parse_war_list(self.get_war_list())
        member_list = self.parse_member_list(self.get_member_list_raw())
        selected = self.choose_recruiters(member_list)
        return {
            **status,
            "war_list": war_list,
            "member_list": member_list,
            "selected_recruiters": selected,
            "bleeding_reputation_gained": self.bleeding_reputation_gained,
        }

    def snapshot_after_captcha(self) -> dict[str, Any]:
        base = dict(self._cached_snapshot or {})
        war_list = self.parse_war_list(self.get_war_list())
        member_list = self.parse_member_list(self.get_member_list_raw())
        selected = self.choose_recruiters(member_list)
        merged = {
            **base,
            "war_list": war_list,
            "member_list": member_list,
            "selected_recruiters": selected,
            "bleeding_reputation_gained": self.bleeding_reputation_gained,
        }
        return merged

    def _find_target_clan(self, war_list: list[dict[str, Any]], own_clan_id: str) -> Optional[dict[str, Any]]:
        if self.target_clan_id:
            for clan in war_list:
                if clan.get("id") == self.target_clan_id:
                    return clan
        for clan in war_list:
            if clan.get("id") and clan.get("id") != own_clan_id:
                return clan
        return None

    def _battle_reputation_gain(self, response: Any) -> int:
        return self._safe_int(self._extract_first(response, "rep_gain", "reputation_gain", "gain", default=0))

    def _extract_battle_response_stamina(self, response: Any) -> Optional[int]:
        value = self._extract_first(response, "character_stamina", "stamina", default=None)
        if value in (None, ""):
            return None
        try:
            return int(value)
        except Exception:
            return None

    def _is_real_battle_success(self, response: Any, stamina_before: int, post_status: Optional[dict[str, Any]]) -> bool:
        response_stamina = self._extract_battle_response_stamina(response)
        if response_stamina is not None and response_stamina < stamina_before:
            return True
        if isinstance(post_status, dict):
            post_stamina = self._safe_int(post_status.get("char", {}).get("stamina"), stamina_before)
            if post_stamina < stamina_before:
                return True
        if self._battle_reputation_gain(response) > 0:
            return True
        if self._safe_int(self._extract_first(response, "prestige_gain", default=0)) > 0:
            return True
        return False

    def _log_battle_result(self, response: Any, target_name: str, stamina_before: int = 0) -> None:
        result_code = self._safe_int(self._extract_first(response, "result", default=-1))
        battle_result = self._safe_int(self._extract_first(response, "battle_result", default=-1))
        rep_gain = self._battle_reputation_gain(response)
        prestige_gain = self._safe_int(self._extract_first(response, "prestige_gain", default=0))
        stamina_after = self._extract_battle_response_stamina(response)
        stamina_text = str(stamina_after) if stamina_after is not None else f"unknown (last snapshot {stamina_before})"
        expected_stamina_after = max(0, stamina_before - CLAN_BATTLE_STAMINA_COST)
        expected_stamina_text = str(expected_stamina_after)
        if result_code == 0:
            print(f"Clan War quick victory vs {target_name}: REP +{rep_gain}, Prestige +{prestige_gain}, Stamina left {stamina_text}, expected local stamina {expected_stamina_text}")
        elif result_code == 2:
            outcome = "win" if battle_result == 1 else "lose"
            print(f"Clan War quick battle vs {target_name}: {outcome}, REP +{rep_gain}, Prestige +{prestige_gain}, Stamina left {stamina_text}, expected local stamina {expected_stamina_text}")
        elif result_code == 1:
            print(f"Clan War defender loaded a manual battle for {target_name}; quick battle path is not available for this target, Stamina left {stamina_text}, expected local stamina {expected_stamina_text}")
        else:
            print(f"Clan War unexpected battle response for {target_name}: {response} | Stamina left {stamina_text}, expected local stamina {expected_stamina_text}")

    def _has_captcha(self, payload: Any) -> bool:
        value = self._extract_first(payload, "show_captcha", default=False)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes"}

    def run(self) -> None:
        if self._resume_from_war_list_only:
            initial = self.snapshot_after_captcha()
            self._resume_from_war_list_only = False
        else:
            initial = self.snapshot()
        clan_name = initial.get("clan", {}).get("name", "Unknown Clan")
        print(f"NinjaSaga Clan War ready for clan: {clan_name}")
        self._emit_state(snapshot=initial, running=True)

        while not self._check_stop_event():
            if self._resume_from_war_list_only:
                self._resume_from_war_list_only = False
                snapshot = self.snapshot_after_captcha()
            else:
                snapshot = self.snapshot()
            self._cached_snapshot = snapshot
            self._emit_state(snapshot=snapshot, running=True)
            stamina = self._safe_int(snapshot.get("char", {}).get("stamina"), 0)
            own_clan_id = str(snapshot.get("clan", {}).get("id") or "")
            war_list = snapshot.get("war_list") or []
            member_list = snapshot.get("member_list") or []

            if stamina < CLAN_BATTLE_STAMINA_COST:
                if self.auto_spend_token:
                    print("Clan War stamina below 10, trying to buy stamina...")
                    self.buy_stamina()
                    if not self._wait_with_stop_check(max(1, int(self.settings.get("buy_stamina_delay_seconds", 3)))):
                        return
                    continue
                print("Clan War stamina below 10 and auto spend is disabled. Stopping battle loop.")
                return

            target = self._find_target_clan(war_list, own_clan_id)
            if not target:
                print("No clan war target available right now, refreshing soon...")
                if not self._wait_with_stop_check(max(1, int(self.settings.get("refresh_delay_seconds", 4)))):
                    return
                continue

            target_id = target.get("id") or ""
            target_name = target.get("name") or "Unknown Clan"
            self.target_clan_id = str(target_id)
            self.target_clan_name = str(target_name)

            recruiters = self.choose_recruiters(member_list)
            recruiter_str = ",".join(recruiters) if recruiters else ""
            if recruiters:
                print(f"Clan War bleeding mode recruiters: {recruiter_str}")

            response = None
            post_status = None
            selected_strategy = ""
            for strategy_name in self._battle_defender_strategies_for_cycle(self._battle_defender_strategy_index):
                selected_strategy = strategy_name
                response = self.get_battle_defender(target_id, target_name, recruiter_str, True, strategy=strategy_name)
                self._log_battle_defender_response_debug(response)
                if self._has_captcha(response):
                    print("Clan War debug | captcha-trigger response:")
                    print(self._format_debug_payload(response))
                    message = "Clan War captcha required. Solve it in the panel captcha screen to continue."
                    if not self._wait_for_captcha_resolution(message):
                        return
                    response = None
                    break
                if self._awaiting_first_post_captcha_response:
                    self._awaiting_first_post_captcha_response = False
                    print("Clan War debug | first post-captcha response:")
                    print(self._format_debug_payload(response))
                self._log_battle_result(response, target_name, stamina_before=stamina)
                try:
                    post_status = self.parse_status_snapshot({"status": self.get_clan_status(), "clan": self.get_clan()})
                    self._log_post_battle_status_debug(post_status)
                except Exception as exc:
                    post_status = None
                    print(f"Clan War debug | post-battle status refresh failed: {exc}")
                if self._is_real_battle_success(response, stamina, post_status):
                    self._battle_defender_strategy_index = CLAN_BATTLE_DEFENDER_STRATEGIES.index(strategy_name)
                    print(f"Clan War strategy locked: {strategy_name}")
                    break
                print(f"Clan War strategy {strategy_name} did not consume stamina or gain rewards, trying next variant...")
            if response is None:
                continue

            rep_gain = self._battle_reputation_gain(response)
            if rep_gain > 0 and self.bleeding_mode and not self.bleeding_reputation_gained:
                self.bleeding_reputation_gained = True
                print("Bleeding mode: first reputation gain detected, stop using recruiters for next battles")

            if self._safe_int(self._extract_first(response, "result", default=-1)) == 1:
                print("Clan War quick path fell into manual defender battle; stopping loop here for safety")
                return

            if not self._wait_with_stop_check(max(1, int(self.settings.get("battle_delay_seconds", 8)))):
                return


def build_clan_war_snapshot(params: Optional[dict[str, Any]] = None, *, force_refresh_token: bool = False) -> dict[str, Any]:
    options = params if isinstance(params, dict) else {}
    event = NinjaSagaClanWarEvent(
        target_clan_id=options.get("target_clan_id"),
        target_clan_name=options.get("target_clan_name") or "",
        auto_spend_token=bool(options.get("auto_spend_token")),
        bleeding_mode=bool(options.get("bleeding_mode")),
        manual_recruit=bool(options.get("manual_recruit")),
        manual_member_ids=options.get("manual_member_ids") or [],
        settings=options.get("settings") or {},
        force_refresh_token=force_refresh_token,
    )
    return event.snapshot()


def clan_war_event(
    params: Optional[dict[str, Any]] = None,
    state_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    captcha_resume_event: Optional[threading.Event] = None,
    start_from_war_list_only: bool = False,
) -> None:
    options = params if isinstance(params, dict) else {}
    event = NinjaSagaClanWarEvent(
        target_clan_id=options.get("target_clan_id"),
        target_clan_name=options.get("target_clan_name") or "",
        auto_spend_token=bool(options.get("auto_spend_token")),
        bleeding_mode=bool(options.get("bleeding_mode")),
        manual_recruit=bool(options.get("manual_recruit")),
        manual_member_ids=options.get("manual_member_ids") or [],
        settings=options.get("settings") or {},
        state_callback=state_callback,
        captcha_resume_event=captcha_resume_event,
        start_from_war_list_only=start_from_war_list_only,
    )
    event.run()
