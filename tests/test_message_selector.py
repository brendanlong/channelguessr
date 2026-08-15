"""Tests for message selector."""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import MagicMock

import discord
import pytest

from bot.services.message_selector import URL_PATTERN, MessageSelector, is_interesting_message
from config import Config
from utils.snowflake import snowflake_to_timestamp_ms, timestamp_ms_to_snowflake

DAY_MS = 24 * 60 * 60 * 1000


class TestUrlPattern:
    def test_matches_http(self):
        assert URL_PATTERN.search("Check out http://example.com")

    def test_matches_https(self):
        assert URL_PATTERN.search("Check out https://example.com")

    def test_matches_with_path(self):
        assert URL_PATTERN.search("See https://example.com/path/to/page")

    def test_matches_with_query(self):
        assert URL_PATTERN.search("Link: https://example.com?foo=bar")

    def test_no_match_without_protocol(self):
        assert not URL_PATTERN.search("Visit example.com")

    def test_no_match_plain_text(self):
        assert not URL_PATTERN.search("Just some plain text")


class TestIsInterestingMessage:
    def test_bot_message_not_interesting(self, mock_discord_message):
        msg = mock_discord_message(content="A" * 500, author_bot=True)
        assert is_interesting_message(msg) is False

    def test_long_message_is_interesting(self, mock_discord_message):
        # 200+ characters
        msg = mock_discord_message(content="A" * 200)
        assert is_interesting_message(msg) is True

    def test_short_message_not_interesting(self, mock_discord_message):
        msg = mock_discord_message(content="Short message")
        assert is_interesting_message(msg) is False

    def test_message_with_attachment_is_interesting(self, mock_discord_message):
        class MockAttachment:
            content_type = "image/png"

        msg = mock_discord_message(content="check this out", attachments=[MockAttachment()])
        assert is_interesting_message(msg) is True

    def test_message_with_embed_is_interesting(self, mock_discord_message):
        class MockEmbed:
            pass

        msg = mock_discord_message(content="", embeds=[MockEmbed()])
        assert is_interesting_message(msg) is True

    def test_message_with_url_is_interesting(self, mock_discord_message):
        msg = mock_discord_message(content="Check out https://example.com")
        assert is_interesting_message(msg) is True

    def test_empty_message_not_interesting(self, mock_discord_message):
        msg = mock_discord_message(content="")
        assert is_interesting_message(msg) is False

    def test_borderline_length(self, mock_discord_message):
        # Exactly 199 characters - not enough
        msg = mock_discord_message(content="A" * 199)
        assert is_interesting_message(msg) is False

        # Exactly 200 characters - enough
        msg = mock_discord_message(content="A" * 200)
        assert is_interesting_message(msg) is True


class MockChannel:
    """A text channel whose history() returns a fixed list of messages."""

    def __init__(
        self,
        name="general",
        messages=None,
        created_ms=None,
        last_message_ms=None,
        forbidden_after=None,
        empty=False,
    ):
        self.name = name
        self.id = 999
        self._messages = messages or []
        self._forbidden_after = forbidden_after
        now_ms = int(time.time() * 1000)
        created_ms = created_ms if created_ms is not None else now_ms - 400 * DAY_MS
        self.created_at = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
        # `empty` models a channel nobody has ever posted in, where Discord
        # reports last_message_id as None
        if last_message_ms is None:
            last_message_ms = now_ms - 2 * DAY_MS
        self.last_message_id = None if empty else timestamp_ms_to_snowflake(last_message_ms)
        self.history_calls = []
        self.before_calls = []

    def history(self, *, after, before, limit, oldest_first):
        self.history_calls.append(after.id)
        self.before_calls.append(before.id)
        messages = self._messages
        forbid = self._forbidden_after is not None and len(self.history_calls) > self._forbidden_after

        async def _iter():
            if forbid:
                raise discord.Forbidden(MagicMock(status=403), "Missing Access")
            for msg in messages[:limit]:
                yield msg

        return _iter()

    def permissions_for(self, _member):
        class Permissions:
            read_messages = True
            read_message_history = True

        return Permissions()


class MockChannelGuild:
    def __init__(self, channels):
        self.id = 1
        self.me = object()
        self.text_channels = channels


def as_guild(*channels: MockChannel) -> discord.Guild:
    """Wrap mock channels in a guild the selector will accept."""
    return cast(discord.Guild, MockChannelGuild(list(channels)))


def as_channel(channel: MockChannel) -> discord.TextChannel:
    return cast(discord.TextChannel, channel)


