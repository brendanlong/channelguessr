"""Pydantic models for game data structures."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GameRound(BaseModel):
    """A game round record from the database."""

    id: int
    guild_id: str
    game_channel_id: str
    target_message_id: str
    target_channel_id: str
    target_timestamp_ms: int
    target_author_id: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    status: str = "active"


class Guess(BaseModel):
    """A player's guess for a round."""

    id: int
    round_id: int
    player_id: str
    guessed_channel_id: Optional[str] = None
    guessed_timestamp_ms: Optional[int] = None
    submitted_at: Optional[datetime] = None
    channel_correct: Optional[bool] = None
    time_score: Optional[int] = None
    guessed_author_id: Optional[str] = None
    author_correct: Optional[bool] = None


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
