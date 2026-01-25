"""Tests for message formatting utilities."""

import pytest
from utils.formatting import format_game_message, DISCORD_MAX_LENGTH


class TestFormatGameMessage:
    def test_message_under_limit(self, mock_discord_message):
        """Short messages should be formatted without modification."""
        target = mock_discord_message(content="Short message", author_id=1)
        before = [mock_discord_message(content="Before", author_id=2)]
        after = [mock_discord_message(content="After", author_id=3)]

        result = format_game_message(target, before, after, round_number=1, timeout_seconds=60)

        assert len(result) <= DISCORD_MAX_LENGTH
        assert "Short message" in result
        assert "Before" in result
        assert "After" in result

    def test_long_context_is_trimmed(self, mock_discord_message):
        """When context is too long, messages are removed to fit the limit."""
        # Create a message that's 450 chars (close to 500 limit)
        long_content = "A" * 450
        target = mock_discord_message(content=long_content, author_id=1)

        # Create many context messages that would exceed 2000 chars total
        before = [
            mock_discord_message(content=long_content, author_id=i)
            for i in range(2, 7)  # 5 messages
        ]
        after = [
            mock_discord_message(content=long_content, author_id=i)
            for i in range(7, 12)  # 5 messages
        ]

        result = format_game_message(target, before, after, round_number=1, timeout_seconds=60)

        # Result must fit within Discord's limit
        assert len(result) <= DISCORD_MAX_LENGTH
        # Target message should still be present
        assert long_content[:100] in result  # At least part of target

    def test_no_context_still_works(self, mock_discord_message):
        """Message with no context should format correctly."""
        target = mock_discord_message(content="Solo message", author_id=1)

        result = format_game_message(target, [], [], round_number=42, timeout_seconds=60)

        assert len(result) <= DISCORD_MAX_LENGTH
        assert "Solo message" in result
        assert "ROUND #42" in result

    def test_very_long_target_message(self, mock_discord_message):
        """Even with very long target, result should fit limit."""
        # format_message_content truncates to 500 chars, but let's test a very long one
        very_long = "X" * 1000
        target = mock_discord_message(content=very_long, author_id=1)

        result = format_game_message(target, [], [], round_number=1, timeout_seconds=60)

        # Should fit (target gets truncated to 500 by format_message_content)
        assert len(result) <= DISCORD_MAX_LENGTH

    def test_preserves_target_over_context(self, mock_discord_message):
        """The target message should be preserved even when trimming context."""
        unique_target = "UNIQUE_TARGET_CONTENT_HERE"
        target = mock_discord_message(content=unique_target, author_id=1)

        # Lots of long context
        long_content = "B" * 450
        before = [
            mock_discord_message(content=long_content, author_id=i)
            for i in range(2, 7)
        ]
        after = [
            mock_discord_message(content=long_content, author_id=i)
            for i in range(7, 12)
        ]

        result = format_game_message(target, before, after, round_number=1, timeout_seconds=60)

        # Target should always be present
        assert unique_target in result
