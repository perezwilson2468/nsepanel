import uuid

from ..core import config
from . import amf_req
from .runtime import (
    check_stop_event,
    enemy_name,
    get_char_id,
    get_session_key,
    mission_damage,
    response_message,
    rift_delay,
    rift_random_wait,
    send_rift_request,
    wait_with_stop,
)
from .utils import CUCSG


RIFT_EVENT_CONFIG = {
    "hanami_event": {
        "label": "Hanami Event 2026",
        "service": "HanamiEvent2026",
        "restore_event": "hanami",
        "settings_prefix": "rift_hanami_event",
        "boss_count": 6,
        "energy_cost": 10,
        "mode": "boss_select",
    },
    "easter_event": {
        "label": "Easter Event 2026",
        "service": "EasterEvent2026",
        "restore_event": "easter",
        "settings_prefix": "rift_easter_event",
        "energy_cost": 10,
        "mode": "map",
    },
}

HANAMI_BOSS_NAMES = {
    0: "Origami Kite",
    1: "Origami Deer",
    2: "Origami Bear",
    3: "Origami Dragon",
    4: "Origami Spider",
    5: "Origami Fox",
}

RIFT_EASTER_TREASURE_MARKERS = (
    "box",
    "treasure",
    "chest",
    "gift",
    "reward",
    "coin",
    "gold",
    "token",
    "material",
    "item",
)


def _buy_event_energy(event_cfg: dict) -> bool:
    label = event_cfg["label"]
    restore_event = event_cfg.get("restore_event")
    if not restore_event:
        print(f"No confirmed token refill API is configured for {label}.")
        return False

    random_code = uuid.uuid4().hex[:25]
    params = [get_char_id(), get_session_key(), "event", "tokens_20", random_code, restore_event, "normal"]
    print(f"{label}: buying full event energy refill for 20 tokens...")
    result = send_rift_request("EnergySystem.executeService", ["restoreEnergy", params])
    if isinstance(result, dict) and str(result.get("status")) == "1":
        print(f"{label}: energy refill successful.")
        return True

    print(f"{label}: energy refill failed: {response_message(result)}")
    return False


def _handle_empty_event_energy(event_cfg: dict) -> bool:
    label = event_cfg["label"]
    settings = config.get_rift_settings()
    prefix = event_cfg.get("settings_prefix") or "rift_event"
    mode = str(settings.get(f"{prefix}_empty_resource_mode") or settings.get("rift_event_empty_resource_mode", "wait")).strip().lower()
    if mode not in {"buy", "wait", "stop"}:
        mode = "wait"
    wait_minutes = max(0, int(settings.get(f"{prefix}_wait_minutes") or settings.get("rift_event_wait_minutes", 30) or 30))

    if mode == "stop":
        print(f"{label} stopped: no event energy available.")
        return False

    if mode == "buy":
        return _buy_event_energy(event_cfg)
    else:
        print(f"{label} waiting {wait_minutes} minute(s) for event energy.")

    if wait_minutes <= 0:
        return False
    return wait_with_stop(wait_minutes * 60)


def _format_reward_list(rewards) -> str:
    if not isinstance(rewards, list) or not rewards:
        return "-"
    return ", ".join(str(item) for item in rewards)


def _log_event_extra_data(label: str, extra_data, context: str):
    if not isinstance(extra_data, dict):
        return
    rewards = extra_data.get("rewards")
    message = extra_data.get("message")
    if isinstance(rewards, list) and rewards:
        print(f"{label} {context} rewards: {_format_reward_list(rewards)}")
    if message:
        print(f"{label} {context} message: {message}")


def _event_request(service: str, function_name: str, params: list):
    return send_rift_request(f"{service}.executeService", [function_name, params])


def _get_event_data(service: str):
    return _event_request(service, "getData", [get_char_id(), get_session_key()])


