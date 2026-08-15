from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .eudemon import eudemon_garden
from .leveling import zenshin_leveling
from .ss import ss_training
from .tp import tp_training


@dataclass
class ActionSpec:
    func: Callable
    name: str


def resolve_zenshin_action(
    action: str,
    params,
    refresh_factory: Callable[[], Callable],
    current_base_game: dict,
) -> ActionSpec:
    if action == "refresh":
        return ActionSpec(refresh_factory(), "Refresh Character Info")
    if action == "leveling":
        return ActionSpec(zenshin_leveling, "Start Ninja Zenshin Leveling")
    if action == "tp_training":
        return ActionSpec(tp_training, "Ninja Zenshin TP Training")
    if action == "ss_training":
        return ActionSpec(ss_training, "Ninja Zenshin SS Training")
    if action == "eudemon_garden":
        return ActionSpec(eudemon_garden, "Ninja Zenshin Eudemon Garden")
    raise NotImplementedError(
        f"{current_base_game['label']} actions are not implemented yet in this panel"
    )
