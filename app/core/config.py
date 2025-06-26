from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    database_url: str = "postgresql+psycopg2://dev:password@localhost:5432/thegathering"

    secret_key: str = "super-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    app_name: str = "The Gathering API"
    debug: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


settings = Settings()
