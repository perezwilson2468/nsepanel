import random
import string
import time
from typing import Any, Optional

import requests

from . import config
from .utils import flatten_json, save_fight_data, send_amf_request

CLAN_BATTLE_STAMINA_COST = 10
CLAN_STAMINA_POLL_SECONDS = 5
CLAN_STAMINA_MIN_REQUEST_INTERVAL = 10
CLAN_IDLE_SECONDS = 30 * 60
CLAN_BETWEEN_BATTLES_SECONDS = 8
REQUEST_TIMEOUT_SECONDS = 20
CLAN_WAR_DEFAULT_SETTINGS = {
    "battle_delay_seconds": 8,
    "buy_stamina_delay_seconds": 3,
    "stamina_refill_source": "auto",
}


class ClanWarEvent:
    def __init__(self, *, auto_spend_token: bool = False, settings: Optional[dict[str, Any]] = None):
        if not isinstance(config.char_data, dict):
            raise ValueError("Character data is not loaded in memory")
        if not isinstance(config.login_data, dict):
            raise ValueError("Login data is not loaded in memory")

        self.char_data = config.char_data
        self.login_data = config.login_data
        char_flat = flatten_json(self.char_data)
        self.char_flat = char_flat
        self.char_id = (
            char_flat.get("character_data_character_id")
            or char_flat.get("character_id")
        )
        if not self.char_id:
            raise ValueError("Character ID is missing from current character data")

        self.session_key = self.login_data.get("sessionkey")
        if not self.session_key:
            raise ValueError("Session key is missing from login data")

        current_profile = config.get_current_amf_profile()
        self.current_profile = current_profile
        self.base_url = (
            char_flat.get("character_data_clan_url")
            or char_flat.get("clan_url")
            or current_profile.get("clan_url")
        )
        if not self.base_url:
            raise ValueError(f"Clan war is not available for {current_profile['label']}")

        self.service_bridge_token = (
            self.login_data.get("service_bridge_token")
            or char_flat.get("character_data_service_bridge_token")
            or char_flat.get("service_bridge_token")
        )

        self.http = requests.Session()
        self.http.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Agent": f"{self._agent_prefix()} {config.GAME_BUILD_NUM}",
        })

        self.auth_token: Optional[str] = None
        self.clan_data: dict[str, Any] = {}
        self.clan_char_data: dict[str, Any] = {}
        self._last_logged_stamina: Optional[tuple[Any, Any]] = None
        self._last_stamina_value: Optional[int] = None
        self._last_stamina_fetch_at: float = 0.0
        self.auto_spend_token = bool(auto_spend_token)
        merged_settings = dict(CLAN_WAR_DEFAULT_SETTINGS)
        if isinstance(settings, dict):
            merged_settings.update(settings)
        self.settings = merged_settings

    def _agent_prefix(self) -> str:
        if self.current_profile.get("id") == "alternate4":
            return "ClassicNinja"
        return "NinjaSage"

    @staticmethod
    def _check_stop_event() -> bool:
        if hasattr(config, "stop_event") and config.stop_event.is_set():
            print("Clan war stopped by user request")
            return True
        return False

    def _wait_with_stop_check(self, seconds: int) -> bool:
        for _ in range(seconds):
            if self._check_stop_event():
                return False
            time.sleep(1)
        return True

    @staticmethod
    def _response_message(response: Any) -> str:
        if response is None:
            return "No response"
        fault_string = getattr(response, "faultString", None) or getattr(response, "fault_string", None)
        fault_code = getattr(response, "faultCode", None) or getattr(response, "fault_code", None)
        if fault_string or fault_code:
            return " ".join(str(item) for item in (fault_code, fault_string) if item)
        if isinstance(response, dict):
            for key in ("errorMessage", "message", "error", "result", "detail"):
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
                token = ClanWarEvent._extract_token(value)
                if token:
                    return token
        elif isinstance(payload, list):
            for item in payload:
                token = ClanWarEvent._extract_token(item)
                if token:
                    return token
        return None

    @staticmethod
    def _generate_code(length: int = 24) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choice(alphabet) for _ in range(length))

    @staticmethod
    def _walk_values(payload: Any):
        if isinstance(payload, dict):
            yield payload
            for value in payload.values():
                yield from ClanWarEvent._walk_values(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from ClanWarEvent._walk_values(item)

    @staticmethod
    def _to_int_or_none(value: Any) -> Optional[int]:
        try:
            return int(value)
        except Exception:
            return None

    def _tokens_amount(self) -> Optional[int]:
        for payload in (self.char_data, self.login_data, getattr(config, "all_char", None)):
            for item in self._walk_values(payload):
                for key in ("tokens", "account_tokens", "token"):
                    if key in item:
                        amount = self._to_int_or_none(item.get(key))
                        if amount is not None:
                            return amount
        return None

    def _inventory_amount(self, item_id: str) -> Optional[int]:
        item_id = str(item_id or "")
        for payload in (self.char_data, self.login_data, getattr(config, "all_char", None)):
            if isinstance(payload, dict):
                direct = self._to_int_or_none(payload.get(item_id))
                if direct is not None:
                    return direct
            for item in self._walk_values(payload):
                for key in ("id", "item_id", "material_id", "essential_id", "name", "code"):
                    if str(item.get(key) or "") == item_id:
                        for amount_key in ("amount", "quantity", "qty", "count", "num", "value"):
                            amount = self._to_int_or_none(item.get(amount_key))
                            if amount is not None:
                                return amount
        return None

    def _available_refill_requirements(self) -> list[str]:
        refill_source = str(self.settings.get("stamina_refill_source") or "auto").strip().lower()
        material_amount = self._inventory_amount("material_69")
        token_amount = self._tokens_amount()

        if refill_source == "token":
            return ["tokens_10"] if token_amount is None or token_amount >= 10 else []

        if refill_source in {"roll", "stamina_roll", "onigiri"}:
            return ["material_69"] if material_amount is None or material_amount >= 1 else []

        requirements: list[str] = []
        if material_amount is None or material_amount >= 1:
            requirements.append("material_69")
        if token_amount is None or token_amount >= 10:
            requirements.append("tokens_10")
        return requirements

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
            print("Clan session expired, re-authenticating...")
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

    def authenticate(self) -> bool:
        print("Authenticating clan war session...")
        try:
            payload = {
                "char_id": self.char_id,
                "session_key": self.session_key,
            }
            if self.current_profile.get("id") == "alternate4" and self.service_bridge_token:
                payload["service_bridge_token"] = self.service_bridge_token
            response = self._post_json("/auth/login", payload)
        except Exception as exc:
            print(f"Failed to authenticate clan war session: {exc}")
            return False

        token = self._extract_token(response)
        if not token:
            print(f"Clan war auth failed: {self._response_message(response)}")
            return False

        self.auth_token = token
        self.http.headers["Authorization"] = f"Bearer {token}"
        print("Clan war session authenticated")
        return True

    def get_clan_info(self) -> Optional[dict[str, Any]]:
        try:
            response = self._post_json_with_reauth("/player/clan")
        except Exception as exc:
            print(f"Failed to get clan data: {exc}")
            return None

        if isinstance(response, dict) and "clan" in response and "char" in response:
            self.clan_data = response["clan"] or {}
            self.clan_char_data = response["char"] or {}
            return response

        if isinstance(response, dict) and response.get("statusCode") == 404:
            print("Character is not in a clan")
            return None

        print(f"Failed to get clan data: {self._response_message(response)}")
        return None

    def get_stamina(self, announce: bool = True) -> Optional[int]:
        now = time.time()
        if (
            self._last_stamina_value is not None
            and (now - self._last_stamina_fetch_at) < CLAN_STAMINA_MIN_REQUEST_INTERVAL
        ):
            stamina = self._last_stamina_value
            max_stamina = self.clan_char_data.get("max_stamina", 0)
            stamina_pair = (stamina, max_stamina)
            if announce and stamina_pair != self._last_logged_stamina:
                print(f"Clan stamina: {stamina} / {max_stamina}")
                self._last_logged_stamina = stamina_pair
            return stamina

        try:
            response = self._post_json_with_reauth("/player/stamina")
        except Exception as exc:
            print(f"Failed to refresh clan stamina: {exc}")
            return None

        if not isinstance(response, dict) or "char" not in response:
            print(f"Failed to refresh clan stamina: {self._response_message(response)}")
            return None

        self.clan_char_data = response["char"] or {}
        stamina = self.clan_char_data.get("stamina", 0)
        self._last_stamina_value = stamina
        self._last_stamina_fetch_at = time.time()
        max_stamina = self.clan_char_data.get("max_stamina", 0)
        stamina_pair = (stamina, max_stamina)
        if announce and stamina_pair != self._last_logged_stamina:
            print(f"Clan stamina: {stamina} / {max_stamina}")
            self._last_logged_stamina = stamina_pair
        return stamina

    def get_opponents(self) -> list[dict[str, Any]]:
        try:
            response = self._post_json_with_reauth("/battle/opponents")
        except Exception as exc:
            print(f"Failed to get clan battle opponents: {exc}")
            return []
        if isinstance(response, dict) and isinstance(response.get("clans"), list):
            return response["clans"]
        print(f"Failed to get clan battle opponents: {self._response_message(response)}")
        return []

    def pick_first_opponent(self) -> Optional[dict[str, Any]]:
        own_clan_id = self.clan_data.get("id") or self.clan_data.get("clan_id")
        for clan in self.get_opponents():
            if clan.get("id") != own_clan_id:
                return clan
        return None

    def quick_attack(self, opponent_id: Any) -> Any:
        return self._post_json_with_reauth(
            f"/battle/quick/{opponent_id}",
            {"code": self._generate_code(24)},
        )

    def buy_stamina(self) -> bool:
        requirements = self._available_refill_requirements()
        if not requirements:
            print("No clan stamina refill item/token is available (needs material_69 or 10 tokens).")
            return False

        label = "Onigiri / Stamina Roll" if requirements[0] == "material_69" else "10 tokens"
        try:
            print(f"Buying clan stamina refill with {label}...")
            response = self._post_json_with_reauth("/player/stamina/refill")
        except Exception as exc:
            print(f"Failed to buy clan stamina with {label}: {exc}")
            return False

        if response == "ok" or (isinstance(response, dict) and str(response.get("status")) == "1"):
            self._last_stamina_fetch_at = 0.0
            self.get_stamina(announce=True)
            return True

        print(f"Failed to buy clan stamina with {label}: {self._response_message(response)}")
        return False

    def _log_quick_result(self, result: dict[str, Any]) -> None:
        opponent_name = result.get("opponent_name", "Unknown Clan")
        gain = result.get("gain", "n/a")
        reputation = result.get("reputation", "n/a")
        prestige = result.get("prestige", "n/a")
        stamina = result.get("stamina", self.clan_char_data.get("stamina", "n/a"))
        opponent_reputation = result.get("opponent_reputation", "n/a")
        print(
            f"Clan battle result vs {opponent_name}: "
            f"Gain {gain}, Reputation {reputation}, Prestige {prestige}, "
            f"Opponent Reputation {opponent_reputation}, Stamina {stamina}"
        )

    def _apply_battle_result(self, result: dict[str, Any]) -> None:
        if "reputation" in result:
            self.clan_data["reputation"] = result["reputation"]
        if "stamina" in result:
            self.clan_char_data["stamina"] = result["stamina"]
            self._last_stamina_value = result["stamina"]
            self._last_stamina_fetch_at = time.time()

        prestige = result.get("prestige")
        if prestige is not None:
            current_prestige = int(self.clan_char_data.get("prestige", 0) or 0)
            try:
                self.clan_char_data["prestige"] = current_prestige + int(prestige)
            except Exception:
                pass

    def _idle_until_stamina_returns(self) -> bool:
        print("Clan stamina is below 10. Idling for 30 minutes while checking every 5 seconds...")
        end_time = time.time() + CLAN_IDLE_SECONDS
        last_minute_logged = None

        while time.time() < end_time:
            if self._check_stop_event():
                return False

            stamina = self.get_stamina(announce=True)
            if stamina is not None and stamina >= CLAN_BATTLE_STAMINA_COST:
                print("Clan stamina is ready again, resuming battles")
                return True

            remaining_seconds = max(0, int(end_time - time.time()))
            remaining_minutes = remaining_seconds // 60
            if remaining_minutes != last_minute_logged and remaining_seconds % 60 < CLAN_STAMINA_POLL_SECONDS:
                print(f"Clan war idle time remaining: {remaining_minutes} minute(s)")
                last_minute_logged = remaining_minutes

            if not self._wait_with_stop_check(CLAN_STAMINA_POLL_SECONDS):
                return False

        stamina = self.get_stamina(announce=True)
        if stamina is not None and stamina >= CLAN_BATTLE_STAMINA_COST:
            print("30 minutes passed and clan stamina recovered")
            return True

        print("30 minutes passed but stamina is still below 10, continuing to wait...")
        return True

    def run(self) -> None:
        if self._check_stop_event():
            return
        if not self.authenticate():
            return

        clan_info = self.get_clan_info()
        if not clan_info:
            return

        clan_name = self.clan_data.get("name", "Unknown Clan")
        clan_reputation = self.clan_data.get("reputation", "n/a")
        print(f"Clan war ready for clan: {clan_name} | Reputation: {clan_reputation}")

        while not self._check_stop_event():
            stamina = self.get_stamina(announce=True)
            if stamina is None:
                print("Unable to read clan stamina, retrying in 5 seconds...")
                if not self._wait_with_stop_check(CLAN_STAMINA_POLL_SECONDS):
                    return
                continue

            if stamina < CLAN_BATTLE_STAMINA_COST:
                if self.auto_spend_token:
                    print("Clan stamina is below 10. Trying to refill stamina...")
                    if self.buy_stamina():
                        delay_seconds = max(1, int(self.settings.get("buy_stamina_delay_seconds", 3)))
                        if not self._wait_with_stop_check(delay_seconds):
                            return
                        continue
                if not self._idle_until_stamina_returns():
                    return
                continue

            opponent = self.pick_first_opponent()
            if not opponent:
                print("No clan opponents available right now, retrying in 30 seconds...")
                if not self._wait_with_stop_check(30):
                    return
                continue

            opponent_id = opponent.get("id")
            opponent_name = opponent.get("name", "Unknown Clan")
            opponent_rep = opponent.get("reputation", "n/a")
            print(f"Attacking first available clan: {opponent_name} (ID: {opponent_id}, Reputation: {opponent_rep})")

            try:
                result = self.quick_attack(opponent_id)
            except Exception as exc:
                print(f"Clan quick battle failed: {exc}")
                if not self._wait_with_stop_check(CLAN_STAMINA_POLL_SECONDS):
                    return
                continue

            save_fight_data(result)
            if isinstance(result, dict) and "reputation" in result:
                self._apply_battle_result(result)
                self._log_quick_result(result)
            else:
                print(f"Clan quick battle failed: {self._response_message(result)}")
                if self._is_auth_error(result):
                    if not self.authenticate():
                        return

            delay_seconds = max(1, int(self.settings.get("battle_delay_seconds", CLAN_BETWEEN_BATTLES_SECONDS)))
            if not self._wait_with_stop_check(delay_seconds):
                return


def clan_war_event(params: Optional[dict[str, Any]] = None) -> None:
    options = params if isinstance(params, dict) else {}
    try:
        event = ClanWarEvent(
            auto_spend_token=bool(options.get("auto_spend_token")),
            settings=options.get("settings") or {},
        )
    except ValueError as exc:
        print(str(exc))
        return
    event.run()
