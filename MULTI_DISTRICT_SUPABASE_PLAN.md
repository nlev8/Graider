# Multi-District Analytics with Supabase

## Complete Implementation Plan

### Overview

Transform Graider from a single-teacher local tool into a multi-district SaaS platform using Supabase for:
- Multi-tenant data isolation
- Built-in authentication
- Real-time dashboards
- Scalable PostgreSQL backend

---

## Table of Contents

1. [Architecture](#architecture)
2. [Supabase Setup](#supabase-setup)
3. [Database Schema](#database-schema)
4. [Backend Implementation](#backend-implementation)
5. [API Routes](#api-routes)
6. [Frontend Implementation](#frontend-implementation)
7. [Authentication Flow](#authentication-flow)
8. [Real-time Subscriptions](#real-time-subscriptions)
9. [Deployment Guide](#deployment-guide)
10. [Migration from Local](#migration-from-local)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SUPABASE CLOUD                                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         PostgreSQL Database                          │    │
│  │                                                                      │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │    │
│  │  │ District A  │  │ District B  │  │ District C  │                 │    │
│  │  │             │  │             │  │             │                 │    │
│  │  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │                 │    │
│  │  │ │School 1 │ │  │ │School 1 │ │  │ │School 1 │ │                 │    │
│  │  │ │School 2 │ │  │ │School 2 │ │  │ │School 2 │ │                 │    │
│  │  │ │School 3 │ │  │ │School 3 │ │  │ │School 3 │ │                 │    │
│  │  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │                 │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                 │    │
│  │                                                                      │    │
│  │  Row-Level Security ensures complete data isolation                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │     Auth     │  │   Storage    │  │  Real-time   │  │   Edge Fn    │    │
│  │  - Email/PW  │  │  - Exports   │  │  - Live      │  │  - Webhooks  │    │
│  │  - SSO       │  │  - Reports   │  │    updates   │  │  - Cron      │    │
│  │  - Clever    │  │  - Backups   │  │  - Presence  │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       │ HTTPS + WebSocket
                                       │
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                              GRAIDER CLIENTS                                 │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Teacher    │    │  Principal   │    │   District   │                   │
│  │    Client    │    │    Client    │    │    Admin     │                   │
│  │              │    │              │    │              │                   │
│  │ - Grade work │    │ - School     │    │ - All        │                   │
│  │ - View own   │    │   analytics  │    │   schools    │                   │
│  │   analytics  │    │ - Teacher    │    │ - Compare    │                   │
│  │ - Sync data  │    │   oversight  │    │ - Reports    │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Role Hierarchy

```
Super Admin (Graider Staff)
    └── District Admin
            └── Principal (School Admin)
                    └── Teacher
```

---

## Supabase Setup

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com)
2. Create new project: `graider-production`
3. Choose region closest to users (e.g., `us-east-1`)
4. Save the generated password securely

### 2. Get API Keys

From Project Settings > API:

```bash
# Add to .env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 3. Install Dependencies

```bash
pip install supabase python-dotenv
```

```bash
cd frontend && npm install @supabase/supabase-js
```

---

## Database Schema

### File: `supabase/migrations/001_initial_schema.sql`

```sql
-- ══════════════════════════════════════════════════════════════
-- EXTENSIONS
-- ══════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ══════════════════════════════════════════════════════════════
-- ENUMS
-- ══════════════════════════════════════════════════════════════

CREATE TYPE user_role AS ENUM ('teacher', 'principal', 'district_admin', 'super_admin');
CREATE TYPE grade_letter AS ENUM ('A', 'B', 'C', 'D', 'F');
CREATE TYPE sync_status AS ENUM ('pending', 'syncing', 'completed', 'failed');

-- ══════════════════════════════════════════════════════════════
-- CORE TABLES
-- ══════════════════════════════════════════════════════════════

-- Districts (Top-level tenant)
CREATE TABLE districts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    state TEXT NOT NULL DEFAULT 'FL',
    settings JSONB DEFAULT '{
        "anonymize_students": true,
        "auto_sync": true,
        "sync_interval_hours": 24,
        "require_approval": false
    }'::jsonb,
    logo_url TEXT,
    primary_contact_email TEXT,
    subscription_tier TEXT DEFAULT 'free' CHECK (subscription_tier IN ('free', 'basic', 'premium', 'enterprise')),
    subscription_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Schools
CREATE TABLE schools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    district_id UUID NOT NULL REFERENCES districts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    school_code TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    phone TEXT,
    principal_name TEXT,
    settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(district_id, school_code)
);

-- User Profiles (extends Supabase auth.users)
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'teacher',
    district_id UUID REFERENCES districts(id) ON DELETE SET NULL,
    school_id UUID REFERENCES schools(id) ON DELETE SET NULL,
    subjects TEXT[] DEFAULT '{}',
    grade_levels TEXT[] DEFAULT '{}',
    avatar_url TEXT,
    settings JSONB DEFAULT '{
        "notifications": true,
        "auto_sync": true,
        "theme": "system"
    }'::jsonb,
    last_sync_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════
-- GRADING DATA
-- ══════════════════════════════════════════════════════════════

-- Students (anonymized)
CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    district_id UUID NOT NULL REFERENCES districts(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE SET NULL,
    student_hash TEXT NOT NULL,  -- SHA256 hash of student ID
    grade_level TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(district_id, student_hash)
);

-- Assignments (optional - for tracking assignment types)
CREATE TABLE assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    district_id UUID NOT NULL REFERENCES districts(id) ON DELETE CASCADE,
    teacher_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    subject TEXT,
    grade_level TEXT,
    max_points INTEGER DEFAULT 100,
    rubric JSONB,
    ai_instructions TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(district_id, teacher_id, name)
);

-- Grades (core grading data)
CREATE TABLE grades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    district_id UUID NOT NULL REFERENCES districts(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    assignment_id UUID REFERENCES assignments(id) ON DELETE SET NULL,

    -- Assignment info
    assignment_name TEXT NOT NULL,
    subject TEXT,
    grade_level TEXT,
    quarter TEXT,

    -- Scores
    score DECIMAL(5,2) NOT NULL CHECK (score >= 0 AND score <= 100),
    letter_grade grade_letter,

    -- Rubric breakdown
    content_accuracy DECIMAL(5,2),
    completeness DECIMAL(5,2),
    writing_quality DECIMAL(5,2),
    effort_engagement DECIMAL(5,2),

    -- AI Analysis
    authenticity_flag TEXT DEFAULT 'clean',
    authenticity_confidence INTEGER,
    skills_demonstrated JSONB DEFAULT '[]'::jsonb,
    feedback TEXT,

    -- Metadata
    is_handwritten BOOLEAN DEFAULT FALSE,
    marker_status TEXT DEFAULT 'verified',
    source_filename TEXT,
    graded_at TIMESTAMPTZ NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW(),

    -- Indexes will make these queries fast
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sync logs (track data uploads)
CREATE TABLE sync_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    district_id UUID NOT NULL REFERENCES districts(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    status sync_status DEFAULT 'pending',
    records_total INTEGER DEFAULT 0,
    records_synced INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ══════════════════════════════════════════════════════════════
-- INDEXES FOR PERFORMANCE
-- ══════════════════════════════════════════════════════════════

-- Grades indexes (most queried table)
CREATE INDEX idx_grades_district ON grades(district_id);
CREATE INDEX idx_grades_school ON grades(school_id);
CREATE INDEX idx_grades_teacher ON grades(teacher_id);
CREATE INDEX idx_grades_student ON grades(student_id);
CREATE INDEX idx_grades_graded_at ON grades(graded_at DESC);
CREATE INDEX idx_grades_quarter ON grades(quarter);
CREATE INDEX idx_grades_subject ON grades(subject);
CREATE INDEX idx_grades_district_school ON grades(district_id, school_id);
CREATE INDEX idx_grades_district_graded ON grades(district_id, graded_at DESC);

-- Profiles indexes
CREATE INDEX idx_profiles_district ON profiles(district_id);
CREATE INDEX idx_profiles_school ON profiles(school_id);
CREATE INDEX idx_profiles_role ON profiles(role);

-- Students indexes
CREATE INDEX idx_students_district ON students(district_id);
CREATE INDEX idx_students_school ON students(school_id);

-- ══════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS)
-- ══════════════════════════════════════════════════════════════

ALTER TABLE districts ENABLE ROW LEVEL SECURITY;
ALTER TABLE schools ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE grades ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_logs ENABLE ROW LEVEL SECURITY;

-- Helper function to get current user's profile
CREATE OR REPLACE FUNCTION get_my_profile()
RETURNS profiles AS $$
    SELECT * FROM profiles WHERE id = auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER;

-- Helper function to check user role
CREATE OR REPLACE FUNCTION has_role(required_role user_role)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM profiles
        WHERE id = auth.uid()
        AND (
            role = required_role
            OR role = 'super_admin'
            OR (role = 'district_admin' AND required_role IN ('principal', 'teacher'))
            OR (role = 'principal' AND required_role = 'teacher')
        )
    )
$$ LANGUAGE SQL SECURITY DEFINER;

-- ══════════════════════════════════════════════════════════════
-- RLS POLICIES
-- ══════════════════════════════════════════════════════════════

-- Districts: Users see their own district, super_admins see all
CREATE POLICY "Users view own district" ON districts
    FOR SELECT USING (
        id = (SELECT district_id FROM profiles WHERE id = auth.uid())
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'super_admin')
    );

CREATE POLICY "Super admins manage districts" ON districts
    FOR ALL USING (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'super_admin')
    );

-- Schools: Users see schools in their district
CREATE POLICY "Users view district schools" ON schools
    FOR SELECT USING (
        district_id = (SELECT district_id FROM profiles WHERE id = auth.uid())
    );

CREATE POLICY "District admins manage schools" ON schools
    FOR ALL USING (
        district_id = (SELECT district_id FROM profiles WHERE id = auth.uid())
        AND EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('district_admin', 'super_admin'))
    );

-- Profiles: Users see profiles in their district
CREATE POLICY "Users view district profiles" ON profiles
    FOR SELECT USING (
        district_id = (SELECT district_id FROM profiles WHERE id = auth.uid())
        OR id = auth.uid()
    );

CREATE POLICY "Users update own profile" ON profiles
    FOR UPDATE USING (id = auth.uid());

-- Students: District-level access
CREATE POLICY "Users view district students" ON students
    FOR SELECT USING (
        district_id = (SELECT district_id FROM profiles WHERE id = auth.uid())
    );

CREATE POLICY "Teachers manage students" ON students
    FOR INSERT WITH CHECK (
        district_id = (SELECT district_id FROM profiles WHERE id = auth.uid())
    );

-- Grades: Role-based access
CREATE POLICY "Teachers view own grades" ON grades
    FOR SELECT USING (
        teacher_id = auth.uid()
    );

CREATE POLICY "Principals view school grades" ON grades
    FOR SELECT USING (
        school_id = (SELECT school_id FROM profiles WHERE id = auth.uid() AND role = 'principal')
    );

CREATE POLICY "District admins view all district grades" ON grades
    FOR SELECT USING (
        district_id = (SELECT district_id FROM profiles WHERE id = auth.uid() AND role IN ('district_admin', 'super_admin'))
    );

CREATE POLICY "Teachers insert own grades" ON grades
    FOR INSERT WITH CHECK (
        teacher_id = auth.uid()
        AND district_id = (SELECT district_id FROM profiles WHERE id = auth.uid())
        AND school_id = (SELECT school_id FROM profiles WHERE id = auth.uid())
    );

CREATE POLICY "Teachers update own grades" ON grades
    FOR UPDATE USING (teacher_id = auth.uid());

-- Sync logs: Teachers see own, admins see all
CREATE POLICY "Teachers view own sync logs" ON sync_logs
    FOR SELECT USING (teacher_id = auth.uid());

CREATE POLICY "District admins view all sync logs" ON sync_logs
    FOR SELECT USING (
        district_id = (SELECT district_id FROM profiles WHERE id = auth.uid() AND role IN ('district_admin', 'super_admin'))
    );

-- ══════════════════════════════════════════════════════════════
-- VIEWS FOR ANALYTICS
-- ══════════════════════════════════════════════════════════════

-- Teacher stats (for individual teacher dashboard)
CREATE OR REPLACE VIEW teacher_stats AS
SELECT
    teacher_id,
    district_id,
    school_id,
    COUNT(*) as total_grades,
    COUNT(DISTINCT student_id) as total_students,
    COUNT(DISTINCT assignment_name) as total_assignments,
    ROUND(AVG(score)::numeric, 1) as average_score,
    COUNT(*) FILTER (WHERE score >= 90) as count_a,
    COUNT(*) FILTER (WHERE score >= 80 AND score < 90) as count_b,
    COUNT(*) FILTER (WHERE score >= 70 AND score < 80) as count_c,
    COUNT(*) FILTER (WHERE score >= 60 AND score < 70) as count_d,
    COUNT(*) FILTER (WHERE score < 60) as count_f,
    MAX(graded_at) as last_graded_at
FROM grades
GROUP BY teacher_id, district_id, school_id;

-- School stats (for principal dashboard)
CREATE OR REPLACE VIEW school_stats AS
SELECT
    school_id,
    district_id,
    COUNT(*) as total_grades,
    COUNT(DISTINCT teacher_id) as total_teachers,
    COUNT(DISTINCT student_id) as total_students,
    COUNT(DISTINCT assignment_name) as total_assignments,
    ROUND(AVG(score)::numeric, 1) as average_score,
    COUNT(*) FILTER (WHERE score >= 90) as count_a,
    COUNT(*) FILTER (WHERE score >= 80 AND score < 90) as count_b,
    COUNT(*) FILTER (WHERE score >= 70 AND score < 80) as count_c,
    COUNT(*) FILTER (WHERE score >= 60 AND score < 70) as count_d,
    COUNT(*) FILTER (WHERE score < 60) as count_f,
    MAX(graded_at) as last_graded_at
FROM grades
GROUP BY school_id, district_id;

-- District stats (for district admin dashboard)
CREATE OR REPLACE VIEW district_stats AS
SELECT
    district_id,
    COUNT(*) as total_grades,
    COUNT(DISTINCT school_id) as total_schools,
    COUNT(DISTINCT teacher_id) as total_teachers,
    COUNT(DISTINCT student_id) as total_students,
    COUNT(DISTINCT assignment_name) as total_assignments,
    ROUND(AVG(score)::numeric, 1) as average_score,
    COUNT(*) FILTER (WHERE score >= 90) as count_a,
    COUNT(*) FILTER (WHERE score >= 80 AND score < 90) as count_b,
    COUNT(*) FILTER (WHERE score >= 70 AND score < 80) as count_c,
    COUNT(*) FILTER (WHERE score >= 60 AND score < 70) as count_d,
    COUNT(*) FILTER (WHERE score < 60) as count_f,
    MAX(graded_at) as last_graded_at
FROM grades
GROUP BY district_id;

-- Subject breakdown
CREATE OR REPLACE VIEW subject_stats AS
SELECT
    district_id,
    school_id,
    subject,
    COUNT(*) as total_grades,
    ROUND(AVG(score)::numeric, 1) as average_score,
    COUNT(DISTINCT student_id) as total_students
FROM grades
WHERE subject IS NOT NULL
GROUP BY district_id, school_id, subject;

-- Quarterly trends
CREATE OR REPLACE VIEW quarterly_stats AS
SELECT
    district_id,
    school_id,
    quarter,
    COUNT(*) as total_grades,
    ROUND(AVG(score)::numeric, 1) as average_score
FROM grades
WHERE quarter IS NOT NULL
GROUP BY district_id, school_id, quarter
ORDER BY quarter;

-- Monthly trends (for charts)
CREATE OR REPLACE VIEW monthly_trends AS
SELECT
    district_id,
    school_id,
    DATE_TRUNC('month', graded_at) as month,
    COUNT(*) as total_grades,
    ROUND(AVG(score)::numeric, 1) as average_score,
    COUNT(DISTINCT teacher_id) as active_teachers
FROM grades
WHERE graded_at > NOW() - INTERVAL '12 months'
GROUP BY district_id, school_id, DATE_TRUNC('month', graded_at)
ORDER BY month DESC;

-- ══════════════════════════════════════════════════════════════
-- FUNCTIONS
-- ══════════════════════════════════════════════════════════════

-- Get district trends for charts
CREATE OR REPLACE FUNCTION get_district_trends(p_district_id UUID, p_months INTEGER DEFAULT 12)
RETURNS TABLE (
    month DATE,
    total_grades BIGINT,
    average_score NUMERIC,
    active_teachers BIGINT,
    active_schools BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        DATE_TRUNC('month', g.graded_at)::DATE as month,
        COUNT(*)::BIGINT as total_grades,
        ROUND(AVG(g.score)::numeric, 1) as average_score,
        COUNT(DISTINCT g.teacher_id)::BIGINT as active_teachers,
        COUNT(DISTINCT g.school_id)::BIGINT as active_schools
    FROM grades g
    WHERE g.district_id = p_district_id
    AND g.graded_at > NOW() - (p_months || ' months')::INTERVAL
    GROUP BY DATE_TRUNC('month', g.graded_at)
    ORDER BY month DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get school comparison for district
CREATE OR REPLACE FUNCTION get_school_comparison(p_district_id UUID)
RETURNS TABLE (
    school_id UUID,
    school_name TEXT,
    total_teachers BIGINT,
    total_students BIGINT,
    total_grades BIGINT,
    average_score NUMERIC,
    grade_distribution JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id as school_id,
        s.name as school_name,
        COUNT(DISTINCT g.teacher_id)::BIGINT as total_teachers,
        COUNT(DISTINCT g.student_id)::BIGINT as total_students,
        COUNT(g.id)::BIGINT as total_grades,
        ROUND(AVG(g.score)::numeric, 1) as average_score,
        jsonb_build_object(
            'A', COUNT(*) FILTER (WHERE g.score >= 90),
            'B', COUNT(*) FILTER (WHERE g.score >= 80 AND g.score < 90),
            'C', COUNT(*) FILTER (WHERE g.score >= 70 AND g.score < 80),
            'D', COUNT(*) FILTER (WHERE g.score >= 60 AND g.score < 70),
            'F', COUNT(*) FILTER (WHERE g.score < 60)
        ) as grade_distribution
    FROM schools s
    LEFT JOIN grades g ON g.school_id = s.id
    WHERE s.district_id = p_district_id
    GROUP BY s.id, s.name
    ORDER BY average_score DESC NULLS LAST;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get teacher leaderboard for school
CREATE OR REPLACE FUNCTION get_teacher_leaderboard(p_school_id UUID)
RETURNS TABLE (
    teacher_id UUID,
    teacher_name TEXT,
    total_grades BIGINT,
    total_students BIGINT,
    average_score NUMERIC,
    last_graded_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id as teacher_id,
        p.full_name as teacher_name,
        COUNT(g.id)::BIGINT as total_grades,
        COUNT(DISTINCT g.student_id)::BIGINT as total_students,
        ROUND(AVG(g.score)::numeric, 1) as average_score,
        MAX(g.graded_at) as last_graded_at
    FROM profiles p
    LEFT JOIN grades g ON g.teacher_id = p.id
    WHERE p.school_id = p_school_id
    AND p.role = 'teacher'
    GROUP BY p.id, p.full_name
    ORDER BY total_grades DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ══════════════════════════════════════════════════════════════
-- TRIGGERS
-- ══════════════════════════════════════════════════════════════

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_districts_updated_at
    BEFORE UPDATE ON districts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_schools_updated_at
    BEFORE UPDATE ON schools
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-create profile on user signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO profiles (id, email, full_name, role)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email),
        COALESCE((NEW.raw_user_meta_data->>'role')::user_role, 'teacher')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();
```

---

## Backend Implementation

### File: `backend/supabase_client.py`

```python
"""
Supabase Client for Multi-District Graider
==========================================
Handles all database operations with Supabase.
"""

import os
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Lazy import to avoid issues if supabase not installed
_supabase_client = None
_supabase_admin = None


def get_client():
    """Get Supabase client for authenticated requests."""
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if url and key:
            _supabase_client = create_client(url, key)
    return _supabase_client


def get_admin_client():
    """Get Supabase client with service role (bypasses RLS)."""
    global _supabase_admin
    if _supabase_admin is None:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if url and key:
            _supabase_admin = create_client(url, key)
    return _supabase_admin


def is_configured() -> bool:
    """Check if Supabase is configured."""
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))


# ══════════════════════════════════════════════════════════════
# AUTHENTICATION
# ══════════════════════════════════════════════════════════════

def sign_up(email: str, password: str, full_name: str, role: str = "teacher"):
    """Register a new user."""
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}

    result = client.auth.sign_up({
        "email": email,
        "password": password,
        "options": {
            "data": {
                "full_name": full_name,
                "role": role
            }
        }
    })
    return result


def sign_in(email: str, password: str):
    """Sign in a user."""
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}

    result = client.auth.sign_in_with_password({
        "email": email,
        "password": password
    })
    return result


