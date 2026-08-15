PANEL_BUILD_NUM = "V420.69"

BASE_GAMES = {
    "sage": {
        "label": "Ninja Sage",
        "panel_title": "Ninja Sage",
        "panel_subtitle": "Web Panel",
        "server_selection_note": "Panel will only follow Ninja Sage for the event! Error on other server will ignored!",
        "has_tokens": True,
        "has_account_stats": False,
        "library_url": None,
        "bootstrap_url": None,
        "bootstrap_game": None,
        "default_profile_id": "official",
    },
    "ninjasaga": {
        "label": "Ninja Saga",
        "panel_title": "Ninja Saga",
        "panel_subtitle": "Web Panel",
        "server_selection_note": "NinjaSaga uses separate client-side signature/encryption flow and is isolated from other games.",
        "has_tokens": True,
        "has_account_stats": False,
        "library_url": None,
        "bootstrap_url": None,
        "bootstrap_game": None,
        "default_profile_id": "official",
        "build_num": "latest",
    },
    "zenshin": {
        "label": "Ninja Zenshin",
        "panel_title": "Ninja Zenshin",
        "panel_subtitle": "Experimental Web Panel",
        "server_selection_note": "Experimental desktop-only adapter. Login uses the Zenshin website flow, or paste a full /game/frame URL for debugging.",
        "has_tokens": True,
        "has_account_stats": False,
        "library_url": None,
        "bootstrap_url": "https://ninjazenshin.online/game",
        "bootstrap_game": "zenshin",
        "default_profile_id": "official",
        "build_num": "1.0.2",
    },
    "rift": {
        "label": "Ninja Rift",
        "panel_title": "Ninja Rift",
        "panel_subtitle": "Web Panel",
        "server_selection_note": "Choose the Ninja Rift server first, then continue to login.",
        "has_tokens": True,
        "has_account_stats": False,
        "library_url": "https://ninjarift.org/library/",
        "bootstrap_url": None,
        "bootstrap_game": None,
        "default_profile_id": "official",
        "build_num": "Public 2.40"
    },
    "shinobi": {
        "label": "Shinobi Warfare",
        "panel_title": "Shinobi Warfare",
        "panel_subtitle": "Web Panel",
        "server_selection_note": "Choose the Shinobi Warfare server first, then continue to login.",
        "has_tokens": False,
        "has_account_stats": True,
        "library_url": None,
        "bootstrap_url": None,
        "bootstrap_game": None,
        "default_profile_id": "official",
        "build_num": "1.070",
    },

}

SAGE_AMF_PROFILES = {
    "official": {
        "label": "Ninja Sage ID",
        "gateway": "https://play.ninjasage.id/amf",
        "build_num": "Public 0.59",
        "clan_url": "https://clan.ninjasage.id",
        "crew_url": None,
        "crew_url": "https://crew.ninjasage.id",
    },
    "alternate5": {
        "label": "Ninja Eskrim",
        # Update this profile with your other responder/build when needed.
        "gateway": "https://ninjaeskrim.web.id/amf",
        "build_num": "Public 0.59",
        "clan_url": None,
        "crew_url": None,
    },
    "alternate": {
        "label": "Ninja ID",
        # Update this profile with your other responder/build when needed.
        "gateway": "https://ninja-id.com/amf",
        "build_num": "Skip Check",
        "clan_url": "https://ninja-id.com/clan",
        "crew_url": None,
    },
    "alternate2": {
        "label": "Ninja Jolay",
        # Update this profile with your other responder/build when needed.
        "gateway": "https://game.ninjajolay.id/amf",
        "build_num": "Public 0.59",
        "clan_url": None,
        "crew_url": None,
    },

    "alternate6": {
        "label": "Ninja Extreme",
        "gateway": "https://kotagames.web.id/amf",
        "build_num": "Public 0.59",
        "clan_url": None,
        "crew_url": None,
    },
    "alternate3": {
        "label": "Fun Private Server Ninja Sage",
        # Update this profile with your other responder/build when needed.
        "gateway": "https://ninjasage.example.com/amf",
        "build_num": "Public 0.59",
        "clan_url": None,
        "crew_url": None,
    },
    "alternate4": {
        "label": "Classic Ninja",
        "gateway": "https://play.classicninja.cc/amf",
        "build_num": "V27",
        "clan_url": "https://play.classicninja.cc/clan",
        "crew_url": None,
    },
}

