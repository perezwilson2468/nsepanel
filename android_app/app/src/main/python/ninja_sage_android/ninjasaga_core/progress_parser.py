from __future__ import annotations

from typing import Any


def extract_character_id(char_data: dict[str, Any] | None) -> Any:
    if not isinstance(char_data, dict):
        return None
    value = char_data.get("character_id") or char_data.get("char_id") or char_data.get("id")
    if value is None:
        for key in ("character_data", "data", "character", "result"):
            nested = char_data.get(key)
            if not isinstance(nested, dict):
                continue
            value = nested.get("character_id") or nested.get("char_id") or nested.get("id")
            if value is not None:
                break
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def extract_character_level(char_data: dict[str, Any] | None, default: int = 1) -> int:
    if not isinstance(char_data, dict):
        return int(default)
    value = char_data.get("character_level") or char_data.get("level") or default
    if value == default:
        for key in ("character_data", "data", "character", "result"):
            nested = char_data.get(key)
            if not isinstance(nested, dict):
                continue
            nested_value = nested.get("character_level") or nested.get("level")
            if nested_value is not None:
                value = nested_value
                break
    try:
        return int(value)
    except Exception:
        return int(default)


def extract_progress_snapshot(
    response: Any,
    default_level: int,
    default_rank: int | None = None,
) -> tuple[str, int, int, int, int | None, int | None]:
    data = response if isinstance(response, dict) else {}
    nested = None
    for key in ("character_data", "data", "character", "result"):
        value = data.get(key)
        if isinstance(value, dict):
            nested = value
            break
    merged = dict(nested or {})
    merged.update(data)

    name = merged.get("character_name") or merged.get("name") or "Unknown"
    level_raw = merged.get("character_level") or merged.get("level")
    xp_raw = merged.get("character_xp") or merged.get("xp")
    gold_raw = merged.get("character_gold") or merged.get("gold")
    rank_raw = (
        merged.get("character_rank")
        or merged.get("rank")
        or merged.get("current_rank")
        or merged.get("rank_id")
    )
    energy_raw = merged.get("character_energy") or merged.get("current_energy") or merged.get("energy")

    try:
        level = int(level_raw) if level_raw is not None else int(default_level)
    except Exception:
        level = int(default_level)

    try:
        xp = int(xp_raw) if xp_raw is not None else 0
    except Exception:
        xp = 0

    try:
        gold = int(gold_raw) if gold_raw is not None else 0
    except Exception:
        gold = 0

    try:
        rank = int(rank_raw) if rank_raw is not None else default_rank
    except Exception:
        rank = default_rank

    try:
        energy = int(energy_raw) if energy_raw is not None else None
    except Exception:
        energy = None

    return str(name), level, xp, gold, rank, energy