def sign_out():
    """Sign out current user."""
    client = get_client()
    if client:
        client.auth.sign_out()


def get_current_user():
    """Get currently authenticated user."""
    client = get_client()
    if not client:
        return None
    return client.auth.get_user()


def set_session(access_token: str, refresh_token: str):
    """Set auth session from tokens."""
    client = get_client()
    if client:
        client.auth.set_session(access_token, refresh_token)


# ══════════════════════════════════════════════════════════════
# DISTRICT MANAGEMENT
# ══════════════════════════════════════════════════════════════

def create_district(name: str, slug: str, state: str = "FL", settings: dict = None) -> dict:
    """Create a new district (super_admin only)."""
    client = get_admin_client()
    if not client:
        return {"error": "Supabase not configured"}

    data = {
        "name": name,
        "slug": slug,
        "state": state,
    }
    if settings:
        data["settings"] = settings

    result = client.table("districts").insert(data).execute()
    return result.data[0] if result.data else {"error": "Failed to create district"}


def get_district(district_id: str) -> Optional[dict]:
    """Get district by ID."""
    client = get_client()
    if not client:
        return None

    result = client.table("districts").select("*").eq("id", district_id).single().execute()
    return result.data


def list_districts() -> List[dict]:
    """List all districts (super_admin only)."""
    client = get_admin_client()
    if not client:
        return []

    result = client.table("districts").select("*").order("name").execute()
    return result.data or []


