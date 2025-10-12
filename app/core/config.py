from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import (
    DEFAULT_COOKIE_SAMESITE,
    DEFAULT_COOKIE_SECURE,
    DEFAULT_CSRF_TOKEN_LENGTH,
    DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS,
)


class Settings(BaseSettings):
    """Application settings"""

    database_url: str

    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int = DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS

    app_name: str
    debug: bool

    deepl_api_key: str
    openai_api_key: str | None = None

    redis_url: str
    ai_features_enabled: bool = True

    # Cookie Security Configuration
    cookie_domain: str | None = None
    cookie_secure: bool = DEFAULT_COOKIE_SECURE
    cookie_samesite: Literal["lax", "strict", "none"] = DEFAULT_COOKIE_SAMESITE

    # CSRF Configuration
    csrf_token_length: int = DEFAULT_CSRF_TOKEN_LENGTH

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @property
    def is_ai_available(self) -> bool:
        """Check if AI features can be enabled."""
        return self.ai_features_enabled and self.openai_api_key is not None


settings = Settings()
