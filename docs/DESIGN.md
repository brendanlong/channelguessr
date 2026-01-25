# Discord Message Geoguessr - Design Document

## Overview

A Discord bot game where players are shown a random "interesting" message (with surrounding context) and must guess which channel it came from and approximately when it was posted.

## Game Flow

1. A player triggers a new round with `/geoguessr start`
2. The bot selects a random interesting message from the server's indexed pool
3. The bot posts the message with ~5 messages of context before/after, with channel name and timestamps hidden
4. Players submit guesses for channel and time period using `/geoguessr guess`
5. After a timeout (60 seconds), the bot reveals the answer and scores players

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  Discord Bot    │────▶│   SQLite DB     │
│  (Game Logic)   │     │  (Message Pool) │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  Event Handlers │
│  (Real-time     │
│   Indexing)     │
└─────────────────┘
```

### Components

- **Bot Commands**: Slash commands for game interaction (`/geoguessr start`, `/geoguessr guess`, etc.)
- **Event Handlers**: Real-time indexing of messages and reactions as they occur
- **Game Service**: Core game logic for selecting messages, managing rounds, and scoring
- **Database**: SQLite storage for indexed messages, active rounds, guesses, and leaderboards

## Database Schema

### interesting_messages
Stores messages that meet the "interesting" criteria for potential game rounds.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| message_id | TEXT | Discord snowflake (unique) |
| channel_id | TEXT | Source channel |
| guild_id | TEXT | Server ID |
| author_id | TEXT | Message author |
| content | TEXT | Message text |
| timestamp_ms | INTEGER | Unix timestamp in ms |
| interest_score | INTEGER | Bitmask of interest flags |
| created_at | DATETIME | When indexed |

### game_rounds
Tracks active and completed game rounds.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| guild_id | TEXT | Server ID |
| game_channel_id | TEXT | Where game is played |
| target_message_id | TEXT | The mystery message |
| target_channel_id | TEXT | Correct channel answer |
| target_timestamp_ms | INTEGER | Correct time answer |
| started_at | DATETIME | Round start time |
| ended_at | DATETIME | Round end time |
| status | TEXT | active/completed/cancelled |

### guesses
Player guesses for each round.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| round_id | INTEGER | Foreign key to game_rounds |
| player_id | TEXT | Discord user ID |
| guessed_channel_id | TEXT | Channel guess |
| guessed_timestamp_ms | INTEGER | Time guess |
| submitted_at | DATETIME | When submitted |
| channel_correct | BOOLEAN | Was channel right? |
| time_score | INTEGER | Points for time accuracy |

### player_scores
Aggregated leaderboard data per server.

| Column | Type | Description |
|--------|------|-------------|
| guild_id | TEXT | Server ID (composite PK) |
| player_id | TEXT | User ID (composite PK) |
| total_score | INTEGER | Cumulative points |
| rounds_played | INTEGER | Games participated in |
| perfect_guesses | INTEGER | Both channel and time correct |

## Interest Criteria

Messages are indexed if they meet one or more criteria:

| Flag | Value | Criteria |
|------|-------|----------|
| REACTIONS | 1 | 3+ reactions |
| LONG_TEXT | 2 | 200+ characters |
| HAS_IMAGE | 4 | Has attachment/embed |
| HAS_REPLIES | 8 | 2+ replies |
| HAS_LINK | 16 | Contains URL |

Stored as a bitmask so multiple criteria can be tracked.

## Scoring System

| Component | Points | Criteria |
|-----------|--------|----------|
| Channel | 500 | Correct channel |
| Time (1 day) | 500 | Within 1 day |
| Time (1 week) | 400 | Within 1 week |
| Time (1 month) | 300 | Within 1 month |
| Time (3 months) | 200 | Within 3 months |
| Time (6 months) | 100 | Within 6 months |
| Time (1 year) | 50 | Within 1 year |

Maximum score per round: 1000 points

## Message Display

Messages are displayed with anonymized usernames to prevent guessing based on who frequents which channel:

```
╭──────────────────────────────────────╮
│  🔍 DISCORD GEOGUESSR - ROUND #42   │
╰──────────────────────────────────────╯

**[Context Before]**
> **User_A:** anyone here play valorant?
> **User_B:** yeah I'm down

**[MYSTERY MESSAGE]**
> **User_C:** I just hit immortal for the first time...

**[Context After]**
> **User_B:** LETS GOOO
> **User_A:** carry me pls

───────────────────────────────────────
❓ **Which channel?** Use `/geoguessr guess`
⏰ **When was this posted?**
🕐 You have 60 seconds!
```

## Commands

| Command | Description |
|---------|-------------|
| `/geoguessr start` | Start a new round |
| `/geoguessr guess <channel> <time>` | Submit a guess |
| `/geoguessr skip` | Skip current round (mod only) |
| `/geoguessr leaderboard` | Show server leaderboard |
| `/geoguessr stats [@user]` | Show player stats |

## MVP Scope

This implementation covers Phase 1 (MVP):

- Single-server support
- Basic game commands
- SQLite database
- Real-time message indexing (no historical backfill)
- Equal channel weights for random selection
- Basic scoring system
- Leaderboard

### Not Included in MVP

- Channel activity weighting
- Historical message backfill
- Configurable interest criteria
- Multi-round games
- Reaction-based guessing UI
- Hints system

## File Structure

```
discord-geoguessr/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Bot entry point
│   ├── commands/
│   │   ├── __init__.py
│   │   └── game.py          # /geoguessr commands
│   ├── events/
│   │   ├── __init__.py
│   │   ├── message.py       # on_message indexing
│   │   └── reaction.py      # on_reaction tracking
│   └── services/
│       ├── __init__.py
│       ├── game_service.py  # Game logic
│       └── scoring_service.py
├── db/
│   ├── __init__.py
│   ├── database.py          # SQLite wrapper
│   └── migrations/
│       └── 001_initial.sql
├── utils/
│   ├── __init__.py
│   ├── snowflake.py         # Snowflake utilities
│   └── formatting.py        # Message display
├── config.py
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

Environment variables:

- `DISCORD_TOKEN`: Bot token from Discord Developer Portal

Game settings (in config.py):

- `ROUND_TIMEOUT_SECONDS`: 60
- `CONTEXT_MESSAGES`: 5
- `MIN_INTERESTING_MESSAGES`: 10 (for MVP, lowered from 100)
- `MIN_MESSAGE_AGE_HOURS`: 24 (exclude recent messages)

## Required Discord Permissions

Bot requires:
- Read Messages/View Channels
- Send Messages
- Read Message History
- Add Reactions
- Use Slash Commands

Privileged Intents required:
- Message Content Intent

## Privacy Considerations

- Only indexes messages in channels the bot can read
- Skips bot messages
- Anonymizes usernames in game display
- Excludes messages less than 24 hours old
- Future: Add user opt-out mechanism