# ══════════════════════════════════════════════════════════════
# SCHOOL MANAGEMENT
# ══════════════════════════════════════════════════════════════

def create_school(district_id: str, name: str, school_code: str = None, **kwargs) -> dict:
    """Create a new school."""
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}

    data = {
        "district_id": district_id,
        "name": name,
        "school_code": school_code,
        **kwargs
    }

    result = client.table("schools").insert(data).execute()
    return result.data[0] if result.data else {"error": "Failed to create school"}


def get_school(school_id: str) -> Optional[dict]:
    """Get school by ID."""
    client = get_client()
    if not client:
        return None

    result = client.table("schools").select("*").eq("id", school_id).single().execute()
    return result.data


def list_schools(district_id: str = None) -> List[dict]:
    """List schools, optionally filtered by district."""
    client = get_client()
    if not client:
        return []

    query = client.table("schools").select("*")
    if district_id:
        query = query.eq("district_id", district_id)

    result = query.order("name").execute()
    return result.data or []


# ══════════════════════════════════════════════════════════════
# USER/PROFILE MANAGEMENT
# ══════════════════════════════════════════════════════════════

def get_profile(user_id: str) -> Optional[dict]:
    """Get user profile."""
    client = get_client()
    if not client:
        return None

    result = client.table("profiles").select("*, districts(name), schools(name)").eq("id", user_id).single().execute()
    return result.data


