"""Game service for managing game rounds."""

import asyncio
import logging

import discord
from discord.ext import commands

from bot.services.message_selector import MessageSelector
from bot.services.scoring_service import (
    calculate_time_score,
    calculate_total_score,
    is_perfect_guess,
)
from config import Config
from db.database import Database
from utils.formatting import (
    format_game_message,
    format_round_results,
)
from utils.snowflake import snowflake_to_timestamp_ms

logger = logging.getLogger(__name__)


class GameService:
    """Service for managing game rounds."""

    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db
        self.message_selector = MessageSelector()
        self._active_timers: dict[str, asyncio.Task] = {}

    async def start_round(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        context_messages: int | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[bool, str]:
        """Start a new game round.

        Returns (success, message) tuple.
        """
        # Use provided values or fall back to config defaults
        context_size = context_messages if context_messages is not None else Config.CONTEXT_MESSAGES
        timeout = timeout_seconds if timeout_seconds is not None else Config.ROUND_TIMEOUT_SECONDS
        guild_id = str(guild.id)
        channel_id = str(channel.id)

        logger.info(f"Starting new round in guild {guild.name} ({guild_id}), channel #{channel.name}")

        # Check for active round
        active_round = await self.db.get_active_round(guild_id, channel_id)
        if active_round:
            logger.info(f"Round already active in channel #{channel.name}")
            return (False, "A round is already active! Wait for it to finish.")

        # Select random message from guild history
        logger.info("Searching for a random message from guild history...")
        result = await self.message_selector.select_random_message(guild)
        if not result:
            return (
                False,
                "Couldn't find a suitable message. The server might be too new "
                "or channels may not have enough history. Try again later!",
            )

        target_message, target_channel = result
        logger.info(f"Found message {target_message.id} in #{target_channel.name}")

        # Fetch context messages
        logger.info("Fetching context messages around target...")
        before_messages, after_messages = await self._fetch_context(target_channel, target_message, context_size)
        logger.info(f"Fetched {len(before_messages)} before and {len(after_messages)} after context messages")

        # Create round in database
        round_number = await self.db.get_round_number(guild_id) + 1
        target_timestamp_ms = snowflake_to_timestamp_ms(target_message.id)
        target_author_id = str(target_message.author.id)
        round_id = await self.db.create_round(
            guild_id=guild_id,
            game_channel_id=channel_id,
            target_message_id=str(target_message.id),
            target_channel_id=str(target_channel.id),
            target_timestamp_ms=target_timestamp_ms,
            target_author_id=target_author_id,
        )
        logger.info(f"Created round {round_id} (round #{round_number})")

        # Format and send game message
        game_text = format_game_message(
            target_message=target_message,
            before_messages=before_messages,
            after_messages=after_messages,
            round_number=round_number,
            timeout_seconds=timeout,
        )

        await channel.send(game_text)
        logger.info(f"Round {round_id} started successfully")

        # Start timeout timer
        timer_key = f"{guild_id}:{channel_id}"
        self._active_timers[timer_key] = asyncio.create_task(self._round_timeout(round_id, guild, channel, timeout))

        return (True, "")

    async def _fetch_context(
        self, channel: discord.TextChannel, target_message: discord.Message, context_size: int
    ) -> tuple[list[discord.Message], list[discord.Message]]:
        """Fetch context messages around the target."""

        # Fetch messages around the target
        # We need to fetch before and after separately for accuracy
        before_messages = []
        after_messages = []

        try:
            # Fetch messages before
            logger.debug(f"Fetching {context_size} messages before target in #{channel.name}")
            async for msg in channel.history(limit=context_size, before=target_message, oldest_first=False):
                before_messages.append(msg)

            # Reverse to get chronological order
            before_messages.reverse()

            # Fetch messages after
            logger.debug(f"Fetching {context_size} messages after target in #{channel.name}")
            async for msg in channel.history(limit=context_size, after=target_message, oldest_first=True):
                after_messages.append(msg)

        except discord.Forbidden:
            logger.warning(f"Can't read history in channel #{channel.name} ({channel.id})")

        return (before_messages, after_messages)

    async def _round_timeout(self, round_id: int, guild: discord.Guild, channel: discord.TextChannel, timeout: int):
        """Handle round timeout."""
        await asyncio.sleep(timeout)

        # End the round
        try:
            await self.end_round(round_id, guild, channel)
        except Exception:
            logger.exception(f"Error ending round {round_id} after timeout")

    async def end_round(
        self,
        round_id: int,
        guild: discord.Guild,
        channel: discord.TextChannel,
        status: str = "completed",
    ):
        """End a round and show results."""
        logger.info(f"Ending round {round_id} with status '{status}'")

        # Get round info
        row = await self.db.fetch_one("SELECT * FROM game_rounds WHERE id = ?", (round_id,))

        if not row or row["status"] != "active":
            logger.warning(f"Round {round_id} not active or not found, skipping end_round")
            return

        from models import GameRound

        round_info = GameRound(**dict(row))

        # Mark round as ended
        await self.db.end_round(round_id, status)

        # Cancel timer if exists (but not if we ARE the timer task)
        timer_key = f"{round_info.guild_id}:{round_info.game_channel_id}"
        if timer_key in self._active_timers:
            timer_task = self._active_timers.pop(timer_key)
            if timer_task is not asyncio.current_task():
                timer_task.cancel()

        # Get guesses
        guesses = await self.db.get_guesses_for_round(round_id)
        logger.info(f"Round {round_id} received {len(guesses)} guesses")

        # Update player scores
        for guess in guesses:
            channel_correct = guess.channel_correct or False
            time_score = guess.time_score or 0
            author_correct = guess.author_correct or False
            total_score = calculate_total_score(channel_correct, time_score, author_correct)
            is_perfect = is_perfect_guess(channel_correct, time_score, author_correct)

            await self.db.update_player_score(
                guild_id=str(guild.id),
                player_id=guess.player_id,
                score=total_score,
                is_perfect=is_perfect,
            )

        # Format and send results
        target_channel = guild.get_channel(int(round_info.target_channel_id))
        results_text = format_round_results(
            target_channel=target_channel,
            target_timestamp_ms=round_info.target_timestamp_ms,
            target_message_id=round_info.target_message_id,
            target_author_id=round_info.target_author_id,
            guesses=guesses,
            guild=guild,
        )

        await channel.send(results_text)
        logger.info(f"Round {round_id} ended, results posted")

    async def submit_guess(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        player: discord.Member,
        guessed_channel: discord.TextChannel,
        guessed_time: str,
        guessed_author: discord.Member | None = None,
    ) -> tuple[bool, str]:
        """Submit a guess for the active round.

        Returns (success, message) tuple.
        """
        guild_id = str(guild.id)
        channel_id = str(channel.id)

        # Get active round
        active_round = await self.db.get_active_round(guild_id, channel_id)
        if not active_round:
            return (False, "No active round! Start one with `/start`")

        # Check if player already guessed
        if await self.db.player_has_guessed(active_round.id, str(player.id)):
            return (False, "You've already submitted a guess for this round!")

        # Parse time guess
        guessed_timestamp_ms = self._parse_time_guess(guessed_time)
        if guessed_timestamp_ms is None:
            return (
                False,
                "Couldn't understand that time. Try formats like: 'March 2024', 'Jan 15 2023', '2024-06-01'",
            )

        # Calculate scores
        channel_correct = str(guessed_channel.id) == active_round.target_channel_id
        time_score = calculate_time_score(guessed_timestamp_ms, active_round.target_timestamp_ms)

        # Calculate author score
        guessed_author_id = str(guessed_author.id) if guessed_author else None
        author_correct = guessed_author_id == active_round.target_author_id if guessed_author_id else False

        # Save guess
        await self.db.add_guess(
            round_id=active_round.id,
            player_id=str(player.id),
            guessed_channel_id=str(guessed_channel.id),
            guessed_timestamp_ms=guessed_timestamp_ms,
            channel_correct=channel_correct,
            time_score=time_score,
            guessed_author_id=guessed_author_id,
            author_correct=author_correct,
        )

        total_score = calculate_total_score(channel_correct, time_score, author_correct)
        return (True, f"Guess submitted! You'll score **{total_score}** points.")

    def _parse_time_guess(self, time_str: str) -> int | None:
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
                    dt = datetime(int(year_str), month, int(day_str), tzinfo=timezone.utc)
                    return int(dt.timestamp() * 1000)
                except ValueError:
                    pass

        # Try just year (2023)
        if re.match(r"^\d{4}$", time_str):
            dt = datetime(int(time_str), 6, 15, tzinfo=timezone.utc)  # Middle of year
            return int(dt.timestamp() * 1000)

        return None

    async def skip_round(self, guild: discord.Guild, channel: discord.TextChannel) -> tuple[bool, str]:
        """Skip the current round (moderator only).

        Returns (success, message) tuple.
        """
        guild_id = str(guild.id)
        channel_id = str(channel.id)

        active_round = await self.db.get_active_round(guild_id, channel_id)
        if not active_round:
            return (False, "No active round to skip!")

        await self.end_round(active_round.id, guild, channel, status="cancelled")
        return (True, "Round skipped!")