RIFT_AMF_PROFILES = {
    "official": {
        "label": "Ninja Rift Official",
        "gateway": "https://ninjarift.org/amf_nl/",
        "build_num": "Public 2.40",
        "clan_url": None,
    },
}

SHINOBI_PROFILES = {
    "official": {
        "label": "Shinobi Warfare Official",
        "gateway": "https://prod.shinobiwarfare.com/json/",
        "build_num": "1.070",
        "clan_url": None,
    },
}

NINJASAGA_PROFILES = {
    "official": {
        "label": "NinjaSaga.cc",
        "gateway": "https://amf.ninjasaga.cc/",
        "build_num": "latest",
        "clan_url": "https://ninjasaga.cc/",
    },
}

ZENSHIN_PROFILES = {
    "official": {
        "label": "Ninja Zenshin",
        "gateway": "https://amf.ninjazenshin.online/",
        "build_num": "1.0.2",
        "clan_url": None,
    },
}

NINJASAGA_ANTI_DETECTION_PROFILE = {
    "action_delay_seconds": 10,
    "cycle_cooldown_seconds": 5,
    "rest_every_cycles": 40,
    "rest_duration_seconds": 60,
    "action_jitter_seconds": 2,
    "min_call_delay_seconds": 4,
    "start_retry_delay_seconds": 6,
    "start_max_retries": 3,
    "cloudflare_rest_seconds": 60,
    "cloudflare_backoff_steps_seconds": [60, 120, 240],
    "cloudflare_backoff_max_seconds": 300,
    "failure_window_seconds": 180,
    "max_failures_in_window": 6,
    "circuit_cooldown_seconds": 120,
}

NINJASAGA_AUTO_SPEND_PROFILE = {
    "enabled": False,
    "target": "energy",
    "trigger_energy": 0,
    "max_refills_per_run": 1,
}

NINJASAGA_EVENT_RESOURCE_POLICY = {
    "mode": "wait",
    "wait_minutes": 30,
}

NINJASAGA_EVENT_TIMING = {
    "sakura_battle_delay_seconds": 20,
}

SAGE_GLOBAL_SETTINGS = {
    "leveling_delay_seconds": 10,
    "leveling_cycle_cooldown_seconds": 5,
    "leveling_rest_every_cycles": 40,
    "leveling_rest_duration_seconds": 60,
    "leveling_action_jitter_seconds": 2,
    "leveling_min_call_delay_seconds": 4,
    "leveling_start_retry_delay_seconds": 6,
    "leveling_start_max_retries": 3,
    "leveling_failure_window_seconds": 180,
    "leveling_max_failures_in_window": 6,
    "leveling_circuit_cooldown_seconds": 120,
    "sage_exam_start_delay_seconds": 8,
    "sage_exam_finish_delay_seconds": 5,
    "sage_battle_wait_seconds": 5,
    "sage_post_finish_delay_seconds": 0,
    "sage_auto_relogin_wait_seconds": 20,
    "sage_infinite_loop_rest_every_cycles": 50,
    "sage_infinite_loop_rest_duration_seconds": 10,
    "sage_limited_loop_rest_every_cycles": 15,
    "sage_limited_loop_rest_duration_seconds": 10,
    "sage_special_jounin_class_skill": "skill_4001",
    "sage_event_empty_resource_mode": "wait",
    "sage_event_wait_minutes": 30,
    "sage_aniv_event_empty_resource_mode": "wait",
    "sage_aniv_event_wait_minutes": 30,
    "sage_sakura_event_empty_resource_mode": "wait",
    "sage_sakura_event_wait_minutes": 30,
    "sage_easter_event_empty_resource_mode": "wait",
    "sage_easter_event_wait_minutes": 30,
    "sage_shadow_war_empty_resource_mode": "wait",
    "sage_shadow_war_wait_minutes": 30,
    "clan_war_auto_spend_token": False,
    "clan_war_stamina_refill_source": "auto",
    "clan_war_battle_delay_seconds": 8,
    "clan_war_buy_stamina_delay_seconds": 3,
}

