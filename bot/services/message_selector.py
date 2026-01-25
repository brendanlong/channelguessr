"""Service for selecting random messages from guild history."""

import discord
import logging
import random
import re
import time
from typing import Optional

from config import Config
from utils.snowflake import timestamp_ms_to_snowflake

logger = logging.getLogger(__name__)

# URL pattern for detecting links
URL_PATTERN = re.compile(r"https?://\S+")


def is_interesting_message(message: discord.Message) -> bool:
    """Check if a message is interesting enough for the game.

    A message is interesting if it has ANY of:
    - 200+ characters of text
    - Attachments (images, files)
    - Embeds
    - URLs in content
    """
    # Skip bot messages
    if message.author.bot:
        return False

    # Check message length
    if len(message.content) >= Config.MIN_MESSAGE_LENGTH:
        return True

    # Check for attachments (images, videos, files)
    if message.attachments:
        return True

    # Check for embeds
    if message.embeds:
        return True

    # Check for URLs
    if URL_PATTERN.search(message.content):
        return True

    return False


class MessageSelector:
    """Service for selecting random messages from guild history."""

    async def select_random_message(
        self, guild: discord.Guild
    ) -> Optional[tuple[discord.Message, discord.TextChannel]]:
        """Select a random interesting message from the guild's history.

        Returns a tuple of (message, channel) if found, or None if no
        suitable message could be found after all retries.
        """
        # Get list of text channels the bot can read
        readable_channels = self._get_readable_channels(guild)

        if not readable_channels:
            logger.warning(f"No readable text channels in guild {guild.id}")
            return None

        # Calculate time bounds
        now_ms = int(time.time() * 1000)
        min_age_ms = Config.MIN_MESSAGE_AGE_HOURS * 60 * 60 * 1000
        max_timestamp_ms = now_ms - min_age_ms
        min_timestamp_ms = now_ms - (Config.LOOKBACK_DAYS * 24 * 60 * 60 * 1000)

        for attempt in range(Config.MAX_SEARCH_RETRIES):
            # Pick a random channel
            channel = random.choice(readable_channels)

            # Generate random timestamp in range
            random_timestamp_ms = random.randint(min_timestamp_ms, max_timestamp_ms)
            after_snowflake = timestamp_ms_to_snowflake(random_timestamp_ms)

            logger.info(
                f"Message search attempt {attempt + 1}/{Config.MAX_SEARCH_RETRIES}: "
                f"checking #{channel.name}..."
            )

            try:
                # Fetch messages starting from the random point
                messages = []
                async for msg in channel.history(
                    after=discord.Object(id=after_snowflake),
                    limit=Config.MESSAGE_SEARCH_LIMIT,
                    oldest_first=True,
                ):
                    messages.append(msg)

                # If we got very few messages, this channel/time is too sparse
                if len(messages) < 5:
                    logger.info(
                        f"Channel #{channel.name} too sparse at this time "
                        f"({len(messages)} messages found), retrying..."
                    )
                    continue

                # Find the first interesting message
                for msg in messages:
                    if is_interesting_message(msg):
                        logger.info(
                            f"Selected message {msg.id} from #{channel.name} "
                            f"on attempt {attempt + 1}"
                        )
                        return (msg, channel)

                logger.info(
                    f"No interesting messages in batch of {len(messages)} from #{channel.name}, retrying..."
                )

            except discord.Forbidden:
                logger.warning(f"Lost permission to read channel #{channel.name}")
                readable_channels.remove(channel)
                if not readable_channels:
                    logger.warning("No more readable channels left")
                    return None
            except discord.HTTPException as e:
                logger.warning(f"HTTP error fetching history: {e}")
                continue

        logger.warning(
            f"Failed to find interesting message after {Config.MAX_SEARCH_RETRIES} attempts"
        )
        return None

    def _get_readable_channels(
        self, guild: discord.Guild
    ) -> list[discord.TextChannel]:
        """Get list of text channels the bot can read."""
        readable = []
        for channel in guild.text_channels:
            permissions = channel.permissions_for(guild.me)
            if permissions.read_messages and permissions.read_message_history:
                readable.append(channel)
        return readable
