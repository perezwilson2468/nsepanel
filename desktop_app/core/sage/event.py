from .utils import (
    send_amf_request,
    flatten_json,
    get_data_by_id,
    StatManager,
    CUCSG,
    save_fight_data,
    open_json_to_dict,
)
from .. import config
import time
import sys
import re
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
import random

BATTLE_HASH = config.BATTLE_HASH


@dataclass
class EventConfig:
    """Configuration for event battle systems."""
    name: str
    api_class: str
    enemy_choices: Dict[str, Tuple[str, str]]
    is_fixed_boss: bool = False
    boss_id: Optional[str] = None
    boss_hp: Optional[int] = None
    boss_agility: Optional[int] = None
    is_random_enemy: bool = False  # Flag for random enemy events
    delay_between_calls: int = 0  # Default delay in seconds between API calls
    finish_damage: int = 0
    
    def get_battle_data_method(self) -> str:
        if self.api_class == "WorldCupEvent2026":
            return f"{self.api_class}.geteventdata"
        if self.api_class == "EasterEvent2026":
            return f"{self.api_class}.getEventData"
        return f"{self.api_class}.getBattleData"
    
    def get_start_battle_method(self) -> str:
        if self.api_class == "WorldCupEvent2026":
            return f"{self.api_class}.startbattle"
        return f"{self.api_class}.startBattle"
    
    def get_finish_battle_method(self) -> str:
        if self.api_class == "WorldCupEvent2026":
            return f"{self.api_class}.finishbattle"
        return f"{self.api_class}.finishBattle"
    
    def get_enemy_from_battle_data(self, battle_data: dict) -> Optional[str]:
        """Extract enemy ID from battle data response."""
        try:
            # Handle different response types
            if battle_data is None:
                return None
            
            # Check for rate limiting or errors
            if isinstance(battle_data, dict):
                if battle_data.get('status') == 2:
                    error_msg = battle_data.get('result', 'Unknown error')
                    print(f"⚠️  Server response: {error_msg}")
                    return None
                
                # Check for 'enemy' key (like in Aniv event)
                if 'enemy' in battle_data:
                    return str(battle_data['enemy'])
                # Check for 'bossId' key (like in other events)
                elif 'bossId' in battle_data:
                    return str(battle_data['bossId'])
                # Check for 'id' in nested boss object
                elif 'boss' in battle_data and isinstance(battle_data['boss'], dict):
                    if 'id' in battle_data['boss']:
                        return str(battle_data['boss']['id'])
            
            # If it's a custom object with attributes
            elif hasattr(battle_data, 'enemy'):
                return str(battle_data.enemy)
            elif hasattr(battle_data, 'bossId'):
                return str(battle_data.bossId)
                
            # If it's a list or tuple
            elif isinstance(battle_data, (list, tuple)) and len(battle_data) > 0:
                return self.get_enemy_from_battle_data(battle_data[0])
            
            return None
            
        except Exception as e:
            print(f"Error extracting enemy ID: {e}")
            return None


