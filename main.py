from contextlib import asynccontextmanager
from fastapi import FastAPI
import os
import uvicorn

from app.core.config import settings
from app.core.database import create_tables, drop_tables
from app.api.v1.endpoints.conversation_router import router as conversation_router
from app.api.v1.endpoints.room_router import router as rooms_router
from app.api.v1.endpoints.auth_router import router as auth_router
from testing_setup import setup_complete_test_environment


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown.
    """
    print("Starting...")

    if os.getenv("RESET_DB") == "true":
        print("RESET_DB=true - Resetting database...")
        drop_tables()
        print("Database reset complete")

    create_tables()
    setup_complete_test_environment()
    print("Database tables created")
    yield
    print("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="Virtual meeting space with 3 type chat system",
    docs_url="/docs",
    lifespan=lifespan,
)

app.include_router(rooms_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(conversation_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "Welcome to The Gathering API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "rooms": "/api/v1/rooms",
            "room_health": "/api/v1/rooms/health/check",
        },
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/test")
def test_endpoint():
    return {"status": "FastAPI works!", "project": "The Gathering"}


if __name__ == "__main__":
    print("API Documentation: http://localhost:8000/docs")
    print("Room Endpoint: http://localhost:8000/api/v1/rooms")

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
