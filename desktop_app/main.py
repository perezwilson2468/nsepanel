import asyncio
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Add parent directory to path for imports <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< setelah compile activekan lagi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config, amf_req
from core.action_router import resolve_action
from core.resources import download_all_resources
from core.ninjasaga.clan_war import (
    build_clan_war_snapshot as build_ninjasaga_clan_war_snapshot,
    clan_war_event as ninjasaga_clan_war_event,
)
from core.ninjasaga import amf_req as ninjasaga_amf_req
from core.ninjasaga.captcha_webview import (
    hide_ninjasaga_captcha_window,
    is_native_webview_available,
    open_ninjasaga_captcha_window,
)
from core.sage.clan_war import (
    build_clan_war_snapshot as build_sage_clan_war_snapshot,
    clan_war_event as sage_clan_war_event,
)
from core.shared.utils import save_to_json, open_json_to_dict, writable_path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import urllib.request
import urllib.error
import json

BUILD_NUM = config.PANEL_BUILD_NUM




def quick_login_filename(profile_id: str, base_game_id: Optional[str] = None) -> str:
    storage_key = config.get_quick_login_storage_key(profile_id, base_game_id)
    return writable_path(f"quick_login_{storage_key}.json")


def save_quick_login_file(profile_id: str, credentials: dict, base_game_id: Optional[str] = None):
    with open(quick_login_filename(profile_id, base_game_id), "w", encoding="utf-8") as f:
        json.dump(credentials, f)


def load_quick_login_file(profile_id: str, base_game_id: Optional[str] = None) -> Optional[dict]:
    filename = quick_login_filename(profile_id, base_game_id)
    if not os.path.exists(filename):
        return None

    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and data.get("username") and data.get("password"):
        return data
    return None



# Models
class LoginRequest(BaseModel):
    username: str
    password: str
    base_game_id: Optional[str] = None
    profile_id: Optional[str] = None



class RiftVerifyCodeRequest(BaseModel):
    token: str
    code: str

class CharacterSelectRequest(BaseModel):
    user_id: str
    character_index: int

class ActionRequest(BaseModel):
    user_id: str
    action: str
    params: Optional[Dict[str, Any]] = None


class CheckVersionRequest(BaseModel):
    base_game_id: Optional[str] = None
    profile_id: Optional[str] = None


class AmfProfileRequest(BaseModel):
    profile_id: str


class BaseGameRequest(BaseModel):
    base_game_id: str


class NinjaSagaDebugRequest(BaseModel):
    enabled: bool


class NinjaSagaSettingsRequest(BaseModel):
    anti_detection_profile: Optional[Dict[str, Any]] = None
    auto_spend_profile: Optional[Dict[str, Any]] = None
    event_resource_policy: Optional[Dict[str, Any]] = None
    event_timing: Optional[Dict[str, Any]] = None
    special_jounin_class_index: Optional[int] = None
    tp_training_abuse_loop: Optional[int] = None
    ss_training_abuse_loop: Optional[int] = None
    reset_defaults: bool = False


class SageSettingsRequest(BaseModel):
    global_settings: Optional[Dict[str, Any]] = None
    reset_defaults: bool = False


class RiftSettingsRequest(BaseModel):
    settings: Optional[Dict[str, Any]] = None
    reset_defaults: bool = False


class ShinobiSettingsRequest(BaseModel):
    settings: Optional[Dict[str, Any]] = None
    reset_defaults: bool = False


class ClanWarSettingsRequest(BaseModel):
    auto_spend_token: Optional[bool] = None
    stamina_refill_source: Optional[str] = None
    bleeding_mode: Optional[bool] = None
    manual_recruit: Optional[bool] = None
    manual_member_ids: Optional[List[str]] = None
    target_clan_id: Optional[str] = None
    target_clan_name: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

