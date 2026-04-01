"""Task calculation utilities for computed fields and business logic.

This module provides utility functions for calculating task metrics
that were previously embedded in the Task model as computed fields.
"""

from functools import cached_property

from ..schemas.unified_models import TaskComplexity, TaskCore, TaskPriority


class TaskCalculations:
    """Utility class for task-related calculations and computed fields."""

    @staticmethod
    def complexity_score(task: TaskCore) -> int:
        """Numeric representation of complexity for calculations."""
        complexity_map = {
            TaskComplexity.LOW: 1,
            TaskComplexity.MEDIUM: 2,
            TaskComplexity.HIGH: 3,
            TaskComplexity.VERY_HIGH: 4,
        }
        return complexity_map[task.complexity]

    @staticmethod
    def priority_score(task: TaskCore) -> int:
        """Numeric representation of priority for calculations."""
        priority_map = {
            TaskPriority.LOW: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.HIGH: 3,
            TaskPriority.CRITICAL: 4,
        }
        return priority_map[task.priority]

    @staticmethod
    def effort_index(task: TaskCore) -> float:
        """Calculate effort index based on complexity, priority, and time estimate."""
        complexity = TaskCalculations.complexity_score(task)
        priority = TaskCalculations.priority_score(task)

        base_score = complexity * priority
        time_factor = min(task.time_estimate_hours / 8.0, 3.0)  # Cap at 3x
        phase_factor = 1.0 + (task.phase * 0.1)  # Later phases slightly more complex
        return round(base_score * time_factor * phase_factor, 2)

    @staticmethod
    def risk_factor(task: TaskCore) -> float:
        """Calculate risk factor for task execution."""
        if task.time_estimate_hours == 0:
            return 1.0

        complexity = TaskCalculations.complexity_score(task)
        complexity_time_ratio = complexity / max(task.time_estimate_hours, 0.1)
        priority_adjustment = 1.2 if task.priority == TaskPriority.CRITICAL else 1.0
        return round(complexity_time_ratio * priority_adjustment, 2)


class EnhancedTaskCore(TaskCore):
    """TaskCore with computed fields via utility methods.

    Provides the same computed fields as the old Task class
    but delegates calculations to TaskCalculations utility.
    """

    @cached_property
    def complexity_score(self) -> int:
        """Numeric representation of complexity for calculations."""
        return TaskCalculations.complexity_score(self)

    @cached_property
    def priority_score(self) -> int:
        """Numeric representation of priority for calculations."""
        return TaskCalculations.priority_score(self)

    @cached_property
    def effort_index(self) -> float:
        """Calculate effort index based on complexity, priority, and time estimate."""
        return TaskCalculations.effort_index(self)

    @cached_property
    def risk_factor(self) -> float:
        """Calculate risk factor for task execution."""
        return TaskCalculations.risk_factor(self)
