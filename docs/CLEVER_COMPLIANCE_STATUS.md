# Clever Compliance Status

**Last verified:** May 5, 2026 (post 2026-05-05 SIS compliance hardening sprint, PRs #208–#213)
**Total Clever tests:** 117+ (all passing — 87 baseline + 30+ added by sprint)
**Overall status:** Production-ready for Clever Library certification

---

| Clever Requirement | Status | Evidence |
|---|---|---|
| OAuth SSO (teacher + student) | ✅ | `clever_routes.py` callback, 14 callback tests |
| CSRF state validation | ✅ | State generated + validated on callback |
| Account merging | ✅ | Email match on first Clever login, 5 tests |
| school_admin role | ✅ | In allowed roles list |
| Server-side section filtering | ✅ | Teachers see only own sections, 4 tests |
| Roster sync on login | ✅ | Background thread, `_sync_classes_to_db` |
| Manual roster sync | ✅ | Endpoint with session check + Supabase sync |
| IEP/ELL accommodation detection | ✅ | `extract_student_accommodations`, 5 tests |
| Accommodation wiring to grading | ✅ | `build_prompt_from_student_accommodations`, 15 tests |
| Delivery accommodations (portal) | ✅ | Extended time, large text, read-aloud |
| Data deletion (district disconnect) | ✅ | Local files + full Supabase cascade, 2 tests |
| Audit trail | ✅ | `_clever_audit` → Supabase `audit_log`, 3 tests |
| @require_clever_session | ✅ | Decorator on 5 endpoints, 2 tests |
| @handle_route_errors | ✅ | On all 11 Clever routes |
| District API key management | ✅ | GET/POST with admin checks |
| Student SSO (auth codes) | ✅ | 60s TTL, 5 SSO tests |
| Health check | ✅ | `/api/clever/health` |
| Analytics opt-out | ✅ | `disableAnalytics()`, localStorage flag |
| FERPA doc updated | ✅ | All items marked Done |

---

## Test Coverage

| Test File | Tests | Coverage |
|---|---|---|
| `test_clever.py` | 40 | API helpers, roster persistence, data deletion |
| `test_clever_classes.py` | 17 | Sections → DB sync, edge cases, failures |
| `test_clever_callback.py` | 14 | OAuth flow, account merging |
| `test_clever_student_sso.py` | 5 | Student session creation |
| `test_clever_compliance.py` | 11 | Section filtering, deletion cascade, audit, session decorator |
| **Total** | **87** | |

---

## Key Files

| File | Responsibility |
|---|---|
| `backend/clever.py` | Clever API client, roster sync, data persistence |
| `backend/routes/clever_routes.py` | OAuth callback, sync/delete endpoints, audit logging |
| `backend/auth.py` | Account merging, session resolution |
| `backend/utils/auth_decorators.py` | `require_clever_session` decorator |
| `backend/accommodations.py` | IEP/ELL preset system, delivery accommodations |
| `backend/services/portal_grading.py` | Accommodation wiring to grading pipeline |
| `frontend/src/components/StudentPortal.jsx` | Delivery accommodations UI |
| `frontend/src/services/posthog.js` | Analytics with district opt-out |

---

## Data Handling & FERPA

| Requirement | Status | Implementation |
|---|---|---|
| Data stored only for educational purpose | ✅ | Roster data used for grading + accommodations only |
| Data deletion on district disconnect | ✅ | Full cascade: local files + Supabase (classes, students, enrollments, submissions, sessions) |
| Audit trail for data access | ✅ | `_clever_audit()` logs all sync, delete, accommodation, and key operations. `audit_log("CLEVER_USER_READ")` covers `/me` + `/users/{id}` PII reads (PR #213). `audit_log("ROSTER_SYNC_*")` covers entry/exit on every Clever/ClassLink/OneRoster sync (PR #213). All to Supabase `audit_log`. |
| PII redaction in operational logs | ✅ | `redact_email()` + 8-char SHA256 hash for IDs across 8 OAuth log sites (PR #210). `_clever_audit` audit-log payloads scrubbed. AST-based test pins regression. |
| ClassLink OIDC id_token validation | ✅ | RS256 signature, iss/aud/exp validation against discovered JWKS, identity from id_token claims, alg=none rejection (PR #208). |
| ClassLink CSRF state + nonce hardening | ✅ | Self-initiated flows require strict state + nonce match; LaunchPad-initiated permissive on state, id_token signature is auth proof (PR #209). |
| LTI 1.3 deployment_id allowlist | ✅ | `validate_launch_jwt` enforces deployment_ids list per platform; TOFU migration for legacy registrations with audit-log visibility (PR #212). |
| Teacher sees only their own students | ✅ | Server-side section filtering by teacher Clever ID |
| Student PII not sent to AI | ✅ | Only accommodation type sent (not names, IDs) |
| Analytics opt-out for districts | ✅ | `GRAIDER_DISABLE_ANALYTICS` or `disableAnalytics()` |
| Privacy Policy published | ✅ | graider.live |
| DPA available | ✅ | Available for district agreements |

## Data Retention

- **Roster data**: Refreshed on every teacher login. Deleted on district disconnect.
- **Student submissions**: Retained until teacher deletes or district disconnects.
- **Grading results**: Retained in teacher's results storage. Deleted with FERPA data deletion.
- **Audit logs**: Retained indefinitely for compliance review.

## COPPA Compliance

- No student accounts created without district/school authorization via Clever
- No direct collection of student data — all data comes through Clever API
- No advertising or third-party data sharing
- Analytics (PostHog) can be disabled per district

---

## Remaining Items (Post-Beta)

| Item | Priority | Notes |
|---|---|---|
| ~~Periodic roster sync (24h)~~ | ✅ shipped | Cron webhook at `/api/sync/periodic-roster` (`backend/routes/sync_routes.py:269` + `.github/workflows/roster-sync.yml`). PERIODIC_SYNC_SECRET-gated. |
| Clever Events API | Low | Not available in Library tier |
| Multi-district token storage | Low | Single district for beta |
| Encrypt local roster files | Low | Mitigated by Railway ephemeral filesystem |
| Multi-worker auth codes (Redis) | Low | Single-process Railway deploy |
| Clever Library/Complete tier-gated IEP/ELL fetch | Deferred | Currently fetches unconditionally; gate on district config when wired |
| OneRoster `modifiedSince` delta sync | Deferred | Performance, not compliance. Filed as future product hardening. |
| OneRoster demographics consent gate | Deferred | Better handled with config-backed district consent toggle than rushed. |
