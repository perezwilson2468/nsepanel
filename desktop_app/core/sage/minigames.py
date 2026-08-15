from dataclasses import dataclass
import hashlib
import random
import time
from typing import Any, Optional

from .. import config
from .utils import CUCSG, flatten_json, save_fight_data, send_amf_request


MINIGAME_FINISH_DELAY_SECONDS = 25
MINIGAME_REQUEST_DELAY_SECONDS = 2
MINIGAME_BETWEEN_RUNS_SECONDS = 3


@dataclass(frozen=True)
class MinigameConfig:
    key: str
    label: str
    api_class: str
    finish_value: Any
    data_method_name: str = "getMinigameData"
    start_method_name: str = "startMinigame"
    finish_method_name: str = "finishMinigame"
    energy_key: str = "energy"
    battle_code_key: str = "code"
    finish_hash_mode: str = "default"

    def get_data_method(self) -> str:
        return f"{self.api_class}.{self.data_method_name}"

    def start_method(self) -> str:
        return f"{self.api_class}.{self.start_method_name}"

    def finish_method(self) -> str:
        return f"{self.api_class}.{self.finish_method_name}"

    def get_finish_value(self) -> Any:
        if self.finish_value == "random_worldcup_score":
            return random.randint(26000, 30000)
        return self.finish_value


MINIGAME_CONFIGS = {
    "christmas": MinigameConfig(
        key="christmas",
        label="Christmas Event 2025 Minigame",
        api_class="ChristmasEvent2025",
        finish_value=121,
    ),
    "anniversary": MinigameConfig(
        key="anniversary",
        label="Anniversary Event 2026 Minigame",
        api_class="AnniversaryEvent2026",
        finish_value="win",
    ),
    "worldcup": MinigameConfig(
        key="worldcup",
        label="World Cup Event 2026 Minigame",
        api_class="WorldCupEvent2026",
        finish_value="random_worldcup_score",
        data_method_name="getminigamedata",
        start_method_name="startminigame",
        finish_method_name="finishminigame",
        energy_key="minigame_energy",
        battle_code_key="battle_code",
        finish_hash_mode="worldcup",
    ),
}


