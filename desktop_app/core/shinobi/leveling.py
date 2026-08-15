import hashlib
import random
import re
import time

from .. import config
from .utils import get_device_id, get_shinobi_state, post_encrypted_json


SHINOBI_LEVELING_DELAY_SECONDS = 2
SHINOBI_MISSION_FINISH_DELAY_SECONDS = 6
SHINOBI_MISSION_BETWEEN_DELAY_SECONDS = 1
SHINOBI_DEBUG = True
SHINOBI_FORCE_TEST_MISSION_ID = None
SHINOBI_TEST_PATTERN = "skills"
SHINOBI_XTRA_TURN_RANGE = (15, 30)
SHINOBI_XTRA_DAMAGE_RANGE = (500, 1500)
SHINOBI_XTRA_SKILL_ID_RANGE = (10, 500)
SHINOBI_XTRA_FORCE_TEST_MISSION_ID = 1
# Checkpoint:
# - Keep this at 1 while debugging Training Dummy.
# - Set it to None to restore the normal mission picker.
# - Set SHINOBI_TEST_PATTERN to "captured", "weapon", or "skills" to switch test baselines.


def check_stop_event():
    if hasattr(config, "stop_event") and config.stop_event.is_set():
        print("Shinobi leveling stopped by user request")
        return True
    return False


def wait_with_stop_check(seconds: int) -> bool:
    for _ in range(max(0, int(seconds))):
        if check_stop_event():
            return False
        time.sleep(1)
    return True


def _settings() -> dict:
    try:
        return config.get_shinobi_settings()
    except Exception:
        return {}


def _cfg_int(name: str, default: int) -> int:
    value = _settings().get(name, default)
    try:
        return max(0, int(value))
    except Exception:
        return default


def _cfg_bool(name: str, default: bool) -> bool:
    value = _settings().get(name, default)
    return bool(value)


def _cfg_text(name: str, default: str) -> str:
    value = str(_settings().get(name, default) or default).strip().lower()
    return value or default


def _between_delay_seconds() -> int:
    return _cfg_int(
        "between_missions_delay_seconds",
        SHINOBI_MISSION_BETWEEN_DELAY_SECONDS,
    )


def _response_message(response) -> str:
    if response is None:
        return "No response"

    if isinstance(response, dict):
        for key in (
            "result",
            "message",
            "msg",
            "error_message",
            "body",
            "reason",
            "detail",
            "error",
        ):
            value = response.get(key)
            if value not in (None, "", False, 0):
                return str(value)
        return str(response)

    return str(response)


def _ensure_character_context():
    if not isinstance(config.char_data, dict):
        raise ValueError("Character data is not loaded in memory")
    if not isinstance(config.login_data, dict):
        raise ValueError("Login data is not loaded in memory")

    char_snapshot = config.char_data.get("character_data", config.char_data)
    if not isinstance(char_snapshot, dict):
        raise ValueError("Invalid Shinobi character snapshot")

    state = get_shinobi_state()
    access_token = state.get("access_token")
    user_key = (
        state.get("user_key")
        or config.login_data.get("user_key")
        or config.login_data.get("sessionkey")
    )
    char_id = char_snapshot.get("character_id") or char_snapshot.get("char_id")

    if not access_token:
        raise ValueError("Shinobi access token is missing")
    if not user_key:
        raise ValueError("Shinobi user key is missing")
    if not char_id:
        raise ValueError("Character ID is missing from Shinobi character data")

    return char_snapshot, access_token, user_key, char_id


def _md5_string(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


# def _build_mission_key(time_value, key_value) -> str:
#     return _md5_string(str(int(int(time_value) / 8) - int(key_value) * 765))
def _build_mission_key(time_value, key_value) -> str:
    return hashlib.md5(
        str(int(int(time_value) / 8) - int(key_value) * 765).encode("utf-8")
    ).hexdigest()

def _post(route: str, payload: dict | None = None):
    state = get_shinobi_state()
    return post_encrypted_json(route, payload or {}, access_token=state.get("access_token"))


def _auth_payload() -> dict:
    state = get_shinobi_state()
    payload = {
        "user_key": state.get("user_key"),
        "auth": get_device_id(),
    }
    return {key: value for key, value in payload.items() if value is not None}


def _load_recruits():
    return _post("friends/process_load_recruits.php", _auth_payload())


def _load_missions():
    response = _post("mission/process_load_missions.php", _auth_payload())

    if isinstance(response, dict):
        key = response.get("key")
        if isinstance(key, dict) and key.get("time") is not None and key.get("key") is not None:
            response["_panel_key"] = _build_mission_key(key["time"], key["key"])

    return response


def _load_enemy(enemy_id):
    return _post(
        "process_load_enemy_by_id.php",
        {
            **_auth_payload(),
            "id": int(enemy_id),
        },
    )


def _build_analysis(char_id, turns, actions, damages, enemy_analysis, friend_analysis=None):
    player_actions = list(actions)
    player_damages = list(damages)

    return {
        "player": {
            "player_id": int(char_id),
            "turns": int(turns),
            "damages": player_damages,
            "actions": player_actions,
            "npc": False,
        },
        "friends": list(friend_analysis or []),
        "enemies": enemy_analysis,
    }


def _normalize_complete_analysis(analysis):
    player = analysis.get("player", {}) if isinstance(analysis, dict) else {}
    friends = analysis.get("friends", []) if isinstance(analysis, dict) else []
    enemies = analysis.get("enemies", []) if isinstance(analysis, dict) else []

    player_turns = int(player.get("turns") or 0)
    player_actions = list(player.get("actions") or [])
    player_damages = list(player.get("damages") or [])

    normalized_player = {
        "player_id": int(player.get("player_id") or 0),
        "turns": player_turns,
        "damages": player_damages,
        "actions": player_actions,
        "npc": bool(player.get("npc", False)),
    }

    def _normalize_side(entries):
        normalized_entries = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            normalized_entries.append(
                {
                    "player_id": int(entry.get("player_id") or 0),
                    "turns": int(entry.get("turns") or 0),
                    "damages": list(entry.get("damages") or []),
                    "actions": list(entry.get("actions") or []),
                    "npc": bool(entry.get("npc", False)),
                }
            )
        return normalized_entries

    normalized = {
        "player": normalized_player,
        "friends": _normalize_side(friends),
        "enemies": _normalize_side(enemies),
    }
    return normalized, player_turns, player_actions, player_damages


def _first_turn_payload(actions, damages, fallback_action="weapon", fallback_damage=1):
    first_action = fallback_action
    first_damage = fallback_damage
    if actions:
        first_action = str(actions[0])
    if damages:
        try:
            first_damage = int(damages[0])
        except Exception:
            first_damage = fallback_damage
    return [first_action], [max(0, int(first_damage))]


def _build_client_like_short_analysis(normalized_analysis):
    player = normalized_analysis.get("player") or {}
    friends = normalized_analysis.get("friends") or []
    enemies = normalized_analysis.get("enemies") or []

    player_actions, player_damages = _first_turn_payload(
        player.get("actions") or [],
        player.get("damages") or [],
        fallback_action="weapon",
        fallback_damage=1,
    )
    short_player = {
        "player_id": int(player.get("player_id") or 0),
        "turns": 1,
        "damages": player_damages,
        "actions": player_actions,
        "npc": bool(player.get("npc", False)),
    }

    short_friends = []
    for friend in friends:
        friend_actions, friend_damages = _first_turn_payload(
            friend.get("actions") or [],
            friend.get("damages") or [],
            fallback_action="attack_01",
            fallback_damage=1,
        )
        short_friends.append(
            {
                "player_id": int(friend.get("player_id") or 0),
                "turns": 1,
                "damages": friend_damages,
                "actions": friend_actions,
                "npc": bool(friend.get("npc", True)),
            }
        )

    short_enemies = []
    for enemy in enemies:
        short_enemies.append(
            {
                "player_id": int(enemy.get("player_id") or 0),
                "turns": 0,
                "damages": [],
                "actions": [],
                "npc": bool(enemy.get("npc", True)),
            }
        )

    return {
        "player": short_player,
        "friends": short_friends,
        "enemies": short_enemies,
    }


def _complete_mission(mission_id, mission_key, analysis):
    normalized_analysis, player_turns, player_actions, player_damages = _normalize_complete_analysis(analysis)
    friend_count = len(normalized_analysis.get("friends") or [])
    payload_mode = _cfg_text("complete_payload_mode", "full")

    if payload_mode == "minimal_auth":
        payload = {
            **_auth_payload(),
            "victory": True,
            "missionId": int(mission_id),
            "key": mission_key,
            "turns": player_turns,
            "actions": player_actions,
        }
    elif payload_mode == "xtra_like":
        payload = {
            "user_key": get_shinobi_state().get("user_key"),
            "victory": True,
            "missionId": int(mission_id),
            "key": mission_key,
            "turns": player_turns,
            "actions": player_actions,
            "damages": player_damages,
            "friends": 0,
            "analysis": {
                "player": {
                    "turns": player_turns,
                    "actions": player_actions,
                    "damages": player_damages,
                },
                "friends": [],
                "enemies": [],
            },
        }
    elif payload_mode == "client_like_short":
        short_analysis = _build_client_like_short_analysis(normalized_analysis)
        short_player = short_analysis["player"]
        payload = {
            **_auth_payload(),
            "victory": True,
            "missionId": int(mission_id),
            "key": mission_key,
            "turns": short_player["turns"],
            "actions": list(short_player["actions"]),
            "damages": list(short_player["damages"]),
            "friends": len(short_analysis.get("friends") or []),
            "analysis": short_analysis,
        }
    else:
        payload = {
            **_auth_payload(),
            "victory": True,
            "missionId": int(mission_id),
            "key": mission_key,
            "turns": player_turns,
            "actions": player_actions,
            "damages": player_damages,
            "friends": friend_count,
            "analysis": normalized_analysis,
        }

    if SHINOBI_DEBUG:
        print("MISSION COMPLETE PAYLOAD:", payload)

    response = _post("mission/process_complete_mission.php", payload)

    if SHINOBI_DEBUG:
        print("MISSION COMPLETE RAW RESPONSE:", repr(response))

    return response


def _equipped_actions_from_char_data(char_snapshot: dict):
    raw_user_data = (
        char_snapshot.get("raw_user_data")
        if isinstance(char_snapshot.get("raw_user_data"), dict)
        else None
    )
    user_data = raw_user_data or char_snapshot
    equipped = user_data.get("equipped", {}) if isinstance(user_data, dict) else {}

    actions = []
    debug_sources = []

    def append_skill_tokens(value, source_name):
        appended = []

        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    token = item.strip().replace("_", "")
                    if re.fullmatch(r"skill\d+", token):
                        appended.append(token)

        elif isinstance(value, str):
            for part in value.split(","):
                token = part.strip().replace("_", "")
                if re.fullmatch(r"skill\d+", token):
                    appended.append(token)

        if appended:
            actions.extend(appended)
            debug_sources.append(f"{source_name}={appended}")

    append_skill_tokens(char_snapshot.get("equipped_skills"), "character_data.equipped_skills")

    if isinstance(equipped, dict):
        skills = equipped.get("skills")
        append_skill_tokens(skills, "equipped.skills")

        talent = equipped.get("talent")
        if talent:
            actions.append(str(talent))
            debug_sources.append(f"equipped.talent={[str(talent)]}")

    global_char_data = getattr(config, "char_data", None)
    if isinstance(global_char_data, dict):
        global_snapshot = global_char_data.get("character_data")
        if isinstance(global_snapshot, dict) and global_snapshot is not char_snapshot:
            append_skill_tokens(global_snapshot.get("equipped_skills"), "config.character_data.equipped_skills")

            global_raw_user_data = global_snapshot.get("raw_user_data")
            if isinstance(global_raw_user_data, dict):
                append_skill_tokens(
                    global_raw_user_data.get("equipped", {}).get("skills")
                    if isinstance(global_raw_user_data.get("equipped"), dict)
                    else None,
                    "config.raw_user_data.equipped.skills",
                )

    deduped = []
    seen = set()
    for action in actions:
        if not action or not str(action).strip():
            continue
        normalized = str(action).strip()
        if normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)

    preferred_source_actions = []
    for source_name in (
        "character_data.equipped_skills",
        "equipped.skills",
        "config.character_data.equipped_skills",
        "config.raw_user_data.equipped.skills",
    ):
        for entry in debug_sources:
            if not entry.startswith(source_name + "="):
                continue
            values = entry.split("=", 1)[1].strip()
            values = values.strip("[]")
            if not values:
                continue
            for part in values.split(","):
                token = part.strip().strip("'").strip('"')
                if re.fullmatch(r"skill\d+", token):
                    preferred_source_actions.append(token)

    if preferred_source_actions:
        deduped = []
        seen = set()
        for action in preferred_source_actions:
            if action not in seen:
                deduped.append(action)
                seen.add(action)

    fallback_actions = ["weapon", "skip", "charge"]

    if debug_sources:
        print("Detected Shinobi skill sources: " + " | ".join(debug_sources))
    else:
        visible_keys = sorted(char_snapshot.keys()) if isinstance(char_snapshot, dict) else []
        print(
            "No Shinobi skill ids detected in character data. "
            f"Visible character keys: {', '.join(visible_keys[:20])}"
        )

    return deduped or fallback_actions


