-- ============================================================
-- Graider Cloud Migration Script
-- Paste this into Supabase SQL Editor:
-- https://supabase.com/dashboard/project/hecxqiedfodnpujjriin/sql
-- ============================================================
-- Order: 1) Assessments, 2) Student Portal, 3) Confirmations, 4) Behavior
-- Run as a single transaction.

BEGIN;

-- ============================================
-- 1. PUBLISHED ASSESSMENTS + SUBMISSIONS
-- ============================================
CREATE TABLE IF NOT EXISTS published_assessments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    join_code VARCHAR(10) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    assessment JSONB NOT NULL,
    settings JSONB DEFAULT '{}'::jsonb,
    teacher_name TEXT,
    teacher_email TEXT,
    is_active BOOLEAN DEFAULT true,
    submission_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assessments_join_code ON published_assessments(join_code);
CREATE INDEX IF NOT EXISTS idx_assessments_active ON published_assessments(is_active);

CREATE TABLE IF NOT EXISTS submissions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    assessment_id UUID REFERENCES published_assessments(id) ON DELETE CASCADE,
    join_code VARCHAR(10) NOT NULL,
    student_name TEXT NOT NULL,
    student_email TEXT,
    answers JSONB NOT NULL,
    results JSONB,
    score NUMERIC(5,2),
    total_points NUMERIC(5,2),
    percentage NUMERIC(5,2),
    time_taken_seconds INTEGER,
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    graded_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_submissions_assessment ON submissions(assessment_id);
CREATE INDEX IF NOT EXISTS idx_submissions_join_code ON submissions(join_code);
CREATE INDEX IF NOT EXISTS idx_pa_submissions_student ON submissions(student_name);
CREATE INDEX IF NOT EXISTS idx_submissions_submitted ON submissions(submitted_at);

ALTER TABLE published_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  CREATE POLICY "Anyone can read active assessments" ON published_assessments
      FOR SELECT USING (is_active = true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE POLICY "Service role has full access to assessments" ON published_assessments
      FOR ALL USING (auth.role() = 'service_role');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE POLICY "Anyone can insert submissions" ON submissions
      FOR INSERT WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE POLICY "Anyone can read submissions" ON submissions
      FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE POLICY "Service role has full access to submissions" ON submissions
      FOR ALL USING (auth.role() = 'service_role');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE OR REPLACE FUNCTION increment_submission_count()
RETURNS TRIGGER AS $fn$
BEGIN
    UPDATE published_assessments
    SET submission_count = submission_count + 1,
        updated_at = NOW()
    WHERE id = NEW.assessment_id;
    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_increment_submissions ON submissions;
CREATE TRIGGER trigger_increment_submissions
    AFTER INSERT ON submissions
    FOR EACH ROW
    EXECUTE FUNCTION increment_submission_count();

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $fn$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_assessments_timestamp ON published_assessments;
CREATE TRIGGER trigger_update_assessments_timestamp
    BEFORE UPDATE ON published_assessments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE VIEW assessment_summary AS
SELECT
    pa.id,
    pa.join_code,
    pa.title,
    pa.teacher_name,
    pa.is_active,
    pa.submission_count,
    pa.created_at,
    COALESCE(AVG(s.percentage), 0) as avg_percentage,
    COALESCE(MAX(s.percentage), 0) as max_percentage,
    COALESCE(MIN(s.percentage), 0) as min_percentage
FROM published_assessments pa
LEFT JOIN submissions s ON pa.id = s.assessment_id
GROUP BY pa.id;

-- ============================================
-- 2. STUDENT PORTAL (classes, students, etc.)
-- ============================================
CREATE TABLE IF NOT EXISTS students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    student_id_number TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    period TEXT,
    class_code TEXT,
    accommodations JSONB DEFAULT '{}',
    email TEXT,
    ell_language TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(teacher_id, student_id_number)
);

CREATE INDEX IF NOT EXISTS idx_students_lookup ON students(student_id_number, teacher_id);
CREATE INDEX IF NOT EXISTS idx_students_teacher ON students(teacher_id);
CREATE INDEX IF NOT EXISTS idx_students_email ON students(email, teacher_id);

-- Classes table (may already exist from dummy data)
CREATE TABLE IF NOT EXISTS classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    name TEXT NOT NULL,
    join_code TEXT NOT NULL UNIQUE,
    subject TEXT,
    grade_level TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(teacher_id, name)
);

CREATE INDEX IF NOT EXISTS idx_classes_join_code ON classes(join_code);

