from ..core import config
from . import amf_req
import re
from .runtime import (
    check_stop_event,
    get_char_id,
    get_level,
    get_rank,
    get_session_key,
    rift_delay,
    rift_exam_wait,
    _cfg_text,
    response_message,
    send_rift_request,
    wait_with_stop,
)


RIFT_EXAM_TRIGGER_RANKS = {
    20: 2,
    40: 4,
    60: 6,
    80: 8,
}

RIFT_EXAM_SERVICES = {
    20: {
        "name": "Chunin Exam",
        "prefix": "ChuninExam",
        "params_order": "session_char",
        "promote_service": "ChuninExam.promoteToChunin",
    },
    40: {
        "name": "Jounin Exam",
        "prefix": "JouninExam",
        "params_order": "session_char",
        "promote_service": "JouninExam.promoteToJounin",
    },
    60: {
        "name": "Special Jounin Exam",
        "prefix": "SpecialJouninExam",
        "params_order": "session_char",
        "promote_service": "SpecialJouninExam.promoteToSpecialJounin",
        "promote_params_order": "session_char_skill",
    },
    80: {
        "name": "Ninja Tutor Exam",
        "prefix": "NinjaTutorExam",
        "params_order": "char_session",
        "promote_service": "NinjaTutorExam.promoteToNinjaTutor",
    },
}

_CHUNIN_QUIZ_QUESTIONS = [
    {"id": 2, "a": 3, "q": "Question 1", "c": ["1", "2", "3", "4", "5"]},
    {"id": 3, "a": 1, "q": "Question 2", "c": ["1", "2", "3", "4", "5"]},
    {"id": 4, "a": 1, "q": "Question 3", "c": ["1", "2", "3", "4", "5"]},
    {"id": 1, "a": 2, "q": "Question 4", "c": ["1", "2", "3", "4", "5"]},
    {"id": 5, "a": 1, "q": "Question 5", "c": ["1", "2", "3", "4", "5"]},
]

CHUNIN_STAGE_META = [
    {
        "id": 1,
        "label": "Stage 1",
        "timer_range": (45, 60),
        "finish_builders": [
            lambda session_key, char_id, stage_id: [
                session_key,
                char_id,
                stage_id,
                True,
                _CHUNIN_QUIZ_QUESTIONS,
                [3, 1, 1, 2, 1],
            ],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 1, [], []],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, True, [], []],
        ],
    },
    {
        "id": 2,
        "label": "Stage 2",
        "timer_range": (150, 300),
        "finish_builders": [
            lambda session_key, char_id, stage_id: [
                session_key,
                char_id,
                stage_id,
                True,
                True,
                stage_id,
            ],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 0, 0, 0],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, False, False, stage_id],
        ],
    },
    {
        "id": 3,
        "label": "Stage 3",
        "timer_range": (300, 600),
        "finish_builders": [
            lambda session_key, char_id, stage_id: [
                session_key,
                char_id,
                stage_id,
                0,
                ["ene_21", "ene_19", "ene_20"],
            ],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 0, []],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, []],
        ],
    },
    {
        "id": 4,
        "label": "Stage 4",
        "timer_range": (300, 600),
        "finish_builders": [
            lambda session_key, char_id, stage_id: [
                session_key,
                char_id,
                stage_id,
                ["ene_24", "ene_23", "ene_22"],
            ],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 0, []],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, []],
        ],
    },
    {
        "id": 5,
        "label": "Stage 5",
        "timer_range": (900, 1500),
        "finish_builders": [
            lambda session_key, char_id, stage_id: [
                session_key,
                char_id,
                stage_id,
                ["ene_26", "ene_25"],
            ],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 0, []],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, []],
        ],
    },
]

JOUNIN_STAGE_META = [
    {
        "id": 1,
        "label": "Stage 1",
        "timer_range": (300, 600),
        "finish_builders": [
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 6, 0],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 1, []],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, True, []],
        ],
    },
    {
        "id": 2,
        "label": "Stage 2",
        "timer_range": (300, 1800),
        "finish_builders": [
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, True, True, True, True],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 1, []],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, True, []],
        ],
    },
    {
        "id": 3,
        "label": "Stage 3",
        "timer_range": (300, 600),
        "finish_builders": [
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, True, True, True, True],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 1, []],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, True, []],
        ],
    },
    {
        "id": 4,
        "label": "Stage 4",
        "timer_range": (900, 1800),
        "finish_builders": [
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 1, []],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, True, []],
        ],
    },
    {
        "id": 5,
        "label": "Stage 5",
        "timer_range": (900, 1800),
        "finish_builders": [
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, 1, []],
            lambda session_key, char_id, stage_id: [session_key, char_id, stage_id, True, []],
        ],
    },
]

