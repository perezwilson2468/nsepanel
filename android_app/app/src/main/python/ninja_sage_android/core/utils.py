import json
import os
import sys
import requests
import pyamf
import hashlib
from pyamf import remoting
import zlib, urllib.request
from typing import List
import struct

import binascii
import base64
import time

from . import config
from .. import storage

try:
    from java import jclass
    JavaAesBridge = jclass("com.ninjasage.android.AesBridge")
except Exception:
    JavaAesBridge = None

try:
    from Crypto.Cipher import AES
except Exception:
    AES = None

try:
    import pyaes
except Exception:
    pyaes = None


AES_BLOCK_SIZE = 16
_HTTP_SESSIONS = {}


def _pkcs7_pad(data: bytes, block_size: int = AES_BLOCK_SIZE) -> bytes:
    padding_len = block_size - (len(data) % block_size)
    return data + bytes([padding_len] * padding_len)


def _pkcs7_unpad(data: bytes, block_size: int = AES_BLOCK_SIZE) -> bytes:
    if not data:
        raise ValueError("Invalid padded data")
    padding_len = data[-1]
    if padding_len < 1 or padding_len > block_size:
        raise ValueError("Invalid padding length")
    if data[-padding_len:] != bytes([padding_len] * padding_len):
        raise ValueError("Invalid padding bytes")
    return data[:-padding_len]

def resource_path(relative_path: str) -> str:
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_path = getattr(sys, "_MEIPASS", package_root)
    return os.path.join(base_path, relative_path)


