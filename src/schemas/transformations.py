"""Schema transformation utilities for model conversion.

Provides utilities for converting between different model types,
handling legacy compatibility, and data migration operations.
"""

from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlmodel import SQLModel

# Using the unified schema models
from .database import Task as TaskEntity
from .database import TaskExecutionLog, TaskProgress
from .unified_models import (
    AgentReport,
    TaskCore,
    TaskStatus,
    get_status_progress_percentage,
)

T = TypeVar("T", bound=BaseModel)
E = TypeVar("E", bound=SQLModel)


class SchemaTransformer:
    """Central hub for all schema transformations.

    Provides bidirectional conversion between business models,
    database entities, and legacy formats.
    """

    @staticmethod
    def task_entity_to_core(entity: TaskEntity) -> TaskCore:
        """Convert TaskEntity to TaskCore business model."""
        return entity.to_core_model()

    @staticmethod
    def task_core_to_entity(core_model: TaskCore) -> TaskEntity:
        """Convert TaskCore to TaskEntity."""
        return TaskEntity.from_core_model(core_model)

    @staticmethod
    def legacy_task_table_to_core(task_table: "TaskEntity") -> TaskCore:
        """Convert legacy TaskTable to TaskCore business model."""
        # Map legacy fields to new schema
        return TaskCore(
            id=task_table.id,
            title=task_table.title,
            description=task_table.description,
            component_area=task_table.component_area,
            phase=task_table.phase,
            priority=task_table.priority,  # Maps string to enum
            complexity=task_table.complexity,  # Maps string to enum
            status=TaskStatus(task_table.status),
            source_document=task_table.source_document,
            success_criteria=task_table.success_criteria,
            time_estimate_hours=task_table.time_estimate_hours,
            parent_task_id=task_table.parent_task_id,
        )

    @staticmethod
    def task_core_to_legacy_table(core_model: TaskCore) -> dict[str, Any]:
        """Convert TaskCore to legacy TaskTable format."""
        return {
            "id": core_model.id,
            "title": core_model.title,
            "description": core_model.description,
            "component_area": core_model.component_area.value,
            "phase": core_model.phase,
            "priority": core_model.priority.value,
            "complexity": core_model.complexity.value,
            "status": core_model.status.value,
            "source_document": core_model.source_document,
            "success_criteria": core_model.success_criteria,
            "time_estimate_hours": core_model.time_estimate_hours,
            "parent_task_id": core_model.parent_task_id,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

    @staticmethod
    def agent_report_to_execution_log(report: AgentReport) -> TaskExecutionLog:
        """Convert AgentReport to TaskExecutionLog entity."""
        return TaskExecutionLog.from_agent_report(report)

    @staticmethod
    def execution_log_to_agent_report(log: TaskExecutionLog) -> AgentReport:
        """Convert TaskExecutionLog entity to AgentReport."""
        return log.to_agent_report()

    @staticmethod
    def legacy_agent_report_to_unified(legacy_report: dict[str, Any]) -> AgentReport:
        """Convert legacy agent report dictionary to unified AgentReport."""
        return AgentReport(
            agent_name=legacy_report.get("agent_name", "legacy_agent"),
            agent_type=legacy_report.get("agent_type", "coding"),
            task_id=legacy_report.get("task_id", 0),
            status=TaskStatus(legacy_report.get("status", "completed")),
            success=legacy_report.get("success", True),
            confidence_score=legacy_report.get("confidence_score", 0.8),
            outputs=legacy_report.get("outputs", {}),
            artifacts=legacy_report.get("artifacts", []),
            next_actions=legacy_report.get("next_actions", []),
            issues_found=legacy_report.get("issues_found", []),
            error_details=legacy_report.get("error_details"),
            execution_time_minutes=legacy_report.get("execution_time_minutes", 0.0),
            created_at=datetime.now(),
        )

    @staticmethod
    def create_progress_from_status_change(
        task_id: int,
        old_status: TaskStatus,
        new_status: TaskStatus,
        notes: str = "",
        updated_by: str = "system",
    ) -> TaskProgress:
        """Create TaskProgress entry from status change."""
        progress_percentage = get_status_progress_percentage(new_status)

        return TaskProgress(
            task_id=task_id,
            progress_percentage=progress_percentage,
            notes=notes
            or f"Status changed from {old_status.value} to {new_status.value}",
            updated_by=updated_by,
        )


class BatchTransformer:
    """Utilities for batch transformation operations.

    Handles bulk conversions and data migration scenarios.
    """

    @staticmethod
    def tasks_entity_to_core_list(entities: list[TaskEntity]) -> list[TaskCore]:
        """Convert list of TaskEntity to TaskCore models."""
        return [entity.to_core_model() for entity in entities]

    @staticmethod
    def tasks_core_to_entity_list(core_models: list[TaskCore]) -> list[TaskEntity]:
        """Convert list of TaskCore to TaskEntity models."""
        return [TaskEntity.from_core_model(core) for core in core_models]

    @staticmethod
    def migrate_legacy_tasks_to_entities(
        legacy_tasks: list["TaskEntity"],
    ) -> list[TaskEntity]:
        """Migrate legacy TaskTable objects to new TaskEntity format."""
        entities = []

        for legacy_task in legacy_tasks:
            # Convert to core model first (handles validation)
            core_model = SchemaTransformer.legacy_task_table_to_core(legacy_task)

            # Convert to new entity
            entity = TaskEntity.from_core_model(core_model)
            entities.append(entity)

        return entities

    @staticmethod
    def export_tasks_for_backup(tasks: list[TaskCore]) -> list[dict[str, Any]]:
        """Export tasks to JSON-serializable format for backup."""
        return [task.model_dump() for task in tasks]

    @staticmethod
    def import_tasks_from_backup(backup_data: list[dict[str, Any]]) -> list[TaskCore]:
        """Import tasks from backup data."""
        return [TaskCore.model_validate(task_data) for task_data in backup_data]


class LegacyCompatibilityLayer:
    """Compatibility layer for legacy code integration.

    Provides adapters and shims for existing code that hasn't been
    migrated to the unified schema architecture yet.
    """

    @staticmethod
    def adapt_task_for_legacy_agent(task: TaskCore) -> dict[str, Any]:
        """Adapt TaskCore for legacy agent interfaces.

        Returns a dictionary that matches the expected format
        of legacy agent functions.
        """
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority.value,
            "success_criteria": task.success_criteria,
            "time_estimate": task.time_estimate_hours,
            "is_actionable": task.is_actionable,
            "progress_percentage": task.progress_percentage,
        }

    @staticmethod
    def adapt_legacy_agent_result(result: dict[str, Any], task_id: int) -> AgentReport:
        """Adapt legacy agent result to AgentReport format.

        Handles the various formats that legacy agents might return
        and converts them to the unified AgentReport format.
        """
        # Default values
        defaults = {
            "agent_name": "legacy_agent",
            "agent_type": "coding",  # Default to coding agent
            "task_id": task_id,
            "status": TaskStatus.COMPLETED,
            "start_time": datetime.now(),
            "end_time": datetime.now(),
            "success": True,
            "confidence_score": 0.8,
            "outputs": {},
            "artifacts_created": [],
            "next_actions": [],
            "issues_found": [],
            "error_details": None,
        }

        # Update with actual result data
        defaults.update(result)

        # Handle common legacy field mappings
        if "files_created" in result:
            defaults["artifacts_created"] = result["files_created"]

        if "recommendations" in result:
            defaults["next_actions"] = result["recommendations"]

        if "errors" in result:
            defaults["error_details"] = str(result["errors"])
            defaults["success"] = False
            defaults["status"] = TaskStatus.FAILED

        return AgentReport(**defaults)

    @staticmethod
    def create_legacy_task_dict(task: TaskCore) -> dict[str, Any]:
        """Create dictionary matching legacy task format.

        Used when interfacing with legacy database operations
        or external systems that expect the old format.
        """
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "component_area": task.component_area.value,
            "phase": task.phase,
            "priority": task.priority.value,
            "complexity": task.complexity.value,
            "status": task.status.value,
            "source_document": task.source_document,
            "success_criteria": task.success_criteria,
            "time_estimate_hours": task.time_estimate_hours,
            "parent_task_id": task.parent_task_id,
        }