def make_messages(mock_discord_message, count, interesting_ids=()):
    """Build a batch where only `interesting_ids` pass is_interesting_message."""
    return [
        mock_discord_message(
            content=("A" * 200) if i in interesting_ids else "short",
            message_id=i,
        )
        for i in range(count)
    ]


class TestChannelSearchBounds:
    def test_clamps_start_to_channel_creation(self):
        now_ms = int(time.time() * 1000)
        channel = MockChannel(created_ms=now_ms - 30 * DAY_MS)

        bounds = MessageSelector()._channel_search_bounds(as_channel(channel), now_ms - 365 * DAY_MS, now_ms - DAY_MS)

        assert bounds is not None
        assert bounds[0] == pytest.approx(now_ms - 30 * DAY_MS, abs=1000)

    def test_keeps_window_start_for_older_channels(self):
        now_ms = int(time.time() * 1000)
        channel = MockChannel(created_ms=now_ms - 800 * DAY_MS)
        window_start = now_ms - 365 * DAY_MS

        bounds = MessageSelector()._channel_search_bounds(as_channel(channel), window_start, now_ms - DAY_MS)

        assert bounds is not None
        assert bounds[0] == window_start

    def test_clamps_end_to_last_message(self):
        now_ms = int(time.time() * 1000)
        last_message_ms = now_ms - 100 * DAY_MS
        channel = MockChannel(last_message_ms=last_message_ms)

        bounds = MessageSelector()._channel_search_bounds(as_channel(channel), now_ms - 365 * DAY_MS, now_ms - DAY_MS)

        assert bounds is not None
        assert bounds[1] == last_message_ms

    def test_returns_none_for_channel_dead_before_the_window(self):
        now_ms = int(time.time() * 1000)
        # Last posted well before the lookback window opens
        channel = MockChannel(created_ms=now_ms - 800 * DAY_MS, last_message_ms=now_ms - 500 * DAY_MS)

        assert (
            MessageSelector()._channel_search_bounds(as_channel(channel), now_ms - 365 * DAY_MS, now_ms - DAY_MS)
            is None
        )

    def test_returns_none_for_channel_with_no_messages(self):
        now_ms = int(time.time() * 1000)
        channel = MockChannel(empty=True)

        assert (
            MessageSelector()._channel_search_bounds(as_channel(channel), now_ms - 365 * DAY_MS, now_ms - DAY_MS)
            is None
        )

    def test_returns_none_when_channel_is_newer_than_window(self):
        now_ms = int(time.time() * 1000)
        # Created an hour ago, but messages must be at least a day old
        channel = MockChannel(created_ms=now_ms - 60 * 60 * 1000, last_message_ms=now_ms - 30 * 60 * 1000)

        assert (
            MessageSelector()._channel_search_bounds(as_channel(channel), now_ms - 365 * DAY_MS, now_ms - DAY_MS)
            is None
        )


