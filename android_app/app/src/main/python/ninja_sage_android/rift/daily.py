from ..core import config
from .leveling import _build_mission_payload, _run_one_mission
from .runtime import check_stop_event, get_level, get_village_type, is_premium_user, rift_delay, wait_with_stop
from . import amf_req


def _grade_matches_village(grade: str, village_type: str) -> bool:
    grade = (grade or "").lower()
    if grade.endswith(f"_{village_type}"):
        return True
    return "_" not in grade


def _collect_missions(kind: str):
    mission_library = amf_req.get_mission_library()
    village_type = get_village_type()
    current_level = get_level()
    premium_user = is_premium_user()
    results = []

    for mission_id, mission in mission_library.items():
        grade = str(mission.get("msn_grade") or "").lower()
        is_daily = bool(mission.get("msn_daily")) or grade.startswith("daily_")

        if kind == "daily" and not is_daily:
            continue
        if not _grade_matches_village(grade, village_type):
            continue
        if not isinstance(mission.get("msn_enemy"), list):
            continue
        if bool(mission.get("msn_premium")) and not premium_user:
            continue

        try:
            mission_level = int(mission.get("msn_level") or 0)
        except Exception:
            mission_level = 0
        if mission_level > current_level:
            continue

        results.append((mission_level, str(mission_id), mission))

    results.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in results]


def _run_group(kind: str, empty_message: str):
    missions = _collect_missions(kind)
    if not missions:
        print(empty_message)
        return True

    print(f"Starting Ninja Rift {kind.upper()} missions...")
    failed_missions = 0
    for mission in missions:
        if check_stop_event():
            return False
        mission_payload = _build_mission_payload(mission)
        print(
            f"Running {kind.upper()} mission: {mission_payload['name']} "
            f"(Level {mission.get('msn_level', 0)})"
        )
        if not _run_one_mission(mission_payload, allow_skip_if_completed=True):
            if check_stop_event():
                return False
            failed_missions += 1
            print(
                f"Continuing Ninja Rift {kind.upper()} sweep after failed mission "
                f"{mission_payload['id']}."
            )
            continue
        loop_delay = max(1, rift_delay("rift_loop_delay_seconds", 1))
        if not wait_with_stop(loop_delay):
            return False
    if failed_missions > 0:
        print(
            f"Ninja Rift {kind.upper()} sweep completed with {failed_missions} failed mission"
            f"{'s' if failed_missions != 1 else ''}."
        )
    return True


def rift_daily_missions():
    if not isinstance(config.char_data, dict):
        raise ValueError("Select a Ninja Rift character first")

    print("Starting Ninja Rift mission sweep...")
    success = _run_group("daily", "No Daily Mission")

    if hasattr(config, "stop_event"):
        config.stop_event.clear()

    if success:
        print("Ninja Rift mission sweep finished.")
    else:
        print("Ninja Rift mission sweep stopped.")
    return success
