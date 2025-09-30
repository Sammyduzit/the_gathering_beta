import os
from datetime import datetime

import pytest_asyncio

if not os.getenv("CI"):
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.auth_utils import hash_password
from app.core.database import Base, get_db
from app.models.room import Room
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.message_translation_repository import MessageTranslationRepository
from app.repositories.repository_dependencies import (
    get_conversation_repository,
    get_message_repository,
    get_message_translation_repository,
    get_room_repository,
    get_user_repository,
)
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository
from app.services.conversation_service import ConversationService
from app.services.room_service import RoomService
from app.services.service_dependencies import (
    get_conversation_service,
    get_room_service,
    get_translation_service,
)
from app.services.translation_service import TranslationService
from main import app

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
print(f"Test Database URL: {DATABASE_URL}")

if "sqlite" in DATABASE_URL:
    async_engine = create_async_engine(DATABASE_URL, poolclass=StaticPool, echo=False)
    print("Using async SQLite engine configuration")
else:
    # Convert PostgreSQL URL to async if needed
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    async_engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
    print("Using async PostgreSQL engine configuration")


@event.listens_for(async_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Activate Foreign Key Constraints for SQLite connections."""
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        print("SQLite Foreign Key Constraints aktiviert")


async_testing_session_local = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def async_db_session():
    """Create new async database session for E2E tests."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_testing_session_local() as session:
        yield session

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def async_client(async_db_session):
    """Create async test client for E2E tests."""

    async def override_get_db():
        yield async_db_session

    def override_user_repository():
        return UserRepository(async_db_session)

    def override_room_repository():
        return RoomRepository(async_db_session)

    def override_conversation_repository():
        return ConversationRepository(async_db_session)

    def override_message_repository():
        return MessageRepository(async_db_session)

    def override_message_translation_repository():
        return MessageTranslationRepository(async_db_session)

    def override_translation_service():
        return TranslationService(
            message_repo=MessageRepository(async_db_session),
            translation_repo=MessageTranslationRepository(async_db_session),
        )

    def override_room_service():
        return RoomService(
            room_repo=RoomRepository(async_db_session),
            user_repo=UserRepository(async_db_session),
            message_repo=MessageRepository(async_db_session),
            conversation_repo=ConversationRepository(async_db_session),
            message_translation_repo=MessageTranslationRepository(async_db_session),
            translation_service=TranslationService(
                message_repo=MessageRepository(async_db_session),
                translation_repo=MessageTranslationRepository(async_db_session),
            ),
        )

    def override_conversation_service():
        return ConversationService(
            conversation_repo=ConversationRepository(async_db_session),
            message_repo=MessageRepository(async_db_session),
            user_repo=UserRepository(async_db_session),
            room_repo=RoomRepository(async_db_session),
            translation_service=TranslationService(
                message_repo=MessageRepository(async_db_session),
                translation_repo=MessageTranslationRepository(async_db_session),
            ),
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_user_repository
    app.dependency_overrides[get_room_repository] = override_room_repository
    app.dependency_overrides[get_conversation_repository] = override_conversation_repository
    app.dependency_overrides[get_message_repository] = override_message_repository
    app.dependency_overrides[get_message_translation_repository] = override_message_translation_repository
    app.dependency_overrides[get_translation_service] = override_translation_service
    app.dependency_overrides[get_room_service] = override_room_service
    app.dependency_overrides[get_conversation_service] = override_conversation_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as async_test_client:
        yield async_test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def created_user(async_db_session, sample_user_data):
    """Create a user in database for E2E tests using SQLAlchemy 2.0 eager loading."""
    # Create user
    user = User(
        email=sample_user_data["email"],
        username=sample_user_data["username"],
        password_hash=hash_password(sample_user_data["password"]),
        is_admin=False,
        last_active=datetime.now(),
    )
    async_db_session.add(user)
    await async_db_session.commit()

    # Reload with eager loading of all attributes (SQLAlchemy 2.0 best practice)
    user = await async_db_session.scalar(select(User).where(User.id == user.id))

    async_db_session.expunge(user)
    return user


@pytest_asyncio.fixture
async def created_admin(async_db_session, sample_admin_data):
    """Create an admin in database for E2E tests using SQLAlchemy 2.0 eager loading."""
    # Create admin
    admin = User(
        email=sample_admin_data["email"],
        username=sample_admin_data["username"],
        password_hash=hash_password(sample_admin_data["password"]),
        is_admin=True,
        last_active=datetime.now(),
    )
    async_db_session.add(admin)
    await async_db_session.commit()

    # Reload with eager loading of all attributes (SQLAlchemy 2.0 best practice)
    admin = await async_db_session.scalar(select(User).where(User.id == admin.id))

    async_db_session.expunge(admin)
    return admin


@pytest_asyncio.fixture
async def created_room(async_db_session, sample_room_data):
    """Create a room in database for E2E tests using SQLAlchemy 2.0 eager loading."""
    # Create room
    room = Room(
        name=sample_room_data["name"],
        description=sample_room_data["description"],
        max_users=sample_room_data["max_users"],
    )
    async_db_session.add(room)
    await async_db_session.commit()

    # Reload with eager loading of all attributes (SQLAlchemy 2.0 best practice)
    room = await async_db_session.scalar(select(Room).where(Room.id == room.id))

    async_db_session.expunge(room)
    return room


@pytest_asyncio.fixture
async def authenticated_user_headers(async_client, sample_user_data, created_user):
    """Return headers with JWT token for authenticated user requests."""
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        },
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def authenticated_admin_headers(async_client, sample_admin_data, created_admin):
    """Return headers with JWT token for authenticated admin requests."""
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_admin_data["email"],
            "password": sample_admin_data["password"],
        },
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
