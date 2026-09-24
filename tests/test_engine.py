"""
Unit and Integration Test Suite for Async Web Automation Engine.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import pytest

from config.settings import AppSettings
from core.models import WorkflowNode, SessionState, StepStatus
from core.session import SessionManager
from utils.retry import async_exponential_backoff


def test_settings_validation():
    """Verify that default settings load with expected typing and bounds."""
    settings = AppSettings(
        TARGET_BASE_URL="https://test.example.com",
        MAX_CONCURRENCY=10,
        RETRY_ATTEMPTS=4,
    )
    assert settings.TARGET_BASE_URL == "https://test.example.com"
    assert settings.MAX_CONCURRENCY == 10
    assert settings.RETRY_ATTEMPTS == 4
    headers = settings.get_common_headers()
    assert "User-Agent" in headers
    assert "X-Tenant-ID" in headers


def test_workflow_node_hierarchy_and_leaves():
    """Verify hierarchical tree traversal and leaf node collection."""
    leaf_1 = WorkflowNode(identifier="leaf_1", name="Step 1", mime_type="video/mp4")
    leaf_2 = WorkflowNode(identifier="leaf_2", name="Step 2", mime_type="application/pdf")
    sub_module = WorkflowNode(
        identifier="sub_mod",
        name="Sub Module",
        children=[leaf_2],
    )
    root = WorkflowNode(
        identifier="root_workflow",
        name="Main Workflow",
        children=[leaf_1, sub_module],
    )

    assert not root.is_leaf
    assert leaf_1.is_leaf
    assert not sub_module.is_leaf
    assert leaf_2.is_leaf

    leaves = root.collect_leaves()
    assert len(leaves) == 2
    assert leaves[0].identifier == "leaf_1"
    assert leaves[1].identifier == "leaf_2"


def test_session_state_expiration():
    """Verify TTL and expiration logic on session state models."""
    now = datetime.now(timezone.utc)
    active_session = SessionState(
        auth_token="sample_token",
        user_id="user_123",
        expires_at=now + timedelta(hours=2),
    )
    assert not active_session.is_expired

    expired_session = SessionState(
        auth_token="sample_token",
        user_id="user_123",
        expires_at=now - timedelta(minutes=5),
    )
    assert expired_session.is_expired


def test_jwt_decoder_parsing():
    """Verify offline base64 claims decoding without signature verification."""
    # Header: {"alg":"none","typ":"JWT"} -> eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0
    # Payload: {"sub":"usr_test_999","name":"DevOps Engineer","exp":1893456000}
    sample_jwt = (
        "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0."
        "eyJzdWIiOiJ1c3JfdGVzdF85OTkiLCJuYW1lIjoiRGV2T3BzIEVuZ2luZWVyIiwiZXhwIjoxODkzNDU2MDAwfQ."
    )
    claims = SessionManager.decode_jwt(sample_jwt)
    assert claims.get("sub") == "usr_test_999"
    assert claims.get("name") == "DevOps Engineer"
    assert claims.get("exp") == 1893456000


@pytest.mark.asyncio
async def test_async_exponential_backoff_decorator():
    """Verify retry policy recovers on transient failures and counts attempts."""
    attempts = 0

    @async_exponential_backoff(retries=3, initial_delay=0.01, backoff_factor=1.1)
    async def flaky_operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("Transient network drop")
        return "success"

    result = await flaky_operation()
    assert result == "success"
    assert attempts == 3