def update_profile(user_id: str, updates: dict) -> dict:
    """Update user profile."""
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}

    result = client.table("profiles").update(updates).eq("id", user_id).execute()
    return result.data[0] if result.data else {"error": "Failed to update profile"}


def assign_user_to_district(user_id: str, district_id: str, school_id: str = None, role: str = None) -> dict:
    """Assign a user to a district and optionally a school."""
    updates = {"district_id": district_id}
    if school_id:
        updates["school_id"] = school_id
    if role:
        updates["role"] = role

    return update_profile(user_id, updates)


def list_teachers(school_id: str = None, district_id: str = None) -> List[dict]:
    """List teachers, filtered by school or district."""
    client = get_client()
    if not client:
        return []

    query = client.table("profiles").select("*").eq("role", "teacher")

    if school_id:
        query = query.eq("school_id", school_id)
    elif district_id:
        query = query.eq("district_id", district_id)

    result = query.order("full_name").execute()
    return result.data or []


# ══════════════════════════════════════════════════════════════
# GRADE SYNC
# ══════════════════════════════════════════════════════════════

def hash_student_id(student_id: str, district_id: str) -> str:
    """Create anonymized hash of student ID (salted with district)."""
    salted = f"{district_id}:{student_id}"
    return hashlib.sha256(salted.encode()).hexdigest()[:16]


def get_or_create_student(district_id: str, school_id: str, student_hash: str, grade_level: str = None) -> str:
    """Get or create a student record, return student UUID."""
    client = get_client()
    if not client:
        return None

    # Check if exists
    result = client.table("students").select("id").eq("district_id", district_id).eq("student_hash", student_hash).execute()

    if result.data:
        return result.data[0]["id"]

    # Create new
    new_student = client.table("students").insert({
        "district_id": district_id,
        "school_id": school_id,
        "student_hash": student_hash,
        "grade_level": grade_level,
    }).execute()

    return new_student.data[0]["id"] if new_student.data else None


def sync_grades(
    teacher_id: str,
    district_id: str,
    school_id: str,
    grades_data: List[dict],
    batch_size: int = 100
) -> dict:
    """
    Sync grades to Supabase.

    Args:
        teacher_id: UUID of the teacher
        district_id: UUID of the district
        school_id: UUID of the school
        grades_data: List of grade records (from master_grades.csv or grading_state)
        batch_size: Number of records to insert per batch

    Returns:
        dict with sync results
    """
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}

    # Create sync log entry
    sync_log = client.table("sync_logs").insert({
        "district_id": district_id,
        "school_id": school_id,
        "teacher_id": teacher_id,
        "status": "syncing",
        "records_total": len(grades_data),
    }).execute()

    sync_log_id = sync_log.data[0]["id"] if sync_log.data else None

    records_synced = 0
    records_failed = 0
    errors = []

    # Process in batches
    for i in range(0, len(grades_data), batch_size):
        batch = grades_data[i:i + batch_size]
        batch_records = []

        for g in batch:
            try:
                # Get student ID from raw data
                raw_student_id = g.get("Student ID") or g.get("student_id") or ""
                student_hash = hash_student_id(raw_student_id, district_id)
                grade_level = g.get("Grade Level") or g.get("grade_level")

                # Get or create student
                student_id = get_or_create_student(district_id, school_id, student_hash, grade_level)
                if not student_id:
                    records_failed += 1
                    continue

                # Map grade data
                record = {
                    "district_id": district_id,
                    "school_id": school_id,
                    "teacher_id": teacher_id,
                    "student_id": student_id,
                    "assignment_name": g.get("Assignment") or g.get("assignment") or "Unknown",
                    "subject": g.get("Subject") or g.get("subject"),
                    "grade_level": grade_level,
                    "quarter": g.get("Quarter") or g.get("quarter"),
                    "score": float(g.get("Overall Score") or g.get("score") or 0),
                    "letter_grade": g.get("Letter Grade") or g.get("letter_grade"),
                    "content_accuracy": float(g.get("Content Accuracy") or g.get("content_accuracy") or 0) or None,
                    "completeness": float(g.get("Completeness") or g.get("completeness") or 0) or None,
                    "writing_quality": float(g.get("Writing Quality") or g.get("writing_quality") or 0) or None,
                    "effort_engagement": float(g.get("Effort Engagement") or g.get("effort_engagement") or 0) or None,
                    "authenticity_flag": g.get("authenticity_flag") or "clean",
                    "is_handwritten": g.get("is_handwritten", False),
                    "marker_status": g.get("marker_status") or "verified",
                    "feedback": g.get("Feedback") or g.get("feedback"),
                    "source_filename": g.get("Filename") or g.get("filename"),
                    "graded_at": g.get("Date") or g.get("graded_at") or datetime.now().isoformat(),
                }

                # Clean up None values for letter_grade enum
                if record["letter_grade"] and record["letter_grade"] not in ['A', 'B', 'C', 'D', 'F']:
                    record["letter_grade"] = None

                batch_records.append(record)

            except Exception as e:
                records_failed += 1
                errors.append(str(e))

        # Insert batch
        if batch_records:
            try:
                result = client.table("grades").insert(batch_records).execute()
                records_synced += len(result.data) if result.data else 0
            except Exception as e:
                records_failed += len(batch_records)
                errors.append(str(e))

    # Update sync log
    if sync_log_id:
        status = "completed" if records_failed == 0 else "completed" if records_synced > 0 else "failed"
        client.table("sync_logs").update({
            "status": status,
            "records_synced": records_synced,
            "records_failed": records_failed,
            "error_message": "; ".join(errors[:5]) if errors else None,
            "completed_at": datetime.now().isoformat(),
        }).eq("id", sync_log_id).execute()

    # Update teacher's last_sync_at
    client.table("profiles").update({
        "last_sync_at": datetime.now().isoformat()
    }).eq("id", teacher_id).execute()

    return {
        "status": "success" if records_synced > 0 else "failed",
        "records_synced": records_synced,
        "records_failed": records_failed,
        "errors": errors[:5] if errors else [],
    }


