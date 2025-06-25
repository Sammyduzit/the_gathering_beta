import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest

@pytest.mark.e2e
class TestCriticalUserJourneys:
    """Critical user workflows that must always work."""

    def test_complete_chat_workflow(self, client, created_admin, created_user,
                                    authenticated_admin_headers, authenticated_user_headers,
                                    sample_room_data):
        """Complete user journey: Register → Login → Create Room → Join → Chat → Private Chat"""

        room_response = client.post("/api/v1/rooms/", json=sample_room_data, headers=authenticated_admin_headers)
        assert room_response.status_code == 201
        room_id = room_response.json()["id"]

        admin_join = client.post(f"/api/v1/rooms/{room_id}/join", headers=authenticated_admin_headers)
        assert admin_join.status_code == 200

        user_join = client.post(f"/api/v1/rooms/{room_id}/join", headers=authenticated_user_headers)
        assert user_join.status_code == 200
        assert user_join.json()["user_count"] == 2

        # 3 type chat system messaging
        room_message = client.post(f"/api/v1/rooms/{room_id}/messages",
                                   json={"content": "Hello everyone!"},
                                   headers=authenticated_user_headers)
        assert room_message.status_code == 200
        assert room_message.json()["content"] == "Hello everyone!"

        room_history = client.get(f"/api/v1/rooms/{room_id}/messages", headers=authenticated_admin_headers)
        assert room_history.status_code == 200
        messages = room_history.json()
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello everyone!"
        assert messages[0]["sender_username"] == created_user.username

        conv_data = {"participant_usernames": [created_admin.username], "conversation_type": "private"}
        conv_response = client.post("/api/v1/conversations", json=conv_data, headers=authenticated_user_headers)
        assert conv_response.status_code == 201
        conv_id = conv_response.json()["conversation_id"]

        private_message = client.post(f"/api/v1/conversations/{conv_id}/messages",
                                      json={"content": "Private hello!"},
                                      headers=authenticated_user_headers)
        assert private_message.status_code == 200

        private_history = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=authenticated_admin_headers)
        assert private_history.status_code == 200
        private_messages = private_history.json()
        assert len(private_messages) == 1
        assert private_messages[0]["content"] == "Private hello!"

        assert room_message.json()["room_id"] == room_id
        assert room_message.json()["conversation_id"] is None
        assert private_message.json()["conversation_id"] == conv_id
        assert private_message.json()["room_id"] is None

    def test_room_closure_workflow(self, client, created_admin, created_user,
                                   authenticated_admin_headers, authenticated_user_headers):
        """Test room deletion workflow with cleanup."""
        # Create room and conversation
        room_response = client.post("/api/v1/rooms/",
                                    json={"name": "Test Room", "description": "Test"},
                                    headers=authenticated_admin_headers)
        room_id = room_response.json()["id"]

        client.post(f"/api/v1/rooms/{room_id}/join", headers=authenticated_admin_headers)
        client.post(f"/api/v1/rooms/{room_id}/join", headers=authenticated_user_headers)

        conv_response = client.post("/api/v1/conversations",
                                    json={"participant_usernames": [created_admin.username], "conversation_type": "private"},
                                    headers=authenticated_user_headers)
        conv_id = conv_response.json()["conversation_id"]

        client.post(f"/api/v1/conversations/{conv_id}/messages",
                    json={"content": "Test message"}, headers=authenticated_user_headers)

        # Verify users are in room
        room_users = client.get(f"/api/v1/rooms/{room_id}/users", headers=authenticated_admin_headers)
        assert room_users.json()["total_users"] == 2

        # Admin closes room
        delete_response = client.delete(f"/api/v1/rooms/{room_id}", headers=authenticated_admin_headers)
        assert delete_response.status_code == 200
        delete_result = delete_response.json()

        assert "closed" in delete_result["message"]
        assert delete_result["users_kicked"] == 2
        assert delete_result["conversations_archived"] == 1
        assert "Chat history remains accessible" in delete_result["note"]

        # Verify users were kicked out
        room_users_after = client.get(f"/api/v1/rooms/{room_id}/users", headers=authenticated_admin_headers)
        assert room_users_after.status_code == 404

    def test_authentication_security(self, client, sample_user_data):
        """Test authentication and authorization security."""
        # Unauthorized access
        no_auth_response = client.get("/api/v1/auth/me")
        assert no_auth_response.status_code == 401

        register_response = client.post("/api/v1/auth/register", json=sample_user_data)
        assert register_response.status_code == 201

        login_response = client.post("/api/v1/auth/login", json={
            "email": sample_user_data["email"], "password": sample_user_data["password"]
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Authenticated access
        auth_headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert me_response.status_code == 200
        assert me_response.json()["username"] == sample_user_data["username"]

        # Non-admin should not be able to create rooms
        room_data = {"name": "Test Room", "description": "Test"}
        create_room_response = client.post("/api/v1/rooms/", json=room_data, headers=auth_headers)
        assert create_room_response.status_code == 403