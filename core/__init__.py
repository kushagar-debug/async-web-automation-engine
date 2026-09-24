"""
Core automation package containing models, session orchestration, browser lifecycle,
and asynchronous HTTP telemetry clients.
"""

from .models import WorkflowNode, SessionState, ExecutionReport, TelemetryEvent
from .session import SessionManager
from .telemetry_client import AsyncTelemetryClient

__all__ = [
    "WorkflowNode",
    "SessionState",
    "ExecutionReport",
    "TelemetryEvent",
    "SessionManager",
    "AsyncTelemetryClient",
]
