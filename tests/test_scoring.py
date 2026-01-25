"""Tests for scoring service."""

from bot.services.scoring_service import (
    calculate_time_score,
    calculate_total_score,
    is_perfect_guess,
)


class TestCalculateTimeScore:
    def test_exact_match(self):
        # Guessed exactly right
        actual = 1609459200000
        guessed = 1609459200000
        assert calculate_time_score(guessed, actual) == 500

    def test_within_one_day(self):
        actual = 1609459200000
        # 12 hours off
        guessed = actual + (12 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 500

    def test_exactly_one_day(self):
        actual = 1609459200000
        # Exactly 1 day (24 hours) - should still be 500
        guessed = actual + (24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 500

    def test_within_one_week(self):
        actual = 1609459200000
        # 3 days off
        guessed = actual + (3 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 400

    def test_within_one_month(self):
        actual = 1609459200000
        # 15 days off
        guessed = actual + (15 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 300

    def test_within_three_months(self):
        actual = 1609459200000
        # 60 days off
        guessed = actual + (60 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 200

    def test_within_six_months(self):
        actual = 1609459200000
        # 120 days off
        guessed = actual + (120 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 100

    def test_within_one_year(self):
        actual = 1609459200000
        # 300 days off
        guessed = actual + (300 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 50

    def test_over_one_year(self):
        actual = 1609459200000
        # 400 days off
        guessed = actual + (400 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 0

    def test_guessed_before_actual(self):
        actual = 1609459200000
        # 3 days before
        guessed = actual - (3 * 24 * 60 * 60 * 1000)
        assert calculate_time_score(guessed, actual) == 400


class TestCalculateTotalScore:
    def test_perfect_score(self):
        # Without author
        assert calculate_total_score(True, 500) == 1000
        # With author correct
        assert calculate_total_score(True, 500, True) == 1500

    def test_correct_channel_no_time(self):
        assert calculate_total_score(True, 0) == 500

    def test_wrong_channel_perfect_time(self):
        assert calculate_total_score(False, 500) == 500

    def test_wrong_channel_no_time(self):
        assert calculate_total_score(False, 0) == 0

    def test_partial_time_score(self):
        assert calculate_total_score(True, 300) == 800
        assert calculate_total_score(False, 300) == 300

    def test_author_points(self):
        # Author correct adds 500 points
        assert calculate_total_score(True, 500, True) == 1500
        assert calculate_total_score(True, 500, False) == 1000
        assert calculate_total_score(False, 0, True) == 500


class TestIsPerfectGuess:
    def test_perfect(self):
        # Perfect requires channel + time + author
        assert is_perfect_guess(True, 500, True) is True

    def test_perfect_without_author(self):
        # Without author correct, not perfect
        assert is_perfect_guess(True, 500) is False
        assert is_perfect_guess(True, 500, False) is False

    def test_wrong_channel(self):
        assert is_perfect_guess(False, 500, True) is False

    def test_imperfect_time(self):
        assert is_perfect_guess(True, 400, True) is False

    def test_both_wrong(self):
        assert is_perfect_guess(False, 100, False) is False
