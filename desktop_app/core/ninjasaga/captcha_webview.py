from __future__ import annotations

import json
import threading
import time
from typing import Optional

try:
    import webview  # type: ignore
except Exception:  # pragma: no cover
    webview = None


_WINDOW_LOCK = threading.Lock()
_CAPTCHA_WINDOW = None
NINJASAGA_AIR_URL = "https://ninjasaga.cc/?minimal&air&noreauth=1"
NINJASAGA_WEB_LOGIN_ENDPOINT = "https://ninjasaga.cc/api.php/login"


def is_native_webview_available() -> bool:
    if webview is None:
        return False
    try:
        return bool(getattr(webview, "windows", []))
    except Exception:
        return False


def _post_window_message(action: str) -> None:
    global _CAPTCHA_WINDOW
    if _CAPTCHA_WINDOW is None:
        return
    script = f"try {{ parent.postMessage({{action: '{action}'}}, '*'); }} catch (e) {{ try {{ window.postMessage({{action: '{action}'}}, '*'); }} catch (e2) {{}} }}"
    for _ in range(10):
        try:
            _CAPTCHA_WINDOW.evaluate_js(script)
            return
        except Exception:
            time.sleep(0.5)


def _login_and_show_action(username: str, password: str, action: str) -> None:
    global _CAPTCHA_WINDOW
    if _CAPTCHA_WINDOW is None:
        return
    payload = {
        "username": username,
        "password": password,
        "minimal": "0",
        "air": "0",
        "w": "1920",
        "h": "1080",
        "tz": "Asia/Makassar",
        "cpu": "12",
        "ram": "8",
        "browser_ver": "Chrome 146",
        "uuid": "110e047e-bf6d-45df-b9df-a1205e321183",
        "gpu": "ANGLE (AMD, AMD Radeon Graphics, D3D11)",
    }
    payload_json = json.dumps(payload)
    script = f"""
    (async function() {{
      try {{
        await fetch({json.dumps(NINJASAGA_WEB_LOGIN_ENDPOINT)}, {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'X-Requested-With': 'XMLHttpRequest'
          }},
          credentials: 'include',
          body: JSON.stringify({payload_json})
        }});
      }} catch (e) {{}}
      try {{
        parent.postMessage({{action: {json.dumps(action)}}}, '*');
      }} catch (e) {{
        try {{
          window.postMessage({{action: {json.dumps(action)}}}, '*');
        }} catch (e2) {{}}
      }}
    }})();
    """
    for _ in range(12):
        try:
            _CAPTCHA_WINDOW.evaluate_js(script)
            return
        except Exception:
            time.sleep(0.5)


def open_ninjasaga_captcha_window(
    url: str = NINJASAGA_AIR_URL,
    title: str = "NinjaSaga Clan War Captcha",
    action: str = "show_captcha",
    username: str = "",
    password: str = "",
) -> bool:
    global _CAPTCHA_WINDOW
    if not url or webview is None:
        return False
    try:
        windows = getattr(webview, "windows", [])
    except Exception:
        windows = []
    if not windows:
        return False

    with _WINDOW_LOCK:
        if _CAPTCHA_WINDOW is None:
            try:
                _CAPTCHA_WINDOW = webview.create_window(
                    title,
                    url=url,
                    width=520,
                    height=820,
                    resizable=True,
                )
                target = _login_and_show_action if username and password else _post_window_message
                args = (username, password, action) if username and password else (action,)
                threading.Thread(target=target, args=args, daemon=True).start()
                return True
            except Exception:
                _CAPTCHA_WINDOW = None
                return False

        try:
            _CAPTCHA_WINDOW.set_title(title)
        except Exception:
            pass
        try:
            _CAPTCHA_WINDOW.load_url(url)
        except Exception:
            pass
        try:
            _CAPTCHA_WINDOW.show()
        except Exception:
            pass
        try:
            _CAPTCHA_WINDOW.restore()
        except Exception:
            pass
        target = _login_and_show_action if username and password else _post_window_message
        args = (username, password, action) if username and password else (action,)
        threading.Thread(target=target, args=args, daemon=True).start()
        return True


def hide_ninjasaga_captcha_window() -> None:
    global _CAPTCHA_WINDOW
    with _WINDOW_LOCK:
        if _CAPTCHA_WINDOW is None:
            return
        try:
            _CAPTCHA_WINDOW.hide()
        except Exception:
            pass