class TestSelectRandomMessage:
    @pytest.mark.asyncio
    async def test_samples_across_all_interesting_messages(self, mock_discord_message):
        # Three interesting messages in the batch; the old "take the first" logic
        # would always return message 1
        messages = make_messages(mock_discord_message, 10, interesting_ids={1, 5, 9})
        guild = as_guild(MockChannel(messages=messages))
        selector = MessageSelector()

        seen = set()
        for _ in range(200):
            result = await selector.select_random_message(guild)
            assert result is not None
            seen.add(result[0].id)

        assert seen == {1, 5, 9}

    @pytest.mark.asyncio
    async def test_search_starts_within_channel_lifespan(self, mock_discord_message):
        now_ms = int(time.time() * 1000)
        created_ms = now_ms - 30 * DAY_MS
        messages = make_messages(mock_discord_message, 10, interesting_ids={3})
        channel = MockChannel(messages=messages, created_ms=created_ms, last_message_ms=now_ms - 2 * DAY_MS)
        selector = MessageSelector()

        for _ in range(50):
            await selector.select_random_message(as_guild(channel))

        # Every probe should land inside [created, last message], never in the
        # dead time before the channel existed
        window = (
            timestamp_ms_to_snowflake(created_ms - 1000),
            timestamp_ms_to_snowflake(now_ms - 2 * DAY_MS + 1000),
        )
        assert channel.history_calls
        assert all(window[0] <= call <= window[1] for call in channel.history_calls)

    @pytest.mark.asyncio
    async def test_history_is_bounded_by_minimum_message_age(self, mock_discord_message):
        messages = make_messages(mock_discord_message, 10, interesting_ids={3})
        channel = MockChannel(messages=messages)

        await MessageSelector().select_random_message(as_guild(channel))

        # The batch must not be allowed to run past the minimum-age cutoff
        cutoff_ms = int(time.time() * 1000) - Config.MIN_MESSAGE_AGE_HOURS * 60 * 60 * 1000
        assert channel.before_calls
        assert all(abs(snowflake_to_timestamp_ms(before) - cutoff_ms) < 1000 for before in channel.before_calls)

    @pytest.mark.asyncio
    async def test_empty_channels_never_consume_retries(self, mock_discord_message):
        # A guild full of channels nobody has ever posted in, plus one real one.
        # The empty ones must not be probed at all, or they'd exhaust the retries.
        empty = [MockChannel(name=f"empty-{i}", empty=True) for i in range(10)]
        real = MockChannel(name="general", messages=make_messages(mock_discord_message, 10, interesting_ids={7}))

        for _ in range(20):
            result = await MessageSelector().select_random_message(as_guild(*empty, real))
            assert result is not None
            assert result[0].id == 7

        assert all(not channel.history_calls for channel in empty)

    @pytest.mark.asyncio
    async def test_logs_which_channels_were_skipped(self, mock_discord_message, caplog):
        empty = MockChannel(name="rules", empty=True)
        real = MockChannel(name="general", messages=make_messages(mock_discord_message, 10, interesting_ids={7}))

        with caplog.at_level(logging.INFO, logger="bot.services.message_selector"):
            await MessageSelector().select_random_message(as_guild(empty, real))

        assert "Searching 1 of 2 readable channels" in caplog.text
        assert "#rules" in caplog.text

    @pytest.mark.asyncio
    async def test_prefers_fresh_candidate_over_fallback_from_another_channel(self, mock_discord_message, monkeypatch):
        # Enough retries that both channels are near-certain to be tried
        monkeypatch.setattr(Config, "MAX_SEARCH_RETRIES", 30)
        used = MockChannel(name="used", messages=make_messages(mock_discord_message, 10, interesting_ids={2}))
        fresh = MockChannel(name="fresh", messages=make_messages(mock_discord_message, 10, interesting_ids={6}))

        for _ in range(20):
            result = await MessageSelector().select_random_message(as_guild(used, fresh), exclude_message_ids={"2"})
            assert result is not None
            assert result[0].id == 6

    @pytest.mark.asyncio
    async def test_falls_back_when_channel_becomes_unreadable(self, mock_discord_message):
        # Only interesting message was used recently, then the bot loses access to
        # the guild's only channel. The already-fetched fallback should still be used.
        messages = make_messages(mock_discord_message, 10, interesting_ids={4})
        channel = MockChannel(messages=messages, forbidden_after=1)

        result = await MessageSelector().select_random_message(as_guild(channel), exclude_message_ids={"4"})

        assert result is not None
        assert result[0].id == 4

    @pytest.mark.asyncio
    async def test_skips_recently_used_messages(self, mock_discord_message):
        messages = make_messages(mock_discord_message, 10, interesting_ids={1, 5, 9})
        guild = as_guild(MockChannel(messages=messages))
        selector = MessageSelector()

        for _ in range(50):
            result = await selector.select_random_message(guild, exclude_message_ids={"1", "9"})
            assert result is not None
            assert result[0].id == 5

    @pytest.mark.asyncio
    async def test_falls_back_to_used_message_when_nothing_else_available(self, mock_discord_message):
        messages = make_messages(mock_discord_message, 10, interesting_ids={4})
        guild = as_guild(MockChannel(messages=messages))

        result = await MessageSelector().select_random_message(guild, exclude_message_ids={"4"})

        assert result is not None
        assert result[0].id == 4

    @pytest.mark.asyncio
    async def test_returns_none_without_interesting_messages(self, mock_discord_message):
        messages = make_messages(mock_discord_message, 10)
        guild = as_guild(MockChannel(messages=messages))

        assert await MessageSelector().select_random_message(guild) is None

    @pytest.mark.asyncio
    async def test_returns_none_for_sparse_channel(self, mock_discord_message):
        messages = make_messages(mock_discord_message, 3, interesting_ids={0, 1, 2})
        guild = as_guild(MockChannel(messages=messages))

        assert await MessageSelector().select_random_message(guild) is None

    @pytest.mark.asyncio
    async def test_returns_none_without_readable_channels(self):
        assert await MessageSelector().select_random_message(as_guild()) is None

    @pytest.mark.asyncio
    async def test_skips_channels_with_no_history_in_window(self, mock_discord_message):
        too_new = MockChannel(name="new", messages=make_messages(mock_discord_message, 10, interesting_ids={0}))
        too_new.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        guild = as_guild(too_new)

        assert await MessageSelector().select_random_message(guild) is None
        assert too_new.history_calls == []
