from fastapi import APIRouter, Depends, HTTPException, status
from datetime import timedelta

from app.models import User
from app.schemas.auth_schemas import UserResponse, UserRegister, UserLogin
from app.core.auth_utils import hash_password, verify_password
from app.core.jwt_utils import create_access_token
from app.core.auth_dependencies import get_current_active_user
from app.core.config import settings
from app.schemas.auth_schemas import Token
from app.services.avatar_service import generate_avatar_url

from app.repositories.user_repository import IUserRepository
from app.repositories.repository_dependencies import get_user_repository

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(
    user_data: UserRegister, user_repo: IUserRepository = Depends(get_user_repository)
):
    """
    Register a new user.
    :param user_data: New user data
    :param user_repo: User Repository instance
    :return: Created user object
    """

    if user_repo.email_exists(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    if user_repo.username_exists(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    hashed_password = hash_password(user_data.password)
    avatar_url = generate_avatar_url(user_data.username)

    new_user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=hashed_password,
        avatar_url=avatar_url,
    )

    created_user = user_repo.create(new_user)

    return created_user


@router.post("/login", response_model=Token)
async def login_user(
    user_credentials: UserLogin,
    user_repo: IUserRepository = Depends(get_user_repository),
):
    """
    Login user and return JWT token.
    :param user_credentials: User login credentials
    :param user_repo: User Repository instance
    :return: JWT token object
    """
    user = user_repo.get_by_email(user_credentials.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    if not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive"
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current user info.
    :param current_user: Current authenticated user
    :return: User information
    """
    return current_user
