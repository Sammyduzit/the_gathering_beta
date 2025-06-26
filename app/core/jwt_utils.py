from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status

import jwt

from app.core.config import settings


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create JWT access token
    :param data: Data to encode
    :param expires_delta: Token expiration time
    :return: JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    encode_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )

    return encode_jwt


def verify_token(token: str) -> dict:
    """
    Verify and decode JWT token.
    :param token: JWT token string
    :return: Decoded token
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_user_from_token(token: str) -> str:
    """
    Extract username from JWT token.
    :param token: JWT token string
    :return: Username from token
    """
    payload = verify_token(token)
    username: str = payload.get("sub")

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return username
