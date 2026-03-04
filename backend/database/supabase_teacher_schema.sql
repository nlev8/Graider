-- ═══════════════════════════════════════════════════════════════
-- Graider Teacher Data Schema
-- ═══════════════════════════════════════════════════════════════
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor > New query)
--
-- Two tables:
--   teacher_data    — KV store for all per-teacher JSON blobs
--   student_history — Per-student grading history (N rows per teacher)
-- ═══════════════════════════════════════════════════════════════

-- 1. Teacher Data (KV store)
CREATE TABLE IF NOT EXISTS teacher_data (
    teacher_id  TEXT NOT NULL,
    data_key    TEXT NOT NULL,
    data        JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (teacher_id, data_key)
);

-- Index for listing keys by prefix
CREATE INDEX IF NOT EXISTS idx_teacher_data_key_prefix
    ON teacher_data (teacher_id, data_key text_pattern_ops);

-- 2. Student History
CREATE TABLE IF NOT EXISTS student_history (
    teacher_id  TEXT NOT NULL,
    student_id  TEXT NOT NULL,
    history     JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (teacher_id, student_id)
);

-- ═══════════════════════════════════════════════════════════════
-- Row Level Security
-- ═══════════════════════════════════════════════════════════════

-- Enable RLS
ALTER TABLE teacher_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_history ENABLE ROW LEVEL SECURITY;

-- Service role has full access (used by backend)
-- No restrictive policies needed since the backend uses service_role key,
-- which bypasses RLS. These policies are for safety if anyone connects
-- with the anon key.

-- Teachers can only read/write their own data via authenticated role
CREATE POLICY teacher_data_own ON teacher_data
    FOR ALL
    USING (auth.uid()::text = teacher_id)
    WITH CHECK (auth.uid()::text = teacher_id);

CREATE POLICY student_history_own ON student_history
    FOR ALL
    USING (auth.uid()::text = teacher_id)
    WITH CHECK (auth.uid()::text = teacher_id);

-- ═══════════════════════════════════════════════════════════════
-- Auto-update updated_at on upsert
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER teacher_data_updated_at
    BEFORE UPDATE ON teacher_data
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER student_history_updated_at
    BEFORE UPDATE ON student_history
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
