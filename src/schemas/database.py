"""SQLModel database entity models with Pydantic integration.

This module provides SQLModel table definitions that work seamlessly with
the existing Pydantic business models, enabling end-to-end type safety.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, Column, Index, UniqueConstraint
from sqlmodel import Field, Relationship

from .unified_models import (
    AgentReport,
    AgentType,
    BaseEntityModel,
    ComponentArea,
    DependencyType,
    TaskComplexity,
    TaskCore,
    TaskPriority,
    TaskStatus,
)


class Task(BaseEntityModel, table=True):
    """SQLModel task table with full Pydantic integration.

    Bridges the TaskCore business model with database persistence,
    enabling seamless conversion between business and persistence layers.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_component_area", "component_area"),
        Index("ix_tasks_phase", "phase"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_priority", "priority"),
        Index("ix_tasks_uuid", "uuid"),
        CheckConstraint("time_estimate_hours > 0", name="ck_positive_time"),
        CheckConstraint("phase BETWEEN 1 AND 10", name="ck_valid_phase"),
    )

    # Primary key and identifiers
    id: int | None = Field(default=None, primary_key=True)
    uuid: UUID = Field(default_factory=uuid4, unique=True, index=True)

    # Core fields (matching TaskCore business model)
    title: str = Field(min_length=1, max_length=200, index=True)
    description: str = Field(default="", max_length=2000)
    component_area: ComponentArea = ComponentArea.TASK
    phase: int = Field(default=1, ge=1, le=10)
    priority: TaskPriority = TaskPriority.MEDIUM
    complexity: TaskComplexity = TaskComplexity.MEDIUM
    status: TaskStatus = TaskStatus.NOT_STARTED
    source_document: str = Field(default="", max_length=500)
    success_criteria: str = Field(default="", max_length=1000)
    time_estimate_hours: float = Field(default=1.0, ge=0.1, le=100.0)
    parent_task_id: int | None = Field(default=None, foreign_key="tasks.id")

    # Relationships
    dependencies: list["TaskDependency"] = Relationship(
        back_populates="task",
        sa_relationship_kwargs={"foreign_keys": "[TaskDependency.task_id]"},
    )
    dependents: list["TaskDependency"] = Relationship(
        back_populates="depends_on_task",
        sa_relationship_kwargs={"foreign_keys": "[TaskDependency.depends_on_task_id]"},
    )
    progress_records: list["TaskProgress"] = Relationship(back_populates="task")
    execution_logs: list["TaskExecutionLog"] = Relationship(back_populates="task")
    subtasks: list["Task"] = Relationship(
        back_populates="parent_task", sa_relationship_kwargs={"remote_side": "Task.id"}
    )
    parent_task: Optional["Task"] = Relationship(
        back_populates="subtasks", sa_relationship_kwargs={"remote_side": "Task.id"}
    )

    def to_core_model(self) -> TaskCore:
        """Convert to TaskCore business model."""
        return TaskCore.model_validate(self.model_dump())

    @classmethod
    def from_core_model(cls, core_model: TaskCore) -> "Task":
        """Create from TaskCore business model."""
        data = core_model.model_dump(exclude={"uuid"} if core_model.id else set())
        return cls.model_validate(data)

    def update_from_core_model(self, core_model: TaskCore) -> None:
        """Update entity from business model."""
        for field, value in core_model.model_dump(exclude={"id", "uuid"}).items():
            if hasattr(self, field):
                setattr(self, field, value)
        self.updated_at = datetime.now()


class TaskDependency(BaseEntityModel, table=True):
    """SQLModel task dependency with validation."""

    __tablename__ = "task_dependencies"
    __table_args__ = (
        Index("ix_task_dependencies_task_id", "task_id"),
        Index("ix_task_dependencies_depends_on", "depends_on_task_id"),
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),
        CheckConstraint("task_id != depends_on_task_id", name="ck_no_self_dependency"),
    )

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id")
    depends_on_task_id: int = Field(foreign_key="tasks.id")
    dependency_type: DependencyType = DependencyType.BLOCKS

    # Relationships
    task: Task = Relationship(
        back_populates="dependencies",
        sa_relationship_kwargs={"foreign_keys": "[TaskDependency.task_id]"},
    )
    depends_on_task: Task = Relationship(
        back_populates="dependents",
        sa_relationship_kwargs={"foreign_keys": "[TaskDependency.depends_on_task_id]"},
    )


class TaskProgress(BaseEntityModel, table=True):
    """SQLModel task progress tracking."""

    __tablename__ = "task_progress"
    __table_args__ = (
        Index("ix_task_progress_task_id", "task_id"),
        Index("ix_task_progress_created_at", "created_at"),
        CheckConstraint(
            "progress_percentage BETWEEN 0 AND 100", name="ck_valid_progress"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id")
    progress_percentage: int = Field(ge=0, le=100, default=0)
    notes: str = Field(default="", max_length=1000)
    updated_by: str = Field(default="system", max_length=100)

    # Relationships
    task: Task = Relationship(back_populates="progress_records")


class TaskExecutionLog(BaseEntityModel, table=True):
    """SQLModel task execution logging."""

    __tablename__ = "task_execution_logs"
    __table_args__ = (
        Index("ix_task_execution_logs_task_id", "task_id"),
        Index("ix_task_execution_logs_agent_type", "agent_type"),
        Index("ix_task_execution_logs_status", "status"),
        Index("ix_task_execution_logs_execution_id", "execution_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id")
    execution_id: UUID = Field(default_factory=uuid4, unique=True)
    agent_type: AgentType
    status: TaskStatus
    start_time: datetime
    end_time: datetime | None = None
    outputs: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error_details: str | None = Field(default=None, max_length=2000)
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)

    # Relationships
    task: Task = Relationship(back_populates="execution_logs")

    def to_agent_report(self) -> AgentReport:
        """Convert to AgentReport business model."""
        return AgentReport(
            agent_name=f"{self.agent_type.value}_agent",
            agent_type=self.agent_type,
            task_id=self.task_id,
            execution_id=self.execution_id,
            status=self.status,
            start_time=self.start_time,
            end_time=self.end_time,
            outputs=self.outputs,
            error_details=self.error_details,
            confidence_score=self.confidence_score,
        )

    @classmethod
    def from_agent_report(cls, report: AgentReport) -> "TaskExecutionLog":
        """Create from AgentReport business model."""
        return cls(
            task_id=report.task_id,
            execution_id=report.execution_id,
            agent_type=report.agent_type,
            status=report.status,
            start_time=report.start_time,
            end_time=report.end_time,
            outputs=report.outputs,
            error_details=report.error_details,
            confidence_score=report.confidence_score,
        )


class TaskComment(BaseEntityModel, table=True):
    """SQLModel task comments for tracking notes and updates."""

    __tablename__ = "task_comments"
    __table_args__ = (
        Index("ix_task_comments_task_id", "task_id"),
        Index("ix_task_comments_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id")
    comment: str = Field(max_length=2000)
    comment_type: str = Field(default="note", max_length=50)
    created_by: str = Field(default="system", max_length=100)


# Legacy compatibility with existing TaskTable
TaskTable = Task
TaskDependencyTable = TaskDependency
TaskProgressTable = TaskProgress
TaskExecutionLogTable = TaskExecutionLog
TaskCommentTable = TaskComment
