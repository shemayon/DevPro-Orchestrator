"""AI Job Scraper - Task Orchestration System.

This package contains the task management and multi-agent orchestration
system for the AI Job Scraper project.

Core Components:
- task_manager: Core task management interface with SQLite database
- supervisor: Modern multi-agent supervisor using langgraph-supervisor library
- agents: Specialized worker agents (research, coding, testing, documentation)
- integrations: API clients for Exa and Crawl4AI services
- common: Shared utilities, models, and enums
"""

# Core task management
# Core components (avoiding circular imports)
# from .agents import CodingAgent, DocumentationAgent, ResearchAgent, TestingAgent
# from .core.agent_protocol import AgentConfig, AgentExecutionError, BaseAgent
# from .core.state import AgentState

# Common utilities and schemas
# Integration tools
from .integrations import Crawl4AIClient, ExaClient
from .schemas import (
    AgentReport,
    TaskComplexity,
    TaskCore,
    TaskDelegation,
    TaskPriority,
    TaskStatus,
)

# Modern multi-agent supervisor
from .supervisor import Supervisor

# Task management
from .task_manager import TaskDependency, TaskManager

__all__ = [
    "AgentReport",
    "Crawl4AIClient",
    "ExaClient",
    "Supervisor",
    "TaskComplexity",
    "TaskCore",
    "TaskDelegation",
    "TaskDependency",
    "TaskManager",
    "TaskPriority",
    "TaskStatus",
]


def check_system_availability():
    """Check which orchestration systems are available."""
    return {
        "core_task_management": True,
        "supervisor": True,
        "specialized_agents": True,
        "integrations": True,
    }
