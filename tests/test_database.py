"""Tests for database operations."""

import pytest
import pytest_asyncio

from db.database import Database


@pytest_asyncio.fixture
async def db():
    """Create an in-memory database for testing."""
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


class TestDatabaseConnection:
    @pytest.mark.asyncio
    async def test_connect_and_close(self):
        db = Database(":memory:")
        await db.connect()
        assert db._connection is not None
        await db.close()
        assert db._connection is None


class TestGameRounds:
    @pytest.mark.asyncio
    async def test_create_round(self, db):
        round_id = await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
        )
        assert round_id is not None
        assert round_id > 0

    @pytest.mark.asyncio
    async def test_get_active_round(self, db):
        # Create a round
        round_id = await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
        )

        # Get active round
        active = await db.get_active_round("123", "456")
        assert active is not None
        assert active["id"] == round_id
        assert active["status"] == "active"
        assert active["target_author_id"] == "author123"

    @pytest.mark.asyncio
    async def test_no_active_round_returns_none(self, db):
        active = await db.get_active_round("123", "456")
        assert active is None

    @pytest.mark.asyncio
    async def test_end_round(self, db):
        round_id = await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
        )

        await db.end_round(round_id, "completed")

        # Should no longer be active
        active = await db.get_active_round("123", "456")
        assert active is None

        # But should exist with completed status
        row = await db.fetch_one("SELECT * FROM game_rounds WHERE id = ?", (round_id,))
        assert row["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_round_number(self, db):
        guild_id = "123"

        # Initially 0
        assert await db.get_round_number(guild_id) == 0

        # Create a round
        await db.create_round(
            guild_id=guild_id,
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
        )
        assert await db.get_round_number(guild_id) == 1

        # Create another
        await db.create_round(
            guild_id=guild_id,
            game_channel_id="456",
            target_message_id="790",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author456",
        )
        assert await db.get_round_number(guild_id) == 2


class TestGuesses:
    @pytest.mark.asyncio
    async def test_add_guess(self, db):
        # Create a round first
        round_id = await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
        )

        result = await db.add_guess(
            round_id=round_id,
            player_id="player1",
            guessed_channel_id="101",
            guessed_timestamp_ms=1609459200000,
            channel_correct=True,
            time_score=500,
            guessed_author_id="author123",
            author_correct=True,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_player_has_guessed(self, db):
        round_id = await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
        )

        # Initially hasn't guessed
        assert await db.player_has_guessed(round_id, "player1") is False

        # Add guess
        await db.add_guess(
            round_id=round_id,
            player_id="player1",
            guessed_channel_id="101",
            guessed_timestamp_ms=1609459200000,
            channel_correct=True,
            time_score=500,
        )

        # Now has guessed
        assert await db.player_has_guessed(round_id, "player1") is True
        # Other player hasn't
        assert await db.player_has_guessed(round_id, "player2") is False

    @pytest.mark.asyncio
    async def test_get_guesses_for_round(self, db):
        round_id = await db.create_round(
            guild_id="123",
            game_channel_id="456",
            target_message_id="789",
            target_channel_id="101",
            target_timestamp_ms=1609459200000,
            target_author_id="author123",
        )

        # Add multiple guesses
        await db.add_guess(
            round_id=round_id,
            player_id="player1",
            guessed_channel_id="101",
            guessed_timestamp_ms=1609459200000,
            channel_correct=True,
            time_score=500,
            guessed_author_id="author123",
            author_correct=True,
        )
        await db.add_guess(
            round_id=round_id,
            player_id="player2",
            guessed_channel_id="102",
            guessed_timestamp_ms=1609459200000,
            channel_correct=False,
            time_score=300,
            guessed_author_id="wrong_author",
            author_correct=False,
        )

        guesses = await db.get_guesses_for_round(round_id)
        assert len(guesses) == 2


class TestPlayerScores:
    @pytest.mark.asyncio
    async def test_update_player_score_new_player(self, db):
        await db.update_player_score(
            guild_id="123",
            player_id="player1",
            score=750,
            is_perfect=False,
        )

        stats = await db.get_player_stats("123", "player1")
        assert stats["total_score"] == 750
        assert stats["rounds_played"] == 1
        assert stats["perfect_guesses"] == 0

    @pytest.mark.asyncio
    async def test_update_player_score_existing_player(self, db):
        await db.update_player_score("123", "player1", 500, False)
        await db.update_player_score("123", "player1", 750, True)

        stats = await db.get_player_stats("123", "player1")
        assert stats["total_score"] == 1250
        assert stats["rounds_played"] == 2
        assert stats["perfect_guesses"] == 1

    @pytest.mark.asyncio
    async def test_get_leaderboard(self, db):
        await db.update_player_score("123", "player1", 500, False)
        await db.update_player_score("123", "player2", 1000, True)
        await db.update_player_score("123", "player3", 750, False)

        leaderboard = await db.get_leaderboard("123", limit=10)
        assert len(leaderboard) == 3
        # Should be sorted by score descending
        assert leaderboard[0]["player_id"] == "player2"
        assert leaderboard[1]["player_id"] == "player3"
        assert leaderboard[2]["player_id"] == "player1"

    @pytest.mark.asyncio
    async def test_get_player_rank(self, db):
        await db.update_player_score("123", "player1", 500, False)
        await db.update_player_score("123", "player2", 1000, True)
        await db.update_player_score("123", "player3", 750, False)

        assert await db.get_player_rank("123", "player2") == 1
        assert await db.get_player_rank("123", "player3") == 2
        assert await db.get_player_rank("123", "player1") == 3

    @pytest.mark.asyncio
    async def test_get_player_rank_no_scores(self, db):
        # Player with no scores should get rank 1
        rank = await db.get_player_rank("123", "nonexistent")
        assert rank == 1
