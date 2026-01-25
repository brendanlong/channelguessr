"""Tests for time parsing in game service."""

from datetime import datetime, timezone

from bot.services.game_service import GameService


class TestParseTimeGuess:
    """Test the _parse_time_guess method."""

    def setup_method(self):
        # Create a GameService instance without bot/db for testing the parser
        self.service = GameService.__new__(GameService)

    def test_iso_format(self):
        result = self.service._parse_time_guess("2024-06-15")
        expected = datetime(2024, 6, 15, tzinfo=timezone.utc)
        assert result == int(expected.timestamp() * 1000)

    def test_iso_format_with_spaces(self):
        result = self.service._parse_time_guess("  2024-06-15  ")
        expected = datetime(2024, 6, 15, tzinfo=timezone.utc)
        assert result == int(expected.timestamp() * 1000)

    def test_month_year_full(self):
        result = self.service._parse_time_guess("March 2024")
        expected = datetime(2024, 3, 15, tzinfo=timezone.utc)
        assert result == int(expected.timestamp() * 1000)

    def test_month_year_abbreviated(self):
        result = self.service._parse_time_guess("Jan 2023")
        expected = datetime(2023, 1, 15, tzinfo=timezone.utc)
        assert result == int(expected.timestamp() * 1000)

    def test_month_year_case_insensitive(self):
        result = self.service._parse_time_guess("DECEMBER 2022")
        expected = datetime(2022, 12, 15, tzinfo=timezone.utc)
        assert result == int(expected.timestamp() * 1000)

    def test_month_day_year_full(self):
        result = self.service._parse_time_guess("January 15 2023")
        expected = datetime(2023, 1, 15, tzinfo=timezone.utc)
        assert result == int(expected.timestamp() * 1000)

    def test_month_day_year_abbreviated(self):
        result = self.service._parse_time_guess("Jan 15 2023")
        expected = datetime(2023, 1, 15, tzinfo=timezone.utc)
        assert result == int(expected.timestamp() * 1000)

    def test_month_day_year_with_ordinal(self):
        result = self.service._parse_time_guess("Jan 1st 2023")
        expected = datetime(2023, 1, 1, tzinfo=timezone.utc)
        assert result == int(expected.timestamp() * 1000)

    def test_month_day_year_with_comma(self):
        result = self.service._parse_time_guess("January 15, 2023")
        expected = datetime(2023, 1, 15, tzinfo=timezone.utc)
        assert result == int(expected.timestamp() * 1000)

    def test_just_year(self):
        result = self.service._parse_time_guess("2023")
        # Should default to middle of year (June 15)
        expected = datetime(2023, 6, 15, tzinfo=timezone.utc)
        assert result == int(expected.timestamp() * 1000)

    def test_all_months_full_name(self):
        months = [
            ("January", 1),
            ("February", 2),
            ("March", 3),
            ("April", 4),
            ("May", 5),
            ("June", 6),
            ("July", 7),
            ("August", 8),
            ("September", 9),
            ("October", 10),
            ("November", 11),
            ("December", 12),
        ]
        for month_name, month_num in months:
            result = self.service._parse_time_guess(f"{month_name} 2023")
            expected = datetime(2023, month_num, 15, tzinfo=timezone.utc)
            assert result == int(expected.timestamp() * 1000), f"Failed for {month_name}"

    def test_all_months_abbreviated(self):
        months = [
            ("Jan", 1),
            ("Feb", 2),
            ("Mar", 3),
            ("Apr", 4),
            ("May", 5),
            ("Jun", 6),
            ("Jul", 7),
            ("Aug", 8),
            ("Sep", 9),
            ("Oct", 10),
            ("Nov", 11),
            ("Dec", 12),
        ]
        for month_name, month_num in months:
            result = self.service._parse_time_guess(f"{month_name} 2023")
            expected = datetime(2023, month_num, 15, tzinfo=timezone.utc)
            assert result == int(expected.timestamp() * 1000), f"Failed for {month_name}"

    def test_invalid_format_returns_none(self):
        assert self.service._parse_time_guess("not a date") is None
        assert self.service._parse_time_guess("yesterday") is None
        assert self.service._parse_time_guess("") is None
        assert self.service._parse_time_guess("13/25/2023") is None
