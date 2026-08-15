from dataclasses import dataclass
from typing import Callable, Optional

from .clan_war import clan_war_event
from .crew_battle import crew_battle_event
from .daily import daily
from .eudemon import fight_eudemon_boss
from .event import (
    fight_aniv_event,
    fight_aniv_special_mission,
    fight_cd_event,
    fight_easter_event,
    fight_worldcup_event,
    fight_phantom_event,
    fight_pumpkin_event,
    fight_sakura_event,
    fight_snow_event,
    fight_thanks_event,
    fight_yinyang_event,
)
from .event_finisher import event_finisher
from .leveling import start_leveling
from .minigames import fight_minigame_event
from .mission_s import mission_s
from .monster_hunting import MonsterHunt
from .shadow_war import shadow_war_event


@dataclass
class ActionSpec:
    func: Callable
    name: str


def _run_monster_hunt(*args, **kwargs):
    MonsterHunt().run(*args, **kwargs)


_BASE_ACTIONS = {
    "leveling": ActionSpec(start_leveling, "Start Leveling"),
    "daily": ActionSpec(daily, "Daily Missions"),
    "eudemon": ActionSpec(fight_eudemon_boss, "Fight Eudemon Boss"),
    "monster_hunt": ActionSpec(_run_monster_hunt, "Monster Hunting"),
    "cd_event": ActionSpec(fight_cd_event, "Fight CD Event"),
    "aniv_event": ActionSpec(fight_aniv_event, "Fight Aniv Event"),
    "aniv_special": ActionSpec(fight_aniv_special_mission, "Fight Special Boss Event"),
    "phantom": ActionSpec(fight_phantom_event, "Phantom Kyunoki"),
    "snow_event": ActionSpec(fight_snow_event, "Fight Christmas Event"),
    "thanks_event": ActionSpec(fight_thanks_event, "Fight Thanksgiving Event"),
    "sakura_event": ActionSpec(fight_sakura_event, "Fight Sakura Bloom Event"),
    "easter_event": ActionSpec(fight_easter_event, "Fight Easter Event 2026"),
    "worldcup_event": ActionSpec(fight_worldcup_event, "Fight World Cup Event 2026"),
    "pumpkin_event": ActionSpec(fight_pumpkin_event, "Fight Pumpkin Event"),
    "yinyang_event": ActionSpec(fight_yinyang_event, "Fight Yin Yang Event"),
    "event_finisher": ActionSpec(event_finisher, "Event Finisher"),
    "shadow_war": ActionSpec(shadow_war_event, "Shadow War"),
    "clan_war": ActionSpec(clan_war_event, "Clan War"),
    "crew_battle": ActionSpec(crew_battle_event, "Crew Battle"),
    "mission_s": ActionSpec(mission_s, "Mission S"),
    "minigame_event": ActionSpec(fight_minigame_event, "MiniGames Event"),
}

_ENEMY_SELECTION_ACTIONS = {"pumpkin_event", "yinyang_event", "snow_event", "thanks_event", "easter_event", "worldcup_event"}


def _wrap_single_arg(action_func: Callable, arg_value):
    def wrapped_action(*_args, **_kwargs):
        action_func(arg_value)

    return wrapped_action


def resolve_sage_action(
    action: str,
    params: Optional[dict],
    refresh_factory: Callable[[], Callable],
    current_profile: dict,
) -> ActionSpec:
    if action == "refresh":
        return ActionSpec(refresh_factory(), "Refresh Character Info")

    if action not in _BASE_ACTIONS:
        raise ValueError(f"Unknown action: {action}")

    spec = _BASE_ACTIONS[action]

    if action == "clan_war" and not current_profile.get("clan_url"):
        raise ValueError(f"Clan War is not available for {current_profile['label']}")
    if action == "crew_battle" and not current_profile.get("crew_url"):
        raise ValueError(f"Crew Battle is not available for {current_profile['label']}")

    if action in _ENEMY_SELECTION_ACTIONS:
        if not params or "enemy_id" not in params:
            raise ValueError("Enemy selection required")
        enemy_id = params["enemy_id"]
        enemy_name = params.get("enemy_name", "")
        return ActionSpec(
            _wrap_single_arg(spec.func, enemy_id),
            f"{spec.name} - {enemy_name}",
        )

    if action == "minigame_event":
        if not params or "minigame_type" not in params:
            raise ValueError("Minigame selection required")
        minigame_type = params["minigame_type"]
        minigame_name = params.get("minigame_name", minigame_type)
        return ActionSpec(
            _wrap_single_arg(spec.func, minigame_type),
            f"{spec.name} - {minigame_name}",
        )

    return spec
