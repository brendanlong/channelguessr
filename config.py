"""Application configuration using pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Discord
    discord_token: str = Field(default="", alias="DISCORD_TOKEN")

    # Database
    database_path: str = Field(default="channelguessr.db", alias="DATABASE_PATH")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Game settings
    round_timeout_seconds: int = Field(default=60, alias="ROUND_TIMEOUT_SECONDS")
    context_messages: int = Field(default=5, alias="CONTEXT_MESSAGES")
    min_message_age_hours: int = Field(default=24, alias="MIN_MESSAGE_AGE_HOURS")

    # Message search settings
    message_search_limit: int = Field(default=100, alias="MESSAGE_SEARCH_LIMIT")
    max_search_retries: int = Field(default=5, alias="MAX_SEARCH_RETRIES")
    lookback_days: int = Field(default=365, alias="LOOKBACK_DAYS")

    # Message filtering
    min_message_length: int = Field(default=200, alias="MIN_MESSAGE_LENGTH")

    # Scoring
    channel_score: int = Field(default=500, alias="CHANNEL_SCORE")
    time_max_score: int = Field(default=500, alias="TIME_MAX_SCORE")
    author_score: int = Field(default=500, alias="AUTHOR_SCORE")


# Global settings instance
settings = Settings()


# Backwards compatibility - expose as Config class with uppercase attributes
class Config:
    """Backwards-compatible config interface."""

    DISCORD_TOKEN = settings.discord_token
    DATABASE_PATH = settings.database_path
    LOG_LEVEL = settings.log_level.upper()
    ROUND_TIMEOUT_SECONDS = settings.round_timeout_seconds
    CONTEXT_MESSAGES = settings.context_messages
    MIN_MESSAGE_AGE_HOURS = settings.min_message_age_hours
    MESSAGE_SEARCH_LIMIT = settings.message_search_limit
    MAX_SEARCH_RETRIES = settings.max_search_retries
    LOOKBACK_DAYS = settings.lookback_days
    MIN_MESSAGE_LENGTH = settings.min_message_length
    CHANNEL_SCORE = settings.channel_score
    TIME_MAX_SCORE = settings.time_max_score
    AUTHOR_SCORE = settings.author_score
