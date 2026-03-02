-- Graider Behavior Tracking Schema
-- Run this in Supabase SQL Editor to create the behavior tracking tables.
-- Requires: classes table and students table already exist.

-- ============================================================
-- Table: behavior_sessions
-- ============================================================
CREATE TABLE behavior_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    class_id UUID REFERENCES classes(id),
    period TEXT NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    device TEXT,                -- 'web' | 'ios' | 'watch'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(teacher_id, date, period, started_at)
);

-- Composite unique for FK target from behavior_events
ALTER TABLE behavior_sessions ADD UNIQUE (id, teacher_id);

-- Indexes for common queries
CREATE INDEX idx_sessions_teacher_active ON behavior_sessions(teacher_id, is_active);
CREATE INDEX idx_sessions_teacher_date ON behavior_sessions(teacher_id, date);

-- RLS
ALTER TABLE behavior_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Teachers manage own sessions"
    ON behavior_sessions FOR ALL
    USING (auth.uid() = teacher_id)
    WITH CHECK (auth.uid() = teacher_id);

-- ============================================================
-- Table: behavior_events
-- ============================================================
CREATE TABLE behavior_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    teacher_id UUID NOT NULL,
    student_id UUID REFERENCES students(id),
    student_name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('correction', 'praise')),
    note TEXT,
    transcript TEXT,               -- what Whisper heard (STT events only)
    source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'stt', 'watch')),
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ,
    client_id UUID,                -- client-generated UUID for offline dedup

    -- Composite FK: events can only reference sessions owned by same teacher
    FOREIGN KEY (session_id, teacher_id)
        REFERENCES behavior_sessions(id, teacher_id) ON DELETE CASCADE,

    -- Prevent duplicate uploads from offline retry
    UNIQUE(client_id)
);

-- Indexes
CREATE INDEX idx_events_session ON behavior_events(session_id);
CREATE INDEX idx_events_student ON behavior_events(student_id);
CREATE INDEX idx_events_teacher_session_time ON behavior_events(teacher_id, session_id, event_time);
CREATE INDEX idx_events_teacher_date ON behavior_events(teacher_id, event_time);

-- RLS
ALTER TABLE behavior_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Teachers manage own events"
    ON behavior_events FOR ALL
    USING (auth.uid() = teacher_id)
    WITH CHECK (auth.uid() = teacher_id);

-- ============================================================
-- Enable real-time for both tables
-- ============================================================
ALTER PUBLICATION supabase_realtime ADD TABLE behavior_sessions;
ALTER PUBLICATION supabase_realtime ADD TABLE behavior_events;
