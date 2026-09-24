"""
Session & Cookie Persistence Subsystem.

Encapsulates serialization, deserialization, TTL validation, and automated
extraction of browser session state, cookies, and tokens over Chrome DevTools Protocol.
Enables workflow resumption without manual re-authentication.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from pydantic import ValidationError

from config.settings import AppSettings, get_settings
from core.models import SessionState
from utils.logger import get_logger

logger = get_logger("engine.session")


class SessionManager:
    """
    Manages session lifecycle, persistent storage, and live browser extraction.
    """

    DEFAULT_STORAGE_KEYS = [
        "auth_token",
        "access_token",
        "user-token",
        "jwt",
        "token",
        "auth",
        "kc",
        "keycloak",
        "session",
    ]

    def __init__(self, settings: Optional[AppSettings] = None) -> None:
        self.settings = settings or get_settings()
        self.session_file = Path(self.settings.SESSION_FILE)

    # ── Persistence & Serialization ──────────────────────────────────────────

    def save_session(self, session: SessionState, path: Optional[Path] = None) -> Path:
        """
        Serializes and persists the SessionState model to disk.
        """
        target_path = Path(path) if path else self.session_file
        target_path.parent.mkdir(parents=True, exist_ok=True)

        serialized = session.model_dump_json(indent=2)
        target_path.write_text(serialized, encoding="utf-8")
        logger.info(f"Persisted session state to {target_path} (User: {session.user_id})")
        return target_path

    def load_session(self, path: Optional[Path] = None) -> Optional[SessionState]:
        """
        Loads and validates a persisted SessionState from disk.
        Returns None if file is missing, corrupt, or expired.
        """
        target_path = Path(path) if path else self.session_file
        if not target_path.exists():
            logger.debug(f"No existing session found at {target_path}")
            return None

        try:
            content = target_path.read_text(encoding="utf-8")
            data = json.loads(content)
            session = SessionState(**data)

            if session.is_expired:
                logger.warning(
                    f"Cached session at {target_path} expired at {session.expires_at} UTC. Re-authentication required."
                )
                return None

            logger.info(
                f"Loaded active session for user '{session.user_id}' (expires: {session.expires_at or 'N/A'})"
            )
            return session
        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            logger.warning(f"Failed to deserialize session state from {target_path}: {exc}")
            return None

    # ── JWT Inspection & Decoding ─────────────────────────────────────────────

    @staticmethod
    def decode_jwt(token: str) -> Dict[str, Any]:
        """
        Extracts and parses JWT claims without cryptographic verification.
        Used for expiration inspection and identity claim extraction.
        """
        try:
            segments = token.split(".")
            if len(segments) != 3:
                return {}
            payload_b64 = segments[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            decoded_bytes = base64.b64decode(payload_b64)
            return json.loads(decoded_bytes.decode("utf-8"))
        except Exception as exc:
            logger.debug(f"Unable to parse token as JWT: {exc}")
            return {}

    # ── DevTools Protocol Extraction ──────────────────────────────────────────

    def extract_from_cdp(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        target_url_keyword: Optional[str] = None,
    ) -> Optional[SessionState]:
        """
        Connects via Chrome DevTools Protocol to inspect active browser tabs,
        queries localStorage/sessionStorage across common token keys,
        and constructs a validated SessionState object.
        """
        import websocket

        cdp_host = host or self.settings.CDP_DEBUG_HOST
        cdp_port = port or self.settings.CDP_DEBUG_PORT
        debugger_list_url = f"http://{cdp_host}:{cdp_port}/json"

        logger.info(f"Probing browser DevTools Protocol endpoint at {debugger_list_url}...")

        try:
            with httpx.Client(timeout=4.0) as client:
                resp = client.get(debugger_list_url)
                if resp.status_code != 200:
                    logger.error(f"CDP endpoint returned unexpected status: {resp.status_code}")
                    return None
                targets = resp.json()
        except Exception as exc:
            logger.error(
                f"Failed to connect to CDP debugger on {debugger_list_url}. "
                f"Ensure browser is launched with --remote-debugging-port={cdp_port}. Details: {exc}"
            )
            return None

        # Locate suitable browser page tab
        ws_url = None
        tab_title = "Unknown"
        domain_filter = target_url_keyword or self.settings.TARGET_BASE_URL.replace("https://", "").replace("http://", "").split("/")[0]

        for target in targets:
            url = target.get("url", "")
            candidate_ws = target.get("webSocketDebuggerUrl")
            if candidate_ws and (not domain_filter or domain_filter.lower() in url.lower() or "about:blank" not in url):
                ws_url = candidate_ws
                tab_title = target.get("title", url)
                logger.info(f"Target browser tab detected: '{tab_title}' ({url[:60]})")
                break

        if not ws_url and targets:
            # Fall back to first available page with websocket URL
            ws_url = targets[0].get("webSocketDebuggerUrl")
            tab_title = targets[0].get("title", "Active Tab")

        if not ws_url:
            logger.error("No inspectable browser page found in CDP target list.")
            return None

        # Execute extraction script via CDP Runtime.evaluate
        result_payload: Dict[str, Any] = {}
        js_keys_literal = json.dumps(self.DEFAULT_STORAGE_KEYS)
        js_extractor = f"""
        (() => {{
            const keys = {js_keys_literal};
            for (const key of keys) {{
                try {{
                    const raw = localStorage.getItem(key);
                    if (raw) {{
                        let token = null;
                        try {{
                            const parsed = JSON.parse(raw);
                            token = parsed.token || parsed.access_token || parsed.auth_token || parsed.authToken || parsed.idToken;
                        }} catch (e) {{
                            token = raw;
                        }}
                        if (token && typeof token === 'string' && token.split('.').length === 3) {{
                            return JSON.stringify({{ key: key, token: token, origin: 'localStorage' }});
                        }}
                    }}
                }} catch(e) {{}}
            }}
            for (const key of keys) {{
                try {{
                    const raw = sessionStorage.getItem(key);
                    if (raw) {{
                        let token = null;
                        try {{
                            const parsed = JSON.parse(raw);
                            token = parsed.token || parsed.access_token || parsed.auth_token;
                        }} catch (e) {{
                            token = raw;
                        }}
                        if (token && typeof token === 'string' && token.split('.').length === 3) {{
                            return JSON.stringify({{ key: 'session:' + key, token: token, origin: 'sessionStorage' }});
                        }}
                    }}
                }} catch(e) {{}}
            }}
            return null;
        }})()
        """

        def on_open(ws):
            ws.send(json.dumps({
                "id": 101,
                "method": "Runtime.evaluate",
                "params": {"expression": js_extractor, "returnByValue": True}
            }))

        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get("id") == 101:
                    result = data.get("result", {}).get("result", {})
                    val = result.get("value")
                    if val:
                        result_payload["extracted"] = json.loads(val)
                    ws.close()
            except Exception as e:
                logger.debug(f"CDP message parsing error: {e}")
                ws.close()

        def on_error(ws, error):
            logger.debug(f"CDP WebSocket error: {error}")
            ws.close()

        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
        )
        ws.run_forever(suppress_origin=True)

        extracted = result_payload.get("extracted")
        if not extracted or not extracted.get("token"):
            logger.warning("Could not extract a valid Bearer token from browser localStorage/sessionStorage.")
            return None

        token = extracted["token"]
        claims = self.decode_jwt(token)
        user_id = claims.get("sub") or claims.get("wid") or claims.get("user_id") or "authenticated_user"
        exp_timestamp = claims.get("exp")
        expires_at = datetime.fromtimestamp(exp_timestamp) if exp_timestamp else None

        session_state = SessionState(
            auth_token=token,
            user_id=str(user_id),
            tenant_id=self.settings.TENANT_ID,
            storage_key=extracted.get("key", "extracted_token"),
            expires_at=expires_at,
        )

        self.save_session(session_state)
        return session_state
