import hashlib
import json
import random
import string
import time
from typing import Any, Optional

import requests

from .. import config
from .utils import flatten_json, open_json_to_dict, save_fight_data

CREW_BATTLE_STAMINA_COST = 10
CREW_BATTLE_IDLE_SECONDS = 30 * 60
CREW_BATTLE_POLL_SECONDS = 5
CREW_BATTLE_MIN_STAMINA_REFRESH = 10
CREW_BATTLE_BETWEEN_BATTLES_SECONDS = 8
REQUEST_TIMEOUT_SECONDS = 20


def _load_crew_game_data() -> dict[str, Any]:
    data = open_json_to_dict("../data/gamedata.json")
    if not isinstance(data, list):
        return {}
    for entry in data:
        if isinstance(entry, dict) and entry.get("id") == "crew":
            return entry.get("data") or {}
    return {}


CREW_GAME_DATA = _load_crew_game_data()
CREW_BOSSES = CREW_GAME_DATA.get("boss") or []
CREW_CASTLE_NAMES = CREW_GAME_DATA.get("castle") or []


class CrewBattleEvent:
    def __init__(self) -> None:
        if not isinstance(config.char_data, dict):
            raise ValueError("Character data is not loaded in memory")
        if not isinstance(config.login_data, dict):
            raise ValueError("Login data is not loaded in memory")

        self.char_data = config.char_data
        self.login_data = config.login_data
        self.char_flat = flatten_json(self.char_data)
        self.char_id = (
            self.char_flat.get("character_data_character_id")
            or self.char_flat.get("character_id")
        )
        if not self.char_id:
            raise ValueError("Character ID is missing from current character data")

        self.session_key = self.login_data.get("sessionkey")
        if not self.session_key:
            raise ValueError("Session key is missing from login data")

        self.current_profile = config.get_current_amf_profile()
        self.base_url = self.current_profile.get("crew_url")
        if not self.base_url:
            raise ValueError(f"Crew Battle is not available for {self.current_profile['label']}")

        self.http = requests.Session()
        self.http.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Agent": f"NinjaSage {config.BUILD_NUM}",
            }
        )

        self.crew_data: dict[str, Any] = {}
        self.crew_char_data: dict[str, Any] = {}
        self.phase: int = 0
        self._last_stamina: Optional[int] = None
        self._last_stamina_fetch_at: float = 0.0
        self._last_logged_stamina: Optional[tuple[Any, Any]] = None

    @staticmethod
    def _check_stop_event() -> bool:
        if hasattr(config, "stop_event") and config.stop_event.is_set():
            print("Crew battle stopped by user request")
            return True
        return False

    def _wait_with_stop_check(self, seconds: int) -> bool:
        for _ in range(max(0, int(seconds))):
            if self._check_stop_event():
                return False
            time.sleep(1)
        return True

    @staticmethod
    def _response_message(response: Any) -> str:
        if response is None:
            return "No response"
        if isinstance(response, dict):
            for key in ("errorMessage", "message", "error", "detail", "result"):
                value = response.get(key)
                if value:
                    return str(value)
            return str(response)
        return str(response)

    @staticmethod
    def _extract_token(payload: Any) -> Optional[str]:
        if isinstance(payload, dict):
            for key in ("token", "access_token", "accessToken", "bearer", "jwt"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            for value in payload.values():
                token = CrewBattleEvent._extract_token(value)
                if token:
                    return token
        elif isinstance(payload, list):
            for item in payload:
                token = CrewBattleEvent._extract_token(item)
                if token:
                    return token
        return None

    def _post_json(self, path: str, payload: Optional[dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        response = self.http.post(url, json=payload or {}, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def _post_json_with_reauth(self, path: str, payload: Optional[dict[str, Any]] = None) -> Any:
        response = self._post_json(path, payload)
        if self._is_auth_error(response):
            print("Crew session expired, re-authenticating...")
            if not self.authenticate():
                return response
            response = self._post_json(path, payload)
        return response

    @staticmethod
    def _is_auth_error(response: Any) -> bool:
        if not isinstance(response, dict):
            return False
        status_code = response.get("statusCode")
        if status_code in (401, 403):
            return True
        message = str(
            response.get("errorMessage")
            or response.get("message")
            or response.get("error")
            or ""
        ).lower()
        return any(
            marker in message
            for marker in ("unauthorized", "token", "auth", "forbidden", "expired")
        )

    @staticmethod
    def _generate_code(length: int = 24) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choice(alphabet) for _ in range(length))

    def _phase2_signature(self, battle_code: str, timestamp: int, castle_id: Any) -> str:
        raw = "|".join([str(self.char_id), str(battle_code), str(timestamp), str(castle_id)])
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def authenticate(self) -> bool:
        print("Authenticating crew battle session...")
        try:
            response = self._post_json(
                "/auth/login",
                {
                    "char_id": self.char_id,
                    "session_key": self.session_key,
                },
            )
        except Exception as exc:
            print(f"Failed to authenticate crew battle session: {exc}")
            return False

        token = self._extract_token(response)
        if not token:
            print(f"Crew battle auth failed: {self._response_message(response)}")
            return False

        self.http.headers["Authorization"] = f"Bearer {token}"
        print("Crew battle session authenticated")
        return True

    def get_crew_info(self) -> Optional[dict[str, Any]]:
        try:
            response = self._post_json_with_reauth("/player/crew")
        except Exception as exc:
            print(f"Failed to get crew data: {exc}")
            return None

        if isinstance(response, dict) and "crew" in response and "char" in response:
            self.crew_data = response.get("crew") or {}
            self.crew_char_data = response.get("char") or {}
            return response

        if isinstance(response, dict) and response.get("statusCode") == 404:
            print("Character is not in a crew")
            return None

        print(f"Failed to get crew data: {self._response_message(response)}")
        return None

    def get_stamina(self, announce: bool = True) -> Optional[int]:
        now = time.time()
        if (
            self._last_stamina is not None
            and (now - self._last_stamina_fetch_at) < CREW_BATTLE_MIN_STAMINA_REFRESH
        ):
            stamina = self._last_stamina
            max_stamina = self.crew_char_data.get("max_stamina", 0)
            pair = (stamina, max_stamina)
            if announce and pair != self._last_logged_stamina:
                print(f"Crew stamina: {stamina} / {max_stamina}")
                self._last_logged_stamina = pair
            return stamina

        try:
            response = self._post_json_with_reauth("/player/stamina")
        except Exception as exc:
            print(f"Failed to refresh crew stamina: {exc}")
            return None

        if not isinstance(response, dict) or "char" not in response:
            print(f"Failed to refresh crew stamina: {self._response_message(response)}")
            return None

        self.crew_char_data = response.get("char") or {}
        season = response.get("season") or {}
        try:
            self.phase = int(season.get("phase", self.phase or 0) or 0)
        except Exception:
            pass
        stamina = int(self.crew_char_data.get("stamina", 0) or 0)
        self._last_stamina = stamina
        self._last_stamina_fetch_at = time.time()
        max_stamina = self.crew_char_data.get("max_stamina", 0)
        pair = (stamina, max_stamina)
        if announce and pair != self._last_logged_stamina:
            print(f"Crew stamina: {stamina} / {max_stamina} | Phase {self.phase or '?'}")
            self._last_logged_stamina = pair
        return stamina

    def get_castles(self) -> list[dict[str, Any]]:
        try:
            response = self._post_json_with_reauth("/battle/castles/")
        except Exception as exc:
            print(f"Failed to get crew castles: {exc}")
            return []

        if isinstance(response, dict) and isinstance(response.get("castles"), list):
            return response["castles"]

        print(f"Failed to get crew castles: {self._response_message(response)}")
        return []

    def pick_phase2_castle(self) -> Optional[dict[str, Any]]:
        own_crew_id = self.crew_data.get("id")
        castles = self.get_castles()
        for castle in castles:
            if castle.get("owner_id") != own_crew_id:
                return castle
        return None

    def start_phase2_battle(self, castle: dict[str, Any]) -> Any:
        battle_code = self._generate_code(24)
        timestamp = int(time.time())
        castle_id = castle.get("id")
        payload = {
            "c": castle_id,
            "b": battle_code,
            "t": timestamp,
            "h": self._phase2_signature(battle_code, timestamp, castle_id),
        }
        return self._post_json_with_reauth("/battle/phase2/start", payload)

    def _log_phase2_result(self, castle: dict[str, Any], result: dict[str, Any]) -> None:
        castle_name = castle.get("name") or "Unknown Castle"
        defender_name = result.get("l") or castle.get("owner_name") or "Unknown Crew"
        winner_name = result.get("w") or self.crew_data.get("name") or "Unknown Crew"
        damage = result.get("d", "n/a")
        merit = result.get("m", "n/a")
        stamina = result.get("s", self.crew_char_data.get("stamina", "n/a"))
        print(
            f"Crew battle result at {castle_name}: "
            f"winner={winner_name}, defender={defender_name}, "
            f"damage={damage}, merit={merit}, stamina={stamina}"
        )

    def _idle_until_stamina_returns(self) -> bool:
        print("Crew stamina is below 10. Idling for 30 minutes while checking every 5 seconds...")
        end_time = time.time() + CREW_BATTLE_IDLE_SECONDS
        while time.time() < end_time:
            if self._check_stop_event():
                return False
            stamina = self.get_stamina(announce=True)
            if stamina is not None and stamina >= CREW_BATTLE_STAMINA_COST:
                print("Crew stamina is ready again, resuming battles")
                return True
            if not self._wait_with_stop_check(CREW_BATTLE_POLL_SECONDS):
                return False
        return True

    def run(self) -> None:
        if self._check_stop_event():
            return
        if not self.authenticate():
            return
        if not self.get_crew_info():
            return

        crew_name = self.crew_data.get("name", "Unknown Crew")
        print(f"Crew battle ready for crew: {crew_name}")

        while not self._check_stop_event():
            stamina = self.get_stamina(announce=True)
            if stamina is None:
                print("Unable to read crew stamina, retrying in 5 seconds...")
                if not self._wait_with_stop_check(CREW_BATTLE_POLL_SECONDS):
                    return
                continue

            if self.phase == 1:
                print("Crew Battle phase 1 is not automated yet in desktop panel. Waiting for phase 2.")
                return

            if stamina < CREW_BATTLE_STAMINA_COST:
                if not self._idle_until_stamina_returns():
                    return
                continue

            castle = self.pick_phase2_castle()
            if not castle:
                print("No crew battle castle target available right now, retrying in 30 seconds...")
                if not self._wait_with_stop_check(30):
                    return
                continue

            castle_name = castle.get("name") or castle.get("owner_name") or "Unknown Castle"
            owner_name = castle.get("owner_name", "Unknown Crew")
            print(f"Attacking castle: {castle_name} | Owner: {owner_name}")

            try:
                result = self.start_phase2_battle(castle)
            except Exception as exc:
                print(f"Crew battle failed: {exc}")
                if not self._wait_with_stop_check(CREW_BATTLE_POLL_SECONDS):
                    return
                continue

            save_fight_data(result)
            if isinstance(result, dict) and "b" in result:
                if "s" in result:
                    self.crew_char_data["stamina"] = result["s"]
                    self._last_stamina = int(result["s"] or 0)
                    self._last_stamina_fetch_at = time.time()
                self._log_phase2_result(castle, result)
            else:
                print(f"Crew battle failed: {self._response_message(result)}")
                if self._is_auth_error(result):
                    if not self.authenticate():
                        return

            if not self._wait_with_stop_check(CREW_BATTLE_BETWEEN_BATTLES_SECONDS):
                return


def crew_battle_event() -> None:
    try:
        event = CrewBattleEvent()
    except ValueError as exc:
        print(str(exc))
        return
    event.run()
