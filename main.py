"""
Main Command Line Interface for Async Web Automation Engine.

Provides an enterprise CLI interface for concurrent workflow orchestration,
browser session synchronization, authentication verification, and telemetry generation.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click

from config.settings import AppSettings, get_settings
from core.models import WorkflowNode
from core.session import SessionManager
from core.telemetry_client import AsyncTelemetryClient
from handlers.workflow_engine import WorkflowEngine
from utils.logger import get_logger, setup_logging

logger = get_logger("engine.cli")

BANNER = r"""
    ___                                  ______            _            
   /   |  _______  ______  _____        / ____/___  ____ _(_)___  ___   
  / /| | / ___/ / / / __ \/ ___/______ / __/ / __ \/ __ `/ / __ \/ _ \  
 / ___ |(__  ) /_/ / / / / /__/_____// /___/ / / / /_/ / / / / /  __/  
/_/  |_/____/\__, /_/ /_/\___/      /_____/_/ /_/\__, /_/_/ /_/\___/   
            /____/                              /____/   v2.0.0 Enterprise
"""


def extract_resource_id_from_url(url_or_id: str) -> str:
    """
    Sanitizes and extracts the unique resource/workflow identifier from a target URL or ID string.
    """
    if not url_or_id.startswith("http"):
        return url_or_id.strip()

    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url_or_id)
    qs = parse_qs(parsed.query)

    # Check for common collection or module ID query parameters
    for key in ("collectionId", "resourceId", "workflowId", "id"):
        if key in qs and qs[key]:
            return qs[key][0]

    # Inspect path components
    segments = [s for s in parsed.path.rstrip("/").split("/") if s]
    for i, seg in enumerate(segments):
        if seg in ("toc", "viewer", "module", "courses", "workflows") and i + 1 < len(segments):
            return segments[i + 1]

    return segments[-1] if segments else url_or_id


async def run_pipeline(
    target: str,
    concurrency: int,
    sync_session: bool,
    validate_auth: bool,
    dry_run: bool,
    settings: AppSettings,
) -> int:
    """
    Executes the asynchronous orchestration pipeline.
    """
    session_mgr = SessionManager(settings)

    # 1. DevTools CDP Session Sync (if requested)
    if sync_session:
        logger.info("Initiating browser session synchronization over CDP...")
        extracted = session_mgr.extract_from_cdp()
        if not extracted:
            logger.error("Session sync failed. Ensure Chrome/Edge is running with remote debugging enabled.")
            return 1
        logger.info(f"Session token synchronized successfully for user: {extracted.user_id}")

    # 2. Asynchronous Telemetry Client Initialization
    async with AsyncTelemetryClient(settings) as client:
        # 3. Credential Validation
        if validate_auth:
            logger.info("Validating authentication credentials...")
            is_valid = await client.verify_credentials()
            if not is_valid:
                logger.error("Authentication check failed. Update .env or refresh session via --sync-session.")
                return 1
            logger.info("Authentication verification passed.")
            if not target:
                return 0

        if not target:
            logger.error("Missing required TARGET workflow identifier or URL.")
            return 1

        resource_id = extract_resource_id_from_url(target)
        logger.info(f"Target Resource Identifier: {resource_id}")

        # 4. Hierarchy Fetching & Traversal
        root_node = await client.fetch_workflow_hierarchy(resource_id)
        if not root_node:
            logger.error(f"Failed to resolve workflow hierarchy for: {resource_id}")
            return 1

        # 5. Workflow Execution Engine
        engine = WorkflowEngine(client=client, settings=settings)
        report = await engine.execute_workflow(root_node=root_node, dry_run=dry_run)

        # 6. Summary Telemetry Output
        click.echo("\n" + "=" * 65)
        click.echo("  TELEMETRY EXECUTION SUMMARY")
        click.echo("=" * 65)
        click.echo(f"  Target ID    : {report.workflow_id}")
        click.echo(f"  Total Items  : {report.total_nodes}")
        click.echo(f"  Completed    : {report.completed_nodes}")
        click.echo(f"  Skipped      : {report.skipped_nodes}")
        click.echo(f"  Failed       : {report.failed_nodes}")
        click.echo(f"  Success Rate : {report.success_rate}%")
        click.echo(f"  Duration     : {report.duration_seconds}s")
        click.echo("=" * 65 + "\n")

        return 0 if report.failed_nodes == 0 else 1


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("target", required=False, default="")
@click.option(
    "--concurrency", "-c",
    type=int,
    default=5,
    help="Number of concurrent worker coroutines for execution.",
)
@click.option(
    "--sync-session", "-s",
    is_flag=True,
    default=False,
    help="Auto-sync session token from active browser via CDP debugger (port 9222).",
)
@click.option(
    "--validate-auth", "-v",
    is_flag=True,
    default=False,
    help="Validate existing or cached authentication credentials.",
)
@click.option(
    "--dry-run", "-d",
    is_flag=True,
    default=False,
    help="Parse and traverse hierarchy without committing remote mutations.",
)
@click.option(
    "--log-level", "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Set logging output verbosity level.",
)
def cli(
    target: str,
    concurrency: int,
    sync_session: bool,
    validate_auth: bool,
    dry_run: bool,
    log_level: str,
) -> None:
    """
    Async Web Automation & Telemetry Engine (v2.0.0).

    TARGET can be a full URL or a unique workflow/course identifier.
    """
    # Initialize settings and structured logger
    settings = get_settings()
    settings.MAX_CONCURRENCY = concurrency
    settings.LOG_LEVEL = log_level

    setup_logging(log_level=settings.LOG_LEVEL, log_file=settings.LOG_FILE)
    click.echo(BANNER)

    exit_code = asyncio.run(
        run_pipeline(
            target=target,
            concurrency=concurrency,
            sync_session=sync_session,
            validate_auth=validate_auth,
            dry_run=dry_run,
            settings=settings,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