def open_json_to_dict(filename):
    with open(resource_path(filename), 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data

weapon_list = open_json_to_dict("data/weapon-effect.json")
back_item_list = open_json_to_dict("data/back_item-effect.json")
accessory_list = open_json_to_dict("data/accessory-effect.json")

def save_to_json(data,filename):
    with open(storage.state_path(f"{filename}.json"), 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file)

CLASSIC_REQUEST_EXCLUDED_SERVICES = {
    "SystemLogin.checkVersion",
    "SystemLogin.registerUser",
    "SystemLogin.getLoginChallenge",
    "SystemLogin.loginUser",
}
CLASSIC_REQUEST_SECRET = "Classic:Ninja:AMF:Shield:V1"


def _is_classic_profile() -> bool:
    current_profile = config.get_current_amf_profile()
    return current_profile.get("id") == "alternate4"


def _classic_session_key() -> str:
    if isinstance(getattr(config, "login_data", None), dict):
        return str(config.login_data.get("sessionkey") or "")
    return ""


def _classic_should_wrap_request(service: str) -> bool:
    if not _is_classic_profile():
        return False
    if service in CLASSIC_REQUEST_EXCLUDED_SERVICES:
        return False
    return bool(_classic_session_key())


def _classic_next_seq() -> int:
    config.CLASSIC_REQUEST_SEQ = int(getattr(config, "CLASSIC_REQUEST_SEQ", 0) or 0) + 1
    return config.CLASSIC_REQUEST_SEQ


def _classic_nonce() -> str:
    return f"n{int(time.time() * 1000):x}{int.from_bytes(os.urandom(5), 'big'):x}"


def _classic_canonical_json(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ",".join(_classic_canonical_json(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        return "{" + ",".join(
            json.dumps(str(key)) + ":" + _classic_canonical_json(value[key])
            for key in keys
        ) + "}"
    return json.dumps(str(value))


def _classic_request_meta(service: str, params):
    ts = int(time.time())
    nonce = _classic_nonce()
    seq = _classic_next_seq()
    build = str(config.GAME_BUILD_NUM)
    payload_signature = _classic_canonical_json(params or [])
    sign_input = "|".join([
        service,
        payload_signature,
        _classic_session_key(),
        str(ts),
        nonce,
        str(seq),
        build,
    ])
    sig = hashlib.sha256(f"{sign_input}|{CLASSIC_REQUEST_SECRET}".encode("utf-8")).hexdigest()
    return {
        "sig": sig,
        "ts": ts,
        "build": build,
        "nonce": nonce,
        "seq": seq,
    }


def _prepare_amf_params(service, params):
    prepared = list(params) if isinstance(params, list) else [params]
    if _classic_should_wrap_request(service):
        prepared.append({"__cn_req": _classic_request_meta(service, params)})
    return prepared


def _session_cache_key() -> str:
    base_game = config.get_current_base_game()["id"]
    profile = config.get_current_amf_profile()["id"]
    return f"{base_game}:{profile}"


def _get_http_session() -> requests.Session:
    cache_key = _session_cache_key()
    session = _HTTP_SESSIONS.get(cache_key)
    if session is None:
        session = requests.Session()
        _HTTP_SESSIONS[cache_key] = session
    return session


def _is_rift_base_game() -> bool:
    return config.get_current_base_game()["id"] == "rift"


def _rift_warmup(session: requests.Session) -> None:
    if session.headers.get("X-Rift-Warm") == "1":
        return
    try:
        session.get(
            "https://ninjarift.org/",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) AdobeAIR/51.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            timeout=15,
        )
    except Exception:
        pass
    session.headers["X-Rift-Warm"] = "1"


def _build_amf_headers() -> dict:
    headers = {
        "Content-Type": "application/x-amf",
    }
    if _is_rift_base_game():
        headers.update({
            "Accept": "application/x-amf, application/octet-stream, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) AdobeAIR/51.0",
            "Referer": "app:/NinjaRift.swf",
            "Origin": "https://ninjarift.org",
            "X-Flash-Version": "32,0,0,465",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
    return headers


def fetch_json_url(url: str, timeout: int = 20):
    session = _get_http_session()
    headers = {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if _is_rift_base_game():
        _rift_warmup(session)
        headers.update({
            "Referer": "https://ninjarift.org/",
            "Origin": "https://ninjarift.org",
        })

    resp = session.get(url, headers=headers, timeout=timeout)
    content_type = (resp.headers.get("Content-Type") or "").lower()
    content_prefix = resp.content[:120]
    if resp.status_code >= 400 or "text/html" in content_type or content_prefix.lstrip().startswith(b"<!DOCTYPE html"):
        gateway_label = config.get_current_amf_profile().get("label", "Unknown Gateway")
        if _is_rift_base_game() and resp.status_code == 403:
            raise ValueError(f"Ninja Rift library request was blocked with HTTP 403 on {gateway_label}")
        raise ValueError(f"HTTP request failed with status {resp.status_code} while loading JSON from {url}")

    return resp.json()


def send_amf_request(service, params):
    prepared_params = _prepare_amf_params(service, params)
    req = remoting.Request(service, [prepared_params])
    env = remoting.Envelope(pyamf.AMF3)
    env['/0'] = req
    data = remoting.encode(env).getvalue()

    headers = _build_amf_headers()
    session = _get_http_session()
    if _is_rift_base_game():
        _rift_warmup(session)
    resp = session.post(config.GATEWAY, data=data, headers=headers, timeout=20)

    # Decode AMF response
    resp_env = remoting.decode(resp.content)
    _, message = resp_env.bodies[0]
    result = message.body
    return result

def download_resource(resource_name):
    raw = urllib.request.urlopen(f"https://ns-assets.ninjasage.id/static/lib/{resource_name}.bin").read()
    data = json.loads(zlib.decompress(raw).decode("utf-8"))
    with open(storage.state_path(f"{resource_name}.json"), "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=2)

# Function to flatten nested JSON
def flatten_json(nested_json, parent_key='', sep='_'):
    items = []
    for k, v in nested_json.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_json(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            if len(v) > 0 and isinstance(v[0], dict):
                for i, elem in enumerate(v):
                    items.extend(flatten_json(elem, f"{new_key}_{i}", sep=sep).items())
            else:
                items.append((new_key, v))
        else:
            items.append((new_key, v))
    return dict(items)

class StatManager:
    
    check_talent = False
    check_senjutsu = False
    main = None

    def __init__(self, param1=False):
        self.main = param1
        
    @staticmethod
    def calculate_stats_with_data(param1, character):
        
        param2 = character["character_data_character_level"]
        param3 = character["character_points_atrrib_earth"]
        param4 = character["character_points_atrrib_water"]
        param5 = character["character_points_atrrib_wind"]
        param6 = character["character_points_atrrib_lightning"]
        param7 = character["character_sets_weapon"]
        param9 = character["character_sets_accessory"]
        param8 = character["character_sets_back_item"]

        # Buff effects (placeholders for the actual data handling)
        effects_weapon = StatManager.weaponbuffs(param7).get("effects", [])
        effects_back_item = StatManager.backbuffs(param8).get("effects", [])
        effects_accessory = StatManager.accessorybuffs(param9).get("effects", [])
        effects_list = [effects_weapon, effects_back_item, effects_accessory]

        if param1 == "hp":
            base_hp = 60 + int(param2) * 40 + param3 * 30
            return StatManager.checkEquippedSetNew("hp", base_hp, effects_list)

        if param1 == "cp":
            base_cp = 60 + int(param2) * 40 + param4 * 30
            return StatManager.checkEquippedSetNew("cp", base_cp, effects_list)

        if param1 == "sp":
            base_sp = 1000 + int(param2 - 80) * 40
            return StatManager.checkEquippedSetNew("sp", base_sp, effects_list)

        if param1 == "agility":
            base_agility = 9 + int(param2) + int(param5)
            return StatManager.checkEquippedSetNew("agility", base_agility, effects_list)

        if param1 == "critical":
            base_critical = 5 + param6 * 0.4
            return round(StatManager.checkEquippedSetNew("critical", base_critical, effects_list), 1)

        if param1 == "dodge":
            base_dodge = 5 + param5 * 0.4
            return round(StatManager.checkEquippedSetNew("dodge", base_dodge, effects_list), 1)

        if param1 == "purify":
            base_purify = 0 + param4 * 0.4
            return round(StatManager.checkEquippedSetNew("purify", base_purify, effects_list), 1)

        if param1 == "accuracy":
            base_accuracy = 0
            return round(StatManager.checkEquippedSetNew("accuracy", base_accuracy, effects_list), 1)

    @staticmethod
    def checkEquippedSetNew(param1, param2, param3):
        # This is a simplified function to apply max and min effects (placeholders for actual effect logic)
        effect_dict = {
            "agility": {"inc": ["agility_increase", "increase_agility"], "dec": ["agility_decrease", "decrease_agility"]},
            "critical": {"inc": ["critical_increase", "increase_critical"], "dec": ["critical_decrease", "decrease_critical"]},
            "dodge": {"inc": ["dodge_increase", "increase_dodge"], "dec": ["dodge_decrease", "decrease_dodge"]},
            "purify": {"inc": ["purify_increase", "increase_purify"], "dec": ["decrease_purify", "decrease_purify"]},
            "accuracy": {"inc": ["accuracy_increase", "increase_accuracy"], "dec": ["accuracy_decrease", "decrease_accuracy"]},
        }

        if param1 in effect_dict:
            param2 = StatManager.applyEffects(param2, param3, effect_dict[param1]["inc"], effect_dict[param1]["dec"])
        return param2

    @staticmethod
    def applyEffects(param1, param2, inc_effects, dec_effects):
        # Placeholder to apply effects
        for effect in param2:
            for buff in effect:
                if buff.get("effect") in inc_effects:
                    amount = int(buff.get("amount"))
                    param1 += amount
                if buff.get("effect") in dec_effects:
                    amount = int(buff.get("amount"))
                    param1 -= amount
        return param1

    @staticmethod
    def get_data_by_id(data_id, data_list):
        # Search for the enemy in the list by ID
        for data in data_list:
            if data["id"] == data_id:
                return data
        return None  # Return None if not found
    
    @staticmethod
    def weaponbuffs(data_id):
        # weapon_list = open_json_to_dict("weapon-effect.json")
        weapon_data = StatManager.get_data_by_id(data_id, weapon_list)
        if weapon_data:
            return weapon_data
        return {}

    @staticmethod
    def backbuffs(data_id):
        # back_item_list = open_json_to_dict("back_item-effect.json")
        back_data = StatManager.get_data_by_id(data_id, back_item_list)
        if back_data:
            return back_data
        return {}

    @staticmethod
    def accessorybuffs(data_id):
        # accessory_list = open_json_to_dict("accessory-effect.json")
        accessory_data = StatManager.get_data_by_id(data_id, accessory_list)
        if accessory_data:
            return accessory_data
        return {}
    
class IntUtil:
    @staticmethod
    def ror(value: int, shift: int) -> int:
        """Rotate right - 32-bit rotation"""
        return ((value >> shift) | (value << (32 - shift))) & 0xFFFFFFFF
    
    @staticmethod
    def toHex(value: int, include_prefix: bool = False) -> str:
        """Convert integer to hexadecimal string (8 characters)"""
        # Handle negative numbers using two's complement
        if value < 0:
            value = (1 << 32) + value
        return format(value, '08x')


class CUCSG:
    digest = bytearray()
    
    @staticmethod
    def hash(param1: str) -> str:
        loc2 = CUCSG.createBlocksFromString(param1)
        loc3 = CUCSG.hashBlocks(loc2)
        
        # Read 8 integers (32-bit) from the byte array and convert to hex
        result = ""
        for i in range(8):
            value = struct.unpack('>i', loc3[i*4:(i+1)*4])[0]
            result += IntUtil.toHex(value, True)
        
        return result
    
    @staticmethod
    def hashBytes(param1: bytearray) -> str:
        loc2 = CUCSG.createBlocksFromByteArray(param1)
        loc3 = CUCSG.hashBlocks(loc2)
        
        result = ""
        for i in range(8):
            value = struct.unpack('>i', loc3[i*4:(i+1)*4])[0]
            result += IntUtil.toHex(value, True)
        
        return result
    
    @staticmethod
    def hashBlocks(param1: List[int]) -> bytearray:
        # SHA-256 initial hash values
        loc19 = 0x6a09e667  # 1779033703
        loc20 = 0xbb67ae85  # 3144134277  
        loc21 = 0x3c6ef372  # 1013904242
        loc22 = 0xa54ff53a  # 2773480762
        loc23 = 0x510e527f  # 1359893119
        loc24 = 0x9b05688c  # 2600822924
        loc25 = 0x1f83d9ab  # 528734635
        loc26 = 0x5be0cd19  # 1541459225
        
        # SHA-256 constants
        loc27 = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
        ]
        
        loc28 = len(param1)
        loc29 = [0] * 64
        
        loc30 = 0
        while loc30 < loc28:
            loc2 = loc19
            loc3 = loc20
            loc4 = loc21
            loc5 = loc22
            loc6 = loc23
            loc7 = loc24
            loc8 = loc25
            loc9 = loc26
            
            # Message schedule
            loc10 = 0
            while loc10 < 64:
                if loc10 < 16:
                    loc29[loc10] = param1[loc30 + loc10]
                    if loc29[loc10] is None:
                        loc29[loc10] = 0
                    # Ensure 32-bit
                    loc29[loc10] &= 0xFFFFFFFF
                else:
                    loc17 = IntUtil.ror(loc29[loc10 - 15], 7) ^ IntUtil.ror(loc29[loc10 - 15], 18) ^ (loc29[loc10 - 15] >> 3)
                    loc18 = IntUtil.ror(loc29[loc10 - 2], 17) ^ IntUtil.ror(loc29[loc10 - 2], 19) ^ (loc29[loc10 - 2] >> 10)
                    loc29[loc10] = (loc29[loc10 - 16] + loc17 + loc29[loc10 - 7] + loc18) & 0xFFFFFFFF
                
                # Compression function
                loc11 = IntUtil.ror(loc2, 2) ^ IntUtil.ror(loc2, 13) ^ IntUtil.ror(loc2, 22)
                loc12 = (loc2 & loc3) ^ (loc2 & loc4) ^ (loc3 & loc4)
                loc13 = (loc11 + loc12) & 0xFFFFFFFF
                
                loc14 = IntUtil.ror(loc6, 6) ^ IntUtil.ror(loc6, 11) ^ IntUtil.ror(loc6, 25)
                loc15 = (loc6 & loc7) ^ ((~loc6) & loc8)
                loc16 = (loc9 + loc14 + loc15 + loc27[loc10] + loc29[loc10]) & 0xFFFFFFFF
                
                # Update working variables
                loc9 = loc8
                loc8 = loc7
                loc7 = loc6
                loc6 = (loc5 + loc16) & 0xFFFFFFFF
                loc5 = loc4
                loc4 = loc3
                loc3 = loc2
                loc2 = (loc16 + loc13) & 0xFFFFFFFF
                
                loc10 += 1
            
            # Update hash values
            loc19 = (loc19 + loc2) & 0xFFFFFFFF
            loc20 = (loc20 + loc3) & 0xFFFFFFFF
            loc21 = (loc21 + loc4) & 0xFFFFFFFF
            loc22 = (loc22 + loc5) & 0xFFFFFFFF
            loc23 = (loc23 + loc6) & 0xFFFFFFFF
            loc24 = (loc24 + loc7) & 0xFFFFFFFF
            loc25 = (loc25 + loc8) & 0xFFFFFFFF
            loc26 = (loc26 + loc9) & 0xFFFFFFFF
            
            loc30 += 16
        
        # Create final byte array
        loc31 = bytearray()
        for value in [loc19, loc20, loc21, loc22, loc23, loc24, loc25, loc26]:
            loc31.extend(struct.pack('>I', value))
        
        CUCSG.digest = bytearray(loc31)
        return loc31
    
    @staticmethod
    def createBlocksFromByteArray(param1: bytearray) -> List[int]:
        original_pos = 0  # In Python we don't track position the same way
        
        loc3 = []
        loc4 = len(param1) * 8
        loc5 = 0xFF
        loc6 = 0
        
        while loc6 < loc4:
            index = loc6 >> 5
            if index >= len(loc3):
                loc3.extend([0] * (index - len(loc3) + 1))
            
            byte_val = param1[loc6 // 8] if loc6 // 8 < len(param1) else 0
            shift = 24 - (loc6 % 32)
            loc3[index] |= (byte_val & loc5) << shift
            loc6 += 8
        
        # Padding
        index = loc4 >> 5
        if index >= len(loc3):
            loc3.extend([0] * (index - len(loc3) + 1))
        loc3[index] |= 0x80 << (24 - loc4 % 32)
        
        # Length in bits
        final_index = ((loc4 + 64 >> 9) << 4) + 15
        if final_index >= len(loc3):
            loc3.extend([0] * (final_index - len(loc3) + 1))
        loc3[final_index] = loc4
        
        return loc3
    
    @staticmethod
    def createBlocksFromString(param1: str) -> List[int]:
        loc2 = []
        loc3 = len(param1) * 8
        loc4 = 0xFF
        loc5 = 0
        
        while loc5 < loc3:
            index = loc5 >> 5
            if index >= len(loc2):
                loc2.extend([0] * (index - len(loc2) + 1))
            
            char_code = ord(param1[loc5 // 8]) if loc5 // 8 < len(param1) else 0
            shift = 24 - (loc5 % 32)
            loc2[index] |= (char_code & loc4) << shift
            loc5 += 8
        
        # Padding
        index = loc3 >> 5
        if index >= len(loc2):
            loc2.extend([0] * (index - len(loc2) + 1))
        loc2[index] |= 0x80 << (24 - loc3 % 32)
        
        # Length in bits
        final_index = ((loc3 + 64 >> 9) << 4) + 15
        if final_index >= len(loc2):
            loc2.extend([0] * (final_index - len(loc2) + 1))
        loc2[final_index] = loc3
        
        return loc2

def get_data_by_id(data_id,data_list,key="id"):
    # Search for the enemy in the list by ID
    for data in data_list:
        if data[key] == data_id:
            return data
    return None  # Return None if not found


class PM_PRNG:
    """
    A Python implementation of the ActionScript PM_PRNG class:
    
    seed = (seed * 16807) % 2147483647
    nextInt() returns the next seed.
    nextDouble() returns seed / 2147483647.
    """
    def __init__(self, seed=None):
        if seed is None:
            # If no seed provided, use time + random component (similar to AS)
            current_time = int(time.time() * 1000)  # ms
            # Use Python's random just for this fallback seed
            import random
            random_value = int(random.random() * 0.025 * (2**31-1))
            self.seed = current_time ^ random_value
        else:
            self.seed = int(seed)
        # Make sure seed is in valid range [1 .. 2147483646]
        self._modulus = 2147483647
        self._multiplier = 16807
        # Optional: avoid seed = 0
        if self.seed <= 0 or self.seed >= self._modulus:
            # Use a default safe seed
            self.seed = 1

    def gen(self):
        self.seed = (self.seed * self._multiplier) % self._modulus
        return self.seed

    def next_int(self):
        return self.gen()

    def next_double(self):
        return self.gen() / self._modulus

    def next_int_range(self, low, high):
        low_adj = low - 0.4999
        high_adj = high + 0.4999
        return round(low_adj + (high_adj - low_adj)*self.next_double())

    def next_double_range(self, low, high):
        # The AS version uses gen() then divides by modulus
        _val = self.gen() / self._modulus
        return low + (high - low) * _val

def get_random_n_seed(param1, BYTES_LOADED):
    """
    Replicates the ActionScript:
        _loc4_ = param1 % param2["loaderInfo"]["bytesLoaded"];
        prng = new PM_PRNG(_loc4_);
        for 4 times: result += String(prng.nextInt());
        return result;
    """
    seed_val = param1 % BYTES_LOADED
    prng = PM_PRNG(seed_val)
    result = ""
    for _ in range(4):
        result += str(prng.next_int())
    return result

# # Example usage:
# if __name__ == "__main__":
#     param1 = 1762693552
#     BYTES_LOADED = 8228447  # corresponds to param2["loaderInfo"]["bytesLoaded"]
#     seed_string = get_random_n_seed(param1, BYTES_LOADED)
#     print("Generated Random Seed String:", seed_string)

class Crypt:
    @staticmethod
    def encrypt(password: str, key1: str, key2_str: str) -> str:
        """
        Encrypt data using AES-128-CBC
        
        Args:
            password: The data to encrypt
            key1: The encryption key (16 bytes for AES-128)
            key2_str: The IV (Initialization Vector)
        
        Returns:
            Base64 encoded encrypted data
        """
        if JavaAesBridge is not None:
            return str(JavaAesBridge.encryptCbcPkcs5Base64(password, key1, key2_str))

        iv = _pkcs7_pad(key2_str.encode("utf-8"), AES_BLOCK_SIZE)
        data_bytes = password.encode("utf-8")
        key_bytes = key1.encode("utf-8")

        if AES is not None:
            cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
            encrypted_data = cipher.encrypt(_pkcs7_pad(data_bytes, AES.block_size))
            return base64.b64encode(encrypted_data).decode("utf-8")

        if pyaes is None:
            raise RuntimeError("No AES backend available")

        aes = pyaes.AESModeOfOperationCBC(key_bytes, iv=iv)
        encrypter = pyaes.Encrypter(aes, padding=pyaes.PADDING_NONE)
        encrypted_data = encrypter.feed(_pkcs7_pad(data_bytes, AES_BLOCK_SIZE)) + encrypter.feed()
        return base64.b64encode(encrypted_data).decode("utf-8")
    
    @staticmethod
    def decrypt(encrypted_data: str, key1: str, key2_str: str) -> str:
        """
        Decrypt data using AES-128-CBC
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            key1: The encryption key (16 bytes for AES-128)
            key2_str: The IV (Initialization Vector)
        
        Returns:
            Decrypted string
        """
        if JavaAesBridge is not None:
            return str(JavaAesBridge.decryptCbcPkcs5Base64(encrypted_data, key1, key2_str))

        iv = _pkcs7_pad(key2_str.encode("utf-8"), AES_BLOCK_SIZE)
        key_bytes = key1.encode("utf-8")
        encrypted_bytes = base64.b64decode(encrypted_data)

        if AES is not None:
            cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
            decrypted_data = _pkcs7_unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
            return decrypted_data.decode("utf-8")

        if pyaes is None:
            raise RuntimeError("No AES backend available")

        aes = pyaes.AESModeOfOperationCBC(key_bytes, iv=iv)
        decrypter = pyaes.Decrypter(aes, padding=pyaes.PADDING_NONE)
        decrypted_data = decrypter.feed(encrypted_bytes) + decrypter.feed()
        decrypted_data = _pkcs7_unpad(decrypted_data, AES_BLOCK_SIZE)
        return decrypted_data.decode("utf-8")

# Alternative implementation that more closely matches the original ActionScript hex conversion behavior
class CryptExact:
    @staticmethod
    def encrypt(password: str, key1: str, key2_str: str) -> str:
        """
        More exact implementation matching ActionScript hex conversion behavior
        """
        return Crypt.encrypt(password, key1, key2_str)
    
    @staticmethod
    def decrypt(encrypted_data: str, key1: str, key2_str: str) -> str:
        """
        More exact implementation matching ActionScript hex conversion behavior
        """
        return Crypt.decrypt(encrypted_data, key1, key2_str)
    
def save_fight_data(data):
    with open(storage.state_path("fight_logs.txt"), 'a', encoding='utf-8') as file:
        file.write(f"{data}\n")  # Write the data as plain text, followed by a newline
