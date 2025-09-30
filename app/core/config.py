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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")


settings = Settings()