def _resolve_action_pool(all_actions, preferred_actions):
    action_mode = _cfg_text("action_mode", "skills")
    cleaned_all = [str(action).strip() for action in all_actions if str(action).strip()]
    cleaned_skills = [str(action).strip() for action in preferred_actions if str(action).strip()]

    if action_mode == "weapon":
        return ["weapon"]
    if action_mode == "mixed":
        pool = []
        for action in cleaned_skills or cleaned_all:
            if action not in pool:
                pool.append(action)
        if "weapon" not in pool:
            pool.append("weapon")
        return pool or ["weapon"]
    return cleaned_skills or cleaned_all or ["weapon"]


def _mission_level_requirement(mission: dict):
    for key in ("levelRequired", "level_required", "level"):
        value = mission.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return 0


def _is_premium_user(char_snapshot: dict | None = None) -> bool:
    candidates = [
        getattr(config, "all_char", None),
        getattr(config, "char_data", None),
        getattr(config, "login_data", None),
        char_snapshot,
    ]

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        premium = candidate.get("premium")
        if premium is not None:
            return bool(premium)

        nested = candidate.get("character_data")
        if isinstance(nested, dict) and nested.get("premium") is not None:
            return bool(nested.get("premium"))

        raw = candidate.get("raw_user_data")
        if isinstance(raw, dict) and raw.get("premium") is not None:
            return bool(raw.get("premium"))

    return False


def _is_mission_available(mission: dict, char_level: int, is_premium_user: bool) -> bool:
    if not isinstance(mission, dict):
        return False
    if mission.get("playable") is False:
        return False
    if mission.get("premium") and not is_premium_user:
        return False
    return char_level >= _mission_level_requirement(mission)


def _flatten_enemy_ids(enemies):
    flattened = []

    if isinstance(enemies, list):
        for enemy in enemies:
            if isinstance(enemy, list):
                flattened.extend(_flatten_enemy_ids(enemy))
            elif isinstance(enemy, dict):
                enemy_id = enemy.get("id") or enemy.get("enemy_id") or enemy.get("player_id")
                if enemy_id is not None:
                    flattened.append(enemy_id)
            elif isinstance(enemy, str) and "," in enemy:
                flattened.extend(_flatten_enemy_ids([part.strip() for part in enemy.split(",") if part.strip()]))
            elif enemy is not None:
                flattened.append(enemy)

    elif isinstance(enemies, dict):
        enemy_id = enemies.get("id") or enemies.get("enemy_id") or enemies.get("player_id")
        if enemy_id is not None:
            flattened.append(enemy_id)

    elif isinstance(enemies, str) and "," in enemies:
        flattened.extend(_flatten_enemy_ids([part.strip() for part in enemies.split(",") if part.strip()]))

    elif enemies is not None:
        flattened.append(enemies)

    return flattened


def _enemy_count(mission: dict) -> int:
    enemies = _flatten_enemy_ids(mission.get("enemies"))
    return len(enemies)


def _select_mission(missions, char_level: int, is_premium_user: bool):
    available = [
        mission
        for mission in missions
        if _is_mission_available(mission, char_level, is_premium_user)
    ]

    if not available:
        return None

    if SHINOBI_FORCE_TEST_MISSION_ID is not None:
        for mission in available:
            if int(mission.get("id") or 0) == int(SHINOBI_FORCE_TEST_MISSION_ID):
                return mission

    completed_missions = [mission for mission in available if mission.get("completed") is True]
    mission_pool = completed_missions or available

    mission_pool.sort(
        key=lambda mission: (
            -int(mission.get("xp") or 0),
            _enemy_count(mission),
            _mission_level_requirement(mission),
            int(mission.get("id") or 0),
        )
    )

    return mission_pool[0]


def _estimate_turns(enemy_ids):
    max_level = 5

    for enemy_id in enemy_ids:
        if check_stop_event():
            return None

        response = _load_enemy(enemy_id)
        if not isinstance(response, dict) or response.get("error", 0):
            print(f"Failed to load enemy {enemy_id}: {_response_message(response)}")
            continue

        enemy_data = response.get("enemy_data") or {}
        if isinstance(enemy_data, dict):
            try:
                max_level = max(max_level, int(enemy_data.get("level") or 0))
            except (TypeError, ValueError):
                pass

    min_turns = max(5, max_level - 5)
    max_turns = max(min_turns, max_level)
    return random.randint(min_turns, max_turns)


def _load_enemy_profiles(enemy_ids):
    profiles = []

    for enemy_id in enemy_ids:
        if check_stop_event():
            return []

        response = _load_enemy(enemy_id)
        if not isinstance(response, dict) or response.get("error", 0):
            print(f"Failed to load enemy {enemy_id}: {_response_message(response)}")
            continue

        enemy_data = response.get("enemy_data") or {}
        if isinstance(enemy_data, dict):
            profiles.append(enemy_data)

    return profiles


def _load_friend_state():
    return _post("friends/process_load.php", _auth_payload())


def _recruit_npc(npc_id):
    return _post(
        "friends/process_recruit_npc.php",
        {
            **_auth_payload(),
            "npc_id": int(npc_id),
        },
    )


def _extract_recruit_catalog(friend_state: dict) -> list[dict]:
    if not isinstance(friend_state, dict):
        return []

    npc_entries = friend_state.get("npc")
    if isinstance(npc_entries, list):
        return npc_entries

    data = friend_state.get("data")
    if not isinstance(data, dict):
        return []

    npc_entries = data.get("npc")
    return npc_entries if isinstance(npc_entries, list) else []


