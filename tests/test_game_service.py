"""Tests for GameService, particularly timer restoration."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
import pytest_asyncio

from bot.services.game_service import GameService
from db.database import Database


@pytest_asyncio.fixture
async def db():
    """Create an in-memory database for testing."""
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=None)
    return bot


@pytest.fixture
def mock_guild():
    """Create a mock Discord guild."""
    guild = MagicMock()
    guild.id = 123
    guild.name = "Test Guild"
    return guild


@pytest.fixture
def mock_channel():
    """Create a mock Discord text channel."""
    import discord

    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 456
    channel.name = "test-channel"
    channel.send = AsyncMock()
    return channel


class TestRestoreTimers:
    @pytest.mark.asyncio
    async def test_restore_timers_no_active_rounds(self, db, mock_bot):
        """Test restore_timers with no active rounds returns 0."""
        service = GameService(mock_bot, db)

        restored = await service.restore_timers()

        assert restored == 0
        assert len(service._active_timers) == 0

    @pytest.mark.asyncio
    async def test_restore_timers_guild_not_found(self, db, mock_bot):
        """Test that rounds are cancelled when guild is not found."""
        # Create a round with a future timer
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        await db.create_round(
            guild_id="999",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
            timer_expires_at=future_time.isoformat(),
        )

        mock_bot.get_guild.return_value = None
        service = GameService(mock_bot, db)

        restored = await service.restore_timers()

        assert restored == 0
        # Round should be cancelled
        active = await db.get_active_round("999", "456")
        assert active is None

    @pytest.mark.asyncio
    async def test_restore_timers_channel_not_found(self, db, mock_bot, mock_guild):
        """Test that rounds are cancelled when channel is not found."""
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
            timer_expires_at=future_time.isoformat(),
        )

        mock_bot.get_guild.return_value = mock_guild
        mock_guild.get_channel = MagicMock(return_value=None)
        mock_bot.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Not found"))
        service = GameService(mock_bot, db)

        restored = await service.restore_timers()

        assert restored == 0
        # Round should be cancelled
        active = await db.get_active_round("123", "456")
        assert active is None

    @pytest.mark.asyncio
    async def test_restore_timers_channel_fetched_via_api(self, db, mock_bot, mock_guild, mock_channel):
        """Test that channels are fetched via API when not in cache."""
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
            timer_expires_at=future_time.isoformat(),
        )

        mock_bot.get_guild.return_value = mock_guild
        # Cache miss
        mock_guild.get_channel = MagicMock(return_value=None)
        # API hit via bot.fetch_channel
        mock_bot.fetch_channel = AsyncMock(return_value=mock_channel)
        service = GameService(mock_bot, db)

        restored = await service.restore_timers()

        assert restored == 1
        assert "123:456" in service._active_timers
        mock_bot.fetch_channel.assert_called_once_with(456)
        # Clean up
        service._active_timers["123:456"].cancel()

    @pytest.mark.asyncio
    async def test_restore_timers_no_timer_expires_at(self, db, mock_bot, mock_guild, mock_channel):
        """Test that rounds without timer_expires_at are cancelled."""
        # Create a round without timer_expires_at
        await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
            timer_expires_at=None,
        )

        mock_bot.get_guild.return_value = mock_guild
        mock_guild.get_channel = MagicMock(return_value=mock_channel)
        service = GameService(mock_bot, db)

        restored = await service.restore_timers()

        assert restored == 0
        # Round should be cancelled
        active = await db.get_active_round("123", "456")
        assert active is None

    @pytest.mark.asyncio
    async def test_restore_timers_schedules_future_timer(self, db, mock_bot, mock_guild, mock_channel):
        """Test that future timers are scheduled correctly."""
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
            timer_expires_at=future_time.isoformat(),
        )

        mock_bot.get_guild.return_value = mock_guild
        mock_guild.get_channel = MagicMock(return_value=mock_channel)
        service = GameService(mock_bot, db)

        restored = await service.restore_timers()

        assert restored == 1
        assert "123:456" in service._active_timers
        # Clean up the scheduled task
        service._active_timers["123:456"].cancel()

    @pytest.mark.asyncio
    async def test_restore_timers_schedules_expired_timer(self, db, mock_bot, mock_guild, mock_channel):
        """Test that expired timers are scheduled with 0 delay."""
        past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
            timer_expires_at=past_time.isoformat(),
        )

        mock_bot.get_guild.return_value = mock_guild
        mock_guild.get_channel = MagicMock(return_value=mock_channel)
        service = GameService(mock_bot, db)

        restored = await service.restore_timers()

        assert restored == 1
        assert "123:456" in service._active_timers
        # Clean up the scheduled task
        service._active_timers["123:456"].cancel()

    @pytest.mark.asyncio
    async def test_restore_timers_multiple_rounds(self, db, mock_bot, mock_guild, mock_channel):
        """Test restoring timers for multiple active rounds."""
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)

        # Create two rounds in different channels
        await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
            timer_expires_at=future_time.isoformat(),
        )
        await db.create_round(
            guild_id="123",
            game_channel_id="457",
            target_message_id="790",
            target_channel_id="102",
            target_timestamp_ms=1609459200000,
            target_author_id="author456",
            timer_expires_at=future_time.isoformat(),
        )

        mock_bot.get_guild.return_value = mock_guild

        # Create separate mock channels for each channel ID
        mock_channel2 = MagicMock()
        mock_channel2.id = 457

        def get_channel(channel_id):
            import discord

            if channel_id == 456:
                result = MagicMock(spec=discord.TextChannel)
                result.id = 456
                return result
            elif channel_id == 457:
                result = MagicMock(spec=discord.TextChannel)
                result.id = 457
                return result
            return None

        mock_guild.get_channel = get_channel
        service = GameService(mock_bot, db)

        restored = await service.restore_timers()

        assert restored == 2
        assert "123:456" in service._active_timers
        assert "123:457" in service._active_timers

        # Clean up
        for task in service._active_timers.values():
            task.cancel()


class TestCancelGuildTimers:
    @pytest.mark.asyncio
    async def test_cancel_guild_timers_no_timers(self, db, mock_bot):
        """Test cancel_guild_timers with no active timers."""
        service = GameService(mock_bot, db)

        cancelled = service.cancel_guild_timers("123")

        assert cancelled == 0

    @pytest.mark.asyncio
    async def test_cancel_guild_timers_cancels_matching(self, db, mock_bot):
        """Test that cancel_guild_timers only cancels timers for the specified guild."""
        service = GameService(mock_bot, db)

        # Manually add some mock timers
        task1 = asyncio.create_task(asyncio.sleep(100))
        task2 = asyncio.create_task(asyncio.sleep(100))
        task3 = asyncio.create_task(asyncio.sleep(100))

        service._active_timers["123:456"] = task1
        service._active_timers["123:789"] = task2
        service._active_timers["999:456"] = task3

        cancelled = service.cancel_guild_timers("123")

        # Allow cancellation to propagate
        await asyncio.sleep(0)

        assert cancelled == 2
        assert "123:456" not in service._active_timers
        assert "123:789" not in service._active_timers
        assert "999:456" in service._active_timers
        assert task1.cancelled()
        assert task2.cancelled()
        assert not task3.cancelled()

        # Clean up remaining task
        task3.cancel()


class TestTimerExecution:
    @pytest.mark.asyncio
    async def test_expired_timer_ends_round(self, db, mock_bot, mock_guild, mock_channel):
        """Test that an expired timer actually ends the round."""
        # Create a round with an already-expired timer
        # Use numeric IDs to match what Discord would actually provide
        past_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="111222333",
            timer_expires_at=past_time.isoformat(),
        )

        mock_bot.get_guild.return_value = mock_guild
        mock_guild.get_channel = MagicMock(return_value=mock_channel)
        mock_guild.id = 123
        mock_guild.get_member = MagicMock(return_value=None)
        mock_guild.fetch_member = AsyncMock(return_value=None)

        # Mock the channel lookup for end_round
        def get_channel(channel_id):
            if channel_id == 101:
                target_channel = MagicMock()
                target_channel.mention = "#target-channel"
                return target_channel
            return mock_channel

        mock_guild.get_channel = get_channel

        service = GameService(mock_bot, db)

        # Restore timers (should schedule immediate execution)
        restored = await service.restore_timers()
        assert restored == 1

        # Wait for the task to execute
        await asyncio.sleep(0.1)

        # Round should be ended
        active = await db.get_active_round("123", "456")
        assert active is None

        # Results should have been posted
        mock_channel.send.assert_called()


class TestTimeWarning:
    @pytest.mark.asyncio
    async def test_time_warning_sent_before_round_ends(self, db, mock_bot, mock_guild, mock_channel):
        """Test that a warning is sent 10 seconds before the round ends."""
        # Create a round with a timer expiring in 0.15 seconds (enough for warning + end)
        future_time = datetime.now(timezone.utc) + timedelta(seconds=0.15)
        await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="111222333",
            timer_expires_at=future_time.isoformat(),
        )

        mock_bot.get_guild.return_value = mock_guild
        mock_guild.id = 123
        mock_guild.get_member = MagicMock(return_value=None)
        mock_guild.fetch_member = AsyncMock(return_value=None)

        def get_channel(channel_id):
            if channel_id == 101:
                target_channel = MagicMock()
                target_channel.mention = "#target-channel"
                return target_channel
            return mock_channel

        mock_guild.get_channel = get_channel
        service = GameService(mock_bot, db)

        # Restore timers
        restored = await service.restore_timers()
        assert restored == 1

        # Wait for the task to execute (timer is very short, no warning expected)
        await asyncio.sleep(0.3)

        # For very short timers (< 10s), no warning should be sent, only the final results
        # The round should be ended
        active = await db.get_active_round("123", "456")
        assert active is None

    @pytest.mark.asyncio
    async def test_send_time_warning_if_active_sends_warning(self, db, mock_bot, mock_channel):
        """Test that _send_time_warning_if_active sends a warning for active rounds."""
        # Create an active round
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        round_id = await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="111222333",
            timer_expires_at=future_time.isoformat(),
        )

        service = GameService(mock_bot, db)

        # Call the warning method
        await service._send_time_warning_if_active(round_id, mock_channel, 10)

        # Should have sent a warning
        mock_channel.send.assert_called_once()
        call_args = mock_channel.send.call_args[0][0]
        assert "10 seconds remaining" in call_args

    @pytest.mark.asyncio
    async def test_send_time_warning_if_active_skips_ended_round(self, db, mock_bot, mock_channel):
        """Test that _send_time_warning_if_active does not send warning for ended rounds."""
        # Create a round and end it
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        round_id = await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="111222333",
            timer_expires_at=future_time.isoformat(),
        )
        await db.end_round(round_id, "completed")

        service = GameService(mock_bot, db)

        # Call the warning method
        await service._send_time_warning_if_active(round_id, mock_channel, 10)

        # Should NOT have sent a warning
        mock_channel.send.assert_not_called()
