from __future__ import annotations

from typing import Any, Callable

from . import anti_detection, progress_parser, rate_control, recovery


def run_leveling(
    *,
    stop_event: Any,
    char_id: str,
    runtime_settings: dict[str, Any],
    mission_id: str = "auto",
    xp_gain: int = 0,
    gold_gain: int = 0,
    action_delay_seconds: int = 6,
    cycle_cooldown_seconds: int = 5,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str, str], None] | None = None,
    get_character_data: Callable[[Any], dict[str, Any]] | None = None,
    start_mission: Callable[[str], dict[str, Any]] | None = None,
    update_character_progress: Callable[[Any, Any, str, int, int], dict[str, Any]] | None = None,
    pick_auto_mission: Callable[[int, int | None], str] | None = None,
    mission_display_label: Callable[[Any], str] | None = None,
    account_type_from_login: Callable[[], int | None] | None = None,
    runtime_relogin_and_reselect_character: Callable[[Any], bool] | None = None,
    get_rank: Callable[[dict[str, Any]], int] | None = None,
    get_control: Callable[[dict[str, Any]], int] | None = None,
    is_success_response_dict: Callable[[Any], bool] | None = None,
    select_special_jounin_class: Callable[[int], dict[str, Any]] | None = None,
    run_rank_exam_hard: Callable[..., bool] | None = None,
    genin_level_cap: int = 20,
    chunin_level_cap: int = 40,
    jounin_level_cap: int = 60,
    special_jounin_level_cap: int = 80,
    rank_chunin: int = 2,
    rank_jounin: int = 4,
    rank_special_jounin: int = 6,
    rank_tutor: int = 8,
    exam_chunin_arr: list[str] | None = None,
    exam_jounin_arr: list[str] | None = None,
    exam_special_jounin_arr_hard: list[str] | None = None,
    exam_tutor_arr_hard: list[str] | None = None,
) -> None:
    if not all([get_character_data, start_mission, update_character_progress, pick_auto_mission, mission_display_label, account_type_from_login, get_rank, get_control, is_success_response_dict, select_special_jounin_class, run_rank_exam_hard]):
        raise ValueError("Android NinjaSaga leveling core requires complete callbacks")

    anti_profile = anti_detection.build_anti_detection_profile(runtime_settings)
    action_delay_seconds = int(anti_profile.get("action_delay_seconds", action_delay_seconds))
    cycle_cooldown_seconds = int(anti_profile.get("cycle_cooldown_seconds", cycle_cooldown_seconds))
    rest_every_cycles = int(anti_profile.get("rest_every_cycles", 40))
    rest_duration_seconds = int(anti_profile.get("rest_duration_seconds", 60))
    auto_mission = str(mission_id or "").strip().lower() in {"", "auto"}
    account_type = account_type_from_login()
    cycle = 0
    failure_timestamps: list[float] = []
    cloudflare_backoff_index = 0
    exam_chunin_arr = list(exam_chunin_arr or [])
    exam_jounin_arr = list(exam_jounin_arr or [])
    exam_special_jounin_arr_hard = list(exam_special_jounin_arr_hard or [])
    exam_tutor_arr_hard = list(exam_tutor_arr_hard or [])

    while not rate_control.stop_requested(stop_event):
        cycle += 1
        try:
            gate_char = get_character_data(char_id)
            gate_level = progress_parser.extract_character_level(gate_char, default=1)
            gate_rank = get_rank(gate_char)

            if gate_level >= genin_level_cap and gate_rank < rank_chunin:
                if log:
                    log(
                        f"[Cycle {cycle}] Level cap gate detected (Lv {gate_level}, rank {gate_rank}). Running Chunin exam...",
                        "warning",
                    )
                ok = run_rank_exam_hard(
                    stop_event=stop_event,
                    char_id=char_id,
                    exam_name="Chunin",
                    exam_missions=exam_chunin_arr,
                    cycle_cooldown_seconds=cycle_cooldown_seconds,
                    log=log,
                )
                if not ok:
                    return
                refreshed = get_character_data(char_id)
                refreshed_rank = get_rank(refreshed)
                if refreshed_rank < rank_chunin:
                    if log:
                        log("[Exam] Chunin exam finished but rank not promoted yet. Please relog in game once, then continue.", "warning")
                    return
                if log:
                    log("[Exam] Chunin exam success. Continue leveling.", "success")
                continue

            if gate_level >= chunin_level_cap and gate_rank < rank_jounin:
                if log:
                    log(
                        f"[Cycle {cycle}] Level cap gate detected (Lv {gate_level}, rank {gate_rank}). Running Jounin exam...",
                        "warning",
                    )
                ok = run_rank_exam_hard(
                    stop_event=stop_event,
                    char_id=char_id,
                    exam_name="Jounin",
                    exam_missions=exam_jounin_arr,
                    cycle_cooldown_seconds=cycle_cooldown_seconds,
                    log=log,
                )
                if not ok:
                    return
                refreshed = get_character_data(char_id)
                refreshed_rank = get_rank(refreshed)
                if refreshed_rank < rank_jounin:
                    if log:
                        log("[Exam] Jounin exam finished but rank not promoted yet. Please relog in game once, then continue.", "warning")
                    return
                if log:
                    log("[Exam] Jounin exam success. Continue leveling.", "success")
                continue

            if gate_level >= jounin_level_cap and gate_rank < rank_special_jounin:
                if log:
                    log(
                        f"[Cycle {cycle}] Level cap gate detected (Lv {gate_level}, rank {gate_rank}). Running Special Jounin exam (hard)...",
                        "warning",
                    )
                ok = run_rank_exam_hard(
                    stop_event=stop_event,
                    char_id=char_id,
                    exam_name="Special Jounin",
                    exam_missions=exam_special_jounin_arr_hard,
                    cycle_cooldown_seconds=cycle_cooldown_seconds,
                    log=log,
                )
                if not ok:
                    return
                refreshed = get_character_data(char_id)
                refreshed_rank = get_rank(refreshed)
                if refreshed_rank < rank_special_jounin:
                    if log:
                        log("[Exam] Special Jounin exam finished but rank not promoted yet. Please relog in game once, then continue.", "warning")
                    return
                class_index = int(runtime_settings.get("special_jounin_class_index", 3))
                class_res = select_special_jounin_class(class_index)
                if is_success_response_dict(class_res):
                    if log:
                        log(f"[Exam] Special Jounin class selected (class {class_index})", "success")
                else:
                    if log:
                        log(f"[Exam] Special Jounin class select failed: {class_res}", "warning")
                continue

            if gate_level >= special_jounin_level_cap and gate_rank < rank_tutor:
                if log:
                    log(
                        f"[Cycle {cycle}] Level cap gate detected (Lv {gate_level}, rank {gate_rank}). Running Tutor exam (hard)...",
                        "warning",
                    )
                ok = run_rank_exam_hard(
                    stop_event=stop_event,
                    char_id=char_id,
                    exam_name="Tutor",
                    exam_missions=exam_tutor_arr_hard,
                    cycle_cooldown_seconds=cycle_cooldown_seconds,
                    log=log,
                )
                if not ok:
                    return
                refreshed = get_character_data(char_id)
                refreshed_rank = get_rank(refreshed)
                if refreshed_rank < rank_tutor:
                    if log:
                        log("[Exam] Tutor exam finished but rank not promoted yet. Please relog in game once, then continue.", "warning")
                    return
                if log:
                    log("[Exam] Tutor exam success. Continue leveling.", "success")
                continue

            selected_mission_id = pick_auto_mission(gate_level, account_type=account_type) if auto_mission else str(mission_id or "msn2").strip().lower()
            if log:
                log(f"[Cycle {cycle}] start mission {mission_display_label(selected_mission_id)}", "info")

            start_attempts = max(1, int(anti_profile.get("start_max_retries", 3)))
            start_result: Any = None
            active_mission_id = selected_mission_id
            for attempt in range(1, start_attempts + 1):
                start_result = start_mission(active_mission_id)
                if is_success_response_dict(start_result):
                    break
                error_code = str((start_result or {}).get("status") or (start_result or {}).get("error") or "")
                if auto_mission and error_code == "102":
                    fallback_level = max(1, gate_level - attempt)
                    fallback_mission = pick_auto_mission(fallback_level, account_type=account_type)
                    if fallback_mission != active_mission_id:
                        if log:
                            log(
                                f"[Cycle {cycle}] mission {mission_display_label(active_mission_id)} level-gated, fallback to {mission_display_label(fallback_mission)}",
                                "warning",
                            )
                        active_mission_id = fallback_mission
                        continue
                if attempt < start_attempts:
                    retry_wait = max(1, int(anti_profile.get("start_retry_delay_seconds", 6)))
                    if log:
                        log(f"[Cycle {cycle}] startMission failed, retry {attempt}/{start_attempts} in {retry_wait}s...", "warning")
                    if not rate_control.wait_with_stop(stop_event, retry_wait):
                        return
            selected_mission_id = active_mission_id

            if isinstance(start_result, dict) and str(start_result.get("status")) not in ("1", "True", "true"):
                err = start_result.get("error") or start_result
                if log:
                    log(f"[Cycle {cycle}] startMission failed: {err}", "warning")
                if not anti_detection.register_failure_and_maybe_circuit(stop_event, failure_timestamps, anti_profile, cycle, log):
                    return
                if not rate_control.wait_with_stop(stop_event, max(1, cycle_cooldown_seconds)):
                    return
                continue

            failure_timestamps.clear()
            cloudflare_backoff_index = 0
            wait_seconds = rate_control.jittered_wait_seconds(
                action_delay_seconds,
                anti_profile.get("action_jitter_seconds", 0),
            )
            if not rate_control.wait_with_stop(stop_event, wait_seconds):
                return

            char = get_character_data(char_id)
            _, char_level, _, _, _, _ = progress_parser.extract_progress_snapshot(char, default_level=gate_level)
            update_character_progress(char_id, char_level, selected_mission_id, xp_gain=xp_gain, gold_gain=gold_gain)
            if not rate_control.wait_with_stop(stop_event, 1):
                return

            updated = get_character_data(char_id)
            name, level, xp, gold, rank, _ = progress_parser.extract_progress_snapshot(
                updated,
                default_level=max(1, char_level),
                default_rank=get_rank(updated),
            )
            rank = get_rank(updated)
            control = get_control(updated)

            if rank >= rank_special_jounin and control == 0 and not rate_control.stop_requested(stop_event):
                class_index = int(runtime_settings.get("special_jounin_class_index", 3))
                class_skill_map = {
                    1: "skill2002",
                    2: "skill2004",
                    3: "skill2001",
                    4: "skill2003",
                    5: "skill2000",
                }
                class_skill = class_skill_map.get(class_index, "skill2002")
                if log:
                    log(
                        f"[Cycle {cycle}] rank Special Jounin detected with empty class. Selecting class {class_index} ({class_skill})...",
                        "info",
                    )
                class_res = select_special_jounin_class(class_index)
                if is_success_response_dict(class_res):
                    if log:
                        log(f"[Cycle {cycle}] Special Jounin class selected ({class_skill})", "success")
                else:
                    if log:
                        log(f"[Cycle {cycle}] Special Jounin class select failed: {class_res}", "warning")

            if on_update:
                on_update({"level": level, "xp": xp, "gold": gold})
            if log:
                log(f"[Cycle {cycle}] ok -> {name} Lv {level} XP {xp} Gold {gold}", "success")
        except Exception as exc:
            cloudflare_wait, cloudflare_backoff_index = anti_detection.next_cloudflare_wait(
                anti_profile,
                cloudflare_backoff_index,
            )
            recovered = recovery.handle_runtime_exception(
                stop_event=stop_event,
                exc=exc,
                char_id=char_id,
                context=f"[Cycle {cycle}] leveling",
                cloudflare_rest_seconds=cloudflare_wait,
                relogin_and_reselect_character=runtime_relogin_and_reselect_character,
                log=log,
            )
            if not recovered:
                return
            if not anti_detection.register_failure_and_maybe_circuit(stop_event, failure_timestamps, anti_profile, cycle, log):
                return
        finally:
            cooldown = max(1, cycle_cooldown_seconds)
            if not rate_control.wait_with_stop(stop_event, cooldown):
                return
            if rest_every_cycles > 0 and cycle % rest_every_cycles == 0 and not rate_control.stop_requested(stop_event):
                if log:
                    log(f"[Cycle {cycle}] anti-detection rest {rest_duration_seconds}s", "info")
                if not rate_control.wait_with_stop(stop_event, max(1, rest_duration_seconds)):
                    return
