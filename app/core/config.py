from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    database_url: str

    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    app_name: str
    debug: bool

    deepl_api_key: str
    openai_api_key: str | None = None

    redis_url: str
    ai_features_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @property
    def is_ai_available(self) -> bool:
        """Check if AI features can be enabled."""
        return self.ai_features_enabled and self.openai_api_key is not None


settings = Settings()
