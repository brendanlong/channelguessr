"""Tests for message selector."""

from bot.services.message_selector import is_interesting_message, URL_PATTERN


class TestUrlPattern:
    def test_matches_http(self):
        assert URL_PATTERN.search("Check out http://example.com")

    def test_matches_https(self):
        assert URL_PATTERN.search("Check out https://example.com")

    def test_matches_with_path(self):
        assert URL_PATTERN.search("See https://example.com/path/to/page")

    def test_matches_with_query(self):
        assert URL_PATTERN.search("Link: https://example.com?foo=bar")

    def test_no_match_without_protocol(self):
        assert not URL_PATTERN.search("Visit example.com")

    def test_no_match_plain_text(self):
        assert not URL_PATTERN.search("Just some plain text")


class TestIsInterestingMessage:
    def test_bot_message_not_interesting(self, mock_discord_message):
        msg = mock_discord_message(content="A" * 500, author_bot=True)
        assert is_interesting_message(msg) is False

    def test_long_message_is_interesting(self, mock_discord_message):
        # 200+ characters
        msg = mock_discord_message(content="A" * 200)
        assert is_interesting_message(msg) is True

    def test_short_message_not_interesting(self, mock_discord_message):
        msg = mock_discord_message(content="Short message")
        assert is_interesting_message(msg) is False

    def test_message_with_attachment_is_interesting(self, mock_discord_message):
        class MockAttachment:
            content_type = "image/png"

        msg = mock_discord_message(content="check this out", attachments=[MockAttachment()])
        assert is_interesting_message(msg) is True

    def test_message_with_embed_is_interesting(self, mock_discord_message):
        class MockEmbed:
            pass

        msg = mock_discord_message(content="", embeds=[MockEmbed()])
        assert is_interesting_message(msg) is True

    def test_message_with_url_is_interesting(self, mock_discord_message):
        msg = mock_discord_message(content="Check out https://example.com")
        assert is_interesting_message(msg) is True

    def test_empty_message_not_interesting(self, mock_discord_message):
        msg = mock_discord_message(content="")
        assert is_interesting_message(msg) is False

    def test_borderline_length(self, mock_discord_message):
        # Exactly 199 characters - not enough
        msg = mock_discord_message(content="A" * 199)
        assert is_interesting_message(msg) is False

        # Exactly 200 characters - enough
        msg = mock_discord_message(content="A" * 200)
        assert is_interesting_message(msg) is True
