import threading
import time
import sys
import ctypes
import os
import subprocess
import uuid
import urllib.request
import urllib.error

import uvicorn
import webview
import json
import urllib.request
import urllib.error
import socket
from main import app
from core import config

INSTANCE_ARG = "--instance"
INSTANCE_TOKEN_ARG = "--launcher-token="
INSTANCE_TOKEN_ENV = "NINJA_SAGE_LAUNCHER_TOKEN"


def user_data_dir() -> str:
    base = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("APPDATA")
        or os.path.expanduser("~")
        or app_dir()
    )
    path = os.path.join(base, "Ninja Sage Panel")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        return app_dir()
    return path


def pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))  # 0 = OS chooses free port
    port = s.getsockname()[1]
    s.close()
    return port

BUILD_NUM = config.PANEL_BUILD_NUM



def unix_from_datetime(value):
    if not value:
        return None
    try:
        return int(time.mktime(time.strptime(str(value), "%Y-%m-%d %H:%M:%S")))
    except Exception:
        return None


def server_time_now_unix(server_reference_unix, server_reference_monotonic):
    if server_reference_unix is not None and server_reference_monotonic is not None:
        elapsed = max(0, time.monotonic() - server_reference_monotonic)
        return int(server_reference_unix + elapsed)
    return int(time.time())


def launcher_device_id_path() -> str:
    return os.path.join(user_data_dir(), ".ninja_sage_launcher_device")


def launcher_session_path() -> str:
    return os.path.join(user_data_dir(), ".ninja_sage_launcher_session.json")


def legacy_launcher_device_id_path() -> str:
    return os.path.join(app_dir(), ".ninja_sage_launcher_device")


def legacy_launcher_session_path() -> str:
    return os.path.join(app_dir(), ".ninja_sage_launcher_session.json")


def get_launcher_device_id() -> str:
    path = launcher_device_id_path()
    try:
        if os.path.exists(path):
            value = open(path, "r", encoding="utf-8").read().strip()
            if len(value) >= 24:
                return value
    except Exception:
        pass

    legacy_path = legacy_launcher_device_id_path()
    try:
        if os.path.exists(legacy_path):
            value = open(legacy_path, "r", encoding="utf-8").read().strip()
            if len(value) >= 24:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(value)
                return value
    except Exception:
        pass

    value = "pc-" + uuid.uuid4().hex
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(value)
    except Exception:
        pass
    return value


def load_launcher_session() -> dict | None:
    path = launcher_session_path()
    try:
        if not os.path.exists(path):
            legacy_path = legacy_launcher_session_path()
            if os.path.exists(legacy_path):
                path = legacy_path
            else:
                return None
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or not data.get("username") or not data.get("session_token"):
            return None
        if path == legacy_launcher_session_path():
            save_launcher_session(data)
        return data
    except Exception:
        return None

def hide_console():
    if sys.platform == "win32":
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)


def show_console():
    if sys.platform == "win32":
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 5)


def run_server(port: int):
    uvicorn.run(app, host="127.0.0.1", port=port, reload=False, log_level="info")


def wait_for_server(url: str, timeout_sec: float = 30.0, interval_sec: float = 0.2) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(interval_sec)
    return False


SPLASH_HTML = """<!doctype html>
<html><head><meta charset="utf-8" />
<title>Ninja Sage Panel</title>
<style>
body{margin:0;font-family:Segoe UI,Arial;background:#111;color:#fff;overflow:hidden;}
.wrap{height:100vh;display:flex;align-items:center;justify-content:center;flex-direction:column;padding:18px;}
.title{font-size:18px;margin-bottom:12px;}
.sub{font-size:12px;opacity:.9; max-width:380px; text-align:center; line-height:1.45; white-space:pre-line;}
.spinner{
  width:34px;height:34px;border:4px solid rgba(255,255,255,.2);
  border-top-color:rgba(255,255,255,.9);
  border-radius:50%;animation:spin .9s linear infinite;margin-bottom:16px;
}
@keyframes spin{to{transform:rotate(360deg);}}
.badge{margin-top:10px;font-size:11px;opacity:.65}
.hidden{display:none !important;}
h3{margin:0 0 10px 0; font-size:18px;}
.block{max-width:420px;text-align:center;}
.btn{margin-top:14px; padding:10px 14px; border-radius:8px; border:1px solid rgba(255,255,255,.2);
background:rgba(255,255,255,.06); color:#fff; cursor:pointer; font-size:12px;}
</style></head>
<body>
  <div class="wrap">
    <div id="spinner" class="spinner"></div>
    <div id="title" class="title">Starting Ninja Sage Panel…</div>

    <div id="status" class="sub">Please wait</div>
    <div id="badge" class="badge"></div>
  </div>
</body></html>
"""

