"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def mock_discord_message():
    """Create a mock Discord message for testing."""

    class MockAttachment:
        def __init__(self, content_type=None):
            self.content_type = content_type

    class MockAuthor:
        def __init__(self, bot=False, user_id=12345):
            self.bot = bot
            self.id = user_id

    class MockMessage:
        def __init__(
            self,
            content="",
            author_bot=False,
            attachments=None,
            embeds=None,
            author_id=12345,
        ):
            self.content = content
            self.author = MockAuthor(bot=author_bot, user_id=author_id)
            self.attachments = attachments or []
            self.embeds = embeds or []
            self.id = 123456789

    return MockMessage
