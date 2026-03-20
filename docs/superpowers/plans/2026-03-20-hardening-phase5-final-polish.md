# Hardening Phase 5: Final Polish to 10/10

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close remaining gaps to reach 10/10 across all dimensions. Each task addresses residual issues from Phases 1-4.

---

## Task 1: Security 8→10

- [ ] **Redis-backed session storage**: Move Flask sessions from cookie to Redis (prevents session fixation, enables server-side revocation)
- [ ] **CSRF tokens on state-mutating endpoints**: Add Flask-WTF CSRF or custom token validation for non-API form submissions
- [ ] **Content Security Policy refinement**: Tighten CSP to disallow eval(), restrict script-src to specific hashes
- [ ] **Dependency audit**: Run `pip audit` and `npm audit`, fix any vulnerabilities

---

## Task 2: Error Handling 9→10

- [ ] **Frontend error boundaries**: Add React ErrorBoundary component wrapping App, StudentPortal, and StudentDashboard
- [ ] **Retry mechanism for failed grading**: If grading thread fails, queue for retry (max 3 attempts) rather than marking as failed permanently
- [ ] **User-facing error messages**: Ensure every error response includes an actionable message, not just "An internal error occurred"

---

## Task 3: Code Quality 7→10

- [ ] **Split App.jsx**: Extract into logical modules — at minimum separate the state management, publish modal, and main tab rendering into separate files
- [ ] **Split planner_routes.py**: Extract post-processing pipeline, export logic, and generation prompts into separate modules
- [ ] **Eliminate all silent exception swallowing**: Replace all `except Exception: pass` with `except Exception: logger.debug(...)` at minimum
- [ ] **Consistent import patterns**: Replace all `try: from backend.X ... except: from X ...` with a single import strategy

---

## Task 4: Architecture 8→10

- [ ] **Unify publish paths**: Merge `published_assessments` and `published_content` into a single table with `publish_mode` column (join_code vs class). Migrate existing data.
- [ ] **Service layer**: Extract publishing, grading, and accommodation logic from route handlers into `backend/services/`
- [ ] **Decouple grading from app.py**: Move grading thread management into `backend/services/grading_manager.py`

---

## Task 5: Test Coverage 9→10

- [ ] **Integration tests**: End-to-end test: publish → student joins → submits → graded → teacher sees results
- [ ] **Coverage target**: 90%+ line coverage on all backend modules
- [ ] **Frontend tests**: Add Jest tests for critical React components (StudentPortal, MatchingCards)
- [ ] **CI gate**: Add GitHub Actions workflow that runs tests before allowing merge to main

---

## Task 6: Documentation 9→10

- [ ] **Architecture diagram**: Add visual diagram of data flow (Clever → SSO → Dashboard → Portal → Grading → Results)
- [ ] **Deployment guide**: Step-by-step Railway + Supabase + Clever setup for a new district
- [ ] **API documentation**: OpenAPI/Swagger spec for all endpoints
- [ ] **Developer onboarding guide**: "Getting started" for new contributors

---

## Task 7: Observability 8→10

- [ ] **Structured JSON logging**: Replace Python logging with structlog or JSON formatter
- [ ] **Performance metrics**: Track and log API response times, grading duration, Supabase query latency
- [ ] **Alerting**: Set up Railway/Supabase alerting for error rate spikes and grading thread failures
- [ ] **Dashboard**: Simple admin endpoint showing system health (active sessions, pending submissions, grading queue)

---

## Task 8: Data Integrity 8→10

- [ ] **Foreign key constraints**: Add CASCADE constraints between published_assessments→submissions and published_content→student_submissions in Supabase
- [ ] **Transactional writes**: Wrap multi-table operations in Supabase transactions where available
- [ ] **Consistency checker**: Scheduled job that verifies local files match Supabase data
- [ ] **Backup strategy**: Document Supabase backup schedule and recovery procedure

---

## Task 9: Operational Safety 8→10

- [ ] **Database migrations**: Adopt Supabase migrations CLI for schema changes
- [ ] **CI/CD pipeline**: GitHub Actions → test → build → deploy to Railway staging → promote to production
- [ ] **Feature flags**: Simple JSON-based feature flag system in Supabase for gradual rollouts
- [ ] **Rollback procedure**: Document how to revert a Railway deployment

---

## Task 10: Clever Compliance 9→10

- [ ] **Periodic roster sync**: Background task that syncs roster every 24 hours (not just on login)
- [ ] **Multi-district support**: Per-district config storage in Supabase, not env vars
- [ ] **Clever Events API**: Subscribe to roster change events for real-time sync (Clever Secure Sync v2)
- [ ] **Clever certification form**: Complete and submit the Airtable certification form

---

## Expected Final Scores

| Dimension | Before | After Phase 5 |
|---|---|---|
| Security | 8 | 10 |
| Error Handling | 9 | 10 |
| Code Quality | 7 | 10 |
| Architecture | 8 | 10 |
| Test Coverage | 9 | 10 |
| Documentation | 9 | 10 |
| Debugging/Observability | 8 | 10 |
| Data Integrity | 8 | 10 |
| Operational Safety | 8 | 10 |
| Clever Compliance | 9 | 10 |

**Overall: 10/10**