LAUNCHER_HTML = """<!doctype html>
<html><head><meta charset="utf-8" />
<title>Ninja Sage Launcher</title>
<style>
body{margin:0;font-family:Segoe UI,Arial;background:#101312;color:#f4f1e8;}
.wrap{min-height:100vh;padding:22px;box-sizing:border-box;}
.top{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:18px;}
h1{font-size:22px;margin:0;}
.muted{color:#aab5af;font-size:13px;line-height:1.45;}
.panel{border:1px solid #32413d;border-radius:8px;background:#181f1d;padding:16px;margin-bottom:14px;}
.main-grid{display:grid;grid-template-columns:minmax(360px,1.25fr) minmax(220px,.75fr);gap:14px;align-items:stretch;overflow-x:auto;}
.main-grid .panel{margin-bottom:14px;}
.action-panel{display:flex;flex-direction:column;justify-content:space-between;gap:12px;}
.btn{min-height:38px;border:0;border-radius:7px;background:linear-gradient(180deg,#e2b84d,#9f6f19);color:#17120a;font-weight:800;padding:8px 13px;cursor:pointer;}
.btn:disabled{opacity:.55;cursor:not-allowed;filter:grayscale(1);}
.ghost-btn{min-height:31px;border:1px solid #4d625b;border-radius:7px;background:#202a27;color:#f4f1e8;font-size:11px;font-weight:700;padding:5px 9px;cursor:pointer;}
.danger-btn{border-color:#7b3939;color:#ffb3b3;}
label{display:block;font-size:11px;color:#aab5af;font-weight:700;margin:0 0 4px;}
input{width:100%;box-sizing:border-box;border:1px solid #32413d;border-radius:7px;background:#101312;color:#f4f1e8;padding:7px 9px;margin-bottom:7px;font-size:12px;}
.form-grid{display:grid;grid-template-columns:minmax(110px,1fr) minmax(110px,1fr) auto;gap:8px;align-items:end;}
.form-grid .btn{min-height:32px;padding:6px 11px;font-size:12px;margin-bottom:7px;}
.launcher-actions{display:grid;grid-template-columns:1fr;gap:10px;align-items:stretch;}
.launcher-actions .btn,.launcher-actions .ghost-btn{display:flex;align-items:center;justify-content:center;box-sizing:border-box;width:100%;min-height:38px;margin:0;padding:8px 12px;text-align:center;}
.subscription-actions{display:grid;grid-template-columns:auto auto auto;gap:8px;align-items:stretch;justify-content:start;margin-top:4px;}
.subscription-actions .ghost-btn{display:flex;align-items:center;justify-content:center;box-sizing:border-box;margin:0;text-align:center;}
.status{display:inline-flex;align-items:center;gap:8px;border:1px solid #32413d;border-radius:999px;padding:6px 10px;font-size:12px;font-weight:800;color:#aab5af;}
.dot{width:9px;height:9px;border-radius:50%;background:#aab5af;}
.ready .dot,.running .dot{background:#82d895;}
.checking .dot,.starting .dot{background:#e2b84d;}
.error .dot{background:#ff7d7d;}
.closed .dot{background:#8db7ff;}
.row{display:grid;grid-template-columns:92px minmax(150px,1fr) 64px 70px;gap:10px;align-items:center;border-top:1px solid #32413d;padding:12px 0;min-width:430px;}
.row:first-child{border-top:0;}
.name{font-weight:800;}
.small{font-size:12px;color:#aab5af;}
.close-btn{min-height:32px;border:1px solid #4d625b;border-radius:7px;background:#202a27;color:#f4f1e8;font-size:12px;font-weight:700;padding:6px 10px;cursor:pointer;}
.close-btn:hover{border-color:#ffb3b3;color:#ffb3b3;}
.close-btn:disabled{opacity:.45;cursor:not-allowed;}
</style></head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <h1>Ninja Sage Panel Launcher</h1>
        <div class="muted">Login subscription here. Instances are controlled by this launcher.</div>
      </div>
      <span id="statusBadge" class="status checking"><span class="dot"></span><span id="statusText">Checking build...</span></span>
    </div>
    <div class="main-grid">
      <div class="panel">
        <div class="name" style="margin-bottom:8px;">Subscription</div>
        <div id="accountText" class="muted" style="margin-bottom:12px;">Login with your webshop account before opening instances.</div>
        <div id="loginForm" class="">
          <div>
            <label for="username">Username</label>
            <input id="username" autocomplete="username">
          </div>
          <div>
            <label for="password">Password</label>
            <input id="password" type="password" autocomplete="current-password">
          </div>
          <button id="loginBtn" class="btn">Login</button>
        </div>
        <div class="">
          <button id="refreshSubBtn" class="ghost-btn" disabled>Refresh Subscription</button>
          <a class="ghost-btn" style="text-decoration:none;" href="https://example.com/panel/" target="_blank" rel="noopener noreferrer">Buy Subscription</a>
          <button id="logoutBtn" class="ghost-btn" disabled>Logout</button>
        </div>
      </div>
      <div class="panel action-panel">
        <div>
          <div class="name" style="margin-bottom:8px;">Actions</div>
          <div class="muted">Open a controlled panel window, or buy/renew from the webshop.</div>
        </div>
        <div class="launcher-actions">
          <button id="openBtn" class="btn" disabled>Open New Instance</button>
        </div>
        <div id="message" class="muted">Please wait.</div>
      </div>
    </div>
    <div class="panel">
      <div class="name" style="margin-bottom:8px;">Instances</div>
      <div id="instances" class="muted">No instances opened yet.</div>
    </div>
  </div>
<script>
const openBtn = document.getElementById('openBtn');
const message = document.getElementById('message');
const statusBadge = document.getElementById('statusBadge');
const statusText = document.getElementById('statusText');
const instances = document.getElementById('instances');
const accountText = document.getElementById('accountText');
const username = document.getElementById('username');
const password = document.getElementById('password');
const loginBtn = document.getElementById('loginBtn');
const logoutBtn = document.getElementById('logoutBtn');
const refreshSubBtn = document.getElementById('refreshSubBtn');
const loginForm = document.getElementById('loginForm');

function setStatus(state, text) {
  statusBadge.className = 'status ' + state;
  statusText.textContent = text;
}

async function refreshStatus() {
  const status = await pywebview.api.get_launcher_status();
  setStatus(status.state, status.text);
  message.textContent = status.message || '';
  openBtn.disabled = !status.allowed;
  if (status.allowed) {
    accountText.textContent = (status.account || '') + ' Click Open New Instance to start playing.';
  } else if (status.loggedIn) {
    accountText.textContent = (status.account || '') + ' Buy or renew your desktop subscription, then login again.';
  } else {
    accountText.textContent = status.account || 'Login with your webshop account before opening instances.';
  }
  logoutBtn.disabled = !status.loggedIn;
  logoutBtn.style.display = status.loggedIn ? 'inline-flex' : 'none';
  refreshSubBtn.disabled = !status.loggedIn;
  refreshSubBtn.style.display = status.loggedIn ? 'inline-flex' : 'none';
  if (loginForm) loginForm.style.display = status.loggedIn ? 'none' : 'grid';
  loginBtn.disabled = status.loggedIn || !status.buildAllowed;
}

async function refreshInstances() {
  const list = await pywebview.api.list_instances();
  if (!list.length) {
    instances.textContent = 'No instances opened yet.';
    return;
  }
  instances.innerHTML = list.map((item) => `
    <div class="row">
      <span class="status ${item.state}"><span class="dot"></span>${item.stateLabel}</span>
      <div>
        <div class="name">${item.name}</div>
        <div class="small">${item.detail}</div>
      </div>
      <div class="small">${item.returnCode === null ? '' : 'Exit ' + item.returnCode}</div>
      ${item.canReopen
        ? `<button class="close-btn" data-reopen-id="${item.id}">Reopen</button>`
        : `<button class="close-btn" data-close-id="${item.id}" ${item.canClose ? '' : 'disabled'}>Close</button>`}
    </div>
  `).join('');
}

openBtn.addEventListener('click', async () => {
  openBtn.disabled = true;
  const result = await pywebview.api.open_new_instance();
  message.textContent = result.message;
  await refreshInstances();
  await refreshStatus();
});

loginBtn.addEventListener('click', async () => {
  loginBtn.disabled = true;
  message.textContent = 'Checking subscription...';
  const result = await pywebview.api.login_subscription(username.value, password.value);
  message.textContent = result.message;
  if (result.ok) password.value = '';
  await refreshStatus();
  await refreshInstances();
});

logoutBtn.addEventListener('click', async () => {
  const result = await pywebview.api.logout_subscription();
  message.textContent = result.message;
  password.value = '';
  await refreshStatus();
  await refreshInstances();
});

refreshSubBtn.addEventListener('click', async () => {
  refreshSubBtn.disabled = true;
  message.textContent = 'Refreshing subscription...';
  const result = await pywebview.api.refresh_subscription_now();
  message.textContent = result.message;
  await refreshStatus();
  await refreshInstances();
});

instances.addEventListener('click', async (event) => {
  const closeButton = event.target.closest('[data-close-id]');
  const reopenButton = event.target.closest('[data-reopen-id]');
  const button = closeButton || reopenButton;
  if (!button || button.disabled) return;
  button.disabled = true;
  const result = closeButton
    ? await pywebview.api.close_instance(closeButton.dataset.closeId)
    : await pywebview.api.reopen_instance(reopenButton.dataset.reopenId);
  message.textContent = result.message;
  await refreshStatus();
  await refreshInstances();
});

setInterval(refreshInstances, 1200);
setInterval(refreshStatus, 2500);
window.addEventListener('pywebviewready', async () => {
  await refreshStatus();
  await refreshInstances();
});
</script>
</body></html>
"""