def _extract_active_recruit_ids(friend_state: dict) -> list[int]:
    if not isinstance(friend_state, dict):
        return []

    recruits = friend_state.get("recruits")
    if not isinstance(recruits, list):
        data = friend_state.get("data")
        if not isinstance(data, dict):
            return []
        recruits = data.get("recruits")
    if not isinstance(recruits, list):
        return []

    active = []
    for recruit in recruits:
        if not isinstance(recruit, dict):
            continue
        recruit_id = recruit.get("id") or recruit.get("enemy_id") or recruit.get("player_id")
        if recruit_id is None:
            continue
        active.append(_safe_int(recruit_id))
    return [recruit_id for recruit_id in active if recruit_id > 0]


def _friendly_recruit_targets(friend_state: dict) -> list[dict]:
    catalog = _extract_recruit_catalog(friend_state)
    affordable = []
    gold_amount = _safe_int(
        (config.char_data or {}).get("character_data", {}).get("character_gold")
        if isinstance(getattr(config, "char_data", None), dict)
        else 0
    )

    for npc in catalog:
        if not isinstance(npc, dict):
            continue
        price = npc.get("price")
        if not isinstance(price, dict):
            continue
        if str(price.get("type")) != "gold":
            continue
        amount = _safe_int(price.get("amount"))
        if amount <= 0 or amount > gold_amount:
            continue
        if _safe_int(npc.get("enemy_id")) <= 0:
            continue
        affordable.append(npc)

    affordable.sort(key=lambda entry: (_safe_int(entry.get("level")), _safe_int(entry.get("id"))))
    return affordable


def _ensure_mission_recruits(char_snapshot: dict, mission: dict):
    recruit_mode = _cfg_text("recruit_mode", "keep_existing")
    if recruit_mode == "off":
        return []

    if mission.get("solo") is True:
        return []

    friend_state = _load_friend_state()
    if not isinstance(friend_state, dict) or friend_state.get("error", 0):
        print(f"Failed to load friend recruits: {_response_message(friend_state)}")
        return []

    active_ids = _extract_active_recruit_ids(friend_state)
    if active_ids:
        return active_ids

    if recruit_mode != "auto":
        return []

    recruited_any = False
    for npc in _friendly_recruit_targets(friend_state):
        if check_stop_event():
            return active_ids

        npc_id = _safe_int(npc.get("id"))
        enemy_id = _safe_int(npc.get("enemy_id"))
        if npc_id <= 0 or enemy_id <= 0:
            continue

        recruit_result = _recruit_npc(npc_id)
        if isinstance(recruit_result, dict) and not recruit_result.get("error", 0):
            recruited_any = True
            print(f"Recruited mission helper NPC {enemy_id} via catalog id {npc_id}")

            new_data = _extract_new_data(recruit_result)
            _apply_new_data(new_data)

            recruit_entries = recruit_result.get("recruits")
            if isinstance(recruit_entries, list):
                for recruit_entry in recruit_entries:
                    if not isinstance(recruit_entry, dict):
                        continue
                    recruit_id = _safe_int(
                        recruit_entry.get("id")
                        or recruit_entry.get("enemy_id")
                        or recruit_entry.get("player_id")
                    )
                    if recruit_id > 0 and recruit_id not in active_ids:
                        active_ids.append(recruit_id)
        else:
            print(f"Failed to recruit NPC {npc_id}: {_response_message(recruit_result)}")

    if recruited_any and not active_ids:
        refreshed_state = _load_friend_state()
        active_ids = _extract_active_recruit_ids(refreshed_state)

    return active_ids


def _build_enemy_analysis(enemy_profiles, player_turns: int):
    analysis = []

    for enemy in enemy_profiles:
        skill_ids = []
        skills = enemy.get("skills")

        if isinstance(skills, list):
            for skill in skills:
                if isinstance(skill, dict) and skill.get("id"):
                    skill_ids.append(str(skill["id"]))

        enemy_turns = max(0, int(player_turns) - 1)
        default_action = skill_ids[0] if skill_ids else "attack_01"

        analysis.append(
            {
                "player_id": int(enemy.get("id") or enemy.get("enemy_id") or 0),
                "turns": enemy_turns,
                "damages": [0 for _ in range(enemy_turns)],
                "actions": [default_action for _ in range(enemy_turns)],
                "npc": True,
            }
        )

    return analysis


def _build_friend_analysis(friend_profiles, player_turns: int):
    analysis = []

    for friend in friend_profiles or []:
        if not isinstance(friend, dict):
            continue

        turns = max(1, int(player_turns))
        base_damage = max(12, _safe_int(friend.get("damage"), 18))
        damages = [
            max(0, base_damage + random.Random(11000 + turn + _safe_int(friend.get("id"))).randint(-6, 6))
            for turn in range(turns)
        ]

        analysis.append(
            {
                "player_id": _safe_int(friend.get("id") or friend.get("enemy_id") or friend.get("player_id")),
                "turns": turns,
                "damages": damages,
                "actions": ["attack_01" for _ in range(turns)],
                "npc": True,
            }
        )

    return analysis


def _build_training_dummy_payload(preferred_actions):
    if SHINOBI_TEST_PATTERN == "captured":
        return {
            "turns": 3,
            "battle_actions": ["skill4", "skill13", "weapon"],
            "battle_damages": [27, 20, 7],
            "enemy_analysis": [
                {
                    "player_id": 1,
                    "turns": 2,
                    "damages": [0, 0],
                    "actions": ["attack_01", "attack_01"],
                    "npc": True,
                }
            ],
        }

    if SHINOBI_TEST_PATTERN == "weapon":
        return {
            "turns": 8,
            "battle_actions": ["weapon"] * 8,
            "battle_damages": [7, 7, 6, 7, 7, 7, 7, 7],
            "enemy_analysis": [
                {
                    "player_id": 1,
                    "turns": 7,
                    "damages": [0, 0, 0, 0, 0, 0, 0],
                    "actions": ["attack_01"] * 7,
                    "npc": True,
                }
            ],
        }

    ordered = []
    seen = set()

    for action in preferred_actions:
        normalized = str(action).strip()
        if normalized and normalized not in seen:
            ordered.append(normalized)
            seen.add(normalized)

    primary_skill = ordered[0] if ordered else None
    secondary_skill = ordered[1] if len(ordered) > 1 else primary_skill

    if not primary_skill:
        return None

    battle_actions = [primary_skill, secondary_skill, primary_skill]
    battle_damages = [21, 30, 17]
    turns = 3
    enemy_analysis = [
        {
            "player_id": 1,
            "turns": 2,
            "damages": [0, 0],
            "actions": ["attack_01", "attack_01"],
            "npc": True,
        }
    ]

    return {
        "turns": turns,
        "battle_actions": battle_actions,
        "battle_damages": battle_damages,
        "enemy_analysis": enemy_analysis,
    }


def _system_items():
    game_data = getattr(config, "game_data", None)
    if not isinstance(game_data, dict):
        return {}
    system_data = game_data.get("system_data")
    if not isinstance(system_data, dict):
        return {}
    items = system_data.get("items")
    return items if isinstance(items, dict) else {}


def _get_system_item(item_id: str | None):
    if not item_id:
        return None

    for bucket in _system_items().values():
        if isinstance(bucket, dict) and item_id in bucket:
            item = bucket[item_id]
            if isinstance(item, dict):
                return item
    return None


def _item_effects(item_data) -> list[dict]:
    if not isinstance(item_data, dict):
        return []
    effects = item_data.get("effect") or item_data.get("effects") or []
    return [effect for effect in effects if isinstance(effect, dict)]


def _effect_roll(seed: int, chance: int) -> bool:
    if chance <= 0:
        return False
    if chance >= 100:
        return True
    return random.Random(seed).randint(1, 100) <= chance


def _sum_effect_amount(effect_type: str, *item_groups, seed_base: int = 0) -> int:
    total = 0
    effect_index = 0

    for group in item_groups:
        for item in group or []:
            for effect in _item_effects(item):
                if effect.get("type") != effect_type:
                    effect_index += 1
                    continue

                chance = _safe_int(effect.get("chance"), 100)
                if _effect_roll(seed_base + effect_index, chance):
                    total += _safe_int(effect.get("amount"))
                effect_index += 1

    return total


def _parse_csv_ids(raw_value) -> list[str]:
    if isinstance(raw_value, list):
        return [str(value).strip() for value in raw_value if str(value).strip()]
    if not isinstance(raw_value, str):
        return []
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def _player_equipment_items(char_snapshot: dict):
    raw_user_data = char_snapshot.get("raw_user_data")
    equipped = raw_user_data.get("equipped", {}) if isinstance(raw_user_data, dict) else {}

    weapon = _get_system_item(equipped.get("weapon")) if isinstance(equipped, dict) else None
    backitem = _get_system_item(equipped.get("backitem")) if isinstance(equipped, dict) else None
    cloth = _get_system_item(equipped.get("body_set")) if isinstance(equipped, dict) else None

    skill_ids = _parse_csv_ids(equipped.get("skills")) if isinstance(equipped, dict) else []
    skill_items = [_get_system_item(skill_id) for skill_id in skill_ids]
    skill_items = [item for item in skill_items if isinstance(item, dict)]

    return {
        "weapon": weapon,
        "backitem": backitem,
        "cloth": cloth,
        "skills": skill_items,
        "skill_ids": skill_ids,
    }


