-- Active game rounds
CREATE TABLE IF NOT EXISTS game_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    game_channel_id TEXT NOT NULL,        -- Where the game is being played
    target_message_id TEXT NOT NULL,
    target_channel_id TEXT NOT NULL,
    target_timestamp_ms INTEGER NOT NULL,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    status TEXT DEFAULT 'active'          -- active, completed, cancelled
);

CREATE INDEX IF NOT EXISTS idx_rounds_guild_status
    ON game_rounds(guild_id, status);

-- Player guesses
CREATE TABLE IF NOT EXISTS guesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL REFERENCES game_rounds(id),
    player_id TEXT NOT NULL,
    guessed_channel_id TEXT,
    guessed_timestamp_ms INTEGER,
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    channel_correct BOOLEAN,
    time_score INTEGER,                   -- Points based on time accuracy
    UNIQUE(round_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_guesses_round
    ON guesses(round_id);

-- Leaderboard
CREATE TABLE IF NOT EXISTS player_scores (
    guild_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    total_score INTEGER DEFAULT 0,
    rounds_played INTEGER DEFAULT 0,
    perfect_guesses INTEGER DEFAULT 0,    -- Got both channel and time exactly
    PRIMARY KEY (guild_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_scores_guild_total
    ON player_scores(guild_id, total_score DESC);

-- Drop the interesting_messages table if it exists (no longer used)
DROP TABLE IF EXISTS interesting_messages;
