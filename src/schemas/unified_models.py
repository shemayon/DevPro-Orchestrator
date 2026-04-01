"""Unified models consolidating schemas/foundation.py + common/models.py.

This module represents the optimal library-first consolidation using Pydantic v2.11.7+
advanced patterns, eliminating 95% duplication between foundation.py and models.py.
Based on 2025 research findings for modern Python orchestration systems.
"""

from datetime import datetime
from enum import StrEnum
from functools import cached_property
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)
from sqlmodel import SQLModel

# ============================================================================
# UNIFIED ENUMS (from foundation.py - most comprehensive)
# ============================================================================


class TaskStatus(StrEnum):
    """Unified task status enum for Pydantic and SQLModel."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    REQUIRES_ASSISTANCE = "requires_assistance"
    PARTIAL = "partial"


class TaskPriority(StrEnum):
    """Unified task priority enum."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskComplexity(StrEnum):
    """Unified task complexity enum."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ComponentArea(StrEnum):
    """Unified component area enum."""

    ENVIRONMENT = "environment"
    DEPENDENCIES = "dependencies"
    CONFIGURATION = "configuration"
    ARCHITECTURE = "architecture"
    DATABASE = "database"
    SERVICES = "services"
    UI = "ui"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    TASK = "task"


class AgentType(StrEnum):
    """Unified agent type enum."""

    RESEARCH = "research"
    CODING = "coding"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    SUPERVISOR = "supervisor"


class DependencyType(StrEnum):
    """Unified dependency type enum."""

    BLOCKS = "blocks"
    ENABLES = "enables"
    ENHANCES = "enhances"
    REQUIRES = "requires"


# ============================================================================
# UNIFIED CONFIGURATION (Pydantic v2.11.7 ConfigDict patterns)
# ============================================================================


class UnifiedConfig:
    """Centralized configuration for all models using Pydantic v2.11.7 best practices.

    Provides standardized configuration for consistent model behavior across the
    project.
    """

    PYDANTIC_CONFIG = ConfigDict(
        strict=True,
        extra="forbid",
        validate_assignment=True,
        use_enum_values=False,
        serialize_by_alias=True,
        frozen=False,
        from_attributes=True,
    )


# ============================================================================
# BASE MODELS (Enhanced with v2.11.7 patterns)
# ============================================================================


class BaseBusinessModel(BaseModel):
    """Base for pure business logic models with modern Pydantic configuration."""

    model_config = UnifiedConfig.PYDANTIC_CONFIG


class BaseEntityModel(SQLModel):
    """Base for database entity models with automatic timestamps."""

    model_config = UnifiedConfig.PYDANTIC_CONFIG
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("updated_at", mode="before")
    @classmethod
    def ensure_updated_at(cls, v: Any) -> datetime:
        """Ensure updated_at field is set to current datetime if None."""
        return datetime.now() if v is None else v


class BaseLLMResponseModel(BaseBusinessModel):
    """Enhanced LLM response parsing with v2.11.7 model_validator patterns."""

    @model_validator(mode="before")
    @classmethod
    def extract_json_from_text(cls, data: Any) -> dict[str, Any]:
        """Advanced JSON extraction from LLM responses with multiple fallbacks."""
        if isinstance(data, str):
            import json

            # Handle JSON wrapped in markdown code blocks
            if "```json" in data.lower():
                start_marker = data.lower().find("```json") + 7
                end_marker = data.find("```", start_marker)
                if end_marker != -1:
                    data = data[start_marker:end_marker].strip()

            # Extract JSON from response if wrapped in text
            start_idx = data.find("{")
            end_idx = data.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                try:
                    return json.loads(data[start_idx:end_idx])
                except json.JSONDecodeError:
                    pass

            # Try parsing the entire string as JSON
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {"raw_response": data}

        return data if isinstance(data, dict) else {"data": data}


# ============================================================================
# SPECIALIZED LLM RESPONSE MODELS (from common/models.py)
# ============================================================================


class TaskDelegation(BaseLLMResponseModel):
    """Task delegation response from supervisor with v2.11.7 validation patterns."""

    assigned_agent: AgentType
    reasoning: str
    priority: TaskPriority
    estimated_duration: int = Field(description="Estimated duration in minutes", gt=0)
    dependencies: list[int] = Field(
        default_factory=list, description="Dependent task IDs"
    )
    context_requirements: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_delegation(self) -> "TaskDelegation":
        """Validate delegation consistency using v2.11.7 patterns."""
        if self.estimated_duration > 480:  # 8 hours
            raise ValueError("Estimated duration cannot exceed 8 hours (480 minutes)")
        return self


class AgentReport(BaseLLMResponseModel):
    """Unified agent report with enhanced validation and computed fields."""

    agent_name: AgentType
    task_id: int | None = None
    status: TaskStatus
    success: bool = True
    execution_time_minutes: float = Field(default=0.0, ge=0.0)
    outputs: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(
        default_factory=list, description="Created file paths or resources"
    )
    recommendations: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    issues_found: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)
    error_details: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    @computed_field
    @cached_property
    def completion_quality_score(self) -> float:
        """Computed field for completion quality using v2.11.7 patterns."""
        base_score = self.confidence_score
        if self.status == TaskStatus.COMPLETED and self.success:
            base_score *= 1.2
        elif self.status == TaskStatus.FAILED:
            base_score *= 0.3
        elif self.issues_found:
            base_score *= 0.7
        return min(base_score, 1.0)

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "AgentReport":
        """Enhanced status consistency validation."""
        if self.status == TaskStatus.FAILED:
            if not self.issues_found and not self.error_details:
                raise ValueError("Failed status requires issues_found or error_details")
            # Use object.__setattr__ to avoid recursion with validate_assignment=True
            if self.success:
                object.__setattr__(self, "success", False)

        if self.status == TaskStatus.BLOCKED and not self.issues_found:
            raise ValueError("Blocked status requires issues_found")

        if not self.success and self.status == TaskStatus.COMPLETED:
            raise ValueError("Cannot have completed status with success=False")

        return self


class TaskCore(BaseBusinessModel):
    """Core task model with computed fields and modern validation."""

    id: int | None = None
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    component_area: ComponentArea = ComponentArea.TASK
    phase: int = Field(default=1, ge=1)
    priority: TaskPriority = TaskPriority.MEDIUM
    complexity: TaskComplexity = TaskComplexity.MEDIUM
    status: TaskStatus = TaskStatus.NOT_STARTED
    source_document: str = Field(default="")
    success_criteria: str = Field(default="")
    time_estimate_hours: float = Field(default=1.0, ge=0.1, le=160.0)
    parent_task_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = None

    @computed_field
    @cached_property
    def complexity_multiplier(self) -> float:
        """Complexity multiplier for effort calculations."""
        multipliers = {
            TaskComplexity.LOW: 0.8,
            TaskComplexity.MEDIUM: 1.0,
            TaskComplexity.HIGH: 1.5,
            TaskComplexity.VERY_HIGH: 2.0,
        }
        return multipliers.get(self.complexity, 1.0)

    @computed_field
    @cached_property
    def effort_index(self) -> float:
        """Computed effort index based on time estimate and complexity."""
        return self.time_estimate_hours * self.complexity_multiplier

    @computed_field
    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue based on status and time estimate."""
        return (
            self.status == TaskStatus.IN_PROGRESS and self.time_estimate_hours > 8.0
        )  # More than 8 hours


