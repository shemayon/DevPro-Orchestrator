"""Task repository implementations with business logic.

Provides specialized repository classes for task management operations,
integrating seamlessly with the unified schema architecture.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import select

from ..schemas.database import (
    Task,
    TaskDependency,
    TaskExecutionLog,
    TaskProgress,
)
from ..schemas.unified_models import (
    AgentReport,
    AgentType,
    ComponentArea,
    TaskCore,
    TaskStatus,
)
from .base import BaseRepository


class TaskRepository(BaseRepository[Task, TaskCore]):
    """Repository for task operations with business logic.

    Provides comprehensive task management operations including
    dependency handling, status management, and analytics.
    """

    def get_entity_class(self) -> type[Task]:
        """Return the database entity class for this repository."""
        return Task

    def get_business_class(self) -> type[TaskCore]:
        """Return the business model class for this repository."""
        return TaskCore

    def get_by_status(
        self, status: TaskStatus, include_relations: bool = True
    ) -> list[Task]:
        """Get tasks by status with optional relationship loading."""
        statement = select(Task).where(Task.status == status)

        if include_relations:
            statement = statement.options(
                selectinload(Task.dependencies),
                selectinload(Task.progress_records),
                selectinload(Task.execution_logs),
            )

        return list(self.session.exec(statement).all())

    def get_by_component_area(self, component_area: ComponentArea) -> list[Task]:
        """Get tasks by component area."""
        statement = (
            select(Task)
            .where(Task.component_area == component_area)
            .order_by(Task.priority.desc(), Task.created_at)
        )
        return list(self.session.exec(statement).all())

    def get_actionable_tasks(self, limit: int | None = None) -> list[Task]:
        """Get tasks ready for execution."""
        statement = (
            select(Task)
            .where(
                or_(
                    Task.status == TaskStatus.NOT_STARTED,
                    Task.status == TaskStatus.IN_PROGRESS,
                )
            )
            .order_by(Task.priority.desc(), Task.created_at)
        )

        if limit:
            statement = statement.limit(limit)

        return list(self.session.exec(statement).all())

    def get_by_phase(self, phase: int) -> list[Task]:
        """Get tasks by phase."""
        statement = (
            select(Task)
            .where(Task.phase == phase)
            .order_by(Task.priority.desc(), Task.created_at)
        )
        return list(self.session.exec(statement).all())

    def get_critical_path_tasks(self, limit: int = 10) -> list[Task]:
        """Get tasks with most dependencies (critical path)."""
        statement = (
            select(Task)
            .join(TaskDependency, Task.id == TaskDependency.task_id)
            .group_by(Task.id)
            .order_by(func.count(TaskDependency.id).desc())
            .limit(limit)
            .options(selectinload(Task.dependencies))
        )

        return list(self.session.exec(statement).all())

    def get_ready_tasks(self) -> list[Task]:
        """Get tasks that are ready to start (no blocking dependencies)."""
        # Get all not started tasks
        not_started_tasks = self.get_by_status(
            TaskStatus.NOT_STARTED, include_relations=False
        )

        ready_tasks = []
        for task in not_started_tasks:
            # Check if task has any incomplete blocking dependencies
            blocking_deps = self.session.exec(
                select(TaskDependency)
                .join(Task, TaskDependency.depends_on_task_id == Task.id)
                .where(
                    and_(
                        TaskDependency.task_id == task.id,
                        Task.status != TaskStatus.COMPLETED,
                    )
                )
            ).all()

            if not blocking_deps:
                ready_tasks.append(task)

        return ready_tasks

    def update_status_with_progress(
        self,
        task_id: int,
        status: TaskStatus,
        progress_percentage: int | None = None,
        notes: str = "",
        updated_by: str = "system",
    ) -> Task | None:
        """Update task status and create progress record."""
        task = self.get_by_id(task_id)
        if not task:
            return None

        # Update task status
        task.status = status
        task.updated_at = datetime.now()
        self.session.add(task)

        # Create progress record
        if progress_percentage is not None:
            progress = TaskProgress(
                task_id=task_id,
                progress_percentage=progress_percentage,
                notes=notes or f"Status updated to {status.value}",
                updated_by=updated_by,
            )
            self.session.add(progress)

        self.session.flush()
        return task

    def create_task_with_dependencies(
        self, task_core: TaskCore, dependency_task_ids: list[int] | None = None
    ) -> Task:
        """Create task with dependencies in single transaction."""
        # Create task
        task = self.create(task_core)

        # Add dependencies
        if dependency_task_ids:
            for dep_id in dependency_task_ids:
                dependency = TaskDependency(
                    task_id=task.id, depends_on_task_id=dep_id, dependency_type="blocks"
                )
                self.session.add(dependency)

        self.session.flush()
        return task

    def search_tasks(self, search_term: str) -> list[Task]:
        """Search tasks by title or description."""
        statement = (
            select(Task)
            .where(
                or_(
                    Task.title.contains(search_term),
                    Task.description.contains(search_term),
                )
            )
            .order_by(Task.priority.desc(), Task.created_at)
        )
        return list(self.session.exec(statement).all())

    def get_task_statistics(self) -> dict[str, any]:
        """Get comprehensive task statistics."""
        # Basic counts
        total_tasks = self.count()

        status_counts = {}
        for status in TaskStatus:
            count = self.session.exec(
                select(func.count(Task.id)).where(Task.status == status)
            ).one()
            status_counts[status.value] = count

        # Phase breakdown
        phase_stats = self.session.exec(
            select(Task.phase, func.count(Task.id).label("count"))
            .group_by(Task.phase)
            .order_by(Task.phase)
        ).all()

        # Component breakdown
        component_stats = self.session.exec(
            select(Task.component_area, func.count(Task.id).label("count"))
            .group_by(Task.component_area)
            .order_by(func.count(Task.id).desc())
        ).all()

        # Time estimates
        total_hours = (
            self.session.exec(select(func.sum(Task.time_estimate_hours))).one() or 0
        )
        completed_hours = (
            self.session.exec(
                select(func.sum(Task.time_estimate_hours)).where(
                    Task.status == TaskStatus.COMPLETED
                )
            ).one()
            or 0
        )

        return {
            "total_tasks": total_tasks,
            "status_breakdown": status_counts,
            "completion_percentage": round(
                status_counts.get("completed", 0) / total_tasks * 100, 1
            )
            if total_tasks > 0
            else 0,
            "phase_breakdown": [
                {"phase": phase, "count": count} for phase, count in phase_stats
            ],
            "component_breakdown": [
                {"area": area.value, "count": count} for area, count in component_stats
            ],
            "total_estimated_hours": total_hours,
            "completed_hours": completed_hours,
            "progress_percentage": round(completed_hours / total_hours * 100, 1)
            if total_hours > 0
            else 0,
        }

    def get_dependencies(self, task_id: int) -> list[TaskDependency]:
        """Get all dependencies for a task."""
        statement = (
            select(TaskDependency)
            .where(TaskDependency.task_id == task_id)
            .options(selectinload(TaskDependency.depends_on_task))
        )
        return list(self.session.exec(statement).all())

    def add_dependency(
        self, task_id: int, depends_on_task_id: int, dependency_type: str = "blocks"
    ) -> TaskDependency:
        """Add a dependency between tasks."""
        dependency = TaskDependency(
            task_id=task_id,
            depends_on_task_id=depends_on_task_id,
            dependency_type=dependency_type,
        )
        self.session.add(dependency)
        self.session.flush()
        return dependency


class TaskExecutionRepository(BaseRepository[TaskExecutionLog, AgentReport]):
    """Repository for task execution tracking.

    Manages execution logs and provides analytics for task execution patterns.
    """

    def get_entity_class(self) -> type[TaskExecutionLog]:
        """Return the database entity class for this repository."""
        return TaskExecutionLog

    def get_business_class(self) -> type[AgentReport]:
        """Return the business model class for this repository."""
        return AgentReport

    def log_execution_start(
        self, task_id: int, agent_type: AgentType, execution_id: UUID | None = None
    ) -> TaskExecutionLog:
        """Log the start of task execution."""
        log = TaskExecutionLog(
            task_id=task_id,
            execution_id=execution_id or uuid4(),
            agent_type=agent_type,
            status=TaskStatus.IN_PROGRESS,
            start_time=datetime.now(),
        )
        self.session.add(log)
        self.session.flush()
        return log

    def log_execution_complete(
        self,
        execution_id: UUID,
        status: TaskStatus,
        outputs: dict[str, any] | None = None,
        error_details: str | None = None,
        confidence_score: float = 0.8,
    ) -> TaskExecutionLog | None:
        """Log the completion of task execution."""
        statement = select(TaskExecutionLog).where(
            TaskExecutionLog.execution_id == execution_id
        )
        log = self.session.exec(statement).first()

        if log:
            log.status = status
            log.end_time = datetime.now()
            log.outputs = outputs or {}
            log.error_details = error_details
            log.confidence_score = confidence_score
            self.session.add(log)
            self.session.flush()

        return log

    def get_execution_history(self, task_id: int) -> list[TaskExecutionLog]:
        """Get execution history for a task."""
        statement = (
            select(TaskExecutionLog)
            .where(TaskExecutionLog.task_id == task_id)
            .order_by(TaskExecutionLog.start_time.desc())
        )
        return list(self.session.exec(statement).all())

    def get_agent_performance_stats(self, agent_type: AgentType) -> dict[str, any]:
        """Get performance statistics for a specific agent type."""
        # Total executions
        total_executions = self.session.exec(
            select(func.count(TaskExecutionLog.id)).where(
                TaskExecutionLog.agent_type == agent_type
            )
        ).one()

        # Success rate
        successful_executions = self.session.exec(
            select(func.count(TaskExecutionLog.id)).where(
                and_(
                    TaskExecutionLog.agent_type == agent_type,
                    TaskExecutionLog.status == TaskStatus.COMPLETED,
                )
            )
        ).one()

        # Average confidence score
        avg_confidence = (
            self.session.exec(
                select(func.avg(TaskExecutionLog.confidence_score)).where(
                    TaskExecutionLog.agent_type == agent_type
                )
            ).one()
            or 0.0
        )

        return {
            "agent_type": agent_type.value,
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": round(successful_executions / total_executions * 100, 1)
            if total_executions > 0
            else 0,
            "average_confidence_score": round(avg_confidence, 2),
        }

    def get_recent_executions(self, limit: int = 10) -> list[TaskExecutionLog]:
        """Get recent execution logs."""
        statement = (
            select(TaskExecutionLog)
            .order_by(TaskExecutionLog.start_time.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement).all())
