"""Core orchestration components.

This module provides the foundational interfaces and utilities for the
modular multi-agent orchestration system.
"""

from .agent_protocol import AgentConfig, AgentExecutionError, AgentProtocol, BaseAgent
from .agent_registry import AgentRegistry

# ModularOrchestrator import moved to avoid circular dependencies
from .state import AgentReport, AgentState, TaskAssignment

__all__ = [
    "AgentConfig",
    "AgentExecutionError",
    "AgentProtocol",
    "AgentRegistry",
    "AgentReport",
    "AgentState",
    "BaseAgent",
    "TaskAssignment",
]
