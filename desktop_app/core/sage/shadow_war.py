from .. import config
import time
from .utils import flatten_json, send_amf_request, CUCSG, save_fight_data


class ShadowWarEvent:
    def __init__(self):
        if not isinstance(config.char_data, dict):
            raise ValueError("Character data is not loaded in memory")
        if not isinstance(config.login_data, dict):
            raise ValueError("Login data is not loaded in memory")

        self.char_data = config.char_data
        self.login_data = config.login_data
        char_flat = flatten_json(self.char_data)
        self.char_id = (
            char_flat.get("character_data_character_id")
            or char_flat.get("character_id")
        )
        if not self.char_id:
            raise ValueError("Character ID is missing from current character data")

        self.session_key = self.login_data["sessionkey"]
        self.base_params = [self.char_id, self.session_key]
    @staticmethod
    def _check_stop_event():
        if hasattr(config, "stop_event") and config.stop_event.is_set():
            print("Shadow war stopped by user request")
            return True
        return False

    def _wait_with_stop_check(self, seconds: int) -> bool:
        for _ in range(seconds):
            if self._check_stop_event():
                return False
            time.sleep(1)
        return True

    def _handle_empty_shadow_war_energy(self) -> bool:
        settings = config.get_sage_global_settings()
        mode = str(settings.get("sage_shadow_war_empty_resource_mode", "wait")).strip().lower()
        if mode not in {"buy", "wait", "stop"}:
            mode = "wait"
        wait_minutes = max(0, int(settings.get("sage_shadow_war_wait_minutes", 30) or 30))

        if mode == "stop":
            print("No energy available for shadow war. Stopping action.")
            return False

        if mode == "buy":
            return self.refill_energy()

        print(f"No energy available for shadow war. Waiting {wait_minutes} minute(s).")

        if wait_minutes <= 0:
            return False
        return self._wait_with_stop_check(wait_minutes * 60)

    @staticmethod
    def _response_message(response) -> str:
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

    def get_event_status(self):
        """Get current event status including energy."""
        return send_amf_request("ShadowWar.executeService", ["getStatus", self.base_params])

    def refill_energy(self) -> bool:
        """Buy a full Shadow War energy refill with the same API used by the client."""
        print("Shadow War: buying full energy refill for 50 tokens...")
        response = send_amf_request("ShadowWar.executeService", ["refillEnergy", self.base_params])
        if isinstance(response, dict) and str(response.get("status")) == "1":
            print("Shadow War energy refill successful.")
            return True

        print(f"Shadow War energy refill failed: {self._response_message(response)}")
        return False

    def get_available_battles(self):
        """Calculate number of available battles based on energy."""
        event_status = self.get_event_status()
        if not isinstance(event_status, dict):
            print("Shadow War unavailable or no energy right now")
            return 0
        if event_status.get("status") not in (None, 1):
            print("Shadow War unavailable or no energy right now")
            return 0
        energy = event_status.get('energy', 0)
        print(f"{energy} energies available")
        return energy // 10  # Use integer division

    def get_enemies(self):
        """Retrieve list of enemies."""
        return send_amf_request("ShadowWar.executeService", ["getEnemies", self.base_params])

    def start_battle(self, enemy_id):
        """Start a battle with specified enemy."""
        params = [self.char_id, self.session_key, enemy_id]
        return send_amf_request("ShadowWar.executeService", ["startBattle", params])

    def finish_battle(self, battle_id):
        """Finish the battle and get rewards."""
        mission_hash = CUCSG.hash(f"{self.char_id}{battle_id}0{config.BATTLE_HASH}")
        params = [self.char_id, self.session_key, battle_id, 0, config.BATTLE_HASH, mission_hash]
        return send_amf_request("ShadowWar.executeService", ["finishBattle", params])

    def process_battle(self):
        """Process a single battle sequence."""
        try:
            if self._check_stop_event():
                return False

            # Get enemy data
            enemies_data = self.get_enemies()
            if not isinstance(enemies_data, dict):
                print(f"Failed to get shadow war enemies: {self._response_message(enemies_data)}")
                return False
            if 'enemies' not in enemies_data or not enemies_data['enemies']:
                print("No enemies available")
                return False

            enemy_payload = enemies_data['enemies'][0]
            enemy_id = str(enemy_payload['id'])
            enemy_name = str(enemy_payload.get("name", "n/a"))
            enemy_trophy = enemy_payload.get("trophy", "n/a")
            enemy_rank = enemy_payload.get("rank", "n/a")
            print(f"Start fighting ID: {enemy_id}")
            print(f"Battle Begins...")
            # Start battle
            battle_data = self.start_battle(enemy_id)
            if not isinstance(battle_data, dict):
                print(f"Failed to start battle: {self._response_message(battle_data)}")
                return False
            if battle_data.get("status") != 1:
                print(f"Failed to start battle: {self._response_message(battle_data)}")
                return False

            # Wait for battle to complete
            if not self._wait_with_stop_check(20):
                return False

            # Finish battle and get rewards
            battle_result = self.finish_battle(battle_data['id'])
            save_fight_data(battle_result)
            if not isinstance(battle_result, dict):
                print(f"Battle failed: {self._response_message(battle_result)}")
                return False
            if battle_result.get("status") == 1:
                result_payload = battle_result.get("result") or []
                xp_gained = result_payload[0] if len(result_payload) > 0 else "n/a"
                gold_gained = result_payload[1] if len(result_payload) > 1 else "n/a"
                print(
                    f"Victory against {enemy_name}: "
                    f"XP: {xp_gained}, Gold: {gold_gained}, "
                    f"win_trophy: {battle_result.get('win_trophy', 'n/a')}, "
                    f"trophy: {battle_result.get('trophy', 'n/a')}, "
                    f"player_rank: {battle_result.get('rank', '0')}"
                )
                return True
            else:
                print(f"Battle failed: {self._response_message(battle_result)}")
                return False

        except Exception as e:
            print(f"Error processing battle: {e}")
            return False

    def run(self):
        """Main method to run the shadow war event."""
        if self._check_stop_event():
            return

        available_battles = self.get_available_battles()
        while available_battles <= 0:
            if not self._handle_empty_shadow_war_energy():
                return
            available_battles = self.get_available_battles()

        print(f"Starting {available_battles} battles...")
        
        successful_battles = 0
        for i in range(available_battles):
            if self._check_stop_event():
                break
            print(f"Battle {i + 1}/{available_battles}")
            if self.process_battle():
                successful_battles += 1
            
            # Small delay between battles
            if i < available_battles - 1:
                if not self._wait_with_stop_check(30):
                    break
        
        print(f"Completed {successful_battles}/{available_battles} battles successfully")


def shadow_war_event():
    """Main function to execute shadow war event."""
    event = ShadowWarEvent()
    event.run()


