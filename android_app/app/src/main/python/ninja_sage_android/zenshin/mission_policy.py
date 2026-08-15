from __future__ import annotations

import json
import os
import re
from typing import Any

from ..core import config

NINJASAGA_DEFAULT_MISSION_ID = "msn2"

# Synced from NinjaSaga Game Client/ninjasaga/data/Data.as
GRADE_C_MISSION_ARR = [
    "msn2", "msn3", "msn4", "msn7", "msn8", "msn9", "msn10", "msn12", "msn13",
    "msn14", "msn15", "msn16", "msn17", "msn18", "msn19", "msn28", "msn29",
    "msn30", "msn31", "msn32", "msn33", "msn34", "msn39", "msn40", "msn41",
    "msn42", "msn43", "msn44", "msn45", "msn47", "msn48", "msn49", "msn53",
]
GRADE_B_MISSION_ARR = [
    "msn60", "msn61", "msn62", "msn63", "msn65", "msn67", "msn68", "msn69",
    "msn72", "msn73", "msn74", "msn75", "msn76", "msn77", "msn78", "msn79",
    "msn80", "msn81", "msn82", "msn83",
]
GRADE_A_MISSION_ARR = [
    "msn138", "msn139", "msn140", "msn141", "msn142", "msn143", "msn144",
    "msn148", "msn147", "msn214", "msn215", "msn216", "msn217", "msn218",
    "msn219", "msn220", "msn221", "msn222", "msn223",
]
EXAM_CHUNIN_ARR = ["msn55", "msn56", "msn57", "msn58", "msn59"]
EXAM_JOUNIN_ARR = ["msn132", "msn133", "msn134", "msn135", "msn136"]

NINJASAGA_MISSION_DATA_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "ninjasaga-mission-data.json")
)
NINJASAGA_MISSION_DATA_AS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "missiondata.as")
)
_MISSION_METADATA_CACHE: dict[str, dict[str, Any]] | None = None


def normalize_mission_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    return text


def account_type_from_login() -> int | None:
    login_data = getattr(config, "login_data", None)
    if not isinstance(login_data, dict):
        return None
    raw = login_data.get("account_type")
    try:
        return int(raw)
    except Exception:
        return None