SAGE_PROFILE_LOCKED_SETTINGS = {
    "alternate5": {
        "leveling_delay_seconds": 10,
        "sage_exam_start_delay_seconds": 30,
        "sage_exam_finish_delay_seconds": 30,
    },
}

RIFT_SETTINGS = {
    "rift_min_call_delay_seconds": 2,
    "rift_loop_delay_seconds": 1,
    "rift_auto_relogin_wait_seconds": 15,
    "rift_infinite_loop_rest_every_cycles": 40,
    "rift_infinite_loop_rest_duration_seconds": 30,
    "rift_limited_loop_rest_every_cycles": 15,
    "rift_limited_loop_rest_duration_seconds": 15,
    "rift_mission_battle_wait_base_seconds": 20,
    "rift_mission_battle_wait_random_seconds": 20,
    "rift_event_battle_wait_base_seconds": 20,
    "rift_event_battle_wait_random_seconds": 20,
    "rift_eudemon_battle_wait_base_seconds": 20,
    "rift_eudemon_battle_wait_random_seconds": 5,
    "rift_eudemon_between_battles_delay_seconds": 5,
    "rift_hunting_house_battle_wait_base_seconds": 20,
    "rift_hunting_house_battle_wait_random_seconds": 5,
    "rift_hunting_house_between_battles_delay_seconds": 5,
    "rift_exam_wait_min_seconds": 45,
    "rift_exam_wait_max_seconds": 120,
    "rift_exam_stage_gap_seconds": 3,
    "rift_special_jounin_class_skill": "skill_2002",
    "rift_event_empty_resource_mode": "wait",
    "rift_event_wait_minutes": 30,
    "rift_hanami_event_empty_resource_mode": "wait",
    "rift_hanami_event_wait_minutes": 30,
    "rift_easter_event_empty_resource_mode": "wait",
    "rift_easter_event_wait_minutes": 30,
}

SHINOBI_SETTINGS = {
    "debug_http": True,
    "battle_finish_delay_seconds": 6,
    "between_missions_delay_seconds": 1,
    "request_delay_seconds": 0,
    "timeout_seconds": 20,
    "action_mode": "skills",
    "recruit_mode": "keep_existing",
    "use_simulated_battle": True,
    "complete_payload_mode": "full",
}

RIFT_SPECIAL_JOUNIN_SKILL_OPTIONS = [
    {"id": "skill_2002", "label": "Intelligence Class"},
    {"id": "skill_2004", "label": "Surprise Attack Class"},
    {"id": "skill_2001", "label": "Sensor Class"},
    {"id": "skill_2003", "label": "Heavy Attack Class"},
    {"id": "skill_2000", "label": "Medical Class"},
]

GAME_PROFILES = {
    "sage": SAGE_AMF_PROFILES,
    "rift": RIFT_AMF_PROFILES,
    "shinobi": SHINOBI_PROFILES,
    "ninjasaga": NINJASAGA_PROFILES,
    "zenshin": ZENSHIN_PROFILES,
}

ACTIVE_BASE_GAME = "sage"
ACTIVE_AMF_PROFILE = BASE_GAMES[ACTIVE_BASE_GAME]["default_profile_id"]
GATEWAY = GAME_PROFILES[ACTIVE_BASE_GAME][ACTIVE_AMF_PROFILE]["gateway"]
BUILD_NUM = GAME_PROFILES[ACTIVE_BASE_GAME][ACTIVE_AMF_PROFILE]["build_num"]
BYTES_LOADED = 8228447
BYTES_TOTAL = 8228447
CLASSIC_REQUEST_SEQ = 0


def get_base_games():
    return [
        {
            "id": game_id,
            "label": game["label"],
            "panel_title": game.get("panel_title", game["label"]),
            "panel_subtitle": game.get("panel_subtitle", "Web Panel"),
            "server_selection_note": game.get("server_selection_note", ""),
            "has_tokens": bool(game.get("has_tokens")),
            "has_account_stats": bool(game.get("has_account_stats")),
        }
        for game_id, game in BASE_GAMES.items()
    ]


