from . import config
from .ninjasaga import amf_req as ninjasaga_amf_req
from .rift import amf_req as rift_amf_req
from .sage import amf_req as sage_amf_req
from .shinobi import amf_req as shinobi_amf_req
from .zenshin import amf_req as zenshin_amf_req


def _is_ninjasaga():
    return config.get_current_base_game()["id"] == "ninjasaga"


def _is_rift():
    return config.get_current_base_game()["id"] == "rift"


def _is_shinobi():
    return config.get_current_base_game()["id"] == "shinobi"


def _is_zenshin():
    return config.get_current_base_game()["id"] == "zenshin"


def check_version():
    if _is_ninjasaga():
        return ninjasaga_amf_req.check_version()
    if _is_shinobi():
        return shinobi_amf_req.check_version()
    if _is_zenshin():
        return zenshin_amf_req.check_version()
    if _is_rift():
        return rift_amf_req.check_version()
    return sage_amf_req.check_version()


def get_all_characters():
    if _is_ninjasaga():
        return ninjasaga_amf_req.get_all_characters()
    if _is_shinobi():
        return shinobi_amf_req.get_all_characters()
    if _is_zenshin():
        return zenshin_amf_req.get_all_characters()
    if _is_rift():
        return rift_amf_req.get_all_characters()
    return sage_amf_req.get_all_characters()


def get_character_data(char_id, **kwargs):
    if _is_ninjasaga():
        return ninjasaga_amf_req.get_character_data(char_id, **kwargs)
    if _is_shinobi():
        return shinobi_amf_req.get_character_data(char_id, **kwargs)
    if _is_zenshin():
        return zenshin_amf_req.get_character_data(char_id, **kwargs)
    if _is_rift():
        return rift_amf_req.get_character_data(char_id)
    return sage_amf_req.get_character_data(char_id)


def login(username, password, char_dot__, char_dot__underscore):
    if _is_ninjasaga():
        return ninjasaga_amf_req.login(username, password, char_dot__, char_dot__underscore)
    if _is_shinobi():
        return shinobi_amf_req.login(username, password, char_dot__, char_dot__underscore)
    if _is_zenshin():
        return zenshin_amf_req.login(username, password, char_dot__, char_dot__underscore)
    if _is_rift():
        return rift_amf_req.login(username, password, char_dot__, char_dot__underscore)
    return sage_amf_req.login(username, password, char_dot__, char_dot__underscore)
