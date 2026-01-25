"""Game commands for Channelguessr."""

import discord
from discord import app_commands
from discord.ext import commands
import logging

from utils.formatting import format_leaderboard, format_player_stats

logger = logging.getLogger(__name__)


class GameCommands(commands.Cog):
    """Cog containing all game commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    channelguessr_group = app_commands.Group(
        name="channelguessr",
        description="Channelguessr game commands",
    )

    @channelguessr_group.command(name="start", description="Start a new guessing round")
    async def start(self, interaction: discord.Interaction):
        """Start a new game round."""
        logger.info(f"Start command invoked by {interaction.user} in #{interaction.channel.name}")
        await interaction.response.defer()

        success, message = await self.bot.game_service.start_round(
            guild=interaction.guild,
            channel=interaction.channel,
        )

        if not success:
            await interaction.followup.send(message, ephemeral=True)
        else:
            # Game message is sent by the service
            await interaction.followup.send("Round started!", ephemeral=True)

    @channelguessr_group.command(
        name="guess", description="Submit your guess for the current round"
    )
    @app_commands.describe(
        channel="The channel you think the message is from",
        time="When you think the message was posted (e.g., 'March 2024', 'Jan 15 2023')",
        author="The user you think sent the message (optional, +500 points if correct)",
    )
    async def guess(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        time: str,
        author: discord.Member = None,
    ):
        """Submit a guess for the current round."""
        author_info = f", author=@{author.name}" if author else ""
        logger.info(f"Guess command invoked by {interaction.user}: channel=#{channel.name}, time='{time}'{author_info}")
        await interaction.response.defer(ephemeral=True)

        success, message = await self.bot.game_service.submit_guess(
            guild=interaction.guild,
            channel=interaction.channel,
            player=interaction.user,
            guessed_channel=channel,
            guessed_time=time,
            guessed_author=author,
        )

        await interaction.followup.send(message, ephemeral=True)

    @channelguessr_group.command(
        name="skip", description="Skip the current round (moderators only)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def skip(self, interaction: discord.Interaction):
        """Skip the current round."""
        logger.info(f"Skip command invoked by {interaction.user} in #{interaction.channel.name}")
        await interaction.response.defer()

        success, message = await self.bot.game_service.skip_round(
            guild=interaction.guild,
            channel=interaction.channel,
        )

        await interaction.followup.send(message)

    @skip.error
    async def skip_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Handle errors for the skip command."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the 'Manage Messages' permission to skip rounds!",
                ephemeral=True,
            )
        else:
            logger.error(f"Error in skip command: {error}")
            await interaction.response.send_message(
                "An error occurred while skipping the round.", ephemeral=True
            )

    @channelguessr_group.command(
        name="leaderboard", description="Show the server leaderboard"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        """Show the server leaderboard."""
        await interaction.response.defer(ephemeral=True)

        players = await self.bot.db.get_leaderboard(str(interaction.guild.id))
        players_list = [dict(row) for row in players]

        message = format_leaderboard(
            players=players_list,
            guild=interaction.guild,
            title="Leaderboard",
        )

        await interaction.followup.send(message, ephemeral=True)

    @channelguessr_group.command(name="stats", description="Show player stats")
    @app_commands.describe(user="The user to show stats for (defaults to yourself)")
    async def stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
    ):
        """Show player stats."""
        await interaction.response.defer(ephemeral=True)

        target_user = user or interaction.user
        guild_id = str(interaction.guild.id)
        player_id = str(target_user.id)

        stats = await self.bot.db.get_player_stats(guild_id, player_id)
        rank = await self.bot.db.get_player_rank(guild_id, player_id)

        stats_dict = dict(stats) if stats else None
        message = format_player_stats(stats_dict, target_user, rank)

        await interaction.followup.send(message, ephemeral=True)

    @channelguessr_group.command(name="help", description="Show help for the game")
    async def help(self, interaction: discord.Interaction):
        """Show help information."""
        help_text = """
**Channelguessr**

A game where you guess which channel a message came from, when it was posted, and who sent it!

**How to Play:**
1. Use `/channelguessr start` to begin a round
2. You'll see a mystery message with some context
3. Use `/channelguessr guess` to submit your guess
4. After 60 seconds, the round ends and scores are revealed

**Scoring:**
- **Channel:** 500 points if correct
- **Time:** 500 points if within 1 day, scaling down to 0
- **Author:** 500 points if correct (optional)

**Commands:**
- `/channelguessr start` - Start a new round
- `/channelguessr guess <channel> <time> [author]` - Submit your guess
- `/channelguessr skip` - Skip the current round (mods only)
- `/channelguessr leaderboard` - View the leaderboard
- `/channelguessr stats [user]` - View player stats
"""
        await interaction.response.send_message(help_text, ephemeral=True)


async def setup(bot: commands.Bot):
    """Load the cog."""
    await bot.add_cog(GameCommands(bot))