def _build_player_battle_snapshot(char_snapshot: dict):
    level = _safe_int(char_snapshot.get("character_level") or char_snapshot.get("level"), 1)
    ability = _safe_int(
        (char_snapshot.get("raw_user_data") or {}).get("ability")
        if isinstance(char_snapshot.get("raw_user_data"), dict)
        else 0
    )
    ability_level = _safe_int(
        (char_snapshot.get("raw_user_data") or {}).get("ability_level")
        if isinstance(char_snapshot.get("raw_user_data"), dict)
        else 0,
        1,
    )

    equipment = _player_equipment_items(char_snapshot)
    gear_groups = [
        [equipment["cloth"]] if equipment["cloth"] else [],
        [equipment["weapon"]] if equipment["weapon"] else [],
        [equipment["backitem"]] if equipment["backitem"] else [],
        equipment["skills"],
    ]

    max_hp = (level - 1) * 40 + 100
    max_cp = (level - 1) * 40 + 100
    if ability == 0:
        max_hp += int(max_hp / 100 * (ability_level * 8))
    if ability == 2:
        max_cp += int(max_cp / 100 * (ability_level * 5))

    max_hp += int(max_hp / 100 * _sum_effect_amount("add_max_hp", *gear_groups, seed_base=100))
    max_hp += _sum_effect_amount("add_max_hp_number", *gear_groups, seed_base=200)

    max_cp += int(max_cp / 100 * _sum_effect_amount("add_max_cp", *gear_groups, seed_base=300))
    max_cp += _sum_effect_amount("add_max_cp_number", *gear_groups, seed_base=400)

    agility = level + 10
    agility_bonus_percent = _sum_effect_amount("add_agility_percent", *gear_groups, seed_base=500)
    if ability == 4:
        agility_bonus_percent += ability_level * 2
    if ability == 3:
        agility_bonus_percent += ability_level * 1
    agility += _sum_effect_amount("add_agility", *gear_groups, seed_base=600)
    agility += int(agility / 100 * agility_bonus_percent)
    agility = max(agility, level + 10 + int((level + 10) / 100 * 30))

    dodge = 5 + _sum_effect_amount("add_dodge_random", *gear_groups, seed_base=700)
    if ability == 4:
        dodge += ability_level * 2

    critical = 5 + _sum_effect_amount("add_critical_chance", *gear_groups, seed_base=800)
    if ability == 3:
        critical += ability_level * 2

    accuracy = _sum_effect_amount("add_dodge_reduction", *gear_groups, seed_base=900)
    damage_bonus = _sum_effect_amount("add_damage_bonus", *gear_groups, seed_base=1000)

    return {
        "level": level,
        "ability": ability,
        "ability_level": ability_level,
        "max_hp": max_hp,
        "max_cp": max_cp,
        "hp": max_hp,
        "cp": max_cp,
        "agility": agility,
        "dodge": dodge,
        "critical": critical,
        "accuracy": accuracy,
        "damage_bonus": damage_bonus,
        "equipment": equipment,
    }


def _build_enemy_battle_snapshot(enemy_profile: dict):
    level = _safe_int(enemy_profile.get("level"), 1)
    agility = max(level + 10, level + 10 + int((level + 10) / 100 * 30))
    agility += _safe_int(enemy_profile.get("speed"))
    return {
        "id": _safe_int(enemy_profile.get("id")),
        "name": enemy_profile.get("name", f"Enemy {_safe_int(enemy_profile.get('id'))}"),
        "level": level,
        "max_hp": _safe_int(enemy_profile.get("max_hp"), 1),
        "max_cp": _safe_int(enemy_profile.get("max_cp"), 0),
        "hp": _safe_int(enemy_profile.get("max_hp"), 1),
        "cp": _safe_int(enemy_profile.get("max_cp"), 0),
        "accuracy": _safe_int(enemy_profile.get("accuracy")),
        "critical": _safe_int(enemy_profile.get("critical"), 5),
        "dodge": _safe_int(enemy_profile.get("dodge"), 5),
        "agility": agility,
        "skills": enemy_profile.get("skills") if isinstance(enemy_profile.get("skills"), list) else [],
    }


def _action_item_from_token(player_snapshot: dict, token: str):
    token = str(token).strip()
    if token == "weapon":
        return player_snapshot["equipment"]["weapon"]
    return _get_system_item(token)


def _action_cp_cost(action_item, action_token: str) -> int:
    if str(action_token) in {"weapon", "charge", "skip"}:
        return 0
    return _safe_int((action_item or {}).get("cp"))


def _roll_base_damage(action_item, seed: int) -> int:
    if not isinstance(action_item, dict):
        return 0
    base_damage = _safe_int(action_item.get("damage"))
    if base_damage <= 0:
        return 0

    modifier = random.Random(seed).randint(-20, 20)
    rolled = base_damage + int(base_damage / 100 * modifier)
    return max(1, rolled)


def _resolve_attack_damage(action_token: str, player_snapshot: dict, enemy_snapshot: dict, turn_index: int):
    action_item = _action_item_from_token(player_snapshot, action_token)
    if str(action_token) == "charge":
        player_snapshot["cp"] = min(player_snapshot["max_cp"], player_snapshot["cp"] + 60)
        return 0

    if str(action_token) == "skip":
        return 0

    if not isinstance(action_item, dict):
        return 0

    cp_cost = _action_cp_cost(action_item, action_token)
    if cp_cost > player_snapshot["cp"]:
        return 0
    player_snapshot["cp"] -= cp_cost

    dodge_roll = random.Random(2000 + turn_index).randint(1, 100)
    dodge_chance = enemy_snapshot["dodge"] - player_snapshot["accuracy"]
    if dodge_roll <= dodge_chance:
        return 0

    damage = _roll_base_damage(action_item, 3000 + turn_index)

    element = str(action_item.get("type") or action_item.get("element") or "")
    if element == "taijutsu":
        damage += int(damage / 100 * player_snapshot["damage_bonus"])
    else:
        damage += int(damage / 100 * player_snapshot["damage_bonus"])

    crit_roll = random.Random(4000 + turn_index).randint(1, 100)
    if crit_roll <= player_snapshot["critical"]:
        damage += int(damage / 100 * 30)

    return max(0, damage)


def _simulate_enemy_action(enemy_snapshot: dict, player_snapshot: dict, turn_index: int):
    default_action = "attack_01"
    if enemy_snapshot["skills"]:
        default_action = str(enemy_snapshot["skills"][0].get("id") or default_action)

    dodge_roll = random.Random(5000 + turn_index).randint(1, 100)
    if dodge_roll <= player_snapshot["dodge"] - enemy_snapshot["accuracy"]:
        return default_action, 0

    action_item = enemy_snapshot["skills"][0] if enemy_snapshot["skills"] else {"damage": 0}
    damage = _roll_base_damage(action_item, 6000 + turn_index)
    damage = max(0, int(damage * 0.45))
    crit_roll = random.Random(7000 + turn_index).randint(1, 100)
    if crit_roll <= enemy_snapshot["critical"]:
        damage += int(damage / 100 * 30)
    player_snapshot["hp"] = max(0, player_snapshot["hp"] - damage)
    return default_action, max(0, damage)


def _simulate_friend_action(friend_snapshot: dict, enemy_snapshot: dict, turn_index: int):
    action_item = friend_snapshot.get("action_item") or {}
    action_token = str(friend_snapshot.get("action_token") or "attack_01")

    dodge_roll = random.Random(8000 + turn_index + friend_snapshot["id"]).randint(1, 100)
    dodge_chance = max(0, enemy_snapshot["dodge"] - friend_snapshot["accuracy"])
    if dodge_roll <= dodge_chance:
        return action_token, 0

    damage = _roll_base_damage(action_item, 9000 + turn_index + friend_snapshot["id"])
    damage = max(1, int(damage * 1.35))
    crit_roll = random.Random(10000 + turn_index + friend_snapshot["id"]).randint(1, 100)
    if crit_roll <= friend_snapshot["critical"]:
        damage += int(damage / 100 * 30)

    damage += int(damage / 100 * friend_snapshot["damage_bonus"])
    enemy_snapshot["hp"] = max(0, enemy_snapshot["hp"] - damage)
    return action_token, max(0, damage)


def _build_friend_battle_snapshot(enemy_profile: dict):
    snapshot = _build_enemy_battle_snapshot(enemy_profile)
    action_token = "attack_01"
    action_item = {"damage": max(1, _safe_int(enemy_profile.get("damage"), 15))}

    if snapshot["skills"]:
        first_skill = snapshot["skills"][0]
        action_token = str(first_skill.get("id") or action_token)
        if isinstance(first_skill, dict):
            action_item = first_skill

    return {
        "id": snapshot["id"],
        "name": snapshot["name"],
        "hp": snapshot["hp"],
        "max_hp": snapshot["max_hp"],
        "accuracy": snapshot["accuracy"],
        "critical": snapshot["critical"],
        "dodge": snapshot["dodge"],
        "agility": snapshot["agility"],
        "damage_bonus": 0,
        "action_token": action_token,
        "action_item": action_item,
    }


