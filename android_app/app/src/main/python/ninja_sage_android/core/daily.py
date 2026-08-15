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
from . import config

mission_list = open_json_to_dict("data/mission.json")
enemy_list = open_json_to_dict("data/enemy.json")
battle_hash = "eyJpdGVtcyI6eyJhY2Nlc3NvcnkiOiJhY2Nlc3NvcnlfMDEiLCJiYWNrX2l0ZW0iOiJiYWNrXzAxIiwid2VhcG9uIjoid3BuXzAxIiwic2V0Ijoic2V0XzAxXzAifSwic3RhdHVzIjp7ImVhcnRoIjowLCJmaXJlIjowLCJ3YXRlciI6MCwibGlnaHRuaW5nIjowLCJ3aW5kIjowfSwiYnl0ZXMiOnsiXyI6ODIyODQ0NywiX18iOjgyMjg0NDcsIl9fXyI6IjE3NjI3NDY2NTk0MDM2N2MzY2M5OTlhOWY5ZTk1MWExZDMzMjExNTQ1Yjg0YjJkNWE2MzkzM2IwMDIwNDMzMDAwYzNiYjQxMGZiMTc2Mjc0NjY1OTE3NjI3NDY2NTkxNzYyNzQ2NjU5MTc2Mjc0NjY1OSIsIl9fX19fIjo4MjI4NDQ3LCJfX19fX18iOjgyMjg0NDcsIl9fX18iOjE3NjI3NDY2NTl9LCJfX19fIjpbeyJfIjoic2tpbGxfMTMiLCJfXyI6MjkxMzR9XX0="
PRE_MISSION_DELAY_SECONDS = 2
BATTLE_SETTLE_DELAY_SECONDS = 5
POST_MISSION_DELAY_SECONDS = 3


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(getattr(config, name, default))
    except Exception:
        return int(default)


def check_stop_event():
    """Stop automation if a GUI request has been issued."""
    if hasattr(config, "stop_event") and config.stop_event.is_set():
        print("Automation stopped by user request")
        return True
    return False


def build_enemy_attributes(mission):
    """Return the enemy list and formatted attributes for the mission."""
    if check_stop_event():
        return [], ""

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


SAGE_SCROLL_MINIGAME_MISSION_IDS = {"msn_109", "msn_110", "msn_111"}


def _is_sage_scroll_mission(mission):
    return mission.get("id") in SAGE_SCROLL_MINIGAME_MISSION_IDS


def start_daily_battle(mission, char_flat, char_id, session_key):
    """Start a daily mission battle using the same protocol as leveling."""
    if check_stop_event():
        return None

    if _is_sage_scroll_mission(mission):
        time.sleep(PRE_MISSION_DELAY_SECONDS)
        start_result = send_amf_request(
            "BattleSystem.startSageScrollMiniGame",
            [char_id, session_key, mission["id"]],
        )
        print(f"Started SS daily mission {mission['id']} (result: {start_result})")
        battle_wait_seconds = _cfg_int("sage_battle_wait_seconds", BATTLE_SETTLE_DELAY_SECONDS)
        print(f"Waiting {battle_wait_seconds} seconds for battle to settle...")
        time.sleep(battle_wait_seconds)
        return start_result

    enemies, enemy_attrs = build_enemy_attributes(mission)
    if not enemies:
        print(f"Skipping {mission['id']} because enemy data could not be built")
        return None

    agility = StatManager.calculate_stats_with_data("agility", char_flat)
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
    ]

    # print(f"Waiting {PRE_MISSION_DELAY_SECONDS} seconds before starting {mission['id']}...")
    time.sleep(PRE_MISSION_DELAY_SECONDS)
    battle_id = send_amf_request("BattleSystem.startMission", parameters)
    print(f"Started daily mission {mission['id']} (battle id: {battle_id})")
    battle_wait_seconds = _cfg_int("sage_battle_wait_seconds", BATTLE_SETTLE_DELAY_SECONDS)
    print(f"Waiting {battle_wait_seconds} seconds for battle to settle...")
    time.sleep(battle_wait_seconds)
    return battle_id


def finish_daily_battle(mission_id, char_id, battle_id, session_key):
    """Finish a mission after the battle ID was created."""
    if check_stop_event():
        return None

    if mission_id in SAGE_SCROLL_MINIGAME_MISSION_IDS:
        parameters = [char_id, session_key, str(battle_id)]
        result = send_amf_request("BattleSystem.finishSageScrollMiniGame", parameters)
        save_fight_data(result)
        return result

    battle_id = str(battle_id)
    hash_input = f"{mission_id}{char_id}{battle_id}0"
    _loc2_ = CUCSG.hash(hash_input)
    parameters = [char_id, mission_id, battle_id, _loc2_, 0, session_key, battle_hash, 0]

    result = send_amf_request("BattleSystem.finishMission", parameters)
    save_fight_data(result)
    return result


