from .ninjasaga.actions import resolve_ninjasaga_action
from .rift.actions import resolve_rift_action
from .sage.actions import resolve_sage_action
from .shinobi.actions import resolve_shinobi_action
from .zenshin.actions import resolve_zenshin_action


def resolve_action(base_game: dict, action: str, params, refresh_factory, current_profile: dict):
    base_game_id = base_game["id"]

    if base_game_id == "sage":
        return resolve_sage_action(action, params, refresh_factory, current_profile)

    if base_game_id == "zenshin":
        if action in {"motherday_event", "sakura_event"}:
            raise NotImplementedError(
                "Ninja Zenshin event actions are hidden for now because their server flow is not confirmed yet."
            )
        return resolve_zenshin_action(action, params, refresh_factory, base_game)

    if base_game_id == "rift":
        return resolve_rift_action(action, params, refresh_factory, base_game)

    if base_game_id == "shinobi":
        return resolve_shinobi_action(action, refresh_factory, base_game)

    if base_game_id == "ninjasaga":
        return resolve_ninjasaga_action(action, params, refresh_factory, base_game)

    raise NotImplementedError(f"{base_game['label']} is not wired into the action router yet")
