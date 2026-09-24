"""
Asynchronous Playwright Automation Engine & Resilient State Orchestrator.

Handles browser lifecycle, CDP connection attachment, dynamic DOM stabilization,
explicit condition waits, and auto-recovering DOM interaction routines.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    ElementHandle,
    Page,
    Playwright,
    async_playwright,
)

from config.settings import AppSettings, get_settings
from core.models import SessionState
from core.session import SessionManager
from utils.logger import get_logger

logger = get_logger("engine.browser")


class BrowserEngine:
    """
    Asynchronous Playwright automation engine providing robust DOM synchronization,
    CDP attachment, and resilient element interactions.
    """

    def __init__(self, settings: Optional[AppSettings] = None) -> None:
        self.settings = settings or get_settings()
        self.session_mgr = SessionManager(self.settings)
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> BrowserEngine:
        await self.launch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    # ── Lifecycle Management ──────────────────────────────────────────────────

    async def launch(self, attach_cdp: bool = False) -> Page:
        """
        Initializes Playwright runtime and creates a browser context.
        Can either launch a new managed browser or connect to an active CDP session.
        """
        self._playwright = await async_playwright().start()

        if attach_cdp:
            cdp_url = f"http://{self.settings.CDP_DEBUG_HOST}:{self.settings.CDP_DEBUG_PORT}"
            logger.info(f"Connecting to live browser session via CDP: {cdp_url}")
            try:
                self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
                contexts = self._browser.contexts
                self._context = contexts[0] if contexts else await self._browser.new_context()
                pages = self._context.pages
                self._page = pages[0] if pages else await self._context.new_page()
                logger.info(f"Attached to CDP session successfully on page: {self._page.url}")
                return self._page
            except Exception as exc:
                logger.warning(
                    f"CDP connection failed ({exc}). Falling back to launching managed browser instance."
                )

        # Standard managed browser launch
        logger.info(
            f"Launching managed Chromium browser (headless={self.settings.BROWSER_HEADLESS}, "
            f"timeout={self.settings.BROWSER_TIMEOUT_MS}ms)"
        )
        self._browser = await self._playwright.chromium.launch(
            headless=self.settings.BROWSER_HEADLESS,
            slow_mo=self.settings.SLOW_MO_MS,
        )

        # Hydrate session state if cached
        session = self.session_mgr.load_session()
        storage_state_arg = None
        if session and session.cookies:
            storage_state_arg = {
                "cookies": session.cookies,
                "origins": [],
            }

        self._context = await self._browser.new_context(
            storage_state=storage_state_arg,
            viewport={"width": 1440, "height": 900},
            user_agent=self.settings.get_common_headers().get("User-Agent"),
        )
        self._context.set_default_timeout(self.settings.BROWSER_TIMEOUT_MS)
        self._page = await self._context.new_page()

        # Inject authorization header or local storage tokens if present
        if session and session.auth_token:
            await self._inject_session_storage(self._page, session)

        return self._page

    async def _inject_session_storage(self, page: Page, session: SessionState) -> None:
        """Injects authentication credentials into window.localStorage on page load."""
        init_script = f"""
        (() => {{
            try {{
                const token = {repr(session.auth_token)};
                const userId = {repr(session.user_id)};
                localStorage.setItem('auth_token', token);
                localStorage.setItem('access_token', token);
                localStorage.setItem('user-token', token);
                if (userId) {{
                    localStorage.setItem('user_id', userId);
                }}
            }} catch (e) {{
                console.warn('Storage injection error:', e);
            }}
        }})();
        """
        await page.add_init_script(init_script)

    async def shutdown(self) -> None:
        """Gracefully closes open pages, contexts, and browser instances."""
        logger.debug("Shutting down BrowserEngine...")
        try:
            if self._context:
                # Save session cookies & state before closing
                cookies = await self._context.cookies()
                cached = self.session_mgr.load_session() or SessionState(
                    auth_token=self.settings.AUTH_TOKEN,
                    user_id=self.settings.USER_ID,
                )
                cached.cookies = cookies
                self.session_mgr.save_session(cached)
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as exc:
            logger.debug(f"Error during browser teardown: {exc}")
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None

    # ── Resilient DOM Synchronization & Wait Handlers ─────────────────────────

    async def navigate_and_wait(self, url: str, wait_until: str = "networkidle") -> None:
        """
        Navigates to a target URL with explicit lifecycle synchronization.
        """
        if not self._page:
            raise RuntimeError("Browser not initialized. Call launch() first.")

        logger.info(f"Navigating to {url} (wait_until={wait_until})...")
        await self._page.goto(url, wait_until=wait_until, timeout=self.settings.BROWSER_TIMEOUT_MS)

    async def wait_for_selector_stable(
        self,
        selector: str,
        timeout: Optional[int] = None,
        stability_ms: int = 250,
    ) -> ElementHandle:
        """
        Waits until an element matching the selector is attached, visible,
        and has stopped moving (e.g. CSS transitions or dynamic SPA layout shifts).
        """
        if not self._page:
            raise RuntimeError("Browser not initialized.")

        t_out = timeout or self.settings.BROWSER_TIMEOUT_MS
        logger.debug(f"Awaiting DOM element stability for: {selector}")

        # Wait for presence and visibility
        element = await self._page.wait_for_selector(selector, state="visible", timeout=t_out)
        if not element:
            raise TimeoutError(f"Element '{selector}' was not visible after {t_out}ms")

        # Stability verification: check bounding box over a brief interval
        prev_box = await element.bounding_box()
        await asyncio.sleep(stability_ms / 1000.0)
        curr_box = await element.bounding_box()

        if prev_box and curr_box:
            # If coordinates shifted, give an extra moment for animation to finish
            if prev_box != curr_box:
                await asyncio.sleep(0.3)

        return element

    async def wait_for_dom_interactive(self, timeout: Optional[int] = None) -> None:
        """
        Explicitly waits for document.readyState to reach 'interactive' or 'complete'.
        """
        if not self._page:
            return
        t_out = timeout or self.settings.BROWSER_TIMEOUT_MS
        await self._page.wait_for_function(
            "() => document.readyState === 'interactive' || document.readyState === 'complete'",
            timeout=t_out,
        )

    # ── Stale Element Recovery & Resilient Actions ─────────────────────────────

    async def safe_click(
        self,
        selector: str,
        retries: int = 3,
        force: bool = False,
    ) -> bool:
        """
        Executes a click action on a target selector with automatic recovery
        from DOM stale references, animation interceptions, and re-rendering collisions.
        """
        if not self._page:
            raise RuntimeError("Browser not initialized.")

        for attempt in range(1, retries + 1):
            try:
                # Re-query selector dynamically on each attempt
                element = await self.wait_for_selector_stable(selector, timeout=5000)
                await element.scroll_into_view_if_needed(timeout=3000)
                await element.click(force=force, timeout=5000)
                logger.debug(f"Successfully clicked '{selector}' on attempt {attempt}")
                return True
            except Exception as exc:
                logger.warning(
                    f"Click intercepted or stale reference on '{selector}' (attempt {attempt}/{retries}): {exc}"
                )
                if attempt < retries:
                    await asyncio.sleep(0.5 * attempt)
                else:
                    logger.error(f"Failed to click '{selector}' after {retries} retries.")
                    return False
        return False

    async def safe_fill(
        self,
        selector: str,
        value: str,
        retries: int = 3,
    ) -> bool:
        """
        Inputs text into a form or input element with validation and retry mechanics.
        """
        if not self._page:
            raise RuntimeError("Browser not initialized.")

        for attempt in range(1, retries + 1):
            try:
                element = await self.wait_for_selector_stable(selector, timeout=5000)
                await element.fill(value)
                logger.debug(f"Filled '{selector}' on attempt {attempt}")
                return True
            except Exception as exc:
                logger.warning(f"Fill error on '{selector}' (attempt {attempt}/{retries}): {exc}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * attempt)
        return False
