"""
Domain Data Models and Schemas.

Defines Pydantic models for hierarchical workflow execution, dynamic DOM telemetry,
session serialization, and batch execution reporting.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowNode(BaseModel):
    """
    Represents an atomic or composite execution unit within a hierarchical workflow.
    """
    identifier: str = Field(description="Unique identifier for the workflow node")
    name: str = Field(description="Human-readable title or label")
    content_type: str = Field(default="", description="Content or module type classification")
    mime_type: str = Field(default="", description="MIME type or resource format indicator")
    status: str = Field(default="Live", description="Publishing or readiness status")
    children: List[WorkflowNode] = Field(default_factory=list, description="Sub-nodes or dependencies")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata attributes")

    @property
    def is_leaf(self) -> bool:
        """Determines if the node is an actionable leaf unit without further children."""
        return len(self.children) == 0

    def collect_leaves(self) -> List[WorkflowNode]:
        """Recursively traverses the tree and collects all actionable leaf nodes."""
        if self.is_leaf:
            return [self]
        leaves: List[WorkflowNode] = []
        for child in self.children:
            leaves.extend(child.collect_leaves())
        return leaves


class SessionState(BaseModel):
    """
    Encapsulates persistent browser cookies, authorization headers, and JWT metadata.
    """
    auth_token: str = Field(description="Bearer authorization token")
    user_id: str = Field(description="Unique subject or user identifier")
    tenant_id: str = Field(default="", description="Tenant or organization identifier")
    storage_key: str = Field(default="session", description="Storage origin key")
    cookies: List[Dict[str, Any]] = Field(default_factory=list, description="Serialized browser cookies")
    local_storage: Dict[str, str] = Field(default_factory=dict, description="Extracted localStorage items")
    expires_at: Optional[datetime] = Field(default=None, description="Token expiration timestamp")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")

    @property
    def is_expired(self) -> bool:
        """Checks if session token has surpassed its expiration threshold."""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at


class TelemetryEvent(BaseModel):
    """
    Structured telemetry event emitted during workflow step execution.
    """
    event_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    node_id: str
    status: StepStatus
    duration_seconds: float = 0.0
    details: Dict[str, Any] = Field(default_factory=dict)


class ExecutionReport(BaseModel):
    """
    Consolidated telemetry metrics report summarizing an entire workflow run.
    """
    workflow_id: str
    total_nodes: int = 0
    completed_nodes: int = 0
    skipped_nodes: int = 0
    failed_nodes: int = 0
    duration_seconds: float = 0.0
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    node_details: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        actionable = self.total_nodes - self.skipped_nodes
        if actionable <= 0:
            return 100.0
        return round((self.completed_nodes / actionable) * 100.0, 2)
