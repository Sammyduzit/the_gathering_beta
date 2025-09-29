# SQLAlchemy Fixture Refactor Roadmap

## 🎯 Objective
Modernize test fixtures to use SQLAlchemy 2.0 eager loading best practices, eliminating lazy loading issues and improving code quality.

## 📋 Current Problem
- Manual attribute access to prevent lazy loading: `user_email = user.email`
- Generates `F841: unused variable` linting errors
- Not following SQLAlchemy 2.0 best practices
- Inconsistent pattern across fixtures

## ✅ Target Solution
Implement eager loading with `selectinload()` options at query time:

```python
# Before (problematic)
user_email = user.email  # F841 error
user_username = user.username  # F841 error
async_db_session.expunge(user)

# After (best practice)
user = await async_db_session.scalar(
    select(User)
    .options(selectinload(User.relationships))
    .where(User.id == user.id)
)
async_db_session.expunge(user)
```

## 🗺️ Implementation Roadmap

### Phase 1: Analysis & Preparation
- [ ] **1.1** Audit all current fixtures in `tests/e2e/conftest.py`
  - [ ] `created_user` fixture
  - [ ] `created_admin` fixture
  - [ ] `created_room` fixture
- [ ] **1.2** Identify all User/Room model attributes that need eager loading
- [ ] **1.3** Identify any relationships that should be loaded (if any)
- [ ] **1.4** Create helper patterns for consistent implementation

### Phase 2: Core Implementation
- [ ] **2.1** Refactor `created_user` fixture
  - [ ] Replace manual attribute access with eager loading query
  - [ ] Test all dependent test cases
  - [ ] Verify no lazy loading issues
- [ ] **2.2** Refactor `created_admin` fixture
  - [ ] Apply same pattern as user fixture
  - [ ] Ensure admin-specific attributes are loaded
- [ ] **2.3** Refactor `created_room` fixture
  - [ ] Load room-specific attributes eagerly
  - [ ] Handle room relationships if any

### Phase 3: Testing & Validation
- [ ] **3.1** Run complete test suite
  - [ ] Unit tests: `pytest tests/unit/ -v`
  - [ ] E2E tests: `pytest tests/e2e/ -v`
  - [ ] Coverage check: `pytest --cov=app`
- [ ] **3.2** Validate linting passes
  - [ ] `ruff check app/ tests/ main.py`
  - [ ] `ruff format --check app/ tests/ main.py`
- [ ] **3.3** Performance validation
  - [ ] Verify query count reduction
  - [ ] Check test execution times

### Phase 4: Documentation & Standardization
- [ ] **4.1** Update `CLAUDE.md` with new fixture pattern
- [ ] **4.2** Document eager loading best practices
- [ ] **4.3** Create fixture template for future use
- [ ] **4.4** Add comments explaining the pattern in code

### Phase 5: Cleanup & Finalization
- [ ] **5.1** Remove all unused variable assignments
- [ ] **5.2** Verify all `F841` linting errors are resolved
- [ ] **5.3** Final test suite run
- [ ] **5.4** Git commit with descriptive message

## 🔧 Technical Implementation Details

### Eager Loading Pattern
```python
@pytest_asyncio.fixture
async def created_user(async_db_session, sample_user_data):
    """Create a user in database for E2E tests with eager loading."""
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

    # Reload with eager loading of all attributes
    user = await async_db_session.scalar(
        select(User)
        .options(
            # Add relationship loading if needed:
            # selectinload(User.rooms),
            # selectinload(User.conversations)
        )
        .where(User.id == user.id)
    )

    print(f"✅ Created test user: {user.username} ({user.email})")
    async_db_session.expunge(user)
    return user
```

### Required Imports
```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload  # If relationships exist
```

## 📊 Success Metrics
- [ ] Zero `F841` linting errors
- [ ] All tests pass (35 unit + 18 e2e = 53 tests)
- [ ] No lazy loading `MissingGreenlet` errors
- [ ] Consistent pattern across all fixtures
- [ ] Improved code maintainability

## 🚨 Risk Mitigation
- **Backup Strategy**: Work on feature branch before merging
- **Testing**: Comprehensive test suite validation at each phase
- **Rollback Plan**: Git history allows reverting to previous patterns
- **Dependencies**: Ensure SQLAlchemy 2.0 features are properly imported

## 📚 References
- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Eager Loading Techniques](https://docs.sqlalchemy.org/en/20/orm/loading_techniques.html)
- [Session Expunge Best Practices](https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.expunge)

## 🔄 Estimated Timeline
- **Phase 1**: 30 minutes (Analysis)
- **Phase 2**: 45 minutes (Implementation)
- **Phase 3**: 30 minutes (Testing)
- **Phase 4**: 15 minutes (Documentation)
- **Phase 5**: 15 minutes (Cleanup)
- **Total**: ~2.5 hours

---
*Created: 2025-09-29*
*Last Updated: 2025-09-29*
*Status: Planning Phase*