def get_current_base_game() -> dict:
    game = BASE_GAMES[ACTIVE_BASE_GAME]
    return {
        "id": ACTIVE_BASE_GAME,
        "label": game["label"],
        "panel_title": game.get("panel_title", game["label"]),
        "panel_subtitle": game.get("panel_subtitle", "Web Panel"),
        "server_selection_note": game.get("server_selection_note", ""),
        "has_tokens": bool(game.get("has_tokens")),
        "has_account_stats": bool(game.get("has_account_stats")),
        "library_url": game.get("library_url"),
        "bootstrap_url": game.get("bootstrap_url"),
    }


def _profiles_for_base_game(base_game_id: str | None = None):
    resolved_base_game = base_game_id or ACTIVE_BASE_GAME
    if resolved_base_game not in GAME_PROFILES:
        raise ValueError(f"Unknown base game: {resolved_base_game}")
    return GAME_PROFILES[resolved_base_game]


def _sync_runtime_connection():
    global GATEWAY, BUILD_NUM
    profile = _profiles_for_base_game()[ACTIVE_AMF_PROFILE]
    GATEWAY = profile["gateway"]
    BUILD_NUM = profile["build_num"]


def set_base_game(base_game_id: str) -> dict:
    global ACTIVE_BASE_GAME, ACTIVE_AMF_PROFILE, CLASSIC_REQUEST_SEQ

    if base_game_id not in BASE_GAMES:
        raise ValueError(f"Unknown base game: {base_game_id}")

    ACTIVE_BASE_GAME = base_game_id
    ACTIVE_AMF_PROFILE = BASE_GAMES[base_game_id]["default_profile_id"]
    CLASSIC_REQUEST_SEQ = 0
    _sync_runtime_connection()
    return get_current_base_game()


def set_runtime_connection(gateway: str | None = None, build_num: str | None = None):
    global GATEWAY, BUILD_NUM
    if gateway:
        GATEWAY = gateway
    if build_num:
        BUILD_NUM = build_num


def _default_quick_login_store():
    return {
        "last_profile_id": None,
        "profiles": {},
    }


def get_amf_profiles():
    profiles = _profiles_for_base_game()
    return [
        {
            "id": profile_id,
            "label": profile["label"],
            "gateway": profile["gateway"],
            "build_num": profile["build_num"],
            "clan_url": profile.get("clan_url"),
        }
        for profile_id, profile in profiles.items()
    ]


def set_amf_profile(profile_id: str) -> dict:
    global ACTIVE_AMF_PROFILE, CLASSIC_REQUEST_SEQ

    profiles = _profiles_for_base_game()
    if profile_id not in profiles:
        raise ValueError(f"Unknown AMF profile: {profile_id}")

    ACTIVE_AMF_PROFILE = profile_id
    CLASSIC_REQUEST_SEQ = 0
    _sync_runtime_connection()
    return get_current_amf_profile()


def get_current_amf_profile() -> dict:
    profile = _profiles_for_base_game()[ACTIVE_AMF_PROFILE]
    return {
        "id": ACTIVE_AMF_PROFILE,
        "base_game_id": ACTIVE_BASE_GAME,
        "label": profile["label"],
        "gateway": profile["gateway"],
        "build_num": profile["build_num"],
        "clan_url": profile.get("clan_url"),
    }


def normalize_quick_login_data(data):
    if not data:
        return _default_quick_login_store()

    if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
        store = _default_quick_login_store()
        store["last_profile_id"] = data.get("last_profile_id")
        store["profiles"] = {
            profile_id: {
                "username": profile_data.get("username"),
                "password": profile_data.get("password"),
                "amf_label": profile_data.get("amf_label"),
            }
            for profile_id, profile_data in data["profiles"].items()
            if isinstance(profile_data, dict)
        }
        if not store["last_profile_id"] and store["profiles"]:
            store["last_profile_id"] = next(iter(store["profiles"]))
        return store

    if isinstance(data, dict) and data.get("username") and data.get("password"):
        current_profile = get_current_amf_profile()
        return {
            "last_profile_id": get_quick_login_storage_key(current_profile["id"], current_profile["base_game_id"]),
            "profiles": {
                get_quick_login_storage_key(current_profile["id"], current_profile["base_game_id"]): {
                    "username": data["username"],
                    "password": data["password"],
                    "amf_label": current_profile["label"],
                }
            },
        }

    return _default_quick_login_store()


