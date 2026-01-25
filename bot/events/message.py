"""Message event handlers for real-time indexing."""

import discord
from discord.ext import commands
import logging
import re

from config import Config
from utils.snowflake import snowflake_to_timestamp_ms

logger = logging.getLogger(__name__)


class InterestFlags:
    """Bitmask flags for why a message is interesting."""

    REACTIONS = 1 << 0  # 3+ reactions
    LONG_TEXT = 1 << 1  # 200+ chars
    HAS_IMAGE = 1 << 2  # Has attachment
    HAS_REPLIES = 1 << 3  # 2+ replies (not tracked in MVP)
    HAS_LINK = 1 << 4  # Contains URL


# URL pattern for detecting links
URL_PATTERN = re.compile(r"https?://\S+")


def calculate_interest_flags(message: discord.Message) -> int:
    """Calculate the interest flags for a message."""
    flags = 0

    # Check message length
    if len(message.content) >= Config.MIN_MESSAGE_LENGTH:
        flags |= InterestFlags.LONG_TEXT

    # Check for attachments (images, videos, files)
    if message.attachments:
        flags |= InterestFlags.HAS_IMAGE

    # Check for embeds
    if message.embeds:
        flags |= InterestFlags.HAS_IMAGE

    # Check for URLs
    if URL_PATTERN.search(message.content):
        flags |= InterestFlags.HAS_LINK

    return flags


class MessageEvents(commands.Cog):
    """Cog for handling message events and indexing."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Index interesting messages as they're posted."""
        # Skip DMs
        if not message.guild:
            return

        # Skip bot messages
        if message.author.bot:
            return

        # Skip empty messages
        if not message.content and not message.attachments and not message.embeds:
            return

        # Calculate interest flags
        interest_flags = calculate_interest_flags(message)

        # Only store if message has at least one interesting flag
        if not interest_flags:
            return

        # Store in database
        db = self.bot.db
        timestamp_ms = snowflake_to_timestamp_ms(message.id)

        success = await db.add_interesting_message(
            message_id=str(message.id),
            channel_id=str(message.channel.id),
            guild_id=str(message.guild.id),
            author_id=str(message.author.id),
            content=message.content,
            timestamp_ms=timestamp_ms,
            interest_score=interest_flags,
        )

        if success:
            logger.debug(
                f"Indexed message {message.id} in #{message.channel.name} "
                f"(flags: {interest_flags})"
            )


async def setup(bot: commands.Bot):
    """Load the cog."""
    await bot.add_cog(MessageEvents(bot))
