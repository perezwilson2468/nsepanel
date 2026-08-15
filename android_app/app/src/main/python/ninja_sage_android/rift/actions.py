from dataclasses import dataclass
from typing import Callable

from .daily import rift_daily_missions
from .eudemon import fight_eudemon_boss
from .exam import rift_exam
from .events import rift_easter_event
from .hunting_house import fight_hunting_house
from .leveling import rift_leveling
from .runtime import check_stop_event, rift_delay, wait_with_stop


@dataclass
class ActionSpec:
    func: Callable
    name: str


def rift_finisher_action():
    print("Starting Ninja Rift Finisher Action...")
    steps = [
        ("Hunting House", fight_hunting_house),
        ("Eudemon Garden", fight_eudemon_boss),
        ("Daily Missions", rift_daily_missions),
        ("Leveling", rift_leveling),
    ]

    for index, (label, action_func) in enumerate(steps, start=1):
        if check_stop_event():
            print("Rift Finisher Action stopped before the next step.")
            return False

        print(f"[Finisher {index}/{len(steps)}] Running {label}...")
        success = bool(action_func())
        if not success:
            print(f"Rift Finisher Action stopped during {label}.")
            return False

        if index < len(steps):
            step_delay = max(1, rift_delay("rift_loop_delay_seconds", 1))
            print(f"[Finisher] Waiting {step_delay} seconds before the next step...")
            if not wait_with_stop(step_delay):
                print("Rift Finisher Action stopped during step cooldown.")
                return False

    print("Rift Finisher Action finished.")
    return True


_BASE_ACTIONS = {
    "finisher_action": ActionSpec(rift_finisher_action, "Finisher Action"),
    "leveling": ActionSpec(rift_leveling, "Start Leveling"),
    "daily_missions": ActionSpec(rift_daily_missions, "Daily Missions"),
    "eudemon_garden": ActionSpec(fight_eudemon_boss, "Eudemon Garden"),
    "hunting_house": ActionSpec(fight_hunting_house, "Hunting House"),
    "easter_event": ActionSpec(rift_easter_event, "Easter Event 2026"),
    "exam": ActionSpec(rift_exam, "Auto Exam"),
}


def resolve_rift_action(
    action: str,
    params,
    refresh_factory: Callable[[], Callable],
    current_base_game: dict,
) -> ActionSpec:
    if action == "refresh":
        return ActionSpec(refresh_factory(), "Refresh Character Info")

    if action in _BASE_ACTIONS:
        return _BASE_ACTIONS[action]

    raise ValueError(f"Unknown action: {action}")