def get_quick_login_storage_key(profile_id: str | None = None, base_game_id: str | None = None) -> str:
    resolved_base = base_game_id or ACTIVE_BASE_GAME
    resolved_profile = profile_id or ACTIVE_AMF_PROFILE
    return f"{resolved_base}__{resolved_profile}"


def set_quick_login_credentials(profile_id: str, username: str, password: str, amf_label: str | None = None):
    global quick_login_data

    store = normalize_quick_login_data(quick_login_data)
    profile = _profiles_for_base_game().get(profile_id, {})
    storage_key = get_quick_login_storage_key(profile_id)
    store["profiles"][storage_key] = {
        "username": username,
        "password": password,
        "amf_label": amf_label or profile.get("label") or profile_id,
    }
    store["last_profile_id"] = storage_key
    quick_login_data = store
    return store


def get_quick_login_credentials(profile_id: str | None = None, data=None):
    store = normalize_quick_login_data(quick_login_data if data is None else data)
    requested_storage_key = get_quick_login_storage_key(profile_id)
    credentials = store.get("profiles", {}).get(requested_storage_key)
    if credentials:
        return credentials, requested_storage_key

    fallback_profile_id = profile_id or ACTIVE_AMF_PROFILE
    legacy_credentials = store.get("profiles", {}).get(fallback_profile_id)
    if legacy_credentials:
        return legacy_credentials, fallback_profile_id

    resolved_profile_id = store.get("last_profile_id") or requested_storage_key
    return store.get("profiles", {}).get(resolved_profile_id), resolved_profile_id


weapon_list = None
back_item_list = None
accessory_list = None

all_char = None
char_data = None
game_data = None
rift_bootstrap = None
shinobi_state = None
shinobi_settings_state = None
ninjasaga_state = None
zenshin_state = None
sage_state = None
rift_state = None
login_data = None
quick_login_data = None
character_update_callback = None
session_reauth_required_callback = None
action_log_callback = None
ninjasaga_debug = False


battle_id = None
char_token = None

BATTLE_HASH = "eyJpdGVtcyI6eyJhY2Nlc3NvcnkiOiJhY2Nlc3NvcnlfMDQiLCJiYWNrX2l0ZW0iOiJiYWNrXzIyMDIiLCJ3ZWFwb24iOiJ3cG5fMjIxMyIsInNldCI6InNldF84MzFfMCJ9LCJfX19fIjpbeyJfIjoic2tpbGxfMDQiLCJfXyI6MjMzOTd9LHsiXyI6InNraWxsXzIzMDciLCJfXyI6NTQxMTR9LHsiXyI6InNraWxsXzAzIiwiX18iOjIyOTM0fSx7Il8iOiJza2lsbF82NTMiLCJfXyI6ODE1MTJ9LHsiXyI6InNraWxsXzE5NSIsIl9fIjo2NTczM30seyJfIjoic2tpbGxfMzE0IiwiX18iOjUyNjgxfSx7Il8iOiJza2lsbF8xODciLCJfXyI6NDc1Nzl9LHsiXyI6InNraWxsXzE2NCIsIl9fIjo1NDQ0NH1dLCJzdGF0dXMiOnsiZWFydGgiOjAsImxpZ2h0bmluZyI6MCwiZmlyZSI6MCwid2F0ZXIiOjAsIndpbmQiOjczfSwiYnl0ZXMiOnsiX19fIjoiMTc2Mjg0MzY2NjQwMzY3YzNjYzk5OWE5ZjllOTUxYTFkMzMyMTE1NDViODRiMmQ1YTYzOTMzYjAwMjA0MzMwMDBjM2JiNDEwZmIxNzYyODQzNjY2MTc2Mjg0MzY2NjE3NjI4NDM2NjYxNzYyODQzNjY2IiwiX19fX19fIjo4MjI4NDQ3LCJfIjo4MjI4NDQ3LCJfXyI6ODIyODQ0NywiX19fXyI6MTc2Mjg0MzY2NiwiX19fX18iOjgyMjg0NDd9fQ=="

