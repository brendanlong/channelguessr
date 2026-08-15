"""Service for selecting random messages from guild history."""

import logging
import random
import re
import time
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

import discord

from config import Config
from utils.snowflake import snowflake_to_timestamp_ms, timestamp_ms_to_snowflake

logger = logging.getLogger(__name__)

# URL pattern for detecting links
URL_PATTERN = re.compile(r"https?://\S+")

# Batches smaller than this only happen at the very end of a channel's eligible
# history, where the candidate pool is tiny and would repeat constantly
MIN_BATCH_SIZE = 5

DAY_MS = 24 * 60 * 60 * 1000

# How quickly the per-channel density estimate follows new observations. Each
# probe is noisy (activity varies over a channel's history), so blend rather
# than replace.
DENSITY_EWMA_ALPHA = 0.3

# Floor on the density used for channel weighting, equivalent to one message
# per week. Without it a channel that once measured near-zero would never be
# probed again and couldn't recover if it came back to life.
MIN_WEIGHT_DENSITY = 1 / (7 * DAY_MS)


@dataclass
class _ChannelState:
    """What we've learned about a channel from history probes.

    Kept in memory only: it's all derived from message timestamps we fetch
    anyway, rebuilds itself within a few rounds after a restart, and storing
    it would complicate the privacy story for no real gain.
    """

    # EWMA of messages per millisecond, measured around the points we've probed
    density_per_ms: float | None = None
    # Whether we've probed for the first in-window message yet; distinguishes
    # "never looked" from "looked and found nothing" (first_message_ms=None)
    probed: bool = False
    # Timestamp of the channel's first message at or after the search window
    # start, or None if the probe found no message there
    first_message_ms: int | None = None
    # The channel's last_message_id when we probed, to notice new traffic in a
    # channel whose probe came up empty
    probed_last_message_id: int | None = None

    def cached_first_message(self, start_ms: int, last_message_id: int | None) -> tuple[bool, int | None]:
        """Look up the first in-window message for a window starting at start_ms.

        Returns (cache_is_valid, first_message_ms). The lookback window only
        ever moves forward, so a cached first message stays correct until the
        window start passes it; a cached "nothing in the window" stays correct
        until the channel sees a new message.
        """
        if not self.probed:
            return (False, None)
        if self.first_message_ms is None:
            return (last_message_id == self.probed_last_message_id, None)
        return (self.first_message_ms >= start_ms, self.first_message_ms)


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

    def __init__(self) -> None:
        # Channel IDs are globally unique, so one map works across guilds
        self._channel_states: dict[int, _ChannelState] = {}

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
        min_timestamp_ms = now_ms - (Config.LOOKBACK_DAYS * DAY_MS)
        before_snowflake = timestamp_ms_to_snowflake(max_timestamp_ms)

        # Pair each readable channel with its own search window up front. Channels
        # with no history in the window are dropped here rather than wasting one of
        # our retries, since working this out costs no API calls.
        searchable = self._get_searchable_channels(guild, min_timestamp_ms, max_timestamp_ms)

        if not searchable:
            logger.warning(f"No readable channels with history in the search window in guild {guild.id}")
            return None

        # First message we had to reject as recently used, kept in case every
        # attempt comes up empty
        fallback: tuple[discord.Message, discord.TextChannel] | None = None

        for attempt in range(Config.MAX_SEARCH_RETRIES):
            # Weight channels by how many eligible messages each is estimated to
            # hold, so every message in the guild is roughly equally likely
            # rather than every channel. Recomputed each attempt because every
            # probe refines the estimates.
            entry = random.choices(searchable, weights=self._channel_weights(searchable))[0]
            channel, (channel_min_ms, channel_max_ms) = entry

            logger.info(
                f"Message search attempt {attempt + 1}/{Config.MAX_SEARCH_RETRIES}: checking #{channel.name}..."
            )

            try:
                # Snap the window start to the first message actually in it, so a
                # long-dormant channel whose traffic is all recent doesn't collapse
                # most draws onto its oldest messages
                first_message_ms = await self._first_in_window_ms(channel, channel_min_ms)
                if first_message_ms is None or first_message_ms > channel_max_ms:
                    # last_message_id promised history here, but none of it is in
                    # the eligible window (deleted, or younger than the minimum age)
                    logger.info(f"#{channel.name} has no messages in its eligible window, skipping")
                    searchable.remove(entry)
                    if not searchable:
                        logger.warning("No more searchable channels left")
                        break
                    continue
                channel_min_ms = max(channel_min_ms, first_message_ms)

                # Pick a random point within the channel's own message history, so
                # that timestamps before its first message don't all collapse onto
                # its oldest messages
                random_timestamp_ms = random.randint(channel_min_ms, channel_max_ms)
                after_snowflake = timestamp_ms_to_snowflake(random_timestamp_ms)

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

                # Every batch doubles as a free measurement of how busy the
                # channel is, which feeds the next round's channel weighting
                self._observe_density(channel, random_timestamp_ms, channel_max_ms, messages)

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
        readable = self._get_readable_channels(guild)
        searchable = []
        skipped = []
        for channel in readable:
            bounds = self._channel_search_bounds(channel, min_timestamp_ms, max_timestamp_ms)
            if bounds is None:
                skipped.append(channel.name)
                continue
            searchable.append((channel, bounds))

        if skipped:
            logger.info(
                f"Searching {len(searchable)} of {len(readable)} readable channels; "
                f"skipped {len(skipped)} with no eligible history: {', '.join('#' + name for name in skipped)}"
            )
        return searchable

    def _channel_search_bounds(
        self, channel: discord.TextChannel, min_timestamp_ms: int, max_timestamp_ms: int
    ) -> tuple[int, int] | None:
        """Clamp the global search window to a channel's own lifespan.

        Both bounds come from snowflakes already cached on the channel object, so
        this costs no API calls. Returns None if the channel has no history that
        overlaps the search window.
        """
        # Discord never rewinds last_message_id, even when that message is
        # deleted, so None means nothing has ever been posted here
        if channel.last_message_id is None:
            logger.debug(f"#{channel.name} has never had a message")
            return None

        created_ms = int(channel.created_at.timestamp() * 1000)
        last_message_ms = snowflake_to_timestamp_ms(channel.last_message_id)
        start_ms = max(min_timestamp_ms, created_ms)
        end_ms = min(max_timestamp_ms, last_message_ms)

        if start_ms > end_ms:
            if last_message_ms < min_timestamp_ms:
                reason = (
                    f"last message was {(min_timestamp_ms - last_message_ms) // DAY_MS} days before the lookback window"
                )
            else:
                reason = f"created {(created_ms - max_timestamp_ms) // (60 * 60 * 1000)}h after the minimum message age cutoff"
            logger.debug(f"#{channel.name} has no eligible history: {reason}")
            return None

        # Tighten the start further using the cached first-in-window probe, if
        # we have one; this only reads the cache and never costs an API call
        state = self._channel_states.get(channel.id)
        if state is not None:
            valid, first_message_ms = state.cached_first_message(start_ms, channel.last_message_id)
            if valid:
                if first_message_ms is None:
                    logger.debug(f"#{channel.name} has no messages in the search window")
                    return None
                start_ms = max(start_ms, first_message_ms)
                if start_ms > end_ms:
                    logger.debug(f"#{channel.name}'s only in-window messages are younger than the age cutoff")
                    return None
        return (start_ms, end_ms)

    def _channel_weights(self, searchable: list[tuple[discord.TextChannel, tuple[int, int]]]) -> list[float]:
        """Estimate how many eligible messages each channel holds.

        A channel's weight is its measured message density times the span of
        its search window. Channels we haven't probed yet get the mean density
        of the ones we have, so the first round behaves like a uniform pick and
        the weighting self-calibrates as probes accumulate.
        """
        known = [
            state.density_per_ms
            for channel, _ in searchable
            if (state := self._channel_states.get(channel.id)) is not None and state.density_per_ms is not None
        ]
        if not known:
            return [1.0] * len(searchable)

        default_density = sum(known) / len(known)
        weights = []
        for channel, (start_ms, end_ms) in searchable:
            state = self._channel_states.get(channel.id)
            density = (
                state.density_per_ms if state is not None and state.density_per_ms is not None else default_density
            )
            weights.append(max(density, MIN_WEIGHT_DENSITY) * (end_ms - start_ms + 1))
        return weights

    def _observe_density(
        self, channel: discord.TextChannel, probe_ms: int, window_end_ms: int, messages: list[discord.Message]
    ) -> None:
        """Fold one history batch into the channel's message-density estimate.

        A full batch of N messages after probe_ms means N messages fell between
        the probe point and the last message's timestamp. A short batch means
        the channel's eligible history ran out, so the same N messages cover
        everything up to the end of the search window instead.
        """
        if len(messages) >= Config.MESSAGE_SEARCH_LIMIT:
            span_ms = snowflake_to_timestamp_ms(messages[-1].id) - probe_ms
        else:
            span_ms = window_end_ms - probe_ms
        observed = len(messages) / max(span_ms, 1)

        state = self._channel_states.setdefault(channel.id, _ChannelState())
        if state.density_per_ms is None:
            state.density_per_ms = observed
        else:
            state.density_per_ms = DENSITY_EWMA_ALPHA * observed + (1 - DENSITY_EWMA_ALPHA) * state.density_per_ms
        logger.debug(f"#{channel.name} density estimate is now {state.density_per_ms * DAY_MS:.1f} messages/day")

    async def _first_in_window_ms(self, channel: discord.TextChannel, start_ms: int) -> int | None:
        """Find the timestamp of the channel's first message at or after start_ms.

        Costs one API call per channel, cached for the process lifetime. It only
        re-probes when the advancing window start passes the cached first
        message, or when a channel whose probe found nothing gets new traffic.
        """
        state = self._channel_states.setdefault(channel.id, _ChannelState())
        valid, first_message_ms = state.cached_first_message(start_ms, channel.last_message_id)
        if valid:
            return first_message_ms

        first = None
        async for msg in channel.history(
            after=discord.Object(id=timestamp_ms_to_snowflake(start_ms)),
            limit=1,
            oldest_first=True,
        ):
            first = msg

        state.probed = True
        state.probed_last_message_id = channel.last_message_id
        state.first_message_ms = snowflake_to_timestamp_ms(first.id) if first is not None else None
        return state.first_message_ms

    def _get_readable_channels(self, guild: discord.Guild) -> list[discord.TextChannel]:
        """Get list of text channels the bot can read."""
        readable = []
        for channel in guild.text_channels:
            permissions = channel.permissions_for(guild.me)
            if permissions.read_messages and permissions.read_message_history:
                readable.append(channel)
        return readable