# Convenience functions for common transformations
def convert_to_core_model(
    obj: TaskEntity | dict[str, Any],
) -> TaskCore:
    """Convert any supported type to TaskCore model.

    Args:
        obj: TaskEntity or dictionary representation

    Returns:
        TaskCore business model

    """
    if isinstance(obj, TaskEntity):
        return obj.to_core_model()
    elif isinstance(obj, dict):
        return TaskCore.model_validate(obj)
    else:
        raise ValueError(f"Unsupported type for conversion: {type(obj)}")


def convert_to_entity(obj: TaskCore | dict[str, Any]) -> TaskEntity:
    """Convert TaskCore or dict to TaskEntity.

    Args:
        obj: TaskCore model or dictionary representation

    Returns:
        TaskEntity for database operations

    """
    if isinstance(obj, TaskCore):
        return TaskEntity.from_core_model(obj)
    elif isinstance(obj, dict):
        core_model = TaskCore.model_validate(obj)
        return TaskEntity.from_core_model(core_model)
    else:
        raise ValueError(f"Unsupported type for conversion: {type(obj)}")


def validate_and_transform(data: dict[str, Any], target_type: type[T]) -> T:
    """Validate data and transform to target Pydantic model.

    Args:
        data: Raw data dictionary
        target_type: Target Pydantic model class

    Returns:
        Validated instance of target_type

    """
    return target_type.model_validate(data)
