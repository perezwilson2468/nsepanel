from __future__ import annotations

from . import mission_policy, progress_parser, rate_control, recovery


def test_mission_picker_basic() -> None:
    mid_l1 = mission_policy.pick_auto_mission(1, account_type=1)
    assert isinstance(mid_l1, str) and mid_l1.startswith("msn"), "Level 1 should resolve a mission id"

    mid_l20 = mission_policy.pick_auto_mission(20, account_type=1)
    req_l20 = mission_policy.mission_required_level(mid_l20)
    assert req_l20 is None or req_l20 <= 20, "Picked mission must not exceed character level"

    # Ensure auto filters are respected by helper.
    assert not mission_policy.is_mission_auto_eligible("msn125", account_type=1), "Daily mission should be filtered"
    assert not mission_policy.is_mission_auto_eligible("msn66", account_type=1), "No-grade mission should be filtered"
    assert not mission_policy.is_mission_auto_eligible("msn55", account_type=1), "Zero-reward mission should be filtered"


def test_progress_parser_basic() -> None:
    payload = {
        "character_name": "Smoke",
        "character_level": 7,
        "character_xp": 321,
        "character_gold": 654,
        "character_rank": 2,
    }
    name, level, xp, gold, rank, energy = progress_parser.extract_progress_snapshot(
        payload,
        default_level=1,
        default_rank=None,
    )
    assert name == "Smoke"
    assert level == 7
    assert xp == 321
    assert gold == 654
    assert rank == 2
    assert energy is None


def test_recovery_and_rate_helpers() -> None:
    assert recovery.is_gateway_blocked_error(Exception("HTTP 403 cloudflare blocked"))
    assert not recovery.is_gateway_blocked_error(Exception("timeout"))

    ok, ts = rate_control.wait_min_call_interval(
        last_call_at=None,
        min_call_delay_seconds=1,
        action_jitter_seconds=0,
    )
    assert ok and isinstance(ts, float)


def run_all() -> None:
    test_mission_picker_basic()
    test_progress_parser_basic()
    test_recovery_and_rate_helpers()
    print("NinjaSaga smoke tests passed")


if __name__ == "__main__":
    run_all()
