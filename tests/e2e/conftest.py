import os
from datetime import datetime

import pytest_asyncio

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

# E2E tests require PostgreSQL for production parity
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "E2E tests require DATABASE_URL environment variable with PostgreSQL.\n"
        "Please set DATABASE_URL or use 'docker-compose up -d db' for local development."
    )

# Ensure we're using PostgreSQL
if not DATABASE_URL.startswith(("postgresql://", "postgresql+asyncpg://")):
    raise RuntimeError(
        f"E2E tests require PostgreSQL, got: {DATABASE_URL}\n"
        "Unit tests use SQLite, E2E tests need PostgreSQL for production parity."
    )

print(f"E2E Test Database URL: {DATABASE_URL}")

# Convert PostgreSQL URL to async if needed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Optimized PostgreSQL configuration for testing
async_engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,  # Set to True for SQL debugging
    future=True,
    pool_size=5,
    max_overflow=10
)
print("Using async PostgreSQL engine configuration")


@pytest_asyncio.fixture(scope="session")
async def async_db_schema():
    """Create database schema once per test session."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def async_db_session(async_db_schema):
    """Create isolated database session for each test with transaction rollback."""
    # Create session maker for this test
    async_session_maker = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        # Start a transaction that we can rollback
        async with session.begin():
            yield session
            # Transaction is automatically rolled back at the end of the context


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
