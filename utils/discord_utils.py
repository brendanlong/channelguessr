"""Discord API utility helpers."""

import logging

import discord

logger = logging.getLogger(__name__)


async def get_or_fetch_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
    """Look up a guild member by ID, falling back to an API call if not cached."""
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            logger.warning(f"Failed to fetch member {user_id}")
    return member