SPECIAL_JOUNIN_STAGE_META = [
    {"id": 11, "label": "Stage 1 Chapter 1", "start_token": "1-1", "mission_code": "200", "timer_range": (10, 20)},
    {"id": 12, "label": "Stage 1 Chapter 2", "start_token": "1-2", "mission_code": "205", "timer_range": (10, 20)},
    {"id": 13, "label": "Stage 2 Chapter 1", "start_token": "2-1", "mission_code": "202", "timer_range": (10, 20)},
    {"id": 14, "label": "Stage 2 Chapter 2", "start_token": "2-2", "mission_code": "206", "timer_range": (10, 20)},
    {"id": 15, "label": "Stage 3 Chapter 1", "start_token": "3-1", "mission_code": "203", "timer_range": (10, 20)},
    {"id": 16, "label": "Stage 3 Chapter 2", "start_token": "3-2", "mission_code": "207", "timer_range": (10, 20)},
    {"id": 17, "label": "Stage 4 Chapter 1", "start_token": "4-1", "mission_code": "204", "timer_range": (10, 20)},
    {"id": 18, "label": "Stage 4 Chapter 2", "start_token": "4-2", "mission_code": "208", "timer_range": (10, 20)},
    {"id": 19, "label": "Stage 5 Chapter 1", "start_token": "5-1", "mission_code": "201", "timer_range": (10, 20)},
    {"id": 20, "label": "Stage 5 Chapter 2", "start_token": "5-2", "mission_code": "209", "timer_range": (10, 20)},
    {"id": 21, "label": "Stage 6 Chapter 1", "start_token": "6-1", "mission_code": "210", "timer_range": (10, 20)},
    {"id": 22, "label": "Stage 6 Chapter 2", "start_token": "6-2", "mission_code": "211", "timer_range": (10, 20)},
    {"id": 23, "label": "Stage 6 Chapter 3", "start_token": "6-3", "mission_code": "212", "timer_range": (10, 20)},
]

for stage in SPECIAL_JOUNIN_STAGE_META:
    stage["finish_builder"] = (
        lambda session_key, char_id, stage_id, _stage=stage: [
            session_key,
            char_id,
            _stage["start_token"],
            [],
            _stage["mission_code"],
        ]
    )

TUTOR_STAGE_META = [
    {"id": 1, "start_id": 1, "finish_id": 24, "label": "Stage 1 Chapter 1", "stage_key": "stage1-1", "timer_range": (180, 360)},
    {"id": 2, "start_id": 2, "finish_id": 25, "label": "Stage 1 Chapter 2", "stage_key": "stage1-2", "timer_range": (1200, 2400)},
    {"id": 3, "start_id": 3, "finish_id": 26, "label": "Stage 2 Chapter 1", "stage_key": "stage2-1", "timer_range": (90, 180)},
    {"id": 4, "start_id": 4, "finish_id": 27, "label": "Stage 2 Chapter 2", "stage_key": "stage2-2", "timer_range": (900, 1800)},
    {"id": 5, "start_id": 5, "finish_id": 28, "label": "Stage 3 Chapter 1", "stage_key": "stage3-1", "timer_range": (450, 900)},
    {"id": 6, "start_id": 6, "finish_id": 29, "label": "Stage 3 Chapter 2", "stage_key": "stage3-2", "timer_range": (600, 1200)},
    {"id": 7, "start_id": 7, "finish_id": 30, "label": "Stage 4 Chapter 1", "stage_key": "stage4-1", "timer_range": (450, 900)},
    {"id": 8, "start_id": 8, "finish_id": 31, "label": "Stage 4 Chapter 2", "stage_key": "stage4-2", "timer_range": (600, 1200)},
    {"id": 9, "start_id": 9, "finish_id": 32, "label": "Stage 5 Chapter 1", "stage_key": "stage5-1", "timer_range": (450, 900)},
    {"id": 10, "start_id": 10, "finish_id": 33, "label": "Stage 5 Chapter 2", "stage_key": "stage5-2", "timer_range": (600, 1200)},
    {"id": 11, "start_id": 11, "finish_id": 34, "label": "Stage 6 Chapter 1", "stage_key": "stage6-1", "timer_range": (1500, 3000)},
    {"id": 12, "start_id": 12, "finish_id": 35, "label": "Stage 6 Chapter 2", "stage_key": "stage6-2", "timer_range": (900, 1800)},
]

for stage in TUTOR_STAGE_META:
    stage["finish_builders"] = (
        lambda session_key, char_id, stage_id, _stage=stage: [
            [char_id, session_key, _stage["id"], []],
            [char_id, session_key, _stage["finish_id"], []],
            [char_id, session_key, _stage["finish_id"], 0, []],
        ]
    )

