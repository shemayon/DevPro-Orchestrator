"""Base repository pattern with common operations.

Provides the foundation for all repository implementations with
standardized CRUD operations and query patterns.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from sqlmodel import Session, select

EntityT = TypeVar("EntityT")
BusinessT = TypeVar("BusinessT")


class BaseRepository(Generic[EntityT, BusinessT], ABC):
    """Base repository with common operations.

    Provides standardized data access patterns and ensures consistency
    across all repository implementations.
    """

    def __init__(self, session: Session):
        self.session = session

    @abstractmethod
    def get_entity_class(self) -> type[EntityT]:
        """Return the SQLModel entity class."""
        pass

    @abstractmethod
    def get_business_class(self) -> type[BusinessT]:
        """Return the Pydantic business model class."""
        pass

    def create(self, business_model: BusinessT, **kwargs) -> EntityT:
        """Create entity from business model."""
        entity_data = business_model.model_dump(exclude_unset=True)
        entity_data.update(kwargs)
        entity = self.get_entity_class()(**entity_data)
        self.session.add(entity)
        self.session.flush()
        return entity

    def get_by_id(self, entity_id: int) -> EntityT | None:
        """Get entity by ID."""
        return self.session.get(self.get_entity_class(), entity_id)

    def update(self, entity_id: int, updates: dict[str, Any]) -> EntityT | None:
        """Update entity with validation."""
        entity = self.get_by_id(entity_id)
        if entity:
            for key, value in updates.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            # Update timestamp if entity has updated_at
            if hasattr(entity, "updated_at"):
                from datetime import datetime

                entity.updated_at = datetime.now()
            self.session.add(entity)
            self.session.flush()
        return entity

    def delete(self, entity_id: int) -> bool:
        """Delete entity by ID."""
        entity = self.get_by_id(entity_id)
        if entity:
            self.session.delete(entity)
            return True
        return False

    def list_all(self, limit: int | None = None) -> list[EntityT]:
        """Get all entities with optional limit."""
        statement = select(self.get_entity_class())
        if limit:
            statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def count(self) -> int:
        """Count total entities."""
        from sqlalchemy import func

        statement = select(func.count()).select_from(self.get_entity_class())
        return self.session.exec(statement).one()

    def exists(self, entity_id: int) -> bool:
        """Check if entity exists."""
        return self.get_by_id(entity_id) is not None
