import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Discord
    DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

    # Database
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "geoguessr.db")

    # Game settings
    ROUND_TIMEOUT_SECONDS = 60
    CONTEXT_MESSAGES = 5
    MIN_INTERESTING_MESSAGES = 10  # Minimum pool before game can start
    MIN_MESSAGE_AGE_HOURS = 24  # Exclude messages newer than this

    # Interest thresholds
    MIN_REACTIONS = 3
    MIN_MESSAGE_LENGTH = 200
    MIN_REPLIES = 2