def _claim_free_gift(service: str, payload: dict):
    menu_data = payload.get("menuData")
    if not isinstance(menu_data, dict):
        return payload
    if int(menu_data.get("canClaimFreeGift") or 0) != 1:
        return payload

    print(f"Claiming free gift for {service}...")
    result = _event_request(service, "claimFreeGift", [get_char_id(), get_session_key()])
    if isinstance(result, dict) and result.get("status") == 1:
        return result
    print(f"Free gift claim failed: {response_message(result)}")
    return payload


def _claim_progress_rewards(service: str, payload: dict):
    battle_data = payload.get("battleData")
    if not isinstance(battle_data, dict):
        return payload

    progress_list = battle_data.get("battleProgress")
    progress_data = battle_data.get("battleProgressData")
    kills_required = battle_data.get("killsRequired")
    if not isinstance(progress_list, (list, dict)) or not isinstance(progress_data, (list, dict)) or not isinstance(kills_required, list):
        return payload

    latest = payload
    progress_count = len(progress_list) if isinstance(progress_list, list) else len(progress_list.keys())
    for progress_id in range(progress_count):
        if check_stop_event():
            return latest
        try:
            progress_entry = progress_list[progress_id] if isinstance(progress_list, list) else progress_list[str(progress_id)]
            progress_claims = progress_data[progress_id] if isinstance(progress_data, list) else progress_data[str(progress_id)]
            total_kills = int((progress_entry or {}).get("total_kills") or 0)
        except Exception:
            continue

        if not isinstance(progress_claims, (list, dict)):
            continue

        for reward_index, required_kills in enumerate(kills_required):
            try:
                claim_entry = progress_claims[reward_index] if isinstance(progress_claims, list) else progress_claims[str(reward_index)]
                claimed = int((claim_entry or {}).get("claimed") or 0)
                required_value = int(required_kills or 0)
            except Exception:
                continue
            if claimed != 0 or total_kills < required_value:
                continue

            print(f"Claiming progress reward {progress_id}:{reward_index} for {service}...")
            result = _event_request(
                service,
                "claimBattleProgress",
                [get_char_id(), get_session_key(), progress_id, reward_index],
            )
            if isinstance(result, dict) and result.get("status") == 1:
                latest = result
            else:
                print(f"Progress reward claim failed: {response_message(result)}")
    return latest


def _resolve_enemy_ids(start_result: dict) -> list[str]:
    raw_ids = start_result.get("enemy_id") or []
    if isinstance(raw_ids, list):
        return [str(item) for item in raw_ids]
    if isinstance(raw_ids, str):
        return [part.strip() for part in raw_ids.split(",") if part.strip()]
    return []


def _finish_event_battle(service: str, battle_code: str, damage: int):
    finish_hash = CUCSG.hash(f"{battle_code}{damage}")
    return _event_request(
        service,
        "endBattle",
        [get_char_id(), get_session_key(), battle_code, damage, finish_hash, -1, False],
    )


def _event_battle_wait() -> int:
    return max(
        5,
        rift_random_wait(
            "rift_event_battle_wait_base_seconds",
            "rift_event_battle_wait_random_seconds",
            20,
            20,
        ),
    )


def _event_loop_delay() -> bool:
    loop_delay = max(1, rift_delay("rift_loop_delay_seconds", 1))
    return wait_with_stop(loop_delay)


def _start_and_finish_event_battle(service: str, label: str, start_result: dict, enemy_label: str):
    battle_code = start_result.get("battle_code")
    if not battle_code:
        print(f"{label} did not return battle_code.")
        return False

    enemy_ids = _resolve_enemy_ids(start_result)
    enemy_library = amf_req.get_enemy_library()
    enemy_stats = [dict(enemy_library.get(enemy_id) or {}) for enemy_id in enemy_ids]
    damage = mission_damage(enemy_ids, enemy_stats)

    battle_wait = _event_battle_wait()
    print(f"Fighting {label}: {enemy_label}. Waiting {battle_wait} seconds before finish...")
    if not wait_with_stop(battle_wait):
        return False

    finish_result = _finish_event_battle(service, battle_code, damage)
    if not isinstance(finish_result, dict) or finish_result.get("status") != 1:
        print(f"{label} finish failed: {response_message(finish_result)}")
        return None

    rewards = []
    extra_data = finish_result.get("extra_data")
    if isinstance(extra_data, dict) and isinstance(extra_data.get("rewards"), list):
        rewards = extra_data.get("rewards")
    print(f"{label} finished: {enemy_label} | Rewards: {_format_reward_list(rewards)}")
    return finish_result


