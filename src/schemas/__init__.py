"""Unified schema package for the orchestration system.

This package provides the complete unified schema architecture including:
- Foundation models and enums
- Business models with validation
- Database entity models
- Schema transformation utilities

Quick usage:
    from orchestration.schemas import TaskCore, TaskStatus, AgentType
    from orchestration.repositories import TaskRepository
    from orchestration.services import TaskService
"""

# Core business models
# Database entities
from .database import (
    Task,
    TaskComment,
    TaskCommentTable,
    TaskDependency,
    TaskDependencyTable,
    TaskExecutionLog,
    TaskExecutionLogTable,
    TaskProgress,
    TaskProgressTable,
    # Legacy compatibility aliases
    TaskTable,
)

# Transformation utilities
from .transformations import (
    BatchTransformer,
    LegacyCompatibilityLayer,
    SchemaTransformer,
    convert_to_core_model,
    convert_to_entity,
    validate_and_transform,
)

# Unified models and types
from .unified_models import (
    AgentReport,
    AgentType,
    BaseBusinessModel,
    BaseEntityModel,
    BaseLLMResponseModel,
    ComponentArea,
    DependencyType,
    TaskComplexity,
    TaskCore,
    TaskDelegation,
    TaskPriority,
    TaskStatus,
    UnifiedConfig,
    can_transition_status,
    get_status_progress_percentage,
)

__all__ = [
    "AgentReport",
    "AgentType",
    "BaseBusinessModel",
    "BaseEntityModel",
    "BaseLLMResponseModel",
    "BatchTransformer",
    "ComponentArea",
    "DependencyType",
    "LegacyCompatibilityLayer",
    "SchemaTransformer",
    "Task",
    "TaskComment",
    "TaskCommentTable",
    "TaskComplexity",
    "TaskCore",
    "TaskDelegation",
    "TaskDependency",
    "TaskDependencyTable",
    "TaskExecutionLog",
    "TaskExecutionLogTable",
    "TaskPriority",
    "TaskProgress",
    "TaskProgressTable",
    "TaskStatus",
    "TaskTable",
    "UnifiedConfig",
    "can_transition_status",
    "convert_to_core_model",
    "convert_to_entity",
    "get_status_progress_percentage",
    "validate_and_transform",
]
