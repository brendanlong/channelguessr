"""Pydantic models for game data structures."""

from datetime import datetime

from pydantic import BaseModel


class GameRound(BaseModel):
    """A game round record from the database."""

    id: int
    guild_id: str
    game_channel_id: str
    target_message_id: str
    target_channel_id: str
    target_timestamp_ms: int
    target_author_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    status: str = "active"
    timer_expires_at: datetime | None = None


class Guess(BaseModel):
    """A player's guess for a round."""

    id: int
    round_id: int
    player_id: str
    guessed_channel_id: str | None = None
    guessed_timestamp_ms: int | None = None
    submitted_at: datetime | None = None
    channel_correct: bool | None = None
    time_score: int | None = None
    guessed_author_id: str | None = None
    author_correct: bool | None = None


class PlayerScore(BaseModel):
    """A player's cumulative score record."""

    guild_id: str
    player_id: str
    total_score: int = 0
    rounds_played: int = 0
    perfect_guesses: int = 0


class UserDataDeletion(BaseModel):
    """Result of deleting a user's data."""

    guesses: int = 0
    scores: int = 0
