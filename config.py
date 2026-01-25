import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Discord
    DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

    # Database
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "channelguessr.db")

    # Game settings
    ROUND_TIMEOUT_SECONDS = 60
    CONTEXT_MESSAGES = 5
    MIN_MESSAGE_AGE_HOURS = 24  # Exclude messages newer than this

    # Message search settings
    MESSAGE_SEARCH_LIMIT = 100  # Messages to fetch per API call
    MAX_SEARCH_RETRIES = 5  # How many channel/time combos to try
    LOOKBACK_DAYS = 365  # How far back to look for messages

    # Interest thresholds
    MIN_MESSAGE_LENGTH = 200