class EventBattleSystem:
    """Unified system for handling all event battles."""
    
    EVENT_CONFIGS = {
        # Alternative configuration if boss is random/determined by server
        "phantom": EventConfig(
            name="Phantom Kyunoki Event 2026",
            api_class="PhantomKyunokiEvent2026",
            enemy_choices={
                "1": ("ene_258", "Phantom Kyunoki"),
            },
            is_fixed_boss=False,
            is_random_enemy=False,  # It's a specific boss
            boss_id="ene_258",  # The boss ID from your response
            boss_hp=74925,      # From your response
            boss_agility=169,   # From your response
            delay_between_calls=2
        ),
        "snow": EventConfig(
            name="Christmas Event 2025",
            api_class="ChristmasEvent2025",
            enemy_choices={
                "1": ("ene_2117", "Yuki Onna Warrior"),
                "2": ("ene_2118", "Snow Spirit"),
                "3": ("ene_2119", "Yuki Onna")
                },
            delay_between_calls=2  # 2 second delay for Aniv event
        ),
        "thanks": EventConfig(
            name="Thanks GivingEvent 2025",
            api_class="ThanksGivingEvent2025",
            enemy_choices={
                "1": ("ene_2113", "Cornfield Bandit"),
                "2": ("ene_2114", "Cranberry Mage"),
                "3": ("ene_2115", "Grateful Farmer"),
                "4": ("ene_2116", "Turkey Champ")
                },
            delay_between_calls=2  # 2 second delay for Aniv event
        ),
        "sakura": EventConfig(
            name="Sakura Bloom Event 2026",
            api_class="HanamiEvent2026",
            enemy_choices={
                "1": ("ene_2120", "Sakura Duelist"),
                "2": ("ene_2121", "Hanami Spirit"),
                "3": ("ene_2122", "Withered"),
            },
            delay_between_calls=2,
            finish_damage=200000,
        ),
        "easter": EventConfig(
            name="Easter Event 2026",
            api_class="EasterEvent2026",
            enemy_choices={
                "1": ("ene_2124", "Berserk Hornbill"),
                "2": ("ene_2125", "Panzer Bear"),
                "3": ("ene_2126", "Crimson Thorn"),
                "4": ("ene_2127", "Calamity Serpent"),
                "5": ("ene_2128", "Crimson Demon"),
            },
            delay_between_calls=2,
            finish_damage=200000,
        ),
        "worldcup": EventConfig(
            name="World Cup Event 2026",
            api_class="WorldCupEvent2026",
            enemy_choices={
                "1": ("ene_2129", "Spirit Team Captain"),
                "2": ("ene_2130", "Spirit Goalkeeper"),
            },
            delay_between_calls=2,
            finish_damage=200000,
        ),
        "cd": EventConfig(
            name="Confronting Death Event",
            api_class="ConfrontingDeathEvent2025",
            enemy_choices={},
            is_fixed_boss=True,
            boss_id="ene_2112",
            boss_hp=30000,
            boss_agility=150
        ),
        "aniv": EventConfig(
            name="Anniversary Event 2026",
            api_class="AnniversaryEvent2026",
            enemy_choices={},  # Empty because enemy is randomly selected by server
            is_fixed_boss=False,
            is_random_enemy=True,  # Mark as random enemy event
            delay_between_calls=2  # 2 second delay for Aniv event
        ),
        "pumpkin": EventConfig(
            name="Pumpkin Event",
            api_class="HalloweenEvent2025",
            enemy_choices={
                "1": ("ene_2104", "Pumpkin Minion"),
                "2": ("ene_2105", "Skeleton Ninja"),
                "3": ("ene_2106", "Zombie Samurai"),
                "4": ("ene_2103", "Headless Pumpkin Horseman"),
                "5": ("ene_2102", "Cursed Pumpkin King"),
            },
            delay_between_calls=3  # 3 second delay for Pumpkin event
        ),
        "yinyang": EventConfig(
            name="Yin Yang Event",
            api_class="YinYangEvent",
            enemy_choices={
                "1": ("ene_2100", "Yin Tiger"),
                "2": ("ene_2101", "Yang Dragon"),
            },
            delay_between_calls=3
        ),
        "independence": EventConfig(
            name="Independence Event",
            api_class="IndependenceEvent2025",
            enemy_choices={
                "1": ("ene_2095", "Lembuswana"),
                "2": ("ene_2096", "Besukih"),
                "3": ("ene_2097", "Leak"),
                "4": ("ene_2098", "Ahool"),
                "5": ("ene_2099", "Sembrani"),
            },
            delay_between_calls=3
        ),
    }
    
    def __init__(self):
        self.enemy_list = open_json_to_dict("../data/enemy.json")
    
    @staticmethod
    def _check_stop_event():
        """Check if stop event is set from GUI"""
        if hasattr(config, 'stop_event') and config.stop_event.is_set():
            print("Event battle stopped by user request")
            return True
        return False
    
    @staticmethod
    def _get_character_data() -> Tuple[dict, str, str]:
        """Get character data and session info."""
        char_data = flatten_json(config.char_data)
        char_id = char_data["character_data_character_id"]
        session_key = config.login_data["sessionkey"]
        return char_data, char_id, session_key
    
    @staticmethod
    def _check_hack_detection(result: dict, initial_tokens: int) -> None:
        """Check for hack detection and exit if detected."""
        if result.get('account_tokens', float('inf')) < initial_tokens:
            print("Hack detected, exit system immediately")
            sys.exit()
    
    def _wait_with_stop_check(self, seconds: int):
        """Wait for specified seconds while checking stop event."""
        for _ in range(seconds):
            if self._check_stop_event():
                return False
            time.sleep(1)
        return True

    def _send_event_request(
        self,
        event_config: EventConfig,
        method: str,
        parameters: list,
        *,
        delay: Optional[int] = None,
    ):
        """Apply a small delay before each event AMF request."""
        wait_seconds = event_config.delay_between_calls if delay is None else delay
        if wait_seconds > 0 and not self._wait_with_stop_check(wait_seconds):
            return None
        return send_amf_request(method, parameters)

    @staticmethod
    def _response_message(response) -> str:
        """Extract a readable message from AMF responses and faults."""
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
    def _extract_retry_delay(message: str, default_seconds: int = 5) -> int:
        """Return a wait time when the server asks us to slow down."""
        if not message:
            return 0

        lowered = message.lower()
        if "please wait for" in lowered or "rate limited" in lowered or "try again in a few seconds" in lowered:
            match = re.search(r"(\d+)\s*seconds?", lowered)
            if match:
                return int(match.group(1))
            return default_seconds

        return 0
    
    def _prompt_enemy_selection(self, event_config: EventConfig, battle_data: dict = None) -> str:
        """Prompt user to select an enemy."""
        print(f"Choose your enemy to fight:")
        
        for num, (enemy_id, enemy_name) in event_config.enemy_choices.items():
            kill_count = ""
            if battle_data:
                # Try to get kill count from various possible keys
                if 'kill_counts' in battle_data:
                    kill_count = f" ({battle_data['kill_counts'].get(enemy_id, 0)} kills)"
                elif 'yin_kills' in battle_data and enemy_id == "ene_2100":
                    kill_count = f" ({battle_data['yin_kills']} kills)"
                elif 'yang_kills' in battle_data and enemy_id == "ene_2101":
                    kill_count = f" ({battle_data['yang_kills']} kills)"
            
            print(f"{num}. {enemy_name}{kill_count}")
        
        choice = input("What enemy do you want to fight? ")
        enemy_id, _ = event_config.enemy_choices.get(choice, (None, None))
        return enemy_id
    
    def _create_battle_hash(self, char_id: str, enemy_id: str, 
                           battle_code: str, damage: int) -> str:
        """Create battle hash for validation."""
        hash_input = f"{char_id}{enemy_id}{battle_code}{damage}{BATTLE_HASH}"
        return CUCSG.hash(hash_input)
    
    def _execute_battle(self, char_data: dict, char_id: str, session_key: str,
                    enemy_id: str, enemy_data: dict, event_config: EventConfig) -> dict:
        """
        Execute a single battle (simplified version - most logic moved to fight_event).
        This is kept for backward compatibility.
        """
        agility = StatManager.calculate_stats_with_data("agility", char_data)
        enemy_attr = f"id:{enemy_id}|hp:{enemy_data['hp']}|agility:{enemy_data['agility']}"
        
        # Start battle
        hash_input = f"{char_id}{enemy_id}{enemy_attr}{agility}"
        mission_hash = CUCSG.hash(hash_input)
        parameters = [char_id, enemy_id, agility, enemy_attr, mission_hash, session_key]
        
        battle_data = send_amf_request(event_config.get_start_battle_method(), parameters)
        
        if not battle_data or 'code' not in battle_data:
            return {"status": 0, "error": "No battle code"}
        
        # Finish battle
        battle_dmg = 0
        finish_hash = self._create_battle_hash(char_id, enemy_id, battle_data['code'], battle_dmg)
        parameters = [char_id, enemy_id, battle_data['code'], battle_dmg, 
                    finish_hash, BATTLE_HASH, session_key]
        
        result = send_amf_request(event_config.get_finish_battle_method(), parameters)
        save_fight_data(result)
        
        return result
    
    def check_energy(self, event_type):
        """Check available energy for event"""
        if self._check_stop_event():
            return 0
            
        if event_type not in self.EVENT_CONFIGS:
            raise ValueError(f"Unknown event type: {event_type}. "
                           f"Available: {', '.join(self.EVENT_CONFIGS.keys())}")
        
        event_config = self.EVENT_CONFIGS[event_type]
        _, char_id, session_key = self._get_character_data()
        
        # Add delay before checking energy to avoid rate limiting
        # print(f"Waiting {event_config.delay_between_calls} seconds before checking energy...")
        # if not self._wait_with_stop_check(event_config.delay_between_calls):
        #     return 0
        
        parameters = [char_id, session_key]
        battle_data = self._send_event_request(
            event_config,
            event_config.get_battle_data_method(),
            parameters,
        )

        if battle_data is None:
            return 0

        if isinstance(battle_data, dict):
            return battle_data.get('energy', 0)

        error_msg = self._response_message(battle_data)
        print(f"Could not read {event_config.name} energy: {error_msg}")
        return 0

    def _buy_event_energy(self, event_config: EventConfig) -> bool:
        _, char_id, session_key = self._get_character_data()
        direct_refill_apis = {
            "HanamiEvent2026",
            "AnniversaryEvent2026",
            "EasterEvent2026",
            "PhantomKyunokiEvent2026",
            "ChristmasEvent2025",
            "ThanksGivingEvent2025",
        }
        if event_config.api_class == "WorldCupEvent2026":
            print(f"{event_config.name}: buying full energy refill for 50 tokens...")
            result = send_amf_request(f"{event_config.api_class}.refillenergy", [char_id, session_key])
            if isinstance(result, dict) and str(result.get("status")) == "1":
                print(f"{event_config.name}: energy refill successful.")
                return True

            print(f"{event_config.name}: energy refill failed: {self._response_message(result)}")
            return False

        if event_config.api_class in direct_refill_apis:
            print(f"{event_config.name}: buying full energy refill for 50 tokens...")
            result = send_amf_request(f"{event_config.api_class}.refillEnergy", [char_id, session_key])
            if isinstance(result, dict) and str(result.get("status")) == "1":
                print(f"{event_config.name}: energy refill successful.")
                return True

            print(f"{event_config.name}: energy refill failed: {self._response_message(result)}")
            return False

        print(f"No confirmed token refill API is configured for {event_config.name}.")
        return False

    def _event_resource_policy(self, event_type: str) -> tuple[str, int]:
        settings = config.get_sage_global_settings()
        key_map = {
            "aniv": "sage_aniv_event",
            "sakura": "sage_sakura_event",
            "easter": "sage_easter_event",
        }
        prefix = key_map.get(event_type, "sage_event")
        mode = str(settings.get(f"{prefix}_empty_resource_mode") or settings.get("sage_event_empty_resource_mode", "wait")).strip().lower()
        if mode not in {"buy", "wait", "stop"}:
            mode = "wait"
        wait_minutes = max(0, int(settings.get(f"{prefix}_wait_minutes") or settings.get("sage_event_wait_minutes", 30) or 30))
        return mode, wait_minutes

    def _handle_empty_event_energy(self, event_type: str, event_config: EventConfig) -> bool:
        mode, wait_minutes = self._event_resource_policy(event_type)

        if mode == "stop":
            print(f"No energy left for {event_config.name}. Stopping action.")
            return False

        if mode == "buy":
            return self._buy_event_energy(event_config)
        else:
            print(f"No energy left for {event_config.name}. Waiting {wait_minutes} minute(s).")

        if wait_minutes <= 0:
            return False
        return self._wait_with_stop_check(wait_minutes * 60)
    
    def _get_random_enemy_with_retry(self, event_config: EventConfig, char_id: str, 
                                     session_key: str, battle_number: int) -> Optional[Tuple[str, dict]]:
        """
        Get a random enemy ID with retry logic.
        Returns tuple of (enemy_id, enemy_data) or None if failed.
        """
        max_retries = 5
        retry_count = 0
        base_delay = event_config.delay_between_calls
        
        while retry_count < max_retries:
            if retry_count > 0:
                wait_time = base_delay * retry_count
                print(f"Retry {retry_count}/{max_retries} to get enemy (waiting {wait_time}s)...")
                if not self._wait_with_stop_check(wait_time):
                    return None
            
            # Add delay before API call
            print(f"Waiting {base_delay} seconds before requesting enemy {battle_number}...")
            battle_data = self._send_event_request(
                event_config,
                event_config.get_battle_data_method(),
                [char_id, session_key],
                delay=base_delay,
            )
            if battle_data is None:
                return None
            
            # Extract enemy ID
            enemy_id = event_config.get_enemy_from_battle_data(battle_data)
            
            if enemy_id:
                # Get enemy data
                enemy_data = get_data_by_id(enemy_id, self.enemy_list)
                if not enemy_data:
                    print(f"Warning: Using default stats for enemy {enemy_id}")
                    enemy_data = {
                        'hp': 1000,
                        'agility': 50
                    }
                return (enemy_id, enemy_data)
            
            print(f"Failed to get enemy ID, retrying...")
            retry_count += 1
        
        print(f"Failed to get enemy ID after {max_retries} attempts")
        return None
    def _enemy_name_from_id(self, enemy_id):
        data = get_data_by_id(enemy_id, self.enemy_list)
        if not data:
            return str(enemy_id)

        # adjust key if needed (common cases)
        return data.get("name") or data.get("enemy_name") or data.get("boss_name") or str(enemy_id)

    @staticmethod
    def _is_hanami_boss_unlocked(battle_data: dict) -> bool:
        if not isinstance(battle_data, dict):
            return False
        unlock_value = battle_data.get("ene_2122")
        if isinstance(unlock_value, str):
            return unlock_value.lower() == "unlocked"
        return bool(unlock_value)

    def _select_hanami_enemy(self, battle_data: dict, unlocked_base_enemies: set[str]) -> str:
        if self._is_hanami_boss_unlocked(battle_data):
            return random.choice(["ene_2120", "ene_2121", "ene_2122", "ene_2122"])

        for enemy_id in ("ene_2120", "ene_2121"):
            if enemy_id not in unlocked_base_enemies:
                return enemy_id

        return random.choice(["ene_2120", "ene_2121"])
    def fight_event(self, event_type: str, enemy_id: Optional[str] = None, 
                    num_loops: Optional[int] = None) -> None:
        """
        Unified event fight handler for all event types.
        Includes 25-second total delay per battle (start + wait + finish).
        
        Args:
            event_type: Type of event ('cd', 'aniv', 'pumpkin', 'yinyang', 'independence', 'phantom', 'snow')
            enemy_id: Optional enemy ID to fight (if None, uses first available)
            num_loops: Number of battles to execute (if None, uses all available energy)
        """
        # Check stop event at the beginning
        if self._check_stop_event():
            return
            
        if event_type not in self.EVENT_CONFIGS:
            raise ValueError(f"Unknown event type: {event_type}. "
                        f"Available: {', '.join(self.EVENT_CONFIGS.keys())}")
        
        event_config = self.EVENT_CONFIGS[event_type]
        char_data, char_id, session_key = self._get_character_data()
        
        # Check energy first. The wait/buy/stop policy prevents event actions from
        # silently dying when the account is out of event energy.
        available_energy = self.check_energy(event_type)
        while available_energy == 0:
            print(f"{available_energy} energy available for {event_config.name} fights.")
            if not self._handle_empty_event_energy(event_type, event_config):
                return
            available_energy = self.check_energy(event_type)
        print(f"{available_energy} energy available for {event_config.name} fights.")

        # Determine number of battles to execute
        if num_loops is None:
            battles_to_execute = available_energy
        else:
            if num_loops <= 0:
                print(f"⚠️  WARNING: Number of loops must be positive. Requested: {num_loops}")
                return
            
            if num_loops > available_energy:
                print(f"⚠️  WARNING: Requested {num_loops} battles but only {available_energy} energy available.")
                print(f"Cannot proceed. Please reduce the number of loops or wait for energy to regenerate.")
                return
            
            battles_to_execute = num_loops
            print(f"Will execute {battles_to_execute} out of {available_energy} available battles.")
        
        # Define delay constants (in seconds)
        PRE_BATTLE_DELAY = 1    # Delay before starting battle
        POST_START_DELAY = 26   # Delay after starting battle (before finishing)
        POST_BATTLE_DELAY = 3  # Server requires 25 seconds after each battle
        TOTAL_DELAY_PER_BATTLE = PRE_BATTLE_DELAY + POST_START_DELAY + POST_BATTLE_DELAY
        
        # print(f"\n⏱️  Each battle will take approximately {TOTAL_DELAY_PER_BATTLE} seconds total")
        # print(f"   • {PRE_BATTLE_DELAY}s before start")
        # print(f"   • {POST_START_DELAY}s after start")
        # print(f"   • {POST_BATTLE_DELAY}s after finish\n")
        
        # Execute battles
        successful_battles = 0
        failed_attempts = 0
        max_failed_attempts = 10
        hanami_progress_kills = set()
        
        for i in range(battles_to_execute):
            # Check stop event at the start of each battle
            if self._check_stop_event():
                break
            
            print(f"\n{'='*60}")
            print(f"Battle {i+1}/{battles_to_execute} - {event_config.name}")
            print(f"{'='*60}")
            
            # --- PRE-BATTLE DELAY ---
            # print(f"⏳ Pre-battle delay: {PRE_BATTLE_DELAY} seconds...")
            if not self._wait_with_stop_check(PRE_BATTLE_DELAY):
                break
            
            # Get enemy for this battle
            current_enemy_id = None
            current_enemy_data = None
            
            if event_type == "sakura":
                battle_data = self._send_event_request(
                    event_config,
                    event_config.get_battle_data_method(),
                    [char_id, session_key],
                )
                if battle_data is None:
                    break

                current_enemy_id = enemy_id or self._select_hanami_enemy(
                    battle_data,
                    hanami_progress_kills,
                )
                current_enemy_data = get_data_by_id(current_enemy_id, self.enemy_list)
                if not current_enemy_data:
                    print(f"Warning: Could not find enemy data for {current_enemy_id}")
                    current_enemy_data = {"hp": 1, "agility": 1}
                print(f"🎲 Enemy: {self._enemy_name_from_id(current_enemy_id)}")
            elif event_config.is_fixed_boss:
                # Fixed boss event (like CD)
                current_enemy_id = event_config.boss_id
                current_enemy_data = {
                    'hp': event_config.boss_hp,
                    'agility': event_config.boss_agility
                }
                #print(f"🎯 Boss: {current_enemy_id}")
                print(f"🎯 Boss: {self._enemy_name_from_id(current_enemy_id)}")
            elif event_config.is_random_enemy:
                # Random enemy event (like Aniv)
                result = self._get_random_enemy_with_retry(event_config, char_id, session_key, i+1)
                if result is None:
                    failed_attempts += 1
                    if failed_attempts >= max_failed_attempts:
                        print(f"❌ Too many consecutive failures ({failed_attempts}). Stopping event.")
                        break
                    continue
                
                current_enemy_id, current_enemy_data = result
                #print(f"🎲 Enemy: {current_enemy_id}")
                print(f"🎲 Enemy: {self._enemy_name_from_id(current_enemy_id)}")
                failed_attempts = 0
                
            else:
                # Regular event with enemy choices
                if enemy_id:
                    # Use provided enemy_id
                    current_enemy_id = enemy_id
                else:
                    # No enemy_id provided, use first available
                    if event_config.enemy_choices:
                        first_choice = next(iter(event_config.enemy_choices.items()))
                        current_enemy_id = first_choice[1][0]
                        print(f"🎯 Fighting: {first_choice[1][1]}")
                    else:
                        print("❌ No enemy selected and no defaults available.")
                        return
                
                # Get fresh enemy data for each battle
                current_enemy_data = get_data_by_id(current_enemy_id, self.enemy_list)
                if not current_enemy_data:
                    print(f"❌ Invalid enemy ID: {current_enemy_id}")
                    return
                
                #print(f"🎯 Fighting: {current_enemy_id}")
                # print(f"🎯 Fighting: {self._enemy_name_from_id(current_enemy_id)}")
            # Ensure we have valid enemy data
            if not current_enemy_id or not current_enemy_data:
                print("❌ Failed to get valid enemy data")
                failed_attempts += 1
                if failed_attempts >= max_failed_attempts:
                    print(f"❌ Too many consecutive failures ({failed_attempts}). Stopping event.")
                    break
                continue
            
            # Show enemy stats
            print(f"   HP: {current_enemy_data.get('hp', '?')} | AGI: {current_enemy_data.get('agility', '?')}")
            
            initial_tokens = config.all_char['tokens']
            
            # --- START BATTLE ---
            print(f"\n⚔️  Starting battle! Finishing in 25 Second...")
            
            # Calculate agility and create enemy attribute string
            agility = StatManager.calculate_stats_with_data("agility", char_data)
            enemy_attr = f"id:{current_enemy_id}|hp:{current_enemy_data['hp']}|agility:{current_enemy_data['agility']}"
            
            # Create battle hash
            hash_input = f"{char_id}{current_enemy_id}{enemy_attr}{agility}"
            mission_hash = CUCSG.hash(hash_input)
            
            # Start battle parameters
            start_params = [char_id, current_enemy_id, agility, enemy_attr, mission_hash, session_key]
            
            # Handle cooldown/rate-limit responses by retrying the same battle.
            battle_code = None
            while True:
                if event_type == "phantom":
                    battle_data = self._send_event_request(
                        event_config,
                        event_config.get_start_battle_method(),
                        start_params,
                    )
                    if battle_data is None:
                        return

                    if isinstance(battle_data, list) and len(battle_data) >= 2:
                        battle_code = str(battle_data[0])
                        break
                    if isinstance(battle_data, dict) and 'code' in battle_data:
                        battle_code = battle_data['code']
                        break

                    error_msg = self._response_message(battle_data)
                    retry_delay = self._extract_retry_delay(error_msg, default_seconds=event_config.delay_between_calls or 5)
                    if retry_delay > 0:
                        print(f"⏳ Start battle delayed by server. Waiting {retry_delay} seconds...")
                        if not self._wait_with_stop_check(retry_delay):
                            return
                        continue

                    print(f"❌ Unexpected battle data format: {battle_data}")
                    failed_attempts += 1
                    break
                else:
                    battle_data = self._send_event_request(
                        event_config,
                        event_config.get_start_battle_method(),
                        start_params,
                    )
                    if battle_data is None:
                        return

                    if isinstance(battle_data, dict) and 'code' in battle_data:
                        battle_code = battle_data['code']
                        break

                    error_msg = self._response_message(battle_data)
                    retry_delay = self._extract_retry_delay(error_msg, default_seconds=event_config.delay_between_calls or 5)
                    if retry_delay > 0:
                        print(f"⏳ Start battle delayed by server. Waiting {retry_delay} seconds...")
                        if not self._wait_with_stop_check(retry_delay):
                            return
                        continue

                    print(f"❌ Failed to start battle: {battle_data}")
                    failed_attempts += 1
                    break

            if not battle_code:
                if failed_attempts >= max_failed_attempts:
                    print(f"❌ Too many consecutive failures ({failed_attempts}). Stopping event.")
                    break
                continue
            
            # print(f"✅ Battle started! Code: {battle_code}")
            
            # Check stop event
            if self._check_stop_event():
                print("Battle stopped by user")
                break
            
            # --- POST-START DELAY ---
            # print(f"\n⏳ Waiting {POST_START_DELAY} seconds before finishing...")
            if not self._wait_with_stop_check(POST_START_DELAY):
                break
            
            # Check stop event before finishing
            if self._check_stop_event():
                print("Battle stopped by user")
                break
            
            # --- FINISH BATTLE ---
            print(f"\n🏁 Finishing battle...")
            
            battle_dmg = event_config.finish_damage
            finish_hash = self._create_battle_hash(char_id, current_enemy_id, battle_code, battle_dmg)
            
            # Finish battle parameters
            finish_params = [char_id, current_enemy_id, battle_code, battle_dmg, 
                            finish_hash, BATTLE_HASH, session_key]
            
            result = self._send_event_request(
                event_config,
                event_config.get_finish_battle_method(),
                finish_params,
            )
            if result is None:
                break
            save_fight_data(result)
            
            # Check result
            if isinstance(result, dict) and result.get('status') == 1:
                successful_battles += 1
                xp = result['result'][0] if 'result' in result and len(result['result']) > 0 else '?'
                gold = result['result'][1] if 'result' in result and len(result['result']) > 1 else '?'
                print(f"✅ Victory! XP: {xp} | Gold: {gold}")
                if event_type == "sakura" and current_enemy_id in {"ene_2120", "ene_2121"}:
                    hanami_progress_kills.add(current_enemy_id)
                self._check_hack_detection(result, initial_tokens)
                failed_attempts = 0
            else:
                error_msg = self._response_message(result)
                print(f"❌ Battle failed: {error_msg}")
                failed_attempts += 1
                
                if failed_attempts >= max_failed_attempts:
                    print(f"❌ Too many consecutive failures ({failed_attempts}). Stopping event.")
                    break
            
            # --- POST-BATTLE DELAY (except for last battle) ---
            if i < battles_to_execute - 1:
                print(f"\n⏳ Waiting {POST_BATTLE_DELAY} seconds before next battle...")
                if not self._wait_with_stop_check(POST_BATTLE_DELAY):
                    break
        
        # Clear the stop event when finished
        if hasattr(config, 'stop_event') and not config.stop_event.is_set():
            config.stop_event.clear()
        
        # Summary
        remaining_energy = available_energy - successful_battles
        total_time = successful_battles * TOTAL_DELAY_PER_BATTLE
        
        print(f"\n{'='*60}")
        print(f"📊 FINISHED {event_config.name.upper()}")
        print(f"{'='*60}")
        print(f"  • Battles executed: {successful_battles}/{battles_to_execute}")
        print(f"  • Remaining energy: {remaining_energy}")
        print(f"  • Failed attempts: {failed_attempts}")
        print(f"  • Total time: ~{total_time} seconds ({total_time/60:.1f} minutes)")
        print(f"{'='*60}")
    def start_special_mission(self, num_loops: Optional[int] = None) -> None:
        """
        Start special mission battle for Anniversary Event 2026.
        This is a fixed boss fight against ene_525 that can be done 2 times per day.
        Does not use energy.
        
        Args:
            num_loops: Number of battles to execute (max 2 per day, if None tries both)
        """
        event_type = "aniv"
        
        # Check stop event at the beginning
        if self._check_stop_event():
            return
            
        if event_type not in self.EVENT_CONFIGS:
            raise ValueError(f"Unknown event type: {event_type}")
        
        event_config = self.EVENT_CONFIGS[event_type]
        char_data, char_id, session_key = self._get_character_data()
        
        # Fixed boss for special mission
        boss_id = "ene_525"
        
        # Get boss data from enemy list
        boss_data = get_data_by_id(boss_id, self.enemy_list)
        if not boss_data:
            print(f"Warning: Could not find data for boss {boss_id}, using defaults")
            boss_data = {
                'hp': 150000,  # From your earlier response
                'agility': 160
            }
        
        # Get character agility
        agility = StatManager.calculate_stats_with_data("agility", char_data)
        
        # Create enemy attribute string
        enemy_attr = f"id:{boss_id}|hp:{boss_data['hp']}|agility:{boss_data['agility']}"
        
        print(f"\n{'='*60}")
        print(f"Starting {event_config.name} Special Mission")
        print(f"Boss: {boss_id} (2 attempts per day)")
        print(f"Boss HP: {boss_data['hp']}, Boss Agility: {boss_data['agility']}")
        print(f"Your Agility: {agility}")
        print(f"{'='*60}")
        
        # Determine number of battles to execute
        if num_loops is None:
            battles_to_execute = 2  # Max 2 per day
        else:
            if num_loops <= 0:
                print(f"⚠️  WARNING: Number of battles must be positive. Requested: {num_loops}")
                return
            battles_to_execute = min(num_loops, 2)  # Never more than 2
            if battles_to_execute < num_loops:
                print(f"⚠️  Special missions are limited to 2 per day. Will execute {battles_to_execute}.")
        
        print(f"Will attempt {battles_to_execute} special mission battle(s).")
        
        # Execute special mission battles
        successful_battles = 0
        failed_attempts = 0
        max_failed_attempts = 3
        
        for i in range(battles_to_execute):
            # Check stop event at the start of each battle
            if self._check_stop_event():
                break
            
            print(f"\n{'─'*40}")
            print(f"Special Mission Battle {i+1}/{battles_to_execute}")
            print(f"{'─'*40}")
            
            # Add delay before API call
            if event_config.delay_between_calls > 0:
                print(f"Waiting {event_config.delay_between_calls} seconds...")
                if not self._wait_with_stop_check(event_config.delay_between_calls):
                    break
            
            # Create battle hash
            hash_input = f"{char_id}{boss_id}{enemy_attr}{agility}"
            mission_hash = CUCSG.hash(hash_input)
            
            # Call startSpecialMission with full parameters
            parameters = [
                char_id,           # character ID
                boss_id,           # boss ID
                agility,           # character agility
                enemy_attr,        # enemy attributes string
                mission_hash,      # calculated hash
                session_key        # session key
            ]
            
            # print(f"DEBUG - Parameters: {parameters}")
            battle_data = send_amf_request("AnniversaryEvent2026.startSpecialMission", parameters)
            
            # print(f"DEBUG - Start special mission response: {battle_data}")
            
            # Check if battle was stopped
            if self._check_stop_event():
                print("Special mission stopped by user")
                break
            
            # Process battle data
            if battle_data and isinstance(battle_data, dict):
                status = battle_data.get('status', 0)
                
                if status == 1:
                    # Success - battle started
                    code = battle_data.get('code')
                    boss_id_response = battle_data.get('boss')
                    battle_hash = battle_data.get('hash')
                    
                    if code and boss_id_response and battle_hash:
                        print(f"✓ Battle started successfully!")
                        print(f"  • Battle Code: {code}")
                        print(f"  • Boss: {boss_id_response}")
                        
                        # Show battle details from body if available
                        if 'body' in battle_data and isinstance(battle_data['body'], list):
                            if len(battle_data['body']) > 0 and isinstance(battle_data['body'][0], list):
                                battle_info = battle_data['body'][0]
                                if len(battle_info) >= 4:
                                    print(f"\n  Battle Details:")
                                    print(f"  • Mission ID: {battle_info[0]}")
                                    print(f"  • Enemy ID: {battle_info[1]}")
                                    print(f"  • Enemy Stats: {battle_info[3]}")
                        
                        # Wait before finishing battle
                        print(f"\n  Waiting 10 seconds before finishing battle...")
                        if not self._wait_with_stop_check(10):
                            break
                        
                        # Finish the battle
                        finish_result = self._finish_special_mission(
                            char_id, 
                            boss_id_response, 
                            code, 
                            battle_hash, 
                            session_key
                        )
                        
                        if finish_result and finish_result.get('status') == 1:
                            successful_battles += 1
                            print(f"  ✓ Battle finished successfully!")
                            
                            # Show rewards
                            if 'result' in finish_result and isinstance(finish_result['result'], list):
                                rewards = finish_result['result']
                                if len(rewards) >= 2:
                                    print(f"  • XP gained: {rewards[0]}")
                                    print(f"  • Gold gained: {rewards[1]}")
                            
                            print(f"\n  ✅ Special Mission {i+1} completed!")
                            failed_attempts = 0  # Reset on success
                        else:
                            failed_attempts += 1
                            error_msg = finish_result.get('result', 'Unknown error') if finish_result else "No response"
                            print(f"  ✗ Failed to finish battle: {error_msg}")
                    else:
                        failed_attempts += 1
                        print(f"✗ Battle {i+1} failed: Incomplete battle data")
                        print(f"   Missing code, boss, or hash")
                        
                elif status == 2:
                    # Status 2 means already finished or no attempts left
                    error_msg = battle_data.get('result', 'No attempts left for today')
                    print(f"⚠️  {error_msg}")
                    print("No more special missions available today.")
                    break
                else:
                    failed_attempts += 1
                    error_msg = battle_data.get('result', f'Unknown error (status: {status})')
                    print(f"✗ Battle {i+1} failed: {error_msg}")
                    
                    # If status is 0, it might mean no attempts left
                    if status == 0:
                        print("This might mean no special missions left for today.")
            else:
                failed_attempts += 1
                print(f"✗ Battle {i+1} failed: Unexpected response type: {type(battle_data)}")
            
            # Check if too many failures
            if failed_attempts >= max_failed_attempts:
                print(f"Too many consecutive failures ({failed_attempts}). Stopping special missions.")
                break
            
            # Add delay between battles
            if i < battles_to_execute - 1:
                # print(f"\nWaiting {event_config.delay_between_calls} seconds before next battle...")
                if not self._wait_with_stop_check(event_config.delay_between_calls):
                    break
        
        print(f"\n{'='*60}")
        print(f"Finished {event_config.name} Special Missions:")
        print(f"  • Successful battles: {successful_battles}/{battles_to_execute}")
        print(f"  • Failed attempts: {failed_attempts}")
        if successful_battles < battles_to_execute:
            remaining = battles_to_execute - successful_battles
            print(f"  • {remaining} attempt(s) may be remaining for today")
            print(f"{'='*60}")

    def _finish_special_mission(self, char_id: str, enemy_id: str, 
                               battle_code: str, battle_hash: str, 
                               session_key: str) -> dict:
        """
        Finish a special mission battle.
        """
        try:
            # Create finish battle parameters
            battle_dmg = 0
            
            # Create the finish hash
            finish_hash_input = f"{char_id}{enemy_id}{battle_code}{battle_dmg}{BATTLE_HASH}"
            finish_hash = CUCSG.hash(finish_hash_input)
            
            # Parameters for finishing the battle
            parameters = [char_id, enemy_id, battle_code, battle_dmg, 
                     finish_hash, BATTLE_HASH, session_key]
            
            # Call finishBattle method
            result = send_amf_request("AnniversaryEvent2026.finishSpecialMission", parameters)
            
            # Save fight data
            if result:
                save_fight_data(result)
            
            return result
            
        except Exception as e:
            print(f"Error finishing special mission: {e}")
            return {"status": 0, "error": str(e)}