RIFT_EXAM_STAGE_META = {
    20: CHUNIN_STAGE_META,
    40: JOUNIN_STAGE_META,
    60: SPECIAL_JOUNIN_STAGE_META,
    80: TUTOR_STAGE_META,
}


def _refresh_character():
    char_id = get_char_id()
    result = amf_req.get_character_data(char_id)
    if not isinstance(result, dict):
        return None
    return result


def _current_exam_gate():
    level = get_level()
    rank = get_rank()
    if level >= 80 and rank < RIFT_EXAM_TRIGGER_RANKS[80]:
        return 80
    if level >= 60 and rank < RIFT_EXAM_TRIGGER_RANKS[60]:
        return 60
    if level >= 40 and rank < RIFT_EXAM_TRIGGER_RANKS[40]:
        return 40
    if level >= 20 and rank < RIFT_EXAM_TRIGGER_RANKS[20]:
        return 20
    return None


def _get_exam_data(level_gate: int):
    cfg = RIFT_EXAM_SERVICES[level_gate]
    char_id = get_char_id()
    session_key = get_session_key()
    if cfg["params_order"] == "char_session":
        params = [char_id, session_key]
    else:
        params = [session_key, char_id]

    result = send_rift_request(f"{cfg['prefix']}.getData", params)
    if isinstance(result, dict) and result.get("status") == 1:
        return result
    return result


def _promote_exam(level_gate: int):
    cfg = RIFT_EXAM_SERVICES[level_gate]
    char_id = get_char_id()
    session_key = get_session_key()
    params_order = cfg.get("promote_params_order", cfg["params_order"])
    if params_order == "char_session":
        params = [char_id, session_key]
    elif params_order == "session_char_skill":
        selected_skill = _cfg_text("rift_special_jounin_class_skill", "skill_2001")
        params = [session_key, char_id, selected_skill]
    else:
        params = [session_key, char_id]

    result = send_rift_request(cfg["promote_service"], params)
    if not isinstance(result, dict) or result.get("status") != 1:
        print(f"{cfg['name']} promotion failed: {response_message(result)}")
        return False

    _refresh_character()
    print(f"{cfg['name']} promotion completed.")
    if level_gate == 60:
        selected_skill = _cfg_text("rift_special_jounin_class_skill", "skill_2001")
        print(f"Special Jounin auto-promotion used class skill: {selected_skill}")
    return True


def _find_next_open_stage(level_gate: int, exam_result: dict):
    data = exam_result.get("data")
    if not isinstance(data, list):
        return None

    stage_meta = RIFT_EXAM_STAGE_META.get(level_gate, [])
    for index, item in enumerate(data):
        if index >= len(stage_meta):
            break
        if not isinstance(item, dict):
            continue
        try:
            status = int(item.get("status", 0))
        except Exception:
            status = 0
        if status == 1:
            resolved = dict(stage_meta[index])
            resolved["_source_item"] = dict(item)
            if item.get("stage"):
                resolved["stage_key"] = str(item.get("stage"))
            if item.get("stage_end_date"):
                resolved["stage_end_date"] = item.get("stage_end_date")
            return index, resolved
    return None


def _exam_all_clear(exam_result: dict) -> bool:
    data = exam_result.get("data")
    if not isinstance(data, list) or not data:
        return False
    statuses = []
    for item in data:
        try:
            statuses.append(int(item.get("status", 0)))
        except Exception:
            statuses.append(0)
    return all(status == 2 for status in statuses)


def _log_exam_mode(level_gate: int, exam_result: dict):
    mode = str(exam_result.get("current_mode") or "").strip().lower()
    time_remaining = str(exam_result.get("time_remaining") or "").strip()
    if not mode and not time_remaining:
        return
    label = RIFT_EXAM_SERVICES[level_gate]["name"]
    if time_remaining:
        print(f"{label} mode: {mode or '-'} | Time remaining: {time_remaining}")
    else:
        print(f"{label} mode: {mode or '-'}")


def _build_start_candidates(level_gate: int, stage_index: int, stage_meta: dict) -> list:
    source_item = stage_meta.get("_source_item") if isinstance(stage_meta, dict) else None
    raw_candidates = []
    if isinstance(source_item, dict):
        raw_candidates.extend(
            [
                source_item.get("start_token"),
                source_item.get("start_id"),
                source_item.get("target"),
                source_item.get("stage_target"),
                source_item.get("stage_id"),
                source_item.get("id"),
                source_item.get("stage"),
            ]
        )

    raw_candidates.extend(
        [
            stage_meta.get("start_token"),
            stage_meta.get("start_id"),
            stage_meta.get("stage_key"),
            stage_meta.get("id"),
        ]
    )
    raw_candidates.append(stage_index + 1)

    candidates = []
    seen = set()
    for value in raw_candidates:
        if value in (None, ""):
            continue
        options = [value]
        text = str(value).strip()
        if text and text != value:
            options.append(text)
        try:
            number = int(text)
        except Exception:
            number = None
        if number is None and text:
            match = re.search(r"(\d+)$", text)
            if match:
                try:
                    number = int(match.group(1))
                except Exception:
                    number = None
        if number is not None:
            options.extend([number, str(number)])
        for option in options:
            key = (type(option).__name__, repr(option))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(option)

    return candidates or [stage_index + 1]


