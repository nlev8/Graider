-- Roster RLS Policies: Multi-tenant security for classes, students, and enrollments
-- Run this in the Supabase SQL Editor after importing rosters.

-- Enable RLS on all roster tables
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_students ENABLE ROW LEVEL SECURITY;

-- Teachers can manage their own students
CREATE POLICY students_own ON students FOR ALL
  USING (auth.uid() = teacher_id)
  WITH CHECK (auth.uid() = teacher_id);

-- Teachers can manage their own classes
CREATE POLICY classes_own ON classes FOR ALL
  USING (auth.uid() = teacher_id)
  WITH CHECK (auth.uid() = teacher_id);

-- Teachers can manage enrollments in their own classes
CREATE POLICY class_students_own ON class_students FOR ALL
  USING (class_id IN (SELECT id FROM classes WHERE teacher_id = auth.uid()))
  WITH CHECK (class_id IN (SELECT id FROM classes WHERE teacher_id = auth.uid()));
