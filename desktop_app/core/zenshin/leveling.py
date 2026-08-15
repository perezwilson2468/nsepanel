import json
import os
import time
import re
import random
from typing import Any

from .. import config
from . import amf_req
from . import mission_policy, progress_parser, rate_control, recovery, anti_detection

NINJASAGA_DEFAULT_MISSION_ID = "msn2"
NINJASAGA_DEFAULT_XP_GAIN = 0
NINJASAGA_DEFAULT_GOLD_GAIN = 0
NINJASAGA_STOP_POLL_SECONDS = 0.2

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
EXAM_SPECIAL_JOUNIN_ARR = [
    "msn200", "msn205", "msn202", "msn206", "msn203", "msn207", "msn204",
    "msn208", "msn201", "msn209", "msn210", "msn211", "msn212",
]
EXAM_SPECIAL_JOUNIN_ARR_EASY = [
    "msn226", "msn227", "msn228", "msn229", "msn230", "msn231", "msn232",
    "msn233", "msn234", "msn235", "msn236", "msn237", "msn238",
]
EXAM_TUTOR_ARR = [
    "msn266", "msn259", "msn267", "msn260", "msn268", "msn261", "msn270",
    "msn262", "msn269", "msn263", "msn264", "msn265",
]
EXAM_TUTOR_ARR_EASY = [
    "msn250", "msn252", "msn249", "msn253", "msn248", "msn254", "msn247",
    "msn255", "msn251", "msn256", "msn257", "msn258",
]
TP_TRAINING_MISSIONS = ["msn170", "msn171", "msn172", "msn173", "msn174"]
EXAM_FIXED_ACTION_DELAY_SECONDS = 30
SPECIAL_JOUNIN_CLASS_SKILL_ARR = ["skill2002", "skill2004", "skill2001", "skill2003", "skill2000"]


def _runtime_game_label() -> str:
    current = config.get_current_base_game()
    return str(current.get("label") or "NinjaSaga")


def _is_zenshin_runtime() -> bool:
    current = config.get_current_base_game()
    return str(current.get("id") or "") == "zenshin"

# Synced from NinjaSaga Game Client/ninjasaga/data/RankData.as
RANK_STUDENT = 0
RANK_GENIN = 1
RANK_CHUNIN = 2
RANK_CHUNIN_TALENTED = 3
RANK_JOUNIN = 4
RANK_JOUNIN_TALENTED = 5
RANK_SPECIAL_JOUNIN = 6
RANK_SPECIAL_JOUNIN_TALENTED = 7
RANK_TUTOR = 8
RANK_TUTOR_SENIOR = 9

GENIN_LEVEL_CAP = 20
CHUNIN_LEVEL_CAP = 40
JOUNIN_LEVEL_CAP = 60
SPECIAL_JOUNIN_LEVEL_CAP = 80
TUTOR_LEVEL_CAP = 100

RANK_NAME_BY_ID = {
    RANK_STUDENT: "Student",
    RANK_GENIN: "Genin",
    RANK_CHUNIN: "Chunin",
    RANK_CHUNIN_TALENTED: "Tensai Chunin",
    RANK_JOUNIN: "Jounin",
    RANK_JOUNIN_TALENTED: "Tensai Jounin",
    RANK_SPECIAL_JOUNIN: "Special Jounin",
    RANK_SPECIAL_JOUNIN_TALENTED: "Tensai Special Jounin",
    RANK_TUTOR: "Ninja Tutor",
    RANK_TUTOR_SENIOR: "Tensai Ninja Tutor",
}

NINJASAGA_MISSION_DATA_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "ninjasaga-mission-data.json")
)
_MISSION_METADATA_CACHE: dict[str, dict[str, Any]] | None = None


def _stop_requested() -> bool:
    stop_event = getattr(config, "stop_event", None)
    return bool(stop_event and stop_event.is_set())


def _extract_char_id(char_data: dict[str, Any] | None) -> Any:
    return progress_parser.extract_character_id(char_data)


def _load_ninjasaga_mission_metadata() -> dict[str, dict[str, Any]]:
    return mission_policy.load_ninjasaga_mission_metadata()


def _account_type_from_login() -> int | None:
    return mission_policy.account_type_from_login()


def _mission_display_label(mission_id: Any, account_type: int | None = None) -> str:
    return mission_policy.mission_display_label(mission_id, account_type=account_type)


def _extract_char_level(char_data: dict[str, Any] | None) -> int:
    return progress_parser.extract_character_level(char_data, default=1)


def _resolve_current_character() -> tuple[Any, int]:
    snapshot = getattr(config, "char_data", None)
    char_id = _extract_char_id(snapshot)
    char_level = _extract_char_level(snapshot)
    if char_id is not None:
        return char_id, char_level

    chars = amf_req.get_all_characters()
    rows = []
    if isinstance(chars, dict):
        rows = chars.get("account_data") or chars.get("characters") or []
    if not rows:
        raise ValueError(f"No {_runtime_game_label()} characters available for leveling")

    first = rows[0]
    if isinstance(first, dict):
        char_id = _extract_char_id(first)
        char_level = _extract_char_level(first)
    elif isinstance(first, (list, tuple)):
        char_id = first[0] if first else None
        char_level = int(first[2]) if len(first) > 2 and str(first[2]).isdigit() else 1
    else:
        char_id = first
        char_level = 1

    if char_id is None:
        raise ValueError(f"Could not resolve {_runtime_game_label()} character ID for leveling")
    return char_id, char_level


def _extract_char_rank(char_data: dict[str, Any] | None):
    if not isinstance(char_data, dict):
        return None
    value = None
    # Direct shape
    for key in ("character_rank", "rank", "current_rank", "rank_id"):
        if char_data.get(key) is not None:
            value = char_data.get(key)
            break
    # Nested shapes from NinjaSaga responses
    if value is None:
        for container_key in ("character_data", "data", "character", "result"):
            nested = char_data.get(container_key)
            if not isinstance(nested, dict):
                continue
            for key in ("character_rank", "rank", "current_rank", "rank_id"):
                if nested.get(key) is not None:
                    value = nested.get(key)
                    break
            if value is not None:
                break
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _resolve_char_rank_with_refresh(char_id: Any, fallback_data: dict[str, Any] | None = None):
    rank_value = _extract_char_rank(fallback_data)
    if rank_value is not None:
        return _effective_rank_from_snapshot(fallback_data, rank_value)
    try:
        refreshed = amf_req.get_character_data(
            char_id,
            include_system_data=False,
            include_extra_data=False,
        )
    except Exception:
        return None
    if isinstance(refreshed, dict):
        config.char_data = refreshed
        return _effective_rank_from_snapshot(refreshed, _extract_char_rank(refreshed))
    return None


def _refresh_character_snapshot(char_id: Any) -> dict[str, Any] | None:
    try:
        refreshed = amf_req.get_character_data(
            char_id,
            include_system_data=False,
            include_extra_data=False,
        )
    except Exception:
        return None
    if isinstance(refreshed, dict):
        config.char_data = refreshed
        return refreshed
    return None


