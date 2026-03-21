# Graider Deployment Guide

## Architecture

```
Student Browser → app.graider.live (Railway) → Flask API → Supabase (DB)
                                              → OpenAI/Anthropic (Grading)
Teacher Browser → app.graider.live (Railway) → Flask API → Supabase (DB)
                                              → Clever API (SSO + Roster)

Landing Page → graider.live (Vercel)
```

## Prerequisites

- **Railway account** with a project
- **Supabase project** with tables created
- **Clever developer account** with app registered
- **OpenAI API key** (for grading)
- **GitHub repository** connected to Railway

## 1. Supabase Setup

### Create Tables

Run these SQL files in the Supabase SQL editor in order:

1. `backend/database/supabase_schema.sql` — published_assessments, submissions
2. `supabase_student_portal_schema.sql` — classes, students, published_content, student_submissions
3. `backend/database/migration_2026_03_20_fk_constraints.sql` — FK cascade constraints

### Additional Migrations

```sql
-- Teacher ID on published_assessments (required for multi-teacher)
ALTER TABLE published_assessments ADD COLUMN IF NOT EXISTS teacher_id TEXT;
CREATE INDEX IF NOT EXISTS idx_assessments_teacher ON published_assessments(teacher_id);

-- Unique constraints (prevent duplicate submissions)
CREATE UNIQUE INDEX IF NOT EXISTS idx_submissions_unique_student
ON submissions(join_code, student_name) WHERE student_name IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_student_submissions_unique
ON student_submissions(student_id, content_id) WHERE attempt_number = 1;

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  timestamp TEXT NOT NULL,
  teacher_id TEXT,
  action TEXT NOT NULL,
  details TEXT,
  user_type TEXT DEFAULT 'teacher',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_teacher ON audit_log(teacher_id);

-- Teacher data storage (for settings, rubrics, resources)
CREATE TABLE IF NOT EXISTS teacher_data (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  teacher_id TEXT NOT NULL,
  data_key TEXT NOT NULL,
  data JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(teacher_id, data_key)
);
```

## 2. Railway Setup

### Environment Variables

Set these in Railway dashboard → Variables:

```
# Required
FLASK_SECRET_KEY=<random 64-char string>
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_JWT_SECRET=<from Supabase Settings → API>

# Clever Integration
CLEVER_CLIENT_ID=<from Clever developer dashboard>
CLEVER_CLIENT_SECRET=<from Clever developer dashboard>
CLEVER_REDIRECT_URI=https://app.graider.live/api/clever/callback
CLEVER_API_VERSION=v3.0

# AI Grading (at least one required)
OPENAI_API_KEY=sk-...

# Optional
FLASK_ENV=production
REDIS_URL=<if using Redis for rate limiting>
ANTHROPIC_API_KEY=sk-ant-...
```

### Deploy

Railway auto-deploys from `git push origin main`. The `Procfile` or `railway.json` should specify:

```
web: cd backend && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

## 3. Clever Configuration

### Register App

1. Go to [Clever Developer Dashboard](https://apps.clever.com/)
2. Create new application
3. Set redirect URI to `https://app.graider.live/api/clever/callback`
4. Note Client ID and Client Secret
5. Request access to a district (or use sandbox)

### District Setup

1. District admin installs Graider from Clever Library
2. District admin shares sections with Graider
3. Teacher logs in via Clever SSO
4. Roster syncs automatically on first login

## 4. Frontend Build

The frontend is pre-built and included in `backend/static/`. To rebuild:

```bash
cd frontend && npm ci && npm run build
```

Output goes to `backend/static/` which Flask serves.

## 5. Verify Deployment

```bash
# Health check
curl https://app.graider.live/api/clever/health

# Should return:
# {"clever_configured": true, "supabase_connected": true, ...}
```

## 6. Landing Page (Vercel)

```bash
cd landing && npx vercel --prod
```

Separate Vercel project at `graider.live`.

## Rollback

Railway keeps deployment history. To rollback:
1. Go to Railway dashboard → Deployments
2. Click the previous successful deployment
3. Click "Redeploy"

## Monitoring

- **Logs**: Railway dashboard → Logs (structured JSON in production)
- **Audit trail**: Supabase → audit_log table
- **Health**: `GET /api/clever/health`