# ══════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════

def get_teacher_stats(teacher_id: str) -> Optional[dict]:
    """Get stats for a specific teacher."""
    client = get_client()
    if not client:
        return None

    result = client.table("teacher_stats").select("*").eq("teacher_id", teacher_id).single().execute()
    return result.data


def get_school_stats(school_id: str) -> Optional[dict]:
    """Get stats for a specific school."""
    client = get_client()
    if not client:
        return None

    result = client.table("school_stats").select("*").eq("school_id", school_id).single().execute()
    return result.data


def get_district_stats(district_id: str) -> Optional[dict]:
    """Get stats for a district."""
    client = get_client()
    if not client:
        return None

    result = client.table("district_stats").select("*").eq("district_id", district_id).single().execute()
    return result.data


def get_district_analytics(district_id: str) -> dict:
    """Get comprehensive district analytics."""
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}

    # Get district stats
    stats = get_district_stats(district_id)

    # Get school comparison
    schools = client.rpc("get_school_comparison", {"p_district_id": district_id}).execute()

    # Get trends
    trends = client.rpc("get_district_trends", {"p_district_id": district_id, "p_months": 12}).execute()

    # Get subject breakdown
    subjects = client.table("subject_stats").select("*").eq("district_id", district_id).is_("school_id", "null").execute()

    return {
        "summary": stats or {},
        "schools": schools.data or [],
        "trends": trends.data or [],
        "by_subject": subjects.data or [],
    }


def get_school_analytics(school_id: str) -> dict:
    """Get comprehensive school analytics."""
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}

    # Get school stats
    stats = get_school_stats(school_id)

    # Get teacher leaderboard
    teachers = client.rpc("get_teacher_leaderboard", {"p_school_id": school_id}).execute()

    # Get subject breakdown
    subjects = client.table("subject_stats").select("*").eq("school_id", school_id).execute()

    # Get quarterly stats
    quarters = client.table("quarterly_stats").select("*").eq("school_id", school_id).execute()

    return {
        "summary": stats or {},
        "teachers": teachers.data or [],
        "by_subject": subjects.data or [],
        "by_quarter": quarters.data or [],
    }
```

---

## API Routes

### File: `backend/routes/supabase_routes.py`

```python
"""
Supabase API Routes for Multi-District Graider
"""

from flask import Blueprint, request, jsonify, g
from functools import wraps
import csv
import os

from backend import supabase_client as sb

supabase_bp = Blueprint('supabase', __name__)


# ══════════════════════════════════════════════════════════════
# AUTH MIDDLEWARE
# ══════════════════════════════════════════════════════════════