def _normalize_mission_entries(raw_missions):
    """Normalize mission availability into a list of (mission_id, run_count)."""
    if not raw_missions:
        return []

    if isinstance(raw_missions, dict):
        mission_items = []
        for mission_id, available in raw_missions.items():
            try:
                run_count = max(int(available or 0), 0)
            except (TypeError, ValueError):
                run_count = 0
            mission_items.append((mission_id, run_count))
        return mission_items

    return [(mission_id, 1) for mission_id in raw_missions]


def _mission_entries_from_grade(grade):
    """Return mission.json entries for a specific mission grade."""
    return [
        (mission["id"], 1)
        for mission in mission_list
        if str(mission.get("grade", "")).lower() == grade
    ]


def _add_missing_grade_entries(grouped_missions, grade_key):
    """Add TP/SS missions from mission.json when room data omitted them."""
    existing_ids = {mission_id for mission_id, _ in grouped_missions.get(grade_key, [])}
    missing_entries = []

    for mission_id, run_count in _mission_entries_from_grade(grade_key.lower()):
        if mission_id in existing_ids:
            continue
        print(
            f"{grade_key} mission {mission_id} not available in room mission data, trying the mission anyway"
        )
        missing_entries.append((mission_id, 1))

    if missing_entries:
        grouped_missions.setdefault(grade_key, []).extend(missing_entries)


def _resolve_mission_group(mission_id):
    """Resolve the UI/logging group from mission.json grade."""
    mission_data = get_data_by_id(mission_id, mission_list) or {}
    grade = str(mission_data.get("grade", "")).lower()
    if grade == "tp":
        return "TP"
    if grade == "ss":
        return "SS"
    return "Daily"


def _merge_mission_items(mission_items, group, entries):
    """Merge mission entries by mission_id so TP/SS don't get duplicated."""
    for mission_id, run_count in entries:
        if not mission_id:
            continue
        try:
            normalized_count = max(int(run_count or 0), 0)
        except (TypeError, ValueError):
            normalized_count = 0
        if normalized_count <= 0:
            continue

        existing = next((idx for idx, item in enumerate(mission_items) if item[1] == mission_id), None)
        if existing is None:
            mission_items.append((group, mission_id, normalized_count))
            continue

        existing_group, _, existing_count = mission_items[existing]
        preferred_group = group if existing_group == "Daily" and group in {"TP", "SS"} else existing_group
        mission_items[existing] = (preferred_group, mission_id, max(existing_count, normalized_count))


def _extract_battle_id(start_result):
    """Extract a battle id from the startMission response."""
    if isinstance(start_result, dict):
        if start_result.get("status") != 1:
            return None
        return (
            start_result.get("code")
            or start_result.get("battle_id")
            or start_result.get("result")
            or start_result.get("id")
        )
    return start_result


def _get_character_rank():
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


