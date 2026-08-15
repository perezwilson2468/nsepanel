import time

from . import config
from .utils import (
    CUCSG,
    StatManager,
    flatten_json,
    get_data_by_id,
    open_json_to_dict,
    save_fight_data,
    send_amf_request,
)

mission_list = open_json_to_dict("data/mission.json")
enemy_list = open_json_to_dict("data/enemy.json")
battle_hash = "eyJpdGVtcyI6eyJhY2Nlc3NvcnkiOiJhY2Nlc3NvcnlfMDEiLCJiYWNrX2l0ZW0iOiJiYWNrXzAxIiwid2VhcG9uIjoid3BuXzAxIiwic2V0Ijoic2V0XzAxXzAifSwic3RhdHVzIjp7ImVhcnRoIjowLCJmaXJlIjowLCJ3YXRlciI6MCwibGlnaHRuaW5nIjowLCJ3aW5kIjowfSwiYnl0ZXMiOnsiXyI6ODIyODQ0NywiX18iOjgyMjg0NDcsIl9fXyI6IjE3NjI3NDY2NTk0MDM2N2MzY2M5OTlhOWY5ZTk1MWExZDMzMjExNTQ1Yjg0YjJkNWE2MzkzM2IwMDIwNDMzMDAwYzNiYjQxMGZiMTc2Mjc0NjY1OTE3NjI3NDY2NTkxNzYyNzQ2NjU5MTc2Mjc0NjY1OSIsIl9fX19fIjo4MjI4NDQ3LCJfX19fX18iOjgyMjg0NDcsIl9fX18iOjE3NjI3NDY2NTl9LCJfX19fIjpbeyJfIjoic2tpbGxfMTMiLCJfXyI6MjkxMzR9XX0="
MISSION_S_FINISH_DAMAGE = 235000

MISSION_S_STAGE_CONFIG = {
    1: {"mission_id": "msn_112", "energy_cost": 10, "min_level": 80},
    2: {"mission_id": "msn_113", "energy_cost": 12, "min_level": 81},
    3: {"mission_id": "msn_114", "energy_cost": 14, "min_level": 82},
    4: {"mission_id": "msn_115", "energy_cost": 16, "min_level": 83},
    5: {"mission_id": "msn_116", "energy_cost": 25, "min_level": 84},
}

MISSION_S_START_WAIT_SECONDS = 5
MISSION_S_BETWEEN_BATTLES_SECONDS = 5


def check_stop_event():
    if hasattr(config, "stop_event") and config.stop_event.is_set():
        print("Mission S stopped by user request")
        return True
    return False


def wait_with_stop_check(seconds: int) -> bool:
    for _ in range(seconds):
        if check_stop_event():
            return False
        time.sleep(1)
    return True


def response_message(response) -> str:
    if response is None:
        return "No response"
    if isinstance(response, dict):
        return str(
            response.get("result")
            or response.get("message")
            or response.get("error")
            or response
        )
    for attr in ("description", "message", "details", "faultString"):
        value = getattr(response, attr, None)
        if value:
            return str(value)
    return str(response)


def get_mission_by_id(mission_id: str):
    return get_data_by_id(mission_id, mission_list)


def get_character_context():
    if not isinstance(config.char_data, dict):
        raise ValueError("Character data is not loaded in memory")
    if not isinstance(config.login_data, dict):
        raise ValueError("Login data is not loaded in memory")

    char_snapshot = config.char_data.get("character_data", config.char_data)
    if not isinstance(char_snapshot, dict):
        raise ValueError("Invalid character data snapshot")

    char_id = char_snapshot.get("character_id") or char_snapshot.get("char_id")
    char_level = int(char_snapshot.get("character_level") or char_snapshot.get("level") or 0)
    session_key = config.login_data.get("sessionkey")

    if not char_id:
        raise ValueError("Character ID is missing from current character data")
    if not session_key:
        raise ValueError("Session key is missing from login data")

    return char_id, char_level, session_key


def get_mission_s_data(char_id, session_key):
    return send_amf_request("BattleSystem.getMissionSData", [char_id, session_key])


def build_enemy_attributes(mission):
    enemies = []
    enemy_attrs = []
    for enemy_id in mission.get("enemies", []):
        enemy = get_data_by_id(enemy_id, enemy_list)
        if not enemy:
            print(f"Missing enemy definition for {enemy_id}")
            continue
        enemies.append(enemy_id)
        enemy_attrs.append(f"id:{enemy_id}|hp:{enemy['hp']}|agility:{enemy['agility']}")
    return enemies, "#".join(enemy_attrs)


