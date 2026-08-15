from .utils import (
    send_amf_request,
    flatten_json,
    get_data_by_id,
    StatManager,
    CUCSG,
    open_json_to_dict,
    save_fight_data,
)
import time
import keyboard
from .. import config
from . import amf_req

mission_list = open_json_to_dict("../data/mission.json")
enemy_list = open_json_to_dict("../data/enemy.json")
battle_hash = "eyJpdGVtcyI6eyJhY2Nlc3NvcnkiOiJhY2Nlc3NvcnlfMDEiLCJiYWNrX2l0ZW0iOiJiYWNrXzAxIiwid2VhcG9uIjoid3BuXzAxIiwic2V0Ijoic2V0XzAxXzAifSwic3RhdHVzIjp7ImVhcnRoIjowLCJmaXJlIjowLCJ3YXRlciI6MCwibGlnaHRuaW5nIjowLCJ3aW5kIjowfSwiYnl0ZXMiOnsiXyI6ODIyODQ0NywiX18iOjgyMjg0NDcsIl9fXyI6IjE3NjI3NDY2NTk0MDM2N2MzY2M5OTlhOWY5ZTk1MWExZDMzMjExNTQ1Yjg0YjJkNWE2MzkzM2IwMDIwNDMzMDAwYzNiYjQxMGZiMTc2Mjc0NjY1OTE3NjI3NDY2NTkxNzYyNzQ2NjU5MTc2Mjc0NjY1OSIsIl9fX19fIjo4MjI4NDQ3LCJfX19fX18iOjgyMjg0NDcsIl9fX18iOjE3NjI3NDY2NTl9LCJfX19fIjpbeyJfIjoic2tpbGxfMTMiLCJfXyI6MjkxMzR9XX0="

# Global variable untuk tracking relogin attempts
relogin_attempts = 0
MAX_RELOGIN_ATTEMPTS = 3

EXAM_CONFIG = {
    20: {
        "name": "Chunin Exam",
        "service": "ChuninExam.getData",
        "params_order": "session_char",
        "required_rank": 1,
        "promotion_hint": "claim the reward and promote to Chunin in the game",
        "promote_service": "ChuninExam.promoteToChunin",
        "promote_params_order": "session_char",
        "manual_claim": False
    },
    40: {
        "name": "Jounin Exam",
        "service": "JouninExam.getData",
        "params_order": "session_char",
        "required_rank": 3,
        "promotion_hint": "claim the reward and promote to Jounin in the game",
        "promote_service": "JouninExam.promoteToJounin",
        "promote_params_order": "session_char",
        "manual_claim": False
    },
    60: {
        "name": "Special Jounin Exam",
        "service": "SpecialJouninExam.getData",
        "params_order": "session_char",
        "required_rank": 5,
        "promotion_hint": "claim the reward, pick your class skill, and promote to Special Jounin in the game",
        "promote_service": "SpecialJouninExam.promoteToSpecialJounin",
        "promote_params_order": "session_char_skill",
        "manual_claim": True
    },
    80: {
        "name": "Ninja Tutor Exam",
        "service": "NinjaTutorExam.getData",
        "params_order": "char_session",
        "required_rank": 7,
        "promotion_hint": "log in to the game, claim the reward, and promote to Ninja Tutor",
        "promote_service": "NinjaTutorExam.promoteToNinjaTutor",
        "promote_params_order": "char_session",
        "manual_claim": False
    }
}

DEFAULT_SPECIAL_JOUNIN_CLASS_SKILL = "skill_4001"
EXAM_START_DELAY_SECONDS = 8
EXAM_FINISH_DELAY_SECONDS = 5


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(getattr(config, name, default))
    except Exception:
        return int(default)


def _cfg_text(name: str, default: str) -> str:
    value = getattr(config, name, default)
    text = str(value).strip()
    return text or default

EXAM_MANUAL_HINTS = {
    20: {},
    40: {},
    60: {},
    80: {}
}

