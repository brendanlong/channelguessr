"""Tests for scoring service."""

from bot.services.scoring_service import (
    calculate_time_score,
    calculate_total_score,
    is_perfect_guess,
)


class TestCalculateTimeScore:
    def test_exact_match(self):
        # Guessed exactly right - exact day
        actual = 1609459200000
        guessed = 1609459200000
        assert calculate_time_score(guessed, actual) == 1000

    def test_within_one_day(self):
        actual = 1609459200000
        # 12 hours off - still exact day
        guessed = actual + (12 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 1000

    def test_exactly_one_day(self):
        actual = 1609459200000
        # Exactly 1 day (24 hours) - still exact day
        guessed = actual + (24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 1000

    def test_just_over_one_day(self):
        actual = 1609459200000
        # 1 day + 1 hour - correct month tier
        guessed = actual + (25 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 500

    def test_within_16_days(self):
        actual = 1609459200000
        # 10 days off - correct month (month guess -> 15th, within 16 day window)
        guessed = actual + (10 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 500

    def test_exactly_16_days(self):
        actual = 1609459200000
        # Exactly 16 days - still correct month
        guessed = actual + (16 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 500

    def test_just_over_16_days(self):
        actual = 1609459200000
        # 17 days off - adjacent month tier
        guessed = actual + (17 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 300

    def test_within_46_days(self):
        actual = 1609459200000
        # 30 days off - adjacent month
        guessed = actual + (30 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 300

    def test_exactly_46_days(self):
        actual = 1609459200000
        # Exactly 46 days - still adjacent month
        guessed = actual + (46 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 300

    def test_just_over_46_days(self):
        actual = 1609459200000
        # 47 days off - no points
        guessed = actual + (47 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 0

    def test_far_off(self):
        actual = 1609459200000
        # 200 days off - no points
        guessed = actual + (200 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 0

    def test_guessed_before_actual(self):
        actual = 1609459200000
        # 10 days before - correct month
        guessed = actual - (10 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 500

    def test_guessed_before_actual_adjacent(self):
        actual = 1609459200000
        # 30 days before - adjacent month
        guessed = actual - (30 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 300


class TestCalculateTotalScore:
    def test_perfect_score(self):
        # Without author
        assert calculate_total_score(True, 1000) == 1500
        # With author correct
        assert calculate_total_score(True, 1000, True) == 2000

    def test_correct_channel_no_time(self):
        assert calculate_total_score(True, 0) == 500

    def test_wrong_channel_perfect_time(self):
        assert calculate_total_score(False, 1000) == 1000

    def test_wrong_channel_no_time(self):
        assert calculate_total_score(False, 0) == 0

    def test_partial_time_score(self):
        assert calculate_total_score(True, 500) == 1000
        assert calculate_total_score(False, 500) == 500

    def test_author_points(self):
        # Author correct adds 500 points
        assert calculate_total_score(True, 1000, True) == 2000
        assert calculate_total_score(True, 1000, False) == 1500
        assert calculate_total_score(False, 0, True) == 500


class TestIsPerfectGuess:
    def test_perfect(self):
        # Perfect requires channel + time + author
        assert is_perfect_guess(True, 1000, True) is True

    def test_perfect_without_author(self):
        # Without author correct, not perfect
        assert is_perfect_guess(True, 1000) is False
        assert is_perfect_guess(True, 1000, False) is False

    def test_wrong_channel(self):
        assert is_perfect_guess(False, 1000, True) is False

    def test_imperfect_time(self):
        assert is_perfect_guess(True, 500, True) is False

    def test_both_wrong(self):
        assert is_perfect_guess(False, 100, False) is False
