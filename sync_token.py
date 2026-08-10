"""
sync_token.py — Auto-sync your Infosys Springboard auth token from a live browser session.

REQUIREMENTS:
  Chrome / Edge must be running with remote debugging enabled. Start it like this:

    Chrome:
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\\chrome-debug

    Edge:
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port=9222 --user-data-dir=C:\\edge-debug

  Then log in to https://infyspringboard.onwingspan.com and run:
      py sync_token.py

WHAT IT DOES:
  Connects to your open Springboard browser tab via CDP, reads the JWT token
  from localStorage, extracts wid/sid from it, and updates ~/.infosys-course/config.json
  automatically.
"""

try:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import base64
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("[ERROR] httpx not installed. Run: pip install httpx")
    sys.exit(1)

try:
    import websocket
except ImportError:
    print("[ERROR] websocket-client not installed. Run: pip install websocket-client")
    sys.exit(1)


CONFIG_PATH = Path.home() / ".infosys-course" / "config.json"
DEBUGGER_URL = "http://127.0.0.1:9222/json"

# ── Find active Springboard browser tab ──────────────────────────────────────

def find_springboard_tab() -> tuple[str, str]:
    """Returns (websocket_debugger_url, tab_title) for the active Springboard tab."""
    try:
        r = httpx.get(DEBUGGER_URL, timeout=3)
        targets = r.json()
    except Exception as e:
        print(
            f"\n[ERROR] Cannot connect to browser debugger at {DEBUGGER_URL}\n"
            f"  Make sure Chrome/Edge is running with:\n"
            f"    --remote-debugging-port=9222\n"
            f"  Error: {e}"
        )
        sys.exit(1)

    for target in targets:
        url   = target.get("url", "")
        ws    = target.get("webSocketDebuggerUrl")
        title = target.get("title", "Unknown")
        if "infyspringboard.onwingspan.com" in url and ws:
            return ws, title

    print(
        "\n[ERROR] No active Infosys Springboard tab found in browser.\n"
        "  → Open https://infyspringboard.onwingspan.com and log in, then re-run."
    )
    sys.exit(1)


# ── Extract token via CDP ─────────────────────────────────────────────────────

def extract_token_via_cdp(ws_url: str) -> dict | None:
    """
    Connects to the browser tab via Chrome DevTools Protocol,
    evaluates JavaScript to read the token from localStorage,
    and returns the extracted data.
    """
    result_container = {}

    JS = """
    (function() {
        // Try multiple localStorage keys used by Springboard/Keycloak
        const keys = ['kc', 'keycloak', 'user-token', 'token', 'auth'];
        for (const key of keys) {
            try {
                const raw = localStorage.getItem(key);
                if (raw) {
                    const data = JSON.parse(raw);
                    const token = data.token || data.access_token || data.auth_token || data.authToken;
                    if (token && token.split('.').length === 3) {
                        return JSON.stringify({ key: key, token: token, idToken: data.idToken });
                    }
                }
            } catch(e) {}
        }

        // Try sessionStorage too
        for (const key of keys) {
            try {
                const raw = sessionStorage.getItem(key);
                if (raw) {
                    const data = JSON.parse(raw);
                    const token = data.token || data.access_token;
                    if (token && token.split('.').length === 3) {
                        return JSON.stringify({ key: 'session:' + key, token: token });
                    }
                }
            } catch(e) {}
        }

        return null;
    })()
    """

    def on_open(ws):
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": JS, "returnByValue": True}
        }))

    def on_message(ws, message):
        data = json.loads(message)
        if data.get("id") == 1:
            res = data.get("result", {}).get("result", {})
            val = res.get("value")
            if val:
                result_container["data"] = json.loads(val)
            ws.close()

    def on_error(ws, error):
        print(f"[ERROR] WebSocket error: {error}")
        ws.close()

    def on_close(ws, *args):
        pass

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws.run_forever(suppress_origin=True)

    return result_container.get("data")


# ── Parse token ───────────────────────────────────────────────────────────────

def decode_jwt(token: str) -> dict:
    """Decode JWT payload (no signature verification needed here)."""
    try:
        part = token.split(".")[1]
        part += "=" * (4 - len(part) % 4)
        return json.loads(base64.b64decode(part).decode("utf-8"))
    except Exception as e:
        print(f"[WARN] Could not decode JWT: {e}")
        return {}


# ── Update config ─────────────────────────────────────────────────────────────

def update_config(token: str, wid: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text())
    else:
        cfg = {
            "base_url": "https://infyspringboard.onwingspan.com",
            "root_org": "infosysheadstart",
            "org":      "infosysheadstart",
            "auth":     {}
        }

    cfg["auth"]["auth-token"] = token
    cfg["auth"]["wid"]        = wid
    # Ensure org is correct
    cfg.setdefault("root_org", "infosysheadstart")
    cfg.setdefault("org",      "infosysheadstart")

    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    print(f"\n[OK] config.json updated at {CONFIG_PATH}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Infosys Springboard — Token Sync Utility")
    print("=" * 60)

    ws_url, title = find_springboard_tab()
    print(f"\n[+] Found Springboard tab: {title[:70]}")
    print(f"[+] Connecting via CDP...")

    extracted = extract_token_via_cdp(ws_url)

    if not extracted:
        print(
            "\n[ERROR] Could not find token in browser localStorage.\n"
            "  → Make sure you are logged in to Infosys Springboard.\n"
            "  → Try navigating to any course page first, then re-run."
        )
        sys.exit(1)

    token = extracted.get("token")
    key   = extracted.get("key", "?")
    print(f"[+] Token found in localStorage key: '{key}'")

    payload = decode_jwt(token)

    wid = payload.get("wid") or payload.get("sub", "")
    sid = payload.get("sid") or payload.get("session_state", "")
    exp = payload.get("exp", 0)
    name = payload.get("name", "Unknown")

    if not wid:
        print("[ERROR] Could not extract 'wid' from JWT payload. Token may be malformed.")
        sys.exit(1)

    print(f"\n  Name : {name}")
    print(f"  WID  : {wid}")
    print(f"  SID  : {sid or '(not in token)'}")

    import datetime
    exp_dt = datetime.datetime.fromtimestamp(exp) if exp else None
    if exp_dt:
        remaining = exp_dt - datetime.datetime.now()
        hours = remaining.total_seconds() / 3600
        if hours < 0:
            print(f"  Token: EXPIRED ({exp_dt})")
        else:
            print(f"  Token: valid until {exp_dt} (~{hours:.1f}h remaining)")

    update_config(token, wid)
    print("\n[✓] Done! You can now run:")
    print("      py -m infosys.main <course_url_or_id>")
    print()


if __name__ == "__main__":
    main()
