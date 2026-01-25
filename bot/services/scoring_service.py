"""Scoring service for calculating game scores."""


def calculate_time_score(guessed_timestamp_ms: int, actual_timestamp_ms: int) -> int:
    """Calculate score based on time accuracy.

    Returns 0-500 points based on how close the guess is to the actual time.
    """
    # Calculate difference in days
    diff_ms = abs(guessed_timestamp_ms - actual_timestamp_ms)
    diff_days = diff_ms / (1000 * 60 * 60 * 24)

    if diff_days <= 1:
        return 500
    elif diff_days <= 7:
        return 400
    elif diff_days <= 30:
        return 300
    elif diff_days <= 90:
        return 200
    elif diff_days <= 180:
        return 100
    elif diff_days <= 365:
        return 50
    else:
        return 0


def calculate_total_score(channel_correct: bool, time_score: int) -> int:
    """Calculate total score for a guess."""
    channel_score = 500 if channel_correct else 0
    return channel_score + time_score


def is_perfect_guess(channel_correct: bool, time_score: int) -> bool:
    """Check if a guess is perfect (max channel + time within 1 day)."""
    return channel_correct and time_score == 500
