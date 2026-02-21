"""Application configuration via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Slack
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    allowed_user_id: str = ""

    # Notion
    notion_api_key: str = ""
    notion_database_id: str = ""

    # Gemini
    gemini_api_key: str = ""

    # Scheduler
    scheduler_secret: str = ""

    # App
    environment: str = "development"
    log_level: str = "INFO"
    port: int = 8080


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings. Lazy initialization to avoid import-time errors."""
    return Settings()