def _run_boss_select_event(event_cfg: dict, selected_boss_index: int | None = None, selected_boss_name: str | None = None):
    service = event_cfg["service"]
    label = event_cfg["label"]

    print(f"Loading {label} data...")
    data = _get_event_data(service)
    if not isinstance(data, dict) or data.get("status") != 1:
        raise ValueError(f"Failed to load {label}: {response_message(data)}")

    total_battles = 0
    while True:
        if check_stop_event():
            break

        data = _claim_free_gift(service, data)
        data = _claim_progress_rewards(service, data)

        battle_data = data.get("battleData")
        if not isinstance(battle_data, dict):
            print(f"{label} battle data is not available in the current payload.")
            break

        current_energy = int(battle_data.get("energy") or 0)
        max_energy = int(battle_data.get("max_energy") or 0)
        print(f"{label} energy: {current_energy}/{max_energy}")
        energy_cost = int(event_cfg.get("energy_cost") or 10)
        if current_energy < energy_cost:
            print(f"{label} stopped: energy {current_energy} is below {energy_cost}.")
            if not _handle_empty_event_energy(event_cfg):
                break
            refreshed_data = _get_event_data(service)
            if isinstance(refreshed_data, dict) and refreshed_data.get("status") == 1:
                data = refreshed_data
                continue
            print(f"Failed to refresh {label} after waiting: {response_message(refreshed_data)}")
            break

        progress = battle_data.get("battleProgress")
        if selected_boss_index is not None:
            boss_indices = [selected_boss_index]
        elif isinstance(progress, list) and progress:
            boss_indices = list(range(len(progress)))
        else:
            boss_indices = list(range(int(event_cfg.get("boss_count") or 1)))
        if selected_boss_index is None:
            boss_indices.sort(reverse=True)

        battle_started = False
        for boss_index in boss_indices:
            if check_stop_event():
                break

            print(f"Starting {label} boss {boss_index}...")
            start_result = _event_request(service, "startBattle", [get_char_id(), get_session_key(), boss_index])
            if not isinstance(start_result, dict) or start_result.get("status") != 1:
                print(f"Could not start {label} boss {boss_index}: {response_message(start_result)}")
                continue

            enemy_ids = _resolve_enemy_ids(start_result)
            default_name = selected_boss_name or HANAMI_BOSS_NAMES.get(boss_index) or f"Boss {boss_index}"
            enemy_label = " & ".join(enemy_name(enemy_id, enemy_id) for enemy_id in enemy_ids) if enemy_ids else default_name
            finish_result = _start_and_finish_event_battle(service, label, start_result, enemy_label)
            if not finish_result:
                return
            total_battles += 1
            refreshed_data = _get_event_data(service)
            if isinstance(refreshed_data, dict) and refreshed_data.get("status") == 1:
                data = refreshed_data
            else:
                print(f"Failed to refresh {label} data after battle: {response_message(refreshed_data)}")
                data = finish_result if isinstance(finish_result, dict) else data
            battle_started = True
            break

        if not battle_started:
            print(f"No {label} boss could be started right now.")
            break

        if not _event_loop_delay():
            break

    if hasattr(config, "stop_event"):
        config.stop_event.clear()
    print(f"{label} ended after {total_battles} battles.")


