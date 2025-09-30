# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
- `pytest tests/unit/ -v` - Run unit tests (fast, mocked dependencies, uses SQLite)
- `pytest tests/e2e/ -v` - Run end-to-end integration tests (requires PostgreSQL)
- `pytest --cov=app --cov-report=term-missing` - Run tests with coverage report
- `pytest -m unit` - Run only unit tests
- `pytest -m e2e` - Run only e2e tests

**E2E Test Requirements:**
- E2E tests require PostgreSQL for production parity
- Set `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/the_gathering_test`
- For local development: `docker compose up -d db` to start PostgreSQL
- Unit tests use SQLite in-memory for speed, E2E tests use PostgreSQL for realism

### Code Quality
- `ruff check app/ tests/ main.py` - Run linting checks
- `ruff format app/ tests/ main.py` - Format code
- `ruff format --check app/ tests/ main.py` - Check formatting without changes
- Configuration in `pyproject.toml` optimized for FastAPI projects

### Database Operations
- **Local Development**: `docker compose up -d db` - Start PostgreSQL for E2E tests
- **CI Environment**: PostgreSQL service automatically started
- Set `RESET_DB=true` environment variable to reset database on startup

### Running the Application
- `python main.py` - Start the FastAPI server on localhost:8000
- API docs available at `/docs`
- Health check at `/health`

## Architecture Overview

This is a FastAPI-based chat application called "The Gathering" with a three-tier messaging system supporting:
1. **Public room conversations** - Visible to all room members
2. **Private direct messages** - Between two users
3. **Group conversations** - Small circles within rooms

### Core Architecture Patterns

**Repository Pattern**: Clean separation between data access and business logic
- `app/repositories/` - Data access layer with interfaces
- `app/services/` - Business logic layer
- `app/api/` - API endpoints with dependency injection

**Database Design**:
- PostgreSQL with SQLAlchemy 2.0 ORM
- XOR constraints ensure message routing to exactly one conversation type
- Composite indexes optimize chat performance
- Translation support with DeepL API integration

### Key Components

**Models** (`app/models/`):
- `User` - Authentication with JWT, bcrypt password hashing
- `Room` - Chat spaces with admin permissions
- `Conversation` - Three types: PUBLIC_ROOM, PRIVATE_CHAT, GROUP_CHAT
- `Message` - Content with translation support
- `MessageTranslation` - Multi-language message storage

**Services** (`app/services/`):
- `RoomService` - Room management and public messaging
- `ConversationService` - Private and group chat logic
- `TranslationService` - DeepL API integration for message translation
- `AvatarService` - User avatar management
- `BackgroundService` - Async background task processing with retry logic

**Authentication**:
- JWT tokens with configurable expiration
- Dependency injection for auth requirements
- Role-based access (admin can create rooms)

## Configuration

Environment variables (`.env` file):
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT signing key
- `DEEPL_API_KEY` - Translation service API key
- `RESET_DB` - Set to "true" to reset database on startup

## Test Structure

- `tests/unit/` - Unit tests with mocked dependencies (marked with `@pytest.mark.unit`)
- `tests/e2e/` - Integration tests with real database (marked with `@pytest.mark.e2e`)
- `tests/async_conftest.py` - Async test fixtures with reusable mock services
- `conftest.py` - Shared test fixtures and database setup
- Test environment automatically creates sample users (admin, alice, carol)

### Mock Service Architecture

Unit tests use reusable mock service fixtures for better maintainability:

```python
@pytest_asyncio.fixture
async def mock_translation_service():
    """Reusable mock translation service for all service tests."""
    mock = AsyncMock()
    mock.translate_message_content.return_value = {}
    mock.get_message_translation.return_value = None
    mock.translate_and_store_message.return_value = 0
    return mock
```

### Test Fixture Best Practices (SQLAlchemy 2.0)

E2E test fixtures use SQLAlchemy 2.0 eager loading pattern to prevent lazy loading issues:

```python
@pytest_asyncio.fixture
async def created_user(async_db_session, sample_user_data):
    """Create a user using SQLAlchemy 2.0 eager loading best practice."""
    # Create user
    user = User(...)
    async_db_session.add(user)
    await async_db_session.commit()

    # Reload with eager loading of all attributes
    user = await async_db_session.scalar(
        select(User).where(User.id == user.id)
    )

    async_db_session.expunge(user)
    return user
```

**Key Benefits:**
- Prevents `MissingGreenlet` errors in async contexts
- Follows SQLAlchemy 2.0 documentation recommendations
- Eliminates need for manual attribute access
- Performance-optimized (single query reload)
- Clean, maintainable fixture code

## Database Schema Notes

- Three conversation types use XOR constraint ensuring messages route to exactly one type
- Composite indexes on (room_id, created_at) and (conversation_id, created_at) for performance
- Translation table links to original messages with language codes
- User status tracking (ONLINE, OFFLINE, AWAY)