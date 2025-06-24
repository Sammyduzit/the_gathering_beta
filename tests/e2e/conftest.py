import os
import pytest
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.core.database import get_db, Base
from app.models.user import User
from app.models.room import Room
from app.core.auth_utils import hash_password


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create new database session for E2E tests."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client for E2E tests."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def created_user(db_session, sample_user_data):
    """Create a user in database for E2E tests."""
    user = User(
        email=sample_user_data["email"],
        username=sample_user_data["username"],
        password_hash=hash_password(sample_user_data["password"]),
        is_admin=False,
        last_active=datetime.now()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def created_admin(db_session, sample_admin_data):
    """Create an admin in database for E2E tests."""
    admin = User(
        email=sample_admin_data["email"],
        username=sample_admin_data["username"],
        password_hash=hash_password(sample_admin_data["password"]),
        is_admin=True,
        last_active=datetime.now()
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def created_room(db_session, sample_room_data):
    """Create a room in database for E2E tests."""
    room = Room(
        name=sample_room_data["name"],
        description=sample_room_data["description"],
        max_users=sample_room_data["max_users"],
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


@pytest.fixture
def authenticated_user_headers(client, sample_user_data, created_user):
    """Return headers with JWT token for authenticated user requests."""
    login_response = client.post("/api/v1/auth/login", json={
        "email": sample_user_data["email"],
        "password": sample_user_data["password"]
    })
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authenticated_admin_headers(client, sample_admin_data, created_admin):
    """Return headers with JWT token for authenticated admin requests."""
    login_response = client.post("/api/v1/auth/login", json={
        "email": sample_admin_data["email"],
        "password": sample_admin_data["password"]
    })
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}