def daily():
    if check_stop_event():
        return

    try:
        char_data = config.char_data
    except Exception as exc:
        print(f"Failed to load character data: {exc}")
        return

    char_flat = flatten_json(char_data)
    char_id = char_flat.get("character_data_character_id")
    char_level = char_flat.get("character_data_character_level", "unknown")
    char_rank = _get_character_rank()

    if not char_id:
        print("Character ID missing from saved data")
        return

    try:
        session_key = config.login_data["sessionkey"]
    except Exception as exc:
        print(f"Failed to load login session: {exc}")
        return

    try:
        available_mission = send_amf_request(
            "CharacterService.getMissionRoomData", [char_id, session_key]
        )
    except Exception as exc:
        print(f"Failed to retrieve daily missions: {exc}")
        return

    if available_mission.get("status") != 1:
        print("No available missions")
        return

    mission_items = []
    grouped_missions = {"Daily": [], "TP": [], "SS": []}

    room_entries = _normalize_mission_entries(available_mission.get("daily"))
    if room_entries:
        for mission_id, run_count in room_entries:
            group = _resolve_mission_group(mission_id)
            grouped_missions.setdefault(group, []).append((mission_id, run_count))

    tp_entries = _normalize_mission_entries(available_mission.get("tp"))
    if tp_entries:
        grouped_missions["TP"].extend(tp_entries)
    _add_missing_grade_entries(grouped_missions, "TP")

    ss_entries = _normalize_mission_entries(available_mission.get("ss"))
    if ss_entries:
        grouped_missions["SS"].extend(ss_entries)
    _add_missing_grade_entries(grouped_missions, "SS")

    daily_entries = grouped_missions.get("Daily", [])
    if daily_entries:
        available_daily_entries = []
        for mission_id, run_count in daily_entries:
            if run_count <= 0:
                print(f"Daily mission {mission_id} already finished today")
                continue
            available_daily_entries.append((mission_id, run_count))
        if available_daily_entries:
            _merge_mission_items(mission_items, "Daily", available_daily_entries)
        else:
            print("No daily missions currently available")
    else:
        print("No daily missions currently available")

    if isinstance(char_level, int) and isinstance(char_rank, int) and char_level >= 40 and char_rank >= 5:
        tp_entries = grouped_missions.get("TP") or _mission_entries_from_grade("tp")
        available_tp_entries = []
        for mission_id, run_count in tp_entries:
            if run_count <= 0:
                print(f"TP mission {mission_id} already finished today")
                continue
            available_tp_entries.append((mission_id, run_count))
        if available_tp_entries:
            _merge_mission_items(mission_items, "TP", available_tp_entries)
        else:
            print("No TP Mission")
    else:
        print("Skipping TP Mission: requires level 40+ and rank 5+")

    if isinstance(char_level, int) and isinstance(char_rank, int) and char_level >= 80 and char_rank >= 9:
        ss_entries = grouped_missions.get("SS") or _mission_entries_from_grade("ss")
        available_ss_entries = []
        for mission_id, run_count in ss_entries:
            if run_count <= 0:
                print(f"SS mission {mission_id} already finished today")
                continue
            available_ss_entries.append((mission_id, run_count))
        if available_ss_entries:
            _merge_mission_items(mission_items, "SS", available_ss_entries)
        else:
            print("No SS Mission")
    else:
        print("Skipping SS Mission: requires level 80+ and rank 9+")

    if not mission_items:
        return

    for mission_group, mission_id, run_count in mission_items:
        if check_stop_event():
            break

        if not mission_id:
            continue

        if run_count <= 0:
            continue

        mission_data = get_data_by_id(mission_id, mission_list)
        if not mission_data:
            print(f"Unknown mission config for {mission_id}")
            continue

        print(f"Running {mission_group} mission {mission_id} ({mission_data.get('name')})")

        for attempt in range(run_count):
            if check_stop_event():
                break

            print(f"Attempt {attempt + 1}/{run_count} for {mission_id}")
            try:
                start_result = start_daily_battle(
                    mission_data, char_flat, char_id, session_key
                )
                if not start_result:
                    break
                battle_id = _extract_battle_id(start_result)
                if not battle_id and _is_sage_scroll_mission(mission_data):
                    battle_id = "0"
                    print(f"{mission_group} mission {mission_id} started without battle id, using fallback 0")
                if not battle_id:
                    print(f"{mission_group} mission {mission_id} not available or already completed today")
                    break
                result = finish_daily_battle(mission_id, char_id, battle_id, session_key)
            except Exception as exc:
                print(f"Failed to complete mission {mission_id}: {exc}")
                break

            if not result:
                break

            if result.get("status") == 1:
                rewards = result.get("result") or []
                exp = rewards[0] if len(rewards) > 0 else "n/a"
                gold = rewards[1] if len(rewards) > 1 else "n/a"
                mission_reward_data = mission_data.get("rewards") or {}
                tp = rewards[2] if len(rewards) > 2 else mission_reward_data.get("tp", 0)
                ss = rewards[3] if len(rewards) > 3 else mission_reward_data.get("ss", 0)
                level = result.get("level", char_level)
                print(
                    f"{mission_group} mission {mission_id} complete: EXP: {exp}, Gold: {gold}, "
                    f"Level: {level}, Reward: {tp}"
                )
                char_level = level
            else:
                print(f"Mission {mission_id} returned unexpected payload: {result}")
                break
            post_finish_delay_seconds = _cfg_int("sage_post_finish_delay_seconds", POST_MISSION_DELAY_SECONDS)
            if attempt < run_count - 1:
                time.sleep(post_finish_delay_seconds)
        if not check_stop_event():
            post_finish_delay_seconds = _cfg_int("sage_post_finish_delay_seconds", POST_MISSION_DELAY_SECONDS)
            time.sleep(post_finish_delay_seconds)
    print("Daily missions completed")
