"""
E2E tests for AI entity endpoints.

Tests verify complete AI management workflows:
- Create AI entity (admin only)
- List AI entities
- Update/delete AI entities
- Get available AIs in room
- Invite AI to conversation
- Remove AI from conversation
"""

import pytest


@pytest.mark.e2e
class TestAIEntityEndpoints:
    """E2E tests for AI entity management endpoints."""

    async def test_admin_create_ai_entity_success(self, async_client, authenticated_admin_headers):
        """Test admin successfully creates an AI entity."""
        # Act
        response = await async_client.post(
            "/api/v1/ai/entities",
            headers=authenticated_admin_headers,
            json={
                "name": "assistant_gpt4",
                "display_name": "GPT-4 Assistant",
                "system_prompt": "You are a helpful AI assistant.",
                "model_name": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2000,
            },
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "assistant_gpt4"
        assert data["display_name"] == "GPT-4 Assistant"
        assert data["status"] == "offline"
        assert "id" in data

    async def test_regular_user_cannot_create_ai_entity(self, async_client, authenticated_user_headers):
        """Test regular user cannot create AI entities."""
        # Act
        response = await async_client.post(
            "/api/v1/ai/entities",
            headers=authenticated_user_headers,
            json={
                "name": "unauthorized_ai",
                "display_name": "Unauthorized AI",
                "system_prompt": "Should fail",
                "model_name": "gpt-3.5",
            },
        )

        # Assert
        assert response.status_code == 403

    async def test_get_all_ai_entities(self, async_client, authenticated_user_headers):
        """Test getting all AI entities."""
        # Arrange - Create AI entity first
        await async_client.post(
            "/api/v1/ai/entities",
            headers=await self._get_admin_headers(async_client),
            json={
                "name": "test_ai_1",
                "display_name": "Test AI 1",
                "system_prompt": "Test prompt",
                "model_name": "gpt-3.5",
            },
        )

        # Act
        response = await async_client.get(
            "/api/v1/ai/entities",
            headers=authenticated_user_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(ai["name"] == "test_ai_1" for ai in data)

    async def test_get_ai_entity_by_id(self, async_client, authenticated_user_headers, authenticated_admin_headers):
        """Test getting AI entity by ID."""
        # Arrange - Create AI entity
        create_response = await async_client.post(
            "/api/v1/ai/entities",
            headers=authenticated_admin_headers,
            json={
                "name": "test_ai_get",
                "display_name": "Test AI Get",
                "system_prompt": "Test prompt",
                "model_name": "gpt-3.5",
            },
        )
        ai_id = create_response.json()["id"]

        # Act
        response = await async_client.get(
            f"/api/v1/ai/entities/{ai_id}",
            headers=authenticated_user_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == ai_id
        assert data["name"] == "test_ai_get"

    async def test_update_ai_entity(self, async_client, authenticated_admin_headers):
        """Test updating AI entity (admin only)."""
        # Arrange - Create AI entity
        create_response = await async_client.post(
            "/api/v1/ai/entities",
            headers=authenticated_admin_headers,
            json={
                "name": "test_ai_update",
                "display_name": "Original Name",
                "system_prompt": "Original prompt",
                "model_name": "gpt-3.5",
            },
        )
        ai_id = create_response.json()["id"]

        # Act
        response = await async_client.put(
            f"/api/v1/ai/entities/{ai_id}",
            headers=authenticated_admin_headers,
            json={
                "display_name": "Updated Name",
                "system_prompt": "Updated prompt",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Name"
        assert data["system_prompt"] == "Updated prompt"

    async def test_delete_ai_entity(self, async_client, authenticated_admin_headers):
        """Test deleting AI entity (admin only)."""
        # Arrange - Create AI entity
        create_response = await async_client.post(
            "/api/v1/ai/entities",
            headers=authenticated_admin_headers,
            json={
                "name": "test_ai_delete",
                "display_name": "To Delete",
                "system_prompt": "Test prompt",
                "model_name": "gpt-3.5",
            },
        )
        ai_id = create_response.json()["id"]

        # Act
        response = await async_client.delete(
            f"/api/v1/ai/entities/{ai_id}",
            headers=authenticated_admin_headers,
        )

        # Assert
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

    async def test_get_available_ai_in_room(self, async_client, authenticated_admin_headers, authenticated_user_headers):
        """Test getting available AI entities in a room."""
        # Arrange - Create room
        room_response = await async_client.post(
            "/api/v1/rooms/",
            headers=authenticated_admin_headers,
            json={
                "name": "AI Test Room",
                "description": "Room for AI testing",
                "max_users": 10,
            },
        )
        room_id = room_response.json()["id"]

        # Act
        response = await async_client.get(
            f"/api/v1/ai/rooms/{room_id}/available",
            headers=authenticated_user_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_complete_ai_workflow(
        self, async_client, authenticated_admin_headers, authenticated_user_headers
    ):
        """Test complete AI workflow: create, list, update, delete."""
        # Step 1: Create AI entity
        create_response = await async_client.post(
            "/api/v1/ai/entities",
            headers=authenticated_admin_headers,
            json={
                "name": "workflow_test_ai",
                "display_name": "Workflow Test AI",
                "system_prompt": "Test assistant",
                "model_name": "gpt-3.5",
                "temperature": 0.8,
            },
        )
        assert create_response.status_code == 201
        ai_id = create_response.json()["id"]

        # Step 2: List all AIs (should include our new one)
        list_response = await async_client.get(
            "/api/v1/ai/entities",
            headers=authenticated_user_headers,
        )
        assert list_response.status_code == 200
        assert any(ai["id"] == ai_id for ai in list_response.json())

        # Step 3: Get specific AI
        get_response = await async_client.get(
            f"/api/v1/ai/entities/{ai_id}",
            headers=authenticated_user_headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "workflow_test_ai"

        # Step 4: Update AI
        update_response = await async_client.put(
            f"/api/v1/ai/entities/{ai_id}",
            headers=authenticated_admin_headers,
            json={"display_name": "Updated Workflow AI"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["display_name"] == "Updated Workflow AI"

        # Step 5: Delete AI
        delete_response = await async_client.delete(
            f"/api/v1/ai/entities/{ai_id}",
            headers=authenticated_admin_headers,
        )
        assert delete_response.status_code == 200

    async def _get_admin_headers(self, async_client):
        """Helper to get admin auth headers."""
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.com",
                "password": "admin123456",
            },
        )
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