def _simulate_mission_battle(char_snapshot: dict, preferred_actions, enemy_profiles, friend_profiles=None):
    player_snapshot = _build_player_battle_snapshot(char_snapshot)
    enemy_snapshots = [_build_enemy_battle_snapshot(enemy) for enemy in enemy_profiles]
    friend_snapshots = [
        _build_friend_battle_snapshot(friend_profile)
        for friend_profile in (friend_profiles or [])
        if isinstance(friend_profile, dict)
    ]
    if not enemy_snapshots:
        return None

    ordered_actions = []
    cooldowns = {}
    for action in preferred_actions:
        normalized = str(action).strip()
        if normalized and normalized not in ordered_actions:
            ordered_actions.append(normalized)

    if player_snapshot["equipment"]["weapon"]:
        ordered_actions.append("weapon")
    ordered_actions.extend(["charge", "skip"])

    player_actions = []
    player_damages = []
    enemy_analysis = [
        {
            "player_id": enemy["id"],
            "turns": 0,
            "damages": [],
            "actions": [],
            "npc": True,
        }
        for enemy in enemy_snapshots
    ]
    friend_analysis = [
        {
            "player_id": friend["id"],
            "turns": 0,
            "damages": [],
            "actions": [],
            "npc": True,
        }
        for friend in friend_snapshots
    ]

    max_turns = 20
    total_turns = 0
    player_goes_first = player_snapshot["agility"] >= max(enemy["agility"] for enemy in enemy_snapshots)

    while total_turns < max_turns and player_snapshot["hp"] > 0:
        living_enemies = [enemy for enemy in enemy_snapshots if enemy["hp"] > 0]
        if not living_enemies:
            break

        turn_order = ["player", *living_enemies] if player_goes_first else [*living_enemies, "player"]

        for actor in turn_order:
            if actor == "player":
                target = next((enemy for enemy in enemy_snapshots if enemy["hp"] > 0), None)
                if target is None:
                    break

                selected_action = "skip"
                for action in ordered_actions:
                    action_item = _action_item_from_token(player_snapshot, action)
                    if action.startswith("skill"):
                        remaining_cd = cooldowns.get(action, 0)
                        if remaining_cd > 0:
                            continue
                        if _action_cp_cost(action_item, action) > player_snapshot["cp"]:
                            continue
                    selected_action = action
                    break

                damage = _resolve_attack_damage(selected_action, player_snapshot, target, total_turns)
                if damage > 0:
                    damage = max(1, int(damage * 1.25))
                player_actions.append(selected_action)
                player_damages.append(damage)
                total_turns += 1

                if selected_action.startswith("skill"):
                    action_item = _action_item_from_token(player_snapshot, selected_action) or {}
                    cooldowns[selected_action] = _safe_int(action_item.get("cooldown"))

                if damage > 0:
                    target["hp"] = max(0, target["hp"] - damage)

                if selected_action == "charge":
                    player_snapshot["hp"] = min(player_snapshot["max_hp"], player_snapshot["hp"] + 0)

                for key in list(cooldowns):
                    if cooldowns[key] > 0 and key != selected_action:
                        cooldowns[key] -= 1

                for friend in friend_snapshots:
                    target = next((enemy for enemy in enemy_snapshots if enemy["hp"] > 0), None)
                    if target is None:
                        break
                    friend_action, friend_damage = _simulate_friend_action(friend, target, total_turns)
                    friend_entry = next(
                        (entry for entry in friend_analysis if entry["player_id"] == friend["id"]),
                        None,
                    )
                    if friend_entry is not None:
                        friend_entry["actions"].append(friend_action)
                        friend_entry["damages"].append(friend_damage)
                        friend_entry["turns"] += 1

            else:
                enemy = actor
                if enemy["hp"] <= 0:
                    continue

                enemy_action, enemy_damage = _simulate_enemy_action(enemy, player_snapshot, total_turns)
                enemy_entry = next((entry for entry in enemy_analysis if entry["player_id"] == enemy["id"]), None)
                if enemy_entry is not None:
                    enemy_entry["actions"].append(enemy_action)
                    enemy_entry["damages"].append(enemy_damage)
                    enemy_entry["turns"] += 1

            if player_snapshot["hp"] <= 0:
                player_snapshot["hp"] = 1
                break

        if all(enemy["hp"] <= 0 for enemy in enemy_snapshots):
            break

    cleanup_turn_budget = 4
    while any(enemy["hp"] > 0 for enemy in enemy_snapshots) and cleanup_turn_budget > 0:
        target = next((enemy for enemy in enemy_snapshots if enemy["hp"] > 0), None)
        if target is None:
            break

        player_actions.append("weapon")
        finisher_damage = max(15, int(player_snapshot["damage_bonus"]) + 25)
        player_damages.append(finisher_damage)
        target["hp"] = max(0, target["hp"] - finisher_damage)

        for friend in friend_snapshots:
            if target["hp"] <= 0:
                target = next((enemy for enemy in enemy_snapshots if enemy["hp"] > 0), None)
                if target is None:
                    break
            friend_action, friend_damage = _simulate_friend_action(friend, target, total_turns + cleanup_turn_budget)
            friend_entry = next(
                (entry for entry in friend_analysis if entry["player_id"] == friend["id"]),
                None,
            )
            if friend_entry is not None:
                friend_entry["actions"].append(friend_action)
                friend_entry["damages"].append(friend_damage)
                friend_entry["turns"] += 1

        cleanup_turn_budget -= 1

    return {
        "turns": len(player_actions),
        "battle_actions": player_actions,
        "battle_damages": player_damages,
        "friend_analysis": friend_analysis,
        "enemy_analysis": enemy_analysis,
    }


def _extract_new_data(result: dict):
    if not isinstance(result, dict):
        return {}

    for key in ("newData", "user_data", "data", "result"):
        candidate = result.get(key)
        if isinstance(candidate, dict):
            return candidate

    return {}


def _apply_new_data(new_data: dict):
    if not isinstance(new_data, dict):
        return

    if not isinstance(config.char_data, dict):
        return

    char_snapshot = config.char_data.get("character_data", config.char_data)
    if not isinstance(char_snapshot, dict):
        return

    updates = {}

    if new_data.get("level") is not None:
        char_snapshot["character_level"] = int(new_data["level"])
        char_snapshot["level"] = int(new_data["level"])
        updates["level"] = int(new_data["level"])

    xp_value = new_data.get("xp")
    max_xp_value = new_data.get("max_xp")

    if isinstance(xp_value, (list, tuple)):
        if xp_value:
            max_xp_value = xp_value[1] if len(xp_value) > 1 else max_xp_value
            xp_value = xp_value[0]
        else:
            xp_value = 0

    if xp_value is not None:
        char_snapshot["character_xp"] = int(xp_value)
        char_snapshot["xp"] = int(xp_value)
        updates["xp"] = int(xp_value)

    if max_xp_value is not None:
        char_snapshot["character_max_xp"] = int(max_xp_value)
        char_snapshot["max_xp"] = int(max_xp_value)

    if new_data.get("gold") is not None:
        char_snapshot["character_gold"] = int(new_data["gold"])
        char_snapshot["gold"] = int(new_data["gold"])
        updates["gold"] = int(new_data["gold"])

    if new_data.get("status") is not None:
        char_snapshot["character_rank"] = int(new_data["status"])
        char_snapshot["rank"] = int(new_data["status"])

    if new_data.get("talent_points") is not None:
        char_snapshot["character_tp"] = int(new_data["talent_points"])
        char_snapshot["tp"] = int(new_data["talent_points"])

    if new_data.get("token") is not None:
        char_snapshot["tokens"] = int(new_data["token"])
        updates["tokens"] = int(new_data["token"])

    raw_user_data = char_snapshot.get("raw_user_data")
    if isinstance(raw_user_data, dict):
        raw_user_data.update(new_data)

    callback = getattr(config, "character_update_callback", None)
    if callable(callback) and updates:
        callback(updates)


def _log_reward_pack(result: dict):
    pack = result.get("pack") if isinstance(result, dict) else None
    if not isinstance(pack, dict):
        return

    items = pack.get("items")
    if not isinstance(items, list) or not items:
        return

    reward_parts = []
    for item in items:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type", "item")
        amount = item.get("amount")
        data = item.get("data")

        if amount is not None:
            reward_parts.append(f"{item_type}: {amount}")
        elif data is not None:
            reward_parts.append(f"{item_type}: {data}")

    if reward_parts:
        print("Extra rewards: " + ", ".join(reward_parts))


def _resolve_mission_key(mission: dict, missions_response: dict):
    mission_key = (
        mission.get("key")
        or mission.get("missionKey")
        or mission.get("mission_key")
        or missions_response.get("_panel_key")
    )

    if SHINOBI_DEBUG:
        print("Resolved mission key:", mission_key)

    return mission_key


def _is_success_response(result):
    if not isinstance(result, dict):
        return False

    if result.get("status") == 1:
        return True

    if result.get("error") in (0, "0", None) and isinstance(result.get("newData"), dict):
        return True

    if result.get("reward") or result.get("pack") or result.get("battle_pass_tasks") is not None:
        return True

    return False


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _xtra_select_mission(missions, char_level: int):
    mission_pool = []

    for mission in missions:
        if not isinstance(mission, dict):
            continue
        if mission.get("playable") is False:
            continue
        if mission.get("completed"):
            continue
        if mission.get("premium") is True:
            continue
        if char_level < _mission_level_requirement(mission):
            continue
        mission_pool.append(mission)

    if not mission_pool:
        return None

    if SHINOBI_XTRA_FORCE_TEST_MISSION_ID is not None:
        for mission in mission_pool:
            if _safe_int(mission.get("id")) == _safe_int(SHINOBI_XTRA_FORCE_TEST_MISSION_ID):
                return mission

    mission_pool.sort(
        key=lambda mission: (
            -_safe_int(mission.get("xp")),
            _safe_int(mission.get("id")),
        )
    )
    return mission_pool[0]


def _xtra_select_exam(missions):
    for mission in missions or []:
        if not isinstance(mission, dict):
            continue
        if mission.get("completed"):
            continue
        if mission.get("playable"):
            return mission
    return None


def _xtra_validate_enemy_loads(enemy_ids):
    for enemy_id in enemy_ids:
        if check_stop_event():
            return False

        response = _load_enemy(enemy_id)
        if not isinstance(response, dict):
            print(f"Failed to load enemy {enemy_id}: {_response_message(response)}")
            return False

        if response.get("status") not in (None, 1, "1") and response.get("error") not in (None, 0, "0"):
            print(f"Failed to load enemy {enemy_id}: {_response_message(response)}")
            return False

    return True


