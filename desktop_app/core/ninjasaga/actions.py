from dataclasses import dataclass
from functools import partial
from typing import Callable

from .bootstrap import bootstrap_session
from .clan_war import clan_war_event
from .eudemon import eudemon_garden
from .leveling import ninjasaga_leveling
from .special_events import motherday_event, sakura_event
from .tp import tp_training
from .ss import ss_training


@dataclass
class ActionSpec:
    func: Callable
    name: str


def resolve_ninjasaga_action(
    action: str,
    params,
    refresh_factory: Callable[[], Callable],
    current_base_game: dict,
) -> ActionSpec:
    if action == "refresh":
        return ActionSpec(refresh_factory(), "Refresh Character Info")
    if action == "bootstrap":
        return ActionSpec(bootstrap_session, "Bootstrap Session")
    if action == "leveling":
        return ActionSpec(ninjasaga_leveling, "Start Leveling")
    if action == "tp_training":
        return ActionSpec(tp_training, "TP Training")
    if action == "ss_training":
        return ActionSpec(ss_training, "SS Training")
    if action == "eudemon_garden":
        return ActionSpec(eudemon_garden, "Eudemon Garden")
    if action == "motherday_event":
        return ActionSpec(motherday_event, "Mother Day")
    if action == "sakura_event":
        selected_enemy_id = params.get("enemy_id") if isinstance(params, dict) else None
        selected_enemy_name = params.get("enemy_name") if isinstance(params, dict) else None
        return ActionSpec(
            partial(sakura_event, selected_enemy_id, selected_enemy_name),
            f"Sakura Festival - {selected_enemy_name or selected_enemy_id or 'Default'}",
        )
    if action == "clan_war":
        return ActionSpec(clan_war_event, "Clan War")

    raise NotImplementedError(
        f"{current_base_game['label']} actions are not implemented yet in this panel"
    )
