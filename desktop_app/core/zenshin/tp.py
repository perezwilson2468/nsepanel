from __future__ import annotations

import time

from .. import config
from . import amf_req
from . import leveling as lv


def tp_training(loop_times=None):
    if not isinstance(getattr(config, "zenshin_state", None), dict):
        config.zenshin_state = {}

    if not isinstance(getattr(config, "login_data", None), dict):
        raise ValueError("Login data is not loaded in memory")

    state = getattr(config, "zenshin_state", None) or {}
    profile = lv._build_anti_detection_profile(state)
    delay_seconds = profile["action_delay_seconds"]
    cycle_cooldown_seconds = profile["cycle_cooldown_seconds"]
    action_jitter_seconds = profile["action_jitter_seconds"]
    min_call_delay_seconds = profile["min_call_delay_seconds"]
    start_retry_delay_seconds = profile["start_retry_delay_seconds"]
    start_max_retries = profile["start_max_retries"]

    char_id, char_level = lv._resolve_current_character()
    char_rank = lv._resolve_char_rank_with_refresh(char_id, getattr(config, "char_data", None))
    if char_level < 40:
        print(f"TP Training requires level 40+. Current level: {char_level}.")
        return
    if (char_rank or -1) < lv.RANK_JOUNIN:
        print(
            f"TP Training requires rank Jounin. Current rank: {lv._rank_name(char_rank)}({char_rank})."
        )
        return

    try:
        configured_loops = int(state.get("tp_training_abuse_loop") or 1)
    except Exception:
        configured_loops = 1
    total_passes = int(loop_times) if loop_times is not None else max(1, configured_loops)

    eligible_missions = [
        mid for mid in lv.TP_TRAINING_MISSIONS
        if (lv._mission_required_level(mid) or 0) <= char_level
    ]
    if not eligible_missions:
        print(f"No TP daily missions available for level {char_level}.")
        return

    account_type = lv._account_type_from_login()
    print(
        f"Starting TP Training | char_id={char_id} | level={char_level} | "
        f"rank={lv._rank_name(char_rank)}({char_rank}) | abuse_loops={total_passes}"
    )
    print(
        "TP Training daily mission queue: "
        + ", ".join(lv._mission_display_label(mid, account_type=account_type) for mid in eligible_missions)
    )

    last_amf_call_at = None

    for pass_index in range(1, total_passes + 1):
        if lv._stop_requested():
            print("TP Training stopped by user request")
            break

        any_started = False
        for mission_id in eligible_missions:
            if lv._stop_requested():
                print("TP Training stopped by user request")
                return

            mission_label = lv._mission_display_label(mission_id, account_type=account_type)
            print(f"[TP Pass {pass_index}] try mission {mission_label}")

            start_result = None
            started = False
            for attempt in range(1, start_max_retries + 1):
                ok_to_call, last_amf_call_at = lv._wait_min_call_interval(
                    last_amf_call_at,
                    min_call_delay_seconds,
                    action_jitter_seconds,
                )
                if not ok_to_call:
                    print("TP Training stopped by user request")
                    return
                try:
                    start_result = amf_req.start_mission(mission_id)
                    last_amf_call_at = time.time()
                except Exception as exc:
                    print(f"[TP Pass {pass_index}] startMission {mission_id} exception: {exc}")
                    start_result = {"status": 0, "error": str(exc)}
                    break

                if isinstance(start_result, dict) and str(start_result.get("status", "1")) == "1":
                    started = True
                    any_started = True
                    break

                if lv._error_code(start_result) == 100 and attempt < start_max_retries:
                    retry_wait = lv._jittered_wait_seconds(
                        start_retry_delay_seconds,
                        action_jitter_seconds,
                    )
                    print(
                        f"[TP Pass {pass_index}] {mission_id} locked (error 100), retry "
                        f"{attempt + 1}/{start_max_retries} in {retry_wait:.1f}s..."
                    )
                    if not lv._wait_with_stop(retry_wait):
                        print("TP Training stopped by user request")
                        return
                    continue
                break

            if not started:
                cooldown = lv._cooldown_seconds(start_result)
                if lv._tp_daily_mission_consumed(start_result):
                    print(f"[TP Pass {pass_index}] {mission_id} already consumed/locked today, skipping.")
                elif cooldown > 0:
                    print(f"[TP Pass {pass_index}] {mission_id} cooldown/lock active, skipping.")
                else:
                    print(f"[TP Pass {pass_index}] {mission_id} unavailable: {start_result}")
                continue

            if delay_seconds > 0:
                action_wait = lv._jittered_wait_seconds(delay_seconds, action_jitter_seconds)
                if not lv._wait_with_stop(action_wait):
                    print("TP Training stopped by user request")
                    return

            ok_to_call, last_amf_call_at = lv._wait_min_call_interval(
                last_amf_call_at,
                min_call_delay_seconds,
                action_jitter_seconds,
            )
            if not ok_to_call:
                print("TP Training stopped by user request")
                return

            try:
                update_result = amf_req.update_character_progress(
                    char_id=char_id,
                    char_level=char_level,
                    mission_id=mission_id,
                    xp_gain=0,
                    gold_gain=0,
                )
                last_amf_call_at = time.time()
            except Exception as exc:
                print(f"[TP Pass {pass_index}] updateCharacter {mission_id} exception: {exc}")
                continue

            if not lv._is_success_response(update_result):
                if lv._tp_daily_mission_consumed(update_result):
                    print(f"[TP Pass {pass_index}] {mission_id} already completed today, skipping.")
                else:
                    print(f"[TP Pass {pass_index}] updateCharacter failed for {mission_id}: {update_result}")
                continue

            char_name, parsed_level, char_xp, char_gold, parsed_rank, parsed_energy = lv._extract_progress_snapshot(
                update_result,
                default_level=char_level,
                default_rank=char_rank,
            )
            char_level = parsed_level
            if parsed_rank is not None:
                char_rank = parsed_rank
            tp_reward = lv._extract_training_reward(update_result, "tp") or lv._mission_reward_value(mission_id, "tp")
            rank_suffix = f" {lv._rank_name(char_rank)}({char_rank})" if char_rank is not None else ""
            energy_suffix = f" Energy {parsed_energy}" if parsed_energy is not None else ""
            reward_suffix = f" TP +{tp_reward}" if tp_reward > 0 else ""
            print(
                f"[TP Pass {pass_index}] ok -> {char_name} Lv {char_level}{rank_suffix} "
                f"XP {char_xp} Gold {char_gold}{energy_suffix}{reward_suffix}"
            )
            lv._push_live_progress_update(
                level=char_level,
                xp=char_xp,
                gold=char_gold,
                tokens=(update_result.get("account_tokens") if isinstance(update_result, dict) else None),
            )

            cooldown_wait = lv._jittered_wait_seconds(cycle_cooldown_seconds, action_jitter_seconds)
            if not lv._wait_with_stop(cooldown_wait):
                print("TP Training stopped by user request")
                return

        if not any_started:
            print(f"[TP Pass {pass_index}] No TP mission was available in this pass.")
