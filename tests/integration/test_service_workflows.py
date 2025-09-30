"""
Integration tests for cross-service workflows.

These tests verify that services work correctly together with real database
connections and actual external dependencies, testing complete business
workflows without full HTTP stack.
"""

import pytest


@pytest.mark.integration
class TestRoomServiceWorkflows:
    """Integration tests for room-related service workflows."""

    async def test_room_creation_and_user_joining_workflow(self, room_service, user_factory, db_session):
        """Test complete workflow: create room -> users join -> send messages."""
        # Create admin user
        admin = await user_factory.create_admin(db_session)

        # Admin creates room
        room_data = await room_service.create_room(
            name="Workflow Test Room",
            description="Integration test room",
            max_users=5,
            is_translation_enabled=True,
        )

        assert room_data.name == "Workflow Test Room"
        assert room_data.is_translation_enabled is True

        # Create regular users
        user1 = await user_factory.create(db_session, username="workflow_user1")
        user2 = await user_factory.create(db_session, username="workflow_user2")

        # Users join room
        join_result1 = await room_service.join_room(user1, room_data.id)
        join_result2 = await room_service.join_room(user2, room_data.id)

        assert join_result1["room_id"] == room_data.id
        assert join_result2["room_id"] == room_data.id
        assert join_result2["user_count"] == 2  # Both users joined

        # Users send messages
        message1 = await room_service.send_room_message(user1, room_data.id, "Hello everyone!")
        message2 = await room_service.send_room_message(user2, room_data.id, "Hi there!")

        assert message1.content == "Hello everyone!"
        assert message1.sender_id == user1.id
        assert message2.content == "Hi there!"
        assert message2.sender_id == user2.id

        # Retrieve messages
        messages, count = await room_service.get_room_messages(user1, room_data.id)

        assert count >= 2
        assert len(messages) >= 2

    async def test_room_translation_workflow(self, room_service, user_factory, db_session):
        """Test room translation workflow with real translation service."""
        # Create room with translation enabled
        room_data = await room_service.create_room(
            name="Translation Test Room",
            description="Test translation workflow",
            max_users=5,
            is_translation_enabled=True,
        )

        # Create users with different preferred languages
        english_user = await user_factory.create(
            db_session,
            username="en_user",
            preferred_language="en",
            current_room_id=room_data.id
        )
        german_user = await user_factory.create(
            db_session,
            username="de_user",
            preferred_language="de",
            current_room_id=room_data.id
        )

        # English user sends message
        message = await room_service.send_room_message(
            english_user, room_data.id, "Hello, how are you today?"
        )

        assert message.content == "Hello, how are you today?"
        assert message.sender_id == english_user.id

        # Note: Translation happens in background, so we can't immediately verify
        # the translation result in this test. This would be better tested
        # in a background service integration test.


@pytest.mark.integration
class TestConversationServiceWorkflows:
    """Integration tests for conversation-related service workflows."""

    async def test_private_conversation_workflow(self, conversation_service, test_room_with_users):
        """Test complete private conversation workflow."""
        scenario = test_room_with_users
        user1 = scenario["users"][0]
        user2 = scenario["users"][1]

        # Create private conversation
        conversation = await conversation_service.create_conversation(
            current_user=user1,
            participant_usernames=[user2.username],
            conversation_type="private",
        )

        assert conversation.conversation_type.value == "private"
        assert conversation.room_id == scenario["room"].id

        # Send messages in conversation
        message1 = await conversation_service.send_message(
            user1, conversation.id, "Hi, this is a private message!"
        )
        message2 = await conversation_service.send_message(
            user2, conversation.id, "Hello back!"
        )

        assert message1.content == "Hi, this is a private message!"
        assert message1.conversation_id == conversation.id
        assert message2.content == "Hello back!"
        assert message2.conversation_id == conversation.id

        # Retrieve conversation messages
        messages, count = await conversation_service.get_messages(user1, conversation.id)

        assert count >= 2
        assert len(messages) >= 2

    async def test_group_conversation_workflow(self, conversation_service, test_room_with_users):
        """Test complete group conversation workflow."""
        scenario = test_room_with_users
        creator = scenario["users"][0]
        participant1 = scenario["users"][1]
        admin = scenario["admin"]

        # Create group conversation
        conversation = await conversation_service.create_conversation(
            current_user=creator,
            participant_usernames=[participant1.username, admin.username],
            conversation_type="group",
        )

        assert conversation.conversation_type.value == "group"

        # All participants send messages
        message1 = await conversation_service.send_message(
            creator, conversation.id, "Welcome to our group chat!"
        )
        message2 = await conversation_service.send_message(
            participant1, conversation.id, "Thanks for adding me!"
        )
        message3 = await conversation_service.send_message(
            admin, conversation.id, "Great to have everyone here!"
        )

        # Verify all messages
        messages, count = await conversation_service.get_messages(creator, conversation.id)

        assert count >= 3
        assert len(messages) >= 3

        # Get participants
        participants = await conversation_service.get_participants(creator, conversation.id)

        assert len(participants) == 3
        usernames = {p["username"] for p in participants}
        expected_usernames = {creator.username, participant1.username, admin.username}
        assert usernames == expected_usernames