EXAM_STAGE_REGISTRY = {
    20: {
        0: {
            "label": "Stage 1",
            "start_service": "ChuninExam.startStage",
            "start_params": [1],
            "finish_service": "ChuninExam.finishStage",
            "finish_params_template": [1, 1, [], []],
            "supported": True,
            "reason": "Server accepts finishStage for Stage 1 with pass/questions/answers payload."
        },
        1: {
            "label": "Stage 2",
            "start_service": "ChuninExam.startStage",
            "start_params": [2],
            "finish_service": "ChuninExam.finishStage",
            "finish_params_template": [2, 0, 0, 0],
            "supported": True,
            "reason": "Server accepts finishStage for Stage 2 with scroll-war counters."
        },
        2: {
            "label": "Stage 3",
            "start_service": "ChuninExam.startStage",
            "start_params": [3],
            "finish_service": "ChuninExam.finishStage",
            "finish_params_template": [3, 0, []],
            "supported": True,
            "reason": "Server finishStage completes Stage 3 directly."
        },
        3: {
            "label": "Stage 4",
            "start_service": "ChuninExam.startStage",
            "start_params": [4],
            "finish_service": "ChuninExam.finishStage",
            "finish_params_template": [4, 0, []],
            "supported": True,
            "reason": "Server finishStage completes Stage 4 directly."
        },
        4: {
            "label": "Stage 5",
            "start_service": "ChuninExam.startStage",
            "start_params": [5],
            "finish_service": "ChuninExam.finishStage",
            "finish_params_template": [5, 0, []],
            "supported": True,
            "reason": "Server finishStage completes Stage 5 directly."
        }
    },
    40: {
        0: {
            "label": "Stage 1",
            "start_service": "JouninExam.startStage",
            "start_params": [6],
            "finish_service": "JouninExam.finishStage",
            "finish_params_template": [6, 1, []],
            "supported": True,
            "reason": "Server finishStage accepts a victory-like flag and completes the stage."
        },
        1: {
            "label": "Stage 2",
            "start_service": "JouninExam.startStage",
            "start_params": [7],
            "finish_service": "JouninExam.finishStage",
            "finish_params_template": [7, 1, []],
            "supported": True,
            "reason": "Server finishStage accepts a victory-like flag and completes the stage."
        },
        2: {
            "label": "Stage 3",
            "start_service": "JouninExam.startStage",
            "start_params": [8],
            "finish_service": "JouninExam.finishStage",
            "finish_params_template": [8, 1, []],
            "supported": True,
            "reason": "Server finishStage accepts a victory-like flag and completes the stage."
        },
        3: {
            "label": "Stage 4",
            "start_service": "JouninExam.startStage",
            "start_params": [9],
            "finish_service": "JouninExam.finishStage",
            "finish_params_template": [9, 1, []],
            "supported": True,
            "reason": "Server finishStage accepts a victory-like flag and completes the stage."
        },
        4: {
            "label": "Stage 5",
            "start_service": "JouninExam.startStage",
            "start_params": [10],
            "finish_service": "JouninExam.finishStage",
            "finish_params_template": [10, 1, []],
            "supported": True,
            "reason": "Server finishStage accepts a victory-like flag and completes the stage."
        }
    },
    60: {
        0: {"label": "Stage 1 Chapter 1", "start_service": "SpecialJouninExam.startStage", "start_params": [11], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [11, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        1: {"label": "Stage 1 Chapter 2", "start_service": "SpecialJouninExam.startStage", "start_params": [12], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [12, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        2: {"label": "Stage 2 Chapter 1", "start_service": "SpecialJouninExam.startStage", "start_params": [13], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [13, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        3: {"label": "Stage 2 Chapter 2", "start_service": "SpecialJouninExam.startStage", "start_params": [14], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [14, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        4: {"label": "Stage 3 Chapter 1", "start_service": "SpecialJouninExam.startStage", "start_params": [15], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [15, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        5: {"label": "Stage 3 Chapter 2", "start_service": "SpecialJouninExam.startStage", "start_params": [16], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [16, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        6: {"label": "Stage 4 Chapter 1", "start_service": "SpecialJouninExam.startStage", "start_params": [17], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [17, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        7: {"label": "Stage 4 Chapter 2", "start_service": "SpecialJouninExam.startStage", "start_params": [18], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [18, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        8: {"label": "Stage 5 Chapter 1", "start_service": "SpecialJouninExam.startStage", "start_params": [19], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [19, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        9: {"label": "Stage 5 Chapter 2", "start_service": "SpecialJouninExam.startStage", "start_params": [20], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [20, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        10: {"label": "Stage 6 Chapter 1", "start_service": "SpecialJouninExam.startStage", "start_params": [21], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [21, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        11: {"label": "Stage 6 Chapter 2", "start_service": "SpecialJouninExam.startStage", "start_params": [22], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [22, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        12: {"label": "Stage 6 Chapter 3", "start_service": "SpecialJouninExam.startStage", "start_params": [23], "finish_service": "SpecialJouninExam.finishStage", "finish_params_template": [23, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
    },
    80: {
        0: {"label": "Stage 1 Chapter 1", "start_service": "NinjaTutorExam.startStage", "start_params": [24], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [24, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        1: {"label": "Stage 1 Chapter 2", "start_service": "NinjaTutorExam.startStage", "start_params": [25], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [25, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        2: {"label": "Stage 2 Chapter 1", "start_service": "NinjaTutorExam.startStage", "start_params": [26], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [26, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        3: {"label": "Stage 2 Chapter 2", "start_service": "NinjaTutorExam.startStage", "start_params": [27], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [27, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        4: {"label": "Stage 3 Chapter 1", "start_service": "NinjaTutorExam.startStage", "start_params": [28], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [28, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        5: {"label": "Stage 3 Chapter 2", "start_service": "NinjaTutorExam.startStage", "start_params": [29], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [29, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        6: {"label": "Stage 4 Chapter 1", "start_service": "NinjaTutorExam.startStage", "start_params": [30], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [30, 0, []], "supported": True, "reason":"Server finishStage completes the chapter directly."},
        7: {"label": "Stage 4 Chapter 2", "start_service": "NinjaTutorExam.startStage", "start_params": [31], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [31, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        8: {"label": "Stage 5 Chapter 1", "start_service": "NinjaTutorExam.startStage", "start_params": [32], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [32, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        9: {"label": "Stage 5 Chapter 2", "start_service": "NinjaTutorExam.startStage", "start_params": [33], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [33, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        10: {"label": "Stage 6 Chapter 1", "start_service": "NinjaTutorExam.startStage", "start_params": [34], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [34, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
        11: {"label": "Stage 6 Chapter 2", "start_service": "NinjaTutorExam.startStage", "start_params": [35], "finish_service": "NinjaTutorExam.finishStage", "finish_params_template": [35, 0, []], "supported": True, "reason": "Server finishStage completes the chapter directly."},
    }
}


def check_stop_event():
    """Check if stop event is set from GUI"""
    if hasattr(config, 'stop_event') and config.stop_event.is_set():
        # print("Leveling stopped by user request")
        return True
    return False


def get_character_rank():
    """Best-effort rank lookup from the current character snapshot."""
    if not isinstance(config.char_data, dict):
        return None

    char_snapshot = config.char_data.get("character_data", config.char_data)
    rank = None

    if isinstance(char_snapshot, dict):
        rank = (
            char_snapshot.get("character_rank")
            or char_snapshot.get("rank")
            or char_snapshot.get("character_data_character_rank")
        )

    try:
        return int(rank) if rank is not None else None
    except (TypeError, ValueError):
        return None


def get_exam_data(level_gate, char_id, session_key):
    """Fetch exam progress for the rank gate at the given level."""
    exam_cfg = EXAM_CONFIG[level_gate]
    if exam_cfg["params_order"] == "char_session":
        params = [char_id, session_key]
    else:
        params = [session_key, char_id]

    result = send_amf_request(exam_cfg["service"], params)
    if isinstance(result, dict) and result.get("status") == 1:
        return result.get("data")
    return None


def promote_exam(level_gate, char_id, session_key):
    """Claim exam promotion when the exam is already complete."""
    exam_cfg = EXAM_CONFIG[level_gate]
    params_order = exam_cfg.get("promote_params_order", exam_cfg["params_order"])

    if params_order == "char_session":
        params = [char_id, session_key]
    elif params_order == "session_char_skill":
        selected_skill = _cfg_text("sage_special_jounin_class_skill", DEFAULT_SPECIAL_JOUNIN_CLASS_SKILL)
        params = [session_key, char_id, selected_skill]
    else:
        params = [session_key, char_id]

    result = send_amf_request(exam_cfg["promote_service"], params)
    if isinstance(result, dict) and result.get("status") == 1:
        amf_req.get_character_data(char_id)
        print(f"{exam_cfg['name']} promotion claimed successfully.")
        if level_gate == 60:
            selected_skill = _cfg_text("sage_special_jounin_class_skill", DEFAULT_SPECIAL_JOUNIN_CLASS_SKILL)
            print(
                "Special Jounin auto-claim used the default class skill "
                f"{selected_skill}."
            )
        return True

    print(f"Failed to claim {exam_cfg['name']} promotion: {result}")
    return False


def get_exam_stage_spec(level_gate, progress_index):
    return EXAM_STAGE_REGISTRY.get(level_gate, {}).get(progress_index)


def describe_exam_blocker(level_gate, statuses):
    first_open_index = next((idx for idx, status in enumerate(statuses) if status == 1), None)
    if first_open_index is None:
        return None

    stage_spec = get_exam_stage_spec(level_gate, first_open_index)
    if not stage_spec:
        return None

    label = stage_spec.get("label", f"Stage {first_open_index + 1}")
    reason = stage_spec.get("reason")
    if reason:
        return f"{EXAM_CONFIG[level_gate]['name']} {label} still needs manual completion. {reason}"

    if not stage_spec.get("supported", False):
        return f"{EXAM_CONFIG[level_gate]['name']} {label} still needs manual completion."

    return None


def start_exam_stage(level_gate, progress_index, char_id, session_key):
    stage_spec = get_exam_stage_spec(level_gate, progress_index)
    if not stage_spec:
        return None

    if level_gate in (20, 40, 60):
        params = [session_key, char_id, *stage_spec.get("start_params", [])]
    elif level_gate == 80:
        params = [char_id, session_key, *stage_spec.get("start_params", [])]
    else:
        return None

    return send_amf_request(stage_spec["start_service"], params)


def finish_exam_stage(level_gate, progress_index, char_id, session_key):
    stage_spec = get_exam_stage_spec(level_gate, progress_index)
    if not stage_spec or not stage_spec.get("finish_service"):
        return None

    if level_gate in (20, 40, 60):
        params = [session_key, char_id, *stage_spec.get("finish_params_template", [])]
    elif level_gate == 80:
        params = [char_id, session_key, *stage_spec.get("finish_params_template", [])]
    else:
        return None

    return send_amf_request(stage_spec["finish_service"], params)


def run_supported_exam_stages(level_gate, char_id, session_key, exam_data):
    exam_cfg = EXAM_CONFIG[level_gate]
    registry = EXAM_STAGE_REGISTRY.get(level_gate, {})
    ran_any_stage = False

    for progress_index in sorted(registry.keys()):
        if progress_index >= len(exam_data):
            continue

        try:
            status = int(exam_data[progress_index].get("status", 0))
        except (AttributeError, TypeError, ValueError):
            status = 0

        stage_spec = registry[progress_index]
        if status != 1 or not stage_spec.get("supported", False):
            continue

        if check_stop_event():
            return False

        print(f"Starting {exam_cfg['name']} {stage_spec['label']}...")
        start_result = start_exam_stage(level_gate, progress_index, char_id, session_key)
        if not isinstance(start_result, dict) or start_result.get("status") != 1:
            print(f"Failed to start {exam_cfg['name']} {stage_spec['label']}: {start_result}")
            return False

        exam_start_delay_seconds = _cfg_int("sage_exam_start_delay_seconds", EXAM_START_DELAY_SECONDS)
        print(f"Waiting {exam_start_delay_seconds} seconds before finishing exam stage...")
        time.sleep(exam_start_delay_seconds)

        finish_result = finish_exam_stage(level_gate, progress_index, char_id, session_key)
        if finish_result is None:
            print(f"{exam_cfg['name']} {stage_spec['label']} still needs manual completion.")
            return False

        if isinstance(finish_result, dict):
            finish_status = finish_result.get("status")
        else:
            finish_status = getattr(finish_result, "status", None)

        if finish_status != 1:
            print(f"Failed to finish {exam_cfg['name']} {stage_spec['label']}: {finish_result}")
            return False

        print(f"{exam_cfg['name']} {stage_spec['label']} completed.")
        exam_finish_delay_seconds = _cfg_int("sage_exam_finish_delay_seconds", EXAM_FINISH_DELAY_SECONDS)
        print(f"Waiting {exam_finish_delay_seconds} seconds after finishing exam stage...")
        time.sleep(exam_finish_delay_seconds)
        ran_any_stage = True
        exam_data = get_exam_data(level_gate, char_id, session_key)
        if not isinstance(exam_data, list):
            print(f"Failed to refresh {exam_cfg['name']} progress after {stage_spec['label']}.")
            return False

    return ran_any_stage


def check_exam_gate(char_level, char_id, session_key):
    """Stop leveling when a promotion exam blocks further progression."""
    current_rank = get_character_rank()
    applicable_gate = None
    for level_gate, exam_cfg in sorted(EXAM_CONFIG.items()):
        if char_level >= level_gate and current_rank == exam_cfg["required_rank"]:
            applicable_gate = level_gate
            break

    if applicable_gate is None:
        return True

    exam_cfg = EXAM_CONFIG[applicable_gate]

    exam_data = get_exam_data(applicable_gate, char_id, session_key)
    if not isinstance(exam_data, list) or not exam_data:
        print(
            f"{exam_cfg['name']} check could not be verified for level {char_level} and rank {current_rank}. "
            f"Please open the game and confirm your promotion status before continuing."
        )
        return False

    statuses = []
    for item in exam_data:
        try:
            statuses.append(int(item.get("status", 0)))
        except (AttributeError, TypeError, ValueError):
            statuses.append(0)

    all_complete = bool(statuses) and all(status == 2 for status in statuses)
    has_active_exam = any(status in (1, 2) for status in statuses)

    if all_complete:
        if not exam_cfg.get("manual_claim", False):
            print(f"{exam_cfg['name']} is complete. Claiming promotion automatically...")
            if promote_exam(applicable_gate, char_id, session_key):
                return True
        print(
            f"{exam_cfg['name']} is already finished, but the promotion is not finalized yet. "
            f"Please log in to the game, {exam_cfg['promotion_hint']}, then start leveling again."
        )
        return False

    if has_active_exam:
        if run_supported_exam_stages(applicable_gate, char_id, session_key, exam_data):
            refreshed_data = get_exam_data(applicable_gate, char_id, session_key)
            if isinstance(refreshed_data, list):
                statuses = []
                for item in refreshed_data:
                    try:
                        statuses.append(int(item.get("status", 0)))
                    except (AttributeError, TypeError, ValueError):
                        statuses.append(0)

                if statuses and all(status == 2 for status in statuses):
                    if not exam_cfg.get("manual_claim", False):
                        print(f"{exam_cfg['name']} is complete. Claiming promotion automatically...")
                        if promote_exam(applicable_gate, char_id, session_key):
                            return True
                    else:
                        print(
                            f"{exam_cfg['name']} has been finished. "
                            f"Please log in to the game, {exam_cfg['promotion_hint']}, then start leveling again."
                        )
                        return False

        first_open_stage = next((idx + 1 for idx, status in enumerate(statuses) if status == 1), None)
        manual_hint = EXAM_MANUAL_HINTS.get(applicable_gate, {}).get(first_open_stage)
        if manual_hint:
            print(manual_hint)
            return False
        stage_registry_hint = describe_exam_blocker(applicable_gate, statuses)
        if stage_registry_hint:
            print(stage_registry_hint)
            return False
        print(
            f"{exam_cfg['name']} is available and must be cleared before leveling can continue. "
            "The exam ActionScript uses a different stage flow than normal missions, so it still needs the real stage handlers before we can automate it safely."
        )
        return False

    return True

def automatic_relogin():
    """Fungsi untuk melakukan login ulang otomatis ketika session expired"""
    global relogin_attempts
    
    print("Attempting automatic relogin...")
    
    try:
        # Check stop event before proceeding
        if check_stop_event():
            return False
            
        # Load quick login data from config (stored in memory during login)
        if not config.quick_login_data:
            print("No quick login data found. Cannot auto relogin.")
            return False

        profile_id = config.get_current_amf_profile()["id"]
        credentials, _ = config.get_quick_login_credentials(profile_id)
        if not credentials:
            print(f"No quick login data found for AMF profile: {profile_id}")
            return False

        username = credentials.get("username")
        password = credentials.get("password")
        
        if not username or not password:
            print("Invalid quick login data.")
            return False
        
        config.game_data = amf_req.check_version()
        if config.game_data.get("status") != 1:
            print("Game version check failed during auto relogin.")
            return False
        
        # Check stop event before login
        if check_stop_event():
            return False
            
        # Perform login
        config.login_data = amf_req.login(
            username, 
            password, 
            config.game_data["__"], 
            str(int(config.game_data["_"]))
        )
        
        if config.login_data.get('status') != 1:
            print("Auto relogin failed. Invalid credentials.")
            relogin_attempts += 1
            return False
        
        # Check stop event before getting character data
        if check_stop_event():
            return False
            
        # Get the same character data again
        if config.char_data and "character_data" in config.char_data:
            char_id = config.char_data["character_data"]["character_id"]
            config.char_data = amf_req.get_character_data(char_id)
            
            if config.char_data:
                print("Auto relogin successful! Session renewed.")
                relogin_attempts = 0  # Reset counter on success
                return True
        
        print("Failed to get character data after auto relogin.")
        relogin_attempts += 1
        return False
        
    except Exception as e:
        print(f"Error during auto relogin: {e}")
        relogin_attempts += 1
        return False


def _notify_reauth_required(reason: str):
    callback = getattr(config, "session_reauth_required_callback", None)
    if callable(callback):
        callback(reason)

def get_levelling_mission(char_level):
    """Get appropriate mission for character level"""
    if check_stop_event():
        return None
        
    prohibited_grades = ["daily", "tp", "ss", ""]
    if char_level <= 60:
        levelling_mission = [m for m in mission_list if m['level'] == char_level and m['grade'] not in prohibited_grades]
    else:
        levelling_mission = [m for m in mission_list if m['level'] == 60 and m['grade'] not in prohibited_grades]
    return levelling_mission[0] if levelling_mission else None

def build_enemy_attributes(mission_same_level):
    """Build enemy attributes for battle"""
    if check_stop_event():
        return [], ""
        
    enemies = []
    enemy_attrs = []
    for enemy in mission_same_level['enemies']:
        enemy_attr = get_data_by_id(enemy, enemy_list)
        enemies.append(enemy)
        enemy_attrs.append(f"id:{enemy}|hp:{enemy_attr['hp']}|agility:{enemy_attr['agility']}")
    return enemies, "#".join(enemy_attrs)

def start_battle(mission_same_level, char_id, char_level, session_key, wait_seconds=5):
    """Start a battle mission"""
    if check_stop_event():
        return None
        
    enemies, enemy_attrs = build_enemy_attributes(mission_same_level)
    agility = StatManager.calculate_stats_with_data("agility", flatten_json(config.char_data))

    hash_input = ",".join(enemies) + enemy_attrs + str(agility)
    mission_hash = CUCSG.hash(hash_input)

    parameters = [char_id, mission_same_level["id"], ",".join(enemies), enemy_attrs, agility, mission_hash, session_key]
    battle_id = send_amf_request("BattleSystem.startMission", parameters)

    battle_wait_seconds = _cfg_int("sage_battle_wait_seconds", wait_seconds)
    print(f"wait for {battle_wait_seconds} seconds")

    time.sleep(battle_wait_seconds)
    return battle_id

def finish_battle(mission_id, char_id, battle_id, session_key):
    """Finish a battle mission"""
    if check_stop_event():
        return None
        
    hash_input = f"{mission_id}{char_id}{battle_id}0"
    _loc2_ = CUCSG.hash(hash_input)

    parameters = [char_id, mission_id, battle_id, _loc2_, 0, session_key, battle_hash, 0]
    result = send_amf_request("BattleSystem.finishMission", parameters)
    save_fight_data(result)

    return result

def process_mission(mission_same_level, char_level, char_id, session_key, wait_seconds=5):
    """Process a single mission"""
    global relogin_attempts
    mission_id = mission_same_level["id"]
    
    # Check stop event at the beginning
    if check_stop_event():
        return char_level
        
    try:
        battle_id = start_battle(mission_same_level, char_id, char_level, session_key, wait_seconds=wait_seconds)
        
        # Check stop event after starting battle
        if check_stop_event() or battle_id is None:
            return char_level
            
        result = finish_battle(mission_id, char_id, battle_id, session_key)

        post_finish_delay_seconds = _cfg_int("sage_post_finish_delay_seconds", 0)
        if post_finish_delay_seconds > 0:
            print(f"Waiting {post_finish_delay_seconds} seconds after finishMission...")
            time.sleep(post_finish_delay_seconds)

        # Check stop event after finishing battle
        if check_stop_event() or result is None:
            return char_level

        if result["status"] == 1:
            rewards = result.get("result", [])
            gained_xp = rewards[0] if len(rewards) > 0 else 0
            gained_gold = rewards[1] if len(rewards) > 1 else 0
            print(
                f"Mission completed successfully! "
                f"Gained EXP: {gained_xp} Gained Gold: {gained_gold} "
                f"Current Level: {result['level']}"
            )
            current_gold = 0
            if isinstance(config.char_data, dict):
                char_snapshot = config.char_data.get("character_data", config.char_data)
                if isinstance(char_snapshot, dict):
                    current_gold = char_snapshot.get("character_gold") or char_snapshot.get("gold") or 0

            total_gold = current_gold + gained_gold
            total_xp = result.get("xp")
            total_level = result.get("level", char_level)

            if isinstance(config.char_data, dict):
                char_snapshot = config.char_data.get("character_data", config.char_data)
                if isinstance(char_snapshot, dict):
                    char_snapshot["character_gold"] = total_gold
                    char_snapshot["gold"] = total_gold
                    char_snapshot["character_xp"] = total_xp
                    char_snapshot["xp"] = total_xp
                    char_snapshot["character_level"] = total_level
                    char_snapshot["level"] = total_level

            if callable(getattr(config, "character_update_callback", None)):
                config.character_update_callback({
                    "level": total_level,
                    "xp": total_xp,
                    "gold": total_gold,
                    "tokens": result.get("account_tokens")
                })

            relogin_attempts = 0  # Reset on success
            return result['level']
        else:
            relogin_wait_seconds = _cfg_int("sage_auto_relogin_wait_seconds", 20)
            print(f"Mission failed or session expired. Waiting {relogin_wait_seconds} seconds...")
            
            # Check stop event during wait
            for i in range(relogin_wait_seconds):
                if check_stop_event():
                    return char_level
                time.sleep(1)
            
            # Auto relogin setelah failure
            if relogin_attempts < MAX_RELOGIN_ATTEMPTS:
                if automatic_relogin():
                    # Update session key setelah relogin berhasil
                    new_session_key = config.login_data["sessionkey"]
                    new_char_id = config.char_data["character_data"]["character_id"]
                    print("Retrying mission after auto relogin...")
                    # Retry mission dengan session baru
                    return process_mission(
                        mission_same_level,
                        char_level,
                        new_char_id,
                        new_session_key,
                        wait_seconds=wait_seconds
                    )
                else:
                    relogin_attempts += 1
                    print(f"Auto relogin failed. Attempt {relogin_attempts}/{MAX_RELOGIN_ATTEMPTS}")
            else:
                print("Max auto relogin attempts reached. Stopping leveling.")
                _notify_reauth_required("Auto relogin failed. Please log in again.")
                
    except Exception as e:
        print(f"Error during mission: {e}")
        relogin_wait_seconds = _cfg_int("sage_auto_relogin_wait_seconds", 20)
        print(f"Waiting {relogin_wait_seconds} seconds and attempting auto relogin...")
        
        # Check stop event during wait
        for i in range(relogin_wait_seconds):
            if check_stop_event():
                return char_level
            time.sleep(1)
        
        if relogin_attempts < MAX_RELOGIN_ATTEMPTS:
            if automatic_relogin():
                new_session_key = config.login_data["sessionkey"]
                new_char_id = config.char_data["character_data"]["character_id"]
                print("Retrying mission after auto relogin...")
                return process_mission(
                    mission_same_level,
                    char_level,
                    new_char_id,
                    new_session_key,
                    wait_seconds=wait_seconds
                )
            else:
                relogin_attempts += 1
                if relogin_attempts >= MAX_RELOGIN_ATTEMPTS:
                    _notify_reauth_required("Auto relogin failed. Please log in again.")

    return char_level

def start_leveling(loop_times=None):
    """Main leveling function with stop event support"""
    global relogin_attempts
    
    # Reset relogin attempts ketika mulai leveling baru
    relogin_attempts = 0
    
    char_data = flatten_json(config.char_data)
    char_id = char_data["character_data_character_id"]
    char_level = char_data["character_data_character_level"]
    session_key = config.login_data["sessionkey"]

    if loop_times is None:
        iter_count = 0
        while True:
            # Check stop event at the start of each iteration
            if check_stop_event():
                break
                
            if relogin_attempts >= MAX_RELOGIN_ATTEMPTS:
                print("Too many auto relogin failures. Stopping leveling.")
                _notify_reauth_required("Auto relogin failed. Please log in again.")
                break
                
            infinite_rest_every_cycles = _cfg_int("sage_infinite_loop_rest_every_cycles", 50)
            infinite_rest_duration_seconds = _cfg_int("sage_infinite_loop_rest_duration_seconds", 10)
            if infinite_rest_every_cycles > 0 and iter_count == infinite_rest_every_cycles and iter_count != 0:
                print(f"Waiting {infinite_rest_duration_seconds} seconds after {infinite_rest_every_cycles} mission... ")
                
                # Check stop event during wait
                for i in range(infinite_rest_duration_seconds):
                    if check_stop_event():
                        break
                    time.sleep(1)
                else:
                    iter_count = 0
                    continue
                break  # Break if stop event was set during wait

            mission_same_level = get_levelling_mission(char_level)
            if not mission_same_level:
                print(f"No suitable mission found for level {char_level}")
                break

            # Update data dari config setiap iterasi (untuk handle perubahan setelah relogin)
            char_data = flatten_json(config.char_data)
            char_id = char_data["character_data_character_id"]
            session_key = config.login_data["sessionkey"]

            if not check_exam_gate(char_level, char_id, session_key):
                break
            
            battle_wait_seconds = _cfg_int("sage_battle_wait_seconds", 5)
            new_level = process_mission(mission_same_level, char_level, char_id, session_key, wait_seconds=battle_wait_seconds)
            
            # Only update level if mission was successful
            if new_level != char_level:
                char_level = new_level
                
            iter_count += 1
    else:
        for i in range(loop_times):
            # Check stop event at the start of each iteration
            if check_stop_event():
                break
                
            if relogin_attempts >= MAX_RELOGIN_ATTEMPTS:
                print("Too many auto relogin failures. Stopping leveling.")
                _notify_reauth_required("Auto relogin failed. Please log in again.")
                break
                
            limited_rest_every_cycles = _cfg_int("sage_limited_loop_rest_every_cycles", 15)
            limited_rest_duration_seconds = _cfg_int("sage_limited_loop_rest_duration_seconds", 10)
            if limited_rest_every_cycles > 0 and i % limited_rest_every_cycles == 0 and i != 0:
                print(f"Rate limit reached. Waiting {limited_rest_duration_seconds} seconds...")
                
                # Check stop event during wait
                for _ in range(limited_rest_duration_seconds):
                    if check_stop_event():
                        break
                    time.sleep(1)
                else:
                    continue
                break  # Break if stop event was set during wait

            mission_same_level = get_levelling_mission(char_level)
            if not mission_same_level:
                print(f"No suitable mission found for level {char_level}")
                break

            # Update data dari config setiap iterasi
            print("battle :",i+1)
            char_data = flatten_json(config.char_data)
            char_id = char_data["character_data_character_id"]
            session_key = config.login_data["sessionkey"]

            if not check_exam_gate(char_level, char_id, session_key):
                break
            
            battle_wait_seconds = _cfg_int("sage_battle_wait_seconds", 5)
            new_level = process_mission(mission_same_level, char_level, char_id, session_key, wait_seconds=battle_wait_seconds)
            
            if new_level != char_level:
                char_level = new_level
    
    # Clear the stop event when leveling finishes normally
    if hasattr(config, 'stop_event'):
        config.stop_event.clear()
        
    print("Leveling session ended")