def _xtra_build_battle():
    turns = random.randint(*SHINOBI_XTRA_TURN_RANGE)
    action_pool = None
    if isinstance(getattr(config, "char_data", None), dict):
        char_snapshot = config.char_data.get("character_data", config.char_data)
        if isinstance(char_snapshot, dict):
            detected_actions = [
                action
                for action in _equipped_actions_from_char_data(char_snapshot)
                if str(action).startswith("skill")
            ]
            if detected_actions:
                action_pool = detected_actions

    if not action_pool:
        action_pool = [
            f"skill{random.randint(*SHINOBI_XTRA_SKILL_ID_RANGE)}"
            for _ in range(max(3, turns))
        ]

    actions = [
        random.choice(action_pool)
        for _ in range(turns)
    ]
    damages = [
        random.randint(*SHINOBI_XTRA_DAMAGE_RANGE)
        for _ in range(turns)
    ]
    analysis = _build_analysis(
        0,
        turns,
        actions,
        damages,
        [],
    )
    analysis["player"].pop("player_id", None)
    analysis["player"].pop("npc", None)
    return turns, actions, damages, analysis


def _xtra_player_analysis(turns, actions, damages):
    char_snapshot, _access_token, _user_key, char_id = _ensure_character_context()
    return _build_analysis(
        char_id,
        turns,
        actions,
        damages,
        [],
    )


def _xtra_calc_progress(before_level, before_xp, before_max_xp, before_gold, new_data: dict):
    new_level = _safe_int(new_data.get("level"), before_level)
    new_xp = new_data.get("xp", before_xp)
    if isinstance(new_xp, (list, tuple)):
        new_xp = new_xp[0] if new_xp else 0
    new_xp = _safe_int(new_xp, before_xp)
    new_gold = _safe_int(new_data.get("gold"), before_gold)

    same_level = new_level == before_level
    gained_xp = 0
    if same_level:
        gained_xp = max(0, new_xp - before_xp)
    elif new_level > before_level:
        gained_xp = max(0, before_max_xp - before_xp + new_xp)

    gained_gold = max(0, new_gold - before_gold)
    return {
        "same_level": same_level,
        "gained_xp": gained_xp,
        "gained_gold": gained_gold,
    }


def _load_tensai_exams():
    response = _post("mission/process_load_tensai_exams.php", _auth_payload())

    if isinstance(response, dict):
        key = response.get("key")
        if isinstance(key, dict) and key.get("time") is not None and key.get("key") is not None:
            response["_panel_key"] = _build_mission_key(key["time"], key["key"])

    return response


def _load_daily_missions():
    response = _post("mission/process_load_daily_missions.php", _auth_payload())

    if isinstance(response, dict):
        key = response.get("key")
        if isinstance(key, dict) and key.get("time") is not None and key.get("key") is not None:
            response["_panel_key"] = _build_mission_key(key["time"], key["key"])

    return response


def _load_daily_bootstrap():
    return _post("daily/process_load.php", _auth_payload())


def _bootstrap_action_state():
    response = _load_daily_bootstrap()
    if not isinstance(response, dict) or response.get("status") != 1:
        raise ValueError(f"Failed to bootstrap Shinobi action state: {_response_message(response)}")
    return response


def _load_bosses():
    response = _post("mission/process_load_bosses.php", _auth_payload())

    if isinstance(response, dict):
        key = response.get("key")
        if isinstance(key, dict) and key.get("time") is not None and key.get("key") is not None:
            response["_panel_key"] = _build_mission_key(key["time"], key["key"])

    return response


def _load_arena():
    return _post("arena/process_load_arena.php", _auth_payload())


def _restore_arena_power():
    return _post("arena/process_restore.php", _auth_payload())


def _load_arena_enemies():
    response = _post("arena/process_load_enemies.php", _auth_payload())

    if isinstance(response, dict):
        key = response.get("key")
        if isinstance(key, dict) and key.get("time") is not None and key.get("key") is not None:
            response["_panel_key"] = _build_mission_key(key["time"], key["key"])

    return response


def _load_events():
    return _post("events/process_load_events.php", _auth_payload())


def _load_event_data():
    return _post("events/process_load_data.php", _auth_payload())


def _start_event_mission(event_id, mission_id):
    return _post(
        "events/process_start_mission.php",
        {
            **_auth_payload(),
            "event_id": int(event_id),
            "mission_id": int(mission_id),
        },
    )


def _restore_event_energy():
    return _post("events/process_restore.php", _auth_payload())


def _xtra_complete_route(route: str, payload: dict):
    response = _post(route, payload)

    if SHINOBI_DEBUG:
        print(f"XTRA COMPLETE ROUTE {route} PAYLOAD:", payload)
        print(f"XTRA COMPLETE ROUTE {route} RESPONSE:", repr(response))

    return response


def _xtra_prepare_progress_snapshot(char_snapshot: dict):
    before_level = _safe_int(char_snapshot.get("character_level") or char_snapshot.get("level"))
    before_gold = _safe_int(char_snapshot.get("character_gold") or char_snapshot.get("gold"))
    before_xp = char_snapshot.get("character_xp", char_snapshot.get("xp", 0))
    before_max_xp = char_snapshot.get("character_max_xp", char_snapshot.get("max_xp", 0))

    if isinstance(before_xp, (list, tuple)):
        before_xp = before_xp[0] if before_xp else 0

    return {
        "level": _safe_int(before_level),
        "gold": _safe_int(before_gold),
        "xp": _safe_int(before_xp),
        "max_xp": _safe_int(before_max_xp),
    }


def _xtra_apply_result(char_snapshot: dict, result: dict):
    snapshot = _xtra_prepare_progress_snapshot(char_snapshot)
    new_data = _extract_new_data(result)
    progress = _xtra_calc_progress(
        snapshot["level"],
        snapshot["xp"],
        snapshot["max_xp"],
        snapshot["gold"],
        new_data,
    )
    _apply_new_data(new_data)
    return new_data, progress


def _xtra_select_daily_mission(missions, char_level: int):
    for mission in missions or []:
        if not isinstance(mission, dict):
            continue
        if mission.get("completed"):
            continue
        if mission.get("premium") is True:
            continue
        if char_level < _mission_level_requirement(mission):
            continue
        return mission
    return None


def _xtra_select_boss(response: dict, char_level: int):
    bosses = response.get("bosses")
    completed = response.get("bosses_completed")
    if not isinstance(bosses, list):
        return None

    for index, boss in enumerate(bosses):
        if not isinstance(boss, dict):
            continue
        if _safe_int(boss.get("level")) > char_level:
            continue
        if isinstance(completed, list) and index < len(completed) and _safe_int(completed[index]) == 1:
            continue
        return boss

    return None


def _xtra_select_event(events_response: dict):
    events = events_response.get("events")
    if not isinstance(events, list):
        return None

    for event in events:
        if not isinstance(event, dict):
            continue
        if _xtra_select_event_mission(event):
            return event
    return None


def _xtra_select_event_mission(event: dict):
    missions = event.get("missions")
    if not isinstance(missions, list):
        return None

    for mission in missions:
        if not isinstance(mission, dict):
            continue
        if mission.get("playable") is False:
            continue
        return mission
    return None


def _xtra_complete_standard(route: str, mission_id, mission_key, user_key):
    turns, battle_actions, battle_damages, _analysis = _xtra_build_battle()
    analysis = _xtra_player_analysis(turns, battle_actions, battle_damages)
    payload = {
        **_auth_payload(),
        "turns": turns,
        "actions": battle_actions,
        "damages": battle_damages,
        "analysis": analysis,
        "friends": 0,
        "missionId": int(mission_id),
        "victory": True,
        "key": mission_key,
    }
    return _xtra_complete_route(route, payload)


