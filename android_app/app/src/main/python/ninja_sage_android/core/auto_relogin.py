"""Auto relogin functionality for handling session expiration"""
import time
from . import config, amf_req

def auto_relogin(max_attempts=3, delay=3):
    """
    Attempt to automatically relogin when session expires
    
    Args:
        max_attempts: Maximum number of relogin attempts
        delay: Delay between attempts in seconds
    
    Returns:
        bool: True if relogin successful, False otherwise
    """
    print("Attempting automatic relogin...")
    
    # Check if we have login data in session
    if not hasattr(config, 'quick_login_data') or not config.quick_login_data:
        print("No quick login data found. Cannot auto relogin.")
        return False
    
    profile_id = config.get_current_amf_profile()["id"]
    credentials, _ = config.get_quick_login_credentials(profile_id)
    if not credentials:
        print(f"No quick login data found for AMF profile: {profile_id}")
        return False

    username = credentials.get('username')
    password = credentials.get('password')
    
    if not username or not password:
        print("Invalid quick login data")
        return False
    
    for attempt in range(max_attempts):
        try:
            print(f"Auto relogin attempt {attempt + 1}/{max_attempts}")
            
            # Get game data for version info
            game_data = amf_req.check_version()
            if not game_data or game_data.get('status') != 1:
                print("Failed to get game version")
                time.sleep(delay)
                continue
            
            version_hash = game_data.get('__', '')
            version_underscore = str(int(game_data.get('_', '0')))
            
            # Attempt login
            login_result = amf_req.login(username, password, version_hash, version_underscore)
            
            if login_result and login_result.get('status') == 1:
                print("Auto relogin successful!")
                config.login_data = login_result
                return True
            else:
                print(f"Auto relogin failed. Attempt {attempt + 1}/{max_attempts}")
                time.sleep(delay)
                
        except Exception as e:
            print(f"Error during auto relogin: {e}")
            time.sleep(delay)
    
    print("Max auto relogin attempts reached. Stopping.")
    return False

def handle_session_expired(action_name="current action"):
    """
    Handle session expired error with auto relogin
    
    Args:
        action_name: Name of the action being performed
    
    Returns:
        bool: True if recovered, False if failed
    """
    print(f"Mission failed or session expired. Waiting 20 seconds...")
    time.sleep(20)
    
    success = auto_relogin(max_attempts=3, delay=3)
    
    if success:
        print("Session recovered. Continuing...")
        return True
    else:
        print(f"Auto relogin failed. Stopping {action_name}.")
        return False