def require_auth(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authentication required"}), 401

        token = auth_header.split(' ')[1]

        # Set session and get user
        try:
            sb.set_session(token, token)  # Using same token for simplicity
            user = sb.get_current_user()
            if not user:
                return jsonify({"error": "Invalid token"}), 401
            g.user = user
            g.user_id = user.user.id
        except Exception as e:
            return jsonify({"error": str(e)}), 401

        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """Decorator to require specific role(s)."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'user_id'):
                return jsonify({"error": "Authentication required"}), 401

            profile = sb.get_profile(g.user_id)
            if not profile or profile.get('role') not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403

            g.profile = profile
            return f(*args, **kwargs)
        return decorated
    return decorator


# ══════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════

@supabase_bp.route('/api/auth/signup', methods=['POST'])
def signup():
    """Register a new user."""
    data = request.json

    required = ['email', 'password', 'full_name']
    if not all(data.get(f) for f in required):
        return jsonify({"error": "email, password, and full_name required"}), 400

    result = sb.sign_up(
        data['email'],
        data['password'],
        data['full_name'],
        data.get('role', 'teacher')
    )

    if hasattr(result, 'user') and result.user:
        return jsonify({
            "status": "success",
            "user_id": result.user.id,
            "message": "Check your email to confirm registration"
        })

    return jsonify({"error": "Registration failed"}), 400


@supabase_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Sign in a user."""
    data = request.json

    if not data.get('email') or not data.get('password'):
        return jsonify({"error": "email and password required"}), 400

    result = sb.sign_in(data['email'], data['password'])

    if hasattr(result, 'session') and result.session:
        profile = sb.get_profile(result.user.id)
        return jsonify({
            "status": "success",
            "access_token": result.session.access_token,
            "refresh_token": result.session.refresh_token,
            "user": {
                "id": result.user.id,
                "email": result.user.email,
                "profile": profile
            }
        })

    return jsonify({"error": "Invalid credentials"}), 401


@supabase_bp.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Sign out current user."""
    sb.sign_out()
    return jsonify({"status": "success"})


@supabase_bp.route('/api/auth/me', methods=['GET'])
@require_auth
def get_me():
    """Get current user profile."""
    profile = sb.get_profile(g.user_id)
    return jsonify(profile or {"error": "Profile not found"})


# ══════════════════════════════════════════════════════════════
# DISTRICT ROUTES
# ══════════════════════════════════════════════════════════════

@supabase_bp.route('/api/districts', methods=['GET'])
@require_auth
@require_role('super_admin')
def list_districts():
    """List all districts (super_admin only)."""
    districts = sb.list_districts()
    return jsonify({"districts": districts})


@supabase_bp.route('/api/districts', methods=['POST'])
@require_auth
@require_role('super_admin')
def create_district():
    """Create a new district."""
    data = request.json

    if not data.get('name') or not data.get('slug'):
        return jsonify({"error": "name and slug required"}), 400

    result = sb.create_district(
        data['name'],
        data['slug'],
        data.get('state', 'FL'),
        data.get('settings')
    )

    return jsonify(result)


@supabase_bp.route('/api/districts/<district_id>', methods=['GET'])
@require_auth
def get_district(district_id):
    """Get district details."""
    district = sb.get_district(district_id)
    if not district:
        return jsonify({"error": "District not found"}), 404
    return jsonify(district)


# ══════════════════════════════════════════════════════════════
# SCHOOL ROUTES
# ══════════════════════════════════════════════════════════════

@supabase_bp.route('/api/schools', methods=['GET'])
@require_auth
def list_schools():
    """List schools in user's district."""
    profile = sb.get_profile(g.user_id)
    district_id = request.args.get('district_id') or (profile.get('district_id') if profile else None)

    schools = sb.list_schools(district_id)
    return jsonify({"schools": schools})


@supabase_bp.route('/api/schools', methods=['POST'])
@require_auth
@require_role('district_admin', 'super_admin')
def create_school():
    """Create a new school."""
    data = request.json
    profile = sb.get_profile(g.user_id)

    district_id = data.get('district_id') or profile.get('district_id')
    if not district_id:
        return jsonify({"error": "district_id required"}), 400

    if not data.get('name'):
        return jsonify({"error": "name required"}), 400

    result = sb.create_school(
        district_id,
        data['name'],
        data.get('school_code'),
        **{k: v for k, v in data.items() if k not in ['district_id', 'name', 'school_code']}
    )

    return jsonify(result)


@supabase_bp.route('/api/schools/<school_id>', methods=['GET'])
@require_auth
def get_school(school_id):
    """Get school details."""
    school = sb.get_school(school_id)
    if not school:
        return jsonify({"error": "School not found"}), 404
    return jsonify(school)


# ══════════════════════════════════════════════════════════════
# TEACHER ROUTES
# ══════════════════════════════════════════════════════════════

@supabase_bp.route('/api/teachers', methods=['GET'])
@require_auth
def list_teachers():
    """List teachers in school or district."""
    profile = sb.get_profile(g.user_id)

    school_id = request.args.get('school_id')
    district_id = request.args.get('district_id') or profile.get('district_id')

    teachers = sb.list_teachers(school_id, district_id)
    return jsonify({"teachers": teachers})


@supabase_bp.route('/api/teachers/<teacher_id>/assign', methods=['POST'])
@require_auth
@require_role('district_admin', 'super_admin')
def assign_teacher(teacher_id):
    """Assign a teacher to a district/school."""
    data = request.json

    result = sb.assign_user_to_district(
        teacher_id,
        data.get('district_id'),
        data.get('school_id'),
        data.get('role')
    )

    return jsonify(result)


# ══════════════════════════════════════════════════════════════
# SYNC ROUTES
# ══════════════════════════════════════════════════════════════

@supabase_bp.route('/api/sync', methods=['POST'])
@require_auth
def sync_grades():
    """Sync grades to Supabase."""
    data = request.json
    profile = sb.get_profile(g.user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    district_id = profile.get('district_id')
    school_id = profile.get('school_id')

    if not district_id or not school_id:
        return jsonify({"error": "User not assigned to a district/school"}), 400

    # Option 1: Grades data provided directly
    if data.get('grades'):
        result = sb.sync_grades(
            g.user_id,
            district_id,
            school_id,
            data['grades']
        )
        return jsonify(result)

    # Option 2: Read from output folder
    output_folder = data.get('output_folder')
    if output_folder:
        master_file = os.path.join(output_folder, "master_grades.csv")
        if not os.path.exists(master_file):
            return jsonify({"error": "master_grades.csv not found"}), 404

        grades_data = []
        with open(master_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                grades_data.append(row)

        result = sb.sync_grades(
            g.user_id,
            district_id,
            school_id,
            grades_data
        )
        return jsonify(result)

    return jsonify({"error": "grades or output_folder required"}), 400


@supabase_bp.route('/api/sync/status', methods=['GET'])
@require_auth
def sync_status():
    """Get sync status/history for current teacher."""
    client = sb.get_client()
    if not client:
        return jsonify({"error": "Supabase not configured"}), 500

    result = client.table("sync_logs").select("*").eq("teacher_id", g.user_id).order("started_at", desc=True).limit(10).execute()

    return jsonify({"sync_logs": result.data or []})


# ══════════════════════════════════════════════════════════════
# ANALYTICS ROUTES
# ══════════════════════════════════════════════════════════════

@supabase_bp.route('/api/analytics/me', methods=['GET'])
@require_auth
def my_analytics():
    """Get current teacher's analytics."""
    stats = sb.get_teacher_stats(g.user_id)
    return jsonify(stats or {"error": "No data available"})


@supabase_bp.route('/api/analytics/school', methods=['GET'])
@require_auth
@require_role('principal', 'district_admin', 'super_admin')
def school_analytics():
    """Get school analytics."""
    profile = sb.get_profile(g.user_id)
    school_id = request.args.get('school_id') or profile.get('school_id')

    if not school_id:
        return jsonify({"error": "school_id required"}), 400

    analytics = sb.get_school_analytics(school_id)
    return jsonify(analytics)


@supabase_bp.route('/api/analytics/district', methods=['GET'])
@require_auth
@require_role('district_admin', 'super_admin')
def district_analytics():
    """Get district analytics."""
    profile = sb.get_profile(g.user_id)
    district_id = request.args.get('district_id') or profile.get('district_id')

    if not district_id:
        return jsonify({"error": "district_id required"}), 400

    analytics = sb.get_district_analytics(district_id)
    return jsonify(analytics)


@supabase_bp.route('/api/analytics/compare', methods=['GET'])
@require_auth
@require_role('district_admin', 'super_admin')
def compare_schools():
    """Compare schools in district."""
    profile = sb.get_profile(g.user_id)
    district_id = request.args.get('district_id') or profile.get('district_id')

    if not district_id:
        return jsonify({"error": "district_id required"}), 400

    client = sb.get_client()
    result = client.rpc("get_school_comparison", {"p_district_id": district_id}).execute()

    return jsonify({"schools": result.data or []})
```

### File: `backend/routes/__init__.py` (Update)

```python
# Add to existing imports
from .supabase_routes import supabase_bp

def register_routes(app, grading_state, run_grading_thread, reset_state):
    # ... existing registrations ...

    # Supabase routes (multi-district)
    app.register_blueprint(supabase_bp)
```

---

## Frontend Implementation

### File: `frontend/src/lib/supabase.js`

```javascript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null

export const isSupabaseConfigured = () => !!supabase

// Auth helpers
export const signUp = async (email, password, fullName, role = 'teacher') => {
  if (!supabase) return { error: 'Supabase not configured' }

  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: { full_name: fullName, role }
    }
  })

  return { data, error }
}

export const signIn = async (email, password) => {
  if (!supabase) return { error: 'Supabase not configured' }

  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password
  })

  return { data, error }
}

export const signOut = async () => {
  if (!supabase) return
  await supabase.auth.signOut()
}

export const getSession = async () => {
  if (!supabase) return null
  const { data: { session } } = await supabase.auth.getSession()
  return session
}

export const getUser = async () => {
  if (!supabase) return null
  const { data: { user } } = await supabase.auth.getUser()
  return user
}

// Real-time subscriptions
export const subscribeToGrades = (districtId, callback) => {
  if (!supabase) return null

  return supabase
    .channel('grades-changes')
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'grades',
        filter: `district_id=eq.${districtId}`
      },
      callback
    )
    .subscribe()
}

export const unsubscribe = (subscription) => {
  if (subscription) {
    supabase.removeChannel(subscription)
  }
}
```

### File: `frontend/src/contexts/AuthContext.jsx`

```jsx
import { createContext, useContext, useEffect, useState } from 'react'
import { supabase, getSession, getUser, signIn, signOut, signUp } from '../lib/supabase'

const AuthContext = createContext({})

