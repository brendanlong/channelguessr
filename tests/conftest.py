"""Pytest configuration and shared fixtures."""

from unittest.mock import MagicMock

import discord
import pytest


@pytest.fixture
def mock_attachment():
    """Create a mock Discord attachment for testing."""

    class MockAttachment:
        def __init__(self, content_type=None, filename="file.bin", description=None):
            self.content_type = content_type
            self.filename = filename
            self.description = description

    return MockAttachment


@pytest.fixture
def mock_embed():
    """Create a mock Discord embed for testing."""

    class MockEmbedProxy:
        """Stands in for discord.py's EmbedProxy, where missing fields are None."""

        def __init__(self, name=None):
            self.name = name

    class MockEmbed:
        def __init__(self, title=None, description=None, url=None, author_name=None, provider_name=None):
            self.title = title
            self.description = description
            self.url = url
            self.author = MockEmbedProxy(author_name)
            self.provider = MockEmbedProxy(provider_name)

    return MockEmbed


@pytest.fixture
def mock_discord_message():
    """Create a mock Discord message for testing."""

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
            message_id=123456789,
        ):
            self.content = content
            self.author = MockAuthor(bot=author_bot, user_id=author_id)
            self.attachments = attachments or []
            self.embeds = embeds or []
            self.id = message_id
            self.guild = None  # For escape_mentions; None means mentions won't be resolved

    return MockMessage


@pytest.fixture
def mock_guild():
    """Create a mock Discord guild for testing."""

    class MockMember:
        def __init__(self, display_name: str):
            self.display_name = display_name

    class MockRole:
        def __init__(self, name: str):
            self.name = name

    class MockGuild:
        def __init__(
            self,
            members: dict[int, str] | None = None,
            roles: dict[int, str] | None = None,
        ):
            self._members = {user_id: MockMember(name) for user_id, name in (members or {}).items()}
            self._roles = {role_id: MockRole(name) for role_id, name in (roles or {}).items()}

        def get_member(self, user_id: int) -> MockMember | None:
            return self._members.get(user_id)

        async def fetch_member(self, user_id: int) -> MockMember:
            member = self._members.get(user_id)
            if member is not None:
                return member
            response = MagicMock()
            response.status = 404
            raise discord.NotFound(response, "Unknown Member")

        def get_role(self, role_id: int) -> MockRole | None:
            return self._roles.get(role_id)

    return MockGuild
