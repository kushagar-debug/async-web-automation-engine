"""
Global Application Configuration and Environment Settings.

Utilizes pydantic-settings and python-dotenv to decouple all environment-specific
endpoints, authentication credentials, browser configurations, and telemetry options.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load local environment variables from .env if present
load_dotenv(override=False)


class AppSettings(BaseSettings):
    """
    Unified Application Settings schema with strict typing and validation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Target Endpoints & Networking ──────────────────────────────────────────
    TARGET_BASE_URL: str = Field(
        default="https://app.target-platform.internal",
        description="Root URL of the target web application or SPA portal",
    )
    API_BASE_URL: Optional[str] = Field(
        default=None,
        description="Optional separate API gateway URL. Defaults to TARGET_BASE_URL if unset",
    )
    REQUEST_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="Network request timeout in seconds for API and telemetry calls",
    )

    # ── Authentication & Security Context ─────────────────────────────────────
    AUTH_TOKEN: str = Field(
        default="",
        description="Bearer token or OAuth/JWT access token for authenticated requests",
    )
    USER_ID: str = Field(
        default="",
        description="Unique user/worker identifier (WID/UID/Subject)",
    )
    TENANT_ID: str = Field(
        default="enterprise-core",
        description="Multi-tenant identifier for routing headers",
    )
    ORGANIZATION_ID: str = Field(
        default="enterprise-core",
        description="Sub-organization or business unit identifier",
    )

    # ── Browser Automation & Remote Debugging (CDP) ───────────────────────────
    CDP_DEBUG_HOST: str = Field(
        default="127.0.0.1",
        description="Host address for Chrome DevTools Protocol debugging",
    )
    CDP_DEBUG_PORT: int = Field(
        default=9222,
        description="Port for Chrome DevTools Protocol debugging",
    )
    BROWSER_HEADLESS: bool = Field(
        default=True,
        description="Run browser in headless mode during Playwright operations",
    )
    BROWSER_TIMEOUT_MS: int = Field(
        default=30000,
        description="Playwright explicit wait and action timeout in milliseconds",
    )
    SLOW_MO_MS: int = Field(
        default=0,
        description="Slow down Playwright actions by milliseconds for debugging",
    )

    # ── Concurrency & Resilience Policies ─────────────────────────────────────
    MAX_CONCURRENCY: int = Field(
        default=5,
        description="Maximum concurrent asynchronous tasks in the worker pool",
    )
    RETRY_ATTEMPTS: int = Field(
        default=3,
        description="Maximum retry attempts for transient network or DOM errors",
    )
    RETRY_BACKOFF_FACTOR: float = Field(
        default=1.5,
        description="Multiplier for exponential backoff calculations",
    )
    CIRCUIT_BREAKER_THRESHOLD: int = Field(
        default=5,
        description="Consecutive failure threshold before pausing dispatch",
    )

    # ── State Persistence & Session Caching ───────────────────────────────────
    SESSION_CACHE_DIR: Path = Field(
        default=Path(".sessions"),
        description="Directory used to serialize and cache browser session state",
    )
    SESSION_FILE: Path = Field(
        default=Path(".sessions/session_state.json"),
        description="Target file for serialized cookies, tokens, and storage state",
    )

    # ── Observability & Telemetry ─────────────────────────────────────────────
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Standard logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    LOG_FILE: Path = Field(
        default=Path("logs/automation_engine.log"),
        description="File path for structured rotating log records",
    )
    TELEMETRY_ENABLED: bool = Field(
        default=True,
        description="Enable real-time telemetry and state synchronization",
    )

    @field_validator("API_BASE_URL", mode="before")
    @classmethod
    def resolve_api_base_url(cls, v: Optional[str], info) -> Optional[str]:
        if not v and "TARGET_BASE_URL" in info.data:
            return info.data["TARGET_BASE_URL"]
        return v

    def get_api_endpoint(self, path: str) -> str:
        """Constructs an absolute API endpoint URL given a relative path."""
        base = (self.API_BASE_URL or self.TARGET_BASE_URL).rstrip("/")
        normalized_path = "/" + path.lstrip("/")
        return f"{base}{normalized_path}"

    def get_common_headers(self) -> Dict[str, str]:
        """
        Generates standard request headers incorporating decoupled tenant and auth context.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36 AsyncAutomationEngine/2.0"
            ),
            "X-Tenant-ID": self.TENANT_ID,
            "X-Organization-ID": self.ORGANIZATION_ID,
        }
        if self.AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {self.AUTH_TOKEN}"
        if self.USER_ID:
            headers["X-User-ID"] = self.USER_ID
        return headers


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    Returns a cached instance of validated AppSettings.
    """
    return AppSettings()
