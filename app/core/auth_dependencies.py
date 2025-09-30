from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.jwt_utils import get_user_from_token
from app.models.user import User
from app.repositories.repository_dependencies import get_user_repository
from app.repositories.user_repository import IUserRepository

security = HTTPBearer(auto_error=False)


async def get_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Extract JWT token from Authorization header.
    :param credentials: HTTP authorization credentials
    :return: JWT token string
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


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


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user.
    :param current_user: Current user from token
    :return: Active user object
    """
    return current_user


async def get_current_admin_user(
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
