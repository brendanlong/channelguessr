import os
from dotenv import load_dotenv

load_dotenv()


def _get_int(key: str, default: int) -> int:
    """Get an integer from environment, falling back to default."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Config:
    # Discord
    DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

    # Database
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "channelguessr.db")

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

    # Game settings
    ROUND_TIMEOUT_SECONDS = _get_int("ROUND_TIMEOUT_SECONDS", 60)
    CONTEXT_MESSAGES = _get_int("CONTEXT_MESSAGES", 5)
    MIN_MESSAGE_AGE_HOURS = _get_int("MIN_MESSAGE_AGE_HOURS", 24)

    # Message search settings
    MESSAGE_SEARCH_LIMIT = _get_int("MESSAGE_SEARCH_LIMIT", 100)
    MAX_SEARCH_RETRIES = _get_int("MAX_SEARCH_RETRIES", 5)
    LOOKBACK_DAYS = _get_int("LOOKBACK_DAYS", 365)

    # Message filtering
    MIN_MESSAGE_LENGTH = _get_int("MIN_MESSAGE_LENGTH", 200)

    # Scoring
    CHANNEL_SCORE = _get_int("CHANNEL_SCORE", 500)
    TIME_MAX_SCORE = _get_int("TIME_MAX_SCORE", 500)
    AUTHOR_SCORE = _get_int("AUTHOR_SCORE", 500)
