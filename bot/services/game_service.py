"""Game service for managing game rounds."""

import discord
from discord.ext import commands
import asyncio
import logging
from typing import Optional

from config import Config
from db.database import Database
from utils.snowflake import snowflake_to_timestamp_ms
from utils.formatting import (
    format_game_message,
    format_round_results,
)
from bot.services.scoring_service import (
    calculate_time_score,
    calculate_total_score,
    is_perfect_guess,
)

logger = logging.getLogger(__name__)


class GameService:
    """Service for managing game rounds."""

    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db
        self._active_timers: dict[str, asyncio.Task] = {}

    async def start_round(
        self, guild: discord.Guild, channel: discord.TextChannel
    ) -> tuple[bool, str]:
        """Start a new game round.

        Returns (success, message) tuple.
        """
        guild_id = str(guild.id)
        channel_id = str(channel.id)

        # Check for active round
        active_round = await self.db.get_active_round(guild_id, channel_id)
        if active_round:
            return (False, "A round is already active! Wait for it to finish.")

        # Check message pool size
        min_age_ms = Config.MIN_MESSAGE_AGE_HOURS * 60 * 60 * 1000
        message_count = await self.db.count_interesting_messages(guild_id, min_age_ms)

        if message_count < Config.MIN_INTERESTING_MESSAGES:
            return (
                False,
                f"Not enough messages indexed yet! Need {Config.MIN_INTERESTING_MESSAGES}, "
                f"have {message_count}. Keep chatting and try again later.",
            )

        # Select random message
        message_row = await self.db.get_random_message(guild_id, min_age_ms)
        if not message_row:
            return (False, "Couldn't find a message to use. Try again!")

        # Fetch the actual message and context
        target_channel = guild.get_channel(int(message_row["channel_id"]))
        if not target_channel:
            return (False, "The channel for the selected message no longer exists.")

        try:
            target_message = await target_channel.fetch_message(
                int(message_row["message_id"])
            )
        except discord.NotFound:
            # Message was deleted - remove from pool and try again
            await self.db.execute(
                "DELETE FROM interesting_messages WHERE message_id = ?",
                (message_row["message_id"],),
            )
            return (False, "Selected message was deleted. Try again!")
        except discord.Forbidden:
            return (False, "I don't have permission to read that channel anymore.")

        # Fetch context messages
        before_messages, after_messages = await self._fetch_context(
            target_channel, target_message
        )

        # Create round in database
        round_number = await self.db.get_round_number(guild_id) + 1
        round_id = await self.db.create_round(
            guild_id=guild_id,
            game_channel_id=channel_id,
            target_message_id=str(target_message.id),
            target_channel_id=str(target_channel.id),
            target_timestamp_ms=message_row["timestamp_ms"],
        )

        # Format and send game message
        game_text = format_game_message(
            target_message=target_message,
            before_messages=before_messages,
            after_messages=after_messages,
            round_number=round_number,
            timeout_seconds=Config.ROUND_TIMEOUT_SECONDS,
        )

        await channel.send(game_text)

        # Start timeout timer
        timer_key = f"{guild_id}:{channel_id}"
        self._active_timers[timer_key] = asyncio.create_task(
            self._round_timeout(round_id, guild, channel)
        )

        return (True, "")

    async def _fetch_context(
        self, channel: discord.TextChannel, target_message: discord.Message
    ) -> tuple[list[discord.Message], list[discord.Message]]:
        """Fetch context messages around the target."""
        context_size = Config.CONTEXT_MESSAGES

        # Fetch messages around the target
        # We need to fetch before and after separately for accuracy
        before_messages = []
        after_messages = []

        try:
            # Fetch messages before
            async for msg in channel.history(
                limit=context_size, before=target_message, oldest_first=False
            ):
                before_messages.append(msg)

            # Reverse to get chronological order
            before_messages.reverse()

            # Fetch messages after
            async for msg in channel.history(
                limit=context_size, after=target_message, oldest_first=True
            ):
                after_messages.append(msg)

        except discord.Forbidden:
            logger.warning(f"Can't read history in channel {channel.id}")

        return (before_messages, after_messages)

    async def _round_timeout(
        self, round_id: int, guild: discord.Guild, channel: discord.TextChannel
    ):
        """Handle round timeout."""
        await asyncio.sleep(Config.ROUND_TIMEOUT_SECONDS)

        # End the round
        await self.end_round(round_id, guild, channel)

    async def end_round(
        self,
        round_id: int,
        guild: discord.Guild,
        channel: discord.TextChannel,
        status: str = "completed",
    ):
        """End a round and show results."""
        # Get round info
        round_info = await self.db.fetch_one(
            "SELECT * FROM game_rounds WHERE id = ?", (round_id,)
        )

        if not round_info or round_info["status"] != "active":
            return

        # Mark round as ended
        await self.db.end_round(round_id, status)

        # Cancel timer if exists
        timer_key = f"{round_info['guild_id']}:{round_info['game_channel_id']}"
        if timer_key in self._active_timers:
            self._active_timers[timer_key].cancel()
            del self._active_timers[timer_key]

        # Get guesses
        guess_rows = await self.db.get_guesses_for_round(round_id)
        guesses = [dict(row) for row in guess_rows]

        # Update player scores
        for guess in guesses:
            total_score = calculate_total_score(
                guess["channel_correct"], guess["time_score"]
            )
            is_perfect = is_perfect_guess(guess["channel_correct"], guess["time_score"])

            await self.db.update_player_score(
                guild_id=str(guild.id),
                player_id=guess["player_id"],
                score=total_score,
                is_perfect=is_perfect,
            )

        # Format and send results
        target_channel = guild.get_channel(int(round_info["target_channel_id"]))
        results_text = format_round_results(
            target_channel=target_channel,
            target_timestamp_ms=round_info["target_timestamp_ms"],
            guesses=guesses,
            guild=guild,
        )

        await channel.send(results_text)

    async def submit_guess(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        player: discord.Member,
        guessed_channel: discord.TextChannel,
        guessed_time: str,
    ) -> tuple[bool, str]:
        """Submit a guess for the active round.

        Returns (success, message) tuple.
        """
        guild_id = str(guild.id)
        channel_id = str(channel.id)

        # Get active round
        active_round = await self.db.get_active_round(guild_id, channel_id)
        if not active_round:
            return (False, "No active round! Start one with `/geoguessr start`")

        # Check if player already guessed
        if await self.db.player_has_guessed(active_round["id"], str(player.id)):
            return (False, "You've already submitted a guess for this round!")

        # Parse time guess
        guessed_timestamp_ms = self._parse_time_guess(guessed_time)
        if guessed_timestamp_ms is None:
            return (
                False,
                "Couldn't understand that time. Try formats like: "
                "'March 2024', 'Jan 15 2023', '2024-06-01'",
            )

        # Calculate scores
        channel_correct = str(guessed_channel.id) == active_round["target_channel_id"]
        time_score = calculate_time_score(
            guessed_timestamp_ms, active_round["target_timestamp_ms"]
        )

        # Save guess
        await self.db.add_guess(
            round_id=active_round["id"],
            player_id=str(player.id),
            guessed_channel_id=str(guessed_channel.id),
            guessed_timestamp_ms=guessed_timestamp_ms,
            channel_correct=channel_correct,
            time_score=time_score,
        )

        total_score = calculate_total_score(channel_correct, time_score)
        return (True, f"Guess submitted! You'll score **{total_score}** points.")

    def _parse_time_guess(self, time_str: str) -> Optional[int]:
        """Parse a time string into Unix timestamp in milliseconds.

        Supports various formats like:
        - 'March 2024'
        - 'Jan 15 2023'
        - '2024-06-01'
        - 'last year'
        """
        import re
        from datetime import datetime, timezone

        time_str = time_str.strip().lower()

        # Try ISO format (2024-06-01)
        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d")
            dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            pass

        # Try "Month Year" format (March 2024)
        month_year_pattern = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{4})"
        match = re.match(month_year_pattern, time_str)
        if match:
            month_str, year_str = match.groups()
            month_map = {
                "jan": 1,
                "january": 1,
                "feb": 2,
                "february": 2,
                "mar": 3,
                "march": 3,
                "apr": 4,
                "april": 4,
                "may": 5,
                "jun": 6,
                "june": 6,
                "jul": 7,
                "july": 7,
                "aug": 8,
                "august": 8,
                "sep": 9,
                "september": 9,
                "oct": 10,
                "october": 10,
                "nov": 11,
                "november": 11,
                "dec": 12,
                "december": 12,
            }
            month = month_map.get(month_str)
            if month:
                dt = datetime(int(year_str), month, 15, tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)

        # Try "Month Day Year" format (Jan 15 2023)
        month_day_year_pattern = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})"
        match = re.match(month_day_year_pattern, time_str)
        if match:
            month_str, day_str, year_str = match.groups()
            month_map = {
                "jan": 1,
                "january": 1,
                "feb": 2,
                "february": 2,
                "mar": 3,
                "march": 3,
                "apr": 4,
                "april": 4,
                "may": 5,
                "jun": 6,
                "june": 6,
                "jul": 7,
                "july": 7,
                "aug": 8,
                "august": 8,
                "sep": 9,
                "september": 9,
                "oct": 10,
                "october": 10,
                "nov": 11,
                "november": 11,
                "dec": 12,
                "december": 12,
            }
            month = month_map.get(month_str)
            if month:
                try:
                    dt = datetime(
                        int(year_str), month, int(day_str), tzinfo=timezone.utc
                    )
                    return int(dt.timestamp() * 1000)
                except ValueError:
                    pass

        # Try just year (2023)
        if re.match(r"^\d{4}$", time_str):
            dt = datetime(int(time_str), 6, 15, tzinfo=timezone.utc)  # Middle of year
            return int(dt.timestamp() * 1000)

        return None

    async def skip_round(
        self, guild: discord.Guild, channel: discord.TextChannel
    ) -> tuple[bool, str]:
        """Skip the current round (moderator only).

        Returns (success, message) tuple.
        """
        guild_id = str(guild.id)
        channel_id = str(channel.id)

        active_round = await self.db.get_active_round(guild_id, channel_id)
        if not active_round:
            return (False, "No active round to skip!")

        await self.end_round(active_round["id"], guild, channel, status="cancelled")
        return (True, "Round skipped!")
