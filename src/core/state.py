"""Shared state definitions for multi-agent orchestration.

This module defines the state structures and models used across all agents
and the orchestration system.
"""

from typing import Any, TypedDict

from langchain_core.messages import BaseMessage

from ..schemas import AgentReport, TaskDelegation


class AgentState(TypedDict):
    """Shared state between agents."""

    messages: list[BaseMessage]
    task_id: int | None
    task_data: dict[str, Any] | None
    agent_outputs: dict[str, Any]
    batch_id: str | None
    coordination_context: dict[str, Any]
    error_context: dict[str, Any] | None
    next_agent: str | None


# Type aliases for backwards compatibility and clarity
TaskAssignment = TaskDelegation  # Legacy alias
AgentReportV2 = AgentReport  # Legacy alias