def _extract_char_control(char_data: dict[str, Any] | None):
    if not isinstance(char_data, dict):
        return None
    value = None
    for key in ("character_control", "control", "class_control", "class_id"):
        if char_data.get(key) is not None:
            value = char_data.get(key)
            break
    if value is None:
        for container_key in ("character_data", "data", "character", "result"):
            nested = char_data.get(container_key)
            if not isinstance(nested, dict):
                continue
            for key in ("character_control", "control", "class_control", "class_id"):
                if nested.get(key) is not None:
                    value = nested.get(key)
                    break
            if value is not None:
                break
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _effective_rank_from_snapshot(
    char_data: dict[str, Any] | None,
    rank_value: int | None,
) -> int | None:
    effective_rank = rank_value
    control_value = _extract_char_control(char_data)
    level_value = _extract_char_level(char_data)
    if (
        control_value is not None
        and control_value > 0
        and level_value >= JOUNIN_LEVEL_CAP
        and (effective_rank is None or effective_rank < RANK_SPECIAL_JOUNIN)
    ):
        return RANK_SPECIAL_JOUNIN
    return effective_rank


def _promote_runtime_rank_snapshot(target_rank: int) -> None:
    if not isinstance(getattr(config, "char_data", None), dict):
        return
    payload = config.char_data
    for key in ("character_rank", "rank", "current_rank", "rank_id"):
        if key in payload or key in {"character_rank", "rank"}:
            payload[key] = target_rank
    for container_key in ("character_data", "data", "character", "result"):
        nested = payload.get(container_key)
        if not isinstance(nested, dict):
            continue
        for key in ("character_rank", "rank", "current_rank", "rank_id"):
            if key in nested or key in {"character_rank", "rank"}:
                nested[key] = target_rank


def _resolve_char_control_with_refresh(char_id: Any, fallback_data: dict[str, Any] | None = None):
    control_value = _extract_char_control(fallback_data)
    if control_value is not None:
        return control_value
    try:
        refreshed = amf_req.get_character_data(
            char_id,
            include_system_data=False,
            include_extra_data=False,
        )
    except Exception:
        return None
    if isinstance(refreshed, dict):
        config.char_data = refreshed
        return _extract_char_control(refreshed)
    return None


def _mission_numeric_id(mission_id: Any) -> int:
    return mission_policy.mission_numeric_id(mission_id)


def _mission_required_level(mission_id: Any) -> int | None:
    return mission_policy.mission_required_level(mission_id)


def _is_mission_account_eligible(mission_id: Any, account_type: int | None) -> bool:
    return mission_policy.is_mission_account_eligible(mission_id, account_type)


def _is_mission_auto_eligible(mission_id: Any, account_type: int | None) -> bool:
    return mission_policy.is_mission_auto_eligible(mission_id, account_type)


def _pick_auto_mission(level: int, account_type: int | None = None) -> str:
    return mission_policy.pick_auto_mission(level, account_type=account_type)


def _mission_pool_for_level(level: int) -> list[str]:
    return mission_policy.mission_pool_for_level(level)


def _pick_training_mission(
    level: int,
    reward_key: str,
    reward_value: int,
    account_type: int | None = None,
) -> str | None:
    return mission_policy.pick_training_mission(
        level,
        reward_key=reward_key,
        reward_value=reward_value,
        account_type=account_type,
    )


def _mission_reward_value(mission_id: Any, reward_key: str) -> int:
    return mission_policy.mission_reward_value(mission_id, reward_key)


def _list_training_missions(
    reward_key: str,
    reward_value: int,
    account_type: int | None = None,
) -> list[str]:
    return mission_policy.list_training_missions(
        reward_key,
        reward_value,
        account_type=account_type,
    )


def _extract_training_reward(update_result: dict[str, Any], reward_key: str) -> int:
    reward_name = str(reward_key or "").strip().lower()
    direct_key_map = {
        "tp": ("tp_reward",),
        "ss": ("ss_reward",),
    }
    for key in direct_key_map.get(reward_name, ()):
        try:
            value = int(update_result.get(key) or 0)
        except Exception:
            value = 0
        if value > 0:
            return value

    result = update_result.get("result")
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


def _rank_name(rank_value: int | None) -> str:
    if rank_value is None:
        return "Unknown"
    return RANK_NAME_BY_ID.get(rank_value, f"Rank {rank_value}")


def _exam_mode() -> str:
    # Rank exams are hard-only.
    return "hard"


def _exam_missions_by_mode(easy_missions: list[str], hard_missions: list[str]) -> list[str]:
    return list(hard_missions if _exam_mode() == "hard" else easy_missions)


def _special_jounin_class_choice() -> tuple[int, str]:
    state = getattr(config, "zenshin_state", None)
    class_index = 3
    if isinstance(state, dict):
        try:
            class_index = int(state.get("special_jounin_class_index") or 3)
        except Exception:
            class_index = 3
    class_index = max(1, min(5, class_index))
    return class_index, SPECIAL_JOUNIN_CLASS_SKILL_ARR[class_index - 1]


def _level_cap_gate_reason(level: int, rank_value: int | None) -> str | None:
    if rank_value is None:
        return None
    if level >= GENIN_LEVEL_CAP and rank_value < RANK_CHUNIN:
        return (
            f"Level {level} is capped at Genin ({GENIN_LEVEL_CAP}). "
            f"Current rank is {_rank_name(rank_value)}. You must complete Chunin exam first to continue."
        )
    if level >= CHUNIN_LEVEL_CAP and rank_value < RANK_JOUNIN:
        return (
            f"Level {level} is capped at Chunin/Tensai Chunin ({CHUNIN_LEVEL_CAP}). "
            f"Current rank is {_rank_name(rank_value)}. You must complete Jounin exam first to continue."
        )
    if level >= JOUNIN_LEVEL_CAP and rank_value < RANK_SPECIAL_JOUNIN:
        return (
            f"Level {level} is capped at Jounin/Tensai Jounin ({JOUNIN_LEVEL_CAP}). "
            f"Current rank is {_rank_name(rank_value)}. You must complete Special Jounin exam first to continue."
        )
    if level >= SPECIAL_JOUNIN_LEVEL_CAP and rank_value < RANK_TUTOR:
        return (
            f"Level {level} is capped at Special Jounin ({SPECIAL_JOUNIN_LEVEL_CAP}). "
            f"Current rank is {_rank_name(rank_value)}. You must complete Tutor exam first to continue."
        )
    return None


