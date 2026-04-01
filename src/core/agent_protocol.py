"""Standardized agent protocol interface.

This module defines the core interfaces that all agents must implement
to ensure consistent behavior and enable dynamic agent discovery.
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from .state import AgentState


class AgentConfig(BaseModel):
    """Configuration model for agents."""

    name: str
    enabled: bool = True
    capabilities: list[str] = Field(default_factory=list)
    model: str = "openrouter/horizon-beta"
    timeout: int = 180
    retry_attempts: int = 2
    tools: list[str] = Field(default_factory=list)
    max_concurrent_tasks: int = 1

    class Config:
        """Pydantic configuration."""

        extra = "allow"  # Allow additional fields for agent-specific config


@runtime_checkable
class AgentProtocol(Protocol):
    """Standard protocol that all agents must implement.

    This protocol ensures consistent behavior across all agents and enables
    dynamic agent discovery and coordination.
    """

    name: str
    capabilities: list[str]
    config: AgentConfig

    async def execute_task(self, state: AgentState) -> AgentState:
        """Execute assigned task with given state.

        Args:
            state: Current agent state containing task data and context

        Returns:
            Updated agent state with results and any modifications

        Raises:
            AgentExecutionError: If task execution fails

        """
        ...

    async def validate_task(self, task_data: dict[str, Any]) -> bool:
        """Validate if agent can handle the task.

        Args:
            task_data: Task information to validate

        Returns:
            True if agent can handle the task, False otherwise

        """
        ...

    def get_config(self) -> AgentConfig:
        """Get agent configuration.

        Returns:
            Current agent configuration

        """
        ...

    def get_health_status(self) -> dict[str, Any]:
        """Return agent health and readiness status.

        Returns:
            Dictionary containing health metrics and status information

        """
        ...

    async def cleanup(self) -> None:
        """Cleanup resources and perform shutdown tasks.

        Called when agent is being shut down or removed from registry.
        """
        ...


class BaseAgent(ABC):
    """Abstract base class for agent implementations.

    Provides common functionality and structure for all agents.
    """

    def __init__(self, config: AgentConfig):
        """Initialize agent with configuration."""
        self.config = config
        self.name = config.name
        self.capabilities = config.capabilities
        self._is_healthy = True
        self._current_tasks = 0

    @abstractmethod
    async def execute_task(self, state: AgentState) -> AgentState:
        """Execute assigned task with given state."""
        pass

    async def validate_task(self, task_data: dict[str, Any]) -> bool:
        """Validate task data for agent execution.

        Checks basic requirements like task type and required fields.
        Can be overridden by specific agents for custom validation.
        """
        if not task_data:
            return False

        # Check if agent is at capacity
        if self._current_tasks >= self.config.max_concurrent_tasks:
            return False

        # Check if agent is healthy
        return self._is_healthy

    def get_config(self) -> AgentConfig:
        """Get agent configuration."""
        return self.config

    def get_health_status(self) -> dict[str, Any]:
        """Return agent health and readiness status."""
        return {
            "name": self.name,
            "healthy": self._is_healthy,
            "current_tasks": self._current_tasks,
            "max_concurrent_tasks": self.config.max_concurrent_tasks,
            "capabilities": self.capabilities,
            "enabled": self.config.enabled,
            "last_heartbeat": None,  # Could be implemented with actual heartbeat
        }

    async def cleanup(self) -> None:
        """Clean up agent resources and reset state."""
        self._current_tasks = 0
        self._is_healthy = False

    def _increment_task_count(self) -> None:
        """Increment current task counter."""
        self._current_tasks += 1

    def _decrement_task_count(self) -> None:
        """Decrement current task counter."""
        self._current_tasks = max(0, self._current_tasks - 1)


class AgentExecutionError(Exception):
    """Exception raised when agent task execution fails."""

    def __init__(
        self,
        agent_name: str,
        task_id: int,
        message: str,
        cause: Exception | None = None,
    ):
        """Initialize with agent context."""
        self.agent_name = agent_name
        self.task_id = task_id
        self.cause = cause
        super().__init__(f"Agent {agent_name} failed task {task_id}: {message}")
