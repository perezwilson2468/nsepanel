from __future__ import annotations

from typing import Any, Callable

from . import anti_detection, progress_parser, rate_control, recovery


def run_eudemon_garden(
    *,
    stop_event: Any,
    char_id: str,
    runtime_settings: dict[str, Any],
    start_finish_delay_seconds: int = 5,
    cycle_cooldown_seconds: int = 5,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str, str], None] | None = None,
    get_hunting_status: Callable[[], dict[str, Any]] | None = None,
    extract_rooms: Callable[[Any], list[dict[str, Any]]] | None = None,
    get_character_data: Callable[[Any], dict[str, Any]] | None = None,
    enemy_data: Callable[[], dict[str, dict[str, Any]]] | None = None,
    extract_enemy_ids: Callable[[dict[str, Any]], list[str]] | None = None,
    enemy_list_display: Callable[[list[str]], str] | None = None,
    room_boss_name: Callable[[int], str] | None = None,
    start_hunting: Callable[[int, list[Any] | None], dict[str, Any]] | None = None,
    finish_hunting: Callable[[int], dict[str, Any]] | None = None,
    is_success_response: Callable[[Any], bool] | None = None,
    runtime_relogin_and_reselect_character: Callable[[Any], bool] | None = None,
) -> None:
    if not all([get_hunting_status, extract_rooms, get_character_data, enemy_data, extract_enemy_ids, enemy_list_display, start_hunting, finish_hunting, is_success_response]):
        raise ValueError("Android NinjaSaga Eudemon core requires complete callbacks")

    start_finish_delay_seconds = int(runtime_settings.get("eudemon_start_finish_delay_seconds", start_finish_delay_seconds))
    cycle_cooldown_seconds = int(runtime_settings.get("eudemon_cycle_cooldown_seconds", cycle_cooldown_seconds))
    anti_profile = anti_detection.build_anti_detection_profile(runtime_settings)

    cycle = 0
    while not rate_control.stop_requested(stop_event):
        cycle += 1
        try:
            status_payload = get_hunting_status()
            rooms = extract_rooms(status_payload)
            if not rooms:
                if log:
                    log(f"[Cycle {cycle}] No hunting rooms available", "warning")
                return

            current_char = get_character_data(char_id)
            _, char_level, _, _, _, _ = progress_parser.extract_progress_snapshot(current_char, default_level=1)
            enemies = enemy_data()
            candidates: list[tuple[int, int, dict[str, Any], list[str]]] = []
            for idx, room in enumerate(rooms):
                tries = _safe_int(room.get("time"), 0)
                if tries <= 0:
                    continue
                enemy_ids = extract_enemy_ids(room)
                required_level = max(
                    [_safe_int((enemies.get(enemy_id) or {}).get("min_level"), 0) for enemy_id in enemy_ids] or [0]
                )
                if char_level < required_level:
                    continue
                candidates.append((required_level, idx, room, enemy_ids))
            if not candidates:
                if log:
                    log(f"[Cycle {cycle}] No eligible room (tries finished or level-gated)", "warning")
                return

            candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
            _, room_idx, room, enemy_ids = candidates[0]
            room_xp = _safe_int(room.get("xp"), 0)
            room_gold = _safe_int(room.get("gold"), 0)
            boss_name = room_boss_name(room_idx) if room_boss_name else ""
            boss_prefix = f" boss={boss_name}" if boss_name else ""
            if log:
                log(
                    f"[Cycle {cycle}] startHunting room={room_idx}{boss_prefix} vs {enemy_list_display(enemy_ids)} | xp={room_xp} gold={room_gold}",
                    "info",
                )

            start_result = start_hunting(room_idx, enemy_ids=enemy_ids)
            if not is_success_response(start_result):
                if log:
                    log(f"[Cycle {cycle}] startHunting failed: {start_result}", "warning")
                if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                    return
                continue

            if log:
                log(f"[Cycle {cycle}] waiting fixed {max(1, start_finish_delay_seconds)}s before finishHunting...", "info")
            if not rate_control.wait_with_stop(stop_event, max(1, start_finish_delay_seconds)):
                return

            finish_result = finish_hunting(room_idx)
            if not is_success_response(finish_result):
                if log:
                    log(f"[Cycle {cycle}] finishHunting failed: {finish_result}", "warning")
                if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                    return
                continue

            updated = get_character_data(char_id)
            _, level, xp, gold, _, _ = progress_parser.extract_progress_snapshot(updated, default_level=char_level)
            if on_update:
                on_update({"level": level, "xp": xp, "gold": gold})
            if log:
                log(
                    f"[Cycle {cycle}] ok -> finishHunting success | XP {room_xp or xp} | Gold {room_gold or gold} | Lv {level}",
                    "success",
                )
        except Exception as exc:
            cloudflare_wait, _ = anti_detection.next_cloudflare_wait(anti_profile, 0)
            recovered = recovery.handle_runtime_exception(
                stop_event=stop_event,
                exc=exc,
                char_id=char_id,
                context=f"[Cycle {cycle}] Eudemon Garden",
                cloudflare_rest_seconds=cloudflare_wait,
                relogin_and_reselect_character=runtime_relogin_and_reselect_character,
                log=log,
            )
            if not recovered:
                return

        if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
            return


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)
