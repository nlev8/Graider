# Hardening Phase 4: Architecture + Operational Safety

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Structural improvements — deduplicate grading logic, extract services, add operational safety mechanisms. Brings Architecture from 6→8, Operational Safety from 5→8, Code Quality from 5→7.

**Note:** This phase involves larger refactors. Each task should be done in a worktree with careful testing.

---

## Task 1: Extract shared grading service

**Files:**
- Create: `backend/services/grading_service.py`
- Modify: `backend/routes/student_portal_routes.py`

### Step 1.1: Deduplicate grading logic

- [ ] `grade_student_submission()` and `grade_instant_only()` share ~200 lines of MC/TF/matching logic. Extract into a single `grade_deterministic_questions(assessment, answers, skip_written=False)` function in `backend/services/grading_service.py`.

- [ ] `grade_student_submission` calls the shared function with `skip_written=False` (runs AI for written)
- [ ] `grade_instant_only` calls with `skip_written=True` (marks written as pending_review)

### Step 1.2: Extract teacher config loading

- [ ] The pattern of loading `teacher_config` (global_ai_notes, grade_level, subject, rubric, grading_style) appears 3 times. Extract into `load_teacher_config(teacher_id)` in the grading service.

---

## Task 2: Graceful shutdown for grading threads

**Files:**
- Modify: `backend/services/portal_grading.py`
- Modify: `backend/app.py`

### Step 2.1: Track active grading threads

- [ ] Maintain a set of active thread references. On SIGTERM (Railway shutdown), wait up to 30 seconds for threads to complete before exiting.

```python
import signal
import threading

_active_threads = set()
_shutdown_event = threading.Event()

def _signal_handler(signum, frame):
    _shutdown_event.set()
    for t in _active_threads:
        t.join(timeout=30)
    sys.exit(0)

signal.signal(signal.SIGTERM, _signal_handler)
```

### Step 2.2: Check shutdown event in grading thread

- [ ] At the start of `run_portal_grading_thread`, check `_shutdown_event.is_set()`. If true, skip grading and mark submission as `grading_deferred`.

---

## Task 3: Redis-backed rate limiter (production)

**Files:**
- Modify: `backend/extensions.py`

### Step 3.1: Use Redis when available

- [ ] Check for `REDIS_URL` env var. If set, use it for Flask-Limiter storage. If not, fall back to memory (dev mode).

```python
redis_url = os.getenv('REDIS_URL')
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri=redis_url or "memory://",
)
```

---

## Task 4: Clever multi-district support

**Files:**
- Modify: `backend/routes/clever_routes.py`

### Step 4.1: Scope student lookup by teacher

- [ ] In `_create_clever_student_session`, add `.eq('teacher_id', teacher_id)` to the student lookup query to prevent cross-teacher matches.

### Step 4.2: Per-district token storage

- [ ] Store district tokens in Supabase instead of env var. The existing `/api/clever/district-keys` endpoint already handles this — verify it's used during roster sync instead of `os.getenv("CLEVER_DISTRICT_TOKEN")`.

---

## Task 5: Remove DEBUG=True from config.py

**Files:**
- Modify: `backend/config.py`

- [ ] Set `DEBUG = False` or read from env: `DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'`

---

## Verification

- [ ] Run full test suite
- [ ] Deploy to Railway staging (if available) and verify no regressions
- [ ] Verify graceful shutdown works (kill -SIGTERM)

**Expected score improvement:**
- Architecture: 6 → 8/10
- Operational Safety: 5 → 8/10
- Code Quality: 5 → 7/10
- Clever Compliance: 8 → 9/10
