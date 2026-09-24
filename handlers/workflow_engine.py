"""
Asynchronous Workflow Orchestrator & Task Execution Engine.

Traverses hierarchical node trees, enforces bounded concurrency via asyncio.Semaphore,
filters unsupported leaf types, executes state transitions, and collects structured telemetry metrics.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Callable, List, Optional, Set

from config.settings import AppSettings, get_settings
from core.models import ExecutionReport, StepStatus, WorkflowNode
from core.telemetry_client import AsyncTelemetryClient
from utils.logger import get_logger

logger = get_logger("engine.orchestrator")


class WorkflowEngine:
    """
    Coordinates asynchronous execution of multi-level workflow trees.
    """

    # Module types or MIME patterns that should be gracefully skipped (e.g. manual tests / proctored exams)
    DEFAULT_SKIP_MIME_TYPES: Set[str] = {
        "application/vnd.ekstep.quiz-archive",
        "application/quiz",
        "application/vnd.ekstep.ecml-archive",
        "application/iap-assessment",
        "application/assessment",
    }

    DEFAULT_SKIP_PATTERNS: Set[str] = {
        "proctored assessment",
        "iap assessment",
        "final certification exam",
    }

    def __init__(
        self,
        client: AsyncTelemetryClient,
        settings: Optional[AppSettings] = None,
    ) -> None:
        self.client = client
        self.settings = settings or get_settings()
        self.semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENCY)

    def is_actionable_node(self, node: WorkflowNode) -> bool:
        """Determines whether a leaf node can be automated or should be bypassed."""
        mime = (node.mime_type or "").lower()
        name = (node.name or "").lower()

        if mime in self.DEFAULT_SKIP_MIME_TYPES:
            return False

        if any(pat in name for pat in self.DEFAULT_SKIP_PATTERNS):
            return False

        return True

    async def execute_workflow(
        self,
        root_node: WorkflowNode,
        dry_run: bool = False,
    ) -> ExecutionReport:
        """
        Executes all actionable nodes within a hierarchy tree using bounded concurrency.
        """
        all_leaves: List[WorkflowNode] = root_node.collect_leaves()
        start_time = datetime.utcnow()
        t0 = time.monotonic()

        report = ExecutionReport(
            workflow_id=root_node.identifier,
            total_nodes=len(all_leaves),
            start_time=start_time,
        )

        actionable_nodes: List[WorkflowNode] = []
        for node in all_leaves:
            if self.is_actionable_node(node):
                actionable_nodes.append(node)
            else:
                report.skipped_nodes += 1
                report.node_details.append({
                    "id": node.identifier,
                    "name": node.name,
                    "status": StepStatus.SKIPPED.value,
                    "duration": 0.0,
                    "reason": "Unsupported MIME or proctored assessment pattern",
                })
                logger.info(f"[SKIP]  {node.name[:60]:<60} (Skipped)")

        logger.info(
            f"Orchestration starting: {len(actionable_nodes)} actionable tasks "
            f"({report.skipped_nodes} skipped) across {self.settings.MAX_CONCURRENCY} workers."
        )

        if dry_run:
            logger.info("Dry-run mode active. No remote mutations will be dispatched.")
            for node in actionable_nodes:
                report.completed_nodes += 1
                report.node_details.append({
                    "id": node.identifier,
                    "name": node.name,
                    "status": StepStatus.COMPLETED.value,
                    "duration": 0.0,
                    "dry_run": True,
                })
            report.duration_seconds = time.monotonic() - t0
            report.end_time = datetime.utcnow()
            return report

        # Concurrent task execution with worker semaphore
        async def worker_task(node: WorkflowNode):
            async with self.semaphore:
                node_t0 = time.monotonic()
                try:
                    success = await self.client.dispatch_step_completion(node)
                    elapsed = time.monotonic() - node_t0
                    status = StepStatus.COMPLETED if success else StepStatus.FAILED

                    if success:
                        report.completed_nodes += 1
                        logger.info(f"[OK]    {node.name[:60]:<60} ({elapsed:.2f}s)")
                    else:
                        report.failed_nodes += 1
                        logger.warning(f"[FAIL]  {node.name[:60]:<60} ({elapsed:.2f}s)")

                    report.node_details.append({
                        "id": node.identifier,
                        "name": node.name,
                        "status": status.value,
                        "duration": round(elapsed, 3),
                    })
                except Exception as exc:
                    elapsed = time.monotonic() - node_t0
                    report.failed_nodes += 1
                    logger.error(f"[ERROR] {node.name[:60]:<60} failed: {exc}")
                    report.node_details.append({
                        "id": node.identifier,
                        "name": node.name,
                        "status": StepStatus.FAILED.value,
                        "duration": round(elapsed, 3),
                        "error": str(exc),
                    })

        tasks = [worker_task(node) for node in actionable_nodes]
        await asyncio.gather(*tasks)

        # Trigger top-level aggregation/recalculation
        logger.info("Triggering parent workflow aggregation & state reconciliation...")
        recalc_success = await self.client.trigger_workflow_aggregation(root_node.identifier)
        if recalc_success:
            logger.info("Parent workflow state successfully aggregated.")
        else:
            logger.debug("Parent recalculation signal acknowledged.")

        report.duration_seconds = round(time.monotonic() - t0, 2)
        report.end_time = datetime.utcnow()

        logger.info(
            f"Execution finished in {report.duration_seconds}s. "
            f"Completed: {report.completed_nodes}, Skipped: {report.skipped_nodes}, "
            f"Failed: {report.failed_nodes} (Success rate: {report.success_rate}%)"
        )
        return report
