from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime

from app.core.validators import SanitizedString


class UserRegister(BaseModel):
    """
    Schema for user registration.
    """

    email: EmailStr = Field(description="User email address")
    username: SanitizedString = Field(
        min_length=3, max_length=20, description="Username"
    )
    password: str = Field(min_length=8, description="Password")


class UserLogin(BaseModel):
    """
    Schema for user login.
    """

    email: EmailStr = Field(description="User email address")
    password: str = Field(min_length=8, description="Password")


class Token(BaseModel):
    """
    JWT Token response.
    """

    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration time")


class UserResponse(BaseModel):
    """
    User data response.
    """

    id: int
    email: EmailStr
    username: str
    avatar_url: str | None = None
    preferred_language: str | None = None
    is_active: bool
    is_admin: bool
    created_at: datetime
    current_room_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """
    Schema for Updating User information.
    """
    preferred_language: str | None = Field(None, description="Preferred language code (EN, DE, FR, etc.", min_length=2, max_length=5)

