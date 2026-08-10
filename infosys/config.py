from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

# ── Config paths ──────────────────────────────────────────────────────────────
CONFIG_DIR  = Path.home() / ".infosys-course"
CONFIG_FILE = CONFIG_DIR  / "config.json"

# Root org / org values MUST be "infosysheadstart" — this is what the backend
# router validates against (captured from live browser telemetry requests).
DEFAULT_CONFIG: dict = {
    "base_url": "https://infyspringboard.onwingspan.com",
    "root_org": "infosysheadstart",
    "org":      "infosysheadstart",
    "auth": {
        "auth-token": "...",
        "wid":        "..."
    }
}

BASE_URL = "https://infyspringboard.onwingspan.com"

# ── Loader ────────────────────────────────────────────────────────────────────
def load_config() -> dict:
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
        logger.warning(
            f"Config file created at {CONFIG_FILE}. "
            "Please fill in your auth-token and wid."
        )
    return json.loads(CONFIG_FILE.read_text())


def ensure_auth() -> dict:
    """Return the full auth dict from config, raising on placeholders."""
    cfg   = load_config()
    auth  = cfg.get("auth", {})
    token = auth.get("auth-token", "...")
    wid   = auth.get("wid", "...")

    if token == "..." or wid == "...":
        logger.error(
            f"Auth credentials not set. Edit {CONFIG_FILE} "
            "and fill in 'auth-token' and 'wid'."
        )
        raise SystemExit(1)

    return {
        "auth-token": token,
        "wid":        wid,
        "root_org":   cfg.get("root_org", DEFAULT_CONFIG["root_org"]),
        "org":        cfg.get("org",      DEFAULT_CONFIG["org"]),
        "base_url":   cfg.get("base_url", DEFAULT_CONFIG["base_url"]),
    }


# ── Common request headers ────────────────────────────────────────────────────
# Header casing must match exactly what the Springboard backend/router expects.
# "rootOrg" (camelCase) is required for the telemetry router.
# "rootorg" (lowercase) is required for the main API gateway.
# Both are included since httpx merges per-request headers with session headers.
def get_headers(auth: dict) -> dict:
    return {
        "Authorization":    f"Bearer {auth['auth-token']}",
        "wid":              auth["wid"],
        "rootOrg":          auth["root_org"],
        "org":              auth["org"],
        "hostpath":         "infyspringboard.onwingspan.com",
        "langcode":         "en",
        "locale":           "en",
        "Content-Type":     "application/json",
        "Accept":           "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        ),
    }


# Extra headers required ONLY for telemetry endpoint (camelCase variants)
def get_telemetry_headers(auth: dict) -> dict:
    base = get_headers(auth)
    base.update({
        "rootOrg":          auth["root_org"],   # camelCase — telemetry router
        "dataType":         "json",             # camelCase
        "X-Requested-With": "XMLHttpRequest",
        "origin":           "https://infyspringboard.onwingspan.com",
    })
    return base
