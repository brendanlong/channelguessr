# Discord Message Geoguessr

A Discord bot game where players are shown a random "interesting" message (with surrounding context) and must guess which channel it came from and approximately when it was posted.

## Features

- **Real-time message indexing**: The bot automatically indexes interesting messages as they're posted
- **Context display**: Shows messages before and after the mystery message
- **Anonymized usernames**: Prevents guessing based on who frequents which channel
- **Scoring system**: Points for correct channel (500) and time accuracy (up to 500)
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
cd discord-geoguessr

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your DISCORD_TOKEN

# Run the bot
python -m bot.main
```

## Commands

| Command | Description |
|---------|-------------|
| `/geoguessr start` | Start a new guessing round |
| `/geoguessr guess <channel> <time>` | Submit your guess |
| `/geoguessr skip` | Skip current round (mod only) |
| `/geoguessr leaderboard` | Show server leaderboard |
| `/geoguessr stats [user]` | Show player stats |
| `/geoguessr help` | Show help information |

## How to Play

1. Use `/geoguessr start` to begin a round
2. You'll see a mystery message with context before and after
3. Usernames are anonymized (User_A, User_B, etc.)
4. Use `/geoguessr guess` to submit your channel and time guess
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

**Maximum score per round: 1000 points**

## Message Indexing

The bot automatically indexes messages that meet these criteria:
- 200+ characters long
- Contains images/attachments
- Contains links
- Has 3+ reactions

Messages less than 24 hours old are excluded from the game.

## Configuration

Edit `config.py` to customize:

```python
ROUND_TIMEOUT_SECONDS = 60      # Time limit per round
CONTEXT_MESSAGES = 5             # Messages shown before/after
MIN_INTERESTING_MESSAGES = 10    # Minimum pool size to start
MIN_MESSAGE_AGE_HOURS = 24       # Exclude recent messages
```

## Project Structure

```
discord-geoguessr/
├── bot/
│   ├── main.py              # Entry point
│   ├── commands/
│   │   └── game.py          # Slash commands
│   ├── events/
│   │   ├── message.py       # Message indexing
│   │   └── reaction.py      # Reaction tracking
│   └── services/
│       ├── game_service.py  # Game logic
│       └── scoring_service.py
├── db/
│   ├── database.py          # SQLite wrapper
│   └── migrations/
│       └── 001_initial.sql
├── utils/
│   ├── snowflake.py         # Discord ID utilities
│   └── formatting.py        # Display formatting
├── docs/
│   └── DESIGN.md            # Design document
├── config.py
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10+
- discord.py 2.3+
- aiosqlite

## License

MIT
