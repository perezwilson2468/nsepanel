from . import amf_req


def bootstrap_session():
    version = amf_req.check_version()
    if not isinstance(version, dict) or str(version.get("status")) != "1":
        print("NinjaSaga bootstrap: version check failed")
        return

    chars_payload = amf_req.get_all_characters()
    chars = []
    if isinstance(chars_payload, dict):
        chars = chars_payload.get("account_data") or chars_payload.get("characters") or []

    if chars:
        first_char = chars[0]
        char_id = None
        if isinstance(first_char, dict):
            char_id = first_char.get("character_id") or first_char.get("char_id")
        else:
            char_id = first_char
        if char_id is not None:
            amf_req.get_character_data(char_id, include_system_data=True, include_extra_data=True)

    print("NinjaSaga session bootstrap completed")