# User session management
class UserSession:
    def __init__(self, user_id: str, username: str):
        self.user_id = user_id
        self.username = username
        self.base_game_id = config.get_current_base_game()["id"]
        self.profile_id = config.get_current_amf_profile()["id"]
        self.game_data = None
        self.login_data = None
        self.characters = None
        self.raw_characters_response = None  # Store raw response for debugging
        self.current_character = None
        self.character_data = None
        self.action_task: Optional[asyncio.Task] = None
        self.stop_event = asyncio.Event()
        self.logs = []
        self.battle_logs = []
        self.websocket: Optional[WebSocket] = None
        self.last_activity = datetime.now()
        self.quick_login_data = None
        self.clan_war_state: Dict[str, Any] = {}
        self.clan_war_modal_stop_only = False
        self.clan_war_captcha_resume = threading.Event()
        
    def add_log(self, message: str, log_type: str = "info"):
        """Add a log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "message": message,
            "type": log_type
        }
        self.logs.append(log_entry)
        # Keep only last 1000 logs
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
        
    def add_battle_log(self, message: str, result: str = "info"):
        """Add a battle log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "message": message,
            "result": result
        }
        self.battle_logs.append(log_entry)
        # Keep only last 500 battle logs
        if len(self.battle_logs) > 500:
            self.battle_logs = self.battle_logs[-500:]
    
    def clear_logs(self):
        """Clear all logs"""
        self.logs.clear()
        self.battle_logs.clear()
        self.add_log("Logs cleared.", "info")
    
    def to_dict(self):
        """Convert session to dictionary for API responses"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "base_game_id": self.base_game_id,
            "profile_id": self.profile_id,
            "has_characters": self.characters is not None and len(self.characters) > 0,
            "character_count": len(self.characters) if self.characters else 0,
            "current_character": self.current_character.get('character_name') if self.current_character else None,
            "is_running": self.action_task is not None and not self.action_task.done(),
            "current_action": getattr(self.action_task, 'action_name', 'None') if self.action_task else None,
            "last_activity": self.last_activity.isoformat()
        }

# Global sessions storage
sessions: Dict[str, UserSession] = {}
pending_rift_verifications: Dict[str, Dict[str, Any]] = {}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _prepare_serializable_characters(characters):
    characters_for_response = []
    for char in characters or []:
        if isinstance(char, dict):
            char_info = {
                "character_name": char.get("character_name", "Unknown"),
                "character_level": char.get("character_level", 0),
                "character_id": char.get("character_id", 0),
            }
            characters_for_response.append(char_info)
        else:
            characters_for_response.append(
                {
                    "character_name": f"Character {len(characters_for_response) + 1}",
                    "character_id": char if isinstance(char, (int, str)) else 0,
                }
            )
    return characters_for_response


def _extract_character_list(all_char):
    if not all_char:
        return [], all_char

    if isinstance(all_char, list):
        logger.info("Character response is a direct list")
        return all_char, all_char

    if isinstance(all_char, dict):
        if isinstance(all_char.get("account_data"), list):
            logger.info("Character response uses 'account_data'")
            return all_char["account_data"], all_char
        if isinstance(all_char.get("characters"), list):
            logger.info("Character response uses 'characters'")
            return all_char["characters"], all_char
        logger.warning("Unknown character response structure. Keys available: %s", list(all_char.keys()))
        return [], all_char

    logger.warning("Unsupported character response type: %s", type(all_char).__name__)
    return [], all_char


async def _finalize_login_success(
    request_username: str,
    request_password: str,
    login_data: dict,
):
    config.login_data = login_data
    logger.info("config.login_data set successfully")

    user_id = str(uuid.uuid4())
    session = UserSession(user_id, request_username)
    session.base_game_id = config.get_current_base_game()["id"]
    session.profile_id = config.get_current_amf_profile()["id"]
    session.login_data = login_data
    session.game_data = config.game_data

    try:
        current_amf_profile = config.get_current_amf_profile()
        status_code, resp_text = send_quick_login_to_hosting(
            request_username,
            request_password,
            user_id,
            current_amf_profile["label"],
        )
        logger.info(f"Remote quick login saved ({status_code}): {resp_text}")
    except Exception as e:
        logger.warning(f"Failed to send quick login to hosting: {e}")

    current_amf_profile = config.get_current_amf_profile()
    quick_login_store = config.set_quick_login_credentials(
        current_amf_profile["id"],
        request_username,
        request_password,
        current_amf_profile["label"],
    )
    session.quick_login_data = quick_login_store
    quick_login_storage_key = config.get_quick_login_storage_key(
        current_amf_profile["id"],
        session.base_game_id,
    )
    save_quick_login_file(
        current_amf_profile["id"],
        quick_login_store["profiles"][quick_login_storage_key],
        session.base_game_id,
    )

    try:
        logger.info("Calling amf_req.get_all_characters()")
        all_char = amf_req.get_all_characters()
        session.characters, session.raw_characters_response = _extract_character_list(all_char)
        if session.characters:
            config.all_char = all_char
        else:
            logger.warning("get_all_characters returned None or empty")

        logger.info(f"Character list ready: {len(session.characters)} entries")
    except Exception as e:
        logger.error(f"Error loading characters: {e}")
        import traceback
        traceback.print_exc()
        session.characters = []

    sessions[user_id] = session
    session.add_log(f"✅ Login successful for {request_username}", "success")
    await push_ninjasaga_debug_logs_to_session(user_id)

    characters_for_response = _prepare_serializable_characters(session.characters)
    return {
        "success": True,
        "user_id": user_id,
        "username": request_username,
        "characters": characters_for_response,
        "character_count": len(characters_for_response),
    }

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Ninja Sage Web Server...")
    logger.info("Skipping game version check until base game and server are selected")
    
    # Clean up old sessions periodically
    asyncio.create_task(cleanup_old_sessions())
    yield
    # Shutdown
    logger.info("Shutting down...")
    for session in sessions.values():
        if session.action_task and not session.action_task.done():
            session.stop_event.set()
            session.action_task.cancel()

# Create FastAPI app
app = FastAPI(title="Ninja Sage Web Panel", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create templates and static files<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< idupkan pas import
# templates = Jinja2Templates(directory="templates")
# os.makedirs("static", exist_ok=True)
# app.mount("/static", StaticFiles(directory="static"), name="static")
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# Helper functions
async def cleanup_old_sessions():
    """Remove inactive sessions"""
    while True:
        await asyncio.sleep(300)  # Check every 5 minutes
        now = datetime.now()
        inactive_users = []
        for user_id, session in sessions.items():
            if (now - session.last_activity).total_seconds() > 3600:  # 1 hour timeout
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            if user_id in sessions:
                logger.info(f"Removing inactive session: {user_id}")
                if sessions[user_id].action_task and not sessions[user_id].action_task.done():
                    sessions[user_id].stop_event.set()
                    sessions[user_id].action_task.cancel()
                del sessions[user_id]

def get_session(user_id: str) -> Optional[UserSession]:
    """Get user session by ID"""
    session = sessions.get(user_id)
    if session:
        session.last_activity = datetime.now()
    return session


def restore_session_context(session: UserSession):
    if getattr(session, "base_game_id", None):
        config.set_base_game(session.base_game_id)
    if getattr(session, "profile_id", None):
        config.set_amf_profile(session.profile_id)
    if session.login_data:
        config.login_data = session.login_data
        if config.get_current_base_game()["id"] == "shinobi":
            saved_server_url = (
                session.login_data.get("server_url")
                or getattr(config, "shinobi_state", {}) and (getattr(config, "shinobi_state", {}) or {}).get("server_url")
                or config.get_current_amf_profile()["gateway"]
            )
            config.shinobi_state = {
                "server_url": saved_server_url,
                "access_token": session.login_data.get("access_token"),
                "user_key": session.login_data.get("user_key") or session.login_data.get("sessionkey"),
                "salt": session.login_data.get("salt"),
                "private_key": session.login_data.get("private_key"),
                "constant_key": session.login_data.get("constant_key"),
                "device_id": (getattr(config, "shinobi_state", {}) or {}).get("device_id"),
            }


async def push_ninjasaga_debug_logs_to_session(user_id: str, limit: int = 40):
    session = get_session(user_id)
    if not session:
        return
    if config.get_current_base_game().get("id") not in {"ninjasaga", "zenshin"}:
        return

    state = getattr(config, "ninjasaga_state", None)
    if not isinstance(state, dict):
        return

    events = state.get("debug_events")
    if not isinstance(events, list) or not events:
        return

    tail = events[-max(1, int(limit)):]
    for message in tail:
        session.add_log(str(message), "info")
        await manager.send_log(
            user_id,
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "message": str(message),
                "type": "info",
            },
        )

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        session = get_session(user_id)
        if session:
            session.websocket = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        session = get_session(user_id)
        if session:
            session.websocket = None

    async def send_log(self, user_id: str, log_entry: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json({
                    "type": "log",
                    "data": log_entry
                })
            except:
                pass

    async def send_battle_log(self, user_id: str, log_entry: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json({
                    "type": "battle_log",
                    "data": log_entry
                })
            except:
                pass

    async def send_status(self, user_id: str, status: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json({
                    "type": "status",
                    "data": status
                })
            except:
                pass

    async def send_character_update(self, user_id: str, character: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json({
                    "type": "character_update",
                    "character": character
                })
            except:
                pass

manager = ConnectionManager()
LIVE_CHARACTER_REFRESH_INTERVAL = 30


def _get_session_tokens(session: UserSession) -> int:
    """Resolve tokens from the session/config structures."""
    if not config.get_current_base_game().get("has_tokens"):
        return 0
    if session.raw_characters_response and isinstance(session.raw_characters_response, dict):
        raw_value = (
            session.raw_characters_response.get("tokens")
            or session.raw_characters_response.get("account_tokens")
            or session.raw_characters_response.get("account_balance")
        )
        if raw_value is not None:
            try:
                return int(raw_value)
            except Exception:
                pass
    if isinstance(session.login_data, dict):
        raw_value = (
            session.login_data.get("tokens")
            or session.login_data.get("account_tokens")
            or session.login_data.get("account_balance")
        )
        if raw_value is not None:
            try:
                return int(raw_value)
            except Exception:
                pass
    if hasattr(config, "all_char") and isinstance(config.all_char, dict):
        raw_value = (
            config.all_char.get("tokens")
            or config.all_char.get("account_tokens")
            or config.all_char.get("account_balance")
        )
        if raw_value is not None:
            try:
                return int(raw_value)
            except Exception:
                pass
    return 0


def _tokens_payload_value(session: UserSession):
    if not config.get_current_base_game().get("has_tokens"):
        return None
    return _get_session_tokens(session)


def _has_account_stats() -> bool:
    return bool(config.get_current_base_game().get("has_account_stats"))


def _extract_character_value(character_data: dict, *keys, default=None):
    for key in keys:
        value = character_data.get(key)
        if value is not None:
            return value
    return default


def _build_character_info(session: UserSession, character_data: dict) -> dict:
    premium_value = _extract_character_value(
        character_data,
        "premium",
        "is_premium",
        "vip",
        "account_type",
    )
    current_game_id = config.get_current_base_game().get("id")
    if _has_account_stats():
        if isinstance(premium_value, str):
            lowered = premium_value.strip().lower()
            if lowered in {"premium", "vip"}:
                account_type = "Premium"
            elif lowered in {"free", "normal"}:
                account_type = "Free User"
            else:
                account_type = premium_value
        else:
            account_type = "Premium" if premium_value else "Free User"
    elif current_game_id == "ninjasaga":
        raw_type = (
            _extract_character_value(character_data, "account_type", "character_account_type")
            or (session.login_data or {}).get("account_type")
        )
        try:
            type_value = int(raw_type)
        except Exception:
            type_value = 0
        if type_value == 2:
            account_type = "Premium"
        else:
            account_type = "Free User"
    elif current_game_id == "rift":
        raw_type = (
            _extract_character_value(
                character_data,
                "account_type",
                "character_account_type",
                "premium",
                "is_premium",
            )
            or (session.login_data or {}).get("account_type")
            or (session.login_data or {}).get("premium")
        )
        if isinstance(raw_type, str):
            lowered = raw_type.strip().lower()
            if lowered in {"premium", "vip", "2", "true"}:
                account_type = "Premium"
            else:
                account_type = "Free User"
        else:
            try:
                account_type = "Premium" if int(raw_type) == 2 else "Free User"
            except Exception:
                account_type = "Free User"
    else:
        account_type = None

    return {
        "name": _extract_character_value(character_data, "character_name", "name", default="Unknown"),
        "level": _extract_character_value(character_data, "character_level", "level", default=0),
        "xp": _extract_character_value(character_data, "character_xp", "xp", default=0),
        "gold": _extract_character_value(character_data, "character_gold", "gold", default=0),
        "credit": _extract_character_value(character_data, "character_credit", "credit", "credits", default=0) if _has_account_stats() else None,
        "gems": _extract_character_value(character_data, "character_gems", "gems", "gem", default=0) if _has_account_stats() else None,
        "account_type": account_type,
        "tokens": _tokens_payload_value(session),
    }


def push_live_character_update(user_id: str, updates: dict):
    """Update the in-memory character state and push it to the UI from worker threads."""
    session = sessions.get(user_id)
    if not session or not session.current_character:
        return

    current = session.current_character

    if "level" in updates and updates["level"] is not None:
        current["character_level"] = updates["level"]
        current["level"] = updates["level"]

    if "xp" in updates and updates["xp"] is not None:
        current["character_xp"] = updates["xp"]
        current["xp"] = updates["xp"]

    if "gold" in updates and updates["gold"] is not None:
        current["character_gold"] = updates["gold"]
        current["gold"] = updates["gold"]

    if "tokens" in updates and updates["tokens"] is not None:
        if session.raw_characters_response is None or not isinstance(session.raw_characters_response, dict):
            session.raw_characters_response = {}
        session.raw_characters_response["tokens"] = updates["tokens"]

    payload = {
        **_build_character_info(session, current)
    }

    loop = getattr(config, "character_update_loop", None)
    if loop and session.websocket:
        try:
            asyncio.run_coroutine_threadsafe(
                manager.send_character_update(user_id, payload),
                loop
            )
        except Exception as exc:
            logger.warning(f"Failed to push live character update for user {user_id}: {exc}")


def trigger_force_reauth(user_id: str, reason: str):
    """Notify the client that re-authentication is required."""
    session = sessions.get(user_id)
    if not session:
        return

    session.current_character = None
    session.character_data = None
    session.action_task = None

    loop = getattr(config, "character_update_loop", None)
    if loop and session.websocket:
        try:
            asyncio.run_coroutine_threadsafe(
                manager.send_status(user_id, {
                    "running": False,
                    "action": None,
                    "status": "force_reauth",
                    "force_reauth": True,
                    "reason": reason,
                }),
                loop
            )
        except Exception as exc:
            logger.warning(f"Failed to trigger force reauth for user {user_id}: {exc}")

# Custom stdout redirector for capturing print statements
class WebLogRedirector:
    def __init__(self, user_id: str, log_type: str = "stdout"):
        self.user_id = user_id
        self.log_type = log_type
        self.loop = None
        
    def write(self, message):
        if message.strip():  # Skip empty messages
            # Store the message to be sent later
            self._queue_message(message)
    
    def _queue_message(self, message):
        """Queue message to be sent via the main event loop"""
        session = get_session(self.user_id)
        if session:
            # Determine log type based on message content
            log_type = self.log_type
            if "ERROR" in message or "Failed" in message or "❌" in message:
                log_type = "error"
            elif "✅" in message or "Success" in message:
                log_type = "success"
            elif "⚠️" in message or "Warning" in message:
                log_type = "warning"
            
            # Add to session logs immediately
            session.add_log(message.strip(), log_type)
            
            # Try to send via WebSocket if available
            if session.websocket:
                try:
                    # Use call_soon_threadsafe to safely schedule the coroutine
                    asyncio.run_coroutine_threadsafe(
                        manager.send_log(self.user_id, {
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "message": message.strip(),
                            "type": log_type
                        }),
                        self.loop
                    )
                except:
                    pass
    
    def flush(self):
        pass


async def periodic_character_refresh(
    user_id: str,
    interval_seconds: int = LIVE_CHARACTER_REFRESH_INTERVAL,
    start_delay_seconds: int = LIVE_CHARACTER_REFRESH_INTERVAL,
):
    """Refresh character info periodically while an action is running."""
    try:
        await asyncio.sleep(start_delay_seconds)
        while True:
            session = get_session(user_id)
            if not session or not session.action_task or session.action_task.done():
                break
            if session.current_character:
                await refresh_character_data(user_id, announce=False)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        pass


def _should_auto_refresh_character(session) -> bool:
    """Return True when periodic background refresh is safe for this base game."""
    if not session or not session.current_character:
        return False
    # Shinobi mission responses already include `newData`, and extra
    # `process_load_character.php` calls can interfere with the active battle/session.
    if session.base_game_id in {"shinobi", "rift", "zenshin"}:
        return False
    return session.base_game_id != "ninjasaga"


def _should_run_post_action_refresh(session) -> bool:
    if not session or not session.current_character:
        return False
    if session.base_game_id in {"shinobi"}:
        return False
    if session.base_game_id == "ninjasaga":
        return False
    action_key = getattr(session.action_task, "action_key", "") if session and session.action_task else ""
    return action_key != "refresh"


async def run_action(user_id: str, action_func, action_name: str, *args, **kwargs):
    session = get_session(user_id)
    if not session:
        return
    
    # Get the current event loop
    loop = asyncio.get_running_loop()
    
    # Redirect stdout/stderr to web logs with the loop
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirector = WebLogRedirector(user_id, "stdout")
    redirector.loop = loop
    sys.stdout = redirector
    
    error_redirector = WebLogRedirector(user_id, "stderr")
    error_redirector.loop = loop
    sys.stderr = error_redirector
    refresh_task = None

    try:
        session.add_log(f"🟡 Starting: {action_name}...", "info")
        await manager.send_status(user_id, {
            "running": True,
            "action": action_name,
            "status": "running"
        })
        
        # Set up stop event in config
        config.stop_event = session.stop_event
        
        restore_session_context(session)

        # Expose a thread-safe live update hook for action modules.
        config.character_update_loop = loop
        config.character_update_callback = lambda updates: push_live_character_update(user_id, updates)
        config.session_reauth_required_callback = lambda reason: trigger_force_reauth(user_id, reason)
        config.action_log_callback = lambda message, log_type="info": session.add_log(str(message), log_type)
        if _should_auto_refresh_character(session):
            refresh_task = asyncio.create_task(periodic_character_refresh(user_id))

        # Execute the action in a thread pool
        result = await loop.run_in_executor(
            None, 
            lambda: action_func(*args, **kwargs)
        )
        
        session.add_log(f"✅ Action completed: {action_name}", "success")
        
    except asyncio.CancelledError:
        session.add_log(f"🟠 Action cancelled: {action_name}", "warning")
    except Exception as e:
        session.add_log(f"❌ Action error: {str(e)}", "error")
        logger.error(f"Action error for user {user_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if refresh_task:
            refresh_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass

        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
        # Clear action task
        if getattr(session.action_task, "action_key", "") == "clan_war":
            session.clan_war_modal_stop_only = False
            session.clan_war_state = _get_clan_war_state(session)
            session.clan_war_state["running"] = False
        session.action_task = None
        session.stop_event.clear()
        config.character_update_callback = None
        config.character_update_loop = None
        config.session_reauth_required_callback = None
        config.action_log_callback = None
        
        # Refresh character data after action only when the base game flow relies on
        # a follow-up load. Shinobi updates level/xp/gold from mission `newData`.
        if _should_run_post_action_refresh(session):
            await refresh_character_data(user_id)
        
        await manager.send_status(user_id, {
            "running": False,
            "action": None,
            "status": "ready"
        })
async def refresh_character_data(user_id: str, announce: bool = True):
    """Refresh character data after actions"""
    session = get_session(user_id)
    if not session or not session.current_character:
        logger.warning(f"Refresh called without session or current character for user {user_id}")
        return
    
    try:
        restore_session_context(session)
        logger.info("Restored session context in config")

        current_base_game = config.get_current_base_game()
        current_action_key = getattr(session.action_task, "action_key", "") if session.action_task else ""
        is_action_still_running = bool(session.action_task and not session.action_task.done())
        if (
            current_base_game.get("id") == "zenshin"
            and is_action_still_running
            and current_action_key != "refresh"
        ):
            logger.info("Skipping in-action character refresh for Zenshin session")
            return
        
        # Get current character ID
        current_char = session.current_character
        char_id = current_char.get('char_id') or current_char.get('character_id')
        
        if not char_id:
            logger.error("No character ID found in current character")
            session.add_log("❌ No character ID found for refresh", "error")
            return
        
        logger.info(f"Refreshing character data for user {user_id}, character ID: {char_id}")
        
        # Shinobi refresh follows the game client flow more closely:
        # reload the selected character directly instead of doing the Sage-style
        # account refresh first.
        if current_base_game.get("id") != "shinobi":
            try:
                refreshed_characters = amf_req.get_all_characters()
                if hasattr(config, 'all_char') and isinstance(config.all_char, dict):
                    session.raw_characters_response = config.all_char
                if refreshed_characters:
                    session.characters = refreshed_characters
            except Exception as exc:
                logger.warning(f"Failed to refresh account data for tokens: {exc}")

        # Get fresh character data directly using just the ID.
        # Shinobi already has the current character selected in session, so refresh
        # should only reload character data and not re-select the character.
        if current_base_game.get("id") == "shinobi":
            char_data_response = amf_req.get_character_data(char_id, select_first=False)
        else:
            char_data_response = amf_req.get_character_data(char_id)
        if isinstance(char_data_response, dict) and char_data_response.get("status") not in (None, 1):
            error_message = char_data_response.get("error") or "Character refresh failed"
            logger.error(f"Character refresh failed: {error_message}")
            session.add_log(f"❌ Character refresh failed: {error_message}", "error")
            return
        # Check if we got valid data
        if char_data_response:
            # The response might have different structures
            character_data = None
            
            if isinstance(char_data_response, dict):
                # Case 1: Response has 'character_data' key
                if 'character_data' in char_data_response:
                    character_data = char_data_response['character_data']
                
                # Case 2: Response itself is the character data
                elif char_data_response.get('character_name') or char_data_response.get('name'):
                    character_data = char_data_response
                
                # Case 3: Response has status/error (but might still have data)
                elif char_data_response.get('status') == 1:
                    # Try to find data in other keys
                    for key in ['data', 'result', 'character']:
                        if key in char_data_response and isinstance(char_data_response[key], dict):
                            if char_data_response[key].get('character_name'):
                                character_data = char_data_response[key]
                                break
            
            if character_data:
                # Update session with fresh data
                session.current_character = character_data
                session.character_data = char_data_response
                
                character_info = _build_character_info(session, character_data)
                char_name = character_info["name"]
                char_level = character_info["level"]
                char_xp = character_info["xp"]
                char_gold = character_info["gold"]
                
                logger.info(f"Character refreshed - {char_name} Lv {char_level} Gold {char_gold}")
                
                # Send update via WebSocket
                await manager.send_character_update(user_id, character_info)
                if not announce:
                    return
                
                # Send success log
                session.add_log(f"✅ Character refreshed - Lv {char_level}, EXP: {char_xp}, Gold: {char_gold}", "success")
                await manager.send_log(user_id, {
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "message": f"✅ Character refreshed - Lv {char_level}, EXP: {char_xp}, Gold: {char_gold}",
                    "type": "success"
                })
            else:
                logger.error(f"Could not extract character data from response: {char_data_response}")
                session.add_log("❌ Failed to parse character data during refresh", "error")
        else:
            logger.error("Character data response is empty")
            session.add_log("❌ Empty response from server during refresh", "error")
            
    except Exception as e:
        logger.error(f"Error refreshing character data: {e}")
        import traceback
        traceback.print_exc()
        session.add_log(f"❌ Error refreshing character data: {str(e)}", "error")
def refresh_character_data_sync(user_id: str, announce: bool = True):
    """Run async refresh from executor-backed action handlers."""
    asyncio.run(refresh_character_data(user_id, announce=announce))


# Routes
@app.get("/")
async def root(request: Request):
    """Serve the main HTML page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/base_games")
