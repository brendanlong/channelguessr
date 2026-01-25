"""Message formatting utilities for the game display."""

import discord
import re
from typing import Sequence

# URL pattern for detecting links
URL_PATTERN = re.compile(r"https?://\S+")

# Discord message limit
DISCORD_MAX_LENGTH = 2000


def suppress_url_embeds(text: str) -> str:
    """Wrap URLs in angle brackets to suppress Discord embeds."""
    return URL_PATTERN.sub(r"<\g<0>>", text)


def anonymize_usernames(
    messages: Sequence[discord.Message],
) -> dict[int, str]:
    """Create a mapping of user IDs to anonymized names (User_A, User_B, etc.)."""
    unique_authors = []
    for msg in messages:
        if msg.author.id not in unique_authors:
            unique_authors.append(msg.author.id)

    return {
        user_id: f"User_{chr(65 + i)}"  # A, B, C, ...
        for i, user_id in enumerate(unique_authors)
    }


def format_message_content(
    message: discord.Message,
    anonymized_name: str,
    include_attachments: bool = True,
) -> str:
    """Format a single message for display."""
    content = message.content or ""

    # Suppress URL embeds by wrapping in angle brackets
    content = suppress_url_embeds(content)

    # Add attachment indicators
    if include_attachments and message.attachments:
        attachment_types = []
        for attachment in message.attachments:
            if attachment.content_type:
                if attachment.content_type.startswith("image/"):
                    attachment_types.append("[image]")
                elif attachment.content_type.startswith("video/"):
                    attachment_types.append("[video]")
                else:
                    attachment_types.append("[file]")
            else:
                attachment_types.append("[attachment]")
        if attachment_types:
            content = f"{content} {' '.join(attachment_types)}".strip()

    # Add embed indicators
    if message.embeds:
        content = f"{content} [embed]".strip()

    # Truncate very long messages
    max_length = 500
    if len(content) > max_length:
        content = content[: max_length - 3] + "..."

    return f"> **{anonymized_name}:** {content}"


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
        result = _build_game_message(
            target_message, before_list, after_list, round_number, timeout_seconds
        )

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
        "```",
        "╭──────────────────────────────────────╮",
        f"│  CHANNELGUESSR - ROUND #{round_number:<13}│",
        "╰──────────────────────────────────────╯",
        "```",
        "",
    ]

    # Context before
    if before_messages:
        lines.append("**[Context Before]**")
        for msg in before_messages:
            anon_name = user_map[msg.author.id]
            lines.append(format_message_content(msg, anon_name))
        lines.append("")

    # Target message (highlighted)
    lines.append("**[MYSTERY MESSAGE]**")
    anon_name = user_map[target_message.author.id]
    lines.append(format_message_content(target_message, anon_name))
    lines.append("")

    # Context after
    if after_messages:
        lines.append("**[Context After]**")
        for msg in after_messages:
            anon_name = user_map[msg.author.id]
            lines.append(format_message_content(msg, anon_name))
        lines.append("")

    lines.extend(
        [
            "───────────────────────────────────────",
            "**Which channel?** Use `/channelguessr guess`",
            "**When was this posted?**",
            f"You have {timeout_seconds} seconds!",
        ]
    )

    return "\n".join(lines)


def format_round_results(
    target_channel: discord.TextChannel,
    target_timestamp_ms: int,
    target_message_id: str,
    target_author_id: str,
    guesses: list[dict],
    guild: discord.Guild,
) -> str:
    """Format the results of a completed round."""
    from utils.snowflake import format_timestamp

    message_link = f"https://discord.com/channels/{guild.id}/{target_channel.id}/{target_message_id}"

    lines = [
        "```",
        "╭──────────────────────────────────────╮",
        "│        ROUND COMPLETE!               │",
        "╰──────────────────────────────────────╯",
        "```",
        "",
        f"**Channel:** {target_channel.mention}",
        f"**Posted:** {format_timestamp(target_timestamp_ms, 'f')} ({format_timestamp(target_timestamp_ms, 'R')})",
        f"**Author:** <@{target_author_id}>",
        f"**Message:** [Jump to message]({message_link})",
        "",
    ]

    if guesses:
        lines.append("**Results:**")

        # Sort by total score descending
        sorted_guesses = sorted(
            guesses,
            key=lambda g: (
                g.get("channel_correct", False),
                g.get("time_score", 0),
                g.get("author_correct", False),
            ),
            reverse=True,
        )

        for i, guess in enumerate(sorted_guesses, 1):
            player_id = guess["player_id"]
            channel_correct = guess.get("channel_correct", False)
            time_score = guess.get("time_score", 0)
            author_correct = guess.get("author_correct") or False

            # Calculate total score (channel 500 + time + author 500)
            total_score = (500 if channel_correct else 0) + time_score + (500 if author_correct else 0)

            # Get channel mention for guess
            guessed_channel_id = guess.get("guessed_channel_id")
            if guessed_channel_id:
                guessed_channel = guild.get_channel(int(guessed_channel_id))
                channel_text = (
                    guessed_channel.mention if guessed_channel else "Unknown"
                )
            else:
                channel_text = "No guess"

            channel_emoji = "+" if channel_correct else "-"

            # Format author guess
            guessed_author_id = guess.get("guessed_author_id")
            if guessed_author_id:
                author_emoji = "+" if author_correct else "-"
                author_text = f", Author: {author_emoji}"
            else:
                author_text = ""

            lines.append(
                f"{i}. <@{player_id}>: **{total_score}** pts "
                f"(Channel: {channel_emoji} {channel_text}, Time: +{time_score}{author_text})"
            )
    else:
        lines.append("*No guesses submitted!*")

    return "\n".join(lines)


def format_leaderboard(
    players: list[dict],
    guild: discord.Guild,
    title: str = "Leaderboard",
) -> str:
    """Format the leaderboard display."""
    lines = [
        "```",
        "╭──────────────────────────────────────╮",
        f"│  {title:^36}│",
        "╰──────────────────────────────────────╯",
        "```",
        "",
    ]

    if not players:
        lines.append("*No players yet! Start a game with `/channelguessr start`*")
        return "\n".join(lines)

    medals = ["", "", ""]

    for i, player in enumerate(players):
        medal = medals[i] if i < 3 else f"{i + 1}."
        player_id = player["player_id"]
        total_score = player["total_score"]
        rounds_played = player["rounds_played"]
        perfect = player["perfect_guesses"]

        lines.append(
            f"{medal} <@{player_id}> - **{total_score:,}** pts "
            f"({rounds_played} games, {perfect} perfect)"
        )

    return "\n".join(lines)


def format_player_stats(
    stats: dict | None,
    player: discord.Member | discord.User,
    rank: int,
) -> str:
    """Format a player's stats display."""
    if not stats:
        return f"**{player.display_name}** hasn't played any games yet!"

    total_score = stats["total_score"]
    rounds_played = stats["rounds_played"]
    perfect = stats["perfect_guesses"]
    avg_score = total_score / rounds_played if rounds_played > 0 else 0

    lines = [
        f"**Stats for {player.display_name}**",
        "",
        f"**Rank:** #{rank}",
        f"**Total Score:** {total_score:,} pts",
        f"**Games Played:** {rounds_played}",
        f"**Average Score:** {avg_score:.0f} pts/game",
        f"**Perfect Guesses:** {perfect}",
    ]

    return "\n".join(lines)
