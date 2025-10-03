"""
Unit tests for AIEntityRepository.

Tests focus on CRUD operations and query methods using SQLite in-memory database.
"""

import pytest

from app.models.ai_entity import AIEntity
from app.repositories.ai_entity_repository import AIEntityRepository


@pytest.mark.unit
class TestAIEntityRepository:
    """Unit tests for AIEntityRepository CRUD operations."""

    async def test_create_entity_success(self, db_session):
        """Test successful AI entity creation."""
        repo = AIEntityRepository(db_session)
        entity = AIEntity(
            name="assistant",
            display_name="AI Assistant",
            system_prompt="You are a helpful assistant",
            model_name="gpt-4",
        )

        created_entity = await repo.create(entity)

        assert created_entity.id is not None
        assert created_entity.name == "assistant"
        assert created_entity.display_name == "AI Assistant"
        assert created_entity.is_active is True

    async def test_get_by_id_success(self, db_session):
        """Test successful entity retrieval by ID."""
        repo = AIEntityRepository(db_session)
        entity = AIEntity(name="helper", display_name="Helper Bot", system_prompt="Help users", model_name="gpt-4")
        created = await repo.create(entity)

        found_entity = await repo.get_by_id(created.id)

        assert found_entity is not None
        assert found_entity.id == created.id
        assert found_entity.name == "helper"

    async def test_get_by_id_not_found(self, db_session):
        """Test entity retrieval when ID does not exist."""
        repo = AIEntityRepository(db_session)

        found_entity = await repo.get_by_id(99999)

        assert found_entity is None

    async def test_get_by_name_success(self, db_session):
        """Test successful entity retrieval by name."""
        repo = AIEntityRepository(db_session)
        entity = AIEntity(
            name="coder", display_name="Code Assistant", system_prompt="Help with code", model_name="gpt-4"
        )
        await repo.create(entity)

        found_entity = await repo.get_by_name("coder")

        assert found_entity is not None
        assert found_entity.name == "coder"

    async def test_get_by_name_not_found(self, db_session):
        """Test entity retrieval when name does not exist."""
        repo = AIEntityRepository(db_session)

        found_entity = await repo.get_by_name("nonexistent")

        assert found_entity is None

    async def test_get_active_entities(self, db_session):
        """Test retrieval of active entities only."""
        repo = AIEntityRepository(db_session)

        active_entity = AIEntity(name="active", display_name="Active Bot", system_prompt="Active", model_name="gpt-4")
        inactive_entity = AIEntity(
            name="inactive", display_name="Inactive Bot", system_prompt="Inactive", model_name="gpt-4", is_active=False
        )

        await repo.create(active_entity)
        await repo.create(inactive_entity)

        active_entities = await repo.get_active_entities()

        assert len(active_entities) == 1
        assert active_entities[0].name == "active"

    async def test_name_exists(self, db_session):
        """Test name existence check."""
        repo = AIEntityRepository(db_session)
        entity = AIEntity(name="unique", display_name="Unique Bot", system_prompt="Unique", model_name="gpt-4")
        await repo.create(entity)

        exists = await repo.name_exists("unique")
        not_exists = await repo.name_exists("other")

        assert exists is True
        assert not_exists is False

    async def test_name_exists_with_exclude(self, db_session):
        """Test name existence check excluding specific ID."""
        repo = AIEntityRepository(db_session)
        entity = AIEntity(name="test", display_name="Test Bot", system_prompt="Test", model_name="gpt-4")
        created = await repo.create(entity)

        exists = await repo.name_exists("test", exclude_id=created.id)

        assert exists is False

    async def test_update_entity(self, db_session):
        """Test entity update."""
        repo = AIEntityRepository(db_session)
        entity = AIEntity(name="updatable", display_name="Original Name", system_prompt="Original", model_name="gpt-4")
        created = await repo.create(entity)

        created.display_name = "Updated Name"
        updated = await repo.update(created)

        assert updated.display_name == "Updated Name"

    async def test_soft_delete_entity(self, db_session):
        """Test soft delete sets entity inactive."""
        repo = AIEntityRepository(db_session)
        entity = AIEntity(name="deletable", display_name="Delete Me", system_prompt="Delete", model_name="gpt-4")
        created = await repo.create(entity)

        deleted = await repo.delete(created.id)
        found_entity = await repo.get_by_id(created.id)

        assert deleted is True
        assert found_entity.is_active is False

    async def test_delete_nonexistent_entity(self, db_session):
        """Test delete returns False for nonexistent entity."""
        repo = AIEntityRepository(db_session)

        deleted = await repo.delete(99999)

        assert deleted is False

    async def test_exists_check(self, db_session):
        """Test entity existence check."""
        repo = AIEntityRepository(db_session)
        entity = AIEntity(name="exists", display_name="Exists Bot", system_prompt="Exists", model_name="gpt-4")
        created = await repo.create(entity)

        exists = await repo.exists(created.id)
        not_exists = await repo.exists(99999)

        assert exists is True
        assert not_exists is False

    async def test_get_all_with_pagination(self, db_session):
        """Test get all entities with limit and offset."""
        repo = AIEntityRepository(db_session)

        for i in range(5):
            entity = AIEntity(
                name=f"entity{i}",
                display_name=f"Entity {i}",
                system_prompt="Test",
                model_name="gpt-4",
            )
            await repo.create(entity)

        all_entities = await repo.get_all(limit=2, offset=1)

        assert len(all_entities) == 2
