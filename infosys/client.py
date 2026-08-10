from __future__ import annotations

import time
from typing import Optional

import httpx
from loguru import logger

from .config import ensure_auth, get_headers


class InfosysClient:
    """Thin authenticated HTTP client for the Wingspan / Infosys Springboard API."""

    def __init__(self) -> None:
        self.auth     = ensure_auth()
        self.base     = self.auth["base_url"].rstrip("/")
        self._session = httpx.Client(
            timeout=60.0,
            follow_redirects=True,
            headers=get_headers(self.auth),
        )

    # ── Low-level helpers ─────────────────────────────────────────────────────

    def get(self, path: str, **kwargs) -> Optional[dict]:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Optional[dict]:
        return self._request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs) -> Optional[dict]:
        return self._request("PATCH", path, **kwargs)

    def _request(
        self,
        method: str,
        path: str,
        retries: int = 3,
        **kwargs,
    ) -> Optional[dict]:
        url = path if path.startswith("http") else self.base + path

        # Merge any per-request headers with the session headers
        if "headers" in kwargs:
            merged = dict(self._session.headers)
            merged.update(kwargs.pop("headers"))
            kwargs["headers"] = merged

        for attempt in range(1, retries + 1):
            try:
                resp = self._session.request(method, url, **kwargs)
                if resp.status_code in (200, 201, 204):
                    try:
                        return resp.json()
                    except Exception:
                        return {}
                elif resp.status_code == 401:
                    logger.error(
                        "401 Unauthorized — your auth-token is expired. "
                        "Run: py sync_token.py   OR   update config.json manually."
                    )
                    return None
                elif resp.status_code == 403:
                    logger.warning(
                        f"403 Forbidden on {url} — check rootorg/org headers."
                    )
                    return None
                else:
                    logger.warning(
                        f"[{method}] {url} → {resp.status_code} "
                        f"(attempt {attempt}/{retries}): {resp.text[:200]}"
                    )
                    if attempt < retries:
                        time.sleep(2.0 * attempt)
            except httpx.HTTPError as exc:
                logger.warning(f"Network error on {url} (attempt {attempt}/{retries}): {exc}")
                if attempt < retries:
                    time.sleep(2.0 * attempt)
        return None

    # ── Auth check ────────────────────────────────────────────────────────────

    def verify_auth(self) -> bool:
        """Returns True if auth credentials are valid."""
        import base64
        import json
        import datetime
        from .config import get_telemetry_headers

        token = self.auth.get("auth-token", "")
        wid = self.auth.get("wid", "")

        # 1. JWT Payload Check
        try:
            parts = token.split(".")
            if len(parts) == 3:
                payload_b64 = parts[1]
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                payload = json.loads(base64.b64decode(payload_b64).decode("utf-8"))
                exp = payload.get("exp", 0)
                exp_dt = datetime.datetime.fromtimestamp(exp) if exp else None

                if exp_dt and exp_dt < datetime.datetime.now():
                    logger.error(f"JWT Token EXPIRED at {exp_dt}")
                    return False
                
                jwt_wid = payload.get("wid") or payload.get("sub")
                logger.info(f"JWT token valid for user: {payload.get('name', 'User')} (wid: {jwt_wid})")
        except Exception as e:
            logger.warning(f"Could not parse JWT token: {e}")

        # 2. Online verification via telemetry heartbeat endpoint
        now_ms = int(time.time() * 1000)
        tele_headers = get_telemetry_headers(self.auth)
        tele_payload = {
            "id": "ekstep.telemetry",
            "ver": "3.0",
            "ets": now_ms,
            "events": [{
                "eid": "HEARTBEAT",
                "ets": now_ms,
                "ver": "3.0",
                "mid": f"HB:{wid}:{now_ms}",
                "actor": {"id": wid, "type": "User"},
                "context": {
                    "channel": self.auth.get("root_org", "infosysheadstart"),
                    "pdata": {"id": "infosysheadstart-web-ui", "ver": "1.0.0"},
                    "env": "prod",
                    "sid": "",
                    "did": "a989028d9a54d69cb9e6470e9485431d",
                    "cdata": [],
                    "rollup": {}
                },
                "tags": [self.auth.get("root_org", "infosysheadstart")],
                "edata": {}
            }]
        }

        resp = self.post(
            "/api-gw/wn-apis/infosysheadstart/lex-sb-telemetry/v1/telemetry",
            json=tele_payload,
            headers=tele_headers
        )
        if resp is not None:
            logger.info("Authentication verified via telemetry service!")
            return True

        # Fallback check: standard Wingspan proxy endpoint if available
        resp = self.get("/apis/proxies/v8/user/v3/details")
        if resp and (resp.get("id") or resp.get("userId") or resp.get("wid")):
            logger.info(f"Authenticated as: {resp.get('id') or resp.get('wid')}")
            return True

        logger.error(
            "Authentication failed. Your token is likely expired.\n"
            "  → Run:  py sync_token.py   (if Chrome is open with --remote-debugging-port=9222)\n"
            "  → Or:   manually update auth-token in ~/.infosys-course/config.json"
        )
        return False
