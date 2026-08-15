from .. import config
from .runtime import (
    check_stop_event,
    enemy_name,
    finish_eudemon,
    get_char_id,
    get_level,
    get_session_key,
    rift_delay,
    rift_random_wait,
    response_message,
    send_rift_request,
    wait_with_stop,
)


RIFT_EUDEMON_BOSSES = [
    {"num": 0, "enemy_ids": ["ene_460"], "name": "Kamaitachi", "level": 10},
    {"num": 1, "enemy_ids": ["ene_461"], "name": "Hell Horse", "level": 20},
    {"num": 2, "enemy_ids": ["ene_462"], "name": "Kabutomushi Musha", "level": 25},
    {"num": 3, "enemy_ids": ["ene_463", "ene_464"], "name": "Kinkaku & Ginkaku", "level": 30},
    {"num": 4, "enemy_ids": ["ene_465"], "name": "Thunder Eagle", "level": 40},
    {"num": 5, "enemy_ids": ["ene_466"], "name": "Mammoth King", "level": 50},
    {"num": 6, "enemy_ids": ["ene_467"], "name": "Ocean Queen", "level": 55},
    {"num": 7, "enemy_ids": ["ene_468"], "name": "Ghost Soldier", "level": 60},
    {"num": 8, "enemy_ids": ["ene_469"], "name": "Battle Angel", "level": 70},
    {"num": 9, "enemy_ids": ["ene_470"], "name": "Infernal Chimera", "level": 80},
    {"num": 10, "enemy_ids": ["ene_472", "ene_473", "ene_473"], "name": "Shadow Ninja Master & Shadow Wolfs", "level": 90},
    {"num": 11, "enemy_ids": ["ene_474", "ene_475", "ene_476"], "name": "Demon General & Demon Ninjas", "level": 100},
]


def _format_extra_rewards(rewards) -> str:
    if not isinstance(rewards, list) or len(rewards) <= 2:
        return "-"
    extras = [str(item) for item in rewards[2:] if str(item).strip()]
    return ", ".join(extras) if extras else "-"


def _parse_tries_payload(data_field):
    if not isinstance(data_field, str):
        return []
    parts = [item.strip() for item in data_field.split(",")]
    tries = []
    for item in parts:
        try:
            tries.append(int(item))
        except Exception:
            tries.append(0)
    return tries


def fight_eudemon_boss():
    if not isinstance(config.char_data, dict):
        raise ValueError("Select a Ninja Rift character first")

    char_id = get_char_id()
    session_key = get_session_key()
    level = get_level()

    print("Loading Ninja Rift Eudemon Garden data...")
    data = send_rift_request("EudemonGarden.getData", [session_key, char_id])
    if not isinstance(data, dict) or data.get("status") != 1:
        raise ValueError(f"Failed to load Ninja Rift Eudemon Garden: {response_message(data)}")

    tries = _parse_tries_payload(data.get("data"))
    total_fights = 0
    completed = True

    for boss in RIFT_EUDEMON_BOSSES:
        if check_stop_event():
            completed = False
            break
        if level < boss["level"]:
            continue
        available = tries[boss["num"]] if boss["num"] < len(tries) else 0
        if available <= 0:
            continue
        boss_name = " & ".join(enemy_name(enemy_id, boss["name"]) for enemy_id in boss["enemy_ids"])

        for idx in range(available):
            if check_stop_event():
                completed = False
                break

            print(f"Fighting Rift Eudemon boss: {boss_name} ({idx + 1}/{available})")
            start_result = send_rift_request(
                "EudemonGarden.startHunting",
                [char_id, boss["num"], session_key],
            )
            battle_code = start_result if isinstance(start_result, str) and len(start_result) == 10 else None
            if not battle_code:
                print(f"Could not start Eudemon battle: {response_message(start_result)}")
                completed = False
                break

            battle_wait = max(
                5,
                rift_random_wait(
                    "rift_eudemon_battle_wait_base_seconds",
                    "rift_eudemon_battle_wait_random_seconds",
                    20,
                    5,
                ),
            )
            print(f"Waiting {battle_wait} seconds before finishing {boss_name}...")
            if not wait_with_stop(battle_wait):
                completed = False
                break

            finish_result = finish_eudemon(boss["num"], battle_code)
            if isinstance(finish_result, dict) and finish_result.get("status") == 1:
                rewards = finish_result.get("result", [])
                exp = rewards[0] if len(rewards) > 0 else 0
                gold = rewards[1] if len(rewards) > 1 else 0
                extra_rewards = _format_extra_rewards(rewards)
                print(f"Defeated {boss_name} | EXP: {exp} | Gold: {gold} | Rewards: {extra_rewards}")
                total_fights += 1
            else:
                print(f"Eudemon finish failed: {response_message(finish_result)}")
                completed = False
                break

            between_delay = rift_delay("rift_eudemon_between_battles_delay_seconds", 5)
            if idx < available - 1 and not wait_with_stop(between_delay):
                completed = False
                break

    if hasattr(config, "stop_event"):
        config.stop_event.clear()
    print(f"Ninja Rift Eudemon Garden ended after {total_fights} fights")
    return completed
