-- Migration: Add foreign key constraints with CASCADE
-- Date: 2026-03-20
-- Purpose: Prevent orphaned records when parent records are deleted

-- Submissions → published_assessments (CASCADE delete)
-- Note: Only add if not already present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_submissions_assessment'
    ) THEN
        ALTER TABLE submissions
        ADD CONSTRAINT fk_submissions_assessment
        FOREIGN KEY (assessment_id) REFERENCES published_assessments(id) ON DELETE CASCADE;
    END IF;
END $$;

-- student_submissions → published_content (CASCADE delete)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_student_submissions_content'
    ) THEN
        ALTER TABLE student_submissions
        ADD CONSTRAINT fk_student_submissions_content
        FOREIGN KEY (content_id) REFERENCES published_content(id) ON DELETE CASCADE;
    END IF;
END $$;

-- student_submissions → students (CASCADE delete)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_student_submissions_student'
    ) THEN
        ALTER TABLE student_submissions
        ADD CONSTRAINT fk_student_submissions_student
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE;
    END IF;
END $$;

-- class_students → classes (CASCADE delete)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_class_students_class'
    ) THEN
        ALTER TABLE class_students
        ADD CONSTRAINT fk_class_students_class
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE;
    END IF;
END $$;

-- class_students → students (CASCADE delete)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_class_students_student'
    ) THEN
        ALTER TABLE class_students
        ADD CONSTRAINT fk_class_students_student
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE;
    END IF;
END $$;

-- student_sessions → students (CASCADE delete)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_student_sessions_student'
    ) THEN
        ALTER TABLE student_sessions
        ADD CONSTRAINT fk_student_sessions_student
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE;
    END IF;
END $$;

-- published_content → classes (CASCADE delete)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_published_content_class'
    ) THEN
        ALTER TABLE published_content
        ADD CONSTRAINT fk_published_content_class
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE;
    END IF;
END $$;