def _claim_extra_battle_rewards(service: str, payload: dict):
    latest = _claim_progress_rewards(service, payload)
    latest = _claim_free_gift(service, latest)
    return latest


def _find_current_position(map_data: list) -> tuple[int, int] | None:
    for x, row in enumerate(map_data):
        if not isinstance(row, list):
            continue
        for y, value in enumerate(row):
            if value == "pos":
                return x, y
    return None


def _find_tiles(map_data: list, tile_type: str) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    for x, row in enumerate(map_data):
        if not isinstance(row, list):
            continue
        for y, value in enumerate(row):
            if value == tile_type:
                found.append((x, y))
    return found


def _easter_tile_kind(tile_value) -> str:
    tile_text = str(tile_value or "").strip().lower()
    if tile_text == "pos":
        return "player"
    if tile_text == "rockboss":
        return "final_boss"
    if tile_text in {"", "0", "1", "empty", "road", "path", "floor", "done", "clear", "cleared", "opened", "open"}:
        return "empty"
    if any(marker in tile_text for marker in RIFT_EASTER_TREASURE_MARKERS):
        return "treasure"
    return "other"


def _find_easter_treasure_tiles(map_data: list) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    for x, row in enumerate(map_data):
        if not isinstance(row, list):
            continue
        for y, value in enumerate(row):
            if _easter_tile_kind(value) == "treasure":
                found.append((x, y))
    return found


def _distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _print_easter_map(map_data: list):
    print("Easter map:")
    legend = "P=player  B=final boss  T=treasure/box  .=empty  ?=other"
    print(legend)
    for x, row in enumerate(map_data):
        if not isinstance(row, list):
            continue
        symbols = []
        raw_tiles = []
        for value in row:
            kind = _easter_tile_kind(value)
            if kind == "player":
                symbols.append("P")
            elif kind == "final_boss":
                symbols.append("B")
            elif kind == "treasure":
                symbols.append("T")
            elif kind == "empty":
                symbols.append(".")
            else:
                symbols.append("?")
            raw_tiles.append(str(value))
        print(f"  row {x}: {' '.join(symbols)}    {raw_tiles}")


def _next_easter_step(current_pos: tuple[int, int], target_pos: tuple[int, int]) -> tuple[int, int]:
    curr_x, curr_y = current_pos
    target_x, target_y = target_pos
    if curr_x < target_x:
        return curr_x + 1, curr_y
    if curr_x > target_x:
        return curr_x - 1, curr_y
    if curr_y < target_y:
        return curr_x, curr_y + 1
    if curr_y > target_y:
        return curr_x, curr_y - 1
    return current_pos


