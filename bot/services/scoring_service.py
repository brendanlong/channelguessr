"""Scoring service for calculating game scores."""

from config import Config


def calculate_time_score(guessed_timestamp_ms: int, actual_timestamp_ms: int) -> int:
    """Calculate score based on time accuracy.

    Returns 0-500 points based on how close the guess is to the actual time.

    Scoring brackets are designed to be fair for "Month Year" format guesses,
    where guessing one month off should still give a reasonable score.
    """
    # Calculate difference in days
    diff_ms = abs(guessed_timestamp_ms - actual_timestamp_ms)
    diff_days = diff_ms / (1000 * 60 * 60 * 24)

    if diff_days <= 1:
        return 500
    elif diff_days <= 7:
        return 450
    elif diff_days <= 31:
        return 400
    elif diff_days <= 62:
        return 300
    elif diff_days <= 93:
        return 200
    elif diff_days <= 186:
        return 100
    elif diff_days <= 365:
        return 50
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
