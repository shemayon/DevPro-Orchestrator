"""Unified service layer bridging business logic and persistence.

Provides high-level business operations that coordinate between
multiple repositories and handle complex business rules.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlmodel import Session

from ..database import get_sync_session
from ..repositories import TaskExecutionRepository, TaskRepository
from ..schemas.unified_models import (
    AgentReport,
    AgentType,
    TaskCore,
    TaskDelegation,
    TaskStatus,
)


class TaskService:
    """Unified service layer bridging business logic and persistence.

    Coordinates between repositories, handles complex business operations,
    and provides high-level task management functionality.
    """

    def __init__(
        self,
        session: Session | None = None,
    ):
        """Initialize task service with database session.

        Args:
            session: SQLModel session. If None, creates default sync session.

        """
        if session is None:
            session = get_sync_session()

        self.session = session
        self.task_repo = TaskRepository(session)
        self.execution_repo = TaskExecutionRepository(session)

    def create_task_from_delegation(
        self, delegation: TaskDelegation, title: str, description: str = "", **kwargs
    ) -> TaskCore:
        """Create task from supervisor delegation.

        Converts a TaskDelegation (from supervisor) into a TaskCore business model,
        handling all the business logic for task creation.
        """
        task_core = TaskCore(
            title=title,
            description=description,
            priority=delegation.priority,
            time_estimate_hours=delegation.estimated_duration_minutes / 60.0,
            success_criteria="; ".join(delegation.success_criteria)
            if delegation.success_criteria
            else "",
            **kwargs,
        )

        # Create task with dependencies in repository
        task_entity = self.task_repo.create_task_with_dependencies(
            task_core=task_core, dependency_task_ids=delegation.dependencies or []
        )

        self.session.commit()
        return task_entity.to_core_model()

    def execute_task_with_agent(
        self, task_id: int, agent_type: AgentType, agent_function: Callable[[int], Any]
    ) -> AgentReport:
        """Execute task with agent and track execution.

        Provides complete execution lifecycle management:
        1. Start execution tracking
        2. Update task status
        3. Execute agent function
        4. Process results
        5. Update final status
        6. Log completion
        """
        # Start execution tracking
        execution_log = self.execution_repo.log_execution_start(task_id, agent_type)

        try:
            # Update task status to in-progress
            self.task_repo.update_status_with_progress(
                task_id=task_id,
                status=TaskStatus.IN_PROGRESS,
                progress_percentage=10,
                notes=f"Started execution with {agent_type.value} agent",
            )

            # Execute agent function
            result = agent_function(task_id)

            # Process agent result into AgentReport
            if isinstance(result, dict):
                # Ensure required fields are present
                result.setdefault("agent_name", f"{agent_type.value}_agent")
                result.setdefault("agent_type", agent_type)
                result.setdefault("task_id", task_id)
                result.setdefault("start_time", execution_log.start_time)
                result.setdefault("end_time", datetime.now())
                report = AgentReport(**result)
            elif isinstance(result, AgentReport):
                report = result
            else:
                # Create a basic successful report
                report = AgentReport(
                    agent_name=f"{agent_type.value}_agent",
                    agent_type=agent_type,
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    start_time=execution_log.start_time,
                    end_time=datetime.now(),
                    outputs={"result": str(result)},
                )

            # Update task status based on report
            final_status = report.status
            progress = 100 if final_status == TaskStatus.COMPLETED else 75

            self.task_repo.update_status_with_progress(
                task_id=task_id,
                status=final_status,
                progress_percentage=progress,
                notes=f"Execution completed by {agent_type.value} agent",
            )

            # Log execution completion
            self.execution_repo.log_execution_complete(
                execution_id=execution_log.execution_id,
                status=final_status,
                outputs=report.outputs,
                error_details=report.error_details,
                confidence_score=report.confidence_score,
            )

            self.session.commit()
            return report

        except Exception as e:
            # Log execution failure
            self.execution_repo.log_execution_complete(
                execution_id=execution_log.execution_id,
                status=TaskStatus.FAILED,
                error_details=str(e),
            )

            self.task_repo.update_status_with_progress(
                task_id=task_id,
                status=TaskStatus.FAILED,
                progress_percentage=0,
                notes=f"Execution failed: {e!s}",
            )

            self.session.commit()
            raise

    def get_next_actionable_tasks(self, limit: int = 5) -> list[TaskCore]:
        """Get next tasks ready for execution.

        Returns tasks that are actionable (ready to start or in progress)
        and have no blocking dependencies.
        """
        # Get ready tasks (no blocking dependencies)
        ready_tasks = self.task_repo.get_ready_tasks()

        # Convert to business models and limit
        return [task.to_core_model() for task in ready_tasks[:limit]]

    def get_task_dashboard_data(self) -> dict[str, Any]:
        """Get comprehensive dashboard data.

        Aggregates statistics from multiple repositories to provide
        a complete view of system status.
        """
        # Get basic task statistics
        task_stats = self.task_repo.get_task_statistics()

        # Add execution statistics for each agent type
        agent_stats = {}
        for agent_type in AgentType:
            stats = self.execution_repo.get_agent_performance_stats(agent_type)
            agent_stats[agent_type.value] = stats

        # Get recent executions
        recent_executions = self.execution_repo.get_recent_executions(limit=5)
        recent_execution_data = [
            {
                "execution_id": str(log.execution_id),
                "task_id": log.task_id,
                "agent_type": log.agent_type.value,
                "status": log.status.value,
                "start_time": log.start_time.isoformat(),
                "confidence_score": log.confidence_score,
            }
            for log in recent_executions
        ]

        return {
            **task_stats,
            "agent_performance": agent_stats,
            "recent_executions": recent_execution_data,
        }

    def analyze_critical_path(self) -> list[TaskCore]:
        """Analyze critical path for task dependencies.

        Identifies tasks that are on the critical path (have the most
        dependencies or are blocking the most other tasks).
        """
        critical_tasks = self.task_repo.get_critical_path_tasks()
        return [task.to_core_model() for task in critical_tasks]

    def get_task_details(self, task_id: int) -> dict[str, Any] | None:
        """Get comprehensive task details including dependencies and history.

        Returns a complete view of a task including its dependencies,
        progress history, and execution logs.
        """
        task = self.task_repo.get_by_id(task_id)
        if not task:
            return None

        # Get dependencies
        dependencies = self.task_repo.get_dependencies(task_id)

        # Get execution history
        execution_history = self.execution_repo.get_execution_history(task_id)

        return {
            "task": task.to_core_model().model_dump(),
            "dependencies": [
                {
                    "id": dep.id,
                    "depends_on_task_id": dep.depends_on_task_id,
                    "dependency_type": dep.dependency_type.value,
                    "depends_on_task": dep.depends_on_task.to_core_model().model_dump()
                    if dep.depends_on_task
                    else None,
                }
                for dep in dependencies
            ],
            "execution_history": [
                log.to_agent_report().model_dump() for log in execution_history
            ],
        }

    def search_tasks(self, search_term: str) -> list[TaskCore]:
        """Search tasks by title or description."""
        tasks = self.task_repo.search_tasks(search_term)
        return [task.to_core_model() for task in tasks]

    def update_task_status(
        self,
        task_id: int,
        status: TaskStatus,
        notes: str = "",
        updated_by: str = "system",
    ) -> TaskCore | None:
        """Update task status with progress tracking."""
        from ..schemas.unified_models import get_status_progress_percentage

        progress_percentage = get_status_progress_percentage(status)
        task = self.task_repo.update_status_with_progress(
            task_id=task_id,
            status=status,
            progress_percentage=progress_percentage,
            notes=notes,
            updated_by=updated_by,
        )

        if task:
            self.session.commit()
            return task.to_core_model()
        return None

    def create_task(
        self, task_core: TaskCore, dependency_task_ids: list[int] | None = None
    ) -> TaskCore:
        """Create a new task with optional dependencies."""
        task = self.task_repo.create_task_with_dependencies(
            task_core=task_core, dependency_task_ids=dependency_task_ids or []
        )
        self.session.commit()
        return task.to_core_model()

    def add_task_dependency(
        self, task_id: int, depends_on_task_id: int, dependency_type: str = "blocks"
    ) -> bool:
        """Add a dependency between tasks."""
        try:
            self.task_repo.add_dependency(task_id, depends_on_task_id, dependency_type)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False

    def get_tasks_by_status(self, status: TaskStatus) -> list[TaskCore]:
        """Get all tasks with a specific status."""
        tasks = self.task_repo.get_by_status(status, include_relations=False)
        return [task.to_core_model() for task in tasks]

    def get_tasks_by_phase(self, phase: int) -> list[TaskCore]:
        """Get all tasks for a specific phase."""
        tasks = self.task_repo.get_by_phase(phase)
        return [task.to_core_model() for task in tasks]

    def close(self):
        """Close the database session."""
        if self.session:
            self.session.close()
