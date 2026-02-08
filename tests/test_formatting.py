"""Tests for message formatting utilities."""

from models import PlayerScore
from utils.formatting import (
    DISCORD_MAX_LENGTH,
    escape_mentions,
    format_game_message,
    format_leaderboard,
    format_time_warning,
)


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
        assert "Round 42" in result

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
        before = [mock_discord_message(content=long_content, author_id=i) for i in range(2, 7)]
        after = [mock_discord_message(content=long_content, author_id=i) for i in range(7, 12)]

        result = format_game_message(target, before, after, round_number=1, timeout_seconds=60)

        # Target should always be present
        assert unique_target in result


class TestEscapeMentions:
    """Tests for the escape_mentions function."""

    def test_no_mentions_unchanged(self):
        """Text without mentions should be unchanged."""
        text = "Hello, this is a normal message!"
        result = escape_mentions(text, None)
        assert result == text

    def test_user_mention_without_guild(self):
        """User mentions without guild should become `@user`."""
        text = "Hello <@123456789>!"
        result = escape_mentions(text, None)
        assert result == "Hello `@user`!"

    def test_user_mention_with_nickname_syntax_without_guild(self):
        """User mentions with ! (nickname) should also be escaped."""
        text = "Hello <@!123456789>!"
        result = escape_mentions(text, None)
        assert result == "Hello `@user`!"

    def test_role_mention_without_guild(self):
        """Role mentions without guild should become `@role`."""
        text = "Attention <@&987654321>!"
        result = escape_mentions(text, None)
        assert result == "Attention `@role`!"

    def test_multiple_mentions_without_guild(self):
        """Multiple mentions should all be escaped."""
        text = "Hey <@111> and <@222>, also <@&333>!"
        result = escape_mentions(text, None)
        assert result == "Hey `@user` and `@user`, also `@role`!"

    def test_user_mention_with_guild_member_found(self, mock_guild):
        """User mentions should resolve to member display names when found."""
        guild = mock_guild(members={123456789: "TestUser"})
        text = "Hello <@123456789>!"
        result = escape_mentions(text, guild)
        assert result == "Hello `@TestUser`!"

    def test_user_mention_with_guild_member_not_found(self, mock_guild):
        """User mentions should fall back to `@user` when member not found."""
        guild = mock_guild(members={})
        text = "Hello <@123456789>!"
        result = escape_mentions(text, guild)
        assert result == "Hello `@user`!"

    def test_role_mention_with_guild_role_found(self, mock_guild):
        """Role mentions should resolve to role names when found."""
        guild = mock_guild(roles={987654321: "Moderators"})
        text = "Attention <@&987654321>!"
        result = escape_mentions(text, guild)
        assert result == "Attention `@Moderators`!"

    def test_role_mention_with_guild_role_not_found(self, mock_guild):
        """Role mentions should fall back to `@role` when role not found."""
        guild = mock_guild(roles={})
        text = "Attention <@&987654321>!"
        result = escape_mentions(text, guild)
        assert result == "Attention `@role`!"

    def test_mixed_mentions_with_guild(self, mock_guild):
        """Mix of found and not-found mentions should be handled correctly."""
        guild = mock_guild(
            members={111: "Alice", 222: "Bob"},
            roles={333: "Admins"},
        )
        text = "Hey <@111>, <@222>, <@999>, and <@&333>!"
        result = escape_mentions(text, guild)
        assert result == "Hey `@Alice`, `@Bob`, `@user`, and `@Admins`!"

    def test_channel_mentions_not_escaped(self):
        """Channel mentions (<#id>) should not be modified."""
        text = "Check out <#123456789>!"
        result = escape_mentions(text, None)
        assert result == "Check out <#123456789>!"


