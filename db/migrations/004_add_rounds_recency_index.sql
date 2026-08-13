-- Covering index for looking up recently used target messages in a guild.
-- Without it, get_recent_target_message_ids has to materialize and sort every
-- round in the guild on each round start (idx_rounds_guild_status orders by
-- status, not id, so it can't stream in id DESC order).
CREATE INDEX IF NOT EXISTS idx_rounds_guild_recent
    ON game_rounds(guild_id, id DESC, target_message_id);
