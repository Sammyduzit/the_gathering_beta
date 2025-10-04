import os
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.ai_router import router as ai_router
from app.api.v1.endpoints.auth_router import router as auth_router
from app.api.v1.endpoints.conversation_router import router as conversation_router
from app.api.v1.endpoints.room_router import router as rooms_router
from app.core.config import settings
from app.core.database import create_tables, drop_tables
from app.core.exceptions import (
    DomainException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from testing_setup import setup_complete_test_environment


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown.
    """
    print("Starting...")

    if os.getenv("RESET_DB") == "true":
        print("RESET_DB=true - Resetting database...")
        await drop_tables()
        print("Database reset complete")

    await create_tables()
    await setup_complete_test_environment()
    print("Database tables created")
    yield
    print("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="Virtual meeting space with 3 type chat system",
    docs_url="/docs",
    lifespan=lifespan,
)


# ============================================================================
# Exception Handlers (Convert Domain Exceptions → HTTP Responses)
# ============================================================================


@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    """Handle resource not found exceptions."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(UnauthorizedException)
async def unauthorized_exception_handler(request: Request, exc: UnauthorizedException) -> JSONResponse:
    """Handle authentication exceptions."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(ForbiddenException)
async def forbidden_exception_handler(request: Request, exc: ForbiddenException) -> JSONResponse:
    """Handle authorization exceptions."""
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException) -> JSONResponse:
    """Handle validation exceptions."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
    """Fallback handler for all other domain exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# ============================================================================
# Router Registration
# ============================================================================

API_V1_PREFIX = "/api/v1"

app.include_router(rooms_router, prefix=API_V1_PREFIX)
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(conversation_router, prefix=API_V1_PREFIX)
app.include_router(ai_router, prefix=API_V1_PREFIX)


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
def endpoint_test():
    return {"status": "FastAPI works!", "project": "The Gathering"}


if __name__ == "__main__":
    print("API Documentation: http://localhost:8000/docs")
    print("Room Endpoint: http://localhost:8000/api/v1/rooms")
    print("Admin: admin@test.com / admin123456 \nUser:  user@test.com / user123456")

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
