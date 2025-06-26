import pytest


@pytest.fixture
def sample_user_data():
    """Standard user registration data."""
    return {
        "email": "user@example.com",
        "username": "testuser",
        "password": "password123",
    }


@pytest.fixture
def sample_admin_data():
    """Standard admin registration data."""
    return {
        "email": "admin@example.com",
        "username": "testadmin",
        "password": "adminpass123",
    }


@pytest.fixture
def sample_room_data():
    """Standard room creation data."""
    return {"name": "Test Room", "description": "A test room", "max_users": 5}