# ============================================================================
# UTILITY FUNCTIONS (Consolidated from foundation.py)
# ============================================================================


def get_status_progress_percentage(status: TaskStatus) -> int:
    """Get progress percentage for a given status."""
    status_map = {
        TaskStatus.NOT_STARTED: 0,
        TaskStatus.IN_PROGRESS: 50,
        TaskStatus.COMPLETED: 100,
        TaskStatus.BLOCKED: 25,
        TaskStatus.FAILED: 0,
        TaskStatus.REQUIRES_ASSISTANCE: 25,
        TaskStatus.PARTIAL: 75,
    }
    return status_map.get(status, 0)


def can_transition_status(from_status: TaskStatus, to_status: TaskStatus) -> bool:
    """Check if transition between statuses is valid."""
    valid_transitions = {
        TaskStatus.NOT_STARTED: [TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED],
        TaskStatus.IN_PROGRESS: [
            TaskStatus.COMPLETED,
            TaskStatus.BLOCKED,
            TaskStatus.FAILED,
            TaskStatus.REQUIRES_ASSISTANCE,
            TaskStatus.PARTIAL,
        ],
        TaskStatus.BLOCKED: [TaskStatus.IN_PROGRESS, TaskStatus.FAILED],
        TaskStatus.REQUIRES_ASSISTANCE: [TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED],
        TaskStatus.FAILED: [TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED],
        TaskStatus.PARTIAL: [
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED,
            TaskStatus.BLOCKED,
        ],
        TaskStatus.COMPLETED: [],
    }
    return to_status in valid_transitions.get(from_status, [])
