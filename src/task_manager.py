#!/usr/bin/env python3
"""Task Manager interface for AI Job Scraper.

This module provides a Python interface for managing tasks, dependencies,
and progress tracking backed by a SQLite database. It integrates with
Pydantic v2.11.7 models for strict validation and typed access, including:

- Enhanced field validation with custom validators.
- Computed fields for derived properties.
- ConfigDict for centralized configuration.
- Context-aware serialization methods.
- Performance optimizations with basic in-memory caching.

Typical usage example:
    tm = TaskManager()
    new_task = tm.create_task({...})
    task = tm.get_task_by_id(new_task.id)
    analytics = tm.get_task_analytics()
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from .schemas.unified_models import (
    ComponentArea,
    DependencyType,
    TaskComplexity,
    TaskCore,
    TaskPriority,
    TaskStatus,
    get_status_progress_percentage,
)

# Enhanced Pydantic v2 Configuration Classes
BaseOrchestrationConfig = ConfigDict(
    validate_assignment=True,
    use_enum_values=True,
    str_strip_whitespace=True,
    validate_default=True,
    frozen=False,
    extra="forbid",
)

StrictOrchestrationConfig = ConfigDict(
    validate_assignment=True,
    use_enum_values=True,
    str_strip_whitespace=True,
    validate_default=True,
    frozen=True,
    extra="forbid",
    strict=True,
)


PerformanceOrchestrationConfig = ConfigDict(
    validate_assignment=False,
    use_enum_values=True,
    str_strip_whitespace=True,
    validate_default=True,
    frozen=False,
    extra="forbid",
    arbitrary_types_allowed=True,
)


# All enums now imported from unified schemas/unified_models.py


# Custom field types removed - using unified TaskCore schema


class TaskDependency(BaseModel):
    """Task-to-task dependency with essential business logic.

    Attributes:
        id: Unique identifier of the dependency (database-assigned).
        task_id: ID of the task that has the dependency.
        depends_on_task_id: ID of the task this task depends on.
        dependency_type: Relationship type (e.g., blocks, requires).
        created_at: Creation timestamp (defaults to now).

    Raises:
        ValueError: When validation fails (non-positive IDs or self-dependency).

    """

    model_config = BaseOrchestrationConfig

    id: int | None = None
    task_id: int = Field(ge=1, description="ID of the dependent task")
    depends_on_task_id: int = Field(ge=1, description="ID of the task this depends on")
    dependency_type: DependencyType = DependencyType.BLOCKS
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("task_id", "depends_on_task_id")
    @classmethod
    def validate_task_ids(cls, v: int) -> int:
        """Validate task IDs are positive integers.

        Args:
            v: Candidate task identifier.

        Returns:
            The same integer when validation passes.

        Raises:
            ValueError: If the value is not a positive integer.

        """
        if v <= 0:
            raise ValueError("Task IDs must be positive integers")
        return v

    @model_validator(mode="after")
    def validate_no_self_dependency(self):
        """Ensure task cannot depend on itself.

        Returns:
            Self instance after validation.

        Raises:
            ValueError: If `task_id == depends_on_task_id`.

        """
        if self.task_id == self.depends_on_task_id:
            raise ValueError("Task cannot depend on itself")
        return self

    @computed_field
    @property
    def is_blocking(self) -> bool:
        """Whether this dependency is a blocking relationship.

        Returns:
            True if the dependency type is ``DependencyType.BLOCKS``, else False.

        """
        return self.dependency_type == DependencyType.BLOCKS

    @computed_field
    @property
    def dependency_strength(self) -> float:
        """Calculate dependency strength for prioritization.

        Returns:
            A numeric weight representing the strength of the dependency.

        """
        strength_map = {
            DependencyType.BLOCKS: 1.0,
            DependencyType.REQUIRES: 0.8,
            DependencyType.ENABLES: 0.6,
            DependencyType.ENHANCES: 0.3,
        }
        return strength_map.get(self.dependency_type, 0.5)


class TaskManager:
    """Task management interface with Pydantic v2 model integration.

    This class provides CRUD-like operations for tasks, dependencies, and
    analytics queries over a SQLite database. It validates inputs and outputs
    using Pydantic models from the unified schema package.

    Features:
        - Pydantic model validation for all task operations.
        - Enhanced error handling and data consistency.
        - Advanced querying with computed field support.
        - Performance optimizations with a simple TTL cache.

    Note:
        The manager expects an existing SQLite schema with tables:
        ``tasks``, ``task_dependencies``, ``task_progress``, and
        ``task_comments``. See get_project_stats for expected columns.

    """

    def __init__(self, db_path: str | None = None):
        """Initialize the task manager.

        Args:
            db_path: Optional path to the SQLite database file. When omitted,
                a default path relative to this module is used.

        Raises:
            FileNotFoundError: If the database file is not found at the resolved
                location.

        """
        if db_path is None:
            # Default to database relative to this module's location
            module_dir = Path(__file__).parent
            db_path = str(module_dir / "database" / "implementation_tracker.db")
        self.db_path = db_path
        self._ensure_database_exists()

        # Cache for frequently accessed tasks
        self._task_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL

    def _ensure_database_exists(self):
        """Ensure the database exists.

        Verifies the configured SQLite database path exists. This class does not
        create the schema; the database must be provisioned separately.

        Raises:
            FileNotFoundError: If the database file is missing.

        """
        if not Path(self.db_path).exists():
            print(f"Database not found at {self.db_path}")
            print("Run create_task_db.py first to create the database")
            raise FileNotFoundError(f"Database not found: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Create a SQLite connection.

        Returns:
            A SQLite connection with ``row_factory`` set to ``sqlite3.Row`` for
            dict-like access to columns.

        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_task(self, row: sqlite3.Row) -> TaskCore:
        """Convert a database row to a validated Task model.

        Args:
            row: SQLite row representing a task.

        Returns:
            A validated ``TaskCore`` instance constructed from the row.

        Raises:
            ValueError: If conversion or validation fails.

        """
        try:
            task_data = {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"] or "",
                # Coerce strings from SQLite to enum instances for Pydantic strict mode
                "component_area": ComponentArea(row["component_area"]),
                "phase": row["phase"],
                "priority": TaskPriority(row["priority"]),
                "complexity": TaskComplexity(row["complexity"]),
                "status": TaskStatus(row["status"]),
                "source_document": row["source_document"] or "",
                "success_criteria": row["success_criteria"] or "",
                "time_estimate_hours": float(row["time_estimate_hours"]),
                "parent_task_id": row["parent_task_id"],
                "created_at": datetime.fromisoformat(row["created_at"])
                if row["created_at"]
                else None,
                "updated_at": datetime.fromisoformat(row["updated_at"])
                if row["updated_at"]
                else None,
            }
            return TaskCore(**task_data)
        except Exception as e:
            raise ValueError(f"Failed to create Task from database row: {e}") from e

    def _row_to_task_dependency(self, row: sqlite3.Row) -> TaskDependency:
        """Convert a database row to a validated TaskDependency model.

        Args:
            row: SQLite row representing a dependency.

        Returns:
            A validated ``TaskDependency`` instance.

        Raises:
            ValueError: If conversion or validation fails.

        """
        try:
            dependency_data = {
                "id": row["id"],
                "task_id": row["task_id"],
                "depends_on_task_id": row["depends_on_task_id"],
                "dependency_type": row["dependency_type"],
                "created_at": datetime.fromisoformat(row["created_at"])
                if row["created_at"]
                else datetime.now(),
            }
            return TaskDependency(**dependency_data)
        except Exception as e:
            raise ValueError(
                f"Failed to create TaskDependency from database row: {e}"
            ) from e

    def create_task(self, task_data: dict | TaskCore) -> TaskCore:
        """Create a new task using Pydantic validation.

        Args:
            task_data: Either a dictionary of task data or a Task model instance

        Returns:
            Task: Validated Task model with assigned ID

        Raises:
            ValueError: If task data validation fails

        """
        # Convert to Task model if needed
        task = TaskCore(**task_data) if isinstance(task_data, dict) else task_data

        # Validate task data before database insertion
        validated_data = task.model_dump()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (
                    title, description, component_area, phase, priority,
                    complexity, status, source_document, success_criteria,
                    time_estimate_hours, parent_task_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validated_data["title"],
                    validated_data["description"],
                    validated_data["component_area"],
                    validated_data["phase"],
                    validated_data["priority"],
                    validated_data["complexity"],
                    validated_data["status"],
                    validated_data["source_document"],
                    validated_data["success_criteria"],
                    validated_data["time_estimate_hours"],
                    validated_data["parent_task_id"],
                    validated_data["created_at"].isoformat()
                    if validated_data["created_at"]
                    else None,
                    validated_data["updated_at"].isoformat()
                    if validated_data["updated_at"]
                    else None,
                ),
            )

            task_id = cursor.lastrowid

            # Add initial progress entry
            import datetime as _dt
            cursor.execute(
                """
                INSERT INTO task_progress (task_id, progress_percentage, notes, updated_by, created_at)
                VALUES (?, 0, 'Task created', 'api', ?)
                """,
                (task_id, _dt.datetime.now().isoformat()),
            )

            conn.commit()

            # Return updated task with ID
            task.id = task_id
            return task

    def get_task_by_id(self, task_id: int) -> TaskCore | None:
        """Get a single task by ID with Pydantic validation.

        Args:
            task_id: Task ID to retrieve

        Returns:
            Task model instance or None if not found

        Raises:
            ValueError: If task ID is not positive

        """
        # Check cache first
        cache_key = f"task_{task_id}"
        if cache_key in self._task_cache:
            return self._task_cache[cache_key]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()

            if not row:
                return None

            task = self._row_to_task(row)

            # Cache the result
            self._task_cache[cache_key] = task

            return task

    def get_task(self, task_id: int) -> TaskCore | None:
        """Alias for get_task_by_id for backward compatibility."""
        return self.get_task_by_id(task_id)

    def get_tasks_with_computed_fields(
        self, filters: dict | None = None
    ) -> list[TaskCore]:
        """Get tasks with all computed fields populated.

        Args:
            filters: Optional filters for task selection

        Returns:
            List of Task models with computed fields

        Raises:
            ValueError: If filters contain invalid keys

        """
        where_clause = ""
        params = []

        if filters:
            conditions = []
            for key, value in filters.items():
                if key in [
                    "status",
                    "priority",
                    "complexity",
                    "phase",
                    "component_area",
                ]:
                    conditions.append(f"{key} = ?")
                    params.append(value)
                elif key == "is_overdue":
                    # This would require more complex SQL, simplified for now
                    continue

            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Safe SQL construction - where_clause built from whitelisted columns only
            base_query = "SELECT * FROM tasks"
            order_clause = "ORDER BY priority DESC, created_at ASC"

            if where_clause:
                query = f"{base_query} {where_clause} {order_clause}"
            else:
                query = f"{base_query} {order_clause}"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            tasks = []
            for row in rows:
                task = self._row_to_task(row)
                tasks.append(task)

            return tasks

    def create_task_dependency(
        self, dependency_data: dict | TaskDependency
    ) -> TaskDependency:
        """Create a new task dependency with validation.

        Args:
            dependency_data: Either a dictionary or TaskDependency model instance

        Returns:
            TaskDependency: Validated model with assigned ID

        Raises:
            ValueError: If task or dependency does not exist
            ValueError: If adding dependency would create a circular dependency

        """
        # Convert to TaskDependency model if needed
        if isinstance(dependency_data, dict):
            dependency = TaskDependency(**dependency_data)
        else:
            dependency = dependency_data

        # Additional validation: check that both tasks exist
        task_exists = self.get_task_by_id(dependency.task_id)
        depends_on_exists = self.get_task_by_id(dependency.depends_on_task_id)

        if not task_exists:
            raise ValueError(f"Task {dependency.task_id} does not exist")
        if not depends_on_exists:
            raise ValueError(
                f"Dependency target task {dependency.depends_on_task_id} does not exist"
            )

        # Check for circular dependencies (simplified check)
        if self._would_create_circular_dependency(
            dependency.task_id, dependency.depends_on_task_id
        ):
            raise ValueError("This dependency would create a circular dependency")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO task_dependencies
                (task_id, depends_on_task_id, dependency_type, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    dependency.task_id,
                    dependency.depends_on_task_id,
                    dependency.dependency_type,
                    dependency.created_at.isoformat(),
                ),
            )

            dependency_id = cursor.lastrowid
            conn.commit()

            # Return updated dependency with ID
            dependency.id = dependency_id
            return dependency

    def _would_create_circular_dependency(
        self, task_id: int, depends_on_task_id: int
    ) -> bool:
        """Check if adding a dependency would create a circular dependency.

        This is a simplified check - a full implementation would use graph traversal.
        """
        # Direct circular check
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM task_dependencies
                WHERE task_id = ? AND depends_on_task_id = ?
                """,
                (depends_on_task_id, task_id),
            )
            direct_circular = cursor.fetchone()[0] > 0

            return direct_circular

    def get_task_analytics(self) -> dict[str, Any]:
        """Get advanced task analytics using computed fields.

        Returns:
            Dictionary with comprehensive task analytics

        Raises:
            ValueError: If there are no tasks to calculate analytics

        """
        tasks = self.get_tasks_with_computed_fields()

        if not tasks:
            return {"total_tasks": 0, "analytics": {}, "computed_metrics": {}}

        analytics = {
            "total_tasks": len(tasks),
            "status_distribution": {},
            "priority_distribution": {},
            "complexity_distribution": {},
            "phase_distribution": {},
            "computed_metrics": {
                "average_effort_index": 0.0,
                "average_risk_factor": 0.0,
                "high_risk_tasks": 0,
                "overdue_tasks": 0,
                "total_estimated_hours": 0.0,
                "completion_rate": 0.0,
            },
        }

        # Calculate distributions and metrics
        total_effort = 0.0
        total_risk = 0.0
        high_risk_count = 0
        overdue_count = 0
        completed_count = 0

        for task in tasks:
            # Status distribution
            status = task.status.value
            analytics["status_distribution"][status] = (
                analytics["status_distribution"].get(status, 0) + 1
            )

            # Priority distribution
            priority = task.priority.value
            analytics["priority_distribution"][priority] = (
                analytics["priority_distribution"].get(priority, 0) + 1
            )

            # Complexity distribution
            complexity = task.complexity.value
            analytics["complexity_distribution"][complexity] = (
                analytics["complexity_distribution"].get(complexity, 0) + 1
            )

            # Phase distribution
            phase = task.phase
            analytics["phase_distribution"][f"phase_{phase}"] = (
                analytics["phase_distribution"].get(f"phase_{phase}", 0) + 1
            )

            # Computed metrics
            total_effort += task.effort_index
            total_risk += task.risk_factor

            if task.risk_factor > 2.0:  # Threshold for high risk
                high_risk_count += 1

            if task.is_overdue:
                overdue_count += 1

            if task.status == TaskStatus.COMPLETED:
                completed_count += 1

            analytics["computed_metrics"]["total_estimated_hours"] += (
                task.time_estimate_hours
            )

        # Calculate averages
        analytics["computed_metrics"]["average_effort_index"] = round(
            total_effort / len(tasks), 2
        )
        analytics["computed_metrics"]["average_risk_factor"] = round(
            total_risk / len(tasks), 2
        )
        analytics["computed_metrics"]["high_risk_tasks"] = high_risk_count
        analytics["computed_metrics"]["overdue_tasks"] = overdue_count
        analytics["computed_metrics"]["completion_rate"] = round(
            (completed_count / len(tasks)) * 100, 1
        )

        return analytics

    def add_task(
        self,
        title: str,
        description: str,
        component_area: str,
        phase: int,
        priority: str,
        complexity: str,
        source_document: str,
        **kwargs,
    ) -> int:
        """Add a new task and return its ID.

        Args:
            title: Task title
            description: Task description
            component_area: Task component area
            phase: Task phase
            priority: Task priority
            complexity: Task complexity
            source_document: Task source document
            **kwargs: Additional optional fields (success_criteria,
                time_estimate_hours, parent_task_id)

        Returns:
            Task ID

        Raises:
            ValueError: If required fields are missing

        """
        success_criteria = kwargs.get("success_criteria", "")
        time_estimate_hours = kwargs.get("time_estimate_hours", 1.0)
        parent_task_id = kwargs.get("parent_task_id")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (
                    title, description, component_area, phase, priority,
                    complexity, source_document, success_criteria,
                    time_estimate_hours, parent_task_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    title,
                    description,
                    component_area,
                    phase,
                    priority,
                    complexity,
                    source_document,
                    success_criteria,
                    time_estimate_hours,
                    parent_task_id,
                ),
            )

            task_id = cursor.lastrowid

            # Add initial progress entry
            cursor.execute(
                """
                INSERT INTO task_progress (task_id, progress_percentage, notes)
                VALUES (?, 0, 'Task created')
            """,
                (task_id,),
            )

            conn.commit()
            return task_id

    def update_task_status(self, task_id: int, status: str, notes: str = "") -> None:
        """Update task status with progress tracking.

        Args:
            task_id: Task ID
            status: New task status
            notes: Optional notes for the status change

        """
        # Use centralized status progress mapping from unified schema
        # Using get_status_progress_percentage from unified_models

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Update task status and timestamp
            cursor.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (status, task_id),
            )

            # Add progress entry using unified schema function
            task_status = TaskStatus(status) if isinstance(status, str) else status
            progress = get_status_progress_percentage(task_status)
            cursor.execute(
                """
                INSERT INTO task_progress (task_id, progress_percentage, notes, updated_by, created_at)
                VALUES (?, ?, ?, 'supervisor', CURRENT_TIMESTAMP)
            """,
                (task_id, progress, notes or f"Status changed to {status}"),
            )

            # Add comment if notes provided
            if notes:
                cursor.execute(
                    """
                    INSERT INTO task_comments (task_id, comment, comment_type)
                    VALUES (?, ?, 'note')
                """,
                    (task_id, notes),
                )

            conn.commit()

    def delete_task(self, task_id: int) -> bool:
        """Delete a task and its related records by ID.

        Args:
            task_id: Task ID to delete

        Returns:
            True if the task was deleted, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete related records first (FK cascade not always enabled)
            cursor.execute("DELETE FROM task_progress WHERE task_id = ?", (task_id,))
            cursor.execute("DELETE FROM task_comments WHERE task_id = ?", (task_id,))
            cursor.execute("DELETE FROM task_dependencies WHERE task_id = ? OR depends_on_task_id = ?", (task_id, task_id))
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            rows_deleted = cursor.rowcount
            conn.commit()
            # Invalidate cache if present
            self._task_cache.pop(f"task_{task_id}", None)
            return rows_deleted > 0


    def get_tasks_by_phase(self, phase: int) -> list[dict]:
        """Get all tasks for a specific phase."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tasks
                WHERE phase = ?
                ORDER BY priority DESC, created_at ASC
            """,
                (phase,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_tasks_by_component(self, component_area: str) -> list[dict]:
        """Get all tasks for a specific component area."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tasks
                WHERE component_area = ?
                ORDER BY phase, priority DESC, created_at ASC
            """,
                (component_area,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_tasks_by_status(self, status: str) -> list[dict]:
        """Get all tasks with a specific status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status.lower() == "all":
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    ORDER BY priority DESC, created_at ASC
                """
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    WHERE status = ?
                    ORDER BY priority DESC, created_at ASC
                """,
                    (status,),
                )

            return [dict(row) for row in cursor.fetchall()]

    def get_critical_path(self) -> list[dict]:
        """Get tasks on critical path based on dependencies."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get tasks that block other tasks or are critical priority
            cursor.execute("""
                SELECT DISTINCT t.* FROM tasks t
                LEFT JOIN task_dependencies td ON t.id = td.depends_on_task_id
                WHERE t.priority = 'Critical'
                   OR td.depends_on_task_id IS NOT NULL
                ORDER BY t.phase,
                         CASE t.priority
                             WHEN 'Critical' THEN 4
                             WHEN 'High' THEN 3
                             WHEN 'Medium' THEN 2
                             ELSE 1
                         END DESC,
                         t.created_at ASC
            """)

            return [dict(row) for row in cursor.fetchall()]

    def get_blocked_tasks(self) -> list[dict]:
        """Get tasks that are blocked by incomplete dependencies."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*, GROUP_CONCAT(dt.title) as blocking_tasks
                FROM tasks t
                INNER JOIN task_dependencies td ON t.id = td.task_id
                INNER JOIN tasks dt ON td.depends_on_task_id = dt.id
                WHERE dt.status != 'completed'
                GROUP BY t.id
                ORDER BY t.priority DESC
            """)

            return [dict(row) for row in cursor.fetchall()]

    def get_ready_tasks(self) -> list[dict]:
        """Get tasks that are ready to start (no blocking dependencies)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.* FROM tasks t
                WHERE t.status = 'not_started'
                  AND NOT EXISTS (
                      SELECT 1 FROM task_dependencies td
                      INNER JOIN tasks dt ON td.depends_on_task_id = dt.id
                      WHERE td.task_id = t.id
                        AND dt.status != 'completed'
                  )
                ORDER BY t.priority DESC, t.phase ASC
            """)

            return [dict(row) for row in cursor.fetchall()]

    def add_dependency(
        self, task_id: int, depends_on_task_id: int, dependency_type: str = "blocks"
    ) -> None:
        """Add a dependency between tasks."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO task_dependencies
                (task_id, depends_on_task_id, dependency_type)
                VALUES (?, ?, ?)
            """,
                (task_id, depends_on_task_id, dependency_type),
            )
            conn.commit()

    def get_task_dependencies(self, task_id: int) -> list[dict]:
        """Get all dependencies for a specific task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT td.*, t.title as depends_on_title, t.status as depends_on_status
                FROM task_dependencies td
                INNER JOIN tasks t ON td.depends_on_task_id = t.id
                WHERE td.task_id = ?
            """,
                (task_id,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_task_progress(self, task_id: int) -> list[dict]:
        """Get progress history for a task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM task_progress
                WHERE task_id = ?
                ORDER BY created_at DESC
            """,
                (task_id,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_task_comments(self, task_id: int) -> list[dict]:
        """Get comments for a task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM task_comments
                WHERE task_id = ?
                ORDER BY created_at DESC
            """,
                (task_id,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def add_task_comment(
        self, task_id: int, comment: str, comment_type: str = "note"
    ) -> None:
        """Add a comment to a task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO task_comments (task_id, comment, comment_type)
                VALUES (?, ?, ?)
            """,
                (task_id, comment, comment_type),
            )
            conn.commit()

    def get_project_stats(self) -> dict:
        """Get overall project statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get basic counts
            cursor.execute("SELECT COUNT(*) as total_tasks FROM tasks")
            total_tasks = cursor.fetchone()["total_tasks"]

            cursor.execute(
                "SELECT COUNT(*) as completed_tasks FROM tasks "
                "WHERE status = 'completed'"
            )
            completed_tasks = cursor.fetchone()["completed_tasks"]

            cursor.execute(
                "SELECT COUNT(*) as in_progress_tasks FROM tasks "
                "WHERE status = 'in_progress'"
            )
            in_progress_tasks = cursor.fetchone()["in_progress_tasks"]

            cursor.execute(
                "SELECT COUNT(*) as blocked_tasks FROM tasks WHERE status = 'blocked'"
            )
            blocked_tasks = cursor.fetchone()["blocked_tasks"]

            # Get phase breakdown
            cursor.execute("""
                SELECT phase, COUNT(*) as count,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)
                       as completed
                FROM tasks
                GROUP BY phase
                ORDER BY phase
            """)
            phase_stats = [dict(row) for row in cursor.fetchall()]

            # Get component area breakdown
            cursor.execute("""
                SELECT component_area, COUNT(*) as count,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)
                       as completed
                FROM tasks
                GROUP BY component_area
                ORDER BY count DESC
            """)
            component_stats = [dict(row) for row in cursor.fetchall()]

            # Calculate estimated hours
            cursor.execute("SELECT SUM(time_estimate_hours) as total_hours FROM tasks")
            total_hours = cursor.fetchone()["total_hours"] or 0

            cursor.execute("""
                SELECT SUM(time_estimate_hours) as completed_hours
                FROM tasks WHERE status = 'completed'
            """)
            completed_hours = cursor.fetchone()["completed_hours"] or 0

            return {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "in_progress_tasks": in_progress_tasks,
                "blocked_tasks": blocked_tasks,
                "not_started_tasks": total_tasks
                - completed_tasks
                - in_progress_tasks
                - blocked_tasks,
                "completion_percentage": (completed_tasks / total_tasks * 100)
                if total_tasks > 0
                else 0,
                "total_estimated_hours": total_hours,
                "completed_hours": completed_hours,
                "remaining_hours": total_hours - completed_hours,
                "phase_breakdown": phase_stats,
                "component_breakdown": component_stats,
            }

    def get_next_tasks(self, limit: int = 5) -> list[dict]:
        """Get the next tasks that should be worked on."""
        ready_tasks = self.get_ready_tasks()
        return ready_tasks[:limit]

    def search_tasks(self, search_term: str) -> list[dict]:
        """Search tasks by title or description."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tasks
                WHERE title LIKE ? OR description LIKE ?
                ORDER BY priority DESC, created_at ASC
            """,
                (f"%{search_term}%", f"%{search_term}%"),
            )

            return [dict(row) for row in cursor.fetchall()]