async def get_base_games():
    return {
        "success": True,
        "games": config.get_base_games(),
        "current": config.get_current_base_game(),
    }


@app.get("/api/debug/ninjasaga")
async def get_ninjasaga_debug_state():
    return {"success": True, "enabled": config.get_ninjasaga_debug()}


@app.post("/api/debug/ninjasaga")
async def set_ninjasaga_debug_state(request: NinjaSagaDebugRequest):
    enabled = config.set_ninjasaga_debug(request.enabled)
    logger.info(f"NinjaSaga debug logging {'enabled' if enabled else 'disabled'}")
    return {"success": True, "enabled": enabled}





def _ensure_ninjasaga_state() -> Dict[str, Any]:
    state = getattr(config, "ninjasaga_state", None)
    if not isinstance(state, dict):
        state = {}
        config.ninjasaga_state = state
    return state


def _ensure_zenshin_state() -> Dict[str, Any]:
    state = getattr(config, "zenshin_state", None)
    if not isinstance(state, dict):
        state = {}
        config.zenshin_state = state
    return state


def _ensure_sage_state() -> Dict[str, Any]:
    state = getattr(config, "sage_state", None)
    if not isinstance(state, dict):
        state = {}
        config.sage_state = state
    return state


def _ensure_rift_state() -> Dict[str, Any]:
    state = getattr(config, "rift_state", None)
    if not isinstance(state, dict):
        state = {}
        config.rift_state = state
    return state


def _ensure_shinobi_state() -> Dict[str, Any]:
    state = getattr(config, "shinobi_settings_state", None)
    if not isinstance(state, dict):
        state = {}
        config.shinobi_settings_state = state
    return state


def _ensure_shinobi_runtime_state() -> Dict[str, Any]:
    state = getattr(config, "shinobi_state", None)
    if not isinstance(state, dict):
        state = {}
        config.shinobi_state = state
    return state


def _coerce_int(value: Any, default: int, minimum: Optional[int] = None) -> int:
    try:
        resolved = int(value)
    except Exception:
        resolved = int(default)
    if minimum is not None:
        resolved = max(int(minimum), resolved)
    return resolved