# Convenience functions for backward compatibility
def fight_cd_event(num_loops: Optional[int] = None):
    """Fight Confronting Death Event."""
    system = EventBattleSystem()
    system.fight_event("cd", num_loops=num_loops)
    
def fight_aniv_event(num_loops: Optional[int] = None):
    """Fight Aniv Event 2026."""
    system = EventBattleSystem()
    system.fight_event("aniv", num_loops=num_loops)

def fight_pumpkin_event(enemy_id: Optional[str] = None, num_loops: Optional[int] = None):
    """Fight Pumpkin/Halloween Event."""
    system = EventBattleSystem()
    system.fight_event("pumpkin", enemy_id, num_loops)

def fight_yinyang_event(enemy_id: Optional[str] = None, num_loops: Optional[int] = None):
    """Fight Yin Yang Event."""
    system = EventBattleSystem()
    system.fight_event("yinyang", enemy_id, num_loops)

def fight_gi_event(enemy_id: Optional[str] = None, num_loops: Optional[int] = None):
    """Fight Independence Event."""
    system = EventBattleSystem()
    system.fight_event("independence", enemy_id, num_loops)
def fight_snow_event(enemy_id: Optional[str] = None, num_loops: Optional[int] = None):
    """Fight Independence Event."""
    system = EventBattleSystem()
    system.fight_event("snow", enemy_id, num_loops)