def shinobi_leveling():
    char_snapshot, _access_token, user_key, char_id = _ensure_character_context()
    _bootstrap_action_state()
    actions = _equipped_actions_from_char_data(char_snapshot)

    if not actions:
        raise ValueError("No equipped actions found for Shinobi leveling")

    premium_user = _is_premium_user(char_snapshot)

    print("Starting Shinobi Warfare leveling...")
    print(f"Character ID: {char_id} | User key: {user_key} | Action pool: {', '.join(actions)}")
    print(f"Account type: {'Premium' if premium_user else 'Free User'}")

    while not check_stop_event():
        char_level = int(char_snapshot.get("character_level") or char_snapshot.get("level") or 0)

        recruits_response = _load_recruits()
        if not isinstance(recruits_response, dict) or recruits_response.get("error", 0):
            print(f"Failed to load recruits: {_response_message(recruits_response)}")
            return

        missions_response = _load_missions()
        if not isinstance(missions_response, dict) or missions_response.get("error", 0):
            print(f"Failed to load missions: {_response_message(missions_response)}")
            return

        missions = missions_response.get("missions")
        if not isinstance(missions, list):
            print("Mission list data is incomplete")
            return

        mission = _select_mission(missions, char_level, premium_user)
        if not mission:
            print("No playable Shinobi missions are available for the current level")
            return

        mission_id = mission.get("id")
        mission_name = mission.get("name", f"Mission {mission_id}")
        mission_xp = int(mission.get("xp") or 0)
        mission_gold = int(mission.get("gold") or 0)
        enemy_ids = _flatten_enemy_ids(mission.get("enemies"))
        mission_key = _resolve_mission_key(mission, missions_response)

        if not isinstance(mission_key, str) or len(mission_key) != 32:
            print(f"Invalid mission key before completion: {mission_key!r}")
            return

        print(
            f"Running mission {mission_id} - {mission_name} "
            f"(Lv req: {_mission_level_requirement(mission)}, XP: {mission_xp}, Gold: {mission_gold})"
        )

        if enemy_ids:
            print("Mission enemies: " + ", ".join(str(enemy_id) for enemy_id in enemy_ids))

        enemy_profiles = _load_enemy_profiles(enemy_ids) if enemy_ids else []
        recruit_ids = _ensure_mission_recruits(char_snapshot, mission)
        friend_profiles = _load_enemy_profiles(recruit_ids) if recruit_ids else []
        if friend_profiles:
            print("Mission recruits: " + ", ".join(str(friend.get("id")) for friend in friend_profiles))

        preferred_actions = [action for action in actions if str(action).startswith("skill")]
        action_pool = _resolve_action_pool(actions, preferred_actions)

        simulated_payload = None
        if _cfg_bool("use_simulated_battle", True):
            simulated_payload = _simulate_mission_battle(
                char_snapshot,
                action_pool,
                enemy_profiles,
                friend_profiles=friend_profiles,
            )
        default_friend_analysis = _build_friend_analysis(friend_profiles, max(1, len(enemy_profiles) + 1))

        if simulated_payload:
            turns = simulated_payload["turns"]
            battle_actions = simulated_payload["battle_actions"]
            battle_damages = simulated_payload["battle_damages"]
            friend_analysis = simulated_payload.get("friend_analysis") or []
            enemy_analysis = simulated_payload["enemy_analysis"]
            print("Using client-like Shinobi battle simulation")
            print("Simulated actions: " + ", ".join(battle_actions))
            print("Simulated damages: " + ", ".join(str(value) for value in battle_damages))
        else:
            debug_payload = None
            if int(mission_id or 0) == 1 and (
                SHINOBI_TEST_PATTERN in {"captured", "weapon"} or action_pool
            ):
                debug_payload = _build_training_dummy_payload(action_pool)

            if debug_payload:
                turns = debug_payload["turns"]
                battle_actions = debug_payload["battle_actions"]
                battle_damages = debug_payload["battle_damages"]
                friend_analysis = _build_friend_analysis(friend_profiles, turns)
                enemy_analysis = debug_payload["enemy_analysis"]
                print(f"Using fixed debug payload for mission 1 ({SHINOBI_TEST_PATTERN})")
                print("Debug actions: " + ", ".join(battle_actions))
                print("Debug damages: " + ", ".join(str(value) for value in battle_damages))
            else:
                turns = _estimate_turns(enemy_ids) if enemy_ids else random.randint(5, 10)
                if turns is None or check_stop_event():
                    return

                battle_actions = [random.choice(action_pool) for _ in range(max(1, turns))]
                battle_damages = [random.randint(15, 35) for _ in range(len(battle_actions))]
                friend_analysis = _build_friend_analysis(friend_profiles, turns)
                enemy_analysis = _build_enemy_analysis(enemy_profiles, turns)

        if not friend_analysis and default_friend_analysis:
            friend_analysis = default_friend_analysis

        battle_finish_delay = _cfg_int(
            "battle_finish_delay_seconds",
            SHINOBI_MISSION_FINISH_DELAY_SECONDS,
        )
        print(f"Waiting {battle_finish_delay} seconds before completing mission...")
        if not wait_with_stop_check(battle_finish_delay):
            return

        analysis = _build_analysis(
            char_id,
            turns,
            battle_actions,
            battle_damages,
            enemy_analysis,
            friend_analysis=friend_analysis,
        )

        result = _complete_mission(
            mission_id,
            mission_key,
            analysis,
        )

        if not isinstance(result, dict):
            print(f"Mission completion failed: non-dict response -> {_response_message(result)}")
            return

        if not _is_success_response(result):
            print(f"Mission completion failed: {_response_message(result)}")

            fallback_key = missions_response.get("_panel_key")
            if fallback_key and fallback_key != mission_key:
                print("Retrying mission completion with fallback panel key...")
                result = _complete_mission(
                    mission_id,
                    fallback_key,
                    analysis,
                )

                if not (isinstance(result, dict) and _is_success_response(result)):
                    print(f"Fallback also failed: {_response_message(result)}")
                    return
                else:
                    print("Fallback mission completion succeeded")
            else:
                return

        new_data = _extract_new_data(result)
        _apply_new_data(new_data)

        updated_level = new_data.get("level", char_snapshot.get("character_level", 0))
        updated_gold = new_data.get("gold", char_snapshot.get("character_gold", 0))
        updated_xp = new_data.get("xp", char_snapshot.get("character_xp", 0))

        if isinstance(updated_xp, (list, tuple)):
            updated_xp = updated_xp[0] if updated_xp else 0

        reward = result.get("reward") if isinstance(result, dict) else {}
        if isinstance(reward, dict):
            reward_xp = reward.get("xp")
            reward_gold = reward.get("gold")
            if reward_xp is not None or reward_gold is not None:
                print(f"Reward received -> XP: {reward_xp} | Gold: {reward_gold}")

        print(
            f"Mission complete: {mission_name} | "
            f"Lv {updated_level} | EXP {updated_xp} | Gold {updated_gold}"
        )

        _log_reward_pack(result)

        between_delay = _between_delay_seconds()
        print(f"Waiting {between_delay} second before next mission...")
        if not wait_with_stop_check(between_delay):
            return


def shinobi_leveling_xtra():
    char_snapshot, _access_token, user_key, char_id = _ensure_character_context()
    _bootstrap_action_state()

    print("Starting Shinobi Warfare leveling XTRA...")
    print(f"Character ID: {char_id} | User key: {user_key}")

    while not check_stop_event():
        char_level = _safe_int(char_snapshot.get("character_level") or char_snapshot.get("level"))

        recruits_response = _load_recruits()
        if not isinstance(recruits_response, dict) or recruits_response.get("error", 0):
            print(f"Failed to load recruits: {_response_message(recruits_response)}")
            return

        missions_response = _load_missions()
        if not isinstance(missions_response, dict) or missions_response.get("error", 0):
            print(f"Failed to load missions: {_response_message(missions_response)}")
            return

        missions = missions_response.get("missions")
        if not isinstance(missions, list):
            print("Mission list data is incomplete")
            return

        mission = _xtra_select_mission(missions, char_level)
        if not mission:
            print("No playable XTRA missions are available for the current level")
            return

        mission_key = _resolve_mission_key(mission, missions_response)
        if not isinstance(mission_key, str) or len(mission_key) != 32:
            print(f"Invalid mission key before completion: {mission_key!r}")
            return

        mission_id = mission.get("id")
        mission_name = mission.get("name", f"Mission {mission_id}")
        enemy_ids = _flatten_enemy_ids(mission.get("enemies"))

        print(
            f"Running XTRA mission {mission_id} - {mission_name} "
            f"(Lv req: {_mission_level_requirement(mission)}, XP: {_safe_int(mission.get('xp'))}, Gold: {_safe_int(mission.get('gold'))})"
        )

        if enemy_ids:
            print("Mission enemies: " + ", ".join(str(enemy_id) for enemy_id in enemy_ids))

        if enemy_ids and not _xtra_validate_enemy_loads(enemy_ids):
            print("Mission completion aborted because one or more enemy loads failed")
            return

        before_level = _safe_int(char_snapshot.get("character_level") or char_snapshot.get("level"))
        before_gold = _safe_int(char_snapshot.get("character_gold") or char_snapshot.get("gold"))
        before_xp = char_snapshot.get("character_xp", char_snapshot.get("xp", 0))
        before_max_xp = char_snapshot.get("character_max_xp", char_snapshot.get("max_xp", 0))
        if isinstance(before_xp, (list, tuple)):
            before_xp = before_xp[0] if before_xp else 0
        before_xp = _safe_int(before_xp)
        before_max_xp = _safe_int(before_max_xp)

        turns, battle_actions, battle_damages, analysis = _xtra_build_battle()

        result = _complete_mission(
            mission_id,
            mission_key,
            {
                "player": {
                    "turns": turns,
                    "actions": battle_actions,
                    "damages": battle_damages,
                },
                "friends": [],
                "enemies": [],
            },
        )

        if not isinstance(result, dict):
            print(f"Mission completion failed: non-dict response -> {_response_message(result)}")
            return

        if not _is_success_response(result):
            print(f"Mission completion failed: {_response_message(result)}")
            return

        new_data = _extract_new_data(result)
        progress = _xtra_calc_progress(before_level, before_xp, before_max_xp, before_gold, new_data)
        _apply_new_data(new_data)

        print(
            f"Mission complete: {mission_name} | +{progress['gained_xp']} XP | +{progress['gained_gold']} Gold"
        )

        if progress["same_level"] and progress["gained_xp"] == 0:
            exams_response = _load_tensai_exams()
            if not isinstance(exams_response, dict) or exams_response.get("error", 0):
                print(f"Failed to load Tensai exams: {_response_message(exams_response)}")
                return

            exam = _xtra_select_exam(exams_response.get("missions"))
            if exam:
                exam_key = _resolve_mission_key(exam, exams_response)
                if not isinstance(exam_key, str) or len(exam_key) != 32:
                    print(f"Invalid exam key before completion: {exam_key!r}")
                    return

                exam_id = exam.get("id")
                exam_name = exam.get("name", f"Exam {exam_id}")
                exam_enemy_ids = _flatten_enemy_ids(exam.get("enemies"))
                if exam_enemy_ids and not _xtra_validate_enemy_loads(exam_enemy_ids):
                    print("Exam completion aborted because one or more enemy loads failed")
                    return

                exam_turns, exam_actions, exam_damages, _exam_analysis = _xtra_build_battle()
                exam_result = _complete_mission(
                    exam_id,
                    exam_key,
                    {
                        "player": {
                            "turns": exam_turns,
                            "actions": exam_actions,
                            "damages": exam_damages,
                        },
                        "friends": [],
                        "enemies": [],
                    },
                )

                if not (isinstance(exam_result, dict) and _is_success_response(exam_result)):
                    print(f"Tensai exam completion failed: {_response_message(exam_result)}")
                    return

                exam_new_data = _extract_new_data(exam_result)
                _apply_new_data(exam_new_data)
                print(f"Exam complete: {exam_name}")

        if not wait_with_stop_check(_between_delay_seconds()):
            return


