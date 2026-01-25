"""Tests for Discord snowflake utilities."""

from datetime import datetime, timezone

from utils.snowflake import (
    DISCORD_EPOCH,
    snowflake_to_timestamp_ms,
    timestamp_ms_to_snowflake,
    snowflake_to_datetime,
    format_timestamp,
)


class TestSnowflakeToTimestampMs:
    def test_known_snowflake(self):
        # Discord's first public message snowflake-ish example
        # Snowflake 175928847299117063 = timestamp around 2016-04-30
        snowflake = 175928847299117063
        result = snowflake_to_timestamp_ms(snowflake)
        # Should be a reasonable timestamp (after Discord epoch, before now)
        assert result > DISCORD_EPOCH
        assert result < 2000000000000  # Before year 2033

    def test_string_input(self):
        snowflake = "175928847299117063"
        result = snowflake_to_timestamp_ms(snowflake)
        assert result > DISCORD_EPOCH

    def test_epoch_snowflake(self):
        # A snowflake with timestamp 0 (Discord epoch)
        snowflake = 0
        result = snowflake_to_timestamp_ms(snowflake)
        assert result == DISCORD_EPOCH

    def test_roundtrip(self):
        # Create a timestamp, convert to snowflake, convert back
        original_timestamp = 1609459200000  # 2021-01-01 00:00:00 UTC
        snowflake = timestamp_ms_to_snowflake(original_timestamp)
        result = snowflake_to_timestamp_ms(snowflake)
        assert result == original_timestamp


class TestTimestampMsToSnowflake:
    def test_discord_epoch(self):
        # Converting Discord epoch should give snowflake 0
        result = timestamp_ms_to_snowflake(DISCORD_EPOCH)
        assert result == 0

    def test_known_timestamp(self):
        # 2021-01-01 00:00:00 UTC
        timestamp = 1609459200000
        result = timestamp_ms_to_snowflake(timestamp)
        # Should be a positive number
        assert result > 0
        # Should be 64-bit safe
        assert result < (1 << 64)

    def test_preserves_timestamp_component(self):
        timestamp = 1609459200000
        snowflake = timestamp_ms_to_snowflake(timestamp)
        # When we convert back, we should get the same timestamp
        recovered = snowflake_to_timestamp_ms(snowflake)
        assert recovered == timestamp


class TestSnowflakeToDatetime:
    def test_known_snowflake(self):
        # Create a snowflake from a known timestamp
        known_dt = datetime(2021, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        timestamp_ms = int(known_dt.timestamp() * 1000)
        snowflake = timestamp_ms_to_snowflake(timestamp_ms)

        result = snowflake_to_datetime(snowflake)

        # Should be close (within 1 second due to ms truncation)
        assert result.year == 2021
        assert result.month == 6
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30

    def test_returns_utc(self):
        snowflake = 175928847299117063
        result = snowflake_to_datetime(snowflake)
        assert result.tzinfo == timezone.utc


class TestFormatTimestamp:
    def test_default_style(self):
        timestamp_ms = 1609459200000  # 2021-01-01 00:00:00 UTC
        result = format_timestamp(timestamp_ms)
        assert result == "<t:1609459200:f>"

    def test_relative_style(self):
        timestamp_ms = 1609459200000
        result = format_timestamp(timestamp_ms, "R")
        assert result == "<t:1609459200:R>"

    def test_short_time_style(self):
        timestamp_ms = 1609459200000
        result = format_timestamp(timestamp_ms, "t")
        assert result == "<t:1609459200:t>"

    def test_long_date_style(self):
        timestamp_ms = 1609459200000
        result = format_timestamp(timestamp_ms, "D")
        assert result == "<t:1609459200:D>"
