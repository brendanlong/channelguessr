"""Discord snowflake utilities.

Discord snowflakes are 64-bit IDs that encode a timestamp.
The timestamp is the number of milliseconds since Discord Epoch (2015-01-01T00:00:00.000Z).
"""

# Discord Epoch: January 1, 2015 00:00:00 UTC in milliseconds
DISCORD_EPOCH = 1420070400000


def snowflake_to_timestamp_ms(snowflake: int | str) -> int:
    """Convert a Discord snowflake to Unix timestamp in milliseconds."""
    snowflake = int(snowflake)
    # Timestamp is the first 42 bits of the snowflake
    discord_timestamp = snowflake >> 22
    return discord_timestamp + DISCORD_EPOCH


def timestamp_ms_to_snowflake(timestamp_ms: int) -> int:
    """Convert a Unix timestamp in milliseconds to a Discord snowflake.

    Note: This creates a snowflake with only the timestamp component.
    The other bits (worker ID, process ID, increment) are set to 0.
    """
    discord_timestamp = timestamp_ms - DISCORD_EPOCH
    return discord_timestamp << 22


def snowflake_to_datetime(snowflake: int | str):
    """Convert a Discord snowflake to a datetime object."""
    from datetime import datetime, timezone

    timestamp_ms = snowflake_to_timestamp_ms(snowflake)
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)


def format_timestamp(timestamp_ms: int, style: str = "f") -> str:
    """Format a timestamp for Discord display.

    Styles:
        t - Short time (16:20)
        T - Long time (16:20:30)
        d - Short date (20/04/2021)
        D - Long date (20 April 2021)
        f - Short date/time (20 April 2021 16:20) [default]
        F - Long date/time (Tuesday, 20 April 2021 16:20)
        R - Relative (2 months ago)
    """
    timestamp_seconds = timestamp_ms // 1000
    return f"<t:{timestamp_seconds}:{style}>"


def format_relative_time(timestamp_ms: int) -> str:
    """Format a timestamp as relative time (e.g., '2 months ago')."""
    return format_timestamp(timestamp_ms, "R")
