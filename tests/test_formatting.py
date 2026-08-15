"""Tests for message formatting utilities."""

from models import PlayerScore
from utils.formatting import (
    DISCORD_MAX_LENGTH,
    MAX_LABEL_LENGTH,
    escape_mentions,
    format_game_message,
    format_leaderboard,
    format_message_content,
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

    def test_marker_heavy_round_fits_limit(self, mock_discord_message, mock_attachment, mock_embed):
        """Markers make each line longer; the round must still fit Discord's limit."""

        def loaded(author_id):
            return mock_discord_message(
                content="Y" * 2000,
                author_id=author_id,
                attachments=[
                    mock_attachment(content_type="image/png", filename="a-descriptive-name.png", description="z" * 500)
                    for _ in range(10)
                ],
                embeds=[mock_embed(title="W" * 500) for _ in range(5)],
            )

        result = format_game_message(
            loaded(1), [loaded(i) for i in range(2, 7)], [loaded(i) for i in range(7, 12)], 1, 60
        )

        assert len(result) <= DISCORD_MAX_LENGTH


class TestAttachmentMarkers:
    """Tests for how attachments are described in the message display."""

    def test_kind_from_content_type(self, mock_discord_message, mock_attachment):
        """Attachments are labelled by their broad media type."""
        cases = [
            ("image/png", "[image]"),
            ("video/mp4", "[video]"),
            ("audio/ogg", "[audio]"),
            ("application/pdf", "[file]"),
            (None, "[attachment]"),
        ]
        for content_type, expected in cases:
            message = mock_discord_message(attachments=[mock_attachment(content_type=content_type)])
            assert format_message_content(message, "User A").endswith(expected)

    def test_alt_text_is_shown(self, mock_discord_message, mock_attachment):
        """Poster-written alt text is the best description we have."""
        attachment = mock_attachment(content_type="image/png", filename="IMG_4821.png", description="a very smug cat")
        message = mock_discord_message(attachments=[attachment])

        assert "[image: a very smug cat]" in format_message_content(message, "User A")

    def test_informative_filename_is_shown(self, mock_discord_message, mock_attachment):
        """A filename someone chose deliberately is worth showing."""
        attachment = mock_attachment(content_type="image/png", filename="deployment-diagram.png")
        message = mock_discord_message(attachments=[attachment])

        assert "[image: deployment-diagram]" in format_message_content(message, "User A")

    def test_generic_filenames_are_dropped(self, mock_discord_message, mock_attachment):
        """Auto-generated filenames say nothing, so they're left off."""
        for filename in ["image.png", "unknown.png", "IMG_12.jpg", "Screenshot at.png", "p.png", "1.png"]:
            message = mock_discord_message(attachments=[mock_attachment(content_type="image/png", filename=filename)])
            assert format_message_content(message, "User A").endswith("[image]"), filename

    def test_dated_filenames_are_dropped(self, mock_discord_message, mock_attachment):
        """Filenames with timestamps would give away when the message was posted."""
        dated = [
            "Screenshot 2026-08-14 at 3.42.01 PM.png",
            "PXL_20240101_123456.jpg",
            "vacation-2019.png",
            "vacation-8-14-26.jpg",
            "screen shot aug 14.png",
        ]
        for filename in dated:
            message = mock_discord_message(attachments=[mock_attachment(content_type="image/png", filename=filename)])
            assert format_message_content(message, "User A").endswith("[image]"), filename

    def test_spoilers_are_not_described(self, mock_discord_message, mock_attachment):
        """A poster who hid an image doesn't get it described in the round."""
        attachment = mock_attachment(
            content_type="image/png",
            filename="SPOILER_ending-explained.png",
            description="the killer's identity",
        )
        result = format_message_content(mock_discord_message(attachments=[attachment]), "User A")

        assert result.endswith("[spoiler image]")
        assert "ending" not in result
        assert "killer" not in result

    def test_label_is_sanitized(self, mock_discord_message, mock_attachment):
        """Untrusted labels can't ping, embed, or break out of the quote block."""
        attachment = mock_attachment(
            content_type="image/png",
            description="ping <@99>\nvia https://example.com [note]",
        )
        result = format_message_content(mock_discord_message(attachments=[attachment]), "User A")

        assert "<@99>" not in result
        assert "\n" not in result
        assert "<https://example.com>" in result
        assert "(note)" in result

    def test_label_cannot_ping_everyone(self, mock_discord_message, mock_attachment):
        """A link preview title is written by whoever owns the site, not the poster.

        The backticks are belt-and-braces; the round is also sent with
        allowed_mentions=none, which is what actually stops the ping.
        """
        attachment = mock_attachment(content_type="image/png", description="hey @everyone and @here")
        result = format_message_content(mock_discord_message(attachments=[attachment]), "User A")

        assert "`@everyone`" in result
        assert "`@here`" in result

    def test_label_markdown_is_escaped(self, mock_discord_message, mock_attachment, mock_embed):
        """An unclosed backtick would otherwise swallow the markers after it."""
        message = mock_discord_message(
            attachments=[mock_attachment(content_type="image/png", description="a ` and **bold**")],
            embeds=[mock_embed(title="Cats")],
        )
        result = format_message_content(message, "User A")

        assert "\\`" in result
        assert result.endswith("[embed: Cats]")

    def test_whitespace_only_label_falls_back(self, mock_discord_message, mock_attachment):
        """A label that cleans down to nothing shouldn't render as `[image: ]`."""
        attachment = mock_attachment(content_type="image/png", description="   ")
        result = format_message_content(mock_discord_message(attachments=[attachment]), "User A")

        assert result.endswith("[image]")

    def test_long_label_is_truncated(self, mock_discord_message, mock_attachment):
        """A rambling alt text can't crowd out the rest of the round."""
        attachment = mock_attachment(content_type="image/png", description="z" * 500)
        result = format_message_content(mock_discord_message(attachments=[attachment]), "User A")

        assert len(result) < MAX_LABEL_LENGTH + 50

    def test_truncated_url_cannot_embed(self, mock_discord_message, mock_attachment):
        """Cutting a label after wrapping URLs would leave an unclosed bracket."""
        attachment = mock_attachment(
            content_type="image/png",
            description="see https://example.com/a-very-long-path-that-goes-on-and-on-forever",
        )
        label = format_message_content(mock_discord_message(attachments=[attachment]), "User A").split("**", 2)[2]

        assert label.count("<") == label.count(">")

    def test_attachments_can_be_excluded(self, mock_discord_message, mock_attachment):
        """include_attachments=False leaves attachment markers off entirely."""
        message = mock_discord_message(attachments=[mock_attachment(content_type="image/png")])

        assert format_message_content(message, "User A", include_attachments=False) == "> **User A:**"

    def test_many_attachments_are_summarized(self, mock_discord_message, mock_attachment):
        """Beyond a handful, the tail becomes a count."""
        attachments = [mock_attachment(content_type="image/png") for _ in range(10)]
        result = format_message_content(mock_discord_message(attachments=attachments), "User A")

        assert result.count("[image]") == 4
        assert "[+6 more]" in result

    def test_attachments_do_not_crowd_out_embeds(self, mock_discord_message, mock_attachment, mock_embed):
        """The embed title is usually the best clue, so images can't take its slot."""
        message = mock_discord_message(
            attachments=[mock_attachment(content_type="image/png") for _ in range(6)],
            embeds=[mock_embed(title="Important Article")],
        )
        result = format_message_content(message, "User A")

        assert "[+2 more]" in result
        assert result.endswith("[embed: Important Article]")


class TestEmbedMarkers:
    """Tests for how embeds are described in the message display."""

    def test_title_is_shown(self, mock_discord_message, mock_embed):
        """The link preview title is often the only clue a link-only message has."""
        message = mock_discord_message(embeds=[mock_embed(title="The Bad Place")])

        assert "[embed: The Bad Place]" in format_message_content(message, "User A")

    def test_falls_back_through_author_provider_description(self, mock_discord_message, mock_embed):
        """Without a title, anything naming the content beats a bare marker."""
        cases = [
            (mock_embed(author_name="Some Blogger"), "[embed: Some Blogger]"),
            (mock_embed(provider_name="Tenor"), "[embed: Tenor]"),
            (mock_embed(description="A gif of a man falling over"), "[embed: A gif of a man falling over]"),
        ]
        for embed, expected in cases:
            assert expected in format_message_content(mock_discord_message(embeds=[embed]), "User A")

    def test_empty_embed_keeps_bare_marker(self, mock_discord_message, mock_embed):
        """An embed with nothing to say still shows that something was there."""
        message = mock_discord_message(embeds=[mock_embed()])

        assert format_message_content(message, "User A").endswith("[embed]")

    def test_bot_authored_embeds_are_not_described(self, mock_discord_message, mock_embed):
        """Rich embeds are bot metadata, which routinely names a date or channel."""
        embed = mock_embed(title="Daily Digest - August 14, 2026", embed_type="rich")
        message = mock_discord_message(embeds=[embed])

        result = format_message_content(message, "User A")
        assert result.endswith("[embed]")
        assert "August" not in result

    def test_missing_embed_fields_read_as_none(self):
        """Pin the discord.py contract our fallback chain relies on."""
        import discord

        embed = discord.Embed()
        assert embed.title is None
        assert embed.author.name is None
        assert embed.provider.name is None

        from_payload = discord.Embed.from_dict({"type": "link", "provider": {"name": "Tenor"}})
        assert from_payload.title is None
        assert from_payload.author.name is None
        assert from_payload.provider.name == "Tenor"

    def test_content_and_markers_combine(self, mock_discord_message, mock_attachment, mock_embed):
        """Text, attachments and embeds all appear on one line."""
        message = mock_discord_message(
            content="look at this",
            attachments=[mock_attachment(content_type="image/png", description="a cat")],
            embeds=[mock_embed(title="Cats")],
        )

        assert format_message_content(message, "User A") == "> **User A:** look at this [image: a cat] [embed: Cats]"

    def test_markers_survive_long_content(self, mock_discord_message, mock_embed):
        """Truncating a wall of text must not drop the markers after it."""
        message = mock_discord_message(content="X" * 1000, embeds=[mock_embed(title="Cats")])

        assert format_message_content(message, "User A").endswith("[embed: Cats]")


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

    def test_channel_mentions_are_anonymized(self):
        """A live channel link in the round would hand players the answer."""
        result = escape_mentions("Check out <#123456789>!", None)

        assert result == "Check out `#channel`!"

    def test_everyone_mentions_are_defused(self):
        """@everyone/@here aren't <> mentions, so they need their own escaping."""
        result = escape_mentions("hey @everyone @here", None)

        assert result == "hey `@everyone` `@here`"


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

    async def test_sorts_by_total_score_by_default(self, mock_guild):
        """Leaderboard sorts by total score descending by default."""
        players = [
            PlayerScore(guild_id="123", player_id="1", total_score=500, rounds_played=1, perfect_guesses=0),
            PlayerScore(guild_id="123", player_id="2", total_score=1000, rounds_played=1, perfect_guesses=0),
            PlayerScore(guild_id="123", player_id="3", total_score=750, rounds_played=1, perfect_guesses=0),
        ]
        guild = mock_guild(members={1: "Player1", 2: "Player2", 3: "Player3"})

        result = await format_leaderboard(players, guild)

        # Check order in output: player2 (1000) > player3 (750) > player1 (500)
        # Mentions are escaped as `@DisplayName`
        pos_2 = result.find("`@Player2`")
        pos_3 = result.find("`@Player3`")
        pos_1 = result.find("`@Player1`")
        assert pos_2 < pos_3 < pos_1

    async def test_sorts_by_average_when_requested(self, mock_guild):
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

        result = await format_leaderboard(players, guild, sort_by="average")

        # By average: player2 (750) > player1 (500) = player3 (500)
        # player2 should be first
        # Mentions are escaped as `@DisplayName`
        pos_2 = result.find("`@Player2`")
        pos_1 = result.find("`@Player1`")
        pos_3 = result.find("`@Player3`")
        assert pos_2 < pos_1
        assert pos_2 < pos_3

    async def test_respects_limit(self, mock_guild):
        """Leaderboard respects the limit parameter."""
        players = [
            PlayerScore(guild_id="123", player_id=str(i), total_score=i * 100, rounds_played=1, perfect_guesses=0)
            for i in range(1, 20)
        ]
        # Create members for players 14-19 (the ones we're checking for)
        members = {i: f"Player{i}" for i in range(14, 20)}
        guild = mock_guild(members=members)

        result = await format_leaderboard(players, guild, limit=5)

        # Should only show top 5 (players 19, 18, 17, 16, 15 by score)
        # Mentions are escaped as `@DisplayName`
        assert "`@Player19`" in result
        assert "`@Player15`" in result
        assert "`@Player14`" not in result

    async def test_shows_average_format_when_sorting_by_average(self, mock_guild):
        """Display format changes when sorting by average."""
        players = [
            PlayerScore(guild_id="123", player_id="1", total_score=1000, rounds_played=2, perfect_guesses=0),
        ]
        guild = mock_guild()

        result = await format_leaderboard(players, guild, sort_by="average")

        # Should show "pts/game" format
        assert "pts/game" in result
        assert "500" in result  # 1000 / 2 = 500 avg

    async def test_empty_leaderboard(self, mock_guild):
        """Empty leaderboard shows appropriate message."""
        guild = mock_guild()

        result = await format_leaderboard([], guild)

        assert "No players yet" in result
