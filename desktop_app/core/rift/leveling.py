from .. import config
from . import amf_req
from .exam import ensure_exam_progression
from .runtime import (
    check_stop_event,
    current_gold,
    current_xp,
    finish_mission,
    get_agility,
    get_char_id,
    get_level,
    is_premium_user,
    get_rank,
    get_session_key,
    get_village_type,
    mission_damage,
    rift_delay,
    rift_random_wait,
    response_message,
    send_rift_request,
    update_runtime_character_stats,
    wait_with_stop,
)
from .utils import CUCSG

def _load_leveling_missions():
    mission_library = amf_req.get_mission_library()
    village_type = get_village_type()
    premium_user = is_premium_user()
    eligible = []

    for mission_id, mission in mission_library.items():
        grade = str(mission.get("msn_grade") or "")
        if grade.startswith("daily_"):
            continue
        if grade in {"", "daily"}:
            continue
        if not grade.endswith(f"_{village_type}"):
            continue
        if not isinstance(mission.get("msn_enemy"), list):
            continue
        if bool(mission.get("msn_premium")) and not premium_user:
            continue
        try:
            mission_level = int(mission.get("msn_level") or 0)
        except Exception:
            mission_level = 0
        if mission_level <= 0:
            continue
        eligible.append((mission_level, mission_id, mission))

    eligible.sort(key=lambda item: (item[0], item[1]))
    return eligible


def _select_mission_for_level(level: int):
    missions = _load_leveling_missions()
    if not missions:
        return None

    target_level = max(1, int(level))
    exact = [mission for mission in missions if mission[0] == target_level]
    if exact:
        return exact[0][2]

    lower = [mission for mission in missions if mission[0] <= target_level]
    if lower:
        return lower[-1][2]

    return missions[0][2]


def _build_mission_payload(mission: dict):
    enemy_library = amf_req.get_enemy_library()
    enemy_ids = [str(enemy_id) for enemy_id in mission.get("msn_enemy", [])]
    enemy_stats = []
    parts = []

    for enemy_id in enemy_ids:
        enemy = dict(enemy_library.get(enemy_id) or {})
        hp = int(enemy.get("enemy_hp") or 0)
        agility = int(enemy.get("enemy_agility") or 0)
        enemy_stats.append(enemy)
        parts.append(f"id:{enemy_id}|hp:{hp}|agility:{agility}")

    agility = get_agility()
    enemy_csv = ",".join(enemy_ids)
    enemy_data = "#".join(parts)
    mission_hash = CUCSG.hash(enemy_csv + enemy_data + str(agility))

    return {
        "id": mission["msn_id"],
        "name": mission.get("msn_name") or mission["msn_id"],
        "enemy_ids": enemy_ids,
        "enemy_csv": enemy_csv,
        "enemy_data": enemy_data,
        "agility": agility,
        "hash": mission_hash,
        "enemy_stats": enemy_stats,
        "damage": mission_damage(enemy_ids, enemy_stats),
    }


def _extract_battle_code(start_result):
    if isinstance(start_result, str) and len(start_result) == 10:
        return start_result
    if isinstance(start_result, list) and start_result:
        first = start_result[0]
        if isinstance(first, str) and len(first) == 10:
            return first
    return None


def _is_already_finished_mission_result(result) -> bool:
    message = response_message(result).strip().lower()
    if not message:
        return False
    markers = (
        "already finished",
        "already completed",
        "already done",
        "has been completed",
        "mission completed",
        "finished today",
        "completed today",
    )
    return any(marker in message for marker in markers)


def _run_one_mission(mission_payload: dict, allow_skip_if_completed: bool = False):
    char_id = get_char_id()
    session_key = get_session_key()
    start_result = send_rift_request(
        "BattleSystem.startMission",
        [
            char_id,
            mission_payload["id"],
            mission_payload["enemy_csv"],
            mission_payload["enemy_data"],
            mission_payload["agility"],
            mission_payload["hash"],
            session_key,
        ],
    )
    if start_result is None:
        return False

    battle_code = _extract_battle_code(start_result)
    if not battle_code:
        if allow_skip_if_completed and _is_already_finished_mission_result(start_result):
            print(f"Skipping Ninja Rift mission {mission_payload['id']}: already completed.")
            return True
        print(f"Failed to start Ninja Rift mission {mission_payload['id']}: {response_message(start_result)}")
        return False

    battle_wait = max(
        5,
        rift_random_wait(
            "rift_mission_battle_wait_base_seconds",
            "rift_mission_battle_wait_random_seconds",
            20,
            20,
        ),
    )
    print(f"Mission {mission_payload['name']} started. Waiting {battle_wait} seconds before finish...")
    if not wait_with_stop(battle_wait):
        return False

    finish_result = finish_mission(mission_payload["id"], battle_code, mission_payload["damage"])
    if not isinstance(finish_result, dict) or finish_result.get("status") != 1:
        print(f"Mission {mission_payload['id']} failed: {response_message(finish_result)}")
        return False

    rewards = finish_result.get("result", [])
    gained_exp = rewards[0] if len(rewards) > 0 else 0
    gained_gold = rewards[1] if len(rewards) > 1 else 0
    total_gold = current_gold() + int(gained_gold or 0)
    total_xp = int(finish_result.get("xp") or current_xp())
    total_level = int(finish_result.get("level") or get_level())

    update_runtime_character_stats(level=total_level, xp=total_xp, gold=total_gold)
    print(
        f"Mission completed: {mission_payload['name']} | "
        f"EXP: {gained_exp} | Gold: {gained_gold} | Level: {total_level}"
    )
    return True


def rift_leveling(loop_times=None):
    if not isinstance(config.char_data, dict):
        raise ValueError("Select a Ninja Rift character first")

    cycle = 0
    completed = True
    print("Starting Ninja Rift leveling...")

    while True:
        if check_stop_event():
            completed = False
            break
        if loop_times is not None and cycle >= int(loop_times):
            break

        if not ensure_exam_progression():
            completed = False
            break

        current_level = get_level()
        current_rank = get_rank()
        mission = _select_mission_for_level(current_level)
        if not mission:
            print(f"No Ninja Rift mission found for level {current_level} and rank {current_rank}")
            completed = False
            break

        mission_payload = _build_mission_payload(mission)
        if not _run_one_mission(mission_payload):
            completed = False
            break

        cycle += 1
        if loop_times is None:
            rest_every = rift_delay("rift_infinite_loop_rest_every_cycles", 40)
            rest_duration = rift_delay("rift_infinite_loop_rest_duration_seconds", 30)
        else:
            rest_every = rift_delay("rift_limited_loop_rest_every_cycles", 15)
            rest_duration = rift_delay("rift_limited_loop_rest_duration_seconds", 15)

        if rest_every > 0 and cycle % rest_every == 0:
            print(f"Cooling down for {rest_duration} seconds after {cycle} Rift missions...")
            if not wait_with_stop(rest_duration):
                completed = False
                break
        else:
            delay = max(1, rift_delay("rift_loop_delay_seconds", 1))
            if not wait_with_stop(delay):
                completed = False
                break

    if hasattr(config, "stop_event"):
        config.stop_event.clear()
    print("Ninja Rift leveling ended")
    return completed