def load_ninjasaga_mission_metadata() -> dict[str, dict[str, Any]]:
    global _MISSION_METADATA_CACHE
    if isinstance(_MISSION_METADATA_CACHE, dict):
        return _MISSION_METADATA_CACHE
    try:
        with open(NINJASAGA_MISSION_DATA_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            normalized = {
                str(mid).strip().lower(): value
                for mid, value in payload.items()
                if isinstance(value, dict)
            }
            _merge_as_mission_rewards(normalized)
            _MISSION_METADATA_CACHE = normalized
            return normalized
    except Exception:
        pass
    _MISSION_METADATA_CACHE = {}
    return _MISSION_METADATA_CACHE


def _merge_as_mission_rewards(metadata: dict[str, dict[str, Any]]) -> None:
    try:
        with open(NINJASAGA_MISSION_DATA_AS_FILE, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception:
        return

    entry_pattern = re.compile(
        r'MISSION_DATA\["(?P<id>[^"]+)"\]\s*=\s*\{(?P<body>.*?)\};',
        re.DOTALL,
    )
    for match in entry_pattern.finditer(source):
        mission_id = normalize_mission_id(match.group("id"))
        if not mission_id:
            continue
        body = match.group("body") or ""
        target = metadata.setdefault(mission_id, {"id": mission_id})
        tp_match = re.search(r'"tp"\s*:\s*(\d+)', body)
        sp_match = re.search(r'"sp"\s*:\s*(\d+)', body)
        if tp_match:
            try:
                target["tp"] = int(tp_match.group(1))
            except Exception:
                pass
        if sp_match:
            try:
                target["sp"] = int(sp_match.group(1))
            except Exception:
                pass


def mission_display_label(mission_id: Any, account_type: int | None = None) -> str:
    mission_key = normalize_mission_id(mission_id)
    if not mission_key:
        return str(mission_id)
    metadata = load_ninjasaga_mission_metadata().get(mission_key)
    if not isinstance(metadata, dict):
        return mission_key

    mission_name = str(metadata.get("name") or "").strip()
    mission_level = metadata.get("level")
    premium_only = bool(metadata.get("premium"))

    tags: list[str] = []
    if mission_level is not None:
        tags.append(f"LvReq {mission_level}")
    if premium_only:
        if account_type is not None and int(account_type) < 2:
            tags.append("Premium-Only")
        else:
            tags.append("Premium")

    if mission_name and tags:
        return f"{mission_key} ({mission_name} | {', '.join(tags)})"
    if mission_name:
        return f"{mission_key} ({mission_name})"
    if tags:
        return f"{mission_key} ({', '.join(tags)})"
    return mission_key


def mission_pool_for_level(level: int) -> list[str]:
    if 1 <= level <= 19:
        return GRADE_C_MISSION_ARR
    if 20 <= level <= 41:
        return GRADE_B_MISSION_ARR
    if 42 <= level <= 100:
        return GRADE_A_MISSION_ARR
    return []


def mission_numeric_id(mission_id: Any) -> int:
    text = normalize_mission_id(mission_id) or ""
    if text.startswith("msn") and text[3:].isdigit():
        return int(text[3:])
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def mission_required_level(mission_id: Any) -> int | None:
    mission_key = normalize_mission_id(mission_id)
    if not mission_key:
        return None
    metadata = load_ninjasaga_mission_metadata().get(mission_key)
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("level")
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def mission_reward_value(mission_id: Any, reward_key: str) -> int:
    mission_key = normalize_mission_id(mission_id)
    if not mission_key:
        return 0
    metadata = load_ninjasaga_mission_metadata().get(mission_key)
    if not isinstance(metadata, dict):
        return 0
    try:
        return int(metadata.get(str(reward_key).strip().lower()) or 0)
    except Exception:
        return 0


def is_mission_account_eligible(mission_id: Any, account_type: int | None) -> bool:
    mission_key = normalize_mission_id(mission_id)
    if not mission_key:
        return False
    metadata = load_ninjasaga_mission_metadata().get(mission_key)
    if not isinstance(metadata, dict):
        return True
    premium_only = bool(metadata.get("premium"))
    if not premium_only:
        return True
    return account_type is not None and int(account_type) >= 2


def is_mission_auto_eligible(mission_id: Any, account_type: int | None) -> bool:
    mission_key = normalize_mission_id(mission_id)
    if not mission_key:
        return False
    metadata = load_ninjasaga_mission_metadata().get(mission_key)
    if not isinstance(metadata, dict):
        return True

    grade = str(metadata.get("grade") or "").strip()
    if not grade:
        return False
    if bool(metadata.get("daily")):
        return False

    try:
        xp_value = int(metadata.get("xp") or 0)
    except Exception:
        xp_value = 0
    try:
        gold_value = int(metadata.get("gold") or 0)
    except Exception:
        gold_value = 0
    if xp_value <= 0 and gold_value <= 0:
        return False

    if not is_mission_account_eligible(mission_key, account_type):
        return False
    return True


def pick_auto_mission(level: int, account_type: int | None = None) -> str:
    resolved_level = int(level)
    pool = mission_pool_for_level(resolved_level)
    if not pool:
        return NINJASAGA_DEFAULT_MISSION_ID

    eligible_pool = [mid for mid in pool if is_mission_auto_eligible(mid, account_type)]
    if not eligible_pool:
        eligible_pool = [mid for mid in pool if is_mission_account_eligible(mid, account_type)]
    if not eligible_pool:
        eligible_pool = list(pool)

    candidates: list[tuple[int, int, str]] = []
    for mission_id in eligible_pool:
        req_level = mission_required_level(mission_id)
        if req_level is None:
            req_level = 0
        if req_level <= resolved_level:
            candidates.append((req_level, -mission_numeric_id(mission_id), mission_id))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][2]

    eligible_pool.sort(key=mission_numeric_id)
    return eligible_pool[0] if eligible_pool else NINJASAGA_DEFAULT_MISSION_ID


def pick_training_mission(
    level: int,
    reward_key: str,
    reward_value: int,
    account_type: int | None = None,
) -> str | None:
    mission_ids = list_training_missions(reward_key, reward_value, account_type=account_type)
    resolved_level = int(level)
    candidates: list[tuple[int, int, str]] = []
    fallback: list[tuple[int, int, str]] = []
    for mission_id in mission_ids:
        req_level = mission_required_level(mission_id)
        if req_level is None:
            req_level = 0
        row = (req_level, -mission_numeric_id(mission_id), mission_id)
        fallback.append(row)
        if req_level <= resolved_level:
            candidates.append(row)

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][2]
    if fallback:
        fallback.sort(reverse=True)
        return fallback[0][2]
    return None


def list_training_missions(
    reward_key: str,
    reward_value: int,
    account_type: int | None = None,
) -> list[str]:
    reward_name = str(reward_key).strip().lower()
    desired_value = int(reward_value)
    matches: list[str] = []
    for mission_id, metadata in load_ninjasaga_mission_metadata().items():
        if not isinstance(metadata, dict):
            continue
        if mission_reward_value(mission_id, reward_name) != desired_value:
            continue
        if not is_mission_account_eligible(mission_id, account_type):
            continue
        matches.append(mission_id)
    matches.sort(key=mission_numeric_id)
    return matches
