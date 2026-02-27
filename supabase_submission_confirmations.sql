-- Submission Confirmations: queue confirmation emails for batch sending via Outlook
-- Run this in Supabase SQL Editor

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
