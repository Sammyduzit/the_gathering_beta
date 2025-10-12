from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis

from app.core.auth_dependencies import get_current_active_user
from app.core.auth_utils import hash_password, verify_password
from app.core.config import settings
from app.core.constants import SECONDS_PER_DAY, SECONDS_PER_MINUTE
from app.core.cookie_utils import clear_auth_cookies, generate_csrf_token, set_auth_cookies
from app.core.jwt_utils import create_access_token, create_refresh_token, verify_token
from app.core.redis_client import get_redis
from app.core.validators import validate_language_code
from app.models import User
from app.repositories.repository_dependencies import get_user_repository
from app.repositories.user_repository import IUserRepository
from app.schemas.auth_schemas import Token, UserLogin, UserRegister, UserResponse, UserUpdate
from app.services.avatar_service import generate_avatar_url

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserRegister, user_repo: IUserRepository = Depends(get_user_repository)):
    """
    Register a new user.
    :param user_data: New user data
    :param user_repo: User Repository instance
    :return: Created user object
    """

    if await user_repo.email_exists(user_data.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    if await user_repo.username_exists(user_data.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    hashed_password = hash_password(user_data.password)
    avatar_url = await generate_avatar_url(user_data.username)

    new_user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=hashed_password,
        avatar_url=avatar_url,
    )

    created_user = await user_repo.create(new_user)

    return created_user


@router.post("/login", response_model=Token)
async def login_user(
    response: Response,
    user_credentials: UserLogin,
    user_repo: IUserRepository = Depends(get_user_repository),
    redis: Redis = Depends(get_redis),
):
    """
    Login user and set HttpOnly cookies (access + refresh + CSRF).

    Sets three cookies for secure authentication:
    - tg_access: Short-lived access token (HttpOnly)
    - tg_refresh: Long-lived refresh token (HttpOnly)
    - tg_csrf: CSRF token (readable by JavaScript for header injection)

    Also returns token in JSON response for backward compatibility with existing clients.

    :param response: FastAPI Response object for setting cookies
    :param user_credentials: User login credentials
    :param user_repo: User Repository instance
    :param redis: Redis client for refresh token tracking
    :return: JWT token object (use cookies instead for production)
    """
    # Validate credentials
    user = await user_repo.get_by_email(user_credentials.email)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive")

    # Generate tokens
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)

    refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)
    refresh_token = create_refresh_token(data={"sub": user.username}, expires_delta=refresh_token_expires)

    # Generate CSRF token
    csrf_token = generate_csrf_token()

    # Store refresh token in Redis (for revocation capability)
    refresh_payload = verify_token(refresh_token)
    refresh_jti = refresh_payload["jti"]

    redis_key = f"refresh_token:{user.id}:{refresh_jti}"
    await redis.setex(
        redis_key,
        settings.refresh_token_expire_days * SECONDS_PER_DAY,
        csrf_token,  # Store CSRF with refresh token for validation
    )

    # Set authentication cookies
    set_auth_cookies(response, access_token, refresh_token, csrf_token)

    # JSON response (for backward compatibility, but production apps should use cookies)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * SECONDS_PER_MINUTE,
    }


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    request: Request,
    response: Response,
    user_repo: IUserRepository = Depends(get_user_repository),
    redis: Redis = Depends(get_redis),
):
    """
    Refresh access token using refresh token from HttpOnly cookie.

    This endpoint does NOT require CSRF validation (read-only operation).
    Uses refresh token to generate a new access token without requiring re-authentication.

    :param request: FastAPI Request object for reading cookies
    :param response: FastAPI Response object for updating access token cookie
    :param user_repo: User Repository instance
    :param redis: Redis client for refresh token validation
    :return: New access token
    """
    # Get refresh token from HttpOnly cookie
    refresh_token = request.cookies.get("tg_refresh")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing. Please log in again.",
        )

    # Verify and decode refresh token
    try:
        payload = verify_token(refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token. Please log in again.",
        )

    # Validate token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Expected refresh token.",
        )

    username = payload.get("sub")
    refresh_jti = payload.get("jti")

    # Verify user still exists
    user = await user_repo.get_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please log in again.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
        )

    # Check if refresh token is revoked (Redis lookup)
    redis_key = f"refresh_token:{user.id}:{refresh_jti}"
    csrf_token = await redis.get(redis_key)

    if not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked. Please log in again.",
        )

    # Generate new access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    new_access_token = create_access_token(data={"sub": username}, expires_delta=access_token_expires)

    # Update access token cookie only (refresh token and CSRF remain unchanged)
    response.set_cookie(
        key="tg_access",
        value=new_access_token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * SECONDS_PER_MINUTE,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * SECONDS_PER_MINUTE,
    }


@router.post("/logout")
async def logout_user(
    request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
):
    """
    Logout user by invalidating cookies and revoking refresh token.

    Performs three actions:
    1. Retrieves refresh token from cookie
    2. Deletes refresh token from Redis (revocation)
    3. Clears all auth cookies

    Requires authentication to prevent unauthorized logout attacks.

    :param request: FastAPI Request object for reading cookies
    :param response: FastAPI Response object for clearing cookies
    :param redis: Redis client for token revocation
    :param current_user: Current authenticated user
    :return: Logout confirmation message
    """
    # Get refresh token for revocation
    refresh_token = request.cookies.get("tg_refresh")

    if refresh_token:
        try:
            payload = verify_token(refresh_token)
            refresh_jti = payload.get("jti")

            # Delete from Redis (revoke refresh token)
            redis_key = f"refresh_token:{current_user.id}:{refresh_jti}"
            await redis.delete(redis_key)

        except Exception:
            # Continue with logout even if revocation fails
            # (token might be already expired or invalid)
            pass

    # Clear all auth cookies
    clear_auth_cookies(response)

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current user info.
    :param current_user: Current authenticated user
    :return: User information
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_user_preferences(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    user_repo: IUserRepository = Depends(get_user_repository),
):
    """
    Update current user preferences.
    :param user_update: User update data
    :param current_user: Current authenticated user
    :param user_repo: User Repository instance
    :return: Updated user object
    """
    if user_update.username:
        if await user_repo.username_exists(user_update.username):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
        current_user.username = user_update.username

    if user_update.preferred_language:
        if not validate_language_code(user_update.preferred_language):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported language code: {user_update.preferred_language}",
            )
        current_user.preferred_language = user_update.preferred_language.lower()

    updated_user = await user_repo.update(current_user)
    return updated_user
