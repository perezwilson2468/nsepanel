import random
import string
import time
from typing import Any, Callable, Optional

import requests

from .. import config
from .utils import flatten_json, save_fight_data, send_amf_request

CLAN_BATTLE_STAMINA_COST = 10
CLAN_STAMINA_POLL_SECONDS = 5
CLAN_STAMINA_MIN_REQUEST_INTERVAL = 10
CLAN_IDLE_SECONDS = 30 * 60
CLAN_BETWEEN_BATTLES_SECONDS = 8
REQUEST_TIMEOUT_SECONDS = 20
CLAN_OPPONENTS_MIN_REQUEST_INTERVAL = 30
CLAN_OPPONENTS_RATE_LIMIT_BACKOFF_SECONDS = 60
CLAN_WAR_DEFAULT_SETTINGS = {
    "battle_delay_seconds": 8,
    "refresh_delay_seconds": 30,
    "buy_stamina_delay_seconds": 3,
    "stamina_refill_source": "auto",
}


class ClanWarEvent:
    def __init__(
        self,
        *,
        target_clan_id: Any | None = None,
        target_clan_name: str = "",
        auto_spend_token: bool = False,
        bleeding_mode: bool = False,
        manual_recruit: bool = False,
        manual_member_ids: Optional[list[Any]] = None,
        settings: Optional[dict[str, Any]] = None,
        state_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    ):
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
            "Agent": f"{self._agent_prefix()} {config.BUILD_NUM}",
        })

        self.auth_token: Optional[str] = None
        self.clan_data: dict[str, Any] = {}
        self.clan_char_data: dict[str, Any] = {}
        self._last_logged_stamina: Optional[tuple[Any, Any]] = None
        self._last_stamina_value: Optional[int] = None
        self._last_stamina_fetch_at: float = 0.0
        self._last_opponents: list[dict[str, Any]] = []
        self._last_opponents_fetch_at: float = 0.0
        self._opponents_rate_limited_until: float = 0.0
        self.target_clan_id = str(target_clan_id or "").strip()
        self.target_clan_name = str(target_clan_name or "").strip()
        self.auto_spend_token = bool(auto_spend_token)
        self.bleeding_mode = bool(bleeding_mode)
        self.manual_recruit = bool(manual_recruit)
        self.manual_member_ids = [str(item) for item in (manual_member_ids or []) if str(item).strip()]
        self.bleeding_reputation_gained = False
        self.selected_recruiters: list[str] = []
        merged_settings = dict(CLAN_WAR_DEFAULT_SETTINGS)
        if isinstance(settings, dict):
            merged_settings.update(settings)
        self.settings = merged_settings
        self.state_callback = state_callback

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
        for _ in range(max(0, int(seconds))):
            if self._check_stop_event():
                return False
            time.sleep(1)
        return True

    def _emit_state(self, **updates: Any) -> None:
        if not self.state_callback:
            return
        try:
            self.state_callback(updates)
        except Exception:
            pass

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
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _member_sort_key(member: dict[str, Any]) -> tuple[int, int, str]:
        return (
            ClanWarEvent._safe_int(member.get("stamina")),
            ClanWarEvent._safe_int(member.get("reputation_gain")),
            str(member.get("name") or ""),
        )

    @staticmethod
    def _normalize_list_payload(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            value = list(value.values())
        if not isinstance(value, list):
            return []
        result: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                result.append(item)
        return result

    @staticmethod
    def _sanitize_war_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id") or item.get("clan_id"),
            "name": item.get("name") or item.get("clan_name") or "Unknown Clan",
            "reputation": item.get("reputation", 0),
            "master": item.get("master") or item.get("master_name") or "-",
            "members": item.get("member") or item.get("member_total") or item.get("members") or 0,
            "raw": item,
        }

    @staticmethod
    def _sanitize_member_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id") or item.get("char_id") or item.get("uid"),
            "name": item.get("name") or item.get("character_name") or "Unknown",
            "level": item.get("level") or item.get("character_level") or 0,
            "stamina": item.get("stamina") or 0,
            "reputation_gain": item.get("reputation_gain") or 0,
            "raw": item,
        }

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

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        return bool(response is not None and getattr(response, "status_code", None) == 429)

    @staticmethod
    def _retry_after_seconds(exc: Exception, default: int = CLAN_OPPONENTS_RATE_LIMIT_BACKOFF_SECONDS) -> int:
        response = getattr(exc, "response", None)
        retry_after = None
        if response is not None:
            retry_after = response.headers.get("Retry-After")
        try:
            return max(default, int(float(retry_after)))
        except Exception:
            return default

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

    def _opponents_refresh_delay(self) -> int:
        configured = self._safe_int(self.settings.get("refresh_delay_seconds"), CLAN_OPPONENTS_MIN_REQUEST_INTERVAL)
        return max(CLAN_OPPONENTS_MIN_REQUEST_INTERVAL, configured)

    def get_opponents(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        now = time.time()
        if self._last_opponents and not force_refresh:
            if now < self._opponents_rate_limited_until:
                remaining = int(self._opponents_rate_limited_until - now)
                print(f"Clan opponent refresh is rate-limited; reusing cached target list for {remaining} second(s)")
                return list(self._last_opponents)

            min_interval = self._opponents_refresh_delay()
            if (now - self._last_opponents_fetch_at) < min_interval:
                return list(self._last_opponents)

        try:
            response = self._post_json_with_reauth("/battle/opponents")
        except Exception as exc:
            if self._is_rate_limit_error(exc):
                backoff = self._retry_after_seconds(exc)
                self._opponents_rate_limited_until = time.time() + backoff
                if self._last_opponents:
                    print(
                        f"Clan opponent endpoint is rate-limited (429). "
                        f"Waiting {backoff} second(s) before refreshing and reusing cached opponents."
                    )
                    return list(self._last_opponents)
                print(f"Clan opponent endpoint is rate-limited (429). Waiting {backoff} second(s) before retrying.")
                return []
            print(f"Failed to get clan battle opponents: {exc}")
            if self._last_opponents:
                return list(self._last_opponents)
            return []

        if isinstance(response, dict) and isinstance(response.get("clans"), list):
            opponents = [self._sanitize_war_item(item) for item in response["clans"] if isinstance(item, dict)]
            self._last_opponents = opponents
            self._last_opponents_fetch_at = time.time()
            self._opponents_rate_limited_until = 0.0
            return list(opponents)

        try:
            response = send_amf_request("ClanService.getWarList", [self.session_key])
        except Exception:
            response = None
        if isinstance(response, dict):
            war_list = self._normalize_list_payload(response.get("war_list"))
            if war_list:
                char_stamina = response.get("character_stamina")
                if char_stamina is not None:
                    self.clan_char_data["stamina"] = char_stamina
                opponents = [self._sanitize_war_item(item) for item in war_list]
                self._last_opponents = opponents
                self._last_opponents_fetch_at = time.time()
                return list(opponents)

        print(f"Failed to get clan battle opponents: {self._response_message(response)}")
        if self._last_opponents:
            return list(self._last_opponents)
        return []

    def get_member_list(self) -> list[dict[str, Any]]:
        try:
            response = send_amf_request("ClanWar.getMemberList", [self.session_key])
        except Exception as exc:
            print(f"Failed to get clan member list: {exc}")
            return []

        if isinstance(response, dict):
            members = self._normalize_list_payload(response.get("clan_members"))
            return [self._sanitize_member_item(item) for item in members]
        return []

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

    def choose_recruiters(self, members: list[dict[str, Any]]) -> list[str]:
        if not self.bleeding_mode or self.bleeding_reputation_gained:
            self.selected_recruiters = []
            return []

        if self.manual_recruit and self.manual_member_ids:
            chosen = self.manual_member_ids[:2]
        else:
            sorted_members = sorted(members, key=self._member_sort_key, reverse=True)
            chosen = []
            for member in sorted_members:
                member_id = str(member.get("id") or "").strip()
                if not member_id:
                    continue
                chosen.append(member_id)
                if len(chosen) >= 2:
                    break

        self.selected_recruiters = chosen
        return chosen

    def find_target_opponent(self, opponents: Optional[list[dict[str, Any]]] = None) -> Optional[dict[str, Any]]:
        own_clan_id = str(self.clan_data.get("id") or self.clan_data.get("clan_id") or "")
        if opponents is None:
            opponents = self.get_opponents()
        if self.target_clan_id:
            for clan in opponents:
                if str(clan.get("id")) == self.target_clan_id:
                    return clan
        for clan in opponents:
            if str(clan.get("id")) != own_clan_id:
                return clan
        return None

    def quick_attack(self, opponent_id: Any) -> Any:
        return self._post_json_with_reauth(
            f"/battle/quick/{opponent_id}",
            {"code": self._generate_code(24)},
        )

    def _log_quick_result(self, result: dict[str, Any]) -> None:
        opponent_name = result.get("opponent_name", self.target_clan_name or "Unknown Clan")
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

        reputation_gain = self._safe_int(result.get("gain") or result.get("reputation_gain") or 0)
        if reputation_gain > 0 and not self.bleeding_reputation_gained:
            self.bleeding_reputation_gained = True
            if self.bleeding_mode:
                print("Bleeding mode: first reputation gain detected, disabling auto-recruit for following battles")

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

    def snapshot(self) -> dict[str, Any]:
        if not self.authenticate():
            raise ValueError("Failed to authenticate clan war session")

        clan_info = self.get_clan_info()
        if not clan_info:
            raise ValueError("Character is not currently in a clan")

        stamina = self.get_stamina(announce=False)
        opponents = self.get_opponents()
        members = self.get_member_list()
        chosen_recruiters = self.choose_recruiters(members)

        clan_name = self.clan_data.get("name") or "Unknown Clan"
        reputation = self.clan_data.get("reputation")
        max_stamina = self.clan_char_data.get("max_stamina", 0)
        current_stamina = stamina if stamina is not None else self.clan_char_data.get("stamina", 0)

        return {
            "clan": {
                "id": self.clan_data.get("id") or self.clan_data.get("clan_id"),
                "name": clan_name,
                "reputation": reputation,
            },
            "char": {
                "stamina": current_stamina,
                "max_stamina": max_stamina,
                "prestige": self.clan_char_data.get("prestige"),
            },
            "war_list": opponents,
            "member_list": members,
            "selected_recruiters": chosen_recruiters,
            "bleeding_reputation_gained": self.bleeding_reputation_gained,
        }

    def _current_snapshot(self, opponents: Optional[list[dict[str, Any]]] = None, members: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
        clan_name = self.clan_data.get("name") or "Unknown Clan"
        reputation = self.clan_data.get("reputation")
        max_stamina = self.clan_char_data.get("max_stamina", 0)
        current_stamina = self.clan_char_data.get("stamina", 0)
        war_list = opponents if isinstance(opponents, list) else []
        member_list = members if isinstance(members, list) else []
        return {
            "clan": {
                "id": self.clan_data.get("id") or self.clan_data.get("clan_id"),
                "name": clan_name,
                "reputation": reputation,
            },
            "char": {
                "stamina": current_stamina,
                "max_stamina": max_stamina,
                "prestige": self.clan_char_data.get("prestige"),
            },
            "war_list": war_list,
            "member_list": member_list,
            "selected_recruiters": [],
            "bleeding_reputation_gained": self.bleeding_reputation_gained,
        }

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
        current_opponents = self.get_opponents()
        self._emit_state(snapshot=self._current_snapshot(current_opponents, []), running=True)

        while not self._check_stop_event():
            stamina = self.get_stamina(announce=True)
            if stamina is None:
                print("Unable to read clan stamina, retrying in 5 seconds...")
                if not self._wait_with_stop_check(CLAN_STAMINA_POLL_SECONDS):
                    return
                continue

            if stamina < CLAN_BATTLE_STAMINA_COST:
                if self.auto_spend_token:
                    print("Clan stamina is below 10. Trying to buy stamina...")
                    if self.buy_stamina():
                        if not self._wait_with_stop_check(max(1, int(self.settings.get("buy_stamina_delay_seconds", 3)))):
                            return
                        current_opponents = self.get_opponents()
                        self._emit_state(snapshot=self._current_snapshot(current_opponents, []), running=True)
                        continue
                if not self._idle_until_stamina_returns():
                    return
                current_opponents = self.get_opponents()
                self._emit_state(snapshot=self._current_snapshot(current_opponents, []), running=True)
                continue

            members = self.get_member_list()
            active_recruiters = self.choose_recruiters(members)
            if self.bleeding_mode and not self.bleeding_reputation_gained and active_recruiters:
                print(f"Bleeding mode recruiters: {', '.join(active_recruiters)}")

            opponent = self.find_target_opponent(current_opponents)
            if not opponent and self.target_clan_id:
                current_opponents = self.get_opponents(force_refresh=True)
                opponent = self.find_target_opponent(current_opponents)
            elif not self.target_clan_id:
                current_opponents = self.get_opponents(force_refresh=not bool(current_opponents))
                opponent = self.find_target_opponent(current_opponents)
            if not opponent:
                refresh_delay = self._opponents_refresh_delay()
                print(f"Selected clan opponent is not available right now, retrying in {refresh_delay} seconds...")
                if not self._wait_with_stop_check(refresh_delay):
                    return
                continue

            opponent_id = opponent.get("id")
            opponent_name = opponent.get("name", "Unknown Clan")
            opponent_rep = opponent.get("reputation", "n/a")
            self.target_clan_name = opponent_name
            print(f"Attacking clan: {opponent_name} (ID: {opponent_id}, Reputation: {opponent_rep})")

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
                self._emit_state(snapshot=self._current_snapshot(current_opponents, []), running=True)
            else:
                print(f"Clan quick battle failed: {self._response_message(result)}")
                if self._is_auth_error(result):
                    if not self.authenticate():
                        return

            delay_seconds = max(1, int(self.settings.get("battle_delay_seconds", CLAN_BETWEEN_BATTLES_SECONDS)))
            if not self._wait_with_stop_check(delay_seconds):
                return


def build_clan_war_snapshot(params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    options = params if isinstance(params, dict) else {}
    event_settings = dict(options.get("settings") or {})
    event_settings["stamina_refill_source"] = options.get("stamina_refill_source") or event_settings.get("stamina_refill_source") or "auto"
    event = ClanWarEvent(
        target_clan_id=options.get("target_clan_id"),
        target_clan_name=options.get("target_clan_name") or "",
        auto_spend_token=bool(options.get("auto_spend_token")),
        bleeding_mode=bool(options.get("bleeding_mode")),
        manual_recruit=bool(options.get("manual_recruit")),
        manual_member_ids=options.get("manual_member_ids") or [],
        settings=event_settings,
    )
    return event.snapshot()


def clan_war_event(params: Optional[dict[str, Any]] = None, state_callback: Optional[Callable[[dict[str, Any]], None]] = None) -> None:
    options = params if isinstance(params, dict) else {}
    event_settings = dict(options.get("settings") or {})
    event_settings["stamina_refill_source"] = options.get("stamina_refill_source") or event_settings.get("stamina_refill_source") or "auto"
    event = ClanWarEvent(
        target_clan_id=options.get("target_clan_id"),
        target_clan_name=options.get("target_clan_name") or "",
        auto_spend_token=bool(options.get("auto_spend_token")),
        bleeding_mode=bool(options.get("bleeding_mode")),
        manual_recruit=bool(options.get("manual_recruit")),
        manual_member_ids=options.get("manual_member_ids") or [],
        settings=event_settings,
        state_callback=state_callback,
    )
    event.run()
