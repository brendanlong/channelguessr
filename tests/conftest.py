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

        def get_role(self, role_id: int) -> MockRole | None:
            return self._roles.get(role_id)

    return MockGuild
