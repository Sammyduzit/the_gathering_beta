"""
Global test configuration and fixtures.

This module contains only global fixtures that are shared across all test types.
Test-specific fixtures are located in their respective conftest.py files:
- tests/unit/conftest.py - Unit test fixtures with SQLite + mocks
- tests/integration/conftest.py - Integration test fixtures with PostgreSQL
- tests/e2e/conftest.py - E2E test fixtures with PostgreSQL + FastAPI
"""

import pytest


# Global sample data fixtures (no database dependencies)
@pytest.fixture
def sample_user_data():
    """Standard user registration data for API testing."""
    return {
        "email": "user@example.com",
        "username": "testuser",
        "password": "password123",
    }


@pytest.fixture
def sample_admin_data():
    """Standard admin registration data for API testing."""
    return {
        "email": "admin@example.com",
        "username": "testadmin",
        "password": "adminpass123",
    }


@pytest.fixture
def sample_room_data():
    """Standard room creation data for API testing."""
    return {
        "name": "Test Room",
        "description": "A test room for testing purposes",
        "max_users": 10
    }


@pytest.fixture
def sample_message_data():
    """Standard message data for API testing."""
    return {
        "content": "Test message content for testing purposes"
    }


@pytest.fixture
def sample_conversation_data():
    """Standard conversation data for API testing."""
    return {
        "conversation_type": "PRIVATE",
        "max_participants": 2
    }


# Configuration fixtures
@pytest.fixture(scope="session")
def test_config():
    """Global test configuration."""
    return {
        "test_database_prefix": "test_",
        "max_test_duration": 300,  # 5 minutes
        "cleanup_on_failure": True,
        "log_level": "INFO",
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests with mocked dependencies (fast)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests with real database (medium)"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests with full API (slow)"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take longer to run"
    )
    config.addinivalue_line(
        "markers", "ci: Tests for CI environment"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on their location."""
    for item in items:
        # Auto-mark based on test location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)

        # Auto-mark async tests
        if "async" in item.name or hasattr(item.obj, "__wrapped__"):
            item.add_marker(pytest.mark.asyncio)
