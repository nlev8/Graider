# Comprehensive Hardening Assessment — March 20, 2026

## Current Scores

| Dimension | Score | Target |
|---|---|---|
| Security | 5/10 | 10/10 |
| Error Handling | 7/10 | 10/10 |
| Code Quality | 5/10 | 10/10 |
| Architecture | 6/10 | 10/10 |
| Test Coverage | 6/10 | 10/10 |
| Documentation | 7/10 | 10/10 |
| Debugging/Observability | 5/10 | 10/10 |
| Data Integrity | 5/10 | 10/10 |
| Operational Safety | 5/10 | 10/10 |
| Clever Compliance | 8/10 | 10/10 |

**Overall: 5.9/10 → Target: 10/10**

## Critical Findings

### Security (5/10)
- Path traversal on 4 download endpoints + assignment load/delete
- PUBLIC_PREFIXES too broad (`/api/student/` bypasses all auth)
- Error details leaked in assignment_player_routes
- Clever links stored on local filesystem (not shared across workers)
- In-memory rate limiter not shared across workers

### Error Handling (7/10)
- `handle_route_errors` decorator defined but never used
- 117 instances of silently swallowed exceptions
- Background grading thread crashes invisible
- No frontend error boundaries

### Code Quality (5/10)
- App.jsx: 16,531 lines
- planner_routes.py: 6,811 lines
- assignment_grader.py: 7,429 lines
- Triplicated require_teacher decorator
- Triplicated teacher config loading
- Duplicated grading logic (grade_student_submission vs grade_instant_only)

### Architecture (6/10)
- Two parallel publish paths (published_assessments vs published_content)
- No service layer (business logic in route handlers)
- Grading state coupled to app.py
- Frontend monolith

### Test Coverage (6/10)
- Zero tests for: student_account_routes, student_portal_routes (route level), storage.py, settings_routes, analytics_routes
- 5 failing tests in test_document_routes
- No integration tests
- No path traversal tests

### Documentation (7/10)
- Missing newer routes in API reference
- Missing Supabase tables (teacher_data, student_history, etc.)
- Two publish paths not explained
- Inline comments sparse in large functions

### Debugging/Observability (5/10)
- No structured logging (JSON)
- No request/correlation IDs
- Audit log file-based only (lost on redeploy)
- No metrics or performance monitoring
- Background thread failures invisible

### Data Integrity (5/10)
- Race condition on join-code submissions (no unique constraint)
- Race condition on student session creation
- Dual-write inconsistency risk in storage.py
- datetime.utcnow() deprecated usage
- No foreign key enforcement documented

### Operational Safety (5/10)
- No database migration tool
- No feature flags
- No CI gate before deploy
- In-memory rate limiter
- No graceful shutdown for grading threads
- DEBUG = True in config.py

### Clever Compliance (8/10)
- Single district token (no multi-district)
- Student Clever lookup unscoped by teacher_id
- No periodic roster sync (only on login)
