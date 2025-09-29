import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import app
from app.core.database import get_db
from app.core.auth_dependencies import get_current_active_user
from app.models.user import User, UserStatus
from app.models.room import Room


@pytest.mark.asyncio
class TestIntegrationAPI:
    """Integration tests for API endpoints with real database."""

    @pytest_asyncio.fixture
    async def test_user(self, async_db_session):
        """Create a test user in the database."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            status=UserStatus.AVAILABLE,
            is_active=True,
            preferred_language="en",
        )
        async_db_session.add(user)
        await async_db_session.commit()
        await async_db_session.refresh(user)
        print(f"✅ Created integration test user with ID: {user.id}")
        return user

    @pytest_asyncio.fixture
    async def test_room(self, async_db_session):
        """Create a test room in the database."""
        room = Room(
            name="Integration Test Room",
            description="A room for integration testing",
            max_users=10,
            is_active=True,
            is_translation_enabled=True,
        )
        async_db_session.add(room)
        await async_db_session.commit()
        await async_db_session.refresh(room)
        print(f"✅ Created integration test room with ID: {room.id}")
        return room

    @pytest_asyncio.fixture
    async def authenticated_client(self, async_db_session, test_user):
        """Create HTTP client with real database and authentication."""

        # Override database dependency with real test DB
        async def override_get_db():
            yield async_db_session

        # Override auth dependency with real test user
        async def override_get_current_active_user():
            return test_user

        # Apply overrides
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = override_get_current_active_user

        # Create client
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

        # Clean up
        app.dependency_overrides.clear()

    async def test_health_check_endpoint(self, authenticated_client):
        """Test health check endpoint - no database needed."""
        response = await authenticated_client.get("/api/v1/rooms/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rooms endpoint working"

    async def test_room_count_endpoint(self, authenticated_client):
        """Test room count endpoint with real database."""
        response = await authenticated_client.get("/api/v1/rooms/count")

        assert response.status_code == 200
        data = response.json()
        assert "active_rooms" in data
        assert "message" in data
        assert isinstance(data["active_rooms"], int)

    async def test_get_all_rooms_endpoint(self, authenticated_client, test_room):
        """Test get all rooms with real data."""
        response = await authenticated_client.get("/api/v1/rooms/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Should have at least our test room
        assert len(data) >= 1
        room_names = [room["name"] for room in data]
        assert "Integration Test Room" in room_names

    async def test_get_room_by_id_endpoint(self, authenticated_client, test_room):
        """Test get specific room by ID."""
        response = await authenticated_client.get(f"/api/v1/rooms/{test_room.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_room.id
        assert data["name"] == "Integration Test Room"
        assert data["is_active"] is True
        assert "created_at" in data

    async def test_join_room_workflow(self, authenticated_client, test_room, test_user):
        """Test complete join room workflow."""
        # Join the room
        response = await authenticated_client.post(f"/api/v1/rooms/{test_room.id}/join")

        assert response.status_code == 200
        data = response.json()
        assert data["room_id"] == test_room.id
        assert data["room_name"] == "Integration Test Room"
        assert "message" in data
        assert "user_count" in data

        # Verify user is now in room by checking room users
        users_response = await authenticated_client.get(f"/api/v1/rooms/{test_room.id}/users")
        assert users_response.status_code == 200
        users_data = users_response.json()

        assert users_data["room_id"] == test_room.id
        assert users_data["room_name"] == "Integration Test Room"
        assert len(users_data["users"]) >= 1

        # Find our test user in the users list
        user_found = any(user["username"] == "testuser" for user in users_data["users"])
        assert user_found, "Test user should be found in room users list"

    async def test_send_and_get_messages_workflow(self, authenticated_client, test_room, test_user):
        """Test complete messaging workflow: join room, send message, retrieve messages."""
        # First join the room
        join_response = await authenticated_client.post(f"/api/v1/rooms/{test_room.id}/join")
        assert join_response.status_code == 200

        # Send a message to the room
        message_data = {"content": "Hello from integration test!"}
        send_response = await authenticated_client.post(
            f"/api/v1/rooms/{test_room.id}/messages",
            json=message_data
        )
        assert send_response.status_code == 200

        message_response = send_response.json()
        assert message_response["content"] == "Hello from integration test!"
        assert message_response["sender_id"] == test_user.id
        assert message_response["sender_username"] == "testuser"
        assert message_response["room_id"] == test_room.id

        # Retrieve room messages
        messages_response = await authenticated_client.get(f"/api/v1/rooms/{test_room.id}/messages")
        assert messages_response.status_code == 200

        messages = messages_response.json()
        assert len(messages) >= 1

        # Find our sent message
        our_message = next((msg for msg in messages if msg["content"] == "Hello from integration test!"), None)
        assert our_message is not None, "Sent message should be found in room messages"
        assert our_message["sender_username"] == "testuser"

    async def test_leave_room_workflow(self, authenticated_client, test_room, test_user):
        """Test leave room workflow."""
        # First join the room
        join_response = await authenticated_client.post(f"/api/v1/rooms/{test_room.id}/join")
        assert join_response.status_code == 200

        # Then leave the room
        leave_response = await authenticated_client.post(f"/api/v1/rooms/{test_room.id}/leave")
        assert leave_response.status_code == 200

        leave_data = leave_response.json()
        assert leave_data["room_id"] == test_room.id
        assert leave_data["room_name"] == "Integration Test Room"
        assert "Left room" in leave_data["message"]

        # Verify user is no longer in room
        users_response = await authenticated_client.get(f"/api/v1/rooms/{test_room.id}/users")
        assert users_response.status_code == 200
        users_data = users_response.json()

        # User should not be in the users list anymore (or list should be empty)
        user_still_found = any(user["username"] == "testuser" for user in users_data["users"])
        assert not user_still_found, "User should not be found in room after leaving"