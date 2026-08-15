"""Message formatting utilities for the game display."""

import random
import re
from collections.abc import Sequence
from typing import Literal

import discord

from bot.services.scoring_service import calculate_total_score, is_perfect_guess
from models import Guess, PlayerScore
from utils.discord_utils import get_or_fetch_member

# URL pattern for detecting links
URL_PATTERN = re.compile(r"https?://\S+")

# Discord mention patterns (user and role mentions)
USER_MENTION_PATTERN = re.compile(r"<@!?(\d+)>")
ROLE_MENTION_PATTERN = re.compile(r"<@&(\d+)>")

# Discord message limit
DISCORD_MAX_LENGTH = 2000

# How much of a message's own text we show
MAX_CONTENT_LENGTH = 500

# How much of an attachment/embed description we show. Short, because a message
# can carry several of them and they're only meant to be a hint.
MAX_LABEL_LENGTH = 60

# A message can carry ten attachments plus link previews; describing them all
# would crowd out the rest of the round, so the tail is summarized as a count
MAX_MARKERS = 4

# Filenames Discord or a phone camera made up, which say nothing about the
# message. Compared against the stem with everything but letters stripped, so
# "IMG_12" and "Screenshot at" collapse into this set too.
GENERIC_FILENAME_STEMS = frozenset(
    {
        "attachment",
        "clipboard",
        "download",
        "dsc",
        "file",
        "gif",
        "image",
        "img",
        "mov",
        "paste",
        "pastedimage",
        "photo",
        "pxl",
        "screenshot",
        "screenshotat",
        "unknown",
        "untitled",
        "vid",
        "video",
    }
)

# A run of digits in a filename is nearly always a date or timestamp
# ("Screenshot 2026-08-14 at 3.42 PM", "IMG_20240101_123456"), which would give
# away the round's when-was-this-posted half, so those filenames are dropped.
FILENAME_DIGIT_RUN_PATTERN = re.compile(r"\d{4}")


def suppress_url_embeds(text: str) -> str:
    """Wrap URLs in angle brackets to suppress Discord embeds."""
    return URL_PATTERN.sub(r"<\g<0>>", text)


def escape_mentions(text: str, guild: discord.Guild | None) -> str:
    """Escape Discord mentions to prevent notifications.

    Resolves user mentions to `@username` format and role mentions to
    `@rolename` format, wrapped in backticks to prevent pinging.
    """

    def replace_user_mention(match: re.Match[str]) -> str:
        user_id = int(match.group(1))
        if guild:
            member = guild.get_member(user_id)
            if member:
                return f"`@{member.display_name}`"
        return "`@user`"

    def replace_role_mention(match: re.Match[str]) -> str:
        role_id = int(match.group(1))
        if guild:
            role = guild.get_role(role_id)
            if role:
                return f"`@{role.name}`"
        return "`@role`"

    text = USER_MENTION_PATTERN.sub(replace_user_mention, text)
    text = ROLE_MENTION_PATTERN.sub(replace_role_mention, text)
    return text


def anonymize_usernames(
    messages: Sequence[discord.Message],
) -> dict[int, str]:
    """Create a mapping of user IDs to anonymized names (User A, User B, etc.)."""
    unique_authors = []
    for msg in messages:
        if msg.author.id not in unique_authors:
            unique_authors.append(msg.author.id)

    return {
        user_id: f"User {chr(65 + i)}"  # A, B, C, ...
        for i, user_id in enumerate(unique_authors)
    }


