-- Student Account Portal Schema for Graider
-- Run this in the Supabase SQL Editor to create the required tables.

-- Students table (created from teacher's roster imports)
CREATE TABLE IF NOT EXISTS students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    student_id_number TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    period TEXT,
    class_code TEXT,
    accommodations JSONB DEFAULT '{}',
    ell_language TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(teacher_id, student_id_number)
);

CREATE INDEX IF NOT EXISTS idx_students_lookup ON students(student_id_number, teacher_id);
CREATE INDEX IF NOT EXISTS idx_students_teacher ON students(teacher_id);

-- Classes table (one per period, holds join code)
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

-- Junction: students <-> classes
CREATE TABLE IF NOT EXISTS class_students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id UUID REFERENCES classes(id) ON DELETE CASCADE,
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(class_id, student_id)
);

-- Student sessions (lightweight auth, no Supabase auth.users for students)
-- session_token stores SHA-256 hash, not the raw token
CREATE TABLE IF NOT EXISTS student_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    class_id UUID REFERENCES classes(id) ON DELETE CASCADE,
    session_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON student_sessions(session_token);

-- Published content (unified: assessments + assignments)
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

-- Student submissions (unified)
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

CREATE INDEX IF NOT EXISTS idx_submissions_student ON student_submissions(student_id);
CREATE INDEX IF NOT EXISTS idx_submissions_content ON student_submissions(content_id);
CREATE INDEX IF NOT EXISTS idx_submissions_status ON student_submissions(status);