def main():
    """Demonstrate task manager usage and testing."""
    # Initialize task manager
    tm = TaskManager()

    print("🎯 AI Job Scraper Task Manager")
    print("=" * 50)

    # Get project statistics
    stats = tm.get_project_stats()
    print("\n📊 Project Overview:")
    print(f"   Total Tasks: {stats['total_tasks']}")
    print(
        f"   Completed: {stats['completed_tasks']} "
        f"({stats['completion_percentage']:.1f}%)"
    )
    print(f"   In Progress: {stats['in_progress_tasks']}")
    print(f"   Blocked: {stats['blocked_tasks']}")
    print(f"   Not Started: {stats['not_started_tasks']}")
    print(f"   Estimated Hours: {stats['total_estimated_hours']:.1f}")
    print(f"   Completed Hours: {stats['completed_hours']:.1f}")
    print(f"   Remaining Hours: {stats['remaining_hours']:.1f}")

    # Show phase breakdown
    print("\n📅 Phase Breakdown:")
    for phase_stat in stats["phase_breakdown"]:
        phase = phase_stat["phase"]
        count = phase_stat["count"]
        completed = phase_stat["completed"]
        percentage = (completed / count * 100) if count > 0 else 0
        print(f"   Phase {phase}: {completed}/{count} ({percentage:.1f}%)")

    # Show next tasks to work on
    print("\n🚀 Next Tasks to Work On:")
    next_tasks = tm.get_next_tasks(5)
    for i, task in enumerate(next_tasks, 1):
        print(
            f"   {i}. {task['title']} ({task['component_area']}, "
            f"{task['priority']} priority)"
        )

    # Show critical path
    print("\n⚡ Critical Path Tasks:")
    critical_tasks = tm.get_critical_path()[:5]
    for i, task in enumerate(critical_tasks, 1):
        status_emoji = {
            "not_started": "⭕",
            "in_progress": "🔄",
            "completed": "✅",
            "blocked": "🚫",
        }.get(task["status"], "❓")
        print(f"   {i}. {status_emoji} {task['title']} ({task['status']})")

    # Show any blocked tasks
    blocked_tasks = tm.get_blocked_tasks()
    if blocked_tasks:
        print("\n🚫 Blocked Tasks:")
        for task in blocked_tasks[:3]:
            print(f"   - {task['title']} (blocked by: {task['blocking_tasks']})")

    print("\n💡 Use TaskManager class to manage tasks programmatically!")


if __name__ == "__main__":
    main()
