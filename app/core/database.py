from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker


from app.core.config import settings


engine = create_engine(
    settings.database_url, pool_pre_ping=True, pool_recycle=3600, echo=settings.debug
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    print("All tables created")


def drop_tables():
    """Drop all database tables"""
    try:
        Base.metadata.drop_all(bind=engine, checkfirst=True)
    except (IntegrityError, OperationalError) as e:
        print(f"FK constraint issue, using reflect method: {e}")
        Base.metadata.reflect(bind=engine)
        Base.metadata.drop_all(bind=engine)

    print("All tables dropped")
