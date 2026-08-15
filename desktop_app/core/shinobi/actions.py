from dataclasses import dataclass
from typing import Callable

from .leveling import (
    shinobi_arena_xtra,
    shinobi_daily_missions_xtra,
    shinobi_event_xtra,
    shinobi_hunting_house_xtra,
    shinobi_leveling,
    shinobi_leveling_xtra,
)


@dataclass
class ActionSpec:
    func: Callable
    name: str


def resolve_shinobi_action(
    action: str,
    refresh_factory: Callable[[], Callable],
    current_base_game: dict,
) -> ActionSpec:
    if action == "refresh":
        return ActionSpec(refresh_factory(), "Refresh Character Info")
    if action == "leveling":
        return ActionSpec(shinobi_leveling, "Start Leveling")
    if action == "leveling_xtra":
        return ActionSpec(shinobi_leveling_xtra, "Start Leveling XTRA")
    if action == "daily_missions_xtra":
        return ActionSpec(shinobi_daily_missions_xtra, "Daily Missions XTRA")
    if action == "hunting_house_xtra":
        return ActionSpec(shinobi_hunting_house_xtra, "Hunting House XTRA")
    if action == "arena_xtra":
        return ActionSpec(shinobi_arena_xtra, "Arena XTRA")
    if action == "event_xtra":
        return ActionSpec(shinobi_event_xtra, "Event XTRA")

    raise NotImplementedError(
        f"{current_base_game['label']} actions are not implemented yet in this panel"
    )
