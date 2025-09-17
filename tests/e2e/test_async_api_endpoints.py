import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from main import app
from app.core.database import get_db
from app.core.auth_dependencies import get_current_active_user
from app.models.user import User, UserStatus
from app.models.room import Room


# Test database override
async def override_get_db():
    """Override database dependency for testing."""
    # This would be replaced with actual test database session
    yield AsyncMock()


# Test user override
async def override_get_current_active_user():
    """Override current user dependency for testing."""
    return User(
        id=1,
        username="testuser",
        email="test@example.com",
        status=UserStatus.AVAILABLE,
        is_active=True,
        preferred_language="en",
    )


@pytest.mark.asyncio
class TestAsyncAPIEndpoints:
    """Async E2E tests for API endpoints."""

    @pytest_asyncio.fixture
    async def async_client(self):
        """Create async HTTP client for testing."""
        # Override dependencies
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = override_get_current_active_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

        # Clean up overrides
        app.dependency_overrides.clear()

    async def test_health_check_endpoint(self, async_client):
        """Test health check endpoint."""
        # Act
        response = await async_client.get("/rooms/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rooms endpoint working"

    async def test_get_all_rooms_endpoint(self, async_client):
        """Test get all rooms endpoint."""
        # Arrange
        mock_rooms = [
            {
                "id": 1,
                "name": "Test Room",
                "description": "Test description",
                "max_users": 5,
                "is_active": True,
                "is_translation_enabled": True,
                "current_users": 0,
            }
        ]

        with patch('app.services.room_service.RoomService.get_all_rooms') as mock_get_rooms:
            mock_get_rooms.return_value = mock_rooms

            # Act
            response = await async_client.get("/rooms/")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Test Room"

    async def test_get_room_by_id_endpoint(self, async_client):
        """Test get room by ID endpoint."""
        # Arrange
        room_id = 1
        mock_room = {
            "id": room_id,
            "name": "Test Room",
            "description": "Test description",
            "max_users": 5,
            "is_active": True,
            "is_translation_enabled": True,
            "current_users": 0,
        }

        with patch('app.services.room_service.RoomService.get_room_by_id') as mock_get_room:
            mock_get_room.return_value = mock_room

            # Act
            response = await async_client.get(f"/rooms/{room_id}")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == room_id
            assert data["name"] == "Test Room"

    async def test_get_room_count_endpoint(self, async_client):
        """Test get room count endpoint."""
        # Arrange
        mock_count = {"active_rooms": 3}

        with patch('app.services.room_service.RoomService.get_room_count') as mock_count_rooms:
            mock_count_rooms.return_value = mock_count

            # Act
            response = await async_client.get("/rooms/count")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["active_rooms"] == 3

    async def test_join_room_endpoint(self, async_client):
        """Test join room endpoint with background tasks."""
        # Arrange
        room_id = 1
        mock_join_response = {
            "message": "Successfully joined room",
            "room_id": room_id,
            "room_name": "Test Room",
            "user_count": 2,
        }

        with patch('app.services.room_service.RoomService.join_room') as mock_join_room:
            mock_join_room.return_value = mock_join_response

            with patch('app.core.background_tasks.async_bg_task_manager.add_async_task') as mock_bg_task:
                # Act
                response = await async_client.post(f"/rooms/{room_id}/join")

                # Assert
                assert response.status_code == 200
                data = response.json()
                assert data["room_id"] == room_id
                assert data["message"] == "Successfully joined room"

                # Verify background tasks were scheduled
                assert mock_bg_task.call_count >= 2  # Activity logging + notification

    async def test_leave_room_endpoint(self, async_client):
        """Test leave room endpoint with background tasks."""
        # Arrange
        room_id = 1
        mock_leave_response = {
            "message": "Successfully left room",
            "room_id": room_id,
        }

        with patch('app.services.room_service.RoomService.leave_room') as mock_leave_room:
            mock_leave_room.return_value = mock_leave_response

            with patch('app.core.background_tasks.async_bg_task_manager.add_async_task') as mock_bg_task:
                # Act
                response = await async_client.post(f"/rooms/{room_id}/leave")

                # Assert
                assert response.status_code == 200
                data = response.json()
                assert data["room_id"] == room_id

                # Verify background tasks were scheduled
                assert mock_bg_task.call_count >= 2

    async def test_send_room_message_endpoint(self, async_client):
        """Test send room message endpoint with background translation."""
        # Arrange
        room_id = 1
        message_content = "Hello world"
        mock_message_response = {
            "id": 1,
            "content": message_content,
            "sender_id": 1,
            "room_id": room_id,
            "sent_at": "2024-01-01T00:00:00",
        }

        mock_room = Room(
            id=room_id,
            name="Test Room",
            description="Test room",
            max_users=5,
            is_active=True,
            is_translation_enabled=True,
        )

        mock_room_users = {
            "users": [
                {"id": 1, "username": "testuser", "preferred_language": "en"},
                {"id": 2, "username": "germanuser", "preferred_language": "de"},
            ]
        }

        with patch('app.services.room_service.RoomService.send_room_message') as mock_send_message:
            mock_send_message.return_value = mock_message_response

            with patch('app.services.room_service.RoomService.get_room_by_id') as mock_get_room:
                mock_get_room.return_value = mock_room

                with patch('app.services.room_service.RoomService.get_room_users') as mock_get_users:
                    mock_get_users.return_value = mock_room_users

                    with patch('app.core.background_tasks.async_bg_task_manager.add_async_task') as mock_bg_task:
                        # Act
                        response = await async_client.post(
                            f"/rooms/{room_id}/messages",
                            json={"content": message_content}
                        )

                        # Assert
                        assert response.status_code == 200
                        data = response.json()
                        assert data["content"] == message_content
                        assert data["room_id"] == room_id

                        # Verify background tasks were scheduled
                        # Should include translation + activity logging
                        assert mock_bg_task.call_count >= 2

    async def test_get_room_messages_endpoint(self, async_client):
        """Test get room messages endpoint."""
        # Arrange
        room_id = 1
        mock_messages = [
            {
                "id": 1,
                "content": "Test message",
                "sender_id": 1,
                "room_id": room_id,
                "sent_at": "2024-01-01T00:00:00",
            }
        ]

        with patch('app.services.room_service.RoomService.get_room_messages') as mock_get_messages:
            mock_get_messages.return_value = (mock_messages, 1)

            # Act
            response = await async_client.get(f"/rooms/{room_id}/messages")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["content"] == "Test message"

    async def test_get_room_users_endpoint(self, async_client):
        """Test get room users endpoint."""
        # Arrange
        room_id = 1
        mock_users_response = {
            "room_id": room_id,
            "users": [
                {"id": 1, "username": "testuser", "status": "available"}
            ],
            "user_count": 1,
        }

        with patch('app.services.room_service.RoomService.get_room_users') as mock_get_users:
            mock_get_users.return_value = mock_users_response

            # Act
            response = await async_client.get(f"/rooms/{room_id}/users")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["room_id"] == room_id
            assert data["user_count"] == 1

    async def test_update_user_status_endpoint(self, async_client):
        """Test update user status endpoint."""
        # Arrange
        new_status = "busy"
        mock_status_response = {
            "message": "Status updated successfully",
            "new_status": new_status,
        }

        with patch('app.services.room_service.RoomService.update_user_status') as mock_update_status:
            mock_update_status.return_value = mock_status_response

            # Act
            response = await async_client.patch(
                "/rooms/users/status",
                json={"status": new_status}
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["new_status"] == new_status

    async def test_unauthorized_access_without_mock(self):
        """Test that endpoints require authentication when dependency override is removed."""
        # Don't use the async_client fixture to test without auth override
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/rooms/")

            # Assert
            # Should require authentication
            assert response.status_code in [401, 422]  # Unauthorized or validation error