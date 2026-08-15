from .utils import (
    send_amf_request,
    save_to_json,
    open_json_to_dict,
    get_data_by_id,
    save_fight_data,
    CUCSG,
)
from . import config
import time
import keyboard
from typing import Dict, Any, Optional, Tuple

# Constants
BATTLE_WAIT_TIME = 30  # seconds
MIN_ENERGY_REQUIRED = 10
EVENT_DATA_ENDPOINT = "MonsterHunterEvent2023.getEventData"
START_BATTLE_ENDPOINT = "MonsterHunterEvent2023.startBattle"
FINISH_BATTLE_ENDPOINT = "MonsterHunterEvent2023.finishBattle"

# Load game data
gamedata = open_json_to_dict("data/gamedata.json")
battle_hash = config.BATTLE_HASH

class MonsterHunt:
    def __init__(self):
        self.char_data = config.char_data
        self.char_id = self.char_data["character_data"]["character_id"]
        self.session_key = config.login_data["sessionkey"]
        self.equipment_data = self._get_equipment_data()

    @staticmethod
    def check_stop_event() -> bool:
        """Check if stop event is set from GUI or 'q' is pressed."""
        if hasattr(config, 'stop_event') and config.stop_event.is_set():
            print("Monster hunting stopped by user request")
            return True
        if keyboard.is_pressed('q'):
            print("Operation cancelled by user (q pressed)")
            return True
        return False

    @staticmethod
    def _get_equipment_data() -> str:
        """Return the base64 encoded equipment data."""
        return "eyJpdGVtcyI6eyJhY2Nlc3NvcnkiOiJhY2Nlc3NvcnlfMDEiLCJiYWNrX2l0ZW0iOiJiYWNrXzIzODEiLCJ3ZWFwb24iOiJ3cG5fMjM4MCIsInNldCI6InNldF8yMjU4XzEifSwic3RhdHVzIjp7ImVhcnRoIjowLCJsaWdodG5pbmciOjAsImZpcmUiOjAsIndhdGVyIjowLCJ3aW5kIjo3OH0sImJ5dGVzIjp7Il9fXyI6IjE3NjM4Nzk1ODk0MDM2N2MzY2M5OTlhOWY5ZTk1MWExZDMzMjExNTQ1Yjg0YjJkNWE2MzkzM2IwMDIwNDMzMDAwYzNiYjQxMGZiMTc2Mzg3OTU4OTE3NjM4Nzk1ODkxNzYzODc5NTg5MTc2Mzg3OTU4OSIsIl8iOjgyMjg0NDcsIl9fX18iOjE3NjM4Nzk1ODksIl9fX19fIjo4MjI4NDQ3LCJfXyI6ODIyODQ0NywiX19fX19fIjo4MjI4NDQ3fSwiX19fXyI6W3siXyI6InNraWxsXzIzMTIiLCJfXyI6NTQ2MDV9LHsiXyI6InNraWxsXzM0NSIsIl9fIjo4MDI0M30seyJfIjoic2tpbGxfMjMxMCIsIl9fIjoxMjg0Njl9LHsiXyI6InNraWxsXzIyMTUiLCJfXyI6MjkzNDl9LHsiXyI6InNraWxsXzIyODYiLCJfXyI6NDk0NzR9LHsiXyI6InNraWxsXzIyMDYiLCJfXyI6NjA5NDR9LHsiXyI6InNraWxsXzIzMDgiLCJfXyI6NjUxMDF9LHsiXyI6InNraWxsXzMyOSIsIl9fIjo3NTM1Nn1dfQ=="

    def _get_event_data(self) -> Optional[Dict[str, Any]]:
        """Fetch and return event data from the server."""
        response = send_amf_request(
            EVENT_DATA_ENDPOINT,
            [self.char_id, self.session_key]
        )
        if response.get('status') != 1:
            print(f"Failed to get monster hunt event data: {response}")
            return None
        return response

    def _start_battle(self, boss_id: str) -> Optional[Dict[str, Any]]:
        """Start a battle and return the battle data."""
        battle_hash = CUCSG.hash(f"{self.char_id}{boss_id}")
        response = send_amf_request(
            START_BATTLE_ENDPOINT,
            [self.char_id, boss_id, battle_hash, self.session_key]
        )
        if response.get('status') != 1:
            print(f"Failed to start battle: {response}")
            return None
        return response

    def _finish_battle(self, boss_id: str, battle_id: str, battle_hash_value: str) -> bool:
        """Finish the battle and process rewards."""
        battle_completion_hash = CUCSG.hash(
            f"{self.char_id}{boss_id}{battle_id}0{self.equipment_data}"
        )
        params =  [
                self.char_id,
                boss_id,
                battle_id,
                0,  # Damage dealt
                battle_completion_hash,
                self.equipment_data,
                self.session_key
            ]
        
        response = send_amf_request(
            FINISH_BATTLE_ENDPOINT,
            params
        )
        
        save_fight_data(response)
        return self._process_battle_results(response)

    def _process_battle_results(self, battle_result: Dict[str, Any]) -> bool:
        """Process and display battle results."""
        if battle_result.get('status') != 1:
            print(f"Battle failed with status: {battle_result.get('status')}")
            return False

        rewards = battle_result.get('result', [])
        if rewards and len(rewards) >= 2:
            print(f"Battle completed! Gained {rewards[0]} XP and {rewards[1]} gold")
            if len(rewards) > 2 and isinstance(rewards[2], list):
                print(f"Additional rewards: {', '.join(rewards[2])}")
        return True

    def _wait_for_battle_completion(self) -> bool:
        """Wait for the battle to complete with progress indication."""
        print("Waiting for battle to complete...", end='', flush=True)
        for _ in range(BATTLE_WAIT_TIME):
            if self.check_stop_event():
                print("\nBattle wait interrupted")
                return False
            print('.', end='', flush=True)
            time.sleep(1)
        print()  # New line after progress dots
        return True

    def run(self) -> None:
        """Run the monster hunt process."""
        print("Starting monster hunt process...")
        
        while not self.check_stop_event():
            # Get fresh event data for each iteration
            event_data = self._get_event_data()
            if not event_data:
                print("Failed to get event data, stopping...")
                break

            boss_id = event_data.get('boss_id')
            energy = event_data.get('energy', 0)
            
            # Check energy before starting battle
            if energy < MIN_ENERGY_REQUIRED:
                print(f"Not enough energy to start battle. Current: {energy}/{MIN_ENERGY_REQUIRED} required")
                print("Monster hunt completed (out of energy)")
                break

            print(f"Starting battle with {boss_id} (Energy: {energy})")
            
            # Start battle
            battle_start = self._start_battle(boss_id)
            if not battle_start:
                print("Failed to start battle, stopping...")
                break

            # Wait for battle completion
            if not self._wait_for_battle_completion():
                print("Battle wait interrupted, stopping...")
                break

            # Finish battle
            if not self._finish_battle(
                boss_id,
                battle_start.get('code'),
                battle_start.get('hash')
            ):
                print("Battle completion failed, stopping...")
                break
            
            # Get updated energy after battle
            updated_event_data = self._get_event_data()
            if updated_event_data:
                new_energy = updated_event_data.get('energy', 0)
                energy_used = energy - new_energy
                print(f"Energy used: {energy_used}, Remaining: {new_energy}")
                
                # Check if we have enough energy for another battle
                if new_energy < MIN_ENERGY_REQUIRED:
                    print(f"Not enough energy for another battle. Current: {new_energy}/{MIN_ENERGY_REQUIRED} required")
                    break
            
            # Small delay between battles to prevent rate limiting
            print("Preparing for next battle...")
            time.sleep(2)

# Public function to maintain backward compatibility
def fight_monster_hunt():
    """Public interface to start the monster hunt."""
    MonsterHunt().run()