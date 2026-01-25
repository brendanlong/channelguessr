import aiosqlite
from pathlib import Path
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Connect to the database and run migrations."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._run_migrations()

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _run_migrations(self) -> None:
        """Run all SQL migration files."""
        # Create migrations tracking table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                name TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._connection.commit()

        migrations_dir = Path(__file__).parent / "migrations"

        for migration_file in sorted(migrations_dir.glob("*.sql")):
            # Check if migration already applied
            cursor = await self._connection.execute(
                "SELECT 1 FROM _migrations WHERE name = ?",
                (migration_file.name,)
            )
            if await cursor.fetchone():
                logger.debug(f"Skipping already applied migration: {migration_file.name}")
                continue

            logger.info(f"Running migration: {migration_file.name}")
            sql = migration_file.read_text()
            await self._connection.executescript(sql)
            await self._connection.execute(
                "INSERT INTO _migrations (name) VALUES (?)",
                (migration_file.name,)
            )
            await self._connection.commit()

    async def execute(
        self, query: str, params: tuple = ()
    ) -> aiosqlite.Cursor:
        """Execute a query and return the cursor."""
        cursor = await self._connection.execute(query, params)
        await self._connection.commit()
        return cursor

    async def fetch_one(
        self, query: str, params: tuple = ()
    ) -> Optional[aiosqlite.Row]:
        """Fetch a single row."""
        cursor = await self._connection.execute(query, params)
        return await cursor.fetchone()

    async def fetch_all(
        self, query: str, params: tuple = ()
    ) -> list[aiosqlite.Row]:
        """Fetch all rows."""
        cursor = await self._connection.execute(query, params)
        return await cursor.fetchall()

    async def fetch_value(
        self, query: str, params: tuple = ()
    ) -> Optional[Any]:
        """Fetch a single value from the first column of the first row."""
        row = await self.fetch_one(query, params)
        return row[0] if row else None

    # Game rounds methods

    async def create_round(
        self,
        guild_id: str,
        game_channel_id: str,
        target_message_id: str,
        target_channel_id: str,
        target_timestamp_ms: int,
        target_author_id: str,
    ) -> int:
        """Create a new game round. Returns the round ID."""
        cursor = await self.execute(
            """
            INSERT INTO game_rounds
            (guild_id, game_channel_id, target_message_id, target_channel_id, target_timestamp_ms, target_author_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                game_channel_id,
                target_message_id,
                target_channel_id,
                target_timestamp_ms,
                target_author_id,
            ),
        )
        return cursor.lastrowid

    async def get_active_round(
        self, guild_id: str, game_channel_id: str
    ) -> Optional[aiosqlite.Row]:
        """Get the active round for a channel."""
        return await self.fetch_one(
            """
            SELECT * FROM game_rounds
            WHERE guild_id = ? AND game_channel_id = ? AND status = 'active'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (guild_id, game_channel_id),
        )

    async def end_round(self, round_id: int, status: str = "completed") -> None:
        """End a game round."""
        await self.execute(
            """
            UPDATE game_rounds
            SET status = ?, ended_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, round_id),
        )

    async def get_round_number(self, guild_id: str) -> int:
        """Get the total number of completed rounds for a guild."""
        result = await self.fetch_value(
            """
            SELECT COUNT(*) FROM game_rounds
            WHERE guild_id = ?
            """,
            (guild_id,),
        )
        return result or 0

    # Guesses methods

    async def add_guess(
        self,
        round_id: int,
        player_id: str,
        guessed_channel_id: Optional[str],
        guessed_timestamp_ms: Optional[int],
        channel_correct: bool,
        time_score: int,
        guessed_author_id: Optional[str] = None,
        author_correct: Optional[bool] = None,
    ) -> bool:
        """Add a player guess. Returns True if successful."""
        try:
            await self.execute(
                """
                INSERT OR REPLACE INTO guesses
                (round_id, player_id, guessed_channel_id, guessed_timestamp_ms,
                 channel_correct, time_score, guessed_author_id, author_correct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    round_id,
                    player_id,
                    guessed_channel_id,
                    guessed_timestamp_ms,
                    channel_correct,
                    time_score,
                    guessed_author_id,
                    author_correct,
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add guess: {e}")
            return False

    async def get_guesses_for_round(self, round_id: int) -> list[aiosqlite.Row]:
        """Get all guesses for a round."""
        return await self.fetch_all(
            """
            SELECT * FROM guesses
            WHERE round_id = ?
            ORDER BY submitted_at
            """,
            (round_id,),
        )

    async def player_has_guessed(self, round_id: int, player_id: str) -> bool:
        """Check if a player has already guessed in a round."""
        result = await self.fetch_value(
            """
            SELECT 1 FROM guesses
            WHERE round_id = ? AND player_id = ?
            """,
            (round_id, player_id),
        )
        return result is not None

    # Leaderboard methods

    async def update_player_score(
        self,
        guild_id: str,
        player_id: str,
        score: int,
        is_perfect: bool,
    ) -> None:
        """Update a player's score."""
        perfect_increment = 1 if is_perfect else 0

        await self.execute(
            """
            INSERT INTO player_scores (guild_id, player_id, total_score, rounds_played, perfect_guesses)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(guild_id, player_id) DO UPDATE SET
                total_score = total_score + ?,
                rounds_played = rounds_played + 1,
                perfect_guesses = perfect_guesses + ?
            """,
            (
                guild_id,
                player_id,
                score,
                perfect_increment,
                score,
                perfect_increment,
            ),
        )

    async def get_leaderboard(
        self, guild_id: str, limit: int = 10
    ) -> list[aiosqlite.Row]:
        """Get the top players for a guild."""
        return await self.fetch_all(
            """
            SELECT * FROM player_scores
            WHERE guild_id = ?
            ORDER BY total_score DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )

    async def get_player_stats(
        self, guild_id: str, player_id: str
    ) -> Optional[aiosqlite.Row]:
        """Get a player's stats."""
        return await self.fetch_one(
            """
            SELECT * FROM player_scores
            WHERE guild_id = ? AND player_id = ?
            """,
            (guild_id, player_id),
        )

    async def get_player_rank(self, guild_id: str, player_id: str) -> int:
        """Get a player's rank in the leaderboard."""
        result = await self.fetch_value(
            """
            SELECT COUNT(*) + 1 FROM player_scores
            WHERE guild_id = ? AND total_score > (
                SELECT COALESCE(total_score, 0) FROM player_scores
                WHERE guild_id = ? AND player_id = ?
            )
            """,
            (guild_id, guild_id, player_id),
        )
        return result or 1

    # Data deletion methods

    async def get_all_guild_ids(self) -> set[str]:
        """Get all guild IDs that have data in the database."""
        guild_ids = set()
        for table in ["game_rounds", "player_scores"]:
            rows = await self.fetch_all(f"SELECT DISTINCT guild_id FROM {table}")
            guild_ids.update(row["guild_id"] for row in rows)
        return guild_ids

    async def delete_guild_data(self, guild_id: str) -> None:
        """Delete all data for a guild (used when bot is removed from a server)."""
        # Delete guesses for rounds in this guild
        await self.execute(
            """
            DELETE FROM guesses
            WHERE round_id IN (SELECT id FROM game_rounds WHERE guild_id = ?)
            """,
            (guild_id,),
        )
        # Delete game rounds
        await self.execute(
            "DELETE FROM game_rounds WHERE guild_id = ?",
            (guild_id,),
        )
        # Delete player scores
        await self.execute(
            "DELETE FROM player_scores WHERE guild_id = ?",
            (guild_id,),
        )
        logger.info(f"Deleted all data for guild {guild_id}")
