"""Game commands for Channelguessr."""

import contextlib
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands, ui
from discord.ext import commands

from config import Config
from utils.formatting import format_leaderboard, format_player_stats

if TYPE_CHECKING:
    from bot.main import ChannelguessrBot

logger = logging.getLogger(__name__)


class ClearDataConfirmView(ui.View):
    """Confirmation view for clearing user data."""

    def __init__(self, user_id: int, db):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.db = db
        self.confirmed = False

    @ui.button(label="Yes, delete my data", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This confirmation is not for you.", ephemeral=True)
            return

        self.confirmed = True
        self.stop()

        # Delete the data
        result = await self.db.delete_user_data(str(self.user_id))

        await interaction.response.edit_message(
            content=(
                f"Your data has been deleted:\n"
                f"- {result.guesses} guess(es) removed\n"
                f"- {result.scores} leaderboard entry/entries removed\n\n"
                f"This affects all servers where you played Channelguessr."
            ),
            view=None,
        )

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This confirmation is not for you.", ephemeral=True)
            return

        self.stop()
        await interaction.response.edit_message(content="Data deletion cancelled.", view=None)


class GameCommands(commands.Cog):
    """Cog containing all game commands."""

    bot: "ChannelguessrBot"

    def __init__(self, bot: "ChannelguessrBot"):
        self.bot = bot

    @app_commands.command(name="start", description="Start a new Channelguessr round")
    @app_commands.describe(
        context=f"Number of context messages to show before/after (default: {Config.CONTEXT_MESSAGES})",
        timeout=f"Round timeout in seconds (default: {Config.ROUND_TIMEOUT_SECONDS})",
    )
    async def start(
        self,
        interaction: discord.Interaction,
        context: app_commands.Range[int, 0, 20] | None = None,
        timeout: app_commands.Range[int, 10, 300] | None = None,
    ):
        """Start a new game round."""
        channel_name = getattr(interaction.channel, "name", "DM")
        logger.info(f"Start command invoked by {interaction.user} in #{channel_name}")
        await interaction.response.defer()

        if not interaction.guild or not self.bot.game_service:
            await interaction.followup.send("This command only works in servers.", ephemeral=True)
            return

        success, message = await self.bot.game_service.start_round(
            guild=interaction.guild,
            channel=interaction.channel,  # type: ignore[arg-type]
            context_messages=context,
            timeout_seconds=timeout,
        )

        if not success:
            await interaction.followup.send(message, ephemeral=True)
        else:
            # Game message is sent by the service
            await interaction.followup.send("Round started!", ephemeral=True)

    @app_commands.command(name="guess", description="Submit your guess for the current round")
    @app_commands.describe(
        channel="The channel you think the message is from",
        time="When you think the message was posted (e.g., 'March 2024', 'Jan 15 2023')",
        author="The user you think sent the message (+500 points if correct)",
    )
    async def guess(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        time: str,
        author: discord.Member,
    ):
        """Submit a guess for the current round."""
        logger.info(
            f"Guess command invoked by {interaction.user}: channel=#{channel.name}, time='{time}', author=@{author.name}"
        )
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not self.bot.game_service:
            await interaction.followup.send("This command only works in servers.", ephemeral=True)
            return

        success, message = await self.bot.game_service.submit_guess(
            guild=interaction.guild,
            channel=interaction.channel,  # type: ignore[arg-type]
            player=interaction.user,  # type: ignore[arg-type]
            guessed_channel=channel,
            guessed_time=time,
            guessed_author=author,
        )

        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(name="skip", description="Skip the current round (moderators only)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def skip(self, interaction: discord.Interaction):
        """Skip the current round."""
        channel_name = getattr(interaction.channel, "name", "DM")
        logger.info(f"Skip command invoked by {interaction.user} in #{channel_name}")
        await interaction.response.defer()

        if not interaction.guild or not self.bot.game_service:
            await interaction.followup.send("This command only works in servers.", ephemeral=True)
            return

        success, message = await self.bot.game_service.skip_round(
            guild=interaction.guild,
            channel=interaction.channel,  # type: ignore[arg-type]
        )

        await interaction.followup.send(message)

    @skip.error
    async def skip_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors for the skip command."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the 'Manage Messages' permission to skip rounds!",
                ephemeral=True,
            )
        else:
            logger.error(f"Error in skip command: {error}")
            await interaction.response.send_message("An error occurred while skipping the round.", ephemeral=True)

    @app_commands.command(name="leaderboard", description="Show the server leaderboard")
    @app_commands.describe(
        days="Only include scores from the last N days (e.g., 1 for today, 7 for last week, 30 for last month)",
        adjusted="Sort by average score per round instead of total score",
        public="Show the leaderboard to everyone in the channel instead of just you",
    )
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        days: app_commands.Range[int, 1, 365] | None = None,
        adjusted: bool = False,
        public: bool = False,
    ):
        """Show the server leaderboard."""
        await interaction.response.defer(ephemeral=not public)

        if not interaction.guild or not self.bot.db:
            await interaction.followup.send("This command only works in servers.", ephemeral=True)
            return

        players = await self.bot.db.get_leaderboard(str(interaction.guild.id), days=days)

        # Build the title based on options
        title_parts = []
        if days is not None:
            if days == 1:
                title_parts.append("Today's")
            elif days == 7:
                title_parts.append("Weekly")
            elif days == 30:
                title_parts.append("Monthly")
            else:
                title_parts.append(f"Last {days} Days")
        if adjusted:
            title_parts.append("Adjusted")
        title_parts.append("Leaderboard")
        title = " ".join(title_parts)

        message = await format_leaderboard(
            players=players,
            guild=interaction.guild,
            title=title,
            sort_by="average" if adjusted else "total",
        )

        await interaction.followup.send(message, ephemeral=not public)

    @app_commands.command(name="stats", description="Show your Channelguessr stats")
    @app_commands.describe(user="The user to show stats for (defaults to yourself)")
    async def stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):
        """Show player stats."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not self.bot.db:
            await interaction.followup.send("This command only works in servers.", ephemeral=True)
            return

        target_user = user or interaction.user
        guild_id = str(interaction.guild.id)
        player_id = str(target_user.id)

        stats = await self.bot.db.get_player_stats(guild_id, player_id)
        rank = await self.bot.db.get_player_rank(guild_id, player_id)

        message = format_player_stats(stats, target_user, rank)

        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(name="channelguessr", description="Show help for Channelguessr")
    async def help(self, interaction: discord.Interaction):
        """Show help information."""
        help_text = """
