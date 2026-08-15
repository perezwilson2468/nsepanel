from __future__ import annotations

from typing import Any, Callable

from . import anti_detection, progress_parser, rate_control, recovery


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _collect_reward_values(node: Any, sink: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key).strip().lower()
            if key_text in {"status", "error"}:
                continue
            _collect_reward_values(value, sink)
        return
    if isinstance(node, list):
        for item in node:
            _collect_reward_values(item, sink)
        return
    if node is None:
        return
    text = str(node).strip()
    if text:
        sink.append(text)


def _extract_treasure_reward_summary(response: Any) -> str:
    if not isinstance(response, dict):
        return "reward: unknown"

    direct_values: list[str] = []
    for key in ("reward", "rewards", "item", "items", "gold", "xp", "token", "event_point"):
        value = response.get(key)
        if value is not None:
            direct_values.append(f"{key}={value}")
    result = response.get("result")
    if isinstance(result, dict):
        for key in ("reward", "rewards", "item", "items", "gold", "xp", "token", "event_point"):
            value = result.get(key)
            if value is not None:
                direct_values.append(f"{key}={value}")
    if direct_values:
        return " | ".join(direct_values[:4])

    leaves: list[str] = []
    _collect_reward_values(response, leaves)
    if not leaves:
        return "reward: none"
    unique: list[str] = []
    seen: set[str] = set()
    for token in leaves:
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)
        if len(unique) >= 4:
            break
    return "reward tokens: " + ", ".join(unique)


def _tile_distance(a: int, b: int) -> int:
    ax, ay = a % 5, a // 5
    bx, by = b % 5, b // 5
    return abs(ax - bx) + abs(ay - by)


def _find_treasure_tiles(enemy_ids: list[str], token_kind: Callable[[str], str]) -> list[int]:
    return [idx for idx, token in enumerate(enemy_ids) if token_kind(str(token)) == "treasure"]


def _find_enemy_tiles(enemy_ids: list[str], token_kind: Callable[[str], str]) -> list[int]:
    return [idx for idx, token in enumerate(enemy_ids) if token_kind(str(token)) == "enemy"]


def _choose_target_tile(
    current_pos: int,
    enemy_ids: list[str],
    token_kind: Callable[[str], str],
    boss_tile: int = 19,
) -> tuple[str, int]:
    treasure_tiles = _find_treasure_tiles(enemy_ids, token_kind)
    if treasure_tiles:
        nearest_treasure = min(
            treasure_tiles,
            key=lambda idx: (_tile_distance(current_pos, idx), _tile_distance(idx, boss_tile), idx),
        )
        return "chest", nearest_treasure
    return "final_boss", boss_tile


def _describe_target_hint(current_pos: int, enemy_ids: list[str], token_kind: Callable[[str], str], boss_tile: int = 19) -> str:
    treasure_tiles = _find_treasure_tiles(enemy_ids, token_kind)
    enemy_tiles = [idx for idx in _find_enemy_tiles(enemy_ids, token_kind) if idx != boss_tile]
    target_kind, target_tile = _choose_target_tile(current_pos, enemy_ids, token_kind, boss_tile)
    chest_tiles = ",".join(str(idx) for idx in treasure_tiles) if treasure_tiles else "-"
    enemy_text = ",".join(str(idx) for idx in enemy_tiles) if enemy_tiles else "-"
    return (
        f"chests=[{chest_tiles}] | mini_bosses=[{enemy_text}] | "
        f"target_{target_kind}={target_tile} (distance={_tile_distance(current_pos, target_tile)}) | "
        f"final boss tile={boss_tile} (distance={_tile_distance(current_pos, boss_tile)})"
    )


def _pick_empty_move(
    current_pos: int,
    enemy_ids: list[str],
    *,
    adjacent_indices: Callable[[int], list[int]],
    token_kind: Callable[[str], str],
    previous_pos: int | None = None,
    boss_tile: int = 19,
) -> int | None:
    neighbors = adjacent_indices(current_pos)
    empty_neighbors = [idx for idx in neighbors if idx < len(enemy_ids) and token_kind(enemy_ids[idx]) == "empty"]
    if not empty_neighbors:
        return None
    _, target_tile = _choose_target_tile(current_pos, enemy_ids, token_kind, boss_tile)
    preferred = sorted(
        empty_neighbors,
        key=lambda idx: (
            idx == previous_pos,
            _tile_distance(idx, target_tile),
            _tile_distance(idx, boss_tile),
            idx,
        ),
    )
    return preferred[0] if preferred else None