-- class_students junction (may already exist from dummy data)
CREATE TABLE IF NOT EXISTS class_students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id UUID REFERENCES classes(id) ON DELETE CASCADE,
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(class_id, student_id)
);

CREATE TABLE IF NOT EXISTS student_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    class_id UUID REFERENCES classes(id) ON DELETE CASCADE,
    session_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON student_sessions(session_token);

CREATE TABLE IF NOT EXISTS published_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    class_id UUID REFERENCES classes(id),
    content_type TEXT NOT NULL CHECK (content_type IN ('assessment', 'assignment')),
    title TEXT NOT NULL,
    join_code TEXT UNIQUE,
    content JSONB NOT NULL,
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_published_class ON published_content(class_id, is_active);

CREATE TABLE IF NOT EXISTS student_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id),
    content_id UUID REFERENCES published_content(id),
    student_name TEXT NOT NULL,
    student_id_number TEXT,
    period TEXT,
    answers JSONB,
    results JSONB,
    score NUMERIC,
    total_points NUMERIC,
    percentage NUMERIC,
    letter_grade TEXT,
    status TEXT DEFAULT 'submitted' CHECK (status IN (
        'in_progress', 'submitted', 'grading', 'graded', 'returned'
    )),
    time_taken_seconds INTEGER,
    submitted_at TIMESTAMPTZ DEFAULT now(),
    graded_at TIMESTAMPTZ,
    attempt_number INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_ss_submissions_student ON student_submissions(student_id);
CREATE INDEX IF NOT EXISTS idx_ss_submissions_content ON student_submissions(content_id);
CREATE INDEX IF NOT EXISTS idx_ss_submissions_status ON student_submissions(status);

-- ============================================
-- 3. SUBMISSION CONFIRMATIONS
-- ============================================
CREATE TABLE IF NOT EXISTS submission_confirmations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES student_submissions(id) ON DELETE CASCADE UNIQUE,
    teacher_id UUID NOT NULL,
    student_email TEXT NOT NULL,
    student_name TEXT NOT NULL,
    assignment_title TEXT NOT NULL,
    attempt_number INTEGER DEFAULT 1,
    missing_assignments JSONB DEFAULT '[]',
    submitted_at TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'sent', 'failed')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_confirmations_status ON submission_confirmations(status);
CREATE INDEX IF NOT EXISTS idx_confirmations_teacher ON submission_confirmations(teacher_id, status);

-- ============================================
-- 4. BEHAVIOR TRACKING (may already exist)
-- ============================================
CREATE TABLE IF NOT EXISTS behavior_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    class_id UUID REFERENCES classes(id),
    period TEXT NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    device TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(teacher_id, date, period, started_at)
);

-- Add composite unique if not exists (for FK from behavior_events)
DO $$ BEGIN
  ALTER TABLE behavior_sessions ADD UNIQUE (id, teacher_id);
EXCEPTION WHEN duplicate_table THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_sessions_teacher_active ON behavior_sessions(teacher_id, is_active);
CREATE INDEX IF NOT EXISTS idx_sessions_teacher_date ON behavior_sessions(teacher_id, date);

ALTER TABLE behavior_sessions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  CREATE POLICY "Teachers manage own sessions"
      ON behavior_sessions FOR ALL
      USING (auth.uid() = teacher_id)
      WITH CHECK (auth.uid() = teacher_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS behavior_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    teacher_id UUID NOT NULL,
    student_id UUID REFERENCES students(id),
    student_name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('correction', 'praise')),
    note TEXT,
    transcript TEXT,
    source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'stt', 'watch')),
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ,
    client_id UUID,
    FOREIGN KEY (session_id, teacher_id)
        REFERENCES behavior_sessions(id, teacher_id) ON DELETE CASCADE,
    UNIQUE(client_id)
);

CREATE INDEX IF NOT EXISTS idx_events_session ON behavior_events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_student ON behavior_events(student_id);
CREATE INDEX IF NOT EXISTS idx_events_teacher_session_time ON behavior_events(teacher_id, session_id, event_time);
CREATE INDEX IF NOT EXISTS idx_events_teacher_date ON behavior_events(teacher_id, event_time);

ALTER TABLE behavior_events ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  CREATE POLICY "Teachers manage own events"
      ON behavior_events FOR ALL
      USING (auth.uid() = teacher_id)
      WITH CHECK (auth.uid() = teacher_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Real-time
DO $$ BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE behavior_sessions;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE behavior_events;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

COMMIT;

-- ============================================
-- DONE! All tables created.
-- ============================================