**Channelguessr**

A game where you guess which channel a message came from, when it was posted, and who sent it!

**How to Play:**
1. Use `/start` to begin a round
2. You'll see a mystery message with some context
3. Use `/guess` to submit your guess
4. After 60 seconds, the round ends and scores are revealed

**Scoring:**
- **Channel:** 500 points if correct
- **Time:** 500 points if within 1 day, scaling down to 0
- **Author:** 500 points if correct

**Commands:**
- `/start` - Start a new round
- `/guess <channel> <time> <author>` - Submit your guess
- `/skip` - Skip the current round (mods only)
- `/leaderboard` - View the leaderboard
- `/stats [user]` - View player stats
- `/cleardata` - Delete your data from all servers
"""
        await interaction.response.send_message(help_text, ephemeral=True)

    @app_commands.command(
        name="cleardata",
        description="Delete all your Channelguessr data from all servers",
    )
    async def cleardata(self, interaction: discord.Interaction):
        """Delete all user data with confirmation."""
        logger.info(f"Cleardata command invoked by {interaction.user}")

        view = ClearDataConfirmView(interaction.user.id, self.bot.db)

        await interaction.response.send_message(
            "**Are you sure you want to delete all your Channelguessr data?**\n\n"
            "This will permanently delete:\n"
            "- All your guesses from past rounds\n"
            "- Your leaderboard scores on all servers\n\n"
            "This action cannot be undone.",
            view=view,
            ephemeral=True,
        )

        # Handle timeout
        await view.wait()
        if not view.confirmed and not interaction.is_expired():
            with contextlib.suppress(discord.NotFound):
                await interaction.edit_original_response(content="Data deletion timed out.", view=None)


async def setup(bot: "ChannelguessrBot"):
    """Load the cog."""
    await bot.add_cog(GameCommands(bot))