def _run_easter_event(event_cfg: dict):
    service = event_cfg["service"]
    label = event_cfg["label"]
    energy_cost = int(event_cfg.get("energy_cost") or 10)

    print(f"Loading {label} data...")
    data = _get_event_data(service)
    if not isinstance(data, dict) or data.get("status") != 1:
        raise ValueError(f"Failed to load {label}: {response_message(data)}")

    total_battles = 0

    while True:
        if check_stop_event():
            break

        data = _claim_extra_battle_rewards(service, data)
        battle_data = data.get("battleData")
        map_data = data.get("mapData")
        if not isinstance(battle_data, dict) or not isinstance(map_data, list):
            print(f"{label} data is incomplete for battle/map flow.")
            break

        _print_easter_map(map_data)

        current_energy = int(battle_data.get("energy") or 0)
        max_energy = int(battle_data.get("max_energy") or 0)
        print(f"{label} energy: {current_energy}/{max_energy}")
        if current_energy < energy_cost:
            print(f"{label} stopped: energy {current_energy} is below {energy_cost}.")
            if not _handle_empty_event_energy(event_cfg):
                break
            refreshed_data = _get_event_data(service)
            if isinstance(refreshed_data, dict) and refreshed_data.get("status") == 1:
                data = refreshed_data
                continue
            print(f"Failed to refresh {label} after waiting: {response_message(refreshed_data)}")
            break

        extra_data = data.get("extra_data")
        _log_event_extra_data(label, extra_data, "map")
        if isinstance(extra_data, dict) and extra_data.get("boss"):
            boss_name = str(extra_data.get("boss"))
            print(f"Encountered {boss_name}. Starting battle...")
            start_result = _event_request(service, "startBattle", [get_char_id(), get_session_key()])
            if not isinstance(start_result, dict) or start_result.get("status") != 1:
                print(f"Could not start {label} battle: {response_message(start_result)}")
                break
            enemy_ids = _resolve_enemy_ids(start_result)
            enemy_label = " & ".join(enemy_name(enemy_id, enemy_id) for enemy_id in enemy_ids) if enemy_ids else boss_name
            if not _start_and_finish_event_battle(service, label, start_result, enemy_label):
                return
            total_battles += 1
            if not _event_loop_delay():
                break
            data = _get_event_data(service)
            if not isinstance(data, dict) or data.get("status") != 1:
                print(f"Failed to refresh {label}: {response_message(data)}")
                break
            continue

        current_pos = _find_current_position(map_data)
        treasure_tiles = _find_easter_treasure_tiles(map_data)
        boss_tiles = _find_tiles(map_data, "rockboss")
        if current_pos is None:
            print(f"{label} current position could not be found.")
            break

        if not boss_tiles:
            print(f"{label}: map cleared, moving to next map...")
            data = _event_request(service, "nextMap", [get_char_id(), get_session_key()])
            if not isinstance(data, dict) or data.get("status") != 1:
                print(f"{label} next map failed: {response_message(data)}")
                break
            if not _event_loop_delay():
                break
            continue

        if treasure_tiles:
            target_tile = min(
                treasure_tiles,
                key=lambda pos: (_distance(current_pos, pos), pos[0], pos[1]),
            )
            target_reason = "treasure"
        else:
            target_tile = min(
                boss_tiles,
                key=lambda pos: (_distance(current_pos, pos), pos[0], pos[1]),
            )
            target_reason = "final boss"
        next_step = _next_easter_step(current_pos, target_tile)
        if next_step == current_pos:
            print(f"{label}: already at target {target_reason} tile {target_tile}, refreshing data...")
            data = _get_event_data(service)
            if not isinstance(data, dict) or data.get("status") != 1:
                print(f"Failed to refresh {label}: {response_message(data)}")
            break
            continue

        step_x, step_y = next_step
        print(f"{label}: moving from {current_pos} to {(step_x, step_y)} toward {target_reason} at {target_tile}...")
        data = _event_request(service, "changePos", [get_char_id(), get_session_key(), step_x, step_y])
        if not isinstance(data, dict) or data.get("status") != 1:
            print(f"{label} move failed: {response_message(data)}")
            break
        if not _event_loop_delay():
            break

    if hasattr(config, "stop_event"):
        config.stop_event.clear()
    print(f"{label} ended after {total_battles} battles.")


def _run_event_battle(event_key: str):
    event_cfg = RIFT_EVENT_CONFIG[event_key]
    if event_cfg.get("mode") == "map":
        _run_easter_event(event_cfg)
        return
    _run_boss_select_event(event_cfg)


def rift_hanami_event(selected_enemy_id=None, selected_enemy_name: str | None = None):
    if not isinstance(config.char_data, dict):
        raise ValueError("Select a Ninja Rift character first")
    selected_boss_index = None
    if selected_enemy_id not in (None, ""):
        try:
            selected_boss_index = int(selected_enemy_id)
        except Exception:
            selected_boss_index = None
    _run_boss_select_event(RIFT_EVENT_CONFIG["hanami_event"], selected_boss_index, selected_enemy_name)


def rift_easter_event():
    if not isinstance(config.char_data, dict):
        raise ValueError("Select a Ninja Rift character first")
    _run_event_battle("easter_event")
