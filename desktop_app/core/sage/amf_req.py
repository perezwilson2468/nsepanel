import base64
import json

from .utils import Crypt, get_random_n_seed, save_to_json, send_amf_request
from .. import config


_LOGIN_KEY_HASH = "40367c3cc999a9f9e951a1d33211545b84b2d5a63933b0020433000c3bb410fb"


def _local_login_version_args(char_dot__, char_dot__underscore):
    """Use bundled client bytes when login is intentionally skipping checkVersion."""
    key = str(char_dot__ or "")
    marker = str(char_dot__underscore or "")
    if len(key.encode("utf-8")) in (16, 24, 32) and marker.isdigit() and marker != "0":
        return key, marker

    try:
        battle_hash = json.loads(base64.b64decode(config.BATTLE_HASH).decode("utf-8"))
        bytes_data = battle_hash.get("bytes", {})
        marker = str(bytes_data.get("____") or marker or "0")
        specific_item = str(bytes_data.get("___") or "")
        if marker and _LOGIN_KEY_HASH in specific_item:
            key = specific_item.split(marker, 1)[1][:16]
        if len(key.encode("utf-8")) in (16, 24, 32) and marker.isdigit():
            return key, marker
    except Exception:
        pass

    return key, marker


def check_version():
    return send_amf_request("SystemLogin.checkVersion", [config.BUILD_NUM])


def get_all_characters():
    account_id = config.login_data["uid"]
    session_key = config.login_data["sessionkey"]
    parameters = [account_id, session_key]
    result = send_amf_request("SystemLogin.getAllCharacters", parameters)
    config.all_char = result

    char_list = []
    if result and "total_characters" in result and "account_data" in result:
        total_chars = result["total_characters"]
        account_data = result["account_data"]

        for i in range(total_chars):
            if i < len(account_data):
                char_data = account_data[i]
                char_id = char_data.get("char_id", 0)
                char_name = char_data.get("character_name", f"Character {i + 1}")
                char_level = char_data.get("character_level", 0)
                char_class = char_data.get("class_id", 0)
                char_exp = char_data.get("character_xp", 0)

                character_info = {
                    "char_id": char_id,
                    "character_id": char_id,
                    "character_name": char_name,
                    "name": char_name,
                    "character_level": char_level,
                    "level": char_level,
                    "class_id": char_class,
                    "character_xp": char_exp,
                    "xp": char_exp,
                    "index": i,
                }
                char_list.append(character_info)
            else:
                print(f"Warning: Index {i} out of range for account_data")
    else:
        print("Unexpected result structure:", result)
        if isinstance(result, list):
            for i, char in enumerate(result):
                if isinstance(char, dict):
                    char_info = {
                        "char_id": char.get("char_id", i),
                        "character_id": char.get("char_id", i),
                        "character_name": char.get("character_name", f"Character {i + 1}"),
                        "name": char.get("character_name", f"Character {i + 1}"),
                        "character_level": char.get("character_level", 0),
                        "level": char.get("character_level", 0),
                        "index": i,
                    }
                    char_list.append(char_info)

    return char_list


def get_character_data(char_id):
    parameters = [char_id, config.login_data["sessionkey"]]
    result = send_amf_request("SystemLogin.getCharacterData", parameters)
    config.char_data = result
    return result


def login(username, password, char_dot__, char_dot__underscore):
    char_dot__, char_dot__underscore = _local_login_version_args(char_dot__, char_dot__underscore)
    encrypted = Crypt.encrypt(password, char_dot__, char_dot__underscore)
    specific_item = (
        char_dot__underscore
        + "40367c3cc999a9f9e951a1d33211545b84b2d5a63933b0020433000c3bb410fb"
        + char_dot__underscore
        + char_dot__underscore
        + char_dot__underscore
        + char_dot__underscore
    )
    random_seed = get_random_n_seed(int(char_dot__underscore), config.BYTES_LOADED)

    params = [
        username,
        encrypted,
        float(char_dot__underscore),
        config.BYTES_LOADED,
        config.BYTES_TOTAL,
        char_dot__,
        specific_item,
        random_seed,
        len(password),
    ]
    return send_amf_request("SystemLogin.loginUser", params)