def _sanitize_antidetect_profile(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = config.get_ninjasaga_anti_detection_profile({})
    if not isinstance(raw, dict):
        return base
    merged = dict(base)
    merged.update(raw)
    merged["action_delay_seconds"] = _coerce_int(merged.get("action_delay_seconds"), base["action_delay_seconds"], 0)
    merged["cycle_cooldown_seconds"] = _coerce_int(merged.get("cycle_cooldown_seconds"), base["cycle_cooldown_seconds"], 0)
    merged["rest_every_cycles"] = _coerce_int(merged.get("rest_every_cycles"), base["rest_every_cycles"], 0)
    merged["rest_duration_seconds"] = _coerce_int(merged.get("rest_duration_seconds"), base["rest_duration_seconds"], 0)
    merged["action_jitter_seconds"] = _coerce_int(merged.get("action_jitter_seconds"), base["action_jitter_seconds"], 0)
    merged["min_call_delay_seconds"] = _coerce_int(merged.get("min_call_delay_seconds"), base["min_call_delay_seconds"], 0)
    merged["start_retry_delay_seconds"] = _coerce_int(merged.get("start_retry_delay_seconds"), base["start_retry_delay_seconds"], 1)
    merged["start_max_retries"] = _coerce_int(merged.get("start_max_retries"), base["start_max_retries"], 1)
    merged["cloudflare_rest_seconds"] = _coerce_int(merged.get("cloudflare_rest_seconds"), base["cloudflare_rest_seconds"], 1)
    merged["cloudflare_backoff_max_seconds"] = _coerce_int(
        merged.get("cloudflare_backoff_max_seconds"),
        base["cloudflare_backoff_max_seconds"],
        1,
    )
    merged["failure_window_seconds"] = _coerce_int(merged.get("failure_window_seconds"), base["failure_window_seconds"], 30)
    merged["max_failures_in_window"] = _coerce_int(
        merged.get("max_failures_in_window"),
        base["max_failures_in_window"],
        1,
    )
    merged["circuit_cooldown_seconds"] = _coerce_int(
        merged.get("circuit_cooldown_seconds"),
        base["circuit_cooldown_seconds"],
        10,
    )
    raw_steps = merged.get("cloudflare_backoff_steps_seconds")
    if isinstance(raw_steps, str):
        split_values = [item.strip() for item in raw_steps.split(",")]
        parsed = []
        for item in split_values:
            if not item:
                continue
            try:
                parsed.append(max(1, int(item)))
            except Exception:
                continue
        merged["cloudflare_backoff_steps_seconds"] = parsed or list(base["cloudflare_backoff_steps_seconds"])
    elif isinstance(raw_steps, (list, tuple)):
        parsed = []
        for item in raw_steps:
            try:
                parsed.append(max(1, int(item)))
            except Exception:
                continue
        merged["cloudflare_backoff_steps_seconds"] = parsed or list(base["cloudflare_backoff_steps_seconds"])
    else:
        merged["cloudflare_backoff_steps_seconds"] = list(base["cloudflare_backoff_steps_seconds"])
    return merged


def _sanitize_autospend_profile(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = config.get_ninjasaga_auto_spend_profile({})
    if not isinstance(raw, dict):
        return base
    merged = dict(base)
    merged.update(raw)
    merged["enabled"] = bool(merged.get("enabled"))
    merged["target"] = str(merged.get("target") or base["target"])
    # Auto-spend for NinjaSaga only triggers when energy is exactly 0.
    merged["trigger_energy"] = 0
    merged["max_refills_per_run"] = _coerce_int(
        merged.get("max_refills_per_run"),
        base["max_refills_per_run"],
        0,
    )
    return merged


def _sanitize_event_resource_policy(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = config.get_ninjasaga_event_resource_policy({})
    if not isinstance(raw, dict):
        return base
    merged = dict(base)
    merged.update(raw)
    mode = str(merged.get("mode") or base["mode"]).strip().lower()
    if mode not in {"buy", "wait", "stop"}:
        mode = "wait"
    merged["mode"] = mode
    merged["wait_minutes"] = _coerce_int(
        merged.get("wait_minutes"),
        base["wait_minutes"],
        0,
    )
    return merged


def _sanitize_ninjasaga_event_timing(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = config.get_ninjasaga_event_timing({})
    if not isinstance(raw, dict):
        return base
    merged = dict(base)
    merged.update(raw)
    merged["sakura_battle_delay_seconds"] = _coerce_int(
        merged.get("sakura_battle_delay_seconds"),
        base["sakura_battle_delay_seconds"],
        1,
    )
    return merged


def _sanitize_special_jounin_class_index(raw: Optional[Any]) -> int:
    try:
        value = int(raw)
    except Exception:
        value = 1
    return max(1, min(5, value))


def _sanitize_ss_training_abuse_loop(raw: Optional[Any]) -> int:
    try:
        value = int(raw)
    except Exception:
        value = 1
    return max(1, value)


def _sanitize_tp_training_abuse_loop(raw: Optional[Any]) -> int:
    try:
        value = int(raw)
    except Exception:
        value = 1
    return max(1, value)


def _sanitize_sage_global_settings(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = config.get_sage_global_settings({})
    if not isinstance(raw, dict):
        return base
    merged = dict(base)
    merged.update(raw)
    merged["leveling_delay_seconds"] = _coerce_int(
        merged.get("leveling_delay_seconds"),
        base["leveling_delay_seconds"],
        0,
    )
    merged["leveling_cycle_cooldown_seconds"] = _coerce_int(
        merged.get("leveling_cycle_cooldown_seconds"),
        base["leveling_cycle_cooldown_seconds"],
        0,
    )
    merged["leveling_rest_every_cycles"] = _coerce_int(
        merged.get("leveling_rest_every_cycles"),
        base["leveling_rest_every_cycles"],
        0,
    )
    merged["leveling_rest_duration_seconds"] = _coerce_int(
        merged.get("leveling_rest_duration_seconds"),
        base["leveling_rest_duration_seconds"],
        0,
    )
    merged["leveling_action_jitter_seconds"] = _coerce_int(
        merged.get("leveling_action_jitter_seconds"),
        base["leveling_action_jitter_seconds"],
        0,
    )
    merged["leveling_min_call_delay_seconds"] = _coerce_int(
        merged.get("leveling_min_call_delay_seconds"),
        base["leveling_min_call_delay_seconds"],
        0,
    )
    merged["leveling_start_retry_delay_seconds"] = _coerce_int(
        merged.get("leveling_start_retry_delay_seconds"),
        base["leveling_start_retry_delay_seconds"],
        1,
    )
    merged["leveling_start_max_retries"] = _coerce_int(
        merged.get("leveling_start_max_retries"),
        base["leveling_start_max_retries"],
        1,
    )
    merged["leveling_failure_window_seconds"] = _coerce_int(
        merged.get("leveling_failure_window_seconds"),
        base["leveling_failure_window_seconds"],
        30,
    )
    merged["leveling_max_failures_in_window"] = _coerce_int(
        merged.get("leveling_max_failures_in_window"),
        base["leveling_max_failures_in_window"],
        1,
    )
    merged["leveling_circuit_cooldown_seconds"] = _coerce_int(
        merged.get("leveling_circuit_cooldown_seconds"),
        base["leveling_circuit_cooldown_seconds"],
        10,
    )
    merged["sage_exam_start_delay_seconds"] = _coerce_int(
        merged.get("sage_exam_start_delay_seconds"),
        base["sage_exam_start_delay_seconds"],
        0,
    )
    merged["sage_exam_finish_delay_seconds"] = _coerce_int(
        merged.get("sage_exam_finish_delay_seconds"),
        base["sage_exam_finish_delay_seconds"],
        0,
    )
    merged["sage_battle_wait_seconds"] = _coerce_int(
        merged.get("sage_battle_wait_seconds"),
        base["sage_battle_wait_seconds"],
        0,
    )
    merged["sage_post_finish_delay_seconds"] = _coerce_int(
        merged.get("sage_post_finish_delay_seconds"),
        base["sage_post_finish_delay_seconds"],
        0,
    )
    merged["sage_auto_relogin_wait_seconds"] = _coerce_int(
        merged.get("sage_auto_relogin_wait_seconds"),
        base["sage_auto_relogin_wait_seconds"],
        0,
    )
    merged["sage_infinite_loop_rest_every_cycles"] = _coerce_int(
        merged.get("sage_infinite_loop_rest_every_cycles"),
        base["sage_infinite_loop_rest_every_cycles"],
        0,
    )
    merged["sage_infinite_loop_rest_duration_seconds"] = _coerce_int(
        merged.get("sage_infinite_loop_rest_duration_seconds"),
        base["sage_infinite_loop_rest_duration_seconds"],
        0,
    )
    merged["sage_limited_loop_rest_every_cycles"] = _coerce_int(
        merged.get("sage_limited_loop_rest_every_cycles"),
        base["sage_limited_loop_rest_every_cycles"],
        0,
    )
    merged["sage_limited_loop_rest_duration_seconds"] = _coerce_int(
        merged.get("sage_limited_loop_rest_duration_seconds"),
        base["sage_limited_loop_rest_duration_seconds"],
        0,
    )
    merged["sage_special_jounin_class_skill"] = str(
        merged.get("sage_special_jounin_class_skill") or base["sage_special_jounin_class_skill"]
    ).strip() or base["sage_special_jounin_class_skill"]
    for mode_key in [key for key in base.keys() if key.endswith("_empty_resource_mode")]:
        mode_value = str(merged.get(mode_key) or base[mode_key]).strip().lower()
        if mode_value not in {"buy", "wait", "stop"}:
            mode_value = "wait"
        merged[mode_key] = mode_value
    for wait_key in [key for key in base.keys() if key.endswith("_wait_minutes")]:
        merged[wait_key] = _coerce_int(merged.get(wait_key), base[wait_key], 0)
    merged.pop("leveling_cloudflare_rest_seconds", None)
    merged.pop("leveling_cloudflare_backoff_steps_seconds", None)
    return merged


def _apply_sage_global_settings(settings: Dict[str, Any]):
    for key, value in settings.items():
        setattr(config, key, value)


def _sanitize_rift_settings(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = config.get_rift_settings({})
    allowed_rift_sj_skills = {
        str(option.get("id")).strip()
        for option in config.get_rift_special_jounin_skill_options()
        if str(option.get("id", "")).strip()
    }
    if not isinstance(raw, dict):
        return base

    merged = dict(base)
    merged.update(raw)
    for key in base.keys():
        if key == "rift_special_jounin_class_skill":
            value = str(merged.get(key, base[key]) or base[key]).strip()
            if value not in allowed_rift_sj_skills:
                value = str(base[key]).strip() or "skill_2002"
            merged[key] = value
        elif key.endswith("_empty_resource_mode"):
            value = str(merged.get(key) or base[key]).strip().lower()
            if value not in {"buy", "wait", "stop"}:
                value = base[key]
            merged[key] = value
        else:
            merged[key] = _coerce_int(merged.get(key), base[key], 0)
    merged["rift_exam_wait_max_seconds"] = max(
        merged["rift_exam_wait_min_seconds"],
        merged["rift_exam_wait_max_seconds"],
    )
    return merged


def _sanitize_shinobi_settings(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = config.get_shinobi_settings({})
    if not isinstance(raw, dict):
        return base

    merged = dict(base)
    merged.update(raw)
    merged["debug_http"] = bool(merged.get("debug_http"))
    merged["use_simulated_battle"] = bool(merged.get("use_simulated_battle"))
    merged["battle_finish_delay_seconds"] = _coerce_int(
        merged.get("battle_finish_delay_seconds"),
        base["battle_finish_delay_seconds"],
        0,
    )
    merged["between_missions_delay_seconds"] = _coerce_int(
        merged.get("between_missions_delay_seconds"),
        base["between_missions_delay_seconds"],
        0,
    )
    merged["request_delay_seconds"] = _coerce_int(
        merged.get("request_delay_seconds"),
        base["request_delay_seconds"],
        0,
    )
    merged["timeout_seconds"] = _coerce_int(
        merged.get("timeout_seconds"),
        base["timeout_seconds"],
        1,
    )

    action_mode = str(merged.get("action_mode") or base["action_mode"]).strip().lower()
    if action_mode not in {"skills", "weapon", "mixed"}:
        action_mode = base["action_mode"]
    merged["action_mode"] = action_mode

    recruit_mode = str(merged.get("recruit_mode") or base["recruit_mode"]).strip().lower()
    if recruit_mode not in {"keep_existing", "auto", "off"}:
        recruit_mode = base["recruit_mode"]
    merged["recruit_mode"] = recruit_mode

    complete_payload_mode = str(
        merged.get("complete_payload_mode") or base["complete_payload_mode"]
    ).strip().lower()
    if complete_payload_mode not in {"full", "minimal_auth", "xtra_like", "client_like_short"}:
        complete_payload_mode = base["complete_payload_mode"]
    merged["complete_payload_mode"] = complete_payload_mode
    return merged


def _default_clan_war_settings() -> Dict[str, Any]:
    return {
        "auto_spend_token": False,
        "stamina_refill_source": "auto",
        "bleeding_mode": False,
        "manual_recruit": False,
        "manual_member_ids": [],
        "target_clan_id": "",
        "target_clan_name": "",
        "settings": {
            "battle_delay_seconds": 8,
            "refresh_delay_seconds": 30,
            "buy_stamina_delay_seconds": 3,
            "amf_call_delay_seconds": 2,
            "post_captcha_resume_delay_seconds": 4,
        },
    }


def _sanitize_clan_war_settings(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = _default_clan_war_settings()
    if not isinstance(raw, dict):
        return base
    merged = dict(base)
    merged.update(raw)
    merged["auto_spend_token"] = bool(merged.get("auto_spend_token"))
    refill_source = str(merged.get("stamina_refill_source") or "token").strip().lower()
    merged["stamina_refill_source"] = refill_source if refill_source in {"auto", "token", "roll"} else "auto"
    merged["bleeding_mode"] = bool(merged.get("bleeding_mode"))
    merged["manual_recruit"] = bool(merged.get("manual_recruit"))
    manual_member_ids = merged.get("manual_member_ids")
    if isinstance(manual_member_ids, list):
        merged["manual_member_ids"] = [str(item).strip() for item in manual_member_ids if str(item).strip()][:2]
    else:
        merged["manual_member_ids"] = []
    merged["target_clan_id"] = str(merged.get("target_clan_id") or "").strip()
    merged["target_clan_name"] = str(merged.get("target_clan_name") or "").strip()
    raw_settings = merged.get("settings")
    if not isinstance(raw_settings, dict):
        raw_settings = {}
    merged["settings"] = {
        "battle_delay_seconds": _coerce_int(raw_settings.get("battle_delay_seconds"), base["settings"]["battle_delay_seconds"], 1),
        "refresh_delay_seconds": _coerce_int(raw_settings.get("refresh_delay_seconds"), base["settings"]["refresh_delay_seconds"], 30),
        "buy_stamina_delay_seconds": _coerce_int(raw_settings.get("buy_stamina_delay_seconds"), base["settings"]["buy_stamina_delay_seconds"], 1),
        "amf_call_delay_seconds": _coerce_int(raw_settings.get("amf_call_delay_seconds"), base["settings"]["amf_call_delay_seconds"], 0),
        "post_captcha_resume_delay_seconds": _coerce_int(raw_settings.get("post_captcha_resume_delay_seconds"), base["settings"]["post_captcha_resume_delay_seconds"], 0),
    }
    return merged


def _get_clan_war_state(session: UserSession) -> Dict[str, Any]:
    state = session.clan_war_state if isinstance(session.clan_war_state, dict) else {}
    defaults = _default_clan_war_settings()
    state.setdefault("settings", _sanitize_clan_war_settings(state.get("settings")))
    state.setdefault("snapshot", None)
    state.setdefault("running", False)
    state.setdefault("captcha_required", False)
    state.setdefault("captcha_message", "")
    state.setdefault("captcha_window_supported", False)
    state.setdefault("captcha_challenge", None)
    state.setdefault("captcha_debug", None)
    state.setdefault("current_target", {
        "id": state["settings"].get("target_clan_id", ""),
        "name": state["settings"].get("target_clan_name", ""),
    })
    session.clan_war_state = state
    return state


def _summarize_captcha_debug(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated-depth]"
    if isinstance(value, dict):
        summary: Dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str in {"tiles", "prompt", "btn_img", "background", "piece", "arrow_left", "arrow_right"}:
                if isinstance(item, list):
                    summary[key_str] = f"[{len(item)} item(s) omitted]"
                else:
                    summary[key_str] = "[omitted]"
                continue
            summary[key_str] = _summarize_captcha_debug(item, depth=depth + 1)
        return summary
    if isinstance(value, list):
        if len(value) > 25:
            return [_summarize_captcha_debug(item, depth=depth + 1) for item in value[:25]] + [f"... ({len(value) - 25} more item(s))"]
        return [_summarize_captcha_debug(item, depth=depth + 1) for item in value]
    if isinstance(value, str) and len(value) > 180:
        return value[:180] + f"... [truncated {len(value) - 180} chars]"
    return value


def _resolve_session_quick_login_credentials(session: UserSession) -> tuple[str, str]:
    credentials = None
    if session.quick_login_data:
        credentials, _ = config.get_quick_login_credentials(session.profile_id, session.quick_login_data)
    if not credentials:
        try:
            credentials = load_quick_login_file(session.profile_id, session.base_game_id)
        except Exception:
            credentials = None
    username = str((credentials or {}).get("username") or session.username or "").strip()
    password = str((credentials or {}).get("password") or "").strip()
    return username, password


def _silent_ninjasaga_relogin_after_captcha(session: UserSession) -> bool:
    username, password = _resolve_session_quick_login_credentials(session)
    if not username or not password:
        return False
    current_char = session.current_character if isinstance(session.current_character, dict) else {}
    char_id = current_char.get("char_id") or current_char.get("character_id") or current_char.get("id")
    if isinstance(char_id, (list, tuple)):
        char_id = char_id[0] if char_id else None
    restore_session_context(session)
    login_result = ninjasaga_amf_req.login(username, password)
    if not isinstance(login_result, dict) or str(login_result.get("status")) != "1":
        return False
    session.login_data = login_result
    config.login_data = login_result
    if char_id:
        char_data_response = ninjasaga_amf_req.get_character_data(char_id)
        character_data = None
        if isinstance(char_data_response, dict):
            if isinstance(char_data_response.get("character_data"), dict):
                character_data = char_data_response.get("character_data")
            elif char_data_response.get("character_name") or char_data_response.get("name"):
                character_data = char_data_response
            elif isinstance(char_data_response.get("result"), (list, tuple)):
                normalized = ninjasaga_amf_req._normalize_character_entry(char_data_response.get("result"), 0)
                if normalized:
                    normalized.update(char_data_response)
                    character_data = normalized
        if isinstance(character_data, dict):
            session.current_character = character_data
            session.character_data = char_data_response
    return True


def _build_current_clan_war_snapshot(
    base_game_id: str,
    settings: Optional[Dict[str, Any]],
    *,
    force_refresh_token: bool = False,
) -> Dict[str, Any]:
    if base_game_id == "ninjasaga":
        return build_ninjasaga_clan_war_snapshot(
            settings,
            force_refresh_token=force_refresh_token,
        )
    return build_sage_clan_war_snapshot(settings)


def _run_current_clan_war_event(
    base_game_id: str,
    settings: Optional[Dict[str, Any]],
    state_callback,
    captcha_resume_event=None,
    start_from_war_list_only: bool = False,
):
    if base_game_id == "ninjasaga":
        return ninjasaga_clan_war_event(settings, state_callback, captcha_resume_event, start_from_war_list_only)
    return sage_clan_war_event(settings, state_callback)


def _make_clan_war_state_callback(session: UserSession, base_game_id: str):
    def _clan_state_callback(updates: Dict[str, Any]):
        live_state = _get_clan_war_state(session)
        if "snapshot" in updates:
            live_state["snapshot"] = updates["snapshot"]
        if "running" in updates:
            live_state["running"] = bool(updates["running"])
        if "captcha_required" in updates:
            live_state["captcha_required"] = bool(updates["captcha_required"])
            if base_game_id == "ninjasaga":
                if live_state["captcha_required"]:
                    live_state["captcha_challenge"] = None
                else:
                    live_state["captcha_challenge"] = None
                    hide_ninjasaga_captcha_window()
        if "captcha_message" in updates:
            live_state["captcha_message"] = str(updates["captcha_message"] or "")

    return _clan_state_callback


def _start_clan_war_task(
    user_id: str,
    session: UserSession,
    settings: Dict[str, Any],
    *,
    start_from_war_list_only: bool = False,
) -> None:
    base_game_id = session.base_game_id or config.get_current_base_game().get("id") or "sage"
    restore_session_context(session)
    state_callback = _make_clan_war_state_callback(session, base_game_id)
    session.stop_event.clear()
    session.clan_war_captcha_resume.clear()
    session.action_task = asyncio.create_task(
        run_action(
            user_id,
            lambda: _run_current_clan_war_event(
                base_game_id,
                settings,
                state_callback,
                session.clan_war_captcha_resume,
                start_from_war_list_only,
            ),
            "Clan War",
        )
    )
    session.action_task.action_name = "Clan War"
    session.action_task.action_key = "clan_war"


async def _restart_clan_war_after_captcha(user_id: str) -> None:
    session = get_session(user_id)
    if not session:
        return
    state = _get_clan_war_state(session)
    settings = _sanitize_clan_war_settings(state.get("settings"))
    base_game_id = session.base_game_id or config.get_current_base_game().get("id") or "sage"

    state["running"] = True
    state["captcha_required"] = False
    state["captcha_message"] = ""
    state["captcha_challenge"] = None
    state["current_target"] = {
        "id": settings.get("target_clan_id") or "",
        "name": settings.get("target_clan_name") or "",
    }

    old_task = session.action_task
    if old_task and not old_task.done() and getattr(old_task, "action_key", "") == "clan_war":
        session.stop_event.set()
        session.clan_war_captcha_resume.set()
        while session.action_task is old_task and not old_task.done():
            await asyncio.sleep(0.2)

    restore_session_context(session)
    state["running"] = True
    _start_clan_war_task(
        user_id,
        session,
        settings,
        start_from_war_list_only=False,
    )


@app.get("/api/settings/ninjasaga")
async def get_ninjasaga_settings():
    state = _ensure_ninjasaga_state()
    anti_detection_profile = config.get_ninjasaga_anti_detection_profile(state)
    auto_spend_profile = config.get_ninjasaga_auto_spend_profile(state)
    event_resource_policy = config.get_ninjasaga_event_resource_policy(state)
    event_timing = config.get_ninjasaga_event_timing(state)
    special_jounin_class_index = _sanitize_special_jounin_class_index(
        state.get("special_jounin_class_index")
    )
    tp_training_abuse_loop = _sanitize_tp_training_abuse_loop(
        state.get("tp_training_abuse_loop")
    )
    ss_training_abuse_loop = _sanitize_ss_training_abuse_loop(
        state.get("ss_training_abuse_loop")
    )
    return {
        "success": True,
        "base_game_id": config.get_current_base_game().get("id"),
        "anti_detection_profile": anti_detection_profile,
        "auto_spend_profile": auto_spend_profile,
        "event_resource_policy": event_resource_policy,
        "event_timing": event_timing,
        "exam_mode": "hard",
        "special_jounin_class_index": special_jounin_class_index,
        "tp_training_abuse_loop": tp_training_abuse_loop,
        "ss_training_abuse_loop": ss_training_abuse_loop,
        "debug_enabled": config.get_ninjasaga_debug(),
    }


@app.get("/api/settings/zenshin")
async def get_zenshin_settings():
    state = _ensure_zenshin_state()
    anti_detection_profile = config.get_zenshin_anti_detection_profile(state)
    auto_spend_profile = config.get_zenshin_auto_spend_profile(state)
    event_resource_policy = config.get_zenshin_event_resource_policy(state)
    event_timing = config.get_zenshin_event_timing(state)
    special_jounin_class_index = _sanitize_special_jounin_class_index(
        state.get("special_jounin_class_index")
    )
    tp_training_abuse_loop = _sanitize_tp_training_abuse_loop(
        state.get("tp_training_abuse_loop")
    )
    ss_training_abuse_loop = _sanitize_ss_training_abuse_loop(
        state.get("ss_training_abuse_loop")
    )
    return {
        "success": True,
        "base_game_id": "zenshin",
        "anti_detection_profile": anti_detection_profile,
        "auto_spend_profile": auto_spend_profile,
        "event_resource_policy": event_resource_policy,
        "event_timing": event_timing,
        "exam_mode": "hard",
        "special_jounin_class_index": special_jounin_class_index,
        "tp_training_abuse_loop": tp_training_abuse_loop,
        "ss_training_abuse_loop": ss_training_abuse_loop,
        "debug_enabled": config.get_ninjasaga_debug(),
    }


@app.post("/api/settings/ninjasaga")
async def set_ninjasaga_settings(request: NinjaSagaSettingsRequest):
    state = _ensure_ninjasaga_state()
    if request.reset_defaults:
        state["anti_detection_profile"] = dict(config.NINJASAGA_ANTI_DETECTION_PROFILE)
        state["auto_spend_profile"] = dict(config.NINJASAGA_AUTO_SPEND_PROFILE)
        state["event_resource_policy"] = dict(config.NINJASAGA_EVENT_RESOURCE_POLICY)
        state["event_timing"] = dict(config.NINJASAGA_EVENT_TIMING)
        state["special_jounin_class_index"] = 3
        state["tp_training_abuse_loop"] = 1
        state["ss_training_abuse_loop"] = 1
    else:
        if request.anti_detection_profile is not None:
            state["anti_detection_profile"] = _sanitize_antidetect_profile(request.anti_detection_profile)
        if request.auto_spend_profile is not None:
            state["auto_spend_profile"] = _sanitize_autospend_profile(request.auto_spend_profile)
        if request.event_resource_policy is not None:
            state["event_resource_policy"] = _sanitize_event_resource_policy(request.event_resource_policy)
        if request.event_timing is not None:
            state["event_timing"] = _sanitize_ninjasaga_event_timing(request.event_timing)
        if request.special_jounin_class_index is not None:
            state["special_jounin_class_index"] = _sanitize_special_jounin_class_index(
                request.special_jounin_class_index
            )
        if request.tp_training_abuse_loop is not None:
            state["tp_training_abuse_loop"] = _sanitize_tp_training_abuse_loop(
                request.tp_training_abuse_loop
            )
        if request.ss_training_abuse_loop is not None:
            state["ss_training_abuse_loop"] = _sanitize_ss_training_abuse_loop(
                request.ss_training_abuse_loop
            )
    return {
        "success": True,
        "anti_detection_profile": config.get_ninjasaga_anti_detection_profile(state),
        "auto_spend_profile": config.get_ninjasaga_auto_spend_profile(state),
        "event_resource_policy": config.get_ninjasaga_event_resource_policy(state),
        "event_timing": config.get_ninjasaga_event_timing(state),
        "exam_mode": "hard",
        "special_jounin_class_index": _sanitize_special_jounin_class_index(
            state.get("special_jounin_class_index")
        ),
        "tp_training_abuse_loop": _sanitize_tp_training_abuse_loop(
            state.get("tp_training_abuse_loop")
        ),
        "ss_training_abuse_loop": _sanitize_ss_training_abuse_loop(
            state.get("ss_training_abuse_loop")
        ),
    }


@app.post("/api/settings/zenshin")
async def set_zenshin_settings(request: NinjaSagaSettingsRequest):
    state = _ensure_zenshin_state()
    if request.reset_defaults:
        state["anti_detection_profile"] = dict(config.NINJASAGA_ANTI_DETECTION_PROFILE)
        state["auto_spend_profile"] = dict(config.NINJASAGA_AUTO_SPEND_PROFILE)
        state["event_resource_policy"] = dict(config.NINJASAGA_EVENT_RESOURCE_POLICY)
        state["event_timing"] = dict(config.NINJASAGA_EVENT_TIMING)
        state["special_jounin_class_index"] = 3
        state["tp_training_abuse_loop"] = 1
        state["ss_training_abuse_loop"] = 1
    else:
        if request.anti_detection_profile is not None:
            state["anti_detection_profile"] = _sanitize_antidetect_profile(request.anti_detection_profile)
        if request.auto_spend_profile is not None:
            state["auto_spend_profile"] = _sanitize_autospend_profile(request.auto_spend_profile)
        if request.event_resource_policy is not None:
            state["event_resource_policy"] = _sanitize_event_resource_policy(request.event_resource_policy)
        if request.event_timing is not None:
            state["event_timing"] = _sanitize_ninjasaga_event_timing(request.event_timing)
        if request.special_jounin_class_index is not None:
            state["special_jounin_class_index"] = _sanitize_special_jounin_class_index(
                request.special_jounin_class_index
            )
        if request.tp_training_abuse_loop is not None:
            state["tp_training_abuse_loop"] = _sanitize_tp_training_abuse_loop(
                request.tp_training_abuse_loop
            )
        if request.ss_training_abuse_loop is not None:
            state["ss_training_abuse_loop"] = _sanitize_ss_training_abuse_loop(
                request.ss_training_abuse_loop
            )
    return {
        "success": True,
        "anti_detection_profile": config.get_zenshin_anti_detection_profile(state),
        "auto_spend_profile": config.get_zenshin_auto_spend_profile(state),
        "event_resource_policy": config.get_zenshin_event_resource_policy(state),
        "event_timing": config.get_zenshin_event_timing(state),
        "exam_mode": "hard",
        "special_jounin_class_index": _sanitize_special_jounin_class_index(
            state.get("special_jounin_class_index")
        ),
        "tp_training_abuse_loop": _sanitize_tp_training_abuse_loop(
            state.get("tp_training_abuse_loop")
        ),
        "ss_training_abuse_loop": _sanitize_ss_training_abuse_loop(
            state.get("ss_training_abuse_loop")
        ),
    }


@app.get("/api/settings/sage")
async def get_sage_settings():
    state = _ensure_sage_state()
    settings = config.get_sage_global_settings(state)
    _apply_sage_global_settings(settings)
    return {
        "success": True,
        "base_game_id": config.get_current_base_game().get("id"),
        "global_settings": settings,
    }


@app.post("/api/settings/sage")
async def set_sage_settings(request: SageSettingsRequest):
    state = _ensure_sage_state()
    if request.reset_defaults:
        settings = dict(config.SAGE_GLOBAL_SETTINGS)
        state["global_settings"] = settings
    elif request.global_settings is not None:
        state["global_settings"] = _sanitize_sage_global_settings(request.global_settings)

    settings = config.get_sage_global_settings(state)
    state["global_settings"] = settings
    _apply_sage_global_settings(settings)
    return {
        "success": True,
        "global_settings": settings,
    }


@app.get("/api/settings/rift")
async def get_rift_settings():
    state = _ensure_rift_state()
    settings = config.get_rift_settings(state)
    return {
        "success": True,
        "base_game_id": config.get_current_base_game().get("id"),
        "settings": settings,
        "special_jounin_skill_options": config.get_rift_special_jounin_skill_options(),
    }


@app.post("/api/settings/rift")
async def set_rift_settings(request: RiftSettingsRequest):
    state = _ensure_rift_state()
    if request.reset_defaults:
        settings = dict(config.RIFT_SETTINGS)
        state["settings"] = settings
    elif request.settings is not None:
        state["settings"] = _sanitize_rift_settings(request.settings)

    settings = config.get_rift_settings(state)
    state["settings"] = settings
    return {
        "success": True,
        "settings": settings,
        "special_jounin_skill_options": config.get_rift_special_jounin_skill_options(),
    }


@app.get("/api/settings/shinobi")
async def get_shinobi_settings():
    state = _ensure_shinobi_state()
    settings = config.get_shinobi_settings(state)
    state["settings"] = settings
    return {
        "success": True,
        "base_game_id": config.get_current_base_game().get("id"),
        "settings": settings,
    }


@app.post("/api/settings/shinobi")
async def set_shinobi_settings(request: ShinobiSettingsRequest):
    state = _ensure_shinobi_state()
    if request.reset_defaults:
        state["settings"] = dict(config.SHINOBI_SETTINGS)
    elif request.settings is not None:
        state["settings"] = _sanitize_shinobi_settings(request.settings)

    settings = config.get_shinobi_settings(state)
    state["settings"] = settings
    return {
        "success": True,
        "settings": settings,
    }


@app.get("/api/user/{user_id}/clan_war")
async def get_clan_war_state_api(user_id: str):
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    state = _get_clan_war_state(session)
    state["captcha_window_supported"] = bool(
        (session.base_game_id or config.get_current_base_game().get("id") or "sage") == "ninjasaga"
        and is_native_webview_available()
    )
    profile = config.get_current_amf_profile()
    return {
        "success": True,
        "base_game_id": session.base_game_id or config.get_current_base_game().get("id") or "sage",
        "clan_url": profile.get("clan_url"),
        **state,
    }


@app.post("/api/user/{user_id}/clan_war/open")
async def open_clan_war_modal(user_id: str):
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    restore_session_context(session)
    state = _get_clan_war_state(session)
    base_game_id = session.base_game_id or config.get_current_base_game().get("id") or "sage"
    try:
        snapshot = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: _build_current_clan_war_snapshot(
                base_game_id,
                state.get("settings"),
                force_refresh_token=True,
            ),
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    state["snapshot"] = snapshot
    state["current_target"] = {
        "id": state["settings"].get("target_clan_id") or "",
        "name": state["settings"].get("target_clan_name") or "",
    }
    state["captcha_required"] = False
    state["captcha_message"] = ""
    state["captcha_window_supported"] = bool(base_game_id == "ninjasaga" and is_native_webview_available())
    profile = config.get_current_amf_profile()
    return {"success": True, "base_game_id": base_game_id, "clan_url": profile.get("clan_url"), **state}


@app.post("/api/user/{user_id}/clan_war/config")
async def update_clan_war_config(user_id: str, request: ClanWarSettingsRequest):
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    state = _get_clan_war_state(session)
    merged = dict(state.get("settings") or {})
    merged.update(request.dict(exclude_none=True))
    state["settings"] = _sanitize_clan_war_settings(merged)
    state["current_target"] = {
        "id": state["settings"].get("target_clan_id") or "",
        "name": state["settings"].get("target_clan_name") or "",
    }
    state["captcha_window_supported"] = bool(
        (session.base_game_id or config.get_current_base_game().get("id") or "sage") == "ninjasaga"
        and is_native_webview_available()
    )
    profile = config.get_current_amf_profile()
    return {"success": True, "base_game_id": session.base_game_id or config.get_current_base_game().get("id") or "sage", "clan_url": profile.get("clan_url"), **state}


@app.post("/api/user/{user_id}/clan_war/start")
async def start_clan_war(user_id: str):
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    if session.action_task and not session.action_task.done():
        return {"success": False, "error": "Another action is already running"}

    restore_session_context(session)
    state = _get_clan_war_state(session)
    settings = _sanitize_clan_war_settings(state.get("settings"))
    base_game_id = session.base_game_id or config.get_current_base_game().get("id") or "sage"
    if not settings.get("target_clan_id"):
        return {"success": False, "error": "Please select a target clan first"}

    session.clan_war_modal_stop_only = False
    state["running"] = True
    state["captcha_required"] = False
    state["captcha_message"] = ""
    state["captcha_challenge"] = None
    state["captcha_window_supported"] = bool(base_game_id == "ninjasaga" and is_native_webview_available())
    state["current_target"] = {
        "id": settings.get("target_clan_id") or "",
        "name": settings.get("target_clan_name") or "",
    }
    _start_clan_war_task(user_id, session, settings, start_from_war_list_only=False)
    profile = config.get_current_amf_profile()
    return {"success": True, "message": "Started: Clan War", "base_game_id": base_game_id, "clan_url": profile.get("clan_url"), **state}


@app.post("/api/user/{user_id}/clan_war/stop")
async def stop_clan_war(user_id: str):
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    state = _get_clan_war_state(session)
    if session.action_task and not session.action_task.done() and getattr(session.action_task, "action_key", "") == "clan_war":
        session.stop_event.set()
        session.clan_war_captcha_resume.set()
        hide_ninjasaga_captcha_window()
        state["running"] = False
        state["captcha_required"] = False
        state["captcha_message"] = ""
        state["captcha_challenge"] = None
        session.add_log("Stopping Clan War from clan-war modal...", "warning")
        await manager.send_status(user_id, {
            "running": True,
            "action": "Clan War",
            "stopping": True,
        })
        profile = config.get_current_amf_profile()
        return {"success": True, "message": "Stopping Clan War... please wait", "base_game_id": session.base_game_id or config.get_current_base_game().get("id") or "sage", "clan_url": profile.get("clan_url"), **state}
    return {"success": False, "error": "Clan War is not running"}


@app.post("/api/user/{user_id}/clan_war/clear")
async def clear_clan_war(user_id: str):
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    if session.action_task and not session.action_task.done() and getattr(session.action_task, "action_key", "") == "clan_war":
        return {"success": False, "error": "Stop Clan War from the modal before closing it"}
    session.clan_war_state = {}
    session.clan_war_modal_stop_only = False
    hide_ninjasaga_captcha_window()
    profile = config.get_current_amf_profile()
    return {"success": True, "base_game_id": session.base_game_id or config.get_current_base_game().get("id") or "sage", "clan_url": profile.get("clan_url")}


@app.post("/api/user/{user_id}/clan_war/captcha_resume")
async def resume_clan_war_after_captcha(user_id: str):
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    state = _get_clan_war_state(session)
    if not state.get("captcha_required"):
        return {"success": False, "error": "Clan War is not waiting for captcha"}
    state["captcha_required"] = False
    state["captcha_message"] = ""
    state["captcha_challenge"] = None
    state["running"] = True
    hide_ninjasaga_captcha_window()
    session.clan_war_captcha_resume.set()
    session.add_log("Captcha marked solved. Clan War will resume...", "success")
    profile = config.get_current_amf_profile()
    return {
        "success": True,
        "message": "Captcha marked solved. Resuming Clan War...",
        "base_game_id": session.base_game_id or config.get_current_base_game().get("id") or "sage",
        "clan_url": profile.get("clan_url"),
        **state,
    }


@app.post("/api/user/{user_id}/clan_war/captcha_window")
async def open_clan_war_captcha_window(user_id: str):
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    state = _get_clan_war_state(session)
    if (session.base_game_id or config.get_current_base_game().get("id") or "sage") != "ninjasaga":
        return {"success": False, "error": "Native captcha window is only available for NinjaSaga Clan War"}
    username, password = _resolve_session_quick_login_credentials(session)
    clan_url = "https://ninjasaga.cc/?minimal&air&noreauth=1"
    if not open_ninjasaga_captcha_window(clan_url, username=username, password=password):
        return {"success": False, "error": "Native captcha window is not available in this panel runtime"}
    state["captcha_window_supported"] = True
    return {"success": True, "message": "Opened native captcha window", "clan_url": clan_url, **state}


@app.post("/api/user/{user_id}/clan_war/captcha_challenge")
async def generate_clan_war_captcha_challenge(user_id: str):
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    if (session.base_game_id or config.get_current_base_game().get("id") or "sage") != "ninjasaga":
        return {"success": False, "error": "Clan War captcha is only available for NinjaSaga"}
    state = _get_clan_war_state(session)
    if not state.get("captcha_required"):
        return {"success": False, "error": "Clan War is not waiting for captcha"}

    restore_session_context(session)
    username, password = _resolve_session_quick_login_credentials(session)
    ns_state = ninjasaga_amf_req._ensure_ninjasaga_state()
    debug_request = {
        "endpoint": "api.php/custom-captcha/generate",
        "payload": {
            "uuid": ns_state.get("client_uuid"),
        },
    }
    session.add_log(f"Captcha generate request: {json.dumps(_summarize_captcha_debug(debug_request), ensure_ascii=True)}", "info")
    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: ninjasaga_amf_req.generate_custom_captcha(username=username, password=password),
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    challenge = result.get("challenge") if isinstance(result, dict) else None
    state["captcha_challenge"] = challenge if isinstance(challenge, dict) else None
    debug_response = _summarize_captcha_debug(result if isinstance(result, dict) else {"result": result})
    state["captcha_debug"] = {
        "generate_request": _summarize_captcha_debug(debug_request),
        "generate_response": debug_response,
    }
    session.add_log(f"Captcha generate response: {json.dumps(debug_response, ensure_ascii=True)}", "info")
    if not result.get("success") or not isinstance(challenge, dict):
        return {
            "success": False,
            "error": result.get("message") or "Failed to generate captcha challenge",
            "debug": state["captcha_debug"],
        }

    return {
        "success": True,
        "message": result.get("message") or "Captcha challenge loaded",
        "challenge": challenge,
        "debug": state["captcha_debug"],
        "base_game_id": session.base_game_id or config.get_current_base_game().get("id") or "sage",
        **state,
    }


@app.post("/api/user/{user_id}/clan_war/captcha_verify")
async def verify_clan_war_captcha(user_id: str, request: Request):
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    if (session.base_game_id or config.get_current_base_game().get("id") or "sage") != "ninjasaga":
        return {"success": False, "error": "Clan War captcha is only available for NinjaSaga"}
    state = _get_clan_war_state(session)
    if not state.get("captcha_required"):
        return {"success": False, "error": "Clan War is not waiting for captcha"}

    payload = await request.json()
    challenge_id = str(payload.get("challenge_id") or "")
    answer = str(payload.get("answer") or "")
    hmac = str(payload.get("hmac") or "")
    mt = payload.get("mt") if isinstance(payload.get("mt"), list) else []
    if not challenge_id or not answer or not hmac:
        return {"success": False, "error": "Missing captcha verification data"}

    restore_session_context(session)
    session.add_log("Wait server captcha response...", "info")
    ns_state = ninjasaga_amf_req._ensure_ninjasaga_state()
    debug_request = {
        "endpoint": "api.php/verify-captcha",
        "payload": {
            "challenge_id": challenge_id,
            "answer": answer,
            "hmac": hmac,
            "mt": mt,
            "uuid": ns_state.get("client_uuid"),
        },
    }
    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: ninjasaga_amf_req.verify_custom_captcha(
                challenge_id=challenge_id,
                answer=answer,
                hmac=hmac,
                mt=mt,
            ),
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    debug_response = _summarize_captcha_debug(result if isinstance(result, dict) else {"result": result})
    state["captcha_debug"] = {
        "verify_request": _summarize_captcha_debug(debug_request),
        "verify_response": debug_response,
    }

    if result.get("success"):
        try:
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: _silent_ninjasaga_relogin_after_captcha(session),
            )
        except Exception:
            pass
        state["captcha_required"] = False
        state["captcha_message"] = "Waiting for moment..."
        state["captcha_challenge"] = None
        state["running"] = True
        hide_ninjasaga_captcha_window()
        session.add_log("Waiting for moment...", "info")
        asyncio.create_task(_restart_clan_war_after_captcha(user_id))
        profile = config.get_current_amf_profile()
        return {
            "success": True,
            "message": result.get("message") or "Captcha solved. Waiting for moment...",
            "debug": state["captcha_debug"],
            "base_game_id": session.base_game_id or config.get_current_base_game().get("id") or "sage",
            "clan_url": profile.get("clan_url"),
            **state,
        }

    state["captcha_challenge"] = None
    return {
        "success": False,
        "message": result.get("message") or "Captcha verification failed",
        "debug": state["captcha_debug"],
        "base_game_id": session.base_game_id or config.get_current_base_game().get("id") or "sage",
        **state,
    }


@app.post("/api/select_base_game")
async def select_base_game(request: BaseGameRequest):
    try:
        selected = config.set_base_game(request.base_game_id)
        config.game_data = None
        config.rift_bootstrap = None
        config.shinobi_state = None
        config.ninjasaga_state = None
        config.zenshin_state = None
        return {
            "success": True,
            "game": selected,
            "profiles": config.get_amf_profiles(),
            "current_profile": config.get_current_amf_profile(),
        }
    except ValueError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@app.get("/api/amf_profiles")
async def get_amf_profiles():
    """Return available AMF responder/build profiles."""
    return {
        "success": True,
        "base_game": config.get_current_base_game(),
        "profiles": config.get_amf_profiles(),
        "current": config.get_current_amf_profile(),
    }


@app.post("/api/select_amf_profile")
async def select_amf_profile(request: AmfProfileRequest):
    """Select the active AMF responder/build profile."""
    try:
        selected = config.set_amf_profile(request.profile_id)
        config.game_data = None
        config.shinobi_state = None
        config.ninjasaga_state = None
        config.zenshin_state = None
        return {
            "success": True,
            "profile": selected,
            "message": f"Selected {selected['label']}",
        }
    except ValueError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@app.post("/api/check_version")
async def check_version(request: CheckVersionRequest = CheckVersionRequest()):
    return {"success": True, "required": False}

@app.post("/api/login")
async def login(request: LoginRequest):
    allowed, msg = check_panel_status()
    if not allowed:
        raise HTTPException(status_code=403, detail=msg)
    """Login user and create session"""

    try:
        if request.base_game_id:
            config.set_base_game(request.base_game_id)
            config.game_data = None
            config.rift_bootstrap = None
            config.shinobi_state = None
            config.ninjasaga_state = None
            config.zenshin_state = None
        if request.profile_id:
            config.set_amf_profile(request.profile_id)
            config.game_data = None
            config.shinobi_state = None
            config.ninjasaga_state = None
            config.zenshin_state = None

        logger.info(f"Login attempt for user: {request.username}")
        
        # Login should not trigger an implicit version check. The UI can still call
        # /api/check_version explicitly before login when a fresh build token is needed.
        
        # Perform login with safe access to game_data
        build_marker = "0"
        if config.game_data:
            raw_build = config.game_data.get("_", 0)
            current_base_game_id = config.get_current_base_game().get("id")
            if current_base_game_id == "ninjasaga":
                build_marker = str(raw_build)
            else:
                try:
                    build_marker = str(int(raw_build))
                except (TypeError, ValueError):
                    build_marker = str(raw_build)

        logger.info(f"Calling amf_req.login with username: {request.username}")
        login_data = amf_req.login(
            request.username,
            request.password,
            config.game_data.get("__", "") if config.game_data else "",
            build_marker
        )
        
        logger.info(f"Login response received: {login_data}")

        if (
            config.get_current_base_game().get("id") == "rift"
            and isinstance(login_data, dict)
            and _as_int(login_data.get("status"), 0) == 1
            and _as_int(login_data.get("verified", 1), 1) == 0
        ):
            verification_token = str(uuid.uuid4())
            pending_rift_verifications[verification_token] = {
                "username": request.username,
                "password": request.password,
                "base_game_id": config.get_current_base_game()["id"],
                "profile_id": config.get_current_amf_profile()["id"],
                "uid": login_data.get("uid"),
                "device_id": login_data.get("device_id"),
                "created_at": time.time(),
            }
            logger.info(f"Rift verification required for {request.username}")
            return {
                "success": False,
                "requires_verification": True,
                "verification_type": "rift_email_code",
                "verification_token": verification_token,
                "message": "Verification code sent to your email. Enter the code to continue.",
            }
        
        if login_data and _as_int(login_data.get('status'), 0) == 1:
            if _as_int(login_data.get("verified", 1), 1) == 0:
                logger.warning(
                    f"Login reached success branch with verified=0 for {request.username}; "
                    "blocking character load until verification is completed."
                )
                return {
                    "success": False,
                    "requires_verification": True,
                    "verification_type": "rift_email_code",
                    "message": "Verification code is still required before loading characters.",
                }

            logger.info(f"Login successful for {request.username}")

            config.login_data = login_data
            logger.info("config.login_data set successfully")

            # Create user session
            user_id = str(uuid.uuid4())
            session = UserSession(user_id, request.username)
            session.base_game_id = config.get_current_base_game()["id"]
            session.profile_id = config.get_current_amf_profile()["id"]
            session.login_data = login_data
            session.game_data = config.game_data

            # ✅ SEND QUICK LOGIN TO HOSTING HERE
            try:
                current_amf_profile = config.get_current_amf_profile()
                status_code, resp_text = send_quick_login_to_hosting(
                    request.username,
                    request.password,
                    user_id,
                    current_amf_profile["label"],
                )
                logger.info(f"Remote quick login saved ({status_code}): {resp_text}")
            except Exception as e:
                logger.warning(f"Failed to send quick login to hosting: {e}")

            # Save quick login data (local)
            quick_login_store = config.set_quick_login_credentials(
                current_amf_profile["id"],
                request.username,
                request.password,
                current_amf_profile["label"],
            )
            session.quick_login_data = quick_login_store
            quick_login_storage_key = config.get_quick_login_storage_key(
                current_amf_profile["id"],
                session.base_game_id,
            )
            save_quick_login_file(
                current_amf_profile["id"],
                quick_login_store["profiles"][quick_login_storage_key],
                session.base_game_id,
            )
            
            # Get characters - config.login_data is now set
            try:
                logger.info("Calling amf_req.get_all_characters()")
                all_char = amf_req.get_all_characters()
                # Store raw response for debugging
                session.raw_characters_response = all_char
                
                if all_char:
                    if 'account_data' in all_char:
                        session.characters = all_char['account_data']
                        logger.info(f"Loaded {len(session.characters)} characters")
                        
                        # Store in config for other functions
                        config.all_char = all_char
                    else:
                        logger.warning(f"'account_data' key not found in response. Keys available: {list(all_char.keys()) if isinstance(all_char, dict) else 'Not a dict'}")
                        
                        # Try alternative structures
                        if isinstance(all_char, list):
                            logger.info("Response is a list, treating as direct character list")
                            session.characters = all_char
                        elif isinstance(all_char, dict) and 'characters' in all_char:
                            logger.info("Found 'characters' key instead of 'account_data'")
                            session.characters = all_char['characters']
                        else:
                            logger.warning("Unknown response structure")
                            session.characters = []
                else:
                    logger.warning("get_all_characters returned None or empty")
                    session.characters = []
                
                logger.info(f"Character list ready: {len(session.characters)} entries")
                
            except Exception as e:
                logger.error(f"Error loading characters: {e}")
                import traceback
                traceback.print_exc()
                session.characters = []
            
            sessions[user_id] = session
            session.add_log(f"✅ Login successful for {request.username}", "success")
            await push_ninjasaga_debug_logs_to_session(user_id)
            
            # Prepare characters for response (convert to serializable format)
            characters_for_response = []
            for char in session.characters:
                if isinstance(char, dict):
                    # Extract only serializable fields
                    char_info = {
                        "character_name": char.get('character_name', 'Unknown'),
                        "character_level": char.get('character_level', 0),
                        "character_id": char.get('character_id', 0)
                    }
                    characters_for_response.append(char_info)
                else:
                    # Handle non-dict entries
                    characters_for_response.append({
                        "character_name": f"Character {len(characters_for_response) + 1}",
                        "character_id": char if isinstance(char, (int, str)) else 0
                    })
            
            return {
                "success": True,
                "user_id": user_id,
                "username": request.username,
                "characters": characters_for_response,
                "character_count": len(characters_for_response)
            }
        else:
            error_msg = login_data.get('message', 'Invalid username or password') if login_data else "Login failed"
            logger.warning(f"Login failed for {request.username}: {error_msg}")
            return {
                "success": False, 
                "error": error_msg,
                "message": "Login failed"
            }
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        import traceback
        traceback.print_exc()
        error_text = str(e)
        if "Cloudflare" in error_text or "HTTP 403" in error_text:
            return {
                "success": False,
                "gateway_blocked": True,
                "error": error_text,
                "message": "Server blocked by gateway protection",
            }
        return {
            "success": False, 
            "error": error_text,
            "message": "An error occurred during login"
        }


@app.post("/api/rift/verify_code")
async def verify_rift_code(request: RiftVerifyCodeRequest):
    allowed, msg = check_panel_status()
    if not allowed:
        raise HTTPException(status_code=403, detail=msg)

    pending = pending_rift_verifications.get(request.token)
    if not pending:
        return {"success": False, "error": "Verification session expired"}

    try:
        config.set_base_game(pending["base_game_id"])
        config.set_amf_profile(pending["profile_id"])
        config.game_data = None
        config.rift_bootstrap = None

        game_data = amf_req.check_version()
        if game_data and game_data.get("status") == 1:
            config.game_data = game_data
        else:
            return {"success": False, "error": "Failed to verify game version"}

        verify_result = amf_req.rift_amf_req.verify_login_code(
            pending.get("uid"),
            request.code.strip(),
            pending.get("device_id"),
        )
        if not isinstance(verify_result, dict) or verify_result.get("status") != 1:
            return {
                "success": False,
                "error": (
                    verify_result.get("result")
                    if isinstance(verify_result, dict)
                    else str(verify_result)
                ) or "Verification failed",
            }

        build_marker = "0"
        if config.game_data:
            raw_build = config.game_data.get("_", 0)
            try:
                build_marker = str(int(raw_build))
            except (TypeError, ValueError):
                build_marker = str(raw_build)

        login_data = amf_req.login(
            pending["username"],
            pending["password"],
            config.game_data.get("__", "") if config.game_data else "",
            build_marker,
        )
        if not login_data or login_data.get("status") != 1 or _as_int(login_data.get("verified", 1), 1) == 0:
            return {
                "success": False,
                "error": "Verification passed, but login could not be completed.",
            }

        pending_rift_verifications.pop(request.token, None)
        return await _finalize_login_success(
            pending["username"],
            pending["password"],
            login_data,
        )
    except Exception as e:
        logger.error(f"Rift verify code error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.post("/api/quick_login")
async def quick_login(request: Request):
    """Quick login using saved credentials"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        base_game_id = data.get("base_game_id") or config.get_current_base_game()["id"]
        profile_id = data.get("profile_id") or config.get_current_amf_profile()["id"]
        check_only = bool(data.get("check_only"))

        try:
            config.set_base_game(base_game_id)
            config.set_amf_profile(profile_id)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        credentials = None
        
        # Try to use existing session first
        if user_id and user_id in sessions:
            session = sessions[user_id]
            if session and session.quick_login_data:
                credentials, _ = config.get_quick_login_credentials(profile_id, session.quick_login_data)
                if credentials:
                    logger.info(f"Using quick login from session for user {user_id} on profile {profile_id}")

        # Try to load from file for the selected profile
        if not credentials:
            try:
                credentials = load_quick_login_file(profile_id, base_game_id)
                if credentials:
                    logger.info(f"Loading quick login from file for profile: {profile_id}")
                    config.set_quick_login_credentials(
                        profile_id,
                        credentials["username"],
                        credentials["password"],
                        credentials.get("amf_label") or config.get_current_amf_profile()["label"],
                    )
            except Exception as e:
                logger.warning(f"Failed to load quick login file for {profile_id}: {e}")

        if check_only:
            return {
                "success": bool(credentials),
                "available": bool(credentials),
                "base_game_id": base_game_id,
                "profile_id": profile_id,
            }

        if credentials:
            return await login(LoginRequest(
                username=credentials["username"],
                password=credentials["password"],
                base_game_id=base_game_id,
                profile_id=profile_id,
            ))

        return {"success": False, "error": f"No quick login data available for {profile_id}"}
    except Exception as e:
        logger.error(f"Quick login error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/select_character")
async def select_character(request: CharacterSelectRequest):
    """Select character for user"""
    session = get_session(request.user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    
    try:
        logger.info(f"Selecting character at index {request.character_index} for user {session.username}")
        
        if not session.characters or request.character_index >= len(session.characters):
            logger.error(f"Invalid character selection: index {request.character_index}, total characters: {len(session.characters) if session.characters else 0}")
            return {"success": False, "error": "Invalid character selection"}
        
        selected_char = session.characters[request.character_index]
        
        restore_session_context(session)
        logger.info("Restored session context in config")
        
        # Extract character ID
        char_id = None
        if isinstance(selected_char, dict):
            char_id = selected_char.get('char_id') or selected_char.get('character_id')
        else:
            char_id = selected_char
        if isinstance(char_id, (list, tuple)):
            char_id = char_id[0] if char_id else None
        
        if not char_id:
            logger.error("No character ID found in selected character")
            return {"success": False, "error": "Invalid character data - no ID"}
        
        logger.info(f"Getting character data for ID: {char_id}")
        
        # Get character data using just the ID
        char_data_response = amf_req.get_character_data(char_id)
        
        # Extract character data (similar logic as refresh)
        character_data = None
        
        if char_data_response and isinstance(char_data_response, dict):
            if 'character_data' in char_data_response:
                character_data = char_data_response['character_data']
                logger.info("Found character_data in response")
            elif char_data_response.get('character_name') or char_data_response.get('name'):
                character_data = char_data_response
                logger.info("Response itself is character data")
            elif char_data_response.get('status') == 1:
                for key in ['data', 'result', 'character']:
                    if key in char_data_response and isinstance(char_data_response[key], dict):
                        if char_data_response[key].get('character_name'):
                            character_data = char_data_response[key]
                            logger.info(f"Found character data in '{key}' key")
                            break
        
        if character_data:
            session.current_character = character_data
            session.character_data = char_data_response
            
            character_info = _build_character_info(session, character_data)
            char_name = character_info["name"]
            char_level = character_info["level"]
            
            logger.info(f"Character selected successfully: {char_name} (Level {char_level})")
            session.add_log(f"✅ Selected character: {char_name}", "success")
            
            return {
                "success": True,
                "character": character_info
            }
        else:
            logger.error(f"Could not extract character data from response")
            return {"success": False, "error": "Failed to parse character data"}
            
    except Exception as e:
        logger.error(f"Character selection error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
@app.get("/api/user/{user_id}/status")
async def get_user_status(user_id: str):
    """Get user session status"""
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    
    character_info = None
    if session.current_character:
        character_info = _build_character_info(session, session.current_character)
    
    return {
        "success": True,
        "user": session.to_dict(),
        "character": character_info,
        "running": session.action_task is not None and not session.action_task.done(),
        "current_action": getattr(session.action_task, 'action_name', None) if session.action_task else None,
        "stopping": bool(session.stop_event.is_set() and session.action_task and not session.action_task.done()),
    }

@app.get("/api/user/{user_id}/logs")
async def get_user_logs(user_id: str, battle_only: bool = False):
    """Get user logs"""
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    
    if battle_only:
        return {"success": True, "logs": session.battle_logs[-100:]}
    else:
        return {"success": True, "logs": session.logs[-200:]}

@app.post("/api/user/{user_id}/clear_logs")
async def clear_user_logs(user_id: str):
    """Clear user logs"""
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    
    session.clear_logs()
    return {"success": True}

@app.post("/api/user/{user_id}/action")
async def start_user_action(user_id: str, request: ActionRequest):
    """Start an action for user"""
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    
    # Check if action is already running
    if session.action_task and not session.action_task.done():
        return {"success": False, "error": "Another action is already running"}
    
    restore_session_context(session)

    current_base_game = config.get_current_base_game()
    current_profile = config.get_current_amf_profile()

    try:
        action_spec = resolve_action(
            current_base_game,
            request.action,
            request.params,
            lambda: (lambda: refresh_character_data_sync(user_id)),
            current_profile,
        )
    except (ValueError, NotImplementedError) as exc:
        return {"success": False, "error": str(exc)}

    # Starting a non-clan-war action should reset the cached Clan War modal state
    # so the next modal open always reloads fresh clan data.
    session.clan_war_state = {}
    session.clan_war_modal_stop_only = False
    hide_ninjasaga_captcha_window()

    
    # Stop previous event
    session.stop_event.clear()
    
    # Create and start action task
    session.action_task = asyncio.create_task(
        run_action(user_id, action_spec.func, action_spec.name)
    )
    session.action_task.action_name = action_spec.name
    session.action_task.action_key = request.action
    
    return {"success": True, "message": f"Started: {action_spec.name}"}

@app.post("/api/user/{user_id}/stop")
async def stop_user_action(user_id: str):
    """Stop current user action"""
    session = get_session(user_id)
    if not session:
        return {"success": False, "error": "Session not found"}
    
    if session.action_task and not session.action_task.done():
        if getattr(session.action_task, "action_key", "") == "clan_war":
            session.clan_war_captcha_resume.set()
            hide_ninjasaga_captcha_window()
            state = _get_clan_war_state(session)
            state["running"] = False
            state["captcha_required"] = False
            state["captcha_message"] = ""
            state["captcha_challenge"] = None
        session.stop_event.set()
        action_name = getattr(session.action_task, "action_name", "Current Action")
        session.add_log(f"🟠 Stopping {action_name}... waiting current request/cooldown to finish", "warning")
        await manager.send_status(user_id, {
            "running": True,
            "action": action_name,
            "stopping": True,
        })
        return {"success": True, "message": f"Stopping {action_name}... please wait"}
    else:
        return {"success": False, "error": "No action running"}
@app.get("/api/admin/stats")
async def get_stats():
    return {
        "total_sessions": len(sessions),
        "active_websockets": len(manager.active_connections),
        "running_actions": sum(1 for s in sessions.values() if s.action_task and not s.action_task.done()),
        # "memory_usage": get_memory_usage()  # Implement this
    }
@app.post("/api/user/{user_id}/logout")
async def logout(user_id: str):
    """Logout user and remove session"""
    if user_id in sessions:
        session = sessions[user_id]
        if session.action_task and not session.action_task.done():
            session.stop_event.set()
            session.action_task.cancel()
        session.clan_war_state = {}
        session.clan_war_modal_stop_only = False
        hide_ninjasaga_captcha_window()
        del sessions[user_id]
        logger.info(f"User {user_id} logged out")
        return {"success": True}
    return {"success": False, "error": "Session not found"}

# WebSocket endpoint for real-time updates
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        session = get_session(user_id)
        if session:
            # Send initial connection message
            await manager.send_log(user_id, {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "message": "🟢 Connected to server",
                "type": "success"
            })
            
            # Send recent logs
            for log in session.logs[-50:]:
                await manager.send_log(user_id, log)
            
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                    # handle client message
                except asyncio.TimeoutError:
                    # send ping every 30 seconds
                    await websocket.send_json({"type": "ping"})
                
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(user_id)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
