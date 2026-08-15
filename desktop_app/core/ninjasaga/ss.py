import time
from typing import Any

from .. import config
from . import amf_req
from . import leveling as lv

SS_MISSION_IDS = ["msn279", "msn280", "msn281", "msn282", "msn283"]


def _status_preview(payload: Any) -> str:
    if isinstance(payload, dict):
        keys = list(payload.keys())
        result = payload.get("result")
        if isinstance(result, list):
            return f"dict keys={','.join(str(k) for k in keys[:6])} result_len={len(result)}"
        return f"dict keys={','.join(str(k) for k in keys[:6])}"
    if isinstance(payload, list):
        return f"list len={len(payload)}"
    return str(type(payload).__name__)


def ss_training(loop_times=None):
    if not isinstance(getattr(config, "login_data", None), dict):
        raise ValueError("Login data is not loaded in memory")

    state = getattr(config, "ninjasaga_state", None) or {}
    profile = lv._build_anti_detection_profile(state)
    delay_seconds = profile["action_delay_seconds"]
    cycle_cooldown_seconds = profile["cycle_cooldown_seconds"]
    action_jitter_seconds = profile["action_jitter_seconds"]
    min_call_delay_seconds = profile["min_call_delay_seconds"]
    start_retry_delay_seconds = profile["start_retry_delay_seconds"]
    start_max_retries = profile["start_max_retries"]

    char_id, char_level = lv._resolve_current_character()
    char_rank = lv._resolve_char_rank_with_refresh(char_id, getattr(config, "char_data", None))
    if char_level < 80:
        print(f"SS Training requires level 80+. Current level: {char_level}.")
        return
    if (char_rank or -1) < lv.RANK_TUTOR:
        print(
            f"SS Training requires rank Tutor. Current rank: {lv._rank_name(char_rank)}({char_rank})."
        )
        return

    configured_loops = 1
    try:
        configured_loops = int(state.get("ss_training_abuse_loop") or 1)
    except Exception:
        configured_loops = 1
    total_passes = int(loop_times) if loop_times is not None else max(1, configured_loops)

    print(
        f"Starting SS Training | char_id={char_id} | level={char_level} | "
        f"rank={lv._rank_name(char_rank)}({char_rank}) | abuse_loops={total_passes}"
    )

    account_type = lv._account_type_from_login()
    last_amf_call_at = None

    for pass_index in range(1, total_passes + 1):
        if lv._stop_requested():
            print("SS Training stopped by user request")
            break

        ok_to_call, last_amf_call_at = lv._wait_min_call_interval(
            last_amf_call_at,
            min_call_delay_seconds,
            action_jitter_seconds,
        )
        if not ok_to_call:
            print("SS Training stopped by user request")
            return
        try:
            status_payload = amf_req.get_ss_training_mission_status()
            last_amf_call_at = time.time()
            print(f"[SS Pass {pass_index}] getMissionStatus -> {_status_preview(status_payload)}")
        except Exception as exc:
            print(f"[SS Pass {pass_index}] getMissionStatus failed: {exc}")

        any_started = False
        for mission_id in SS_MISSION_IDS:
            if lv._stop_requested():
                print("SS Training stopped by user request")
                return

            mission_label = lv._mission_display_label(mission_id, account_type=account_type)
            print(f"[SS Pass {pass_index}] try mission {mission_label}")

            start_result = None
            started = False
            for attempt in range(1, start_max_retries + 1):
                ok_to_call, last_amf_call_at = lv._wait_min_call_interval(
                    last_amf_call_at,
                    min_call_delay_seconds,
                    action_jitter_seconds,
                )
                if not ok_to_call:
                    print("SS Training stopped by user request")
                    return
                try:
                    start_result = amf_req.start_mission(mission_id)
                    last_amf_call_at = time.time()
                except Exception as exc:
                    print(f"[SS Pass {pass_index}] startMission {mission_id} exception: {exc}")
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
                        f"[SS Pass {pass_index}] {mission_id} locked (error 100), retry "
                        f"{attempt + 1}/{start_max_retries} in {retry_wait:.1f}s..."
                    )
                    if not lv._wait_with_stop(retry_wait):
                        print("SS Training stopped by user request")
                        return
                    continue
                break

            if not started:
                cooldown = lv._cooldown_seconds(start_result)
                if cooldown > 0:
                    print(f"[SS Pass {pass_index}] {mission_id} cooldown/lock active, skipping.")
                else:
                    print(f"[SS Pass {pass_index}] {mission_id} unavailable: {start_result}")
                continue

            if delay_seconds > 0:
                action_wait = lv._jittered_wait_seconds(delay_seconds, action_jitter_seconds)
                if not lv._wait_with_stop(action_wait):
                    print("SS Training stopped by user request")
                    return

            ok_to_call, last_amf_call_at = lv._wait_min_call_interval(
                last_amf_call_at,
                min_call_delay_seconds,
                action_jitter_seconds,
            )
            if not ok_to_call:
                print("SS Training stopped by user request")
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
                print(f"[SS Pass {pass_index}] updateCharacter {mission_id} exception: {exc}")
                continue

            if not lv._is_success_response(update_result):
                print(f"[SS Pass {pass_index}] updateCharacter failed for {mission_id}: {update_result}")
                continue

            char_name, parsed_level, char_xp, char_gold, parsed_rank, parsed_energy = lv._extract_progress_snapshot(
                update_result,
                default_level=char_level,
                default_rank=char_rank,
            )
            char_level = parsed_level
            if parsed_rank is not None:
                char_rank = parsed_rank
            ss_reward = lv._extract_training_reward(update_result, "ss") or lv._mission_reward_value(mission_id, "sp")
            rank_suffix = f" {lv._rank_name(char_rank)}({char_rank})" if char_rank is not None else ""
            energy_suffix = f" Energy {parsed_energy}" if parsed_energy is not None else ""
            reward_suffix = f" SS +{ss_reward}" if ss_reward > 0 else ""
            print(
                f"[SS Pass {pass_index}] ok -> {char_name} Lv {char_level}{rank_suffix} "
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
                print("SS Training stopped by user request")
                return

        if not any_started:
            print(f"[SS Pass {pass_index}] No SS mission was available in this pass.")
