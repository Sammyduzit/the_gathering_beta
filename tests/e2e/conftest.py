import os
import pytest
from datetime import datetime

if not os.getenv("CI"):
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.core.database import get_db, Base
from app.models.user import User
from app.models.room import Room
from app.core.auth_utils import hash_password
from app.repositories.repository_dependencies import (
    get_user_repository,
    get_room_repository,
    get_conversation_repository,
    get_message_repository,
)
from app.repositories.user_repository import UserRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository

from app.services.service_dependencies import get_room_service, get_conversation_service
from app.services.room_service import RoomService
from app.services.conversation_service import ConversationService
from app.services.translation_service import TranslationService


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///:memory:")
print(f"Test Database URL: {DATABASE_URL}")

if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    print("Using SQLite engine configuration")
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
    print("Using PostgreSQL engine configuration")


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Activate Foreign Key Constraints for SQLite connections."""
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        print("SQLite Foreign Key Constraints aktiviert")


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

    def override_user_repository():
        return UserRepository(db_session)

    def override_room_repository():
        return RoomRepository(db_session)

    def override_conversation_repository():
        return ConversationRepository(db_session)

    def override_message_repository():
        return MessageRepository(db_session)

    def override_room_service():
        return RoomService(
            room_repo=RoomRepository(db_session),
            user_repo=UserRepository(db_session),
            message_repo=MessageRepository(db_session),
            conversation_repo=ConversationRepository(db_session),
            translation_service=TranslationService(MessageRepository(db_session)),
        )

    def override_conversation_service():
        return ConversationService(
            conversation_repo=ConversationRepository(db_session),
            message_repo=MessageRepository(db_session),
            user_repo=UserRepository(db_session),
            translation_service=TranslationService(MessageRepository(db_session)),
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_user_repository
    app.dependency_overrides[get_room_repository] = override_room_repository
    app.dependency_overrides[get_conversation_repository] = (
        override_conversation_repository
    )
    app.dependency_overrides[get_message_repository] = override_message_repository
    app.dependency_overrides[get_room_service] = override_room_service
    app.dependency_overrides[get_conversation_service] = override_conversation_service

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
        last_active=datetime.now(),
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
        last_active=datetime.now(),
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
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        },
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authenticated_admin_headers(client, sample_admin_data, created_admin):
    """Return headers with JWT token for authenticated admin requests."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_admin_data["email"],
            "password": sample_admin_data["password"],
        },
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