_METHOD = "CharacterService.updateCharacter"

def set_ninjasaga_debug(enabled: bool) -> bool:
    global ninjasaga_debug
    ninjasaga_debug = bool(enabled)
    return ninjasaga_debug


def get_ninjasaga_debug() -> bool:
    return bool(ninjasaga_debug)


def get_ninjasaga_anti_detection_profile(state: dict | None = None) -> dict:
    merged = dict(NINJASAGA_ANTI_DETECTION_PROFILE)
    runtime_state = state if isinstance(state, dict) else globals().get("ninjasaga_state")
    if not isinstance(runtime_state, dict):
        runtime_state = {}

    state_profile = runtime_state.get("anti_detection_profile")
    if isinstance(state_profile, dict):
        merged.update(state_profile)

    key_map = {
        "leveling_delay_seconds": "action_delay_seconds",
        "leveling_cycle_cooldown_seconds": "cycle_cooldown_seconds",
        "leveling_rest_every_cycles": "rest_every_cycles",
        "leveling_rest_duration_seconds": "rest_duration_seconds",
        "leveling_action_jitter_seconds": "action_jitter_seconds",
        "leveling_min_call_delay_seconds": "min_call_delay_seconds",
        "leveling_start_retry_delay_seconds": "start_retry_delay_seconds",
        "leveling_start_max_retries": "start_max_retries",
        "leveling_cloudflare_rest_seconds": "cloudflare_rest_seconds",
        "leveling_failure_window_seconds": "failure_window_seconds",
        "leveling_max_failures_in_window": "max_failures_in_window",
        "leveling_circuit_cooldown_seconds": "circuit_cooldown_seconds",
    }
    for state_key, profile_key in key_map.items():
        if state_key in runtime_state and runtime_state.get(state_key) is not None:
            merged[profile_key] = runtime_state.get(state_key)

    raw_steps = merged.get("cloudflare_backoff_steps_seconds")
    if isinstance(raw_steps, (list, tuple)):
        cleaned_steps = []
        for value in raw_steps:
            try:
                v = int(value)
            except Exception:
                continue
            if v > 0:
                cleaned_steps.append(v)
        if cleaned_steps:
            merged["cloudflare_backoff_steps_seconds"] = cleaned_steps
        else:
            merged["cloudflare_backoff_steps_seconds"] = list(
                NINJASAGA_ANTI_DETECTION_PROFILE["cloudflare_backoff_steps_seconds"]
            )
    else:
        merged["cloudflare_backoff_steps_seconds"] = list(
            NINJASAGA_ANTI_DETECTION_PROFILE["cloudflare_backoff_steps_seconds"]
        )
    return merged


def get_zenshin_anti_detection_profile(state: dict | None = None) -> dict:
    runtime_state = state if isinstance(state, dict) else globals().get("zenshin_state")
    return get_ninjasaga_anti_detection_profile(runtime_state if isinstance(runtime_state, dict) else {})


def get_ninjasaga_auto_spend_profile(state: dict | None = None) -> dict:
    merged = dict(NINJASAGA_AUTO_SPEND_PROFILE)
    runtime_state = state if isinstance(state, dict) else globals().get("ninjasaga_state")
    if not isinstance(runtime_state, dict):
        runtime_state = {}

    state_profile = runtime_state.get("auto_spend_profile")
    if isinstance(state_profile, dict):
        merged.update(state_profile)

    key_map = {
        "leveling_auto_spend_enabled": "enabled",
        "leveling_auto_spend_target": "target",
        "leveling_auto_spend_trigger_energy": "trigger_energy",
        "leveling_auto_spend_max_refills_per_run": "max_refills_per_run",
    }
    for state_key, profile_key in key_map.items():
        if state_key in runtime_state and runtime_state.get(state_key) is not None:
            merged[profile_key] = runtime_state.get(state_key)

    merged["enabled"] = bool(merged.get("enabled"))
    merged["target"] = str(merged.get("target") or "energy")
    try:
        merged["max_refills_per_run"] = max(0, int(merged.get("max_refills_per_run", 1)))
    except Exception:
        merged["max_refills_per_run"] = 1
    merged["trigger_energy"] = 0
    return merged