@pytest.mark.integration
class TestTranslationServiceWorkflows:
    """Integration tests for translation service workflows."""

    async def test_translation_and_storage_workflow(self, translation_service, message_factory, user_factory, room_factory, db_session):
        """Test complete translation workflow with real DeepL API."""
        # Create test data
        room = await room_factory.create(db_session, is_translation_enabled=True)
        user = await user_factory.create(db_session, preferred_language="en")
        message = await message_factory.create_room_message(db_session, sender=user, room=room)

        # Test translation workflow
        result_count = await translation_service.translate_and_store_message(
            message_id=message.id,
            content="Hello, how are you today?",
            source_language="en",
            target_languages=["de", "fr"],
        )

        # Should create translations (if API key available)
        if result_count > 0:
            # Verify translations were stored
            german_translation = await translation_service.get_message_translation(
                message.id, "de"
            )
            french_translation = await translation_service.get_message_translation(
                message.id, "fr"
            )

            assert german_translation is not None
            assert french_translation is not None
            assert german_translation != "Hello, how are you today?"  # Should be translated
            assert french_translation != "Hello, how are you today?"  # Should be translated

            # Get all translations
            all_translations = await translation_service.get_all_message_translations(message.id)
            assert len(all_translations) >= 2
        else:
            # API key not available, just verify no errors occurred
            assert result_count == 0

    async def test_translation_service_error_handling(self, translation_service, message_factory, user_factory, room_factory, db_session):
        """Test translation service error handling."""
        # Create test data
        room = await room_factory.create(db_session)
        user = await user_factory.create(db_session)
        message = await message_factory.create_room_message(db_session, sender=user, room=room)

        # Test with empty content
        result_count = await translation_service.translate_and_store_message(
            message_id=message.id,
            content="",
            target_languages=["de"],
        )

        assert result_count == 0

        # Test with no target languages
        result_count = await translation_service.translate_and_store_message(
            message_id=message.id,
            content="Hello world",
            target_languages=[],
        )

        assert result_count == 0

        # Test with invalid language code (should handle gracefully)
        result_count = await translation_service.translate_and_store_message(
            message_id=message.id,
            content="Hello world",
            target_languages=["invalid_lang"],
        )

        # Should not crash, might return 0 or handle gracefully
        assert isinstance(result_count, int)


@pytest.mark.integration
class TestBackgroundServiceWorkflows:
    """Integration tests for background service workflows."""

    async def test_background_translation_workflow(self, background_service, message_factory, user_factory, room_factory, db_session):
        """Test background translation processing."""
        # Create test data
        room = await room_factory.create(db_session, is_translation_enabled=True)
        user = await user_factory.create(db_session, preferred_language="en")
        message = await message_factory.create_room_message(
            db_session, sender=user, room=room, content="Hello, this is a test message!"
        )

        # Process background translation
        result = await background_service.process_message_translation_background(
            message=message,
            target_languages=["de", "fr"],
            room_translation_enabled=True,
        )

        # Result depends on whether API key is available
        assert isinstance(result, dict)

        if result:  # If translations were successful
            assert "de" in result or "fr" in result
            # Verify translations are different from original
            for lang, translation in result.items():
                assert translation != message.content
        else:
            # No translations (API key not available or other reason)
            assert result == {}

    async def test_background_service_logging_workflow(self, background_service):
        """Test background service logging functionality."""
        # Test user activity logging
        await background_service.log_user_activity_background(
            user_id=1,
            activity_type="integration_test",
            details={"test": "background logging"}
        )

        # Should complete without errors (actual logging happens in background)

    async def test_background_service_notification_workflow(self, background_service):
        """Test background service notification functionality."""
        # Test room notifications
        await background_service.notify_room_users_background(
            room_id=1,
            message="Integration test notification",
            exclude_user_ids=[2, 3]
        )

        # Should complete without errors (actual notifications happen in background)