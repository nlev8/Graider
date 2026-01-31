-- Graider Student Portal Schema
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/YOUR_PROJECT/sql

-- ============================================
-- PUBLISHED ASSESSMENTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS published_assessments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    join_code VARCHAR(10) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    assessment JSONB NOT NULL,  -- Full assessment data (questions, sections, etc.)
    settings JSONB DEFAULT '{}'::jsonb,  -- time_limit, allow_multiple_attempts, etc.
    teacher_name TEXT,
    teacher_email TEXT,
    is_active BOOLEAN DEFAULT true,
    submission_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast join code lookups
CREATE INDEX IF NOT EXISTS idx_assessments_join_code ON published_assessments(join_code);
CREATE INDEX IF NOT EXISTS idx_assessments_active ON published_assessments(is_active);

-- ============================================
-- SUBMISSIONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS submissions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    assessment_id UUID REFERENCES published_assessments(id) ON DELETE CASCADE,
    join_code VARCHAR(10) NOT NULL,
    student_name TEXT NOT NULL,
    student_email TEXT,  -- Optional
    answers JSONB NOT NULL,  -- Student's answers
    results JSONB,  -- Grading results (score, feedback, etc.)
    score NUMERIC(5,2),  -- Cached score for easy querying
    total_points NUMERIC(5,2),
    percentage NUMERIC(5,2),
    time_taken_seconds INTEGER,
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    graded_at TIMESTAMPTZ
);

-- Indexes for submissions
CREATE INDEX IF NOT EXISTS idx_submissions_assessment ON submissions(assessment_id);
CREATE INDEX IF NOT EXISTS idx_submissions_join_code ON submissions(join_code);
CREATE INDEX IF NOT EXISTS idx_submissions_student ON submissions(student_name);
CREATE INDEX IF NOT EXISTS idx_submissions_submitted ON submissions(submitted_at);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================
-- Enable RLS
ALTER TABLE published_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;

-- Allow anonymous users to read active assessments (for students joining)
CREATE POLICY "Anyone can read active assessments" ON published_assessments
    FOR SELECT USING (is_active = true);

-- Allow service role (backend) full access
CREATE POLICY "Service role has full access to assessments" ON published_assessments
    FOR ALL USING (auth.role() = 'service_role');

-- Allow anonymous submissions
CREATE POLICY "Anyone can insert submissions" ON submissions
    FOR INSERT WITH CHECK (true);

-- Allow reading own submission (by student name match - simplified)
CREATE POLICY "Anyone can read submissions" ON submissions
    FOR SELECT USING (true);

-- Service role full access to submissions
CREATE POLICY "Service role has full access to submissions" ON submissions
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================
-- FUNCTIONS
-- ============================================

-- Function to increment submission count
CREATE OR REPLACE FUNCTION increment_submission_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE published_assessments
    SET submission_count = submission_count + 1,
        updated_at = NOW()
    WHERE id = NEW.assessment_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-increment submission count
DROP TRIGGER IF EXISTS trigger_increment_submissions ON submissions;
CREATE TRIGGER trigger_increment_submissions
    AFTER INSERT ON submissions
    FOR EACH ROW
    EXECUTE FUNCTION increment_submission_count();

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for assessments
DROP TRIGGER IF EXISTS trigger_update_assessments_timestamp ON published_assessments;
CREATE TRIGGER trigger_update_assessments_timestamp
    BEFORE UPDATE ON published_assessments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================
-- HELPFUL VIEWS
-- ============================================

-- View for assessment summary with submission stats
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
-- SAMPLE DATA (Optional - for testing)
-- ============================================
-- Uncomment to insert test data:
/*
INSERT INTO published_assessments (join_code, title, assessment, settings, teacher_name)
VALUES (
    'TEST01',
    'Sample Quiz',
    '{"title": "Sample Quiz", "sections": [{"name": "Part 1", "questions": [{"number": 1, "question": "What is 2+2?", "type": "multiple_choice", "options": ["A) 3", "B) 4", "C) 5", "D) 6"], "answer": "B", "points": 1}]}], "total_points": 1}'::jsonb,
    '{"time_limit_minutes": 30, "show_correct_answers": true}'::jsonb,
    'Test Teacher'
);
*/