def get_zenshin_auto_spend_profile(state: dict | None = None) -> dict:
    runtime_state = state if isinstance(state, dict) else globals().get("zenshin_state")
    return get_ninjasaga_auto_spend_profile(runtime_state if isinstance(runtime_state, dict) else {})


def get_ninjasaga_event_resource_policy(state: dict | None = None) -> dict:
    merged = dict(NINJASAGA_EVENT_RESOURCE_POLICY)
    runtime_state = state if isinstance(state, dict) else globals().get("ninjasaga_state")
    if not isinstance(runtime_state, dict):
        runtime_state = {}

    saved_policy = runtime_state.get("event_resource_policy")
    if isinstance(saved_policy, dict):
        merged.update(saved_policy)

    merged["mode"] = str(merged.get("mode") or "wait").strip().lower()
    if merged["mode"] not in {"buy", "wait", "stop"}:
        merged["mode"] = "wait"
    try:
        merged["wait_minutes"] = max(0, int(merged.get("wait_minutes", 30)))
    except Exception:
        merged["wait_minutes"] = 30
    return merged


def get_zenshin_event_resource_policy(state: dict | None = None) -> dict:
    runtime_state = state if isinstance(state, dict) else globals().get("zenshin_state")
    return get_ninjasaga_event_resource_policy(runtime_state if isinstance(runtime_state, dict) else {})


def get_ninjasaga_event_timing(state: dict | None = None) -> dict:
    merged = dict(NINJASAGA_EVENT_TIMING)
    runtime_state = state if isinstance(state, dict) else globals().get("ninjasaga_state")
    if not isinstance(runtime_state, dict):
        runtime_state = {}

    saved_timing = runtime_state.get("event_timing")
    if isinstance(saved_timing, dict):
        merged.update(saved_timing)

    try:
        merged["sakura_battle_delay_seconds"] = max(
            1,
            int(merged.get("sakura_battle_delay_seconds", 20)),
        )
    except Exception:
        merged["sakura_battle_delay_seconds"] = 20
    return merged


def get_zenshin_event_timing(state: dict | None = None) -> dict:
    runtime_state = state if isinstance(state, dict) else globals().get("zenshin_state")
    return get_ninjasaga_event_timing(runtime_state if isinstance(runtime_state, dict) else {})


def get_sage_global_settings(state: dict | None = None) -> dict:
    merged = dict(SAGE_GLOBAL_SETTINGS)
    runtime_state = state if isinstance(state, dict) else globals().get("sage_state")
    if not isinstance(runtime_state, dict):
        runtime_state = {}

    saved_settings = runtime_state.get("global_settings")
    if isinstance(saved_settings, dict):
        merged.update(saved_settings)
    merged.pop("leveling_cloudflare_rest_seconds", None)
    merged.pop("leveling_cloudflare_backoff_steps_seconds", None)
    profile_id = get_current_amf_profile().get("id")
    locked_settings = SAGE_PROFILE_LOCKED_SETTINGS.get(profile_id)
    if isinstance(locked_settings, dict):
        merged.update(locked_settings)
    return merged


def get_rift_settings(state: dict | None = None) -> dict:
    merged = dict(RIFT_SETTINGS)
    runtime_state = state if isinstance(state, dict) else globals().get("rift_state")
    if not isinstance(runtime_state, dict):
        runtime_state = {}

    saved_settings = runtime_state.get("settings")
    if isinstance(saved_settings, dict):
        merged.update(saved_settings)

    return merged


def get_shinobi_settings(state: dict | None = None) -> dict:
    merged = dict(SHINOBI_SETTINGS)
    runtime_state = state if isinstance(state, dict) else globals().get("shinobi_settings_state")
    if not isinstance(runtime_state, dict):
        runtime_state = {}

    saved_settings = runtime_state.get("settings")
    if isinstance(saved_settings, dict):
        merged.update(saved_settings)

    merged["debug_http"] = bool(merged.get("debug_http"))
    merged["use_simulated_battle"] = bool(merged.get("use_simulated_battle"))
    return merged


def get_rift_special_jounin_skill_options() -> list[dict]:
    return [dict(option) for option in RIFT_SPECIAL_JOUNIN_SKILL_OPTIONS]