def shinobi_daily_missions_xtra():
    char_snapshot, _access_token, user_key, char_id = _ensure_character_context()
    _bootstrap_action_state()
    print("Starting Shinobi Warfare daily missions XTRA...")
    print(f"Character ID: {char_id} | User key: {user_key}")

    while not check_stop_event():
        char_level = _safe_int(char_snapshot.get("character_level") or char_snapshot.get("level"))
        missions_response = _load_daily_missions()
        if not isinstance(missions_response, dict) or missions_response.get("error", 0):
            print(f"Failed to load daily missions: {_response_message(missions_response)}")
            return

        mission = _xtra_select_daily_mission(missions_response.get("missions"), char_level)
        if not mission:
            print("No more XTRA daily missions are available")
            return

        mission_key = _resolve_mission_key(mission, missions_response)
        enemy_ids = _flatten_enemy_ids(mission.get("enemies"))
        if enemy_ids and not _xtra_validate_enemy_loads(enemy_ids):
            print("Daily mission aborted because one or more enemy loads failed")
            return

        result = _xtra_complete_standard(
            "mission/process_complete_mission.php",
            mission.get("id"),
            mission_key,
            user_key,
        )
        if not (isinstance(result, dict) and _is_success_response(result)):
            print(f"Daily mission failed: {_response_message(result)}")
            return

        _new_data, progress = _xtra_apply_result(char_snapshot, result)
        print(
            f"Daily mission complete: {mission.get('name', mission.get('id'))} | "
            f"+{progress['gained_xp']} XP | +{progress['gained_gold']} Gold"
        )

        if not wait_with_stop_check(_between_delay_seconds()):
            return


def shinobi_hunting_house_xtra():
    char_snapshot, _access_token, user_key, char_id = _ensure_character_context()
    _bootstrap_action_state()
    print("Starting Shinobi Warfare hunting house XTRA...")
    print(f"Character ID: {char_id} | User key: {user_key}")

    while not check_stop_event():
        char_level = _safe_int(char_snapshot.get("character_level") or char_snapshot.get("level"))
        bosses_response = _load_bosses()
        if not isinstance(bosses_response, dict) or bosses_response.get("error", 0):
            print(f"Failed to load bosses: {_response_message(bosses_response)}")
            return

        boss = _xtra_select_boss(bosses_response, char_level)
        if not boss:
            print("No XTRA hunting house bosses are available")
            return

        boss_key = _resolve_mission_key(boss, bosses_response)
        enemy_ids = _flatten_enemy_ids(boss.get("enemies"))
        if enemy_ids and not _xtra_validate_enemy_loads(enemy_ids):
            print("Boss mission aborted because one or more enemy loads failed")
            return

        result = _xtra_complete_standard(
            "mission/process_complete_boss.php",
            boss.get("id"),
            boss_key,
            user_key,
        )
        if not (isinstance(result, dict) and _is_success_response(result)):
            print(f"Boss mission failed: {_response_message(result)}")
            return

        _new_data, progress = _xtra_apply_result(char_snapshot, result)
        print(
            f"Boss mission complete: {boss.get('name', boss.get('id'))} | "
            f"+{progress['gained_xp']} XP | +{progress['gained_gold']} Gold"
        )

        if not wait_with_stop_check(_between_delay_seconds()):
            return


def shinobi_arena_xtra():
    char_snapshot, _access_token, user_key, char_id = _ensure_character_context()
    _bootstrap_action_state()
    print("Starting Shinobi Warfare arena XTRA...")
    print(f"Character ID: {char_id} | User key: {user_key}")

    while not check_stop_event():
        arena_response = _load_arena()
        if not isinstance(arena_response, dict):
            print(f"Failed to load arena: {_response_message(arena_response)}")
            return

        arena_data = arena_response.get("arena_data") or {}
        power = _safe_int(arena_data.get("power"))
        trophies_before = _safe_int(arena_data.get("trophies"))

        if power <= 0:
            restore_response = _restore_arena_power()
            if not isinstance(restore_response, dict) or not restore_response.get("success"):
                print(f"Failed to restore arena power: {_response_message(restore_response)}")
                return

            arena_response = _load_arena()
            arena_data = arena_response.get("arena_data") or {}
            power = _safe_int(arena_data.get("power"))
            if power <= 0:
                print("Arena power is still empty after restore")
                return

        enemies_response = _load_arena_enemies()
        playground = enemies_response.get("playground") if isinstance(enemies_response, dict) else None
        arena_key = enemies_response.get("_panel_key") if isinstance(enemies_response, dict) else None
        if not playground or not arena_key:
            print(f"Failed to load arena enemies: {_response_message(enemies_response)}")
            return

        turns, battle_actions, battle_damages, _analysis = _xtra_build_battle()
        result = _xtra_complete_route(
            "arena/process_complete_match.php",
            {
                **_auth_payload(),
                "turns": turns,
                "actions": battle_actions,
                "damages": battle_damages,
                "analysis": _xtra_player_analysis(turns, battle_actions, battle_damages),
                "friends": 0,
                "victory": True,
                "playground": playground,
                "key": arena_key,
            },
        )
        if not (isinstance(result, dict) and _is_success_response(result)):
            print(f"Arena battle failed: {_response_message(result)}")
            return

        _new_data, progress = _xtra_apply_result(char_snapshot, result)
        arena_after = _load_arena()
        trophies_after = (
            _safe_int((arena_after.get("arena_data") or {}).get("trophies"))
            if isinstance(arena_after, dict)
            else trophies_before
        )
        trophies_gain = max(0, trophies_after - trophies_before)
        print(
            f"Arena battle complete: +{trophies_gain} Trophies | "
            f"+{progress['gained_xp']} XP | +{progress['gained_gold']} Gold"
        )

        if not wait_with_stop_check(_between_delay_seconds()):
            return


def shinobi_event_xtra():
    char_snapshot, _access_token, user_key, char_id = _ensure_character_context()
    _bootstrap_action_state()
    print("Starting Shinobi Warfare event XTRA...")
    print(f"Character ID: {char_id} | User key: {user_key}")

    events_response = _load_events()
    if not isinstance(events_response, dict) or events_response.get("error", 0):
        print(f"Failed to load events: {_response_message(events_response)}")
        return

    event = _xtra_select_event(events_response)
    if not event:
        print("No XTRA event with playable missions is available")
        return

    print(f"Selected event: {event.get('name', event.get('id'))}")

    while not check_stop_event():
        event_data_response = _load_event_data()
        if not isinstance(event_data_response, dict) or event_data_response.get("error", 0):
            print(f"Failed to load event data: {_response_message(event_data_response)}")
            return

        event_player_data = event_data_response.get("data") or {}
        current_energy = _safe_int(event_player_data.get("energy"))
        mission = _xtra_select_event_mission(event)
        if not mission:
            print("No playable missions remain in the selected event")
            return

        mission_energy = _safe_int(mission.get("energy"))
        if current_energy < mission_energy:
            restore_response = _restore_event_energy()
            if not isinstance(restore_response, dict) or not restore_response.get("success"):
                print(f"Failed to restore event energy: {_response_message(restore_response)}")
                return
            current_energy = _safe_int(restore_response.get("energy"), current_energy)
            if current_energy < mission_energy:
                print("Event energy is still too low after restore")
                return

        start_response = _start_event_mission(event.get("id"), mission.get("id"))
        if not isinstance(start_response, dict) or start_response.get("status") != 1:
            print(f"Failed to start event mission: {_response_message(start_response)}")
            return

        event_key = start_response.get("_panel_key")
        if not event_key:
            key = start_response.get("key")
            if isinstance(key, dict) and key.get("time") is not None and key.get("key") is not None:
                event_key = _build_mission_key(key["time"], key["key"])
        if not event_key:
            print(f"Failed to resolve event key: {_response_message(start_response)}")
            return

        turns, battle_actions, battle_damages, _analysis = _xtra_build_battle()
        result = _xtra_complete_route(
            "events/process_complete_mission.php",
            {
                **_auth_payload(),
                "turns": turns,
                "actions": battle_actions,
                "damages": battle_damages,
                "analysis": _xtra_player_analysis(turns, battle_actions, battle_damages),
                "friends": 0,
                "eventId": int(event.get("id")),
                "missionId": int(mission.get("id")),
                "victory": True,
                "key": event_key,
            },
        )
        if not (isinstance(result, dict) and _is_success_response(result)):
            print(f"Event mission failed: {_response_message(result)}")
            return

        _new_data, progress = _xtra_apply_result(char_snapshot, result)
        print(
            f"Event mission complete: {mission.get('name', mission.get('id'))} | "
            f"+{progress['gained_xp']} XP | +{progress['gained_gold']} Gold"
        )

        if not wait_with_stop_check(_between_delay_seconds()):
            return
