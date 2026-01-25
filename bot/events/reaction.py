"""Reaction event handlers for updating interest scores."""

import discord
from discord.ext import commands
import logging

from config import Config
from bot.events.message import InterestFlags

logger = logging.getLogger(__name__)


class ReactionEvents(commands.Cog):
    """Cog for handling reaction events."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Update interest score when messages get reactions."""
        # Skip DMs
        if not reaction.message.guild:
            return

        # Check if reaction count meets threshold
        if reaction.count >= Config.MIN_REACTIONS:
            db = self.bot.db
            await db.update_interest_score(
                message_id=str(reaction.message.id),
                additional_flags=InterestFlags.REACTIONS,
            )
            logger.debug(
                f"Updated interest score for message {reaction.message.id} "
                f"(reactions: {reaction.count})"
            )


async def setup(bot: commands.Bot):
    """Load the cog."""
    await bot.add_cog(ReactionEvents(bot))