class TestFormatTimeWarning:
    """Tests for the format_time_warning function."""

    def test_format_time_warning_10_seconds(self):
        """Test warning message for 10 seconds remaining."""
        result = format_time_warning(10)
        assert "10 seconds remaining" in result
        assert "/guess" in result

    def test_format_time_warning_contains_emoji(self):
        """Test that warning includes a timer emoji."""
        result = format_time_warning(10)
        assert "⏰" in result

    def test_format_time_warning_other_values(self):
        """Test warning message with different second values."""
        result = format_time_warning(5)
        assert "5 seconds remaining" in result


class TestFormatLeaderboard:
    """Tests for format_leaderboard sorting and display."""

    def test_sorts_by_total_score_by_default(self, mock_guild):
        """Leaderboard sorts by total score descending by default."""
        players = [
            PlayerScore(guild_id="123", player_id="1", total_score=500, rounds_played=1, perfect_guesses=0),
            PlayerScore(guild_id="123", player_id="2", total_score=1000, rounds_played=1, perfect_guesses=0),
            PlayerScore(guild_id="123", player_id="3", total_score=750, rounds_played=1, perfect_guesses=0),
        ]
        guild = mock_guild(members={1: "Player1", 2: "Player2", 3: "Player3"})

        result = format_leaderboard(players, guild)

        # Check order in output: player2 (1000) > player3 (750) > player1 (500)
        # Mentions are escaped as `@DisplayName`
        pos_2 = result.find("`@Player2`")
        pos_3 = result.find("`@Player3`")
        pos_1 = result.find("`@Player1`")
        assert pos_2 < pos_3 < pos_1

    def test_sorts_by_average_when_requested(self, mock_guild):
        """Leaderboard sorts by average score when sort_by='average'."""
        players = [
            # player1: 1000 total / 2 rounds = 500 avg
            PlayerScore(guild_id="123", player_id="1", total_score=1000, rounds_played=2, perfect_guesses=0),
            # player2: 750 total / 1 round = 750 avg
            PlayerScore(guild_id="123", player_id="2", total_score=750, rounds_played=1, perfect_guesses=0),
            # player3: 1500 total / 3 rounds = 500 avg
            PlayerScore(guild_id="123", player_id="3", total_score=1500, rounds_played=3, perfect_guesses=0),
        ]
        guild = mock_guild(members={1: "Player1", 2: "Player2", 3: "Player3"})

        result = format_leaderboard(players, guild, sort_by="average")

        # By average: player2 (750) > player1 (500) = player3 (500)
        # player2 should be first
        # Mentions are escaped as `@DisplayName`
        pos_2 = result.find("`@Player2`")
        pos_1 = result.find("`@Player1`")
        pos_3 = result.find("`@Player3`")
        assert pos_2 < pos_1
        assert pos_2 < pos_3

    def test_respects_limit(self, mock_guild):
        """Leaderboard respects the limit parameter."""
        players = [
            PlayerScore(guild_id="123", player_id=str(i), total_score=i * 100, rounds_played=1, perfect_guesses=0)
            for i in range(1, 20)
        ]
        # Create members for players 14-19 (the ones we're checking for)
        members = {i: f"Player{i}" for i in range(14, 20)}
        guild = mock_guild(members=members)

        result = format_leaderboard(players, guild, limit=5)

        # Should only show top 5 (players 19, 18, 17, 16, 15 by score)
        # Mentions are escaped as `@DisplayName`
        assert "`@Player19`" in result
        assert "`@Player15`" in result
        assert "`@Player14`" not in result

    def test_shows_average_format_when_sorting_by_average(self, mock_guild):
        """Display format changes when sorting by average."""
        players = [
            PlayerScore(guild_id="123", player_id="1", total_score=1000, rounds_played=2, perfect_guesses=0),
        ]
        guild = mock_guild()

        result = format_leaderboard(players, guild, sort_by="average")

        # Should show "pts/game" format
        assert "pts/game" in result
        assert "500" in result  # 1000 / 2 = 500 avg

    def test_empty_leaderboard(self, mock_guild):
        """Empty leaderboard shows appropriate message."""
        guild = mock_guild()

        result = format_leaderboard([], guild)

        assert "No players yet" in result