def _looks_like_invalid_mission_error(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    text = str(response.get("error") or response.get("message") or response.get("result") or "").lower()
    return "invalid mission" in text


def _error_code(response: Any):
    if not isinstance(response, dict):
        return None
    return response.get("error")


def _tp_daily_mission_consumed(response: Any) -> bool:
    code = str(_error_code(response) or "").strip()
    return code in {"104", "109"} or _cooldown_seconds(response) > 0


def _pick_repeatable_tp_training_mission(level: int) -> str | None:
    eligible = [
        mid for mid in TP_TRAINING_MISSIONS
        if (_mission_required_level(mid) or 0) <= level
    ]
    if not eligible:
        return None
    return eligible[-1]


def _is_session_expired_response(response: Any) -> bool:
    code = _error_code(response)
    if str(code or "") == "401":
        return True
    text = str(response or "").lower()
    return "text/html" in text or "login page" in text


def _is_level_too_low_error(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    status = str(response.get("status") or "")
    if status == "102":
        return True
    message = str(response.get("error") or response.get("message") or response.get("result") or "").lower()
    return "too low" in message and "level" in message


def _cooldown_seconds(response: Any) -> int:
    if not isinstance(response, dict):
        return 0
    text = str(
        response.get("error_message")
        or response.get("message")
        or response.get("error")
        or ""
    ).lower()
    status_text = str(response.get("status") or "").strip().lower()
    error_text = str(response.get("error") or "").strip().lower()
    if "rate_limited" in {status_text, error_text} or "rate limited" in text or "rate_limited" in text:
        current_game_id = str(config.get_current_base_game().get("id") or "")
        if current_game_id == "zenshin":
            return random.randint(10, 15)
        return 8
    if error_text == "cooldown" or " cooldown" in text or text.startswith("cooldown") or "lock" in text:
        return 60
    # Example: "you can play again in 5 minutes."
    m = re.search(r"(\d+)\s*minute", text)
    if m:
        return max(1, int(m.group(1))) * 60
    s = re.search(r"(\d+)\s*second", text)
    if s:
        return max(1, int(s.group(1)))
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


def _extract_progress_snapshot(response: Any, default_level: int, default_rank: int | None):
    return progress_parser.extract_progress_snapshot(
        response,
        default_level=default_level,
        default_rank=default_rank,
    )


def _format_retry_wait(wait_seconds: int | float) -> str:
    seconds_value = max(0, int(round(float(wait_seconds or 0))))
    if seconds_value < 60:
        return f"{seconds_value}s"
    minutes_value = round(seconds_value / 60, 1)
    return f"{minutes_value} minutes"


def _push_live_progress_update(
    level: int | None = None,
    xp: int | None = None,
    gold: int | None = None,
    tokens: Any = None,
) -> None:
    snapshot = getattr(config, "char_data", None)
    if isinstance(snapshot, dict):
        for target in (
            snapshot,
            snapshot.get("character_data") if isinstance(snapshot.get("character_data"), dict) else None,
            snapshot.get("result") if isinstance(snapshot.get("result"), dict) else None,
            snapshot.get("data") if isinstance(snapshot.get("data"), dict) else None,
            snapshot.get("character") if isinstance(snapshot.get("character"), dict) else None,
        ):
            if not isinstance(target, dict):
                continue
            if level is not None:
                target["character_level"] = level
                target["level"] = level
            if xp is not None:
                target["character_xp"] = xp
                target["xp"] = xp
            if gold is not None:
                target["character_gold"] = gold
                target["gold"] = gold

    callback = getattr(config, "character_update_callback", None)
    if callable(callback):
        callback({
            "level": level,
            "xp": xp,
            "gold": gold,
            "tokens": tokens,
        })


def _wait_with_stop(seconds: int | float) -> bool:
    return rate_control.wait_with_stop(seconds, poll_seconds=NINJASAGA_STOP_POLL_SECONDS)


def _is_success_response(response: Any) -> bool:
    if isinstance(response, dict):
        status = response.get("status")
        if status is not None:
            return str(status) == "1"
        err = response.get("error")
        if err is not None:
            return str(err) in {"0", "None", ""}
        return "result" in response and not _looks_like_invalid_mission_error(response)
    if isinstance(response, (list, tuple)) and response:
        return str(response[0]) in {"1", "true", "True"}
    return False


def _is_gateway_blocked_error(exc: Exception) -> bool:
    return recovery.is_gateway_blocked_error(exc)


def _jittered_wait_seconds(base_seconds: int | float, jitter_seconds: int | float) -> float:
    return rate_control.jittered_wait_seconds(base_seconds, jitter_seconds)


def _int_or_default(value: Any, default: int) -> int:
    return rate_control.int_or_default(value, default)


def _build_anti_detection_profile(state: dict[str, Any]) -> dict[str, Any]:
    return anti_detection.build_anti_detection_profile(state)


def _next_cloudflare_wait(profile: dict[str, Any], backoff_index: int) -> tuple[int, int]:
    return anti_detection.next_cloudflare_wait(profile, backoff_index)


def _wait_min_call_interval(
    last_call_at: float | None,
    min_call_delay_seconds: int,
    action_jitter_seconds: int,
) -> tuple[bool, float]:
    return rate_control.wait_min_call_interval(
        last_call_at,
        min_call_delay_seconds,
        action_jitter_seconds,
        poll_seconds=NINJASAGA_STOP_POLL_SECONDS,
    )


def _register_failure_and_maybe_circuit(
    failure_timestamps: list[float],
    profile: dict[str, Any],
    cycle: int,
) -> bool:
    return anti_detection.register_failure_and_maybe_circuit(
        failure_timestamps,
        profile,
        cycle,
    )


def _handle_runtime_exception(
    exc: Exception,
    char_id: Any,
    context: str,
    cloudflare_rest_seconds: int,
) -> bool:
    return recovery.handle_runtime_exception(exc, char_id, context, cloudflare_rest_seconds)


def _apply_special_jounin_class_selection(
    char_id: Any,
    profile: dict[str, Any],
    last_amf_call_at: float | None,
) -> tuple[float | None, bool]:
    class_index, class_skill = _special_jounin_class_choice()
    current_control = _resolve_char_control_with_refresh(char_id, getattr(config, "char_data", None))
    if current_control is not None and current_control > 0:
        print(
            f"[Exam] Special Jounin class already selected (class={current_control}). "
            f"Current setting class={class_index} ({class_skill})"
        )
        return last_amf_call_at, True

    print(f"[Exam] Selecting Special Jounin class {class_index} ({class_skill})...")
    min_call_delay_seconds = int(profile["min_call_delay_seconds"])
    action_jitter_seconds = int(profile["action_jitter_seconds"])
    start_retry_delay_seconds = int(profile["start_retry_delay_seconds"])
    start_max_retries = int(profile["start_max_retries"])
    cloudflare_backoff_index = 0
    for attempt in range(1, start_max_retries + 1):
        ok_to_call, last_amf_call_at = _wait_min_call_interval(
            last_amf_call_at,
            min_call_delay_seconds,
            action_jitter_seconds,
        )
        if not ok_to_call:
            return last_amf_call_at, False
        try:
            response = amf_req.select_special_jounin_class(class_index)
            last_amf_call_at = time.time()
        except Exception as exc:
            cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
            if _handle_runtime_exception(exc, char_id, "SJClassSelect", cf_wait):
                continue
            return last_amf_call_at, False

        if _is_success_response(response):
            refreshed_control = _resolve_char_control_with_refresh(char_id, getattr(config, "char_data", None))
            print(
                f"[Exam] Special Jounin class selected -> class={class_index} ({class_skill}) "
                f"control={refreshed_control}"
            )
            return last_amf_call_at, True
        if _error_code(response) == 100 and attempt < start_max_retries:
            retry_wait = _jittered_wait_seconds(start_retry_delay_seconds, action_jitter_seconds)
            print(
                f"[Exam] SJClassSelect locked (error 100), retry "
                f"{attempt + 1}/{start_max_retries} in {retry_wait:.1f}s..."
            )
            if not _wait_with_stop(retry_wait):
                return last_amf_call_at, False
            continue
        print(f"[Exam] SJClassSelect failed: {response}")
        return last_amf_call_at, False
    return last_amf_call_at, False


def _apply_tutor_reward_claim(
    char_id: Any,
    profile: dict[str, Any],
    last_amf_call_at: float | None,
) -> tuple[float | None, bool]:
    print("[Exam] Claiming Tutor reward/class...")
    min_call_delay_seconds = int(profile["min_call_delay_seconds"])
    action_jitter_seconds = int(profile["action_jitter_seconds"])
    start_retry_delay_seconds = int(profile["start_retry_delay_seconds"])
    start_max_retries = int(profile["start_max_retries"])
    cloudflare_backoff_index = 0
    for attempt in range(1, start_max_retries + 1):
        ok_to_call, last_amf_call_at = _wait_min_call_interval(
            last_amf_call_at,
            min_call_delay_seconds,
            action_jitter_seconds,
        )
        if not ok_to_call:
            return last_amf_call_at, False
        try:
            response = amf_req.select_tutor_class()
            last_amf_call_at = time.time()
        except Exception as exc:
            cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
            if _handle_runtime_exception(exc, char_id, "NTClassSelect", cf_wait):
                continue
            return last_amf_call_at, False
        if _is_success_response(response):
            print("[Exam] Tutor reward claimed")
            _promote_runtime_rank_snapshot(RANK_TUTOR)
            return last_amf_call_at, True
        if _error_code(response) == 100 and attempt < start_max_retries:
            retry_wait = _jittered_wait_seconds(start_retry_delay_seconds, action_jitter_seconds)
            print(
                f"[Exam] NTClassSelect locked (error 100), retry "
                f"{attempt + 1}/{start_max_retries} in {retry_wait:.1f}s..."
            )
            if not _wait_with_stop(retry_wait):
                return last_amf_call_at, False
            continue
        print(f"[Exam] NTClassSelect failed: {response}")
        return last_amf_call_at, False
    return last_amf_call_at, False


def _normalize_mission_id(value: Any) -> str | None:
    return mission_policy.normalize_mission_id(value)


def _is_truthy_completion(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    text = str(value).strip().lower()
    return text in {"1", "true", "success", "completed", "clear", "done", "passed"}


def _collect_completed_exam_missions(node: Any, completed: set[str], exam_ids: set[str]) -> None:
    if isinstance(node, dict):
        # Case 1: keyed map e.g. {"msn55": 1}
        for key, value in node.items():
            key_id = _normalize_mission_id(key)
            if key_id in exam_ids and _is_truthy_completion(value):
                completed.add(key_id)

        # Case 2: record object e.g. {"mission_id":"msn55","success":1}
        mission_id = None
        for id_key in ("mission_id", "id", "msn", "mission"):
            candidate = _normalize_mission_id(node.get(id_key))
            if candidate in exam_ids:
                mission_id = candidate
                break
        if mission_id is not None:
            for success_key in ("success", "completed", "clear", "done", "passed", "status", "result"):
                if success_key in node and _is_truthy_completion(node.get(success_key)):
                    completed.add(mission_id)
                    break

        for value in node.values():
            _collect_completed_exam_missions(value, completed, exam_ids)
        return

    if isinstance(node, list):
        for item in node:
            _collect_completed_exam_missions(item, completed, exam_ids)
        return

    # Case 3: list of completed mission IDs
    candidate = _normalize_mission_id(node)
    if candidate in exam_ids:
        completed.add(candidate)


def _resolve_exam_start_index(char_id: Any, exam_missions: list[str]) -> int:
    exam_ids = {_normalize_mission_id(mid) for mid in exam_missions}
    exam_ids.discard(None)
    completed: set[str] = set()
    sources: list[Any] = []

    try:
        refreshed = amf_req.get_character_data(
            char_id,
            include_system_data=False,
            include_extra_data=True,
        )
        if isinstance(refreshed, dict):
            config.char_data = refreshed
            sources.append(refreshed)
            sources.append(refreshed.get("extra_data"))
            sources.append(refreshed.get("system_data"))
    except Exception:
        pass

    sources.append(getattr(config, "char_data", None))
    for source in sources:
        _collect_completed_exam_missions(source, completed, exam_ids)

    for idx, mission_id in enumerate(exam_missions):
        if _normalize_mission_id(mission_id) not in completed:
            return idx
    return len(exam_missions)


def _run_rank_exam(
    exam_name: str,
    exam_missions: list[str],
    target_rank: int,
    char_id: Any,
    char_level: int,
    profile: dict[str, Any],
    last_amf_call_at: float | None,
) -> tuple[bool, float | None, int | None]:
    account_type = _account_type_from_login()
    start_index = _resolve_exam_start_index(char_id, exam_missions)
    if start_index >= len(exam_missions):
        print(f"[Exam] All {exam_name} exam stages already completed, checking rank promotion...")
    else:
        print(
            f"[Exam] Resuming {exam_name} exam from stage {start_index + 1}/{len(exam_missions)} "
            f"({exam_missions[start_index]})"
        )
    print(
        f"[Exam] Starting {exam_name} exam sequence ({len(exam_missions)} stages): "
        f"{', '.join(exam_missions)}"
    )

    cycle_cooldown_seconds = int(profile["cycle_cooldown_seconds"])
    action_jitter_seconds = int(profile["action_jitter_seconds"])
    min_call_delay_seconds = int(profile["min_call_delay_seconds"])
    start_retry_delay_seconds = int(profile["start_retry_delay_seconds"])
    start_max_retries = int(profile["start_max_retries"])
    cloudflare_backoff_index = 0

    if exam_name == "Special Jounin":
        print("[Exam] Watching Special Jounin notice...")
        ok_to_call, last_amf_call_at = _wait_min_call_interval(
            last_amf_call_at,
            min_call_delay_seconds,
            action_jitter_seconds,
        )
        if not ok_to_call:
            return False, last_amf_call_at, None
        try:
            notice_result = amf_req.watch_special_jounin_notice()
            last_amf_call_at = time.time()
        except Exception as exc:
            cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
            if _handle_runtime_exception(exc, char_id, "watchSJENotice", cf_wait):
                return False, last_amf_call_at, None
            return False, last_amf_call_at, None
        if not _is_success_response(notice_result):
            print(f"[Exam] watchSJENotice failed: {notice_result}")
            return False, last_amf_call_at, None
        print("[Exam] Starting Special Jounin exam countdown...")
        ok_to_call, last_amf_call_at = _wait_min_call_interval(
            last_amf_call_at,
            min_call_delay_seconds,
            action_jitter_seconds,
        )
        if not ok_to_call:
            return False, last_amf_call_at, None
        try:
            start_exam_result = amf_req.start_special_jounin_exam()
            last_amf_call_at = time.time()
        except Exception as exc:
            cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
            if _handle_runtime_exception(exc, char_id, "startSJExam", cf_wait):
                return False, last_amf_call_at, None
            return False, last_amf_call_at, None
        if not _is_success_response(start_exam_result):
            print(f"[Exam] startSJExam failed: {start_exam_result}")
            return False, last_amf_call_at, None
        print("[Exam] Special Jounin countdown started")
    elif exam_name.startswith("Tutor"):
        print("[Exam] Checking Tutor exam notice...")
        ok_to_call, last_amf_call_at = _wait_min_call_interval(
            last_amf_call_at,
            min_call_delay_seconds,
            action_jitter_seconds,
        )
        if not ok_to_call:
            return False, last_amf_call_at, None
        try:
            notice_result = amf_req.get_tutor_exam_notice()
            last_amf_call_at = time.time()
        except Exception as exc:
            cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
            if _handle_runtime_exception(exc, char_id, "NTExamNotice", cf_wait):
                return False, last_amf_call_at, None
            return False, last_amf_call_at, None
        if not _is_success_response(notice_result):
            print(f"[Exam] NTExamNotice failed: {notice_result}")
            return False, last_amf_call_at, None
        print("[Exam] Starting Tutor exam countdown...")
        ok_to_call, last_amf_call_at = _wait_min_call_interval(
            last_amf_call_at,
            min_call_delay_seconds,
            action_jitter_seconds,
        )
        if not ok_to_call:
            return False, last_amf_call_at, None
        try:
            start_exam_result = amf_req.start_tutor_exam()
            last_amf_call_at = time.time()
        except Exception as exc:
            cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
            if _handle_runtime_exception(exc, char_id, "startNTExam", cf_wait):
                return False, last_amf_call_at, None
            return False, last_amf_call_at, None
        if not _is_success_response(start_exam_result):
            print(f"[Exam] startNTExam failed: {start_exam_result}")
            return False, last_amf_call_at, None
        print("[Exam] Tutor countdown started")

    for index, mission_id in enumerate(exam_missions[start_index:], start=start_index + 1):
        if _stop_requested():
            return False, last_amf_call_at, None
        mission_label = _mission_display_label(mission_id, account_type=account_type)
        print(f"[Exam {index}/{len(exam_missions)}] start mission {mission_label}")

        start_result = None
        started = False
        for attempt in range(1, start_max_retries + 1):
            ok_to_call, last_amf_call_at = _wait_min_call_interval(
                last_amf_call_at,
                min_call_delay_seconds,
                action_jitter_seconds,
            )
            if not ok_to_call:
                return False, last_amf_call_at, None
            try:
                start_result = amf_req.start_mission(mission_id)
                last_amf_call_at = time.time()
            except Exception as exc:
                cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
                if _handle_runtime_exception(exc, char_id, f"Exam startMission {mission_id}", cf_wait):
                    start_result = {"status": 0, "error": "recovered_retry"}
                    continue
                return False, last_amf_call_at, None

            if _is_success_response(start_result):
                started = True
                break
            if _error_code(start_result) == 100 and attempt < start_max_retries:
                retry_wait = _jittered_wait_seconds(
                    start_retry_delay_seconds,
                    action_jitter_seconds,
                )
                print(
                    f"[Exam {index}] startMission locked (error 100), retry "
                    f"{attempt + 1}/{start_max_retries} in {retry_wait:.1f}s..."
                )
                if not _wait_with_stop(retry_wait):
                    return False, last_amf_call_at, None
                continue
            break

        if not started and _is_exam_already_completed_error(start_result):
            print(
                f"[Exam {index}] mission {mission_id} is already completed (error 104). "
                "Checking current rank and trying the next stage..."
            )
            resume_wait = _jittered_wait_seconds(
                max(float(min_call_delay_seconds), 2.0),
                action_jitter_seconds,
            )
            print(f"[Exam {index}] waiting {resume_wait:.1f}s before checking the next stage...")
            if not _wait_with_stop(resume_wait):
                return False, last_amf_call_at, None
            refreshed_snapshot = _refresh_character_snapshot(char_id)
            refreshed_rank = _extract_char_rank(refreshed_snapshot or getattr(config, "char_data", None))
            if refreshed_rank is not None and refreshed_rank >= target_rank:
                print(f"[Exam] {exam_name} rank already promoted after resume check: {_rank_name(refreshed_rank)}({refreshed_rank})")
                return True, last_amf_call_at, refreshed_rank
            continue

        if not started:
            print(f"[Exam {index}] startMission failed: {start_result}")
            return False, last_amf_call_at, None

        action_wait = float(EXAM_FIXED_ACTION_DELAY_SECONDS)
        print(f"[Exam {index}] waiting fixed {EXAM_FIXED_ACTION_DELAY_SECONDS}s before updateCharacter...")
        if not _wait_with_stop(action_wait):
            return False, last_amf_call_at, None

        ok_to_call, last_amf_call_at = _wait_min_call_interval(
            last_amf_call_at,
            min_call_delay_seconds,
            action_jitter_seconds,
        )
        if not ok_to_call:
            return False, last_amf_call_at, None
        try:
            update_result = amf_req.update_character_progress(
                char_id=char_id,
                char_level=char_level,
                mission_id=mission_id,
                xp_gain=0,
                gold_gain=0,
            )
            last_amf_call_at = time.time()
        except Exception as exc:
            cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
            if _handle_runtime_exception(exc, char_id, f"Exam updateCharacter {mission_id}", cf_wait):
                return False, last_amf_call_at, None
            return False, last_amf_call_at, None

        if not _is_success_response(update_result):
            print(f"[Exam {index}] updateCharacter failed: {update_result}")
            return False, last_amf_call_at, None

        print(f"[Exam {index}/{len(exam_missions)}] completed mission {mission_id}")
        cooldown_wait = _jittered_wait_seconds(cycle_cooldown_seconds, action_jitter_seconds)
        if not _wait_with_stop(cooldown_wait):
            return False, last_amf_call_at, None

    refresh_wait = _jittered_wait_seconds(
        max(float(min_call_delay_seconds), 2.0),
        action_jitter_seconds,
    )
    print(f"[Exam] Waiting {refresh_wait:.1f}s and refreshing character data after exam...")
    if not _wait_with_stop(refresh_wait):
        return False, last_amf_call_at, None
    refreshed_snapshot = _refresh_character_snapshot(char_id)
    refreshed_rank = _extract_char_rank(refreshed_snapshot or getattr(config, "char_data", None))
    if exam_name.startswith("Tutor") and (refreshed_rank or -1) < target_rank:
        last_amf_call_at, tutor_claimed = _apply_tutor_reward_claim(char_id, profile, last_amf_call_at)
        refreshed_snapshot = _refresh_character_snapshot(char_id)
        refreshed_rank = _extract_char_rank(refreshed_snapshot or getattr(config, "char_data", None))
        if tutor_claimed and (refreshed_rank or -1) < target_rank:
            _promote_runtime_rank_snapshot(target_rank)
            refreshed_rank = target_rank
    exam_passed = refreshed_rank is not None and refreshed_rank >= target_rank
    if exam_passed:
        print(f"[Exam] {exam_name} exam completed. New rank: {_rank_name(refreshed_rank)}({refreshed_rank})")
    else:
        print(f"[Exam] {exam_name} exam missions finished, but rank is not promoted yet.")
    return exam_passed, last_amf_call_at, refreshed_rank


def _relogin_and_reselect_character(char_id: Any) -> bool:
    return recovery.relogin_and_reselect_character(char_id)


def zenshin_leveling(loop_times=None, training_mode: str | None = None):
    if not isinstance(getattr(config, "login_data", None), dict):
        raise ValueError("Login data is not loaded in memory")

    state = getattr(config, "zenshin_state", None) or {}
    profile = _build_anti_detection_profile(state)
    mission_override = state.get("leveling_mission_id")
    normalized_training_mode = str(training_mode or "").strip().lower() or None
    mission_id = str(mission_override or NINJASAGA_DEFAULT_MISSION_ID)
    auto_mission = not bool(mission_override)
    if normalized_training_mode:
        auto_mission = True
    xp_gain = int(state.get("leveling_xp_gain") or NINJASAGA_DEFAULT_XP_GAIN)
    gold_gain = int(state.get("leveling_gold_gain") or NINJASAGA_DEFAULT_GOLD_GAIN)
    delay_seconds = profile["action_delay_seconds"]
    cycle_cooldown_seconds = profile["cycle_cooldown_seconds"]
    rest_every_cycles = profile["rest_every_cycles"]
    rest_duration_seconds = profile["rest_duration_seconds"]
    action_jitter_seconds = profile["action_jitter_seconds"]
    min_call_delay_seconds = profile["min_call_delay_seconds"]
    start_retry_delay_seconds = profile["start_retry_delay_seconds"]
    start_max_retries = profile["start_max_retries"]

    print(
        "Anti-detection profile | "
        f"call_min={min_call_delay_seconds}s | action_delay={delay_seconds}s | "
        f"cycle_cooldown={cycle_cooldown_seconds}s | rest={rest_every_cycles}/{rest_duration_seconds}s"
    )
    account_type = _account_type_from_login()
    last_amf_call_at = None
    failure_timestamps: list[float] = []
    cloudflare_backoff_index = 0
    success_streak = 0
    training_mode_cfg = {
        "tp": {"reward_key": "tp", "reward_value": 10, "required_rank": RANK_JOUNIN, "required_rank_name": "Jounin", "required_level": 40, "daily": False, "mission_ids": TP_TRAINING_MISSIONS},
        "ss": {"reward_key": "sp", "reward_value": 30, "required_rank": RANK_TUTOR, "required_rank_name": "Tutor", "required_level": 80, "daily": False},
    }.get(normalized_training_mode or "")
    pending_training_missions: list[str] | None = None

    try:
        char_id, char_level = _resolve_current_character()
    except Exception as exc:
        cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
        if not _handle_runtime_exception(exc, None, "Resolve current character", cf_wait):
            return
        if _is_gateway_blocked_error(exc):
            if not _register_failure_and_maybe_circuit(failure_timestamps, profile, 0):
                return
        char_id, char_level = _resolve_current_character()
    char_rank = _resolve_char_rank_with_refresh(char_id, getattr(config, "char_data", None))
    if auto_mission and char_level >= GENIN_LEVEL_CAP and char_rank is None:
        print(
            f"Cannot resolve character rank at level {char_level}. "
            "Please refresh/select character again before auto leveling."
        )
        return
    game_label = _runtime_game_label()
    print(
        f"Starting {game_label} leveling | char_id={char_id} | level={char_level} | "
        f"mission={'auto' if auto_mission else mission_id}"
        + (f" | mode={normalized_training_mode}" if normalized_training_mode else "")
    )
    if training_mode_cfg and char_level < int(training_mode_cfg["required_level"]):
        print(
            f"{str(normalized_training_mode).upper()} Training requires level "
            f"{int(training_mode_cfg['required_level'])}+ . Current level: {char_level}."
        )
        return
    if training_mode_cfg and (char_rank or -1) < int(training_mode_cfg["required_rank"]):
        print(
            f"{str(normalized_training_mode).upper()} Training requires rank "
            f"{training_mode_cfg['required_rank_name']}. Current rank: {_rank_name(char_rank)}({char_rank})."
        )
        return
    if training_mode_cfg and bool(training_mode_cfg["daily"]):
        configured_daily_missions = list(training_mode_cfg.get("mission_ids") or [])
        if configured_daily_missions:
            pending_training_missions = [
                mid for mid in configured_daily_missions
                if (_mission_required_level(mid) or 0) <= char_level
            ]
        else:
            pending_training_missions = [
                mid
                for mid in _list_training_missions(
                    str(training_mode_cfg["reward_key"]),
                    int(training_mode_cfg["reward_value"]),
                    account_type=account_type,
                )
                if (_mission_required_level(mid) or 0) <= char_level
            ]
        if not pending_training_missions:
            print(f"No {str(normalized_training_mode).upper()} daily missions available for level {char_level}.")
            return
        print(
            f"{str(normalized_training_mode).upper()} Training daily mission queue: "
            + ", ".join(_mission_display_label(mid, account_type=account_type) for mid in pending_training_missions)
        )

    cycle = 0
    last_success_mission_id = mission_id
    no_progress_cycles = 0
    last_observed_progress: tuple[int | None, int | None] = (None, None)
    retry_same_cycle = False
    while True:
        if _stop_requested():
            print(f"{game_label} leveling stopped by user request")
            break
        if loop_times is not None and cycle >= int(loop_times):
            break

        if not retry_same_cycle:
            cycle += 1
        if auto_mission:
            gate_reason = None if training_mode_cfg else _level_cap_gate_reason(char_level, char_rank)
            if gate_reason:
                if char_level >= GENIN_LEVEL_CAP and (char_rank or -1) < RANK_CHUNIN:
                    print(f"[Cycle {cycle}] {gate_reason}")
                    print(f"[Cycle {cycle}] Trying to run Chunin exam automatically...")
                    exam_passed, last_amf_call_at, refreshed_rank = _run_rank_exam(
                        exam_name="Chunin",
                        exam_missions=EXAM_CHUNIN_ARR,
                        target_rank=RANK_CHUNIN,
                        char_id=char_id,
                        char_level=char_level,
                        profile=profile,
                        last_amf_call_at=last_amf_call_at,
                    )
                    if refreshed_rank is not None:
                        char_rank = refreshed_rank
                    if exam_passed:
                        print(f"[Cycle {cycle}] Chunin exam success, continuing leveling...")
                        continue
                    if _is_zenshin_runtime():
                        print(f"[Cycle {cycle}] Chunin exam promotion not visible yet. Continuing leveling and watching for progress changes...")
                        continue
                    print(f"[Cycle {cycle}] Chunin exam not completed yet. Leveling stopped.")
                    break
                if char_level >= CHUNIN_LEVEL_CAP and (char_rank or -1) < RANK_JOUNIN:
                    print(f"[Cycle {cycle}] {gate_reason}")
                    print(f"[Cycle {cycle}] Trying to run Jounin exam automatically...")
                    exam_passed, last_amf_call_at, refreshed_rank = _run_rank_exam(
                        exam_name="Jounin",
                        exam_missions=EXAM_JOUNIN_ARR,
                        target_rank=RANK_JOUNIN,
                        char_id=char_id,
                        char_level=char_level,
                        profile=profile,
                        last_amf_call_at=last_amf_call_at,
                    )
                    if refreshed_rank is not None:
                        char_rank = refreshed_rank
                    if exam_passed:
                        print(f"[Cycle {cycle}] Jounin exam success, continuing leveling...")
                        continue
                    if _is_zenshin_runtime():
                        print(f"[Cycle {cycle}] Jounin exam promotion not visible yet. Continuing leveling and watching for progress changes...")
                        continue
                    print(f"[Cycle {cycle}] Jounin exam not completed yet. Leveling stopped.")
                    break
                if char_level >= JOUNIN_LEVEL_CAP and (char_rank or -1) < RANK_SPECIAL_JOUNIN:
                    exam_mode = _exam_mode()
                    special_arr = list(EXAM_SPECIAL_JOUNIN_ARR)
                    print(f"[Cycle {cycle}] {gate_reason}")
                    print(f"[Cycle {cycle}] Trying to run Special Jounin exam automatically ({exam_mode})...")
                    exam_passed, last_amf_call_at, refreshed_rank = _run_rank_exam(
                        exam_name=f"Special Jounin ({exam_mode})",
                        exam_missions=special_arr,
                        target_rank=RANK_SPECIAL_JOUNIN,
                        char_id=char_id,
                        char_level=char_level,
                        profile=profile,
                        last_amf_call_at=last_amf_call_at,
                    )
                    if refreshed_rank is not None:
                        char_rank = refreshed_rank
                    if not exam_passed and (char_rank or -1) < RANK_SPECIAL_JOUNIN:
                        print(f"[Cycle {cycle}] Hard Special Jounin path not promoted yet. Trying class select shortcut first...")
                        last_amf_call_at, class_selected = _apply_special_jounin_class_selection(
                            char_id=char_id,
                            profile=profile,
                            last_amf_call_at=last_amf_call_at,
                        )
                        if class_selected:
                            print(f"[Cycle {cycle}] Special Jounin class selected after cleared hard exam, continuing leveling...")
                            continue
                    if not exam_passed and (char_rank or -1) < RANK_SPECIAL_JOUNIN:
                        print(f"[Cycle {cycle}] Hard Special Jounin path did not finish promotion. Trying easy path resume...")
                        exam_passed, last_amf_call_at, refreshed_rank = _run_rank_exam(
                            exam_name="Special Jounin (easy)",
                            exam_missions=list(EXAM_SPECIAL_JOUNIN_ARR_EASY),
                            target_rank=RANK_SPECIAL_JOUNIN,
                            char_id=char_id,
                            char_level=char_level,
                            profile=profile,
                            last_amf_call_at=last_amf_call_at,
                        )
                        if refreshed_rank is not None:
                            char_rank = refreshed_rank
                    if exam_passed:
                        last_amf_call_at, _ = _apply_special_jounin_class_selection(
                            char_id=char_id,
                            profile=profile,
                            last_amf_call_at=last_amf_call_at,
                        )
                        print(f"[Cycle {cycle}] Special Jounin exam success, continuing leveling...")
                        continue
                    if (char_rank or -1) < RANK_SPECIAL_JOUNIN:
                        last_amf_call_at, class_selected = _apply_special_jounin_class_selection(
                            char_id=char_id,
                            profile=profile,
                            last_amf_call_at=last_amf_call_at,
                        )
                        if class_selected:
                            print(f"[Cycle {cycle}] Special Jounin class selected after easy-path fallback, continuing leveling...")
                            continue
                    if _is_zenshin_runtime():
                        print(f"[Cycle {cycle}] Special Jounin promotion not visible yet. Continuing leveling and watching for progress changes...")
                        continue
                    print(f"[Cycle {cycle}] Special Jounin exam not completed yet. Leveling stopped.")
                    break
                if char_level >= SPECIAL_JOUNIN_LEVEL_CAP and (char_rank or -1) < RANK_TUTOR:
                    exam_mode = _exam_mode()
                    tutor_arr = list(EXAM_TUTOR_ARR)
                    print(f"[Cycle {cycle}] {gate_reason}")
                    print(f"[Cycle {cycle}] Trying to run Tutor exam automatically ({exam_mode})...")
                    exam_passed, last_amf_call_at, refreshed_rank = _run_rank_exam(
                        exam_name=f"Tutor ({exam_mode})",
                        exam_missions=tutor_arr,
                        target_rank=RANK_TUTOR,
                        char_id=char_id,
                        char_level=char_level,
                        profile=profile,
                        last_amf_call_at=last_amf_call_at,
                    )
                    if refreshed_rank is not None:
                        char_rank = refreshed_rank
                    if not exam_passed and (char_rank or -1) < RANK_TUTOR:
                        print(f"[Cycle {cycle}] Hard Tutor path did not finish promotion. Trying easy path resume...")
                        exam_passed, last_amf_call_at, refreshed_rank = _run_rank_exam(
                            exam_name="Tutor (easy)",
                            exam_missions=list(EXAM_TUTOR_ARR_EASY),
                            target_rank=RANK_TUTOR,
                            char_id=char_id,
                            char_level=char_level,
                            profile=profile,
                            last_amf_call_at=last_amf_call_at,
                        )
                        if refreshed_rank is not None:
                            char_rank = refreshed_rank
                    if exam_passed:
                        print(f"[Cycle {cycle}] Tutor exam success, continuing leveling...")
                        continue
                    if _is_zenshin_runtime():
                        print(f"[Cycle {cycle}] Tutor promotion not visible yet. Continuing leveling and watching for progress changes...")
                        continue
                    print(f"[Cycle {cycle}] Tutor exam not completed yet. Leveling stopped.")
                    break
                print(f"[Cycle {cycle}] {gate_reason}")
                break
            if normalized_training_mode == "tp":
                if pending_training_missions is not None:
                    if not pending_training_missions:
                        print("[TP Training] All TP daily missions have been used for this run.")
                        break
                    mission_id = pending_training_missions[0]
                else:
                    mission_id = _pick_repeatable_tp_training_mission(char_level)
                if not mission_id:
                    print(f"[Cycle {cycle}] No TP training mission found for level {char_level}.")
                    break
            elif normalized_training_mode == "ss":
                mission_id = _pick_training_mission(
                    char_level,
                    reward_key="sp",
                    reward_value=30,
                    account_type=account_type,
                )
                if not mission_id:
                    print(f"[Cycle {cycle}] No SS training mission found for level {char_level}.")
                    break
            else:
                mission_id = _pick_auto_mission(char_level, account_type=account_type)
        else:
            mission_id = mission_id

        start_result = None
        started = False
        level_gate_fallback = False
        mission_label = _mission_display_label(mission_id, account_type=account_type)
        if retry_same_cycle:
            print(f"[Cycle {cycle}] retry start mission {mission_label}")
            retry_same_cycle = False
        else:
            print(f"[Cycle {cycle}] start mission {mission_label}")
        for attempt in range(1, start_max_retries + 1):
            ok_to_call, last_amf_call_at = _wait_min_call_interval(
                last_amf_call_at,
                min_call_delay_seconds,
                action_jitter_seconds,
            )
            if not ok_to_call:
                print(f"{game_label} leveling stopped by user request")
                return
            try:
                start_result = amf_req.start_mission(mission_id)
                last_amf_call_at = time.time()
            except Exception as exc:
                cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
                if _handle_runtime_exception(exc, char_id, "startMission", cf_wait):
                    success_streak = 0
                    if not _register_failure_and_maybe_circuit(failure_timestamps, profile, cycle):
                        return
                    start_result = {"status": 0, "error": "recovered_retry"}
                    continue
                return
            if _looks_like_invalid_mission_error(start_result) and mission_id != "msn2":
                print(f"[Cycle {cycle}] mission {mission_id} invalid, retrying with msn2")
                mission_id = "msn2"
                continue
            if isinstance(start_result, dict) and str(start_result.get("status", "1")) == "1":
                started = True
                break
            if _error_code(start_result) == 100 and attempt < start_max_retries:
                retry_wait = _jittered_wait_seconds(
                    start_retry_delay_seconds,
                    action_jitter_seconds,
                )
                print(
                    f"[Cycle {cycle}] startMission locked (error 100), "
                    f"retry {attempt + 1}/{start_max_retries} in {retry_wait:.1f}s..."
                )
                if not _wait_with_stop(retry_wait):
                    print(f"{game_label} leveling stopped by user request")
                    return
                continue
            break

        if not started and _is_level_too_low_error(start_result):
            success_streak = 0
            fallback_id = last_success_mission_id or NINJASAGA_DEFAULT_MISSION_ID
            print(
                f"[Cycle {cycle}] mission {mission_id} level-gated (error 102). "
                f"Will relogin, reselect character, and fallback to {fallback_id} on next cycle."
            )
            _relogin_and_reselect_character(char_id)
            mission_id = fallback_id
            level_gate_fallback = True

        if not _is_success_response(start_result):
            if normalized_training_mode == "tp" and pending_training_missions is not None and mission_id in pending_training_missions:
                if _tp_daily_mission_consumed(start_result):
                    pending_training_missions = [mid for mid in pending_training_missions if mid != mission_id]
                    print(f"[Cycle {cycle}] TP mission {mission_id} already consumed/locked today. Trying the next TP daily mission...")
                    continue
            if _is_session_expired_response(start_result):
                success_streak = 0
                print(f"[Cycle {cycle}] startMission session expired (401). Rebuilding login session and retrying...")
                if _relogin_and_reselect_character(char_id):
                    retry_same_cycle = True
                    continue
                print(f"[Cycle {cycle}] relogin failed after startMission 401")
                break
            if level_gate_fallback:
                if not _wait_with_stop(cycle_cooldown_seconds):
                    print(f"{game_label} leveling stopped by user request")
                    break
                continue
            cooldown = _cooldown_seconds(start_result)
            if cooldown > 0:
                success_streak = 0
                if not _register_failure_and_maybe_circuit(failure_timestamps, profile, cycle):
                    break
                wait_sec = max(cooldown, 60)
                print(
                    f"[Cycle {cycle}] startMission cooldown/lock detected, waiting {_format_retry_wait(wait_sec)} before retry..."
                )
                if not _wait_with_stop(wait_sec):
                    print(f"{game_label} leveling stopped by user request")
                    break
                retry_same_cycle = True
                continue
            if not _register_failure_and_maybe_circuit(failure_timestamps, profile, cycle):
                break
            success_streak = 0
            print(f"[Cycle {cycle}] startMission failed: {start_result}")
            break
        last_success_mission_id = mission_id
        if normalized_training_mode == "tp" and pending_training_missions is not None and mission_id in pending_training_missions:
            pending_training_missions = [mid for mid in pending_training_missions if mid != mission_id]

        if delay_seconds > 0:
            action_wait = _jittered_wait_seconds(delay_seconds, action_jitter_seconds)
            if not _wait_with_stop(action_wait):
                print("Stop requested; finishing current cycle after updateCharacter...")

        ok_to_call, last_amf_call_at = _wait_min_call_interval(
            last_amf_call_at,
            min_call_delay_seconds,
            action_jitter_seconds,
        )
        if not ok_to_call:
            print(f"{game_label} leveling stopped by user request")
            return
        try:
            update_result = amf_req.update_character_progress(
                char_id=char_id,
                char_level=char_level,
                mission_id=mission_id,
                xp_gain=xp_gain,
                gold_gain=gold_gain,
            )
            last_amf_call_at = time.time()
        except Exception as exc:
            cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
            if _handle_runtime_exception(exc, char_id, "updateCharacter", cf_wait):
                success_streak = 0
                if not _register_failure_and_maybe_circuit(failure_timestamps, profile, cycle):
                    return
                continue
            return
        if not _is_success_response(update_result):
            success_streak = 0
            if not _register_failure_and_maybe_circuit(failure_timestamps, profile, cycle):
                break
            print(f"[Cycle {cycle}] updateCharacter failed: {update_result}")
            break

        if isinstance(update_result, dict):
            char_name, parsed_level, char_xp, char_gold, parsed_rank, parsed_energy = _extract_progress_snapshot(
                update_result,
                default_level=char_level,
                default_rank=char_rank,
            )
            # Fallback to character refresh only when updateCharacter payload lacks useful progress fields.
            if (
                parsed_level == char_level
                and char_xp == 0
                and char_gold == 0
                and char_name == "Unknown"
            ):
                try:
                    ok_to_call, last_amf_call_at = _wait_min_call_interval(
                        last_amf_call_at,
                        min_call_delay_seconds,
                        action_jitter_seconds,
                    )
                    if not ok_to_call:
                        print(f"{game_label} leveling stopped by user request")
                        return
                    refreshed = amf_req.get_character_data(
                        char_id,
                        include_system_data=False,
                        include_extra_data=False,
                    )
                    last_amf_call_at = time.time()
                except Exception as exc:
                    cf_wait, cloudflare_backoff_index = _next_cloudflare_wait(profile, cloudflare_backoff_index)
                    if _handle_runtime_exception(exc, char_id, "refresh character data", cf_wait):
                        success_streak = 0
                        if not _register_failure_and_maybe_circuit(failure_timestamps, profile, cycle):
                            return
                        continue
                    return
                if isinstance(refreshed, dict):
                    char_name, parsed_level, char_xp, char_gold, parsed_rank, parsed_energy = _extract_progress_snapshot(
                        refreshed,
                        default_level=char_level,
                        default_rank=char_rank,
                    )

            char_level = parsed_level
            if parsed_rank is not None:
                char_rank = parsed_rank
            rank_suffix = f" {_rank_name(char_rank)}({char_rank})" if char_rank is not None else ""
            energy_suffix = f" Energy {parsed_energy}" if parsed_energy is not None else ""
            reward_suffix = ""
            if normalized_training_mode == "tp":
                tp_reward = _extract_training_reward(update_result, "tp") or _mission_reward_value(mission_id, "tp")
                if tp_reward > 0:
                    reward_suffix = f" TP +{tp_reward}"
            elif normalized_training_mode == "ss":
                ss_reward = _extract_training_reward(update_result, "ss")
                if ss_reward <= 0:
                    ss_reward = _mission_reward_value(mission_id, "sp")
                if ss_reward > 0:
                    reward_suffix = f" SS +{ss_reward}"
            print(
                f"[Cycle {cycle}] ok -> {char_name} Lv {char_level}{rank_suffix} "
                f"XP {char_xp} Gold {char_gold}{energy_suffix}{reward_suffix}"
            )
            _push_live_progress_update(
                level=char_level,
                xp=char_xp,
                gold=char_gold,
                tokens=(update_result.get("account_tokens") if isinstance(update_result, dict) else None),
            )
            current_progress = (char_xp, char_gold)
            if _is_zenshin_runtime() and last_observed_progress != (None, None) and current_progress == last_observed_progress:
                no_progress_cycles += 1
                print(
                    f"[Cycle {cycle}] Warning: no XP/Gold change detected "
                    f"({no_progress_cycles} stagnant mission{'s' if no_progress_cycles != 1 else ''})."
                )
                if no_progress_cycles >= 3:
                    print(
                        f"[Cycle {cycle}] Warning: {game_label} progress is stagnant after multiple successful missions. "
                        "Attempting relogin + character reselection before continuing..."
                    )
                    if _relogin_and_reselect_character(char_id):
                        no_progress_cycles = 0
                        last_observed_progress = (None, None)
                        continue
                    print(f"[Cycle {cycle}] relogin failed after stagnant progress recovery")
                    break
            else:
                no_progress_cycles = 0
            last_observed_progress = current_progress
        else:
            print(f"[Cycle {cycle}] updateCharacter response: {update_result}")
            parsed_energy = None

        success_streak += 1
        if success_streak >= 3:
            cloudflare_backoff_index = 0
            if failure_timestamps:
                failure_timestamps.clear()
        else:
            cloudflare_backoff_index = min(cloudflare_backoff_index, 1)

        if _stop_requested():
            print(f"{game_label} leveling stopped after updateCharacter")
            break

        # Avoid immediate next mission start while server still finalizes previous battle.
        cooldown_wait = _jittered_wait_seconds(cycle_cooldown_seconds, action_jitter_seconds)
        if not _wait_with_stop(cooldown_wait):
            print(f"{game_label} leveling stopped by user request")
            break

        if rest_every_cycles > 0 and (cycle % rest_every_cycles == 0):
            rest_wait = _jittered_wait_seconds(rest_duration_seconds, action_jitter_seconds)
            print(
                f"[Cycle {cycle}] Anti-detection rest: sleeping {rest_wait:.1f} seconds..."
            )
            if not _wait_with_stop(rest_wait):
                print(f"{game_label} leveling stopped by user request")
                break
