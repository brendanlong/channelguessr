-- Add author guess feature
-- Players can now guess who sent the target message for additional points

ALTER TABLE game_rounds ADD COLUMN target_author_id TEXT;
ALTER TABLE guesses ADD COLUMN guessed_author_id TEXT;
ALTER TABLE guesses ADD COLUMN author_correct BOOLEAN;
