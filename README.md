# Channelguessr

[![Add to Discord](https://img.shields.io/badge/Add%20to%20Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1464797297706795193)

A Discord bot game where players are shown a random "interesting" message (with surrounding context) and must guess which channel it came from and approximately when it was posted.

## Features

- **Random message selection**: The bot randomly selects interesting messages from your server's history
- **Context display**: Shows messages before and after the mystery message
- **Anonymized usernames**: Prevents guessing based on who frequents which channel
- **Scoring system**: Points for correct channel (500), time accuracy (up to 500), and author (500)
- **Leaderboards**: Track top players per server
- **Player stats**: View individual performance

## Quick Start

### 1. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. Enable these Privileged Gateway Intents:
   - **Message Content Intent** (required)
5. Copy the bot token

### 2. Invite the Bot

1. Go to the "OAuth2" > "URL Generator" section
2. Select scopes: `bot`, `applications.commands`
3. Select bot permissions:
   - Read Messages/View Channels
   - Send Messages
   - Read Message History
   - Add Reactions
4. Copy the generated URL and open it to invite the bot

### 3. Set Up the Bot

```bash
# Clone the repository
git clone <repo-url>
cd channelguessr

# Install uv (if not already installed)
# See https://docs.astral.sh/uv/getting-started/installation/

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env and add your DISCORD_TOKEN

# Run the bot
uv run python -m bot.main
```

## Commands

| Command | Description |
|---------|-------------|
| `/channelguessr start` | Start a new guessing round |
| `/channelguessr guess <channel> <time> [author]` | Submit your guess |
| `/channelguessr skip` | Skip current round (mod only) |
| `/channelguessr leaderboard` | Show server leaderboard |
| `/channelguessr stats [user]` | Show player stats |
| `/channelguessr help` | Show help information |

## How to Play

1. Use `/channelguessr start` to begin a round
2. You'll see a mystery message with context before and after
3. Usernames are anonymized (User_A, User_B, etc.)
4. Use `/channelguessr guess` to submit your channel and time guess
5. After 60 seconds, the round ends and scores are revealed

## Scoring

- **Channel**: 500 points if correct
- **Time accuracy**:
  - Within 1 day: 500 points
  - Within 1 week: 400 points
  - Within 1 month: 300 points
  - Within 3 months: 200 points
  - Within 6 months: 100 points
  - Within 1 year: 50 points
- **Author**: 500 points if correct (optional)

**Maximum score per round: 1500 points**

## Message Selection

When a round starts, the bot randomly selects a message from your server's history. A message is considered "interesting" if it has ANY of:
- 200+ characters of text
- Attachments (images, files)
- Embeds
- URLs

Messages less than 24 hours old are excluded from the game. The bot searches up to 1 year back in history.

## Configuration

Edit `config.py` to customize:

```python
ROUND_TIMEOUT_SECONDS = 60       # Time limit per round
CONTEXT_MESSAGES = 5             # Messages shown before/after
MIN_MESSAGE_AGE_HOURS = 24       # Exclude recent messages
MESSAGE_SEARCH_LIMIT = 100       # Messages to fetch per API call
MAX_SEARCH_RETRIES = 5           # How many channel/time combos to try
LOOKBACK_DAYS = 365              # How far back to look for messages
MIN_MESSAGE_LENGTH = 200         # Minimum characters for "interesting"
```

## Project Structure

```
channelguessr/
├── bot/
│   ├── main.py                # Entry point
│   ├── commands/
│   │   └── game.py            # Slash commands
│   └── services/
│       ├── game_service.py    # Game logic
│       ├── message_selector.py # Random message selection
│       └── scoring_service.py
├── db/
│   ├── database.py            # SQLite wrapper
│   └── migrations/
│       └── 001_initial.sql
├── tests/                     # Test suite
│   ├── conftest.py
│   └── test_*.py
├── utils/
│   ├── snowflake.py           # Discord ID utilities
│   └── formatting.py          # Display formatting
├── docs/
│   └── DESIGN.md              # Design document
├── config.py
├── pyproject.toml
└── README.md
```

## Requirements

- Python 3.10+
- discord.py 2.3+
- aiosqlite

## License

MIT
