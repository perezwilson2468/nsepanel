from .utils import (
    send_amf_request,
    save_to_json,
    open_json_to_dict,
    flatten_json,
    get_data_by_id,
    StatManager,
    CUCSG,
    save_fight_data,
)
import struct
from typing import List
from .. import config
import time
import keyboard

gamedata = open_json_to_dict("../data/gamedata.json")
battle_hash = config.BATTLE_HASH


def check_stop_event():
    """Check if stop event is set from GUI"""
    if hasattr(config, 'stop_event') and config.stop_event.is_set():
        print("Eudemon boss fight stopped by user request")
        return True
    return False


def fight_eudemon_boss():
    # Check stop event at the beginning
    if check_stop_event():
        return

    char_data = flatten_json(config.char_data)
    char_id = char_data["character_data_character_id"]
    char_level = char_data["character_data_character_level"]
    session_key = config.login_data["sessionkey"]
    
    parameters = [session_key, char_id]
    available_bosses_data = send_amf_request("EudemonGarden.getData", parameters)
    
    # Check stop event after API call
    if check_stop_event():
        return
    
    if 'data' not in available_bosses_data:
        print("Eudemon boss response missing 'data'; skipping available boss fights.")
        return

    available_bosses_raw = available_bosses_data['data']
    if not available_bosses_raw:
        print("Eudemon boss response contains no boss entries; skipping available boss fights.")
        return

    available_bosses = list(map(int, available_bosses_raw.split(",")))

    boss = get_data_by_id("eudemon", gamedata)["data"]["bosses"]

    # Check if 'q' is pressed at the start of each iteration
    for b in boss:
        # Check stop event for each boss
        if check_stop_event() or keyboard.is_pressed('q'):
            print("Stopped by user")
            break
            
        if int(b['lvl']) > char_level:
            break
            
        for i in range(available_bosses[b['num']]):
            # Check for stop event or 'q' key press in inner loop too
            if check_stop_event() or keyboard.is_pressed('q'):
                print("Stopped by user")
                break
                
            print(f"Fighting boss: {b['name']} (Level: {b['lvl']}) - {i+1}/{available_bosses[b['num']]}")

            parameters = [char_id, b['num'], session_key]
            eudemon_boss_battle_data = send_amf_request("EudemonGarden.startHunting", parameters)
            
            # Check stop event after starting battle
            if check_stop_event():
                break
                
            if eudemon_boss_battle_data['status'] != 1:
                print("finished due to error")
                break
                
            battle_id = str(eudemon_boss_battle_data['code'])
            
            # Wait with stop event checking
            print("Waiting 30 seconds for battle to complete...")
            for wait_seconds in range(30):
                if check_stop_event():
                    print("Battle wait interrupted by user")
                    break
                time.sleep(1)
            else:
                # Only proceed if we didn't break the wait loop
                _loc2_ = CUCSG.hash(str(b['num']) + str(char_id) + battle_id)

                parameters = [char_id, b['num'], battle_id, _loc2_, session_key, battle_hash]

                eudemon_boss_battle_result = send_amf_request("EudemonGarden.finishHunting", parameters)
                save_fight_data(eudemon_boss_battle_result)

                if eudemon_boss_battle_result['status'] == 1:
                    print(f"Successfully defeated boss - Gained XP: {eudemon_boss_battle_result['result'][0]}, Gained Gold: {eudemon_boss_battle_result['result'][1]}")
                else:
                    print(f"Battle failed with status: {eudemon_boss_battle_result['status']}")
            
            # Check stop event after finishing battle
            if check_stop_event():
                break
                
        else:
            continue  # Only executed if inner loop didn't break
        break  # Break outer loop if inner loop broke
    
    # Clear the stop event when finished normally
    if hasattr(config, 'stop_event') and not config.stop_event.is_set():
        config.stop_event.clear()
        
    print("Finished fighting available Eudemon bosses.")
    print("")