class LauncherApi:
    def __init__(self):
        self.allowed = False
        self.build_allowed = False
        self.build_state = "checking"
        self.state = "checking"
        self.text = "Checking build..."
        self.message = "Please wait."
        self.account_message = "Login with your webshop account before opening instances."
        self.username = None
        self.password = None
        self.session_token = None
        self.session_needs_validation = False
        self.device_id = get_launcher_device_id()
        self.expires_at = None
        self.expires_at_unix = None
        self.server_reference_unix = None
        self.server_reference_monotonic = None
        self.instance_token = uuid.uuid4().hex + uuid.uuid4().hex
        self.instances = []
        self.lock = threading.Lock()
        self.restore_saved_session()

    def restore_saved_session(self):
        session = load_launcher_session()
        if not session:
            return

        self.username = str(session.get("username") or "")
        self.session_token = str(session.get("session_token") or "")
        self.expires_at = session.get("expires_at")
        try:
            self.expires_at_unix = int(session.get("expires_at_unix") or 0) or None
        except Exception:
            self.expires_at_unix = None
        self.session_needs_validation = True
        self.account_message = f"{self.username} | Restoring saved subscription..."

    def set_status(self, allowed: bool, state: str, text: str, message: str):
        with self.lock:
            self.build_allowed = allowed
            self.build_state = state
            self.text = text
            self.message = message
            self._refresh_allowed_locked()

    def _subscription_active_locked(self):
        return True
    def _subscription_active_locked_OLD(self):
        if self.session_needs_validation:
            return False
        if not self.username or not self.expires_at_unix:
            return False
        return self.expires_at_unix > server_time_now_unix(
            self.server_reference_unix,
            self.server_reference_monotonic,
        )

    def _refresh_allowed_locked(self):
        self.allowed = True
        self.build_allowed = True
        self.state = "ready"
        self.text = "Open Source"
        self.account_message = "Ready to play! Unlimited Instances."
        self.username = "OpenSourceUser"
        return
    def _refresh_allowed_locked_OLD(self):
        subscription_active = self._subscription_active_locked()
        self.allowed = self.build_allowed and subscription_active
        if not self.build_allowed:
            self.state = self.build_state
            return
        if subscription_active:
            self.state = "ready"
            self.text = "Ready"
            self.account_message = f"{self.username} | Valid until {self.expires_at}"
        elif self.username:
            if self.session_needs_validation:
                self.state = "checking"
                self.text = "Validating"
                self.account_message = f"{self.username} | Checking saved subscription..."
            else:
                self.state = "error"
                self.text = "Expired"
                self.account_message = f"{self.username} | Subscription expired. Buy subscription to open instances."
        else:
            self.state = "checking"
            self.text = "Login Required"
            self.account_message = "Login with your webshop account before opening instances."

    def get_launcher_status(self):
        with self.lock:
            self._refresh_allowed_locked()
            should_close = bool(self.username and not self.allowed)
            status = {
                "allowed": self.allowed,
                "state": self.state,
                "text": self.text,
                "message": self.message,
                "account": self.account_message,
                "loggedIn": bool(self.username),
                "buildState": self.build_state,
                "buildAllowed": self.build_allowed,
            }
        return status

    def login_subscription(self, username: str, password: str):
        username = (username or "").strip()
        password = password or ""
        if not username or not password:
            return {"ok": False, "message": "Enter username and password."}

        ok, msg, data = billing_login(username, password, self.device_id)
        if not ok or not data:
            return {"ok": False, "message": msg}

        billing = data.get("billing") if isinstance(data.get("billing"), dict) else {}
        session_token = ((data.get("session") or {}).get("session_token") if isinstance(data.get("session"), dict) else None)
        if billing.get("subscription_active") and not session_token:
            return {"ok": False, "message": "Billing server must be updated for device sessions before desktop subscription can be used."}
        expires_at = billing.get("expires_at")
        expires_at_unix = billing.get("expires_at_unix") or unix_from_datetime(expires_at)
        try:
            server_reference_unix = int(data.get("server_now_unix")) if data.get("server_now_unix") else None
        except Exception:
            server_reference_unix = None
        server_reference_monotonic = time.monotonic() if server_reference_unix is not None else None

        with self.lock:
            self.username = (data.get("user") or {}).get("username") or username
            self.password = password
            self.session_token = session_token
            self.expires_at = expires_at
            self.expires_at_unix = int(expires_at_unix) if expires_at_unix else None
            self.server_reference_unix = server_reference_unix
            self.server_reference_monotonic = server_reference_monotonic
            self.session_needs_validation = False
            self._refresh_allowed_locked()
            active = self.allowed
            account_message = self.account_message
            saved_session = {
                "username": self.username,
                "session_token": self.session_token,
                "expires_at": self.expires_at,
                "expires_at_unix": self.expires_at_unix,
            }

        if self.session_token:
            save_launcher_session(saved_session)

        if not active:
            return {
                "ok": True,
                "message": account_message + " https://example.com/panel/",
            }

        return {"ok": True, "message": account_message}


    def refresh_subscription_from_server(self):
        with self.lock:
            username = self.username
            session_token = self.session_token
            device_id = self.device_id
        if not username or not session_token:
            return False, "Login first."

        ok, msg, data = True, "OK", {"billing": {"subscription_active": True, "expires_at": "2099-12-31 23:59:59"}, "session": {"session_token": session_token}}

        billing = data.get("billing") if isinstance(data.get("billing"), dict) else {}
        subscription_active = bool(billing.get("subscription_active"))
        expires_at = billing.get("expires_at")
        expires_at_unix = billing.get("expires_at_unix") or unix_from_datetime(expires_at)
        try:
            server_reference_unix = int(data.get("server_now_unix")) if data.get("server_now_unix") else None
        except Exception:
            server_reference_unix = None
        server_reference_monotonic = time.monotonic() if server_reference_unix is not None else None

        with self.lock:
            self.expires_at = expires_at
            self.expires_at_unix = int(expires_at_unix) if expires_at_unix else None
            if not subscription_active:
                self.session_token = None
            self.server_reference_unix = server_reference_unix
            self.server_reference_monotonic = server_reference_monotonic
            self.session_needs_validation = False
            was_allowed = self.allowed
            self._refresh_allowed_locked()
            is_allowed = self.allowed
            saved_session = {
                "username": self.username,
                "session_token": self.session_token,
                "expires_at": self.expires_at,
                "expires_at_unix": self.expires_at_unix,
            }

        if self.session_token:
            save_launcher_session(saved_session)
        else:
            clear_launcher_session()
        return True, self.account_message

    def refresh_subscription_now(self):
        ok, message = self.refresh_subscription_from_server()
        self.enforce_expiry()
        with self.lock:
            allowed = self.allowed
        if ok and allowed:
            return {"ok": True, "message": message}
        if ok:
            return {"ok": True, "message": message + " https://example.com/panel/"}
        return {"ok": False, "message": message}

    def enforce_expiry(self):
        with self.lock:
            self._refresh_allowed_locked()
            is_allowed = self.allowed
            has_login = bool(self.username)

    def open_new_instance(self):
        return self._open_instance()

    def _open_instance(self, existing_item=None):
        with self.lock:
            self._refresh_allowed_locked()
            if not self.allowed:
                return {"ok": False, "message": "Active desktop subscription is required."}
            if existing_item is None:
                index = len(self.instances) + 1
                instance_id = uuid.uuid4().hex[:8]
                name = f"Instance {index}"
            else:
                instance_id = existing_item["id"]
                name = existing_item["name"]
            instance_token = self.instance_token

        cmd = instance_command(instance_id, name, instance_token)
        env = os.environ.copy()
        env[INSTANCE_TOKEN_ENV] = instance_token
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            process = subprocess.Popen(cmd, cwd=app_dir(), env=env, creationflags=creationflags)
        except Exception as exc:
            return {"ok": False, "message": f"Failed to open {name}: {exc}"}

        with self.lock:
            if existing_item is None:
                self.instances.append({
                    "id": instance_id,
                    "name": name,
                    "process": process,
                    "created_at": time.strftime("%H:%M:%S"),
                    "close_requested": False,
                    "close_reason": None,
                })
            else:
                existing_item["process"] = process
                existing_item["created_at"] = time.strftime("%H:%M:%S")
                existing_item["close_requested"] = False
                existing_item["close_reason"] = None
        return {"ok": True, "message": f"{name} opened."}

    def reopen_instance(self, instance_id: str):
        with self.lock:
            target = next((item for item in self.instances if item["id"] == instance_id), None)
            if not target:
                return {"ok": False, "message": "Instance was not found."}
            if target["process"].poll() is None:
                return {"ok": False, "message": f"{target['name']} is already running."}

        return self._open_instance(target)

    def close_instance(self, instance_id: str):
        with self.lock:
            target = next((item for item in self.instances if item["id"] == instance_id), None)
            if not target:
                return {"ok": False, "message": "Instance was not found."}

            process = target["process"]
            if process.poll() is not None:
                return {"ok": False, "message": f"{target['name']} is already closed."}

            target["close_requested"] = True
            target["close_reason"] = "launcher"

        try:
            process.terminate()
            return {"ok": True, "message": f"Closing {target['name']}..."}
        except Exception as exc:
            with self.lock:
                target["close_requested"] = False
            return {"ok": False, "message": f"Failed to close {target['name']}: {exc}"}

    def list_instances(self):
        with self.lock:
            rows = []
            for item in self.instances:
                process = item["process"]
                return_code = process.poll()
                if return_code is None:
                    if item.get("close_requested"):
                        state = "starting"
                        state_label = "Closing"
                        detail = f"Close requested. Opened at {item['created_at']}"
                    else:
                        state = "running"
                        state_label = "Running"
                        detail = f"Opened at {item['created_at']}"
                elif return_code == 0:
                    state = "closed"
                    state_label = "Closed"
                    detail = f"Closed. Opened at {item['created_at']}"
                elif item.get("close_requested"):
                    state = "closed"
                    state_label = "Closed"
                    detail = f"Closed by {item.get('close_reason', 'launcher')}. Opened at {item['created_at']}"
                else:
                    state = "error"
                    state_label = "Error"
                    detail = f"Exited with an error. Opened at {item['created_at']}"
                rows.append({
                    "id": item["id"],
                    "name": item["name"],
                    "state": state,
                    "stateLabel": state_label,
                    "detail": detail,
                    "returnCode": return_code,
                    "canClose": return_code is None and not item.get("close_requested"),
                    "canReopen": return_code is not None,
                })
            return rows


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def instance_command(instance_id: str, name: str, token: str):
    if getattr(sys, "frozen", False):
        return [sys.executable, INSTANCE_ARG, f"--instance-id={instance_id}", f"--instance-name={name}", f"{INSTANCE_TOKEN_ARG}{token}"]
    return [sys.executable, os.path.abspath(__file__), INSTANCE_ARG, f"--instance-id={instance_id}", f"--instance-name={name}", f"{INSTANCE_TOKEN_ARG}{token}"]