def _should_fight_adjacent_enemy(
    current_pos: int,
    enemy_pos: int,
    enemy_ids: list[str],
    *,
    token_kind: Callable[[str], str],
    boss_tile: int = 19,
) -> bool:
    if enemy_pos == boss_tile:
        return True
    _, target_tile = _choose_target_tile(current_pos, enemy_ids, token_kind, boss_tile)
    current_distance = _tile_distance(current_pos, target_tile)
    enemy_distance = _tile_distance(enemy_pos, target_tile)
    return enemy_distance < current_distance


def run_easter_event(
    *,
    stop_event: Any,
    char_id: str,
    runtime_settings: dict[str, Any],
    battle_delay_seconds: int = 25,
    cycle_cooldown_seconds: int = 5,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str, str], None] | None = None,
    easter_get_battle_status: Callable[[], dict[str, Any]] | None = None,
    parse_battle_status: Callable[[Any], dict[str, Any] | None] | None = None,
    easter_buy_battle_heart: Callable[[int], dict[str, Any]] | None = None,
    adjacent_indices: Callable[[int], list[int]] | None = None,
    token_kind: Callable[[str], str] | None = None,
    easter_open_treasure: Callable[[int], dict[str, Any]] | None = None,
    easter_start_battle: Callable[[str, int, int], dict[str, Any]] | None = None,
    boss_reward_event: Callable[[str, int], dict[str, Any]] | None = None,
    get_character_data: Callable[[Any], dict[str, Any]] | None = None,
    easter_enemy_label: Callable[[str, int], str] | None = None,
    easter_generate_new_map: Callable[[], dict[str, Any]] | None = None,
    is_success_response: Callable[[Any], bool] | None = None,
    runtime_relogin_and_reselect_character: Callable[[Any], bool] | None = None,
) -> None:
    if not all([easter_get_battle_status, parse_battle_status, easter_buy_battle_heart, adjacent_indices, token_kind, easter_open_treasure, easter_start_battle, boss_reward_event, get_character_data, easter_enemy_label, easter_generate_new_map, is_success_response]):
        raise ValueError("Android NinjaSaga Easter core requires complete callbacks")

    battle_delay_seconds = int(runtime_settings.get("easter_battle_delay_seconds", battle_delay_seconds))
    cycle_cooldown_seconds = int(runtime_settings.get("easter_cycle_cooldown_seconds", cycle_cooldown_seconds))
    auto_spend_enabled = bool(runtime_settings.get("easter_auto_spend_enabled", False))
    auto_spend_max_refills = max(0, int(runtime_settings.get("easter_auto_spend_max_refills_per_run", 0)))
    auto_spend_buy_amount = max(1, int(runtime_settings.get("easter_auto_spend_buy_amount", 3)))
    anti_profile = anti_detection.build_anti_detection_profile(runtime_settings)

    auto_spend_used = 0
    observed_max_heart = 0
    recent_positions: list[int] = []
    cycle = 0
    current_pos: int | None = None
    cached_enemy_ids: list[str] = []
    cached_remain_heart = 0
    cached_refill_remain = 0
    cached_event_point = 0
    status_refresh_needed = True
    previous_pos: int | None = None

    while not rate_control.stop_requested(stop_event):
        cycle += 1
        if status_refresh_needed or not cached_enemy_ids:
            try:
                status_payload = easter_get_battle_status()
                status = parse_battle_status(status_payload)
                if not status:
                    if log:
                        log(f"[Cycle {cycle}] getBattleStatus failed: {status_payload}", "warning")
                    return
            except Exception as exc:
                cloudflare_wait, _ = anti_detection.next_cloudflare_wait(anti_profile, 0)
                recovered = recovery.handle_runtime_exception(
                    stop_event=stop_event,
                    exc=exc,
                    char_id=char_id,
                    context=f"[Cycle {cycle}] Easter getBattleStatus",
                    cloudflare_rest_seconds=cloudflare_wait,
                    relogin_and_reselect_character=runtime_relogin_and_reselect_character,
                    log=log,
                )
                if not recovered:
                    return
                continue

            cached_remain_heart = _safe_int(status.get("remain_heart", 0))
            cached_refill_remain = _safe_int(status.get("heart_refill_remain", 0))
            cached_event_point = _safe_int(status.get("event_point", 0))
            cached_enemy_ids = [str(v) for v in (status.get("enemy_id", []) or [])]
            if current_pos is None:
                current_pos = _safe_int(status.get("start_position", 0))
            status_refresh_needed = False

        remain_heart = cached_remain_heart
        refill_remain = cached_refill_remain
        event_point = cached_event_point
        enemy_ids = list(cached_enemy_ids)
        current_pos = _safe_int(current_pos, 0)
        observed_max_heart = max(observed_max_heart, int(remain_heart))

        boss_missing = len(enemy_ids) <= 19 or token_kind(str(enemy_ids[19])) != "enemy"
        if boss_missing:
            if log:
                log(f"[Cycle {cycle}] final boss tile 19 is gone, generating new map...", "info")
            gen_res = easter_generate_new_map()
            if not is_success_response(gen_res):
                if log:
                    log(f"[Cycle {cycle}] generateNewMap failed: {gen_res}", "warning")
                return
            current_pos = 0
            previous_pos = None
            recent_positions.clear()
            status_refresh_needed = True
            if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                return
            continue

        if log:
            log(
                f"[Cycle {cycle}] hearts={remain_heart} refill={refill_remain}s points={event_point} pos={current_pos}",
                "info",
            )
            log(
                f"[Cycle {cycle}] board -> {_describe_target_hint(current_pos, enemy_ids, token_kind)}",
                "info",
            )

        if remain_heart <= 0 and auto_spend_enabled:
            if auto_spend_used >= auto_spend_max_refills:
                if log:
                    log(f"[Cycle {cycle}] [AutoSpend] {auto_spend_used}/{auto_spend_max_refills} completed. hearts=0, stop.", "warning")
                return
            target = max(1, observed_max_heart)
            if log:
                log(f"[Cycle {cycle}] [AutoSpend] {auto_spend_used}/{auto_spend_max_refills} -> refill to {target}", "info")
            while remain_heart < target and not rate_control.stop_requested(stop_event):
                buy_amount = min(auto_spend_buy_amount, target - remain_heart)
                buy_res = easter_buy_battle_heart(buy_amount)
                if not is_success_response(buy_res):
                    if log:
                        log(f"[Cycle {cycle}] buyBattleHeart failed: {buy_res}", "warning")
                    break
                status_after_buy = parse_battle_status(easter_get_battle_status())
                if not status_after_buy:
                    break
                cached_remain_heart = _safe_int(status_after_buy.get("remain_heart", remain_heart))
                cached_refill_remain = _safe_int(status_after_buy.get("heart_refill_remain", cached_refill_remain))
                cached_event_point = _safe_int(status_after_buy.get("event_point", cached_event_point))
                cached_enemy_ids = [str(v) for v in (status_after_buy.get("enemy_id", enemy_ids) or [])]
                remain_heart = cached_remain_heart
                observed_max_heart = max(observed_max_heart, int(remain_heart))
                if log:
                    log(f"[Cycle {cycle}] hearts after refill -> {remain_heart}", "info")
            auto_spend_used += 1
            if log:
                log(f"[Cycle {cycle}] [AutoSpend] used {auto_spend_used}/{auto_spend_max_refills}", "info")
            if remain_heart <= 0:
                return

        neighbors = adjacent_indices(current_pos)
        treasure_target = next((idx for idx in neighbors if idx < len(enemy_ids) and token_kind(enemy_ids[idx]) == "treasure"), None)
        if treasure_target is not None:
            if log:
                log(f"[Cycle {cycle}] openTreasure slot={treasure_target}", "info")
            open_res = easter_open_treasure(treasure_target)
            if not is_success_response(open_res):
                if log:
                    log(f"[Cycle {cycle}] openTreasure failed: {open_res}", "warning")
                if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                    return
                continue
            if log:
                log(f"[Cycle {cycle}] chest -> {_extract_treasure_reward_summary(open_res)}", "success")
            if treasure_target < len(enemy_ids):
                enemy_ids[treasure_target] = "1"
                cached_enemy_ids = list(enemy_ids)
            if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                return
            continue

        if remain_heart <= 0:
            if log:
                log(
                    f"[Cycle {cycle}] hearts=0 and no adjacent treasure. Cannot start battle; stopping to avoid pointless movement.",
                    "warning",
                )
            return

        enemy_target = next(
            (
                idx
                for idx in neighbors
                if idx < len(enemy_ids)
                and token_kind(enemy_ids[idx]) == "enemy"
                and _should_fight_adjacent_enemy(
                    current_pos,
                    idx,
                    enemy_ids,
                    token_kind=token_kind,
                )
            ),
            None,
        )
        if enemy_target is not None:
            enemy_id = enemy_ids[enemy_target]
            if log:
                log(f"[Cycle {cycle}] startBattle {easter_enemy_label(enemy_id, enemy_target)} at slot={enemy_target}", "info")
            start_res = easter_start_battle(enemy_id, enemy_target, current_pos)
            if not is_success_response(start_res):
                if log:
                    log(f"[Cycle {cycle}] startBattle failed: {start_res}", "warning")
                if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                    return
                continue

            if not rate_control.wait_with_stop(stop_event, max(1, battle_delay_seconds)):
                return

            finish_res = boss_reward_event(enemy_id, 0)
            if not is_success_response(finish_res):
                finish_res = boss_reward_event(enemy_id, 1)
            if not is_success_response(finish_res):
                if log:
                    log(f"[Cycle {cycle}] finish boss failed: {finish_res}", "warning")
                if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                    return
                continue

            previous_pos = current_pos
            current_pos = enemy_target
            status_refresh_needed = True
            updated = get_character_data(char_id)
            _, level, xp, gold, _, _ = progress_parser.extract_progress_snapshot(updated, default_level=1)
            if on_update:
                on_update({"level": level, "xp": xp, "gold": gold})
            if log:
                log(
                    f"[Cycle {cycle}] boss finished: {easter_enemy_label(enemy_id, enemy_target)} | "
                    f"moved {previous_pos} -> {current_pos} | Lv {level} XP {xp} Gold {gold}",
                    "success",
                )
            if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                return
            continue

        empty_target = _pick_empty_move(
            current_pos,
            enemy_ids,
            adjacent_indices=adjacent_indices,
            token_kind=token_kind,
            previous_pos=previous_pos,
            boss_tile=19,
        )
        if empty_target is not None:
            previous = current_pos
            current_pos = empty_target
            previous_pos = previous
            recent_positions.append(current_pos)
            if len(recent_positions) > 8:
                recent_positions = recent_positions[-8:]
            if log:
                log(
                    f"[Cycle {cycle}] move from {previous} -> {current_pos} | "
                    f"{_describe_target_hint(current_pos, enemy_ids, token_kind)}",
                    "info",
                )
            if len(recent_positions) >= 6 and len(set(recent_positions[-6:])) <= 2:
                if log:
                    log(f"[Cycle {cycle}] movement loop detected, generating new map...", "warning")
                gen_res = easter_generate_new_map()
                if not is_success_response(gen_res):
                    if log:
                        log(f"[Cycle {cycle}] generateNewMap failed: {gen_res}", "warning")
                    return
                current_pos = 0
                previous_pos = None
                recent_positions.clear()
                status_refresh_needed = True
                if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                    return
                continue
            if not rate_control.wait_with_stop(stop_event, 1):
                return
            continue

        gen_res = easter_generate_new_map()
        if not is_success_response(gen_res):
            if log:
                log(f"[Cycle {cycle}] generateNewMap failed: {gen_res}", "warning")
            return
        current_pos = 0
        previous_pos = None
        recent_positions.clear()
        status_refresh_needed = True
        if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
            return
