"""Service layer for unified business logic and persistence.

This module provides the service layer that coordinates between
business models, repositories, and external integrations.
"""

from .task_service import TaskService

__all__ = ["TaskService"]
