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

---

# 2026-05-16 Re-Score — 3-Model Reconciled (HEAD `63384d3`)

**The March-20 scores above are the frozen baseline — do not edit them.** This section is the current state, re-measured after PRs #374–#392.

**Method:** three independent models each verified claims against the live code with their own shell commands (Codex via codex-rescue, Claude general-purpose subagent, Gemini CLI 0.41.2). Reconciliation is a **conservative floor, not an average**: on any split the **lower** score wins unless a model presents strong disconfirming file:line evidence; caveats ≥2 models couldn't verify cap the dimension; every divergence is recorded below.

| Dimension | 2026-03-20 | Codex | Claude | Gemini | **Reconciled** |
|---|---:|---:|---:|---:|---:|
| Security | 5 | 8.6 | 9 | 8 | **8** |
| Error Handling | 7 | 8.3 | 8 | 8 | **8** |
| Code Quality | 5 | 7.2 | 7 | 7 | **7** |
| Architecture | 6 | 7.6 | 8 | 7 | **7** |
| Test Coverage | 6 | 8.4 | 8 | 8 | **8** |
| Documentation | 7 | 7.5 | 8 | 8 | **7** |
| Debugging/Observability | 5 | 8.0 | 8 | 8 | **8** |
| Data Integrity | 5 | 8.0 | 8 | 7 | **7** |
| Operational Safety | 5 | 8.5 | 8 | 8 | **8** |
| Clever Compliance | 8 | 8.7 | 9 | 9 | **9** |

**Reconciled overall: 7.7/10** (conservative floor) — baseline was 5.9. Raw 3-model means: Codex 8.1, Claude 8.1, Gemini 7.8 (≈8.0); the reconciled 7.7 is intentionally below them because splits resolve down and unverifiable items don't get credited. **Measured backend coverage: 63.37%** (Claude, from CI run log — the one hard number, not a judgment).

### Per-dimension reconciled rationale

- **Security 8** — Gemini's 8 wins over Claude's 9: `hmac.compare_digest` across 11 OAuth/sync sites (#374), `secure_filename`+`require_teacher` on downloads, `storage.py:48-60` tenant-id sanitization. *Capped at 8 (not 9):* `PUBLIC_PREFIXES` (`auth.py:68-77`) still exposes broad route subtrees (all 3 models); Codex found planner-export still returns truncated exception strings (`planner_routes.py:5674-5676/5924-5926/6048-6050`) — concrete disconfirm of a 9.
- **Error Handling 8** — unanimous. `handle_route_errors` now RFC-7807, applied 290–315×; FE `ErrorBoundary` wired (`main.jsx`); #382 transient propagation. *Capped:* broad-swallow not eliminated — model counts of `except`/`except: pass`: Gemini ~849, Codex 598, Claude 88 (49 broad). Not all log.
- **Code Quality 7** — unanimous. App.jsx 16,531→7,144 (verified) + service layer added, BUT LOC was *relocated, not eliminated*: `PlannerTab.jsx` 7,405, `SettingsTab.jsx` 6,534, `assignment_grader.py` 7,444 ≈ baseline 7,429.
- **Architecture 7** — Gemini's 7 wins over Claude's 8: grading state extracted out of app.py with per-teacher isolation (`grading/state.py`). *Capped:* the two parallel publish paths are still **not consolidated** (~85 cross-route refs; all 3 confirm) + mixed Celery/thread grading paths (Codex). This is the core unaddressed baseline Architecture item.
- **Test Coverage 8** — unanimous. Previously-zero modules now have suites; 250 backend test files; the "5 failing doc-route tests" baseline item is resolved (28 passed). *Capped:* 63% leaves ~11.8k stmts uncovered; e2e is a 6-spec smoke set with conditional skips.
- **Documentation 7** — Codex's 7.5 (lowest, hardest evidence) wins over Claude/Gemini 8: ~307 route decorators vs ~98 documented `/api` entries; no dedicated API-docs file. CLAUDE.md is broad but route coverage is ~1/3. Conservative floor → 7.
- **Debugging/Observability 8** — unanimous. JSON structured logging + `request_id` correlation (`auth.py:171-175`), Sentry integrated, `observability/` package. *Capped:* no metrics/OTel; audit log still file-first (`utils/audit.py`).
- **Data Integrity 7** — Gemini's 7 wins over Codex/Claude 8: join-code submit defended in depth (precheck + UUID + `upsert on_conflict` + `23505` catch). *Capped:* the DB `UNIQUE` constraint backing that catch is **unprovable from the repo** (only baseline migration exists) → Claude's "MITIGATED-NOT-PROVEN"; 2 residual `datetime.utcnow()` in `survey_routes.py:366/375`.
- **Operational Safety 8** — consensus ~8 (Codex 8.5 discounted by its own caveat). Alembic + `Migrations Smoke`; flask-limiter with **fail-fast if no `REDIS_URL` in prod**; `DEBUG` env-gated. *Capped:* only 1 real migration (baseline) — no incremental discipline yet; no feature-flag system; `load-weekly` still `continue-on-error`. (Codex couldn't verify branch protection — GitHub API blocked in its sandbox; the **orchestrator independently verified the 9 required checks via `gh api` earlier this session**, so the CI gate IS real — but the migration/flag gaps still cap at 8.)
- **Clever Compliance 9** — Claude 9 / Gemini 9 / Codex 8.7 → **9**. Periodic roster sync DONE (`roster-sync.yml`); roster paths teacher-scoped (`clever_roster_scope.py`). **Exactly two finite gaps to 10**, independently code-verified, scoped in **`docs/superpowers/plans/2026-05-16-clever-compliance-10.md`**: (A) multi-enrollment student-SSO disambiguation (`clever_routes.py:156-205`, first-row-wins, self-documented); (B) per-district token resolution (sync reads single `CLEVER_DISTRICT_TOKEN` env instead of the existing per-district key store). Clever Library certification does **not** test either → not credited as 10.

### Biggest remaining lever (unanimous, all 3 models)

**Code Quality / Architecture concentrated complexity.** App.jsx was genuinely cut 57%, but the mass moved into `PlannerTab.jsx`/`SettingsTab.jsx`/`assignment_grader.py` (all still 6.5–7.5k LOC) and the two publish/grading execution paths persist. The highest cross-dimension lift is decomposing the grading engine + PlannerTab and consolidating the dual publish path — it directly raises Code Quality, Architecture, and Test Coverage at once.

### Conservative caveats (unverifiable from repo — not credited)

1. Join-code dedup DB `UNIQUE` constraint — code defends `23505` but constraint not in any migration in-repo. Race = mitigated, not proven.
2. Two publish paths — documented, **not** consolidated (~85 refs). Baseline Architecture concern stands.
3. Broad `except` — reduced, not eliminated; not all 88/598/849 (model-dependent count) audited.
4. `PUBLIC_PREFIXES` whole-subtree exposure — inner handlers enforce auth but not every handler verified.
5. Single Clever district token — unchanged (Task B of the Clever→10 plan).

*Next concrete plan: `docs/superpowers/plans/2026-05-16-clever-compliance-10.md` (Clever 9→10, two bounded PRs). No other dimension has a comparably small, well-defined path to 10 — the rest need the multi-week complexity-decomposition sprint described under "biggest lever."*
