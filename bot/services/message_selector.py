"""Service for selecting random messages from guild history."""

import logging
import random
import re
import time
from collections.abc import Set as AbstractSet

import discord

from config import Config
from utils.snowflake import snowflake_to_timestamp_ms, timestamp_ms_to_snowflake

logger = logging.getLogger(__name__)

# URL pattern for detecting links
URL_PATTERN = re.compile(r"https?://\S+")

# Batches smaller than this only happen at the very end of a channel's eligible
# history, where the candidate pool is tiny and would repeat constantly
MIN_BATCH_SIZE = 5


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
    return bool(URL_PATTERN.search(message.content))


class MessageSelector:
    """Service for selecting random messages from guild history."""

    async def select_random_message(
        self,
        guild: discord.Guild,
        exclude_message_ids: AbstractSet[str] | None = None,
    ) -> tuple[discord.Message, discord.TextChannel] | None:
        """Select a random interesting message from the guild's history.

        Args:
            guild: The guild to search.
            exclude_message_ids: Message IDs to avoid (e.g. recently used targets).
                These are only used as a last resort if nothing else is found.

        Returns a tuple of (message, channel) if found, or None if no
        suitable message could be found after all retries.
        """
        excluded = exclude_message_ids if exclude_message_ids is not None else frozenset()

        # Calculate time bounds
        now_ms = int(time.time() * 1000)
        min_age_ms = Config.MIN_MESSAGE_AGE_HOURS * 60 * 60 * 1000
        max_timestamp_ms = now_ms - min_age_ms
        min_timestamp_ms = now_ms - (Config.LOOKBACK_DAYS * 24 * 60 * 60 * 1000)
        before_snowflake = timestamp_ms_to_snowflake(max_timestamp_ms)

        # Pair each readable channel with its own search window up front. Channels
        # with no history in the window are dropped here rather than wasting one of
        # our retries, since working this out costs no API calls.
        searchable = self._get_searchable_channels(guild, min_timestamp_ms, max_timestamp_ms)

        if not searchable:
            logger.warning(f"No readable channels with history in the search window in guild {guild.id}")
            return None

        # Best candidate that was excluded as recently used, in case we find nothing else
        fallback: tuple[discord.Message, discord.TextChannel] | None = None

        for attempt in range(Config.MAX_SEARCH_RETRIES):
            # Pick a random channel and a random point within its own lifespan, so
            # that timestamps before the channel existed don't all collapse onto its
            # oldest messages
            entry = random.choice(searchable)
            channel, (channel_min_ms, channel_max_ms) = entry

            random_timestamp_ms = random.randint(channel_min_ms, channel_max_ms)
            after_snowflake = timestamp_ms_to_snowflake(random_timestamp_ms)

            logger.info(
                f"Message search attempt {attempt + 1}/{Config.MAX_SEARCH_RETRIES}: checking #{channel.name}..."
            )

            try:
                # Fetch messages starting from the random point. `before` keeps the
                # tail of the batch from crossing the minimum-age cutoff.
                messages = []
                async for msg in channel.history(
                    after=discord.Object(id=after_snowflake),
                    before=discord.Object(id=before_snowflake),
                    limit=Config.MESSAGE_SEARCH_LIMIT,
                    oldest_first=True,
                ):
                    messages.append(msg)

                # A short batch means the timestamp landed within the last few
                # eligible messages of the channel (it does not say anything about
                # how busy the channel was around that time). Those batches are a
                # tiny, heavily repeated candidate pool, so skip them.
                if len(messages) < MIN_BATCH_SIZE:
                    logger.info(f"Only {len(messages)} messages left after this point in #{channel.name}, retrying...")
                    continue

                # Pick uniformly from every interesting message in the batch. Taking
                # the *first* one instead would weight each message by the gap since
                # the previous interesting message, which heavily favors the same
                # handful of post-lull messages.
                interesting = [msg for msg in messages if is_interesting_message(msg)]
                candidates = [msg for msg in interesting if str(msg.id) not in excluded]

                if candidates:
                    chosen = random.choice(candidates)
                    logger.info(
                        f"Selected message {chosen.id} from #{channel.name} "
                        f"({len(candidates)} candidates) on attempt {attempt + 1}"
                    )
                    return (chosen, channel)

                if interesting:
                    if fallback is None:
                        fallback = (random.choice(interesting), channel)
                    logger.info(f"All {len(interesting)} candidates in #{channel.name} used recently, retrying...")
                else:
                    logger.info(
                        f"No interesting messages in batch of {len(messages)} from #{channel.name}, retrying..."
                    )

            except discord.Forbidden:
                logger.warning(f"Lost permission to read channel #{channel.name}")
                searchable.remove(entry)
                if not searchable:
                    logger.warning("No more readable channels left")
                    break
            except discord.HTTPException as e:
                logger.warning(f"HTTP error fetching history: {e}")
                continue

        if fallback is not None:
            logger.info(f"Falling back to recently used message {fallback[0].id} from #{fallback[1].name}")
            return fallback

        logger.warning(f"Failed to find interesting message after {Config.MAX_SEARCH_RETRIES} attempts")
        return None

    def _get_searchable_channels(
        self, guild: discord.Guild, min_timestamp_ms: int, max_timestamp_ms: int
    ) -> list[tuple[discord.TextChannel, tuple[int, int]]]:
        """Pair every readable channel with the time window worth searching in it.

        Channels whose history doesn't overlap the search window are omitted.
        """
        searchable = []
        for channel in self._get_readable_channels(guild):
            bounds = self._channel_search_bounds(channel, min_timestamp_ms, max_timestamp_ms)
            if bounds is None:
                logger.debug(f"Skipping #{channel.name}: no history in the search window")
                continue
            searchable.append((channel, bounds))
        return searchable

    def _channel_search_bounds(
        self, channel: discord.TextChannel, min_timestamp_ms: int, max_timestamp_ms: int
    ) -> tuple[int, int] | None:
        """Clamp the global search window to a channel's own lifespan.

        Both bounds come from snowflakes already cached on the channel object, so
        this costs no API calls. Returns None if the channel has no history that
        overlaps the search window.
        """
        created_ms = int(channel.created_at.timestamp() * 1000)
        start_ms = max(min_timestamp_ms, created_ms)

        end_ms = max_timestamp_ms
        if channel.last_message_id is not None:
            end_ms = min(end_ms, snowflake_to_timestamp_ms(channel.last_message_id))

        if start_ms > end_ms:
            return None
        return (start_ms, end_ms)

    def _get_readable_channels(self, guild: discord.Guild) -> list[discord.TextChannel]:
        """Get list of text channels the bot can read."""
        readable = []
        for channel in guild.text_channels:
            permissions = channel.permissions_for(guild.me)
            if permissions.read_messages and permissions.read_message_history:
                readable.append(channel)
        return readable
