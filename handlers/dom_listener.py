"""
Dynamic DOM State Listener & SPA Lifecycle Monitor.

Injects MutationObserver scripts to listen for asynchronous UI mutations,
virtual DOM hydrations, loader spinner dismissals, and single-page application (SPA) client routes.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional

from playwright.async_api import Page

from utils.logger import get_logger

logger = get_logger("engine.dom_listener")


class DOMStateListener:
    """
    Monitors client-side DOM mutations and event cycles inside a Playwright Page.
    """

    def __init__(self, page: Page) -> None:
        self.page = page
        self._observer_installed = False

    async def attach_mutation_observer(self) -> None:
        """
        Installs an in-page MutationObserver that tallies DOM additions/removals
        and tracks SPA URL history mutations.
        """
        if self._observer_installed:
            return

        observer_script = """
        (() => {
            if (window.__automationObserverAttached) return;
            window.__automationObserverAttached = true;
            window.__domMutationCount = 0;
            window.__lastMutationTimestamp = Date.now();

            const observer = new MutationObserver((mutations) => {
                window.__domMutationCount += mutations.length;
                window.__lastMutationTimestamp = Date.now();
            });

            observer.observe(document.body || document.documentElement, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['class', 'style', 'hidden', 'aria-hidden']
            });

            // Track History API pushes for client-side SPA routing
            const originalPushState = history.pushState;
            window.__lastNavigationRoute = window.location.href;
            history.pushState = function(...args) {
                originalPushState.apply(this, args);
                window.__lastNavigationRoute = window.location.href;
                window.__lastMutationTimestamp = Date.now();
            };
        })();
        """
        await self.page.evaluate(observer_script)
        self._observer_installed = True
        logger.debug("Attached DOM MutationObserver and SPA routing interceptor.")

    async def wait_until_dom_settled(
        self,
        quiet_period_ms: int = 400,
        max_wait_ms: int = 10000,
    ) -> bool:
        """
        Polls DOM state until no new mutations have occurred within `quiet_period_ms`.
        Essential for SPAs (React, Angular, Vue) where elements continue to stream in.
        """
        await self.attach_mutation_observer()
        start_time = asyncio.get_event_loop().time()
        max_wait_sec = max_wait_ms / 1000.0
        quiet_sec = quiet_period_ms / 1000.0

        while (asyncio.get_event_loop().time() - start_time) < max_wait_sec:
            last_timestamp = await self.page.evaluate("window.__lastMutationTimestamp || Date.now()")
            now_ms = await self.page.evaluate("Date.now()")
            elapsed_since_mutation = (now_ms - last_timestamp) / 1000.0

            if elapsed_since_mutation >= quiet_sec:
                logger.debug(f"DOM settled: no mutations for {quiet_period_ms}ms.")
                return True

            await asyncio.sleep(0.1)

        logger.warning(f"DOM settlement timed out after {max_wait_ms}ms. Proceeding under best-effort.")
        return False

    async def wait_for_loader_dismissal(
        self,
        spinner_selectors: Optional[List[str]] = None,
        timeout_ms: int = 15000,
    ) -> None:
        """
        Waits for common UI spinners, progress overlays, or skeleton loaders to disappear.
        """
        default_selectors = [
            ".spinner",
            ".loading",
            ".loader",
            "[role='progressbar']",
            ".skeleton-loader",
            ".overlay-loading",
        ]
        selectors = spinner_selectors or default_selectors

        for selector in selectors:
            try:
                # If present, wait until detached or hidden
                element = await self.page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    if is_visible:
                        logger.debug(f"Awaiting dismissal of loader element: {selector}")
                        await self.page.wait_for_selector(
                            selector,
                            state="hidden",
                            timeout=timeout_ms,
                        )
            except Exception as exc:
                logger.debug(f"Loader wait check skipped for '{selector}': {exc}")