def start_battle(mission, char_id, session_key, stage_to_run):
    if check_stop_event():
        return None

    enemies, enemy_attrs = build_enemy_attributes(mission)
    if not enemies:
        print(f"Mission S enemy data missing for {mission['id']}")
        return None

    agility = StatManager.calculate_stats_with_data("agility", flatten_json(config.char_data))
    hash_input = ",".join(enemies) + enemy_attrs + str(agility)
    mission_hash = CUCSG.hash(hash_input)
    parameters = [
        char_id,
        mission["id"],
        ",".join(enemies),
        enemy_attrs,
        agility,
        mission_hash,
        session_key,
        stage_to_run,
    ]
    battle_id = send_amf_request("BattleSystem.startMission", parameters)
    print(f"Started Mission S {mission['name']} (battle id: {battle_id})")
    print(f"Waiting {MISSION_S_START_WAIT_SECONDS} seconds before finishing mission...")
    if not wait_with_stop_check(MISSION_S_START_WAIT_SECONDS):
        return None
    return battle_id


def finish_battle(mission_id, char_id, battle_id, session_key):
    if check_stop_event():
        return None

    hash_input = f"{mission_id}{char_id}{battle_id}{MISSION_S_FINISH_DAMAGE}"
    finish_hash = CUCSG.hash(hash_input)
    parameters = [
        char_id,
        mission_id,
        battle_id,
        finish_hash,
        MISSION_S_FINISH_DAMAGE,
        session_key,
        battle_hash,
        1,
    ]
    result = send_amf_request("BattleSystem.finishMission", parameters)
    save_fight_data(result)
    return result


def resolve_stage_to_run(unlocked_stage: int, energy: int, char_level: int):
    for stage in range(min(unlocked_stage, 5), 0, -1):
        stage_cfg = MISSION_S_STAGE_CONFIG.get(stage)
        if (
            stage_cfg
            and char_level >= stage_cfg["min_level"]
            and energy >= stage_cfg["energy_cost"]
        ):
            return stage
    return None


def mission_s():
    char_id, char_level, session_key = get_character_context()

    if char_level < 80:
        print("Mission S requires level 80")
        return

    print("Starting Mission S automation...")

    while not check_stop_event():
        mission_s_data = get_mission_s_data(char_id, session_key)
        if not isinstance(mission_s_data, dict):
            print(f"Failed to get Mission S data: {response_message(mission_s_data)}")
            return
        if mission_s_data.get("status") != 1:
            print(f"Failed to get Mission S data: {response_message(mission_s_data)}")
            return

        unlocked_stage = int(mission_s_data.get("stage", 0) or 0)
        energy = int(mission_s_data.get("energy", 0) or 0)
        max_energy = int(mission_s_data.get("max_energy", 0) or 0)
        print(f"Mission S energy: {energy}/{max_energy} | unlocked stage: {unlocked_stage}")

        stage_to_run = resolve_stage_to_run(unlocked_stage, energy, char_level)
        if stage_to_run is None:
            print("Mission S has no unlocked stage available for the current level and energy")
            return

        stage_cfg = MISSION_S_STAGE_CONFIG[stage_to_run]
        mission = get_mission_by_id(stage_cfg["mission_id"])
        if not mission:
            print(f"Mission S data missing for stage {stage_to_run}")
            return

        print(f"Running Mission S stage {stage_to_run}: {mission['name']} (cost: {stage_cfg['energy_cost']})")

        battle_id = start_battle(mission, char_id, session_key, stage_to_run)
        if check_stop_event() or battle_id is None:
            return

        result = finish_battle(mission["id"], char_id, battle_id, session_key)
        if check_stop_event() or result is None:
            return

        if isinstance(result, dict) and result.get("status") == 1:
            rewards = result.get("result", [])
            xp = rewards[0] if len(rewards) > 0 else "n/a"
            gold = rewards[1] if len(rewards) > 1 else "n/a"
            level = result.get("level", char_level)
            try:
                char_level = int(level)
            except (TypeError, ValueError):
                pass
            print(f"Mission S completed: {mission['name']} | EXP: {xp}, Gold: {gold}, Level: {level}")
        else:
            print(f"Mission S finish failed: {response_message(result)}")
            return

        if not wait_with_stop_check(MISSION_S_BETWEEN_BATTLES_SECONDS):
            return