def fight_thanks_event(enemy_id: Optional[str] = None, num_loops: Optional[int] = None):
    """Fight Independence Event."""
    system = EventBattleSystem()
    system.fight_event("thanks", enemy_id, num_loops)
def fight_sakura_event(num_loops: Optional[int] = None):
    """Fight Sakura Bloom Event 2026 with auto enemy selection."""
    system = EventBattleSystem()
    system.fight_event("sakura", num_loops=num_loops)
def fight_easter_event(enemy_id: Optional[str] = None, num_loops: Optional[int] = None):
    """Fight Easter Event 2026."""
    system = EventBattleSystem()
    system.fight_event("easter", enemy_id, num_loops)
def fight_worldcup_event(enemy_id: Optional[str] = None, num_loops: Optional[int] = None):
    """Fight World Cup Event 2026."""
    system = EventBattleSystem()
    system.fight_event("worldcup", enemy_id, num_loops)
def fight_aniv_special_mission(num_loops: Optional[int] = None):
    """
    Fight Aniv Event 2026 special mission (fixed boss ene_525, 2 times per day).
    Does not use energy.
    
    Args:
        num_loops: Number of battles to execute (max 2 per day, if None tries both)
    
    Example:
        fight_aniv_special_mission()    # Uses both daily attempts
        fight_aniv_special_mission(1)   # Uses 1 attempt
        fight_aniv_special_mission(2)   # Uses both attempts
    """
    system = EventBattleSystem()
    system.start_special_mission(num_loops)
def fight_phantom_event(num_loops: Optional[int] = None):
    """
    Fight Phantom Kyunoki Event 2026.
    
    Args:
        num_loops: Number of battles to execute (if None, uses all available energy)
    
    Example:
        fight_phantom_event()    # Uses all energy
        fight_phantom_event(5)   # Fights 5 times
    """
    system = EventBattleSystem()
    system.fight_event("phantom", num_loops=num_loops)