export const useAuth = () => useContext(AuthContext)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    getSession().then(session => {
      if (session?.user) {
        setUser(session.user)
        loadProfile(session.user.id)
      }
      setLoading(false)
    })

    // Listen for auth changes
    if (supabase) {
      const { data: { subscription } } = supabase.auth.onAuthStateChange(
        async (event, session) => {
          if (session?.user) {
            setUser(session.user)
            loadProfile(session.user.id)
          } else {
            setUser(null)
            setProfile(null)
          }
        }
      )

      return () => subscription.unsubscribe()
    }
  }, [])

  const loadProfile = async (userId) => {
    if (!supabase) return

    const { data } = await supabase
      .from('profiles')
      .select('*, districts(name, slug), schools(name)')
      .eq('id', userId)
      .single()

    setProfile(data)
  }

  const login = async (email, password) => {
    const { data, error } = await signIn(email, password)
    if (error) throw error
    return data
  }

  const register = async (email, password, fullName, role) => {
    const { data, error } = await signUp(email, password, fullName, role)
    if (error) throw error
    return data
  }

  const logout = async () => {
    await signOut()
    setUser(null)
    setProfile(null)
  }

  const value = {
    user,
    profile,
    loading,
    login,
    register,
    logout,
    isAuthenticated: !!user,
    isTeacher: profile?.role === 'teacher',
    isPrincipal: profile?.role === 'principal',
    isDistrictAdmin: profile?.role === 'district_admin',
    isSuperAdmin: profile?.role === 'super_admin',
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
```

### File: `frontend/src/components/DistrictDashboard.jsx`

```jsx
import { useState, useEffect } from 'react'
import { supabase, subscribeToGrades, unsubscribe } from '../lib/supabase'
import { useAuth } from '../contexts/AuthContext'
import Icon from './Icon'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

const COLORS = ['#4ade80', '#60a5fa', '#fbbf24', '#f97316', '#ef4444']

export default function DistrictDashboard() {
  const { profile } = useAuth()
  const [view, setView] = useState('district') // district, school, teacher
  const [analytics, setAnalytics] = useState(null)
  const [schools, setSchools] = useState([])
  const [selectedSchool, setSelectedSchool] = useState(null)
  const [schoolAnalytics, setSchoolAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [subscription, setSubscription] = useState(null)

  // Load district analytics
  useEffect(() => {
    if (profile?.district_id) {
      loadDistrictAnalytics()
      loadSchools()

      // Subscribe to real-time updates
      const sub = subscribeToGrades(profile.district_id, (payload) => {
        console.log('New grade:', payload)
        // Refresh analytics on new data
        loadDistrictAnalytics()
      })
      setSubscription(sub)

      return () => unsubscribe(sub)
    }
  }, [profile?.district_id])

  // Load school analytics when selected
  useEffect(() => {
    if (selectedSchool) {
      loadSchoolAnalytics(selectedSchool)
    }
  }, [selectedSchool])

  const loadDistrictAnalytics = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/analytics/district', {
        headers: {
          'Authorization': `Bearer ${(await supabase.auth.getSession()).data.session?.access_token}`
        }
      })
      const data = await response.json()
      if (!data.error) {
        setAnalytics(data)
      }
    } catch (e) {
      console.error('Failed to load analytics:', e)
    }
    setLoading(false)
  }

  const loadSchools = async () => {
    try {
      const response = await fetch('/api/schools', {
        headers: {
          'Authorization': `Bearer ${(await supabase.auth.getSession()).data.session?.access_token}`
        }
      })
      const data = await response.json()
      setSchools(data.schools || [])
    } catch (e) {
      console.error('Failed to load schools:', e)
    }
  }

  const loadSchoolAnalytics = async (schoolId) => {
    try {
      const response = await fetch(`/api/analytics/school?school_id=${schoolId}`, {
        headers: {
          'Authorization': `Bearer ${(await supabase.auth.getSession()).data.session?.access_token}`
        }
      })
      const data = await response.json()
      if (!data.error) {
        setSchoolAnalytics(data)
      }
    } catch (e) {
      console.error('Failed to load school analytics:', e)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '60px', textAlign: 'center' }}>
        <Icon name="Loader2" size={48} className="spin" />
        <p style={{ marginTop: '20px', color: 'var(--text-secondary)' }}>Loading analytics...</p>
      </div>
    )
  }

  return (
    <div className="fade-in">
      {/* View Selector */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <button
          onClick={() => { setView('district'); setSelectedSchool(null); }}
          className={`btn ${view === 'district' ? 'btn-primary' : 'btn-secondary'}`}
        >
          <Icon name="Building2" size={16} /> District Overview
        </button>
        <button
          onClick={() => setView('school')}
          className={`btn ${view === 'school' ? 'btn-primary' : 'btn-secondary'}`}
        >
          <Icon name="School" size={16} /> School View
        </button>
      </div>

      {/* District Overview */}
      {view === 'district' && analytics && (
        <>
          <h2 style={{
            fontSize: '1.3rem',
            fontWeight: 700,
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px'
          }}>
            <Icon name="Building2" size={24} />
            {profile?.districts?.name || 'District'} Analytics
            <span style={{
              fontSize: '0.75rem',
              background: 'rgba(16,185,129,0.2)',
              color: '#10b981',
              padding: '4px 8px',
              borderRadius: '12px',
              marginLeft: '10px'
            }}>
              Live
            </span>
          </h2>

          {/* Summary Cards */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(5, 1fr)',
            gap: '15px',
            marginBottom: '20px'
          }}>
            {[
              { label: 'Schools', value: analytics.summary?.total_schools || 0, icon: 'School', color: '#6366f1' },
              { label: 'Teachers', value: analytics.summary?.total_teachers || 0, icon: 'Users', color: '#8b5cf6' },
              { label: 'Students', value: analytics.summary?.total_students || 0, icon: 'GraduationCap', color: '#ec4899' },
              { label: 'Grades', value: analytics.summary?.total_grades || 0, icon: 'FileCheck', color: '#10b981' },
              { label: 'Avg Score', value: `${analytics.summary?.average_score || 0}%`, icon: 'TrendingUp', color: '#f59e0b' },
            ].map((stat, i) => (
              <div key={i} className="glass-card" style={{ padding: '20px', textAlign: 'center' }}>
                <Icon name={stat.icon} size={24} style={{ color: stat.color, marginBottom: '10px' }} />
                <div style={{ fontSize: '1.8rem', fontWeight: 800, color: stat.color }}>{stat.value}</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{stat.label}</div>
              </div>
            ))}
          </div>

          {/* Charts Row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px', marginBottom: '20px' }}>
            {/* Grade Distribution */}
            <div className="glass-card" style={{ padding: '25px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px' }}>
                <Icon name="PieChart" size={20} /> Grade Distribution
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={[
                      { name: 'A', value: analytics.summary?.count_a || 0 },
                      { name: 'B', value: analytics.summary?.count_b || 0 },
                      { name: 'C', value: analytics.summary?.count_c || 0 },
                      { name: 'D', value: analytics.summary?.count_d || 0 },
                      { name: 'F', value: analytics.summary?.count_f || 0 },
                    ].filter(d => d.value > 0)}
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {COLORS.map((c, i) => <Cell key={i} fill={c} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Trends */}
            <div className="glass-card" style={{ padding: '25px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px' }}>
                <Icon name="TrendingUp" size={20} /> Monthly Trends
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={analytics.trends || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--glass-border)" />
                  <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="average_score" stroke="#6366f1" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* School Comparison Table */}
          <div className="glass-card" style={{ padding: '25px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px' }}>
              <Icon name="BarChart3" size={20} /> School Comparison
            </h3>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--glass-border)' }}>
                  <th style={{ textAlign: 'left', padding: '12px' }}>School</th>
                  <th style={{ textAlign: 'right', padding: '12px' }}>Teachers</th>
                  <th style={{ textAlign: 'right', padding: '12px' }}>Students</th>
                  <th style={{ textAlign: 'right', padding: '12px' }}>Grades</th>
                  <th style={{ textAlign: 'right', padding: '12px' }}>Avg Score</th>
                  <th style={{ textAlign: 'right', padding: '12px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {(analytics.schools || []).map((school, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--glass-border)' }}>
                    <td style={{ padding: '12px', fontWeight: 500 }}>{school.school_name}</td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>{school.total_teachers}</td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>{school.total_students}</td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>{school.total_grades}</td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>
                      <span style={{
                        padding: '4px 12px',
                        borderRadius: '20px',
                        fontWeight: 700,
                        background: school.average_score >= 80 ? 'rgba(74,222,128,0.2)' :
                                   school.average_score >= 70 ? 'rgba(251,191,36,0.2)' : 'rgba(248,113,113,0.2)',
                        color: school.average_score >= 80 ? '#4ade80' :
                               school.average_score >= 70 ? '#fbbf24' : '#f87171',
                      }}>
                        {school.average_score}%
                      </span>
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>
                      <button
                        onClick={() => { setSelectedSchool(school.school_id); setView('school'); }}
                        className="btn btn-secondary"
                        style={{ padding: '4px 8px', fontSize: '0.8rem' }}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* School View */}
      {view === 'school' && (
        <div className="glass-card" style={{ padding: '25px' }}>
          <h3 style={{ marginBottom: '15px' }}>Select a School</h3>
          <select
            className="input"
            value={selectedSchool || ''}
            onChange={(e) => setSelectedSchool(e.target.value)}
            style={{ marginBottom: '20px' }}
          >
            <option value="">Choose school...</option>
            {schools.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>

          {schoolAnalytics && (
            <>
              {/* School Stats */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: '15px',
                marginBottom: '20px'
              }}>
                {[
                  { label: 'Teachers', value: schoolAnalytics.summary?.total_teachers || 0, icon: 'Users', color: '#6366f1' },
                  { label: 'Students', value: schoolAnalytics.summary?.total_students || 0, icon: 'GraduationCap', color: '#8b5cf6' },
                  { label: 'Grades', value: schoolAnalytics.summary?.total_grades || 0, icon: 'FileCheck', color: '#10b981' },
                  { label: 'Avg Score', value: `${schoolAnalytics.summary?.average_score || 0}%`, icon: 'TrendingUp', color: '#f59e0b' },
                ].map((stat, i) => (
                  <div key={i} style={{
                    padding: '15px',
                    background: 'var(--input-bg)',
                    borderRadius: '12px',
                    textAlign: 'center'
                  }}>
                    <Icon name={stat.icon} size={20} style={{ color: stat.color }} />
                    <div style={{ fontSize: '1.5rem', fontWeight: 700, color: stat.color }}>{stat.value}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{stat.label}</div>
                  </div>
                ))}
              </div>

              {/* Teacher Leaderboard */}
              <h4 style={{ marginBottom: '10px' }}>Teacher Performance</h4>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--glass-border)' }}>
                    <th style={{ textAlign: 'left', padding: '10px' }}>Teacher</th>
                    <th style={{ textAlign: 'right', padding: '10px' }}>Grades</th>
                    <th style={{ textAlign: 'right', padding: '10px' }}>Students</th>
                    <th style={{ textAlign: 'right', padding: '10px' }}>Avg Score</th>
                  </tr>
                </thead>
                <tbody>
                  {(schoolAnalytics.teachers || []).map((t, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--glass-border)' }}>
                      <td style={{ padding: '10px' }}>{t.teacher_name}</td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>{t.total_grades}</td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>{t.total_students}</td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>{t.average_score}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {/* No Data State */}
      {!analytics && (
        <div className="glass-card" style={{ padding: '60px', textAlign: 'center' }}>
          <Icon name="Building2" size={64} style={{ opacity: 0.3 }} />
          <h2 style={{ marginTop: '20px' }}>No District Data Yet</h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '10px' }}>
            Teachers need to sync their grading data to see analytics here.
          </p>
        </div>
      )}
    </div>
  )
}
```

---

## Environment Variables

### File: `.env` (Backend)

```bash
# OpenAI (existing)
OPENAI_API_KEY=sk-...

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### File: `frontend/.env`

```bash
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Deployment Guide

### 1. Supabase Setup

```bash
# Install Supabase CLI
npm install -g supabase

# Login
supabase login

# Link to project
supabase link --project-ref your-project-ref

# Run migrations
supabase db push
```

### 2. Enable Row Level Security

In Supabase Dashboard:
1. Go to Authentication > Policies
2. Verify all tables have RLS enabled
3. Test policies work correctly

### 3. Configure Auth

In Supabase Dashboard > Authentication > Settings:
1. Enable Email/Password sign-in
2. Configure email templates
3. Add redirect URLs for your domain

### 4. Deploy Backend

```bash
# Install dependencies
pip install supabase python-dotenv

# Set environment variables
export SUPABASE_URL=https://...
export SUPABASE_ANON_KEY=eyJ...
export SUPABASE_SERVICE_KEY=eyJ...

# Run
python backend/app.py
```

### 5. Deploy Frontend

```bash
cd frontend
npm install @supabase/supabase-js
npm run build
```

---

## Migration from Local-Only

### For Existing Teachers

1. Teacher logs into new system
2. Admin assigns them to district/school
3. Teacher clicks "Sync to Cloud"
4. Local master_grades.csv uploaded to Supabase
5. Future grades auto-sync

### Migration Script

```python
# scripts/migrate_to_supabase.py
import os
import csv
from backend.supabase_client import sync_grades

def migrate_teacher(teacher_id, district_id, school_id, output_folder):
    """Migrate a teacher's local data to Supabase."""
    master_file = os.path.join(output_folder, "master_grades.csv")

    if not os.path.exists(master_file):
        print(f"No data found at {master_file}")
        return

    grades = []
    with open(master_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            grades.append(row)

    print(f"Migrating {len(grades)} grades...")
    result = sync_grades(teacher_id, district_id, school_id, grades)
    print(f"Result: {result}")

if __name__ == "__main__":
    # Example usage
    migrate_teacher(
        teacher_id="uuid-from-supabase",
        district_id="district-uuid",
        school_id="school-uuid",
        output_folder="/Users/teacher/Downloads/Graider/Results"
    )
```

---

## Summary

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Database** | Supabase (PostgreSQL) | Multi-tenant data storage |
| **Auth** | Supabase Auth | User management, SSO-ready |
| **API** | Flask + Supabase Client | Backend logic |
| **Real-time** | Supabase Subscriptions | Live dashboard updates |
| **Frontend** | React + Supabase JS | User interface |
| **Security** | Row-Level Security | Data isolation |

### Implementation Order

1. ✅ Set up Supabase project
2. ✅ Run database migrations
3. ✅ Implement `supabase_client.py`
4. ✅ Add API routes
5. ✅ Create frontend auth context
6. ✅ Build district dashboard
7. ✅ Add sync functionality to existing grading flow
8. ✅ Test with multiple districts

### Cost Estimate

| Tier | Districts | Teachers | Monthly Cost |
|------|-----------|----------|--------------|
| Free | 1-2 | 1-10 | $0 |
| Pro | 5-10 | 50-100 | $25 |
| Team | 20+ | 500+ | $599 |
| Enterprise | Unlimited | Unlimited | Custom |