class MinigameSystem:
    @staticmethod
    def _check_stop_event() -> bool:
        if hasattr(config, "stop_event") and config.stop_event.is_set():
            print("Minigame stopped by user request")
            return True
        return False

    def _wait_with_stop_check(self, seconds: int) -> bool:
        for _ in range(seconds):
            if self._check_stop_event():
                return False
            time.sleep(1)
        return True

    def _send_request(self, method: str, parameters: list, delay: int = MINIGAME_REQUEST_DELAY_SECONDS):
        if delay > 0 and not self._wait_with_stop_check(delay):
            return None
        return send_amf_request(method, parameters)

    @staticmethod
    def _response_message(response: Any) -> str:
        if response is None:
            return "No response"
        if isinstance(response, dict):
            return str(
                response.get("result")
                or response.get("error")
                or response.get("message")
                or response
            )
        for attr in ("description", "message", "details", "faultString"):
            value = getattr(response, attr, None)
            if value:
                return str(value)
        return str(response)

    @staticmethod
    def _build_finish_hash(char_id: str, session_key: str, finish_value: Any, battle_code: str) -> str:
        hash_input = f"{char_id}|{session_key}|{finish_value}|{battle_code}"
        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_worldcup_finish_hash(char_id: str, score: int, battle_code: str) -> str:
        return CUCSG.hash(f"{char_id}_{score}_{battle_code}")

    @staticmethod
    def _normalize_rewards(rewards: Any) -> list[str]:
        if not isinstance(rewards, list):
            return []
        return [str(item) for item in rewards]

    @staticmethod
    def _get_character_session() -> tuple[str, str]:
        char_flat = flatten_json(config.char_data)
        char_id = str(char_flat["character_data_character_id"])
        session_key = str(config.login_data["sessionkey"])
        return char_id, session_key

    def run(self, minigame_key: str, num_loops: Optional[int] = None) -> None:
        minigame = MINIGAME_CONFIGS.get(minigame_key)
        if not minigame:
            raise ValueError(f"Unknown minigame: {minigame_key}")

        char_id, session_key = self._get_character_session()
        print(f"Starting {minigame.label}...")

        completed_runs = 0
        while not self._check_stop_event():
            minigame_data = self._send_request(
                minigame.get_data_method(),
                [char_id, session_key],
            )
            if minigame_data is None:
                return
            if not isinstance(minigame_data, dict):
                print(f"Failed to get minigame data: {self._response_message(minigame_data)}")
                return
            if minigame_data.get("status") != 1:
                print(f"Failed to get minigame data: {self._response_message(minigame_data)}")
                return

            energy = int(minigame_data.get(minigame.energy_key, 0) or 0)
            print(f"{minigame.label} energy: {energy}")
            if energy <= 0:
                print(f"No energy left for {minigame.label}")
                return

            if num_loops is not None and completed_runs >= num_loops:
                print(f"Finished requested {completed_runs} run(s) for {minigame.label}")
                return

            print(f"Starting minigame {completed_runs + 1}...")
            start_result = self._send_request(
                minigame.start_method(),
                [char_id, session_key],
            )
            if start_result is None:
                return
            if not isinstance(start_result, dict):
                print(f"Failed to start minigame: {self._response_message(start_result)}")
                return
            if start_result.get("status") != 1:
                print(f"Failed to start minigame: {self._response_message(start_result)}")
                return

            battle_code = start_result.get(minigame.battle_code_key)
            if not battle_code:
                print(f"Failed to start minigame: missing battle code in {start_result}")
                return

            print(f"Battle code: {battle_code}")
            print(f"Waiting {MINIGAME_FINISH_DELAY_SECONDS} seconds before finishing...")
            if not self._wait_with_stop_check(MINIGAME_FINISH_DELAY_SECONDS):
                return

            finish_value = minigame.get_finish_value()
            if minigame.finish_hash_mode == "worldcup":
                finish_hash = self._build_worldcup_finish_hash(char_id, int(finish_value), str(battle_code))
                finish_params = [char_id, session_key, finish_value, finish_hash, str(battle_code)]
                print(f"Score: {finish_value}")
            else:
                finish_hash = self._build_finish_hash(
                    char_id,
                    session_key,
                    finish_value,
                    str(battle_code),
                )
                finish_params = [char_id, session_key, finish_value, finish_hash]
            finish_result = self._send_request(
                minigame.finish_method(),
                finish_params,
            )
            if finish_result is None:
                return

            save_fight_data(finish_result)
            if not isinstance(finish_result, dict):
                print(f"Failed to finish minigame: {self._response_message(finish_result)}")
                return
            if finish_result.get("status") != 1:
                print(f"Failed to finish minigame: {self._response_message(finish_result)}")
                return

            completed_runs += 1
            current_energy = finish_result.get("current_energy", "?")
            rewards = self._normalize_rewards(finish_result.get("rewards"))
            rank = finish_result.get("rank")

            print(f"{minigame.label} completed successfully")
            print(f"Remaining energy: {current_energy}")
            if rewards:
                print(f"Rewards: {', '.join(rewards)}")
            else:
                print("Rewards: none")
            if rank is not None:
                print(f"Rank: {rank}")

            if num_loops is not None and completed_runs >= num_loops:
                print(f"Finished requested {completed_runs} run(s) for {minigame.label}")
                return

            if not self._wait_with_stop_check(MINIGAME_BETWEEN_RUNS_SECONDS):
                return


def fight_minigame_event(minigame_key: str, num_loops: Optional[int] = None) -> None:
    system = MinigameSystem()
    system.run(minigame_key, num_loops=num_loops)


