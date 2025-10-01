"""
Test fixtures and utilities for The Gathering test suite.

This module provides a clean, consistent foundation for all test types:
- Unit tests: Fast, isolated, mocked dependencies
- Integration tests: Real services with PostgreSQL
- E2E tests: Full API testing with PostgreSQL

Architecture follows the test pyramid with clear separation of concerns.
"""

from .factories import UserFactory, RoomFactory, MessageFactory, ConversationFactory

__all__ = [
    "UserFactory",
    "RoomFactory",
    "MessageFactory",
    "ConversationFactory",
]