import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.jwt_utils import get_user_from_token
from app.models.user import User
from app.repositories.repository_dependencies import get_user_repository
from app.repositories.user_repository import IUserRepository

logger = structlog.get_logger(__name__)

security = HTTPBearer(auto_error=False)


def get_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """
    Extract JWT token from HttpOnly cookie (primary) or Authorization header (fallback).

    Cookie-based authentication is the recommended approach for web applications.
    Header-based authentication is maintained for backward compatibility with:
    - API documentation tools (Swagger UI)
    - Development/testing tools (Postman, curl)
    - Mobile apps (if not using cookie-based auth)

    :param request: FastAPI Request object for reading cookies
    :param credentials: HTTP authorization credentials (optional fallback)
    :return: JWT token string
    """
    # Primary: HttpOnly Cookie
    token = request.cookies.get("tg_access")
    if token:
        return token

    # Fallback: Authorization Header (Swagger/Dev/Mobile)
    if credentials:
        logger.warning(
            "header_auth_used",
            path=request.url.path,
            user_agent=request.headers.get("user-agent", "unknown"),
            message="Header-based auth is deprecated for web clients. Use cookie-based login.",
        )
        return credentials.credentials

    # Neither cookie nor header present
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Use POST /api/v1/auth/login to obtain cookie.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: str = Depends(get_token),
    user_repo: IUserRepository = Depends(get_user_repository),
) -> User:
    """
    Get current authenticated user from JWT token.
    :param token: JWT token string
    :param user_repo: User repository instance
    :return: Current user object
    """
    username = get_user_from_token(token)

    user = await user_repo.get_by_username(username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User '{username}' not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user.
    :param current_user: Current user from token
    :return: Active user object
    """
    return current_user


def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get current user and verify admin status.
    :param current_user: Current authenticated user
    :return: Admin user object
    """

    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user