def _start_stage(level_gate: int, stage_index: int, stage_meta: dict):
    cfg = RIFT_EXAM_SERVICES[level_gate]
    char_id = get_char_id()
    session_key = get_session_key()
    start_candidates = _build_start_candidates(level_gate, stage_index, stage_meta)
    source_item = stage_meta.get("_source_item") if isinstance(stage_meta, dict) else None

    last_result = None
    for index, stage_param in enumerate(start_candidates):
        if cfg["params_order"] == "char_session":
            params = [char_id, session_key, stage_param]
        else:
            params = [session_key, char_id, stage_param]
        result = send_rift_request(f"{cfg['prefix']}.startStage", params)
        if isinstance(result, dict) and result.get("status") == 1:
            return result
        last_result = result
    return last_result


def _finish_stage(level_gate: int, stage_meta: dict):
    cfg = RIFT_EXAM_SERVICES[level_gate]
    char_id = get_char_id()
    session_key = get_session_key()
    payload_sets = []
    if "finish_builders" in stage_meta:
        payload_spec = stage_meta["finish_builders"]
        if callable(payload_spec):
            payload_sets = list(payload_spec(session_key, char_id, stage_meta["id"]))
        else:
            for builder in payload_spec:
                payload_sets.append(builder(session_key, char_id, stage_meta["id"]))
    else:
        payload_sets = [stage_meta["finish_builder"](session_key, char_id, stage_meta["id"])]

    last_result = None
    for index, params in enumerate(payload_sets):
        result = send_rift_request(f"{cfg['prefix']}.finishStage", params)
        if isinstance(result, dict) and result.get("status") == 1:
            return result
        last_result = result
        if index + 1 < len(payload_sets):
            print(f"{cfg['name']} {stage_meta['label']} finish payload {index + 1} was rejected, trying fallback...")
    return last_result


def _run_supported_exam(level_gate: int):
    cfg = RIFT_EXAM_SERVICES[level_gate]
    print(f"Starting {cfg['name']}...")

    while True:
        if check_stop_event():
            return False

        exam_result = _get_exam_data(level_gate)
        if not isinstance(exam_result, dict) or exam_result.get("status") != 1:
            print(f"Failed to load {cfg['name']} data: {response_message(exam_result)}")
            return False
        _log_exam_mode(level_gate, exam_result)

        next_stage = _find_next_open_stage(level_gate, exam_result)
        if next_stage is None:
            if _exam_all_clear(exam_result):
                return _promote_exam(level_gate)
            print(f"{cfg['name']} has no open stage to run right now.")
            return False

        stage_index, stage_meta = next_stage
        print(f"{cfg['name']} {stage_meta['label']} ({stage_index + 1}) starting...")
        start_result = _start_stage(level_gate, stage_index, stage_meta)
        if not isinstance(start_result, dict) or start_result.get("status") != 1:
            print(f"Failed to start {cfg['name']} {stage_meta['label']}: {response_message(start_result)}")
            return False

        wait_seconds = rift_exam_wait(stage_meta["timer_range"])
        print(f"Waiting {wait_seconds} seconds before finishing {cfg['name']} {stage_meta['label']}...")
        if not wait_with_stop(wait_seconds):
            return False

        finish_result = _finish_stage(level_gate, stage_meta)
        if not isinstance(finish_result, dict) or finish_result.get("status") != 1:
            print(f"Failed to finish {cfg['name']} {stage_meta['label']}: {response_message(finish_result)}")
            return False

        print(f"{cfg['name']} {stage_meta['label']} completed.")
        if not wait_with_stop(rift_delay("rift_exam_stage_gap_seconds", 3)):
            return False


def ensure_exam_progression():
    level_gate = _current_exam_gate()
    if level_gate is None:
        return True

    return _run_supported_exam(level_gate)


def rift_exam():
    if not isinstance(config.char_data, dict):
        raise ValueError("Select a Ninja Rift character first")

    level_gate = _current_exam_gate()
    if level_gate is None:
        print("No Ninja Rift exam is currently available for this character.")
        return

    success = ensure_exam_progression()
    if hasattr(config, "stop_event"):
        config.stop_event.clear()

    if success:
        print("Ninja Rift exam flow finished.")
    else:
        print("Ninja Rift exam stopped.")