def _truncate(text: str, max_length: int) -> str:
    """Shorten text to max_length, marking it with an ellipsis if cut."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _clean_label(text: str, guild: discord.Guild | None) -> str:
    """Make untrusted text safe to drop inline in the quoted message display."""
    # Collapse newlines so a multi-line description can't escape the blockquote
    text = " ".join(text.split())
    text = escape_mentions(text, guild)
    text = suppress_url_embeds(text)
    # Brackets would be confused with our own [image]/[embed] markers
    text = text.replace("[", "(").replace("]", ")")
    return _truncate(text.strip(), MAX_LABEL_LENGTH)


def _filename_label(filename: str) -> str | None:
    """Describe an attachment by its filename, or None if it says nothing useful."""
    stem = filename.removeprefix("SPOILER_").rsplit(".", 1)[0]
    if FILENAME_DIGIT_RUN_PATTERN.search(stem):
        return None
    if re.sub(r"[^a-z]", "", stem.lower()) in GENERIC_FILENAME_STEMS:
        return None
    return stem


def _describe_attachment(attachment: discord.Attachment, guild: discord.Guild | None) -> str:
    """Build the display marker for one attachment, e.g. `[image: a cat]`."""
    content_type = attachment.content_type or ""
    if content_type.startswith("image/"):
        kind = "image"
    elif content_type.startswith("video/"):
        kind = "video"
    elif content_type.startswith("audio/"):
        kind = "audio"
    elif content_type:
        kind = "file"
    else:
        kind = "attachment"

    # Alt text is written by the poster, so it beats the filename when present
    label = attachment.description or _filename_label(attachment.filename)
    if not label:
        return f"[{kind}]"
    return f"[{kind}: {_clean_label(label, guild)}]"


def _describe_embed(embed: discord.Embed, guild: discord.Guild | None) -> str:
    """Build the display marker for one embed, e.g. `[embed: Article title]`.

    Link previews carry the only description of a link-only message, so showing
    the title (or whatever stands in for it) is often the difference between a
    guessable round and a blank one.
    """
    label = embed.title or embed.author.name or embed.provider.name or embed.description
    if not label:
        return "[embed]"
    return f"[embed: {_clean_label(label, guild)}]"


def format_message_content(
    message: discord.Message,
    anonymized_name: str,
    include_attachments: bool = True,
) -> str:
    """Format a single message for display."""
    content = message.content or ""

    # Escape mentions to prevent notifications
    content = escape_mentions(content, message.guild)

    # Suppress URL embeds by wrapping in angle brackets
    content = suppress_url_embeds(content)

    # Truncate before adding the markers below, so a wall of text can't push
    # them out of the display entirely
    parts = [_truncate(content, MAX_CONTENT_LENGTH)] if content else []

    markers = []
    if include_attachments:
        markers.extend(_describe_attachment(attachment, message.guild) for attachment in message.attachments)
    markers.extend(_describe_embed(embed, message.guild) for embed in message.embeds)

    if len(markers) > MAX_MARKERS:
        hidden = len(markers) - MAX_MARKERS
        markers = markers[:MAX_MARKERS] + [f"[+{hidden} more]"]
    parts.extend(markers)

    return f"> **{anonymized_name}:** {' '.join(parts).strip()}".rstrip()


def format_game_message(
    target_message: discord.Message,
    before_messages: Sequence[discord.Message],
    after_messages: Sequence[discord.Message],
    round_number: int,
    timeout_seconds: int,
) -> str:
    """Format the complete game message display.

    Ensures the output fits within Discord's 2000 character limit by
    progressively reducing context messages if needed.
    """
    # Convert to mutable lists we can trim
    before_list = list(before_messages)
    after_list = list(after_messages)

    # Try building the message, reducing context if it's too long
    while True:
        result = _build_game_message(target_message, before_list, after_list, round_number, timeout_seconds)

        if len(result) <= DISCORD_MAX_LENGTH:
            return result

        # Message too long - reduce context
        # Remove from both ends evenly, preferring to keep messages closer to target
        if len(before_list) > 0 and len(before_list) >= len(after_list):
            before_list.pop(0)  # Remove oldest context
        elif len(after_list) > 0:
            after_list.pop()  # Remove newest context
        else:
            # No more context to remove - truncate the target message more aggressively
            # This shouldn't normally happen, but handle it gracefully
            break

    return result


def _build_game_message(
    target_message: discord.Message,
    before_messages: Sequence[discord.Message],
    after_messages: Sequence[discord.Message],
    round_number: int,
    timeout_seconds: int,
) -> str:
    """Build the game message without length checking."""
    # Combine all messages for anonymization
    all_messages = list(before_messages) + [target_message] + list(after_messages)
    user_map = anonymize_usernames(all_messages)

    lines = [
        f"# CHANNELGUESSR — Round {round_number}",
        "",
    ]

    # Context before
    if before_messages:
        lines.append("**Context Before**")
        for msg in before_messages:
            anon_name = user_map[msg.author.id]
            lines.append(format_message_content(msg, anon_name))
        lines.append("")

    # Target message (highlighted)
    lines.append("🎯 **Mystery Message**")
    anon_name = user_map[target_message.author.id]
    lines.append(format_message_content(target_message, anon_name))
    lines.append("")

    # Context after
    if after_messages:
        lines.append("**Context After**")
        for msg in after_messages:
            anon_name = user_map[msg.author.id]
            lines.append(format_message_content(msg, anon_name))
        lines.append("")

    lines.extend(
        [
            "---",
            "**Which channel?** Use `/guess`",
            "**When was this posted?**",
            f"You have {timeout_seconds} seconds!",
        ]
    )

    return "\n".join(lines)


def format_round_results(
    target_channel: discord.abc.GuildChannel | discord.Thread | None,
    target_timestamp_ms: int,
    target_message_id: str,
    target_author_display_name: str | None,
    guesses: list[Guess],
    guild: discord.Guild,
) -> str:
    """Format the results of a completed round."""
    from utils.snowflake import format_timestamp

    channel_id = target_channel.id if target_channel else 0
    message_link = f"https://discord.com/channels/{guild.id}/{channel_id}/{target_message_id}"

    author_display = f"`@{target_author_display_name}`" if target_author_display_name else "`@unknown`"

    channel_mention = target_channel.mention if target_channel else "#unknown"
    lines = [
        "# Round Complete!",
        "",
        f"📍 **Channel:** {channel_mention}",
        f"**Posted:** {format_timestamp(target_timestamp_ms, 'f')} ({format_timestamp(target_timestamp_ms, 'R')})",
        f"**Author:** {author_display}",
        f"**Message:** [Jump to message]({message_link})",
        "",
    ]

    if guesses:
        lines.append("**Results:**")

        # Calculate scores once upfront
        guesses_with_scores = [
            (g, calculate_total_score(g.channel_correct or False, g.time_score or 0, g.author_correct or False))
            for g in guesses
        ]

        def sort_key(v: tuple[Guess, int]) -> tuple[int, float]:
            return (v[1], random.random())

        # Sort by total score descending, with random tie-breaking
        sorted_guesses = sorted(guesses_with_scores, key=sort_key, reverse=True)

        for i, (guess, total_score) in enumerate(sorted_guesses, 1):
            player_id = guess.player_id
            channel_correct = guess.channel_correct or False
            time_score = guess.time_score or 0
            author_correct = guess.author_correct or False

            details = []

            channel_emoji = "✅" if channel_correct else "❌"
            details.append(f"Channel: {channel_emoji}")

            time_result = "❌" if time_score == 0 else f"+{time_score}"
            details.append(f"Time: {time_result}")

            # Format author guess
            if guess.guessed_author_id:
                author_emoji = "✅" if author_correct else "❌"
                details.append(f"Author: {author_emoji}")

            # Add lion for perfect guesses (for Laura)
            perfect_indicator = " 🦁" if is_perfect_guess(channel_correct, time_score, author_correct) else ""
            lines.append(f"{i}. <@{player_id}>: **{total_score}** pts ({', '.join(details)}){perfect_indicator}")
    else:
        lines.append("*No guesses submitted!*")

    return "\n".join(lines)


async def format_leaderboard(
    players: list[PlayerScore],
    guild: discord.Guild,
    title: str = "Leaderboard",
    sort_by: Literal["total", "average"] = "total",
    limit: int = 10,
) -> str:
    """Format the leaderboard display.

    Args:
        players: List of player scores to display.
        guild: The guild to format for.
        title: The title to show at the top.
        sort_by: Sort and display by "total" score or "average" score per round.
        limit: Maximum number of players to show.
    """
    lines = [
        f"# 🏆 {title}",
        "",
    ]

    if not players:
        lines.append("*No players yet! Start a game with `/start`*")
        return "\n".join(lines)

    # Sort players
    def avg_score(p: PlayerScore) -> float:
        return p.total_score / p.rounds_played if p.rounds_played > 0 else 0

    if sort_by == "average":
        sorted_players = sorted(players, key=avg_score, reverse=True)
    else:
        sorted_players = sorted(players, key=lambda p: p.total_score, reverse=True)

    medals = ["🥇", "🥈", "🥉"]

    for i, player in enumerate(sorted_players[:limit]):
        medal = medals[i] if i < 3 else f"{i + 1}."
        player_id = player.player_id
        rounds_played = player.rounds_played
        perfect = player.perfect_guesses

        # Escape the mention to avoid pinging users
        member = await get_or_fetch_member(guild, int(player_id))
        player_display = f"`@{member.display_name}`" if member else "`@user`"

        if sort_by == "average":
            score_display = f"**{avg_score(player):.0f}** pts/game"
        else:
            score_display = f"**{player.total_score:,}** pts"

        lines.append(f"{medal} {player_display} - {score_display} ({rounds_played} games, {perfect} perfect)")

    return "\n".join(lines)


def format_player_stats(
    stats: PlayerScore | None,
    player: discord.Member | discord.User,
    rank: int,
) -> str:
    """Format a player's stats display."""
    if not stats:
        return f"**{player.display_name}** hasn't played any games yet!"

    total_score = stats.total_score
    rounds_played = stats.rounds_played
    perfect = stats.perfect_guesses
    avg_score = total_score / rounds_played if rounds_played > 0 else 0

    lines = [
        f"## 📊 Stats for {player.display_name}",
        "",
        f"**Rank:** #{rank}",
        f"**Total Score:** {total_score:,} pts",
        f"**Games Played:** {rounds_played}",
        f"**Average Score:** {avg_score:.0f} pts/game",
        f"**Perfect Guesses:** {perfect}",
    ]

    return "\n".join(lines)


def format_time_warning(seconds_remaining: int) -> str:
    """Format a time warning message for the game round."""
    return f"⏰ **{seconds_remaining} seconds remaining!** Submit your guess with `/guess`"
