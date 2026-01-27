-- Add timer expiration tracking for persistent timers
-- Stores when the round timer should expire so timers can be restored on restart

ALTER TABLE game_rounds ADD COLUMN timer_expires_at DATETIME;
