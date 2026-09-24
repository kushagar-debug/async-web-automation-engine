#!/usr/bin/env python
"""
Automated Session & Token Synchronization Utility.

Extracts live session tokens, authorization headers, and cookies from an active
browser instance running with Chrome DevTools Protocol (CDP) enabled.
Persists sanitized session state into .sessions/session_state.json.
"""

from __future__ import annotations

import sys
from config.settings import get_settings
from core.session import SessionManager
from utils.logger import get_logger, setup_logging

logger = get_logger("engine.sync_session")


def main() -> None:
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL, log_file=settings.LOG_FILE)

    print("=" * 65)
    print("  Async Web Automation Engine — Session Token Synchronizer")
    print("=" * 65)

    session_mgr = SessionManager(settings)
    session = session_mgr.extract_from_cdp()

    if not session:
        print("\n[ERROR] Could not extract session state from active browser.")
        print(f"  → Ensure Chrome/Edge was launched with --remote-debugging-port={settings.CDP_DEBUG_PORT}")
        print("  → Ensure you are logged into your target web application in that browser window.")
        sys.exit(1)

    print(f"\n[OK] Successfully synchronized session!")
    print(f"  User ID    : {session.user_id}")
    print(f"  Token Key  : {session.storage_key}")
    print(f"  Expires At : {session.expires_at or 'Session duration / persistent'}")
    print(f"  Saved To   : {settings.SESSION_FILE}")
    print("\nYou can now execute workflows using:")
    print("  py main.py <target_url_or_id>\n")


if __name__ == "__main__":
    main()