def parse_arg_value(prefix: str, default: str) -> str:
    for arg in sys.argv:
        if arg.startswith(prefix):
            return arg.split("=", 1)[1]
    return default


def validate_launcher_token() -> bool:
    return True

def splash_set_status(window, text: str, build: str = "", blocked: bool = False):
    js = f"""
    (function(){{
      var s=document.getElementById('status');
      var b=document.getElementById('badge');
      var sp=document.getElementById('spinner');
      var t=document.getElementById('title');

      if(s) s.innerText = {json.dumps(text)};
      if(b) b.innerText = {json.dumps(build)};

      if({str(blocked).lower()}) {{
        if(sp) sp.classList.add('hidden');
        if(t) t.classList.add('hidden');
      }} else {{
        if(sp) sp.classList.remove('hidden');
        if(t) t.classList.remove('hidden');
      }}
    }})();
    """
    try:
        window.evaluate_js(js)
    except Exception:
        pass
    
def start_instance_app():
    if not validate_launcher_token():
        sys.stderr.write("This panel instance must be opened from the launcher.\n")
        sys.stderr.flush()
        os._exit(2)

    instance_name = parse_arg_value("--instance-name=", "Ninja Sage Panel")
    local_port = pick_free_port()
    base_url = f"http://127.0.0.1:{local_port}/"

    threading.Thread(target=run_server, args=(local_port,), daemon=True).start()

    splash = webview.create_window(
        instance_name,
        html=SPLASH_HTML,
        width=420,
        height=240,
        resizable=True
    )

    hide_console()

    def after_webview_start():
        def worker():
            splash_set_status(splash, "Error nih")

            ok = wait_for_server(base_url, timeout_sec=10)
            if not ok:
                splash_set_status(
                    splash,
                    "Failed to start local server.\nPlease run again or check logs.",
                    f"Build: {BUILD_NUM}",
                    blocked=True
                )
                show_console()
                time.sleep(2)
                os._exit(1)
                return

            splash_set_status(splash, "Opening panel...", f"Build: {BUILD_NUM}")
            time.sleep(1)

            splash.set_title(f"{instance_name} ({BUILD_NUM})")
            try:
                splash.resize(1200, 800)
            except Exception:
                pass

            splash.load_url(base_url)

        threading.Thread(target=worker, daemon=True).start()

    webview.start(after_webview_start)


def start_launcher():
    api = LauncherApi()
    api.allowed = True
    api.build_allowed = True
    api.state = "ready"
    api.text = "Open Source Version"
    api.account_message = "Ready to play!"
    webview.create_window(
        "Ninja Sage Launcher",
        html=LAUNCHER_HTML,
        js_api=api,
        width=600,
        height=520,
        resizable=False
    )
    webview.start()

if __name__ == "__main__":
    try:
        if INSTANCE_ARG in sys.argv:
            start_instance_app()
        else:
            start_launcher()
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
