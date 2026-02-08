"""Scoring service for calculating game scores."""

from config import Config


def calculate_time_score(guessed_timestamp_ms: int, actual_timestamp_ms: int) -> int:
    """Calculate score based on time accuracy.

    Returns 0-1000 points based on how close the guess is to the actual time.

    Since month guesses are converted to the 15th of that month, we use
    day-based thresholds:
    - Within 16 days: correct month (500 points) or exact day (1000 points)
    - Within 46 days: adjacent month (300 points)
    - Beyond 46 days: 0 points

    Exact day is defined as within 1 day (since guesses are date-level).
    """
    diff_ms = abs(guessed_timestamp_ms - actual_timestamp_ms)
    diff_days = diff_ms / (1000 * 60 * 60 * 24)

    if diff_days <= 1:
        return 1000
    elif diff_days <= 16:
        return 500
    elif diff_days <= 46:
        return 300
    else:
        return 0


def calculate_total_score(channel_correct: bool, time_score: int, author_correct: bool = False) -> int:
    """Calculate total score for a guess."""
    channel_points = Config.CHANNEL_SCORE if channel_correct else 0
    author_points = Config.AUTHOR_SCORE if author_correct else 0
    return channel_points + time_score + author_points


def is_perfect_guess(channel_correct: bool, time_score: int, author_correct: bool = False) -> bool:
    """Check if a guess is perfect (max channel + time within 1 day + author correct)."""
    return channel_correct and time_score == Config.TIME_MAX_SCORE and author_correct
