"""
Test fixtures and utilities for The Gathering test suite.

This module provides a clean, consistent foundation for all test types:
- Unit tests: Fast, isolated, mocked dependencies
- Integration tests: Real services with PostgreSQL
- E2E tests: Full API testing with PostgreSQL

Architecture follows the test pyramid with clear separation of concerns.
"""

from .database import DatabaseStrategy, create_test_engine, create_test_session
from .factories import UserFactory, RoomFactory, MessageFactory, ConversationFactory
from .mocks import MockRepositories, MockServices, create_mock_dependencies

__all__ = [
    "DatabaseStrategy",
    "create_test_engine",
    "create_test_session",
    "UserFactory",
    "RoomFactory",
    "MessageFactory",
    "ConversationFactory",
    "MockRepositories",
    "MockServices",
    "create_mock_dependencies",
]