"""Message formatting utilities for the game display."""

import discord
from typing import Sequence


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
    """Format the complete game message display."""
    # Combine all messages for anonymization
    all_messages = list(before_messages) + [target_message] + list(after_messages)
    user_map = anonymize_usernames(all_messages)

    lines = [
        "```",
        "╭──────────────────────────────────────╮",
        f"│  CHANNELGUESSR - ROUND #{round_number:<12}│",
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
    guesses: list[dict],
    guild: discord.Guild,
) -> str:
    """Format the results of a completed round."""
    from utils.snowflake import format_timestamp

    lines = [
        "```",
        "╭──────────────────────────────────────╮",
        "│        ROUND COMPLETE!              │",
        "╰──────────────────────────────────────╯",
        "```",
        "",
        f"**Channel:** {target_channel.mention}",
        f"**Posted:** {format_timestamp(target_timestamp_ms, 'f')} ({format_timestamp(target_timestamp_ms, 'R')})",
        "",
    ]

    if guesses:
        lines.append("**Results:**")

        # Sort by total score descending
        sorted_guesses = sorted(
            guesses,
            key=lambda g: (g.get("channel_correct", False), g.get("time_score", 0)),
            reverse=True,
        )

        for i, guess in enumerate(sorted_guesses, 1):
            player_id = guess["player_id"]
            channel_correct = guess.get("channel_correct", False)
            time_score = guess.get("time_score", 0)
            total_score = (500 if channel_correct else 0) + time_score

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

            lines.append(
                f"{i}. <@{player_id}>: **{total_score}** pts "
                f"(Channel: {channel_emoji} {channel_text}, Time: +{time_score})"
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
