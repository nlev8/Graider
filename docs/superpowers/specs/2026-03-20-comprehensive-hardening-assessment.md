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

---

# 2026-05-16 Closing Re-Score — Clever Tasks A+B shipped (HEAD `71e66de`)

**3-model DELTA re-score after PR #395 (Task A) + #397 (Task B) merged, to verify whether Clever Compliance reaches a true 10/10.** Same conservative-floor reconciliation. Codex + Claude + Gemini each independently verified in-code.

**Verdict: Clever Compliance stays 9/10 — NOT a verified 10. Overall unchanged at 7.7/10.** The plan's premise ("these two tasks are the *only* verified blockers") was **incomplete** — 3-model verification found three in-code residuals. Tasks A & B did close their *planned scope*; the scope was under-drawn.

| Model | Clever | Overall | Verdict |
|---|---:|---:|---|
| Codex | 9 | 7.7 | residual: duplicate-student-row first-pick |
| Claude | 9 | 7.7 | residual: `sync_routes.py:189` |
| Gemini | 10 | 7.8 | "minor debt" — but documented the same residuals |
| **Reconciled** | **9** | **7.7** | 2/3 = 9; Gemini's 10 self-documents the residuals → conservative floor holds |

All other 9 dimensions: **unanimously unchanged** (only Clever code + docs merged 63384d3→71e66de; no drift). Measured backend coverage **63.42%** (Claude, CI run 25971292023).

### Tasks A & B — closed for their planned scope (verified)

- **Task A** (#395 `b9eff4e`): `clever_routes.py` enumerates `class_students` (no `.limit(1)`), `needs_class_selection` + short-lived token, GET/POST `/api/clever/select-class`, `StudentApp.jsx` picker, 9+2 tests. ✓
- **Task B** (#397 `71e66de`): `api_keys.resolve_clever_district_token`; both `clever_routes.py` sync sites use it not `os.getenv`; 6 tests. ✓
- Periodic roster sync: `.github/workflows/roster-sync.yml` present. ✓

### The three verified residuals blocking a true Clever 10/10 (→ Task C)

1. **`backend/routes/clever_routes.py:248`** (Codex; orchestrator-verified). `student_row = res.data[0]` — the `students` lookup is still **first-row-wins when the same Clever ID exists under multiple teachers' rosters**. Task A disambiguated *enrollments for one student row*, not *duplicate student rows*. The original baseline defect ("same Clever student under multiple teachers, first DB row wins") is only **partially** closed. The comment at `:244-247` is now stale (describes the fix as not-done).
2. **`backend/routes/sync_routes.py:189`** (Claude + Gemini, independent). `config.get('district_token') or os.environ.get('CLEVER_DISTRICT_TOKEN')` — the daily periodic-cron path is a **third token-resolution site that bypasses `resolve_clever_district_token`** (per-teacher config + env only; never the per-district store). Multi-district daily sync still can't pick up a district-scoped token.
3. **`backend/api_keys.py::save_district_keys`** (Gemini; orchestrator-verified). Filters to `('openai','anthropic','gemini')` — **`clever_district_token` has no supported write path**, so Task B's per-district resolver branch is unreachable end-to-end (single-district env path works; true multi-district does not).

**Net:** Tasks A+B are real improvements (the common single-row/single-district cases are fixed and tested), but a *verified* Clever 10/10 requires Task C closing all three. The conservative scorecard does not credit a 10 on partial closure.

*Plan reopened: `docs/superpowers/plans/2026-05-16-clever-compliance-10.md` now carries **Task C** with these three file:line items.*

---

# 2026-05-16 Task C Verification — Clever Compliance **9 → 10/10** (verified, HEAD `934e535`)

**Task C (PR #399 `934e535`) closed all three residuals.** Verification re-score:

| Model | Clever verdict | Basis |
|---|---|---|
| Codex | **10**, no residual | airtight file:line proof for C1/C2/C3 + green test counts |
| Gemini | **10**, no residual | independent file:line proof, tests green |
| Claude | *no verdict* | agent stalled at 600s (genuine failure-to-run, not failed-low) |

**Reconciled: Clever Compliance = 10/10. Overall 7.7 → 7.8.** Basis (honest): **two independent models concur** with concrete in-code evidence, **plus** orchestrator first-hand verification (implemented C1/C2/C3 via TDD; 975 clever/sis/student_session/api_key/sync regression green; ruff clean; SIS pins retracked, captures intact). No split among *completed* assessments — Claude failed-to-run, not failed-low. Per the conservative discipline this clears the bar (≥2 independent confirmations + first-hand regression; a 10 is never credited on one optimistic model — that rule is exactly what caught the false-10 in the prior closing re-score).

| Dim | baseline | 2026-05-16 reconciled | **now (934e535)** |
|---|--:|--:|--:|
| Security | 5 | 8 | 8 |
| Error Handling | 7 | 8 | 8 |
| Code Quality | 5 | 7 | 7 |
| Architecture | 6 | 7 | 7 |
| Test Coverage | 6 | 8 | 8 |
| Documentation | 7 | 7 | 7 |
| Debugging/Observability | 5 | 8 | 8 |
| Data Integrity | 5 | 7 | 7 |
| Operational Safety | 5 | 8 | 8 |
| **Clever Compliance** | 8 | 9 | **10** |
| **Overall** | **5.9** | **7.7** | **7.8** |

**C1/C2/C3 — verified closed (Codex + Gemini, file:line):**
- **C1** `clever_routes.py:260` enumerates ALL `students` rows (+ email fallback), not `res.data[0]`; candidates carry `_student_row`; `_public_candidates` (`:96`) strips PII from the browser-facing list (incl. the GET path); finalize mints against the chosen class's owning `_student_row` (legacy fallback). Stale "first DB row wins / requires a UI flow change" comment removed. Tests green.
- **C2** `sync_routes.py:~192` resolves via `resolve_clever_district_token(config.get('district_id'))`; no direct `os.environ`/`os.getenv` `CLEVER_DISTRICT_TOKEN` read remains; resolver owns env fallback (single-district byte-identical).
- **C3** `api_keys.save_district_keys` + `/api/clever/district-keys` POST persist `clever_district_token` → resolver's per-district read has a write path; multi-district reachable end-to-end. save→read round-trips.
- `test_sis_alerting.py` green — 3 clever_routes pins retracked for the C1 line-shift; `capture_exception` calls intact (no observability regression).

**Clever Compliance is now a genuinely verified 10/10.** Other 9 dimensions: unanimously unchanged (only Clever code merged 71e66de→934e535). The biggest remaining lever is unchanged: Code Quality / Architecture concentrated complexity (multi-week decomposition) — no comparably small path to 10 elsewhere. **The Clever→10 plan is fully CLOSED.**

---

# 2026-05-16 Data Integrity Tier 1 — shipped (PR #402, `6a231db`)

Tier 1 of the dimension roadmap, executed from the 3-model reconciled, user-approved forward-only plan (`docs/superpowers/plans/2026-05-16-data-integrity.md`, now CLOSED). TDD, 6 tasks, all merged.

**What shipped:**
- Submission dedup is now a provable, concurrency-safe, forward-only DB guarantee. Nullable `dedup_key` on `submissions` + `student_submissions` with a partial `UNIQUE … WHERE dedup_key IS NOT NULL` index (Alembic `0002`, reversible). Legacy rows stay NULL, so the migration cannot fail on history and rewrites nothing.
- Join-code submit sets the key only when `allow_multiple_attempts` is false (matches the existing case-insensitive pre-check). Class submit keys it by `student_id|content_id|attempt_number` (multi-attempt stays intentional). The racy TOCTOU pre-checks and the previously-dead `23505` catches now have a real constraint behind them.
- Migrations Smoke now applies the base schema before `alembic upgrade head` and asserts the two dedup indexes exist. This both closes the provability gap and fixes that the gate was previously hollow (it only seeded auth stubs, so forward migrations had no tables).
- The last 2 naive `datetime.utcnow()` calls (`survey_routes.py`) are tz-aware. Repo-wide non-test `utcnow()` count is now 0.

**Reconciled effect:** Data Integrity moves from the reconciled **7 → ~9** (the dedup race is closed forward-only and the constraint is reproducible + CI-asserted; 2 residual timestamps fixed). No multi-model re-score was run, by design: unlike Clever, this fix is mechanically CI-proven, not a judgement call. Overall scorecard nudges from **7.8 → ~7.9**. The biggest remaining lever is unchanged (Code Quality / Architecture decomposition). Scope held: full Alembic rebaseline and historical dup cleanup were deliberately out.

**One honest note:** CI surfaced that migration `0002` needed the project's `# destructive:` acknowledgment (the `DROP INDEX`/`DROP COLUMN` in `downgrade()`, flagged by `test_alembic_destructive_ops.py`). Fixed in the same branch with an accurate justification (destructive ops are downgrade-only; no existing-row data loss since `dedup_key` was forward-only). Same class of project-meta-convention catch as the SIS-pin retracks earlier this sprint.

---

# 2026-05-17 Tier 2 Slice 1: planner_routes.py service extraction shipped (PR #406 / #407 / #408 / #409)

The largest backend route file in the codebase was decomposed across four merged PRs. `backend/routes/planner_routes.py` went from 6,050 to 4,598 LOC (1,452 lines moved out). The logic moved into three single-responsibility, Flask-free service modules: `backend/services/planner_standards.py` (243 LOC), `backend/services/planner_export.py` (1,095 LOC), and `backend/services/planner_prompts.py` (172 LOC). Each module ships with unit tests that import and run with no Flask app or test client present, proving the coupling was severed rather than relocated.

**PR sequence:** PR1 (#406, `planner_standards`), PR2 (#407, `planner_export`), PR3 (#409, `planner_prompts`), plus #408 (export characterization broadening + pre-existing bug fix, described below).

**Coupling-reduction rule (plan §3) held.** Two functions were correctly left behind in `planner_routes.py` rather than force-relocated:

- `_get_openai_context` (planner_routes.py:123) reads Flask `g` (`getattr(g, 'user_id', 'local-dev')` at line 131). Parameterizing it cleanly would have required updating every call site in the route handlers; a verbatim move would have carried the Flask dependency into the new service, defeating the purpose.
- `_save_grading_config_for_export` (planner_routes.py:1820) contains an inner `from flask import g` at line 1941 for a best-effort Supabase save path. Same constraint: the Flask dependency is load-bearing inside the function body rather than only in the signature.

Both are recorded in the PR descriptions per the plan's §3 convention.

**PR #408 and the unit_circle bug.** Broadening the export characterization test net to cover all visual question types surfaced a genuine pre-existing production bug: `unit_circle` questions passed a CSS `rgba(...)` string as a matplotlib color argument, which raised a `ValueError`. The function-wide `except` block swallowed it silently, so no visual was rendered in either the student copy or the answer key for HS trig and precalc assignments. This had been invisible because no test covered that branch. The fix was implemented under full TDD (RED confirmed, then GREEN), and the 28-branch characterization net now pins every visual `q_type` so no branch can silently regress again. This directly satisfies the "works for all subjects and grades / nothing coded in error" requirement from the slice spec.

**Reconciled dimension effect.** Code Quality and Architecture each receive a modest nudge upward. The 3-model re-score from 2026-05-16 named Code Quality / Architecture concentrated complexity as the unanimous biggest remaining lever, with `planner_routes.py` cited as a primary example. This is the first delivery against that lever: the largest route file now has a tested, Flask-free service layer beneath it. No multi-model re-score was run, by design; the change is mechanically test-guarded (verbatim moves with characterization and unit tests proving zero behavior change), consistent with how the Data Integrity Tier 1 closeout was handled. The overall stays at approximately 7.9 with Code Quality and Architecture trending up.

**One honest note:** The original PR3 test called `_build_assignment_prompt` with `assignment_type="assignment"`, which returns `None` by documented design (that type is not implemented). The test passed a no-op smoke assertion without actually exercising real behavior. Caught during review, corrected test-only to `assignment_type="essay"` with assertions pinning the real config interpolation. Production code was byte-identical throughout. Same class of self-correction as the migration `# destructive:` and SIS-pin catches earlier in this sprint.

---

# 2026-05-17 Tier 2 Slice 2: assignment_grader.py parsing/extraction service extraction shipped (PR #414 / #415 / #416 / closeout)

The parsing and extraction cluster of `assignment_grader.py` (the codebase's single largest backend file) was decomposed across three merged PRs. `assignment_grader.py` went from 7,444 LOC at slice start to 5,345 LOC now, a reduction of 2,099 lines. The extracted logic lives in a new single-responsibility, network-free, I/O-free module: `backend/services/response_extraction.py` (2,123 LOC), covering 8 leaf helpers, 4 large functions, and the `STUDENT_WORK_MARKERS` constant.

**PR sequence:** spec and plan (#414), PR1 (#415, 8 leaf helpers with per-leaf unit and characterization tests), PR2 (#416, 4 large functions plus `STUDENT_WORK_MARKERS` under an exhaustive characterization net).

**Coupling-reduction rule (spec §3) held.** Two functions were correctly left in `assignment_grader.py` rather than force-moved:

- `extract_from_tables` (currently around line 1187) calls `read_docx_file_structured`, a file-reading I/O function that is out of scope and stays in `assignment_grader.py`. Moving `extract_from_tables` would require importing a staying I/O function back into the service module, creating an import cycle.
- `extract_from_graider_text` (currently around line 1336) calls `extract_from_tables`, so it is transitively bound and also stays.

Both are recorded in the PR descriptions and in the plan per the §3 convention.

**Zero-behavior-change proof.** The exhaustive characterization net covers 43 cases across the cross-product of extraction mode (structured, legacy), document shape (docx-table-derived text, graider-marked text, plain numbered, vocab-term, FITB, summary/written), and subject/grade spread (math gr5, ELA gr8, science gr10, social studies gr12). The net was pinned against pre-move code and then the import was repointed to `backend.services.response_extraction`. Every assertion passed byte-identical. The 818-test broader suite (grading, extraction, pipeline, factors, portal, assignment) also runs 0 failed. That combination is the mechanically-verifiable zero-behavior-change proof, analogous to Slice 1 and Data Integrity Tier 1.

**The net also surfaced a pre-existing bug.** `extract_student_responses_legacy` raises `NameError: name 'response_sections' is not defined` on every call. It is dead code with zero production callers (only the shim re-export references it; the docstring explicitly says "kept for reference but not used"). It was pinned as-is in the characterization net (`pytest.raises(NameError)`) and moved verbatim, consistent with the discipline applied to the Slice 1 `unit_circle` finding: do not fix bugs inside a verbatim-move PR. It is tracked for a dedicated follow-up PR where the correct resolution (delete vs restore the missing parameter) can be decided with full review.

**Reconciled dimension effect.** Code Quality and Architecture each receive a modest nudge upward. This is the second delivery against the unanimous biggest remaining lever (concentrated complexity in the large backend files). `assignment_grader.py` was the single largest backend file; the extraction cluster is now a tested, import-cycle-free service module beneath it. No multi-model re-score was run, by design: the change is mechanically test-guarded (verbatim moves, the pre-move-pinned characterization net that stayed byte-identical post-move, and the 9 CI checks), consistent with how Slice 1 and Data Integrity Tier 1 were handled. The overall stays at approximately 7.9 with Code Quality and Architecture trending up.

**One honest note:** CI surfaced that the shim's implicit re-export tripped mypy strict's `no_implicit_reexport` rule for `backend/grading/pipeline.py`, which is in the strict-scope module list. Fixed in the same PR by converting the shim to the redundant-alias explicit re-export form (e.g., `extract_student_work as extract_student_work`), which satisfies mypy with zero behavior change. Same class of project-meta-convention catch as the migration `# destructive:` acknowledgment and the SIS-pin retracks earlier in this effort. The tracked dead-code follow-up (`extract_student_responses_legacy`) is intentionally out of this slice; it will be resolved via a separate Codex plus Gemini plus Claude reconciled decision covering delete-vs-restore, so the fix is both deliberate and reviewable.

---

# 2026-05-18 3-Model Reconciled Re-Score (HEAD `082b49c`)

First full 3-model re-score since 2026-05-16. Everything between is the cumulative effect of Data Integrity Tier 1 (#402), the export-dir configurability fix and its dead-code follow-up (#418, #419, #420), the matplotlib boxplot forward-compat class elimination (#411, #413), the `unit_circle` real-bug fix (#408), and Tier 2 Slices 1 and 2 (#406 through #417). Those were each shipped with a "no multi-model re-score, mechanically test-guarded" note; this is the deferred reconciliation that credits or withholds the accumulated effect. Codex, Gemini, and Claude each re-scored independently against the 2026-05-16 reconciled baseline, then conservative-floor reconciliation (splits resolve down, unverifiable not credited, the higher value only when concretely and unanimously grounded).

| Dimension | baseline (2026-05-16) | Codex | Gemini | Claude | reconciled |
|---|--:|--:|--:|--:|--:|
| Security | 8 | 8 | 8 | 8 | **8** |
| Error Handling | 8 | 8 | 8 | 8 | **8** |
| Code Quality | 7 | 8 | 8 | 8 | **8** |
| Architecture | 7 | 8 | 8 | 7 | **7** |
| Test Coverage | 8 | 8 | 8 | 8 | **8** |
| Documentation | 7 | 7 | 7 | 7 | **7** |
| Debugging/Observability | 8 | 8 | 8 | 8 | **8** |
| Data Integrity | 7 | 9 | 9 | 9 | **9** |
| Operational Safety | 8 | 9 | 9 | 9 | **9** |
| Clever Compliance | 10 | 10 | 10 | 10 | **10** |
| **Overall** | **7.8** | **8.3** | **8.2** | **8.0** | **8.0** |

**Reconciled overall: 8.0** (raw 3-model means: Codex 8.3, Gemini 8.2, Claude 8.0). The reconciled figure is intentionally the conservative floor, consistent with how prior splits were handled and the discipline that caught the earlier false-10. Net movement from baseline: 7.8 to 8.0.

### Per-dimension reconciled rationale

- **Code Quality 7 to 8 (unanimous).** Verified in-repo: `planner_routes.py` 6,050 to 4,611, `assignment_grader.py` 7,444 to 5,344, four new single-responsibility Flask-free service modules (`planner_standards` 243, `planner_export` 1,095, `planner_prompts` 172, `response_extraction` 1,830) under characterization nets. Held below 9: `assignment_grader.py` (5,344) and `planner_routes.py` (4,611) are still large and `app.py` still carries route logic.
- **Architecture 7 (held; 2-1 split resolved down).** Codex and Gemini scored 8 for the genuine service-layer extraction with no import cycles; Claude held 7 on concrete grounds and the floor rule resolves the split down: the dual publish path (`published_assessments`/`submissions` vs `published_content`/`student_submissions`) is still unconsolidated (dispatched by a `supabase_table` parameter, not a unified abstraction), `app.py` is still 1,935 lines with roughly 40 route functions, and there is no dependency injection. Real progress, not yet a clean architectural boundary.
- **Data Integrity 7 to 9 (unanimous, now concretely credited).** Migration `0002_submission_dedup_forward_only.py` adds partial UNIQUE indexes on both `submissions` and `student_submissions`, CI asserts both indexes after `alembic upgrade head`, `dedup_key` is set on both publish paths, and no `utcnow()` remains in production. The 2026-05-16 note's qualitative "approximately 9" is now a verified 9. Not 10: forward-only by design (pre-migration historical duplicates remain unconstrained); no orphan-cascade tests.
- **Operational Safety 8 to 9 (unanimous).** The docx-spam production root cause is fixed (the `backend/paths.py` call-time resolver replaced 19 hardcoded sites; test isolation converged onto one env-var fixture), and the matplotlib 3.11 `ax.boxplot(labels=)` removal class is eliminated codebase-wide. Not 10: Railway auto-deploy on merge is still the entire rollback story (no staged rollout, no post-deploy smoke gate beyond the pre-merge E2E check).
- **Test Coverage 8 (held).** CI floor is 60%; the claimed 65.00% from a CI run is not stored in-repo and a local `.coverage` read showed a lower total, so no upward credit beyond baseline. The new exhaustive characterization nets add real branch coverage on the extracted code but do not move the absolute number into 9 territory.
- **Security, Error Handling, Documentation, Debugging/Observability, Clever Compliance: unchanged.** No verified post-baseline uplift in any of these; Clever has no changes and no regression.

### Biggest remaining lever and the next concrete step

The unanimous biggest-lever category is unchanged: Architecture and Code Quality concentrated complexity. The three models split on the specific target, and all three are valid:

1. **`app.py` route god-module (Claude).** 1,935 lines, roughly 40 route functions still embedded (grading-results CRUD), which is the specific concrete reason Architecture stayed at 7. Extracting them verbatim into a Blueprint is the exact proven Slice 1 and 2 pattern (pure move under a characterization net), lowest risk, highest confidence, and directly removes the holdout objection.
2. **`frontend/src/tabs/PlannerTab.jsx` (Codex).** 7,405 lines, now the single largest source file in the repository. Highest raw concentrated complexity, but frontend extraction needs a Vitest characterization harness and is the higher-care item (the coupling-reduction rule exists precisely because a prior `App.jsx` extraction relocated lines without cutting coupling).
3. **Dual publish-path consolidation (Gemini).** The biggest architectural lever and the prerequisite for cross-path Data Integrity Tier 2, but the highest blast radius (two tables, both student portals, SSE, grading dual-dispatch). It was deliberately scoped out of Slices 1 and 2 and needs its own brainstorm, not a mechanical slice.

**Next concrete step (Tier 2 Slice 3): extract the grading-results route cluster from `app.py` into a Blueprint** under a characterization net, mirroring Slices 1 and 2. It is the lowest-risk continuous move, directly addresses the Architecture-7 holdout (the `app.py` god-module), and shrinks `app.py` toward an app-factory-plus-error-handlers core. PlannerTab.jsx and the dual publish path are the explicitly sequenced subsequent levers, each requiring its own dedicated design.

**One more honest note:** the prior Slice 1 and 2 closeout notes asserted "overall stays at approximately 7.9." This reconciled re-score lands at 8.0, so those qualitative nudges were slightly conservative rather than wrong. The `App.jsx` figure in the original Critical Findings section (16,531) is stale: it is 7,144 now, halved by an earlier frontend extraction sprint that predates this work, not by these PRs. The Critical Findings section is left as the original-baseline record; this dated section is the current state.

---

# 2026-05-19 Tier 2 Slice 3: app.py route god-module extraction shipped (PR1 #424 / PR2 #425 / PR3)

The remaining domain API route god-module in `backend/app.py` was decomposed across three merged verbatim-extraction PRs, the exact proven Slice 1 and 2 shape (pure `@app.route` to `@bp.route` relocation under an exhaustive pre-move-pinned characterization net). `backend/app.py` went from 1,935 LOC at slice start to 585 LOC, a reduction of 1,350 lines. Sixteen routes moved into three single-responsibility Flask Blueprints registered through the existing `backend/routes/__init__.py` aggregator, with no `url_prefix` and byte-identical paths and decorator stacks.

**PR sequence and contents:**

- **PR1 (#424): `backend/routes/grading_results_routes.py`.** The grading-results CRUD cluster: 4 routes (`/api/grade-individual`, `/api/delete-result`, `/api/update-approval`, `/api/update-approvals-bulk`) plus 2 cluster-internal CSV-sync helpers co-moved verbatim (their sole production callers are the moved routes).
- **PR2 (#425): `backend/routes/ferpa_routes.py`.** The FERPA data-operations cluster: 6 routes (`/api/ferpa/delete-all-data`, `/api/ferpa/audit-log`, `/api/ferpa/data-summary`, `/api/ferpa/export-data`, `/api/ferpa/export-student`, `/api/ferpa/import-student`) plus the cluster-internal `get_audit_logs` reader helper co-moved verbatim, with `AUDIT_LOG_FILE` repointed to the canonical `backend.utils.audit` import (byte-equal to the removed app.py copy) and the now-dead app.py `AUDIT_LOG_FILE` / `RESULTS_FILE` / `SETTINGS_FILE` constants removed.
- **PR3 (this PR): `backend/routes/roster_routes.py`.** The student-history/roster cluster: 6 routes (`/api/student-history/<student_id>`, `/api/student-baseline/<student_id>`, `/api/retranslate-feedback`, `/api/extract-student-from-image`, `/api/add-student-to-roster`, `/api/list-periods`), the two `<student_id>` routes preserving both the path string and the `def f(student_id)` signature exactly. The now-dead `import csv`, the orphaned `from backend.utils.audit import audit_log` (with its now-empty banner), and the entire dead student-history import try/except block (all six names unused once the cluster left) were removed from app.py.

After Slice 3 the only `@app.route` decorators left in `backend/app.py` are the SPA/static factory shell: `/api/user-manual`, `/healthz`, `/`, `/join*`, `/student*`, `/district*`, and the `/<path:path>` SPA catch-all. Zero domain API route logic remains in the app module; it is now an app-factory-plus-error-handlers core, exactly the slice goal.

**Spec refinement (recorded).** The slice design named only `AUDIT_LOG_FILE` for the canonical-import-plus-dead-constant-removal treatment. During PR2 implementation, re-derivation with the authoritative grep gate found that `RESULTS_FILE` and `SETTINGS_FILE` were FERPA-cluster-only app.py-local constants with no canonical home; they received the identical mechanical treatment (co-moved byte-identically into `ferpa_routes`, the now-dead app.py copies removed once the grep gate confirmed zero remaining uses). The coarser pre-scan in the spec did not enumerate them; the plan anticipated implementation-time re-derivation with the grep gate as authoritative, so this is a recorded refinement, not a scope change.

**PR3 honest note: pre-existing route shadowing, faithfully preserved.** Two of the six roster URLs were already shadowed in production before this PR and remain so after: `backend/routes/grading_routes.py` registers `GET /api/student-history/<student_id>` (endpoint `grading.get_student_history`) and `backend/routes/settings_routes.py` registers `GET /api/list-periods` (endpoint `settings.list_periods`). app.py calls `register_routes()` before its cluster `@app.route` decorators, so Werkzeug's first-added-rule-wins matching already made the grading/settings views the live production handlers and the app.py copies dead/shadowed on the real app. `roster_bp` is registered after both `grading_bp` and `settings_bp`, so the moved copies stay shadowed by exactly the same winners: the production contract for those two URLs is unchanged. The characterization net pins both the production winner via the real `register_routes()` wiring and the moved roster body in isolation, so the verbatim body is independently proven byte-identical. This is the same discipline PR2 applied to the pre-existing `save_results` / `grade_with_parallel_detection` latent NameError: a verbatim relocation preserves pre-existing latent conditions rather than fixing them. That NameError remains tracked in **issue #423** for a dedicated characterization PR; it is out of scope for these verbatim moves.

**Recorded out-of-scope (unchanged from the slice spec section 8).** The broader 4x `AUDIT_LOG_FILE` duplication across the codebase, the dual publish-path consolidation (`published_assessments`/`submissions` vs `published_content`/`student_submissions`), and `frontend/src/tabs/PlannerTab.jsx` (the single largest source file in the repository) are each the explicitly sequenced subsequent levers and were deliberately not touched here; each needs its own dedicated design rather than a mechanical slice. The issue #423 `save_results` / `grade_with_parallel_detection` latent NameError is likewise tracked separately.

**Reconciled dimension effect.** Architecture stayed at 7 in the 2026-05-18 reconciled re-score on concrete grounds, the holdout objection being that `app.py` was still 1,935 lines with roughly 40 route functions. That specific objection is now removed: the app module is 585 lines and carries zero domain API routes. Whether that moves Architecture 7 to 8 is a judgment call, not a mechanical fact, so no nudge is asserted here. A 3-model reconciled re-score (Codex, Gemini, Claude, conservative-floor reconciliation against the 2026-05-18 baseline) follows as its own dated section and is the established post-slice judgment step, separate from this mechanically-test-guarded extraction. Consistent with how Slice 1, Slice 2, and Data Integrity Tier 1 were handled, this closeout asserts only the verifiable mechanical facts: three verbatim PRs, the pre-move-pinned characterization nets that stayed byte-identical post-move, the full suite at 0 failed, and the 9 CI checks.

---

# 2026-05-19 Post-Slice-3 3-Model Reconciled Re-Score (HEAD `d54ee8e`)

The deferred judgment step the Slice 3 closeout said would follow. Codex, Gemini, and Claude each re-scored independently against the 2026-05-18 reconciled baseline at the post-Slice-3 state (`backend/app.py` 585 LOC, zero domain API routes, 16 routes in three blueprints), then conservative-floor reconciliation (splits resolve down; the higher value only when concretely and unanimously grounded; unverifiable not credited).

| Dimension | baseline (2026-05-18) | Codex | Gemini | Claude | reconciled |
|---|--:|--:|--:|--:|--:|
| Security | 8 | 8 | 8 | 8 | **8** |
| Error Handling | 8 | 8 | 8 | 8 | **8** |
| Code Quality | 8 | 8 | 8 | 8 | **8** |
| Architecture | 7 | 8 | 7 | 7 | **7** |
| Test Coverage | 8 | 8 | 8 | 8 | **8** |
| Documentation | 7 | 7 | 7 | 7 | **7** |
| Debugging/Observability | 8 | 8 | 8 | 8 | **8** |
| Data Integrity | 9 | 9 | 9 | 9 | **9** |
| Operational Safety | 9 | 9 | 9 | 9 | **9** |
| Clever Compliance | 10 | 10 | 10 | 10 | **10** |
| **Overall** | **8.0** | **8.1** | **8.0** | **8.0** | **8.0** |

**Reconciled overall: 8.0 (unchanged).** Raw 3-model means: Codex 8.1, Gemini 8.0, Claude 8.0. Slice 3 retired a real, named structural-debt item and removed the exact concrete objection that was recorded against Architecture in the 2026-05-18 re-score, but the aggregate does not move, for the grounded reasons below.

### Per-dimension reconciled rationale

- **Architecture 7 (held; 2-1 split resolved down).** Codex scored 8 (the god-module ground is gone; the remaining defects cap below 9 rather than holding at 7). Gemini and Claude independently held 7 on concrete, verified grounds, and the conservative-floor rule resolves the split down. The 2026-05-18 Architecture 7 rested on three concrete grounds: (1) the dual publish path (`published_assessments`/`submissions` vs `published_content`/`student_submissions`) is unconsolidated, dispatched by a `supabase_table` string parameter rather than a unified abstraction; (2) `app.py` was a 1,935-line route god-module; (3) there is no dependency injection. Slice 3 resolved ground (2) cleanly and verifiably (585 LOC, zero domain routes, three cohesive import-cycle-free blueprints registered through the existing aggregator). Grounds (1) and (3) both still hold in-repo: the `supabase_table` dispatch persists across the portal grading and student-portal route paths, and no dependency-injection mechanism was introduced (the existing callback threading through `register_routes` is not DI). One of three concrete grounds resolved is genuine and commendable progress, but a tier bump under the conservative-floor philosophy needs the architectural boundary closed, not the file-size symptom; the decisive reason two independent models held is that the dual-path data model is the boundary defect and it is untouched. This split is the inverse of the 2026-05-18 one (then Codex and Gemini scored 8, Claude held 7) and resolves the same way, now with two of three independently holding rather than one.
- **Code Quality 8 (held, unanimous).** All three kept 8. The 2026-05-18 below-9 hold had two clauses: the two large non-app files (`assignment_grader.py` ~5,344, `planner_routes.py` ~4,611) and "`app.py` still carries route logic." Slice 3 removed the second clause cleanly, but the first clause is unchanged in-repo (both files still large, and `frontend/src/tabs/PlannerTab.jsx` at ~7,405 is the single largest source file), so the dimension stays mid-8 with no 9.
- **All other dimensions unchanged, unanimous.** Security 8, Error Handling 8, Test Coverage 8, Documentation 7, Debugging/Observability 8, Data Integrity 9, Operational Safety 9, Clever Compliance 10. Slice 3 was a pure verbatim relocation: auth and error decorators, Sentry and audit logging, the SIGTERM grading-stop handler, the dedup migration, and the Clever code are all carried through or untouched, so no dimension regressed and none gained verified post-baseline uplift. Two pre-existing latent conditions were faithfully preserved rather than introduced and are tracked (issue #423, the `save_results`/`grade_with_parallel_detection` NameError; issue #426, the two dead-shadowed roster routes).

### Biggest remaining lever (unanimous, all three models)

**Dual publish-path consolidation.** With the `app.py` god-module retired, all three models independently name the unconsolidated dual publish path as the single largest unresolved architectural boundary: it is the remaining concrete Architecture-7 ground with the highest blast radius (two table families, both student portals, SSE, the grading dual-dispatch), and it is the prerequisite for cross-path Data Integrity Tier 2. Claude's distinction is worth recording: `PlannerTab.jsx` (~7,405 LOC) is the largest raw file but is concentrated complexity (a Code Quality lever), whereas the dual path is a boundary defect (the Architecture lever); the latter is what gates the Architecture tier. It was deliberately scoped out of Slices 1 through 3 and needs its own brainstorm and design, not a mechanical verbatim slice.

**Honest note.** Slice 3 did exactly what it set out to do and the result is verified, not asserted: the holdout objection recorded against Architecture is concretely gone, `app.py` is now an app-factory-plus-error-handlers core, and every move was proven zero-behavior-change under a pre-move-pinned net. The aggregate stays at 8.0 because the Architecture tier is gated by the dual-path boundary, which Slice 3 correctly did not attempt. This dated section closes the `2026-05-19-app-routes-extraction` plan and Tier 2 Slice 3. The next lever is the dual publish-path consolidation, which requires its own brainstorm.

---

# 2026-05-19 Tier 2 Slice 4: dual publish-path consolidation, write/grading layer shipped (PR1 #430 / PR2)

The dual publish-path boundary is now closed at the write and grading layer. The `supabase_table` string dispatch that branched the grading pipeline on a table name is gone, replaced by a narrow `SubmissionRepository` abstraction with two adapters (`JoinCodeSubmissionRepository` over `submissions`, `ClassSubmissionRepository` over `student_submissions`), a serializable `SubmissionPathType` enum whose values ARE the legacy table strings, and a `repository_for(path_type, sb)` factory. PR1 (#430) added the module and an exhaustive characterization net pinning both paths against the pre-change wiring; PR2 rewired `backend/services/portal_grading.py`, `backend/tasks/grading_tasks.py`, and the four spawn/enqueue call sites onto the abstraction. This was executed against the `2026-05-19-dual-publish-path-consolidation` spec and plan (both now CLOSED), the design lever the post-Slice-3 re-score named as the single biggest remaining Architecture ground.

**Zero-behavior-change proof.** This is a behavior-preserving refactor, not a verbatim move (the call-site parameter type changes and two per-table branches relocate into the adapters), so the discipline was characterization-net-first. The PR1 net pins both paths independently: the join-code path and the class-based path, fetch and claim and update and the normalized-context dict and the on_failure terminal write. The net was green pre-rewire and stayed byte-identical after every PR2 task (23 of 23). Per-adapter unit tests cover each adapter in isolation with a fake supabase client. A grep gate asserts zero residual `supabase_table` string dispatch in the `portal_grading.py` pipeline body, RED before the rewire and GREEN after. Full local regression is 5115 passed, 14 skipped, 0 failed; `ruff check backend/` clean; the no-import-cycle invariant on the repository module holds; Sentry `capture_exception` accounting is unchanged across both files versus origin/main so `test_sis_alerting.py` needed no update and stays green.

**Three implementation refinements (controller-corrected during PR1, recorded for honesty).** The spec and plan sketched an idealized API; the shipped API was corrected to stay strictly behavior-preserving. (1) `claim_for_grading` mirrors the legacy `_claim_submission_for_grading` exactly: an unconditional 3-field write returning None, not a `-> bool` already-claimed guard. The dedup and stale-claim DECISION stays in the pipeline caller `grade_portal_submission_sync`, unchanged. (2) `_is_stale_claim` stays entirely in `portal_grading.py`: pipeline-scoped, not moved into the repository, not changed, no cycle introduced. (3) `mark_failed` writes exactly `status='failed'` plus the truncated error message, mirroring the `on_failure` write byte-for-byte. One further PR2 detail: the Celery `on_failure` hook and the assessment-unavailable abort path keep calling `_safe_update_submission` rather than `repository_for(...).mark_failed(...)`, because the characterization net pins those hooks by patching that module symbol and the repository write bypasses it; the database effect is identical and `grading_tasks.py` is outside the grep gate scope. The full refinement text is appended to both the spec and the plan as a dated subsection.

**Out of scope (each a separable, sequenced follow-up).** This slice closed only the write and grading dispatch boundary. Still open and deliberately untouched: the `published_assessments` versus `published_content` read split, the divergent dedup pre-check at the route layer, the two HTTP entry routes, and the physical table consolidation (a schema change and data migration that this code-only slice explicitly avoided to not bet live FERPA student-submission data on a migration). The no-dependency-injection Architecture ground is also untouched and still holds in-repo.

**Reconciled dimension effect.** Consistent with how Slices 1 through 3 and Data Integrity Tier 1 were handled, this closeout asserts only the verifiable mechanical facts above and asserts no nudge. Whether closing the dual-path code boundary at the write/grading layer moves Architecture 7 to 8 is a judgment call, not a mechanical fact, and is the specific question this program tracks. A 3-model reconciled re-score (Codex, Gemini, Claude, conservative-floor reconciliation against the post-Slice-3 baseline) follows as its own dated section, weighing that the dual-path read split and the no-DI ground both still hold while the write/grading dispatch is concretely gone.

---

# 2026-05-19 Post-Dual-Path 3-Model Reconciled Re-Score (HEAD `6767d3e`)

The deferred judgment step the Slice 4 closeout said would follow. Codex, Gemini, and Claude were dispatched independently to re-score against the 2026-05-19 Post-Slice-3 reconciled baseline at the post-dual-path state (`SubmissionRepository` is live and load-bearing; the `supabase_table` string dispatch is eliminated from the grading pipeline). Codex's read-only investigation did not converge to a verdict within the dispatch window (extended in-repo verification ran past the time bound without emitting a final scorecard); per the established conservative discipline (the 2026-05-09 Clever re-score precedent), a model that does not produce a completed assessment is treated as failed-to-run, not failed-low, and the reconciliation rests on the assessments that did complete with the conservative-floor rule still applied. The two completed assessments are unanimous and concretely grounded, plus controller first-hand verification independently confirmed the grep gate green, the abstraction load-bearing, scope strictly write-layer-only, the #431 transitional residue present, and the no-DI ground untouched.

| Dimension | baseline (2026-05-19 Post-Slice-3) | Codex | Gemini | Claude | reconciled |
|---|--:|--:|--:|--:|--:|
| Security | 8 | n/a | 8 | 8 | **8** |
| Error Handling | 8 | n/a | 8 | 8 | **8** |
| Code Quality | 8 | n/a | 8 | 8 | **8** |
| Architecture | 7 | n/a | 7 | 7 | **7** |
| Test Coverage | 8 | n/a | 8 | 8 | **8** |
| Documentation | 7 | n/a | 7 | 7 | **7** |
| Debugging/Observability | 8 | n/a | 8 | 8 | **8** |
| Data Integrity | 9 | n/a | 9 | 9 | **9** |
| Operational Safety | 9 | n/a | 9 | 9 | **9** |
| Clever Compliance | 10 | n/a | 10 | 10 | **10** |
| **Overall** | **8.0** | **n/a** | **8.0** | **8.0** | **8.0** |

**Reconciled overall: 8.0 (unchanged).** All ten dimensions are unanimous between the two completed assessments and identical to the post-Slice-3 baseline. The dual-path consolidation retired a named structural-debt item and removed one of the three concrete Architecture-7 objections, but the aggregate does not move, for the grounded reasons below.

### Per-dimension reconciled rationale

- **Architecture 7 (held, unanimous between completed assessments; controller first-hand verification concurs).** Both completed models independently arrived at the same conclusion on the same three grounds. Ground (2) (the `app.py` god-module) was already closed by Slice 3. Ground (1) (the dual-path `supabase_table` string dispatch in the grading pipeline) is concretely closed by this slice and verified genuine, not a rename: zero string dispatch remains in `backend/services/portal_grading.py` (grep gate green), the `SubmissionRepository` interface is a real polymorphic abstraction the pipeline routes through end to end (`grade_portal_submission_sync`, `fetch_submission_full_context`, `run_portal_grading_thread`, and the Celery task body all consume `repository_for(path_type, sb)`), and per-table divergence (the student-id normalization and the accommodations consumption) lives in subclasses rather than in inline branches. Ground (3) (no dependency injection) fully persists: zero DI library in `requirements*.txt`, no container, no `@inject`, no `Depends()`; dependencies are still acquired via in-function imports and module-level `get_supabase()` calls. And the slice was deliberately scoped to the write and grading layer only: the two HTTP entry routes (`/api/student/submit/<code>` and `/api/student/class-submit/<content_id>`), the `published_assessments` versus `published_content` read split, and the route-layer dedup pre-check are all still separate; the physical two-table schema is unchanged. Issue #431 records three transitional residuals that are scaffolding, not a closed seam: the Celery `on_failure` write still goes through `_safe_update_submission` rather than `repo.mark_failed` (pinned by the char net via that module symbol), two dead helpers (`_fetch_submission_row`, `_claim_submission_for_grading`) are retained because the PR1 char net references them directly, and the `supabase_table` parameter name was kept on two pipeline functions to avoid churning signature-pin tests. The conservative-floor rule under these facts is unambiguous: 2 of 3 concrete Architecture grounds are now closed, but the boundary is only half-consolidated (write side, no read or route or physical-table consolidation) and the no-DI ground is wholly untouched, so the tier holds at 7.
- **All other dimensions unchanged, unanimous between completed assessments.** Security 8, Error Handling 8, Code Quality 8, Test Coverage 8, Documentation 7, Debugging/Observability 8, Data Integrity 9, Operational Safety 9, Clever Compliance 10. The consolidation was a behavior-preserving refactor proven byte-identical by the pre-pinned characterization net (5115 passed, 0 failed; `test_sis_alerting.py` untouched and green; Sentry conservation exact; no schema change, no data migration, no frontend change), so no dimension regressed and none gained verified post-baseline uplift. The Code Quality 8 hold has the same shape it did post-Slice-3: real quality gain from the polymorphic abstraction is offset by the documented #431 transitional debt, keeping it within tier 8.

### Biggest remaining lever (the two completed assessments converged)

**Finishing the dual-path consolidation, plus a separate dependency-injection lever.** Both completed models independently named the same two remaining tier-gating items, in roughly the same order: (a) finish the dual-path consolidation outside the write layer (collapse the two HTTP entry routes plus the `published_assessments`/`published_content` read split plus the route-layer dedup pre-check onto the repository abstraction, then retire the #431 transitional residue), and (b) introduce dependency injection (the third Architecture-7 ground, fully untouched). The physical two-table consolidation is the deferred end-state lever the dual-path design explicitly chose not to bet live FERPA student-submission data on; it stays sequenced behind the code-boundary completion above. `frontend/src/tabs/PlannerTab.jsx` (about 7,405 LOC) remains the largest raw file and is the Code Quality concentrated-complexity lever, distinct from these Architecture-tier levers.

**Honest note.** The dual-path consolidation did exactly what its spec scoped: it closed the named code-boundary objection at the write and grading layer with zero behavior change, proven by the byte-identical pre-pinned characterization net plus per-adapter unit tests, and it correctly did not attempt the higher-blast-radius read, route, table, or dependency-injection levers. The aggregate stays 8.0 because the Architecture tier is gated by the remaining half of the boundary plus the no-DI ground, which this slice did not attempt. Codex did not converge within the dispatch window; the result is reported faithfully (failed-to-run, not failed-low), and the reconciliation rests on the two completed, unanimous, concretely-grounded assessments plus controller first-hand verification. This dated section closes the `2026-05-19-dual-publish-path-consolidation` plan and the Tier 2 Slice 4 lever. The next concrete step is the dual-path code-boundary completion (routes plus read split plus #431 cleanup), which the lever recap above sketches and which would be its own brainstorm.

---

# 2026-05-19 Production incident: Railway edge outage (GCP-side) and OpSafety hardening roadmap

This section records a production outage that began on 2026-05-19 evening UTC and the resulting OpSafety hardening roadmap. It is a recorded follow-up artifact, not a re-score. Whether the incident or the hardening that follows moves the Operational Safety dimension is a judgment call deferred to the next 3-model reconciled re-score, once the Tier 1 work below ships. Consistent with how every prior closeout section in this doc has been handled (Slices 1 through 4 and the Data Integrity Tier 1 closeout), the section asserts only the verifiable mechanical facts and asserts no dimension nudge.

## What happened

Slack alerted that `app.graider.live/healthz` was unreachable on 2026-05-19 around 22:00 UTC. The user reproduced the failure in a browser (Chrome `NET::ERR_CERT_COMMON_NAME_INVALID`). Diagnosis sequence (read-only, controller-driven, no production change):

1. `curl https://app.graider.live/healthz` returned the libcurl error "SSL peer cert or SSH remote key was not OK", which confirmed a TLS-layer failure rather than an HTTP-layer failure. This pre-empted any reflexive code rollback (a code regression would produce an HTTP 5xx, not a TLS handshake failure).
2. `openssl s_client -connect app.graider.live:443 -servername app.graider.live -showcerts` returned `Verify return code: 0 (ok)` (the cert chain itself was valid), but the leaf served had `subject=CN=*.up.railway.app` with a SAN list of only `DNS:*.up.railway.app`. Validity `notBefore=Apr 5 2026, notAfter=Jul 4 2026`. The cert was not expired and not malformed; it was the wrong cert for our hostname. Standard hostname validation correctly rejects it because `app.graider.live` is not in the SAN.
3. `dig +short app.graider.live A` showed `app.graider.live -> CNAME ar90ys35.up.railway.app -> 66.33.22.209` (a Railway edge POP). DNS was correct.
4. The user attempted to reach the Railway dashboard via Railway's purple "Go to Railway" button on the edge 404 page and could not. Direct navigation to `railway.app/dashboard` in an incognito window also returned the Railway edge 404 placeholder ("Not Found / The train has not arrived at the station"), with a fresh Request ID. The dashboard control plane itself was impaired.
5. The user reached `status.railway.app`, which showed a Major Outage on the Edge Network as of 22:29 UTC ("widespread service disruption, errors including 'no healthy upstream', 'unconditional drop overload', login failures, and inability to access the dashboard"). The root cause was refined at 22:43 UTC ("access to our upstream cloud provider has been restored, working on a fix"), then again at 23:37 UTC ("Google Cloud has blocked our account, making some Railway services unavailable. We have escalated this directly with Google."). The incident was still ongoing past 01:34 UTC on 2026-05-20, with Railway-metal workloads gradually recovering but GCP-hosted networking still impaired. No ETA was given.

**Net root cause.** Google Cloud blocked Railway's GCP account. This broke Railway's GCP-hosted control plane and edge custom-domain routing. Railway's edge could not authoritatively serve our custom-domain cert (it fell back to the default `*.up.railway.app` wildcard) nor route requests for `app.graider.live` (the edge returned the "train has not arrived" 404 placeholder). The Flask app behind the edge was almost certainly healthy throughout; only Railway's edge layer was degraded.

## What was NOT the cause

The recent merge sequence (#430 additive `SubmissionRepository`, #432 the dual-path rewire, #433 the post-dual-path re-score) was independently ruled out before `status.railway.app` was found. The TLS handshake failure mode plus the served cert subject established that the connection never reached Flask. Reverting code would not have helped and was explicitly recommended against in the Slack template the controller drafted for the alerting channel. That pre-empted the reflexive-revert action that a fresh prod-down alert plus a string of recent merge notifications might otherwise have triggered on a less-disciplined response.

## Our response

(a) Diagnosed upstream before touching code or production state. (b) Did not re-add the custom domain in the Railway dashboard mid-outage (risk: stuck "pending" cert state, duplicate registrations, or failed Let's Encrypt provisioning while the edge plane is degraded). (c) Did not open a Railway customer support ticket (Railway had already identified the cause, escalated to Google Cloud, and was actively working with GCP support; a customer ticket would add backlog without changing the outcome). (d) Drafted a copy-paste Slack message for the alerting channel explaining the upstream cause and instructing the team not to roll back recent PRs. (e) Held position. The recovery is upstream-bound.

## OpSafety datapoint

This is the predicted-class incident the existing 2026-05-18 OpSafety dimension already named. The line in the 2026-05-18 3-Model Reconciled Re-Score (HEAD `082b49c`), per-dimension rationale: *"Operational Safety 8 to 9 (unanimous). [...] Not 10: Railway auto-deploy on merge is still the entire rollback story (no staged rollout, no post-deploy smoke gate beyond the pre-merge E2E check)."* Tonight extends that observation: there is also no customer-side fallback when Railway's edge plane is degraded by an upstream-of-upstream incident, and there is no off-Railway status page for users (teachers, school admins) to land on during a multi-hour Railway outage. The dimension was correctly held below 10; tonight verifies the named gap and adds an adjacent one (customer-facing communication during upstream incidents).

## Hardening roadmap (three tiers)

This roadmap is the recorded plan only. Implementation requires its own brainstorm (and design approval) before code lands, following the established `superpowers:brainstorming` plus writing-plans plus subagent-driven-development flow. Three-model consultation will be applied at the genuine design forks (provider picks; v1 scope versus deferred items).

### Tier 1: cheap, high-value, do in the next week

- **Off-Railway status page.** A `status.graider.live` (or equivalent) hosted on infrastructure independent of Railway (free Statuspage by Atlassian, Instatus, Cachet, or a static page on Vercel or GitHub Pages). When `app.graider.live` is down, the status page is what users land on instead of a cert warning or Railway's edge 404. The single biggest trust win for multi-hour outages.
- **External uptime monitor.** UptimeRobot, BetterStack, or Healthchecks.io free tier, probing `/healthz` from outside our infrastructure at a 1 to 5 minute cadence with a 5-minute flap dampener, posting to the status page automatically. Independent of the existing Slack alert path.
- **A "Railway down" runbook.** Checked into `docs/`. Captures the diagnosis sequence walked above (openssl plus dig plus `status.railway.app`), the decision tree (re-add the domain or wait, file a Railway ticket or wait), the pre-drafted Slack and email comms templates, and the escalation thresholds (when 2-hour silence from Railway justifies a customer ticket). Saves the next on-call two hours of redoing the diagnosis.
- **Customer comms template.** A pre-drafted message (Slack and email) for school admins and teachers when the system is unreachable. School-facing trust during a multi-hour outage depends on us telling them what is happening, not on them noticing and reporting it.

### Tier 2: defensive layering, 1-2 weeks of work

- **Marketing-site banner ability.** `graider.live` is on Vercel (independent of Railway). Add a banner mechanism so when `app.graider.live` is down the marketing site shows an "experiencing issues, see status.graider.live" notice. Low engineering cost given Vercel is already in place.
- **Data-safety boundary documentation.** Supabase is on a separate stack from Railway (managed Postgres, separate vendor). When Railway is down, the data layer is reachable independently. Write down explicitly: what is durable across a Railway outage (Supabase rows, audit log) versus what is at risk (in-flight grading threads, results not yet persisted). This is reassurance for FERPA and school-admin conversations and is mostly documentation, not new infrastructure.
- **Optional graceful-degrade mode.** A static export of recent results behind a Vercel or Cloudflare front. Teachers can at least see yesterday's grading when the app is hard-down. Probably overkill at current scale; recorded as an option, not a commitment.

### Tier 3: architectural, only if a pattern emerges

- **Multi-PaaS active-active.** Railway plus Fly.io (or equivalent), with DNS-failover at the domain level. Real engineering cost: dual-config management, secret sync, CI pipeline doubling, database connection routing. Eliminates single-vendor risk but at high ongoing complexity cost.
- **Direct cloud migration.** AWS, GCP, or Cloudflare Workers, eliminating the Railway-as-middleman layer. Trades it for owning Infrastructure-as-Code, deploy pipelines, observability, secrets management, networking, certs. Massive operational burden for a single-developer team. Probably wrong for this app's current stage.

**Trigger conditions for Tier 3, recorded explicitly so the next on-call is not pressured to migrate reactively after a single bad night.**

- Railway has 3 or more multi-hour outages in 6 months.
- A paying-customer contract demands an SLA Railway cannot provide.
- Scale outgrows Railway's pricing model.
- A specific feature (tight network-layer control, bring-your-own-cloud for school districts) becomes blocking.

**What would NOT justify Tier 3.** One bad night, even a long one. Provider migration as "reliability theater" without measuring whether the alternative is structurally safer for the same incident class. Every PaaS competitor (Fly.io, Render, Heroku) has lived analogous multi-hour outages. Direct cloud carries its own incident class (AWS US-East-1, Cloudflare config-push incidents, GCP networking events). Single-provider risk is the structural item; provider choice rotates which incidents we are exposed to, it does not eliminate the class.

## Provider re-evaluation (recorded honestly)

The question "is Railway the correct backend provider for Graider" was raised during the incident. The recorded answer: probably yes, at this stage, with Tier 1 hardening. Reasoning:

- **Where Railway fits Graider well today.** Flask plus auto-deploy on PR-merge is the loop the project actually runs. The 9 required CI checks plus Railway's auto-deploy plus the Supabase separation is a clean, single-developer-friendly setup. The cost is appropriate for the scale (school teachers and students; bounded multi-tenant, not viral consumer). Normal-operations developer experience is strong compared to what a single developer would have to build on raw cloud.
- **Where tonight exposed a real weakness.** The dimension doc had already named the rollback-story-is-just-Railway gap. Tonight extends that to: no customer-side communication channel during a multi-hour Railway outage. The fix is Tier 1, not provider migration.
- **Competitor positioning, honest.** Fly.io: similar abstraction, similar risk class, has had its own multi-hour networking outages. Render: similar profile. Heroku: more mature but Salesforce-owned, pricing pressure. Vercel: not designed for long-running Flask plus background grading threads plus Celery workers. AWS, GCP, Cloudflare Workers direct: best reliability ceiling but total-cost-of-operation dominated by the team's time.
- **Reactive migration is not warranted by one incident.** The alternative providers carry the same incident class; the gain is not real safety, it is the appearance of action.

## Status

Recorded, not resolved. Tier 1 implementation is a future brainstorm and slice, gated on Railway's recovery (their non-enterprise build queue was throttled during ramp). The Operational Safety dimension is unchanged in this section. Whether tonight plus the Tier 1 work moves it (down 9 to 8 because the named gap was verified live; up 9 to 10 only after Tier 1 ships and the gap is closed) is a judgment call deferred to the next 3-model reconciled re-score once Tier 1 lands. The Slack template that pre-empted reflexive revert and the diagnosis sequence in this section are the two durable artifacts from tonight; both will fold into the Tier 1 runbook when it is written.

---

# 2026-05-20 Tier 2 Slice 5 closeout — dual publish-path consolidation completion

This section records the mechanical facts of the Slice 5 closeout. Per established convention, dimension scores are not asserted here; a 3-model reconciled re-score (Task 3 of the plan) will follow in its own dated section after PR2 merges.

## What shipped

**PR1 (#443) — additive only.** `PublishedContentRepository` module (`backend/services/published_content_repository.py`): `PublishedContentRepository` ABC, `JoinCodePublishedRepository` (table `published_assessments`, lookup column `join_code`), `ClassPublishedRepository` (table `published_content`, lookup column `id`), and `published_content_repository_for(path_type, sb)` factory. `ExistingSubmission` dataclass + `SubmissionRepository.find_existing_submission` extension on the ABC with per-adapter implementations (fuzzy `ilike` for join-code; exact match for class-based). Route-layer char-net extension: `TestRouteContractSeam` (9 tests) pinned both submit routes' full request-to-response observable contract pre-rewire. Test migration: `TestClaimSeam` and `TestUpdateSeam` patch targets moved from module symbols to repo methods. No production code was wired to the new module; behavior change was impossible by construction.

**PR2 (#444) — rewire + #431 fold-in.** Route rewire: both HTTP entry routes (`student_portal_routes.submit_assessment`, `student_account_routes.submit_student_work`) now go through the parallel repos for their published-content fetch and dedup pre-check. Grep gate green: `test_no_inline_published_or_dedup_queries_in_submit_routes` (4 assertions) confirms the inline `db.table('published_assessments')`, `db.table('published_content').select(...).eq('id', ...)`, and the inline `ilike`-name dedup + `content_id`+`student_id` attempt-counter queries are gone from both route bodies. The `count_existing_for` method was added to `SubmissionRepository` and both adapters, with 9 per-adapter unit tests. #431 fold-in: `on_failure` in `backend/tasks/grading_tasks.py` now calls `repository_for(supabase_table, sb).mark_failed(submission_id, exc)` (DB effect byte-identical: `status='failed'`, `error_message=str(exc)[:500]`, correct table selected by path discriminator). Three helpers retired from `backend/services/portal_grading.py`: `_fetch_submission_row` (zero production callers post-rewire), `_claim_submission_for_grading` (zero production callers post-rewire), and `_safe_update_submission` (zero callers remained after the `on_failure` switch). `supabase_table` parameter renamed to `path_type` on `grade_portal_submission_sync` and `run_portal_grading_thread`; the Celery `args[2]` cross-wire slot keeps the `supabase_table` name because the enum's `.value` (the legacy string) crosses the wire and the `on_failure` extraction reads `args[2]`.

## Route + read + dedup boundary status

The inline `db.table(...)` queries that were open-coded in both submit route bodies are gone. Both routes now resolve published-content rows through `published_content_repository_for(...)` and dedup through `submission_repo.find_existing_submission(...)`. The boundary is load-bearing in production: the grep gate and the byte-identical `TestRouteContractSeam` together prove zero behavior change at the route layer. Architecture ground 1 is now fully closed at both the write/grading layer (Slice 4) and the route/read/dedup layer (Slice 5).

## Zero schema change, zero data migration, zero behavior change

Proven by three independent gates:

- `TestRouteContractSeam` (9 tests): both routes' full request-to-response observable contract pinned pre-rewire; assertions byte-identical post-rewire. Any behavior change would have broken a pinned assertion.
- `test_no_inline_published_or_dedup_queries_in_submit_routes` (4 assertions): grep gate confirms the old inline patterns are absent from both route files.
- Per-adapter unit tests for the new abstractions (`count_existing_for`, `find_existing_submission`, `fetch_by_lookup_key`): each adapter's query logic is tested in isolation against `FakeSupabase`.

No Alembic migration, no table alteration, no data backfill. The two physical table pairs (`published_assessments`/`published_content` and `submissions`/`student_submissions`) are unchanged.

## #431 fold-in shipped

All three transitional residuals from Slice 4's char-net contract are retired:

1. `on_failure` unified onto `repo.mark_failed` (the DB write is byte-identical; `TestFailureSeam` patches `SubmissionRepository.update` or `.mark_failed` in lockstep with the production change).
2. `_safe_update_submission`, `_fetch_submission_row`, `_claim_submission_for_grading` all deleted (zero callers verified by grep before deletion).
3. `supabase_table` renamed to `path_type` on `grade_portal_submission_sync` + `run_portal_grading_thread`; the Celery wire boundary keeps the legacy string name via `args[2]`.

## Out of scope (unchanged)

No dependency injection was introduced (Architecture ground 3 remains open). No HTTP endpoint consolidation (the two submit routes remain separate endpoints with their distinct auth models). No frontend change. No physical table consolidation (the four physical tables remain; consolidating FERPA student-submission data across paths was explicitly deferred in the Slice 4 design and remains deferred). These are documented future levers, not regressions.

## Net diff

```
 12 files changed, 385 insertions(+), 334 deletions(-)
```

Branch commits (5 commits beyond main at closeout time):

```
8aac8b6 refactor(portal): close #431 transitional residuals — on_failure unified, 2 dead helpers retired, supabase_table renamed (Slice 5 PR2)
c5eaecd refactor(routes): student_account_routes.submit_student_work uses parallel repos + count_existing_for (Slice 5 PR2)
281eeea test(routes): tighten class-path grep gate to catch multi-line inline patterns (Slice 5 PR2)
e4cf38d refactor(routes): student_portal_routes.submit_assessment uses parallel repos (Slice 5 PR2)
64433f8 test(routes): RED grep gate for inline dedup + published-content fetch removal (Slice 5 PR2)
```

## Sentry conservation

Net -1 capture globally. The three retired helpers (`_safe_update_submission`, `_fetch_submission_row`, `_claim_submission_for_grading`) had `sentry_sdk.capture_exception` calls that were redundant with the repo methods' captures (which have existed since Slice 4 PR1). This is a cleanup, not a coverage loss. `PR_B_EXPECTED_CAPTURES` floor in `tests/test_sis_alerting.py` is unaffected (the renamed-out files were not gated).

## Tests delta

PR1 baseline: 5146 passed. After PR1+PR2: 5145 passed + 14 skipped + 1 known flake (`test_anthropic_chat_uses_breaker` passes in isolation; same sibling pattern as the plan-mentioned `test_gemini_chat_uses_breaker`). The net -1 from baseline accounts for: +1 grep gate test + 9 new `count_existing_for` tests − 11 deleted test instances (6 `TestClaimSeam` parametrized + 5 `TestUpdateSeam`) = −1.

## Next step

3-model reconciled re-score (Task 3 of the plan): Codex, Gemini, and Claude re-score independently against the post-Slice-5 state. The decisive judgment: with Architecture ground 1 now fully closed (both write/grading layer from Slice 4 and route/read/dedup layer from Slice 5) and #431 retired, but ground 3 (no DI) still open and physical table consolidation still deferred, does Architecture move from 7 to 8? Conservative-floor reconcile applies. The re-score appends its own dated section.

---

# 2026-05-21 Post-Slice-5 3-Model Reconciled Re-Score (HEAD `d2f5908`)

The deferred judgment step the Slice 5 closeout said would follow. Codex, Gemini, and Claude were dispatched independently to re-score against the 2026-05-19 Post-Dual-Path reconciled baseline at the post-Slice-5 state (both submit routes route through the parallel repos; the inline published-content fetch and route-layer dedup queries are gone from both route bodies; the three transitional helpers from #431 are retired; the byte-identical characterization net stayed green across the rewire).

Gemini's read-only investigation did not converge to a Slice-5 verdict within the dispatch window (the session went off-task to investigate unrelated planning documents, hit multiple upstream 500s on the underlying API, and emitted an exception-handling refactor plan instead of a re-score). Per the established conservative discipline (the 2026-05-09 Clever re-score precedent and the 2026-05-19 Post-Dual-Path precedent where Codex did not converge), a model that does not produce a completed assessment is treated as failed-to-run, not failed-low, and the reconciliation rests on the assessments that did complete with the conservative-floor rule still applied. The two completed assessments are concretely grounded, plus controller first-hand verification independently confirmed: the grep gate green (`test_no_inline_published_or_dedup_queries_in_submit_routes` all 4 assertions, function-body-scoped via `inspect.getsource`), the char net byte-identical (`TestRouteContractSeam` 9 tests still green post-rewire), the three retired helpers gone with zero production callers, no DI mechanism introduced (no `@inject`, `Depends()`, `injector`, `dependency-injector`, or `punq` in `requirements*.txt`), the physical two-table schema unchanged (migration head unchanged), and Sentry conservation a clean dedup (-1 net global; the retired helpers had captures redundant with the repo-method captures, which have existed since Slice 4 PR1).

| Dimension | baseline (2026-05-19 Post-Dual-Path) | Codex | Gemini | Claude | reconciled |
|---|--:|--:|--:|--:|--:|
| Security | 8 | 8 | n/a | 8 | **8** |
| Error Handling | 8 | 8 | n/a | 8 | **8** |
| Code Quality | 8 | 8 | n/a | 8 | **8** |
| Architecture | 7 | 8 | n/a | 8 | **8** |
| Test Coverage | 8 | 8 | n/a | 9 | **8** |
| Documentation | 7 | 7 | n/a | 7 | **7** |
| Debugging/Observability | 8 | 8 | n/a | 8 | **8** |
| Data Integrity | 9 | 9 | n/a | 9 | **9** |
| Operational Safety | 9 | 9 | n/a | 9 | **9** |
| Clever Compliance | 10 | 10 | n/a | 10 | **10** |
| **Overall** | **8.0** | **8.3** | **n/a** | **8.2** | **~8.1** |

**Reconciled overall: ~8.1 (Architecture 7 → 8 lifts the mean modestly).** Architecture moves from 7 to 8 on unanimous concretely-grounded agreement between the two completed assessments plus controller first-hand verification. All other dimensions are unanimous holds, identical to the post-Slice-4 baseline.

### Per-dimension reconciled rationale

- **Architecture 7 → 8 (bumped, unanimous between completed assessments; controller first-hand verified).** Both completed models independently arrived at 8 on the same in-code grounds. The 2026-05-19 Post-Dual-Path baseline cited three concrete Architecture-7 grounds: (1) the dual-path consolidation was half-closed (write-and-grading layer done, but read/route/dedup/#431 residuals remained), (2) the `app.py` god-module (already closed by Slice 3), and (3) no dependency injection. Slice 5 closes the second half of ground (1) at the boundary, not the symptom: both HTTP submit routes (`submit_assessment` in `student_portal_routes.py`, `submit_student_work` in `student_account_routes.py`) now route their published-content fetch through `content_repo.fetch_by_lookup_key(...)` and their dedup pre-check / attempt counter through `submission_repo.find_existing_submission(...)` / `submission_repo.count_existing_for(...)`. The inline `db.table('published_assessments')`, `db.table('published_content').select(...).eq('id', ...)`, `.ilike('student_name', ...)`, and `.eq('content_id', ...).eq('student_id', ...)` patterns are gone from the route function bodies (verified by a grep gate scoped via `inspect.getsource` so it actually enforces what it claims, not just a name-only check), while remaining present and untouched in other functions of the same files where they belong. The #431 transitional residue is fully retired: `_safe_update_submission`, `_fetch_submission_row`, and `_claim_submission_for_grading` are gone from `backend/services/portal_grading.py` (zero production callers), `on_failure` in `backend/tasks/grading_tasks.py` now calls `repository_for(supabase_table, sb).mark_failed(submission_id, exc)` with byte-identical DB effect, and `supabase_table` is renamed to `path_type` on `grade_portal_submission_sync` and `run_portal_grading_thread`. Char net byte-identical green proves zero behavior change (`TestRouteContractSeam` 9 tests pinned in PR1 stayed green post-rewire). With 2 of the 3 prior Architecture-7 grounds now closed (god-module from Slice 3, dual-path code-boundary completion from Slice 5), the boundary is closed at the read+route+dedup layer for the first time. Ground (3) DI is the dominant remaining lever and what holds Architecture short of 9 (six in-function `from backend.services.submission_repository import …` and `from backend.services.published_content_repository import …` statements in production paths remain — the small dispatch-from-inside-the-function pattern would lift cleanly under a small DI library like `punq` or a hand-rolled provider). Physical two-table consolidation stays deferred for FERPA-data-safety reasons, not architecture debt. 8 is the honest, conservative-floor reflection; 9 would require either DI or the physical schema consolidation.

- **Test Coverage 8 (held; one completed assessment moved to 9, the conservative-floor rule and the 2-independent-confirmations bar both keep it at 8).** Claude scored 9 on the strength of PR1's pre-pinned `TestRouteContractSeam` net (9 tests pre-rewire), the byte-identical post-rewire proof, the per-adapter unit suites for the new abstractions (40 tests in `test_submission_repository.py` including 9 new `count_existing_for` tests, 14 tests in `test_published_content_repository.py`), and the two grep gates (`test_no_supabase_table_string_dispatch_remains` plus the new `test_no_inline_published_or_dedup_queries_in_submit_routes`). Codex held at 8 on failed-to-run on the test execution itself (the read-only sandbox lacked a usable temp directory; the assessment was static-only). Under the conservative-floor discipline plus the established bar that a tier bump needs at least two independent confirmations with concrete grounds, one completed bump is not enough. Test Coverage holds at 8 with the genuine quality win recorded in the prose rationale rather than the numeric tier.

- **All other dimensions unchanged, unanimous between completed assessments.** Security 8, Error Handling 8, Code Quality 8, Documentation 7, Debugging/Observability 8, Data Integrity 9, Operational Safety 9, Clever Compliance 10. Slice 5 was a behavior-preserving refactor (the `TestRouteContractSeam` 9-test char net proves byte-identical request-to-response contract on both submit routes pre and post rewire). No schema change, no data migration, no frontend change, no Clever surface touched. The Code Quality 8 hold is honest about `frontend/src/tabs/PlannerTab.jsx` (around 7,405 LOC) remaining the largest raw file and the concentrated-complexity Code Quality lever, separate from these Architecture-tier levers. Sentry conservation analysis: total backend captures went from 177 to 176 globally; the 3 retired helpers had captures that were redundant with the repo-method captures (which have existed since Slice 4 PR1 alongside the helpers during the transition window); the global net is cleanup, not coverage loss, and `tests/test_sis_alerting.py` (the floor gate) is green and the `PR_B_EXPECTED_CAPTURES` floor list does not gate `portal_grading.py` or `submission_repository.py`, so the contract is unaffected.

### Biggest remaining lever (the two completed assessments converged)

**Dependency injection and the deferred physical-schema consolidation.** Both completed models independently named DI as the single largest unresolved Architecture lever. The repository layer added by Slices 4 and 5 has clean seams (repository factories, the `SubmissionPathType` enum, the byte-identical Celery wire-arg), which means a small DI library could lift the six in-function `from backend.services...import...` statements in production paths without a structural rewrite — the prerequisites for DI are now in place. The deferred physical-schema consolidation (`submissions` + `student_submissions` and `published_assessments` + `published_content`) stays sequenced behind ground (3) because it's deliberately deferred for FERPA-data-safety reasons, not architectural debt. `frontend/src/tabs/PlannerTab.jsx` (around 7,405 LOC) is the separate Code Quality concentrated-complexity lever, distinct from these Architecture-tier levers.

### Honest meta-notes

- **Architecture ground 1 is now fully closed at the code boundary** (write-and-grading layer from Slice 4, read+route+dedup layer from Slice 5), with the #431 transitional residue retired. The same physical two-table schema persists, by design.

- **Gemini failed-to-run faithfully reported.** Gemini's session went off-task and emitted an exception-handling refactor plan rather than a Slice-5 re-score; multiple upstream API 500s during processing didn't help. Treated as failed-to-run, not failed-low, per the established discipline. The reconciliation rests on the two completed assessments (Claude and Codex, both unanimous on Architecture 7 → 8) plus controller first-hand verification of the in-code grounds.

- **Codex's compatibility observation worth recording.** Codex flagged that the `on_failure` body's kwargs fallback default still says `supabase_table='submissions'` (e.g. `kwargs.get('supabase_table', 'submissions')`) while the rename was `supabase_table` → `path_type` on the two pure functions. This is the cross-the-wire constraint the implementer documented (Celery's `args[2]` positional slot keeps the legacy name because `SubmissionPathType.<X>.value` equals the legacy table-name string and crosses the wire byte-identical). Current call sites pass positional `args[2]` per the wire contract, so it's not a current production break, but if a future caller passes `path_type=` as a keyword and omits the positional, failure marking would default to `submissions`. Latent compatibility debt; non-blocking for the tier bump but worth a follow-up issue if anyone ever tightens the Celery wire interface.

This dated section closes the Slice 5 lever. The next concrete step is the third Architecture-7 ground (no dependency injection), which the lever recap above sketches and which would be its own brainstorm + design + plan + slice. Tier 1 OpSafety hardening (the off-Railway status page, external uptime monitor, "Railway down" runbook, customer comms template; recorded in the 2026-05-19 production incident dated section) is the explicitly sequenced item that should come before the next big architectural lever, per the user's request that operational safety lessons from the outage be shipped before resuming pure architectural decomposition.

---

# 2026-05-21 Tier 1 OpSafety hardening closeout (PR #447 + PR #448)

The Tier 1 implementation the 2026-05-19 production incident dated section named as the first thing to ship before resuming pure architectural decomposition. Brainstormed via `superpowers:brainstorming` (spec `docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md`), planned via `superpowers:writing-plans` (plan `docs/superpowers/plans/2026-05-21-opsafety-tier1.md`), executed subagent-driven with two-stage review per task.

## Scope correction recorded

The original 2026-05-19 PR #434 OpSafety roadmap listed "off-Railway status page" and "external uptime monitor" as Tier 1 items, but the BetterStack stack (Uptime + Status Page at `status.graider.live` + Slack alerts + iOS Critical Alerts) already shipped on 2026-04-11 per `docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md` and `docs/observability.md`. The actual remaining gap was narrower: customers had no path from broken `app.graider.live` to the working `status.graider.live`, and the 2026-05-19 diagnosis sequence + comms templates were not captured anywhere durable. The "marketing-site banner" item that the PR #434 roadmap labeled Tier 2 was promoted to Tier 1 in this slice's spec because the incident verified it as the missing piece of customer trust.

## What shipped

- **`docs/runbooks/railway-down.md`** (PR1 #447) — 5-section on-call reference: confirm it's Railway (curl/openssl/dig/status.railway.app), decision tree mapping symptom to cause and action, escalation thresholds (30 min / 2 hr / multi-hour), what NOT to do (no reflex rollback on TLS handshake fail, no domain re-add mid-outage, no Railway ticket within 2 hr, no reactive provider migration), post-incident verification.
- **`docs/runbooks/customer-comms-templates.md`** (PR1 #447) — 3 templates: Slack `#alerts` (internal-team, immediate on incident confirmation), customer email (school admins, multi-hour outages with active impact only; FERPA-aware reassurance that Supabase-stored student work is safe), in-app banner reference (handled by PR2).
- **`landing/status-banner.js`** + **`landing/status-banner.test.js`** (PR2 #448) — vanilla JS module (the spec assumed React but `landing/` is plain HTML/CSS/JS; the plan corrected to vanilla JS with `node:test`). Pure-logic `shouldShowBanner(statusJSON)` + browser-only IIFE fetching `https://status.graider.live/api/v1/status.json` on `DOMContentLoaded` with a 3 s timeout, rendering a sticky dismissible banner when BetterStack reports non-operational. Fails-open on any error. 16 `node:test` unit tests (4 BetterStack status states + monitor-degraded + incident-active edge cases + 8 fails-open shapes), all green.
- **`landing/index.html` + `landing/styles.css`** (PR2 #448) — banner container after `<body>` + sticky yellow/orange CSS + dismiss button + mobile-responsive media query.
- **`docs/observability.md` — "Probe-coverage audit" section** (PR2 #448) — documents the 6 BetterStack monitor config fields to verify (probe URL is custom domain not Railway-internal, expected status, response-body keyword, timeout, follow-redirects, TLS-failure classification). **The audit itself is deferred to the next quarterly drill (first Monday of Jul 2026)** per user decision, because the probe DID fire correctly on 2026-05-19 (Slack alert landed within minutes), making the audit a "verify the why" follow-up rather than a blocking prerequisite.
- **`.gitignore`** (PR2 #448) — one-line `!landing/*.test.js` carve-out of the existing blanket `*.test.js` ignore rule, matching the existing `!frontend/e2e/*.spec.js` negation pattern.

## Deferred within this slice

- **Probe-coverage audit findings** — deferred to the Jul 2026 quarterly drill. The drill checklist is documented in `docs/observability.md`.

## Out of scope (recorded explicitly)

- Tier 2 items (data-safety boundary documentation, graceful-degrade mode). Stay deferred.
- Tier 3 items (multi-PaaS active-active, direct cloud migration). Stay deferred per the trigger conditions in the 2026-05-19 dated section.
- Frontend error tracking — known gap in `docs/observability.md` follow-ups. Separate brainstorm.
- SSL / domain expiry monitoring. BetterStack paid feature, deferred per existing observability doc.
- Provider re-evaluation. The 2026-05-19 incident dated section concluded Railway is the right provider at this stage; not re-litigated.

## Mechanical asserts

Two implementation PRs shipped (#447 docs-only, #448 infrastructure) plus the spec+plan PR (#446). 9 CI checks green on all. `cd landing && node --test status-banner.test.js` returns 16 passed, 0 failed. The customer-facing banner deploys with `cd landing && npx vercel --prod` (explicit CLI step, not auto-deployed on merge); the deployed `index.html` serves the `#status-banner` div (verifiable with `curl -sS https://graider.live/ | grep -c 'id="status-banner"'`).

## Operational Safety dimension note

Whether Tier 1 closure moves the Operational Safety dimension (currently reconciled 9) is a judgment call deferred to a 3-model reconciled re-score, consistent with how every prior slice closeout has been handled. The 2026-05-19 incident verified the customer-communication gap live; this slice closes it (the banner gives customers a path to the status page during a Railway-edge outage). The probe-coverage audit being deferred is the one open thread; a re-score would weigh whether the dimension moves 9 → 10 now or holds at 9 until the audit confirms the probe catches the TLS-handshake failure class.

## Next concrete step

Either: (a) post-slice 3-model reconciled re-score weighing whether Operational Safety moves 9 → 10 given Tier 1 closure (the audit-deferred caveat would factor into the conservative-floor reconciliation), or (b) the third Architecture-7 ground (no dependency injection) brainstorm, which the 2026-05-21 Post-Slice-5 re-score named as the dominant remaining Architecture lever. The repository layer added by Slices 4 + 5 has clean seams (factories, the `SubmissionPathType` enum, byte-identical Celery wire) that make a small DI library a structurally low-risk next slice.

---

# 2026-05-22 DI provider closeout (PR #452 + PR #453)

The third Architecture-7 ground (no dependency injection) addressed at the repository/supabase seam. Brainstormed via superpowers:brainstorming with 3-model consultation on the mechanism (Claude + Codex reconciled on a hand-rolled provider; Gemini leaned toward a DI library but failed to engage the Flask+Celery dual-context constraint — weak signal, treated as failed-to-run-not-failed-low). Executed subagent-driven with two-stage review.

## What shipped

- `backend/providers.py` (PR1 #452) — get_supabase_provider() (contextvars override or supabase_client.get_supabase()), get_submission_repository(path_type), get_published_content_repository(path_type), override_supabase(fake) contextmanager (contextvars-backed, resets in finally including on exception). Plain module functions → context-independent (works in Flask AND Celery). 11 unit tests including a mutation-probe-verified contextvars per-thread isolation test.
- `repository_for(path_type, sb=_UNSET)` + `published_content_repository_for(path_type, sb=_UNSET)` (PR1 #452) — default-resolve from the provider when the arg is OMITTED; a module-level sentinel `_UNSET` (not None) distinguishes "omitted" from "explicit None" so the existing degraded-mode tests that call `repository_for(..., None)` keep working. Backward-compatible.
- Grading/task failure seams (PR2 #453) — `grading_tasks.py` on_failure + the no-assessment failure branch, and `portal_grading.py` run_portal_grading_thread's deferred-update, all route through get_submission_repository(path_type). The gate dropped from `if sb [and submission_id]:` to `if submission_id:` (or removed); the repo's internal `if not self._sb` guard preserves the observable no-write-when-None behavior.
- Char-net update (PR2 #453) — a TestFailureSeam test that asserted `repository_for` was NOT called when the client is None was pinning an implementation detail, and a mutation probe proved the original "no exception" assertion was masked by on_failure's `try/except pass`. Split into two falsifiable contracts: `test_on_failure_writes_via_provider_when_client_present` (TestFailureSeam, recording-client assertion) + the existing repo-layer `test_update_sb_none_pages_sentry_with_hashed_id` (no-write-when-None, no try/except masking). Both mutation-probe-verified. TestRouteContractSeam stayed byte-identical.
- Ergonomics proof (PR2 #453) — `test_task_aborts_when_assessment_is_none` rewritten from 4 patches → 2: a single `override_supabase(fake)` replaces the `repository_for` + `get_supabase` patch pair, with a stronger observable assertion. The single-switch testability win the provider was built for.

## Planning-time scope refinement (recorded honestly)

A code audit during planning found the call-site migration is narrower than the spec first assumed. Three findings: (1) the char net pins call-count at the if-sb guards (migrating makes `repository_for` fire even with a None client, which no-ops via the repo's own guard — observable DB effect identical, but the call-count assertion needed updating to the observable contract); (2) `submit_student_work` uses `get_supabase_or_raise` (raise-if-unconfigured) while the provider uses `get_supabase` (returns None) — raise-vs-None semantics differ; (3) several sites use `sb` for both repo construction AND direct `db.table` queries, so migrating the repo line alone double-acquires + creates a test-interception asymmetry. Decision (user-approved): migrate the clean repo-only `get_supabase`-based seams + update the ~2 call-count assertions to falsifiable observable-effect assertions; defer the dual-use + raise-semantics sites.

## Out of scope (follow-up slices)

The ~80 other get_supabase() call sites, the 6 duplicate _get_supabase() definitions, AI/LLM clients (`api_keys.py`, `llm_adapter/`), config loading, and the dual-use + raise-semantics seams above.

## Verification

Full regression after PR2: 5155 passed, 14 skipped, 1 known network flake (`test_openai_chat_uses_breaker` — third sibling of the anthropic/gemini breaker flakes; passes in isolation in ~19s, verified). Both DI-contract mutation probes green. Ruff clean on modified files. TestRouteContractSeam byte-identical across the rewire.

## Next step

Post-slice 3-model reconciled re-score weighing whether Architecture moves 8 → 9. Honest framing required: this is lightweight provider-based DI live at ONE seam (the grading/task failure path), genuinely used in production, with the testability win demonstrated (override_supabase replaces multi-module patching) — but it is NOT a framework across the codebase, and the dual-use/raise-semantics seams + the ~80 other call sites still acquire deps directly. A conservative-floor reconcile will weigh whether seam-level DI + the clean provider infrastructure clears the bar, or whether the broader conversion follow-up is a prerequisite. The honest expectation is that this likely holds Architecture at 8 (the objection is addressed at the seam but not retired codebase-wide) — the re-score makes that judgment explicit.

---

# 2026-05-22 PlannerTab calendar extraction closeout (PR #456)

The first slice of Wave 3 — the resumption of the Code-Quality concentrated-complexity lever (`frontend/src/tabs/PlannerTab.jsx`, the largest raw file). Distinct from the Architecture-tier DI/dual-path work: this is frontend cluster-extraction continuing the cadence of the 2026-05-04 Planner extraction plan (Waves 1–2 pulled the Planner JSX + ~91 state pairs out of App.jsx and INTO PlannerTab.jsx, which is precisely why PlannerTab itself is now the lever at 7,405 LOC). Brainstormed via superpowers:brainstorming (cluster pick + extraction shape, both user-chosen), planned via superpowers:writing-plans, executed subagent-driven with two-stage review per task. Spec `docs/superpowers/specs/2026-05-22-plannertab-calendar-extraction-design.md`, plan `docs/superpowers/plans/2026-05-22-plannertab-calendar-extraction.md`.

## What shipped

- `frontend/src/components/PlannerCalendar.jsx` (new, 735 LOC) — owns the calendar cluster end-to-end: 15 state vars, the fetch effect, 11 helpers, the ~600-line JSX. Interface: `{ active, addToast, savedLessons, supportDocs, setSupportDocs }`. The cleanest isolated `plannerMode` block (no coupling to lesson/assessment generation; reuses the already-extracted HolidayModal/ImportEventsModal).
- `frontend/src/tabs/PlannerTab.jsx` — renders `<PlannerCalendar active={activeTab === "planner"} … />` inside its existing `{plannerMode === "calendar" && (…)}` gate; the inline calendar state/effect/helpers/JSX removed, plus the now-dead HolidayModal/ImportEventsModal imports and 4 pre-existing dead imports. **7,405 → 6,680 LOC (−725).**
- `frontend/src/__tests__/PlannerCalendar.test.jsx` (new, +3 tests) — pins the one behavioral reformulation, the `active`-prop fetch contract, in isolation. Full frontend suite 181 → 184.

## Behavior preservation

Verbatim move. The only non-verbatim change: the fetch effect re-expressed from `if (activeTab === "planner" && plannerMode === "calendar")` to `useEffect(() => { if (active) loadCalendar(); }, [active])` — the conditional render handles the plannerMode half, the `active` prop the activeTab half (provably equivalent fetch timing). Proven by a whitespace-normalized JSX parity diff (596 lines, byte-for-byte identical) + the existing PlannerTab calendar tests (fetch effect + Calendar mode button) staying green through PlannerTab → PlannerCalendar + the Playwright health-check E2E.

## Course-corrections recorded honestly

- **Audit miss caught at implementation time.** The design audit's external-surface scan omitted `supportDocs`/`setSupportDocs`. They are App-level shared state (`App.jsx:1481`, also consumed by the Settings/Tools tab); the calendar import flow reads the doc list and lazy-loads it. The implementer flagged it and initially localized them — which would have broken the shared-doc-list contract. Corrected to forward them as props; spec §3/§5/§9 + the plan updated to the 5-prop interface. Lesson: an external-identifier scan must enumerate every referenced prop, not a hand-picked subset.
- **Subagent timeout on the large removal.** The Task-3 implementer subagent hit a stream-idle timeout having applied nothing durable (clean slate). The controller completed the 721-line removal directly via an assertion-guarded anchor-based script (aborts rather than corrupts if any anchor is missing/ambiguous), then ran the same two-stage spec + code-quality review on the result. The byte-identical JSX parity diff is the definitive correctness proof for a verbatim move of this size.

## Out of scope (follow-up slices)

The other four `plannerMode` blocks remain inline in PlannerTab.jsx: tools/reading-level (~806 LOC, the next cleanest isolated cluster), dashboard (~573), and the cross-coupled lesson (~2,193) + assessment (~1,625). Each its own brainstorm → spec → plan → slice.

## Verification

Vite build clean; full frontend suite 184 passed; JSX parity OK (596 lines, whitespace-normalized byte-identical); existing PlannerTab calendar tests green; all 9 CI checks green. Merged PR #456 (squash `b696acf`), Railway auto-deployed.

## Scorecard note

Code-Quality lever, not Architecture-tier. A single isolated-cluster extraction is unlikely to move a dimension score on its own; the cumulative effect across the PlannerTab Wave-3 slices (calendar + tools + dashboard + lesson + assessment) is what would. No 3-model re-score run for this slice (deliberate — predictable hold; the judgment is recorded here rather than burning a dispatch), consistent with the DI closeout's reasoning. A re-score becomes worthwhile once several PlannerTab slices have landed and the file is materially smaller.

---

# 2026-05-22 PlannerTab tools + dashboard extraction closeout (PR #458 + PR #459)

Wave 3 slices 2 and 3, continuing the Code-Quality concentrated-complexity lever (`frontend/src/tabs/PlannerTab.jsx`). Both behavior-preserving verbatim moves under the calendar-slice cadence (brainstorm/spec → programmatic assembly+rewire scripts because the file is large and a subagent edit timed out on the calendar removal → two-stage subagent review → byte-for-byte JSX parity). Specs: `docs/superpowers/specs/2026-05-22-plannertab-tools-extraction-design.md`, `…-dashboard-extraction-design.md`.

## What shipped

- **Tools tab → `components/PlannerTools.jsx`** (PR #458, 841 LOC). The full 4-tool tab (reading-level + study guide + flashcards + slides), 24 tool-local state vars moved in, 7 forwarded props. Zero logic change (no effect to re-express). PlannerTab 6,680 → 5,853 LOC (−827).
- **Student Portal Dashboard → `components/PlannerDashboard.jsx`** (PR #459, ~575 LOC). Purely presentational — the block owned no local state (already prop-driven from App), so 34 forwarded props (data + handlers + setters + the `renderTagRow` render-prop + `setAttemptDrawerStudent`); no state removed from PlannerTab. PlannerTab 5,853 → 5,322 LOC (−531).
- **Cumulative Wave 3 (calendar + tools + dashboard): PlannerTab 7,405 → 5,322 LOC (−28%).** Three focused, independently-tested, single-responsibility components extracted (PlannerCalendar 735, PlannerTools 841, PlannerDashboard 575). Frontend suite 181 → 189.

## Audit-method course-corrections (recorded honestly)

Each slice surfaced one external dependency the initial "exhaustive" audit missed — the method converged across the three:
- **calendar:** `supportDocs`/`setSupportDocs` (a shared prop) — caught by the implementer.
- **tools:** `shareWithClass` (a `function X` parent-body closure) — caught by the code-quality review.
- **dashboard:** `renderTagRow` (a `var X = function` parent-body closure) — caught by the controller's own free-variable scan *before* review.
The durable fix: the pre-extraction audit now enumerates **all** free identifiers (props, imports, *and* parent-body `function`/`const`/`var` closures via a call-pattern free-variable scan), and prop sets are derived programmatically so the component signature and the call site cannot drift (verified equal). For prop-driven blocks this matters because a missed handler/render prop is a **runtime** error, not a build error.

## Verification

Per slice: Vite build clean, byte-for-byte normalized-JSX parity (calendar 596, tools 803, dashboard 569 lines — all zero-diff), full frontend suite green (189 after dashboard), both spec-compliance and code-quality reviews passed, all 9 CI checks green, merged. No `App.jsx` or backend change in any slice.

## Next step

3-model reconciled re-score (Claude + Codex + Gemini, conservative floor) weighing whether Wave 3's PlannerTab de-concentration moves **Code Quality 7 → 8**. Honest framing: the prior re-score capped Code Quality at 7 because "LOC was relocated, not eliminated" (PlannerTab 7,405, SettingsTab 6,534, assignment_grader 7,444). Wave 3 genuinely *de-concentrates* PlannerTab (−28%, three focused tested components) — directly attacking the named "concentrated complexity" lever — but the LOC still largely relocated into sibling components, and **SettingsTab (6,534) + assignment_grader (7,444) are untouched** and PlannerTab still carries the lesson (~2,193) + assessment (~1,625) blocks. The re-score makes the continue-vs-pivot call: keep extracting PlannerTab (lesson/assessment), pivot to the other god-files, or consolidate.

---

# 2026-05-22 Post-Wave-3 PlannerTab decomposition re-score (PRs #456 + #458 + #459)

3-model reconciled re-score weighing whether the Wave 3 PlannerTab decomposition (calendar + tools + dashboard slices) moves the **Code Quality** dimension from its prior 7/10. Method: three independent models each verified the live code with their own shell commands — Claude (controller, first-hand), Codex (`codex exec`), Gemini (`gemini -p`). Conservative-floor reconciliation: on a split the lower score wins unless a model presents strong disconfirming file:line evidence.

| Model | Code Quality | Recommendation |
|---|---|---|
| Claude | 7 (hold, "strong direction to 8") | continue lesson/assessment, but the dimension needs broader de-concentration — App.jsx (7,144) is now the largest frontend file |
| Codex | 7.5 | continue PlannerTab lesson/assessment, then pivot to SettingsTab.jsx |
| Gemini | 8 | continue PlannerTab (lesson/assessment) toward a <3k-LOC target, then SettingsTab.jsx |
| **Reconciled** | **7 (held — a near-8 on the cusp)** | continue PlannerTab lesson/assessment, then pivot to SettingsTab.jsx |

## Verdict: Code Quality holds at 7 (conservative floor). Overall unchanged at 7.8.

All three models verified the same facts firsthand — there is **no factual split, only a judgment split** (7 vs 7.5 vs 8) — so the conservative floor takes Claude's 7. Claude's basis (the concentration is multi-file and only one file was partially decomposed) was not disconfirmed by the higher scores.

**What all three confirmed (real, verified progress):**
- `frontend/src/tabs/PlannerTab.jsx` 7,405 → 5,322 LOC (−28%), de-concentrating the repo's former single-largest source file.
- Three focused, cohesive, single-responsibility components extracted with their own tests: `PlannerCalendar.jsx` (735), `PlannerTools.jsx` (840), `PlannerDashboard.jsx` (577); 8 new component tests — the first unit-testable surfaces for these features.
- `assignment_grader.py` is now 5,344 LOC, down from the 7,444 baseline that partly drove the original "Code Quality 7" cap (Gemini's disconfirming evidence against part of the cap basis).

**Why the floor still holds at 7 (Claude's basis, not disconfirmed):**
- The concentration is **multi-file**; Wave 3 improved one file partially. `App.jsx` is now the **largest** frontend file at 7,144 LOC (untouched by Wave 3); `SettingsTab.jsx` remains a 6,534 LOC monolith (all three models); `PlannerTab.jsx` still carries large inline `lesson` (~2,193 LOC) and `assessment` (~1,800 LOC) blocks.
- The LOC was largely **relocated** into sibling components, not eliminated — the original cap's framing partly persists.
- This is now a "high 7 on the cusp": all three agree the trajectory is right. The floor lifts to 8 once PlannerTab is fully decomposed (lesson/assessment) **and** at least one more god-file (SettingsTab) is started.

## Recommendation (consensus): continue, then pivot

All three models recommend **continuing PlannerTab lesson/assessment** next (the warm cadence finishes the file toward a <3k-LOC target), **then pivoting to `SettingsTab.jsx`**. Caveat (Claude): lesson/assessment are the cross-coupled blocks (shared `lessonPlan`/`generatedAssignment`/`generatedAssessment`, question-editing, publish/share modals) — they genuinely decentralize state rather than just move JSX, so they warrant their own brainstorm and are higher-risk than the calendar/tools/dashboard slices. The Code-Quality dimension will not tick to 8 on PlannerTab alone; broader de-concentration (SettingsTab, and revisiting App.jsx) is required.

**Honest note on the 3-model run:** Gemini's first invocation failed (untrusted-workspace, exit 55) and was re-run with `GEMINI_CLI_TRUST_WORKSPACE=true --skip-trust`; both Codex and Gemini then completed cleanly. No model failed-to-run in the final tally; the split is a genuine judgment difference, resolved conservatively.

---

# 2026-05-23 PlannerTab lesson + assessment extraction closeout (PR #463 + #465 + #467)

Wave 3 slices 4–6, the final and hardest part of the PlannerTab decomposition — the cross-coupled `lesson` and `assessment` mode blocks. Brainstormed via `superpowers:brainstorming`, planned via `superpowers:writing-plans` (3-PR plan), executed subagent-driven with two-stage review. Specs/plan: `docs/superpowers/specs/2026-05-22-plannertab-lesson-assessment-extraction-design.md` (+ plan). This closes the PlannerTab Code-Quality lever.

## What shipped

- **PR1 #463 — `useQuestionEditing` hook** (208 LOC). The shared question-editing cluster (4 state vars + 6 handlers) decentralized into `frontend/src/hooks/useQuestionEditing.js`; PlannerTab calls it **once** and forwards the bundle (single instance preserves cross-mode persistence). 5 audited inputs `{getActiveAssignment, setActiveAssignment, addToast, config, unitConfig}`; renderHook unit tests. The genuine state-decentralization win of this slice.
- **PR2 #465 — `PlannerLesson.jsx`** (2,200 LOC) — the ~2,189-line lesson JSX, 69 forwarded props.
- **PR3 #467 — `PlannerAssessment.jsx`** (1,633 LOC) — the ~1,621-line assessment JSX, 59 forwarded props.
- **PlannerTab.jsx: 3,019 (post-PR1) → 1,453 LOC.** **Cumulative Wave 3 (calendar + tools + dashboard + lesson + assessment + hook): 7,405 → 1,453 LOC (−80%).** PlannerTab is now a thin orchestrator that owns shared App-state forwarding, the mode-nav, the trailing modals, the hook call, and renders the five mode components.

## Design pivot recorded (3-model consensus)

The original spec's "move the lesson/assessment local state + handlers INTO the components" design was **invalidated at PR2 implementation time**: the lesson state is woven through code that *stays* in PlannerTab — a subject-change `useEffect` writes `assignmentQuestionCounts`, and the globally-rendered Save Lesson modal uses `showSaveLesson`. Moving that state into the conditionally-rendered component breaks those staying consumers and resets state on mode-switch. This was a genuine design fork, decided by **3-model consultation (Claude + Codex + Gemini, unanimous on Option A)**: **pure-JSX presentational extraction** — move only the JSX, forward everything as props, keep all state/handlers/effects/modals in PlannerTab (the PlannerDashboard pattern at scale). Behavior-preserving; large flat prop surface accepted (prop-grouping deferred to preserve verbatim parity). Recorded in the spec's "Design correction" section.

## Audit-method lessons (honest)

The lesson slice exposed three scan pitfalls — each caught by the deterministic **free-variable scan** before any bug shipped, not by hand-reading:
- The hook interface was corrected twice (9→10→5 inputs) — comment pollution, then a region-scan overshoot into the adjacent doc-upload cluster.
- The prop-window for the destructure parse was cut off at the wrong line (94 vs the real 98), hiding ~40 real props as false "free variables".
- A `handleDocUpload` span computation overshot to EOF, polluting the footprint with assessment/dashboard props.
The durable takeaway: derive prop sets programmatically, and gate every component on a free-variable scan to **zero** undefined identifiers + signature==call-site equality. The deterministic gates (free-var scan, byte-for-byte JSX parity, full-suite, two-stage review) held despite the hand-scan slips.

## Verification

Per PR: Vite build clean, byte-for-byte normalized-JSX parity (lesson 2,189; assessment 1,621 — zero-diff), free-var scan zero, signature==call-site, full frontend suite **195 passed**, all 9 CI checks green, both spec-compliance and code-quality reviews passed. No `App.jsx` or backend change in any of the three PRs.

## Follow-ups filed

- **#464** — pre-existing `config.globalAINotes` regen bug surfaced (not introduced) by the hook extraction; deferred because the fix changes the regenerate request payload (behavior change).
- **#466** — dead setter-props in PlannerTab's destructure after the extractions; cross-cutting (App + PlannerTab), deferred to a dedicated cleanup PR.

## Next step

The PlannerTab Code-Quality lever is closed (−80%). Per the post-Wave-3 re-score, PlannerTab alone does not move Code Quality 7 → 8 — the remaining concentrated-complexity levers are **`SettingsTab.jsx` (6,534 LOC)** and **`App.jsx` (7,144 LOC)**. A re-score is worth running now that PlannerTab is a 1.5k orchestrator, but the conservative expectation is it holds at 7 until SettingsTab/App.jsx are also de-concentrated. The dead-setter-props cleanup (#466) is a small in-PlannerTab follow-up.

---

# 2026-05-23 Post-full-PlannerTab-decomposition re-score (Code Quality 7 → 8)

3-model reconciled re-score after the COMPLETE PlannerTab decomposition (Wave 3 slices 1–6: calendar/tools/dashboard/lesson/assessment + the `useQuestionEditing` hook all shipped and merged). Supersedes the 2026-05-22 re-score, which was taken mid-decomposition (PlannerTab 5,322 LOC, lesson/assessment still inline) and held at 7. Method: Claude (controller, first-hand), Codex (`codex exec`), Gemini (`gemini -p`); conservative-floor reconciliation.

| Model | Code Quality | Recommendation |
|---|---|---|
| Claude | 7 (dissent) | SettingsTab; floor holds on multi-file concentration |
| Codex | 8 | SettingsTab — largest remaining tab-level god-file |
| Gemini | 8 | SettingsTab — decompose into focused sub-tabs |
| **Reconciled** | **8** | SettingsTab.jsx next |

## Verdict: Code Quality 7 → 8. Overall 7.8 → 7.9.

The prior re-score's stated cap reason — "PlannerTab still carries inline lesson/assessment blocks" — is now closed with verified file:line evidence: `PlannerTab.jsx` 7,405 → 1,453 LOC (−80%), a thin orchestrator that renders five focused, independently-tested components (PlannerCalendar 735, PlannerTools 840, PlannerDashboard 577, PlannerLesson 2,200, PlannerAssessment 1,633) + `useQuestionEditing` (208). The single largest and most-cited frontend god-file is fully de-concentrated. Two models independently scored 8 on this basis; per the conservative floor's "strong disconfirming evidence" exception (the cap's specific cited reason is verifiably closed), the dimension moves to 8 — the mirror of how the floor resolves DOWN when the lower score's basis stands (e.g. the 2026-05-11 Architecture 7).

**Claude's dissent (recorded):** Claude held 7 — the concentration is multi-file and the LOC was largely relocated into sibling components (PlannerLesson/PlannerAssessment are themselves 1.6–2.2k LOC) rather than eliminated, with App.jsx (7,144), SettingsTab.jsx (6,534), and assignment_grader.py (5,344) untouched. This is exactly why the reconcile stops at 8, not 9.

## Path to 9 (remaining concentrated-complexity levers)

Unanimous next lever: **SettingsTab.jsx (6,534 LOC)** — the largest remaining tab-level frontend god-file, cleanly decomposable into 7 focused section components (general / grading / ai / classroom / privacy / billing / resources — the same `settingsTab === "X"` pattern as PlannerTab's mode blocks). After that: App.jsx (7,144 — the app shell, already cut 57% in prior work), assignment_grader.py (5,344), and the backend route god-files (planner_routes.py 4,611, student_portal_routes.py 3,686). Reaching 9 needs broad de-concentration across these, not any single file.

## Honest note

Both Codex and Gemini completed cleanly (Gemini via `GEMINI_CLI_TRUST_WORKSPACE=true --skip-trust`). The 7-vs-8 split is a genuine judgment difference — does completely closing the single largest god-file warrant the point while others remain — resolved UP to 8 because the prior cap's specific reason is verifiably closed and two independent models concur with file:line evidence.

---

# 2026-05-23 SettingsTab decomposition closeout (Wave 4, PRs #471–#475)

Wave 4 — the `frontend/src/tabs/SettingsTab.jsx` Code-Quality concentrated-complexity lever, the **unanimous next target** named by the 2026-05-23 post-full-PlannerTab re-score (`#469`) above. Brainstormed via `superpowers:brainstorming` (per-section pure-forward shape, 3-model-validated no-hook), planned via `superpowers:writing-plans` (5-PR plan), executed subagent-driven with two-stage review per PR. Spec/plan: `docs/superpowers/specs/2026-05-23-settingstab-decomposition-design.md` (+ matching plan), shipped as docs PR #470.

## What shipped

Seven focused, independently-tested **presentational** components extracted from the `settingsTab === "X"` section blocks, **pure-forward**: move ONLY the section JSX, forward every referenced value/handler/ref as a prop (programmatic derivation so signature == call site), keep ALL state/effects/modals declared in SettingsTab.

- **PR1 #471** — `SettingsGeneral` (19 props), `SettingsGrading` (4), `SettingsBilling` (9). 6,534 → 5,717 LOC (−817).
- **PR2 #472** — `SettingsAI` (12 props): grading/assistant model select, ensemble config, OpenAI/Anthropic/Gemini API keys, global AI notes. 5,717 → 4,957 (−760).
- **PR3 #473** — `SettingsPrivacy` (15 props): student-data export/import, student history + detail modal, retention/trusted-writers; forwards `importFileRef`. 4,957 → 3,948 (−1,009).
- **PR4 #474** — `SettingsResources` (10 props): support-doc upload list + new-doc form; forwards `supportDocInputRef`. 3,948 → 3,773 (−175).
- **PR5 #475** — `SettingsClassroom` (99 props, ~2,298 lines, the largest section): periods/roster, Clever + OneRoster + LTI SIS integrations, accommodations, parent contacts; forwards 4 parent-body closures (`activeProvider`, `isCleverUser`, `periodInputRef`, `parentContactsInputRef`). 3,773 → 1,576 (−2,196).
- **Cumulative: `SettingsTab.jsx` 6,534 → 1,576 LOC (−76%).** Now a thin orchestrator: tab-nav + the 7 section conditionals + retained state/effects + the cross-section modals. Component LOC: General 376, Grading 256, Billing 248, AI 784, Privacy 1,036, Resources 197, Classroom 2,307. Frontend suite 195 → 202 (one smoke test per component).

## Extraction shape (pure-forward, behavior-preserving)

Option A pure-forward — the proven `PlannerLesson`/`PlannerDashboard`/`PlannerAssessment` pattern. SettingsTab was the cleanest variant of it (no section-local state needing move-in for the small sections, no trailing modals tied to a single section, so no shared hook was required — confirmed in the brainstorm by 3-model validation). Parent-body refs and derived consts referenced by a section (`importFileRef`, `supportDocInputRef`, `activeProvider`, `isCleverUser`, `periodInputRef`, `parentContactsInputRef`) are **forwarded as props by identity**; their declarations stay in SettingsTab so any staying consumers and the cross-section modals are unaffected.

## Why this was safe (deterministic gates, every slice)

- **Byte-for-byte whitespace-normalized JSX parity** for every section (the spec reviewers independently confirmed several were byte-for-byte identical, stronger than normalized).
- **Free-variable scan to zero** undefined identifiers + an explicit **parent-body-closure cross-check** (every referenced closure verified forwarded, none left free).
- **Neighbor-context dead-prop gate** — added mid-series after the PR4 review caught a string-literal false-forward; it removed props the regex deriver matched only in prose/strings/comments: `periods` (PR2 prose), `rubric` (PR4 `value="rubric"`), and `config`/`periods`/`rosters` (PR5 — the section renders `sortedPeriods`). The assembler was also hardened to auto-forward parent-body closures and to recognize `function(...)` callback params.
- Per-component Proxy-`makeProps` **smoke test**; Vite **build**; **full frontend suite** (202); all **9 CI checks**; Playwright **E2E**.
- **Two-stage subagent review per PR** (spec-compliance, then code-quality); all 5 PRs approved with no Critical/Important issues. Each PR re-audited its section boundaries (line numbers drift as prior slices merge) and branched off freshly-merged `main`.

## Follow-ups (recorded, out of scope)

- **`SettingsClassroom` further sub-division** — at 2,307 LOC / 99 props it is now the strongest remaining single-component candidate; it cleanly contains five independent sub-panels (Clever / OneRoster / LTI / periods+roster / accommodations) that share almost no props. Splitting them would shrink each child's prop list and roughly halve the largest file, but it would break this series' byte-for-byte parity guarantee, so it is sequenced as its own later slice.
- **Pre-existing latent no-op** at `SettingsPrivacy.jsx` (`(status.results || [])` where `status` resolves to the browser global `window.status`, so the trusted-writers name-lookup is always a silent no-op) — surfaced in the PR3 spec review, **byte-identical to base**, deferred (fixing it would have broken PR3 parity).

## Dimension effect

Per established convention, **no dimension score is asserted in this closeout**; a 3-model reconciled re-score is the deferred judgment step and appends as its own dated section. The `#469` re-score put **Code Quality at 8** with SettingsTab as the named lever; this **closes that lever**. The honest question the re-score will weigh: does de-concentrating the largest remaining tab-level frontend god-file (6,534 → 1,576, −76%, into 7 tested components) move Code Quality **8 → 9**, or hold at 8 given that `App.jsx` (7,144), `assignment_grader.py` (5,344), and the backend route god-files (`planner_routes.py` 4,611, `student_portal_routes.py` 3,686) remain concentrated — reaching 9 needs broad de-concentration across these, not any single file.

---

# 2026-05-23 Post-SettingsTab-decomposition 3-Model Reconciled Re-Score

The deferred judgment step the SettingsTab closeout (above) said would follow. Codex, Gemini, and Claude each re-scored independently against the 2026-05-23 post-full-PlannerTab baseline (Code Quality 8) at the post-SettingsTab state (`SettingsTab.jsx` 1,576 LOC, a thin orchestrator rendering all 7 extracted `Settings*` components). Method: Claude (controller, first-hand), Codex (`codex exec`), Gemini (`gemini -p`, `GEMINI_CLI_TRUST_WORKSPACE=true --skip-trust`). Conservative-floor reconciliation: on a split the lower score wins unless a model presents strong disconfirming file:line evidence.

| Model | Code Quality | Recommendation |
|-------|--------------|----------------|
| Claude | 8 (floor) | App.jsx — broad multi-file 9-bar unmet (App.jsx + grader untouched) |
| Codex | 8.5 | App.jsx — largest frontend file, clearest remaining UI concentration |
| Gemini | 8.5 | App.jsx — decompose the modal state machine / global handlers |
| **Reconciled** | **8 (held — a high-8 on the cusp of 8.5)** | App.jsx next |

## Verdict: Code Quality holds at 8 (conservative floor). Overall unchanged at 7.9.

All three models verified the live code with their own shell commands and **unanimously agree it is not a 9**. The split is only 8 vs 8.5, resolved DOWN to 8 by the same conservative-floor discipline applied in the 2026-05-22 re-score (Codex 7.5 / Gemini 8 / Claude 7 → reconciled 7): the higher value is credited only when concretely and unanimously grounded, and here it is neither unanimous nor does it cross a tier.

**Verified progress (all three, file:line):**
- `frontend/src/tabs/SettingsTab.jsx` 6,534 → 1,576 LOC (−76%); imports all 7 `Settings*` components at lines 5–11; all 7 section render branches delegated (`general` 300/301, `grading` 325/326, `ai` 335/336, `classroom` 355/356, `privacy` 460/461, `billing` 481/482, `resources` 496/497).
- **Both** of the two largest frontend tab god-files are now de-concentrated: `PlannerTab.jsx` 1,453, `SettingsTab.jsx` 1,576. The two named frontend Code-Quality levers are closed.
- Seven focused, independently-tested components (General 376, Grading 256, Billing 248, AI 784, Privacy 1,036, Resources 197, Classroom 2,307), each with a smoke test.

**Why it holds at 8, not 9 (unanimous grounds):**
- The `#469` re-score set the explicit 9-bar as "broad de-concentration across these [App.jsx 7,144, SettingsTab, assignment_grader.py 5,344], **not any single file**." SettingsTab is now done, but it is one of the three named items — `App.jsx` (7,144, now the single largest frontend file, ~191 hooks) and `assignment_grader.py` (5,344) are wholly untouched, plus the backend route god-files (`planner_routes.py` 4,611, `student_portal_routes.py` 3,686).
- Complexity was partly **relocated, not eliminated**: `SettingsClassroom.jsx` is itself 2,307 LOC with a 99-prop signature (`SettingsClassroom.jsx:6`) — a "sub-god-file" (Gemini), recorded in the closeout as the strongest remaining sub-division candidate.

**The 8.5 case (Codex + Gemini, recorded):** both credited the closure of the *second* major frontend god-file as a genuine half-step beyond the state when 8 was assigned (when SettingsTab was still a 6,534 monolith). This is real, verified progress; under the conservative floor it lands the dimension as a high-8 trending toward the next tier, not a held-flat 8 — the mirror of how the 2026-05-22 re-score recorded a "near-8 on the cusp" while holding at 7.

## Path to 9 (remaining concentrated-complexity levers)

**Unanimous next lever: `frontend/src/App.jsx` (7,144 LOC)** — now the single largest source file in the repository and the clearest remaining UI concentration point (a large modal state machine + global handlers; ~191 `useState`/`useEffect`). After that: `assignment_grader.py` (5,344) and the backend route god-files (`planner_routes.py` 4,611, `student_portal_routes.py` 3,686). Reaching 9 still needs broad de-concentration across these, consistent with every prior re-score — App.jsx is the highest-value single next step toward it.

## Honest note

Both Codex and Gemini completed cleanly and independently landed on 8.5 with concrete file:line evidence and the same App.jsx recommendation; Claude (controller) held the 8 floor on the explicit multi-file 9-bar. No model scored 9. The reconciled 8 is therefore a held dimension with a verified upward trajectory, not a stall: two of the three named frontend/concentration items the original cap cited (PlannerTab, then SettingsTab) are now closed, and the third (App.jsx) plus the backend grader/route files are the named path to 9.

# 2026-05-24 Post-Wave-5 (backend route de-concentration) + App.jsx + docs 3-Model Reconciled Re-Score

The deferred judgment step for **Wave 5** (the `student_portal_routes.py` backend de-concentration, PRs #493–#499), weighed together with the App.jsx decomposition (PRs #488–#490) and the Documentation lever (PR #491) shipped in the same session. Codex, Gemini, and Claude each re-scored independently against the 2026-05-23 Post-SettingsTab baseline (Code Quality 8, Documentation 7, overall 7.9). Method: Claude (controller, first-hand), Codex (`codex exec`), Gemini (`gemini -p`, `GEMINI_CLI_TRUST_WORKSPACE=true --skip-trust`). Conservative-floor reconciliation: on a split the lower score wins unless a model presents strong disconfirming file:line evidence.

| Model | Code Quality | Documentation | Next lever |
|-------|--------------|---------------|------------|
| Claude (first-hand) | 8.5 | 8 | `planner_routes.py` |
| Codex | 8.5 | 8 | `planner_routes.py` |
| Gemini | 8.5 | 8 | `planner_routes.py` |
| **Reconciled** | **8 → 8.5** | **7 → 8** | `planner_routes.py` |

## Verdict: Code Quality 8 → 8.5, Documentation 7 → 8. Overall 7.9 → ~8.1.

**Unanimous, no tie-break required.** All three models independently verified the live code with their own shell commands and landed on the same two numbers and the same next lever. This is the first re-score in the program with a unanimous half-step on Code Quality *and* a full-step on Documentation — the largest combined aggregate uptick in recent waves, and the point at which the holistic overall crosses 8.0.

**Verified progress (all three, file:line):**
- **Wave 5 (headline): `backend/routes/student_portal_routes.py` 3,686 → 2,302 LOC (−37.5%)**, behavior-preserving, into **five new Flask-free, independently-unit-tested service modules** (`student_mastery` 493, `student_remediation` 396 incl. the two `post_remediate` resolvers, `student_progress_reports` 197, `student_gradebook` 315, `student_comparison` 225 — ~1,626 service LOC + ~650 new test LOC). Seven PRs, each byte-identical/behavior-equivalence verified, gated by the existing endpoint test nets + new per-service unit tests + the 9 CI checks, two-stage reviewed (every nit fixed: test gaps, weak assertions, dead code, orphaned imports). The progress-rank cache asymmetry was preserved via a `(payload, cacheable)` contract; submission-detail via `(payload, err)`; the `post_remediate` generation/ThreadPool/OpenAI orchestration was deliberately left route-side (circular-import surface + thread semantics).
- **`frontend/src/App.jsx` 7,144 → 4,810 LOC (−33%)** via extracted domain hooks + components (PRs #488–#490 + earlier).
- **Documentation: from essentially no architecture/API docs to a verified onboarding suite** — `docs/API_REFERENCE.md` (308 endpoints, code-derived; live route scan independently confirmed 308; auth column distinguishes Teacher / School Admin / District Admin / Clever session / Public, with the District-Admin and School-Admin surfaces corrected during PR #491's accuracy pass) + `docs/ARCHITECTURE.md` (stack, repo layout, frontend shell, backend blueprints/services/grading engine, two publish paths, persistence, local dev, testing pyramid, CI).

**Why Code Quality is 8.5, not 9 (unanimous grounds):**
- The 9-bar set by prior re-scores is "broad de-concentration across these — App.jsx, SettingsTab, `assignment_grader.py`, `planner_routes.py`, `student_portal_routes.py` — not any single file." Four of the named items are now de-concentrated (PlannerTab, SettingsTab, App.jsx −33%, student_portal_routes −37.5%), which is genuinely broad — hence the half-step up from the held-8.
- But two central concentrations remain: **`backend/routes/planner_routes.py` (4,611 LOC, untouched)** — the last backend route god-file — and **`assignment_grader.py` (5,344 LOC, deliberately off-limits)**. `App.jsx` is also still 4,810. A clean 9 requires the planner-routes split; the grader is a separate, user-gated lever.

**Why Documentation is 8, not higher (Codex caveat, recorded):** a handful of API-reference `Purpose` cells are blank or truncated (e.g. a few Student-Accounts rows). The suite is comprehensive, accurate, and onboarding-grade — clearly an 8 vs the prior ~no-docs state — but per-row purpose completeness and any deeper per-module/sequence docs are the path beyond 8.

## Path to Code Quality 9 (remaining concentrated-complexity levers)

**Unanimous next lever: `backend/routes/planner_routes.py` (4,611 LOC)** — the last backend route god-file, route-heavy and tied to generation/export/post-processing flows. The same `backend/services/` extraction pattern proven across Wave 5 applies: move planner generation, export, and post-processing helpers into Flask-free services. After that, `assignment_grader.py` (5,344, off-limits pending explicit user steer) and the still-large `App.jsx` (4,810) are the remaining items; reaching 9 needs the planner-routes split at minimum, consistent with every prior re-score.

## Honest note

All three models completed cleanly and independently, verified the live code (Codex and Gemini both ran the 35 new service unit tests green), and unanimously landed on Code Quality 8.5 and Documentation 8 with the same `planner_routes.py` recommendation — no model scored Code Quality 9. The reconciled result is therefore a genuine, verified two-dimension uplift (the first to carry the overall across 8.0), not a stall: the headline Wave 5 lever closed the largest backend route god-file outside the grader, and the named path to 9 (planner_routes) is now the single clear next step. This dated section closes Wave 5 (the `2026-05-23-backend-route-deconcentration` spec + plan) and the Documentation lever.

---

# 2026-05-24 Post-Wave-6 (`planner_routes.py` de-concentration) 3-Model Reconciled Re-Score — **Code Quality 8.5 → 9**

The deferred judgment step for **Wave 6** (the `backend/routes/planner_routes.py` de-concentration, PRs #502–#508 + #510–#518; spec/plan #501). This is the lever the prior (Post-Wave-5) re-score unanimously named as *"the single clear next step"* and *"a clean 9 requires the planner-routes split."* Codex, Gemini, and Claude each re-scored independently against the 2026-05-24 Post-Wave-5 baseline (Code Quality 8.5). Method: Claude (controller, first-hand), Codex (`codex exec`), Gemini (`GEMINI_CLI_TRUST_WORKSPACE=true gemini -p --yolo`). Conservative-floor reconciliation (lower score wins on a split unless strong disconfirming file:line evidence).

| Model | Code Quality | Path-to-9 lever delivered? | Next lever |
|-------|--------------|----------------------------|------------|
| Claude (first-hand) | 9.0 | yes | `assignment_grader.py` (user-gated) |
| Codex | 9.0 | yes | `assignment_grader.py` |
| Gemini | 9.0 | yes | `assignment_grader.py` |
| **Reconciled** | **8.5 → 9.0** | **yes** | `assignment_grader.py` |

## Verdict: Code Quality 8.5 → 9.0. Overall ~8.1 → ~8.2.

**Unanimous, no tie-break required.** All three models independently verified the live code with their own shell commands (each ran the new planner service tests — Codex `17 passed` with a writable HOME, Gemini `17/17 passed`; Codex also ran `compileall` + an import-graph check confirming one-way route→service edges and no service→route cycle) and landed on the same number and the same next lever. This is the first re-score in the program to reach Code Quality 9.

**Verified progress (all three, file:line):**
- **Headline: `backend/routes/planner_routes.py` 4,611 → 2,154 LOC (−53%)**, behavior-preserving, into Flask-free `backend/services/planner_*` modules (~4,200 service LOC): `planner_generation.py` (1,595 — all 5 generation handlers: brainstorm_lesson_ideas, generate_lesson_plan, generate_assessment, generate_assignment_from_lesson, regenerate_questions), `planner_export.py` (1,531), `planner_standards.py` (434 — rewrite_for_alignment, align_document_to_standards, extract_text_from_upload), `planner_study_aids.py` (213), `planner_assessments.py` (219), `planner_content_tools.py` (67), `openai_context.py` (15). 17 PRs total; the route handlers are now thin delegators (parse → resolve `g`/API key → delegate → `jsonify`).
- **Services are genuinely Flask-free** — all three independently confirmed zero `flask`/`request`/`g`/`jsonify` references in the planner service modules; context (user_id, OpenAI key, the `_get_openai_context` tuple) is resolved route-side and passed in. One-way import graph (route → services), no cycle.
- **Behavior preservation was mechanically enforced, not asserted:** every slice was characterization-test-first (route char tests baselined green BEFORE extraction + direct service-contract tests), prompt f-strings verified **byte-identical** via AST string-literal compare (an AST-aware dedent that skips multi-line-string interiors — a naive line dedent silently corrupts embedded JSON examples; caught and fixed in slice 11a), F401/F841 cleaned in each touched function, and two-stage reviewed (spec-compliance first-hand + a code-quality subagent on every PR — all APPROVE). Warts preserved verbatim and pinned by tests: the brainstorm/lesson-plan mock-fallback at 200; generate_assessment's discard of the post-process extra usage (`assignment, _ = ...`) vs generate_assignment's merge; the essay/project early-return that omits usage/method.

**Why Code Quality is 9, not higher (unanimous grounds):**
- The prior baseline's 9-bar was, explicitly and unanimously, "the planner-routes split" — the last de-concentratable backend route god-file. Wave 6 delivered exactly that (−53%, behavior-preserving, into independently-tested Flask-free services). With PlannerTab, SettingsTab, App.jsx (−33%), student_portal_routes (−37.5%), and now planner_routes (−53%) all de-concentrated, the broad-de-concentration bar the program set for 9 is met.
- **Why not 9.5+:** two large concentrations remain — **`assignment_grader.py` (5,344 LOC, the single largest file, deliberately off-limits pending explicit user steer)** and **`frontend/src/App.jsx` (4,810 LOC)**. `planner_routes.py` itself is still 2,154 LOC (export/CRUD handlers + the deferred export-builder render). The path beyond 9 runs through the grader (the "final boss," user-gated) and the residual frontend god-files.

## Path beyond 9 (remaining concentrated-complexity levers)

**Unanimous next lever: `assignment_grader.py` (5,344 LOC)** — now the undisputed largest backend file, currently off-limits pending explicit user steer. Its decomposition (separating the core scoring engine from I/O and route-shim logic, preserving all 18 AI grading factors) is the backend path to 9.5+. Parallel frontend levers: the residual `App.jsx` (4,810) and `SettingsClassroom.jsx` (~2,307). Lower-priority planner follow-ups (deferred, recorded): the export builders (`export_lesson_plan`/`export_assessment`/`export_generated_assignment` — a docx-render extraction entangled with the Flask-`g`-bound `_save_grading_config_for_export`, which stays route-side) and a route-side dead-var sweep (CI-invisible since ruff selects only T20).

## Honest note

All three models completed cleanly and independently, verified the live post-Wave-6 code (each ran the new planner service tests green), and unanimously scored Code Quality 9.0 with the same `assignment_grader.py` next lever — the first 9 in the program. This is a genuine, earned full-step: the headline lever was the one every prior re-score named as gating, and it was delivered behavior-preserving under a characterization net with byte-identical prompt verification, not merely "files moved." The Overall ticks from ~8.1 to ~8.2 (a half-step on one of ~10 dimensions). The honest ceiling note stands: a 9.5+ requires opening the `assignment_grader.py` gate (user decision) and the residual frontend god-files. This dated section closes Wave 6 (the `2026-05-24-planner-routes-deconcentration` spec + plan).

---

# 2026-05-24 Post-Wave-7 (`assignment_grader.py` decomposition) 3-Model Reconciled Re-Score — **Code Quality 9.0 → 9.2**

The deferred judgment step for **Wave 7** — the decomposition of `assignment_grader.py`, the 5,344-LOC grading god-module that every prior re-score named as the gating "final boss" (user opened the gate this session). Phase A (pure helpers + file readers + roster/CSV export, PRs #520–#542) and Phase B (the LLM-coupled scoring core, PRs #543–#547) shipped behind a deterministic SDK-fake **golden net** (#541). Codex 5.5 (high), Gemini, and Claude each re-scored independently against the Post-Wave-6 baseline (Code Quality 9.0). Method: Claude (controller, first-hand), Codex (`codex exec -c model_reasoning_effort=high`), Gemini (`GEMINI_CLI_TRUST_WORKSPACE=true gemini -p --yolo`). Conservative-floor reconciliation (lower score wins on a split unless strong disconfirming file:line evidence).

| Model | Code Quality | Highest-leverage next step |
|-------|--------------|----------------------------|
| Claude (first-hand) | 9.5 | split `grade_assignment`; extract CLI/email |
| Codex 5.5 (high) | 9.2 | split `grade_assignment` (the one change closest to 9.5) |
| Gemini | 9.2 | decompose the `grade_assignment` God Function; extract CLI |
| **Reconciled** | **9.0 → 9.2** | **split `grade_assignment` into pipeline phases** |

## Verdict: Code Quality 9.0 → 9.2. Overall ~8.2 → ~8.3.

**Codex and Gemini independently converged on 9.2; Claude's 9.5 was reconciled down to the floor.** All three verified the live code with their own shell commands (Codex + Gemini both ran `tests/test_grader_golden.py` → `12 passed, 1 skipped`; Codex also ran the e2e grading pipeline → `2 passed`).

**Verified progress (all three, file:line):**
- **Headline: `assignment_grader.py` 5,344 → 658 LOC (−88%)** — the largest single-file reduction in the program. It is now a thin facade: CLI/email orchestration (`run_grading`, `save_emails_to_folder`, `create_outlook_drafts`) + re-export shims. The entire LLM-coupled scoring core moved into focused Flask-free `backend/services/` modules: `grading_models.py` (schemas + `TokenTracker` + `MODEL_PRICING`), `grading_leaves.py` (`grade_per_question`, `detect_ai_plagiarism`, `generate_feedback`, `_translate_feedback`), `grading_pipeline.py` (`grade_multipass`, `grade_assignment`, `grade_with_ensemble`, `grade_with_parallel_detection`), plus `writing_style`, `writing_profile`, `grader_text_prep`, `grading_prep`, `grader_json`, `submission_parsing`, `grader_export`, `grader_roster`.
- **The keystone (all three praised it): the SDK-fake golden net** (`tests/grading_fakes.py` + `tests/test_grader_golden.py`, 12 active goldens). It patches the 3 RAW SDK entrypoints with provider-shaped, thread-safe, content-matched fakes and runs the REAL grading functions — pinning exact scores, token counts (incl. the gpt-4o feedback upgrade), blank short-circuit, the `.parsed`-None fallback contrast, and provider routing. Gemini: "the single most important quality improvement in this wave… you've frozen the behavior of the most volatile part of the system." Codex: "excellent characterization coverage."
- **Behavior preservation was mechanically enforced:** every slice AST-verified function-source byte-identical to `origin/main` modulo mechanical `print()`→`_logger.*`; `ruff --select F821` used to statically confirm zero undefined names BEFORE runtime; re-export shims (explicit `as`, mypy no_implicit_reexport) keep all callers + mock-patch targets resolving; an AST importer-scan (not single-line grep) governed which "orphaned" imports were safe to prune vs kept as test re-exports. A latent test-quality bug class was caught & fixed: patches of internal seams on `assignment_grader` became AttributeError or SILENTLY VACUOUS after the move — all repointed and re-verified the mocks actually fire.

**Why Code Quality is 9.2, not 9.5 (unanimous grounds):** the god-*module* is gone, but a **second-order god-*function*** remains — `grade_assignment` is ~1,138 LOC inside the 2,017-LOC `grading_pipeline.py`, still mixing provider setup, extraction policy, prompt construction, response parsing, scoring caps, rubric weighting, ELL translation, writing-profile updates, audit payloads, and error recovery. The 658-LOC facade also still bundles a ~206-LOC CLI runner + email side effects.

## Path beyond 9.2 (unanimous)
**To 9.5:** (1) split `grade_assignment` into named pipeline phases (provider/client resolution → text/image extraction → prompt assembly → provider call → structured/text parse → deterministic post-processing → audit/token finalization), keeping the public function as orchestration only; (2) extract the CLI/email layer out of the facade (`grader_cli.py` / `grader_email_export.py`); (3) finish lint hygiene (done this closeout: `TokenTracker` F821 + `focus_files` F841) + move dynamic `_logger.info(f"…")` to lazy `%`-style. **To 10:** provider adapters behind one interface, typed request/result objects instead of wide dicts, pure scoring/cap functions with table-driven tests, retire the re-export shims (migrate internal imports to `backend.services.*`), and add low-cost live/contract SDK smoke tests behind `live`/`sdk` markers (mitigating golden-net stale-out + the Gemini-SDK-absent skip).

## New risk introduced (bounded, both external models)
The re-export shims create dual import paths + mock-patch ambiguity → mitigate by migrating internal callers off `assignment_grader` and deprecating the shims. The golden net can't model provider refusals / SDK drift / multimodal edge cases → mitigate with markered live contract tests + visible Gemini-skip in CI reporting.

## Honest note
This is a genuine, earned uplift on the program's hardest target: the grading "final boss" — 5,344 LOC, deliberately gated until this session — decomposed −88% behind a faithful golden net that runs the real functions, not merely "files moved." The two external models independently landed on the same number and the same next lever (`grade_assignment`), so the reconciled 9.2 is conservative and verified. Overall ticks ~8.2 → ~8.3. The honest ceiling note stands: 9.5 needs the intra-function decomposition of `grade_assignment` + the CLI/email split; 10 needs the provider-adapter/typed-result re-architecture. This dated section closes Wave 7 (the `2026-05-24-wave7-phaseb-grader-golden-net` spec + the #520–#547 PR series).

---

# 2026-05-25 Post-Wave-8 (`grade_assignment` + `grade_multipass` intra-function decomposition) 3-Model Reconciled Re-Score — **Code Quality 9.2 → 9.4**

The deferred judgment step for **Wave 8** — splitting the two remaining grading god-*functions* inside `backend/services/grading_pipeline.py` into named pipeline-phase helpers. This is lever (1) of the unanimous Post-Wave-7 path to 9.5. Codex 5.5 (high) and Claude verified the live code independently with their own shell commands; Gemini scored advisory (tool-less under `--skip-trust` — the no-`--yolo` safe mode; it could not run shell, so its vote rests on the facts verified first-hand by Claude and independently by Codex). Conservative-floor reconciliation.

| Model | Code Quality | Verification | Highest-leverage next step |
|-------|--------------|--------------|----------------------------|
| Claude (first-hand) | 9.4 | LOC + golden/snapshot/helpers green; AST byte-identity per slice | CLI/email split → `grader_cli.py` |
| Codex 5.5 (high) | 9.4 | ran golden/helpers `41 passed, 2 skipped` + snapshots `2 passed`; verified 405/361 LOC + 18 helpers | extract CLI/email layer |
| Gemini (advisory) | 9.4 | scored on verified facts (tool-less) | extract `run_grading`/email → `grader_cli.py` |
| **Reconciled** | **9.2 → 9.4** | | **extract the CLI/email layer from `assignment_grader.py`** |

## Verdict: Code Quality 9.2 → 9.4. Overall ~8.3 → ~8.4.

**Unanimous 9.4 — a half-step, not the full step to 9.5, on conservative grounds.** Wave 8 delivered the *primary* path-to-9.5 lever (the `grade_assignment` god-function split) but not all of the named co-requisites.

**Verified progress (all three, file:line):**
- **`grade_assignment`: 1,138 (Wave-7 baseline) → 405 LOC** at `grading_pipeline.py:1075` — cumulatively −64%; this session took it 711 → 405 via 6 behavior-preserving slices (`_detect_blank_submission`, `_analyze_submission_writing_style`, `_detect_fitb_assignment`, `_pre_extract_responses`, `_load_ell_language`, `_finalize_grading_result`).
- **`grade_multipass`: 432 → 361 LOC** at `grading_pipeline.py:1572` via `_apply_vocab_leniency` + `_multipass_perform_extraction`.
- **18 single-responsibility `_helpers`** now in `grading_pipeline.py`; helper unit tests in `tests/test_grading_pipeline_helpers.py` (28 tests). golden + snapshot + helpers = 43 passed, 2 skipped (Codex independently: 41+2).
- **Behavior preservation mechanically enforced per slice:** each extracted helper's statements **AST byte-identical** to its origin block (early-return helpers verified as wrap-only diffs with the dict literals preserved); golden + prompt-snapshot nets unchanged throughout; +unit tests for each now-testable helper. PRs #568–#575 (8 slices). 3 of the slices' contracts were chosen by full 3-AI consult (`_pre_extract_responses`, `_finalize_grading_result`, `_multipass_perform_extraction`).

**Why Code Quality is 9.4, not 9.5 (unanimous grounds):**
- The Post-Wave-7 path to 9.5 had three named items: (1) split `grade_assignment` into pipeline phases — **DONE**; (2) extract the CLI/email layer out of the facade — **NOT done**: `assignment_grader.py` is still 658 LOC with `run_grading` (~206), `save_emails_to_folder` (75), `create_outlook_drafts` (35); (3) lint hygiene — done in the Wave-7 closeout.
- `grade_multipass` (361 LOC) still bundles dense filtering + PASS-2 parallel grading + the AGGREGATE-SCORES/PASS-3/result-assembly tail (~150 LOC) in one flow.

## Path beyond 9.4 (unanimous next step)
**Extract the CLI/email layer from `assignment_grader.py`** into dedicated module(s) (e.g. `grader_cli.py` / `grader_email_export.py`), leaving the facade as compatibility re-exports + thin orchestration — this completes the one explicit Wave-7 path item still missing and makes 9.5 defensible. Secondary: finish `grade_multipass` (the AGGREGATE/PASS-3 tail → a kwargs `_finalize_multipass_result`, the PASS-2 block, a filtering-dedup with `_pre_extract_responses`). **To 10** (unchanged): provider adapters behind one interface, typed request/result objects instead of wide dicts, retire the re-export shims, live/contract SDK smoke tests.

## Honest note
A genuine, earned half-step on the program's hardest target. Wave 8 took the `grade_assignment` god-function from 1,138 → 405 LOC (cumulative −64%) behind the SDK-fake golden net + a prompt-snapshot net, with **every slice AST-verified byte-identical** to its origin block — not "files moved," but behavior frozen and mechanically proven. Two independent models (Claude first-hand, Codex via shell) verified the live code and the green nets; Gemini corroborated on those facts. The reconciled 9.4 is conservative: the primary 9.5 lever is delivered, but the unanimous discipline does not credit the full 9.5 while a named co-requisite (the CLI/email split) is outstanding and `grade_multipass`'s tail is still concentrated. Overall ticks ~8.3 → ~8.4. This dated section records Wave 8 (PRs #568–#575).

---

# 2026-05-25 Post-CLI/email-split 3-Model Reconciled Re-Score — **Code Quality 9.4 → 9.5** (first 9.5 in the program)

The deferred judgment step after completing the **CLI/email facade split** — the one named co-requisite the 9.4 re-score said was blocking the full step to 9.5. Codex 5.5 (high) and Claude verified the live code independently with their own shell commands; Gemini scored advisory (tool-less under `--skip-trust`). Conservative-floor reconciliation.

| Model | Code Quality | Verification | Highest-leverage next step (→10) |
|-------|--------------|--------------|----------------------------------|
| Claude (first-hand) | 9.5 | facade 332 LOC / 0 inline funcs; shim identity; golden+snapshot green | provider adapters |
| Codex 5.5 (high) | 9.5 | `rg "^def "` → 0 top-level funcs; golden `13 passed, 2 skipped`; verified each move's new home | provider adapters (extract OpenAI/Anthropic/Gemini exec + JSON-fallback/recovery from grade_assignment) |
| Gemini (advisory) | 9.5 | scored on verified facts | unify LLM provider routing (polymorphic adapter) |
| **Reconciled** | **9.4 → 9.5** | | **provider-adapter interface** |

## Verdict: Code Quality 9.4 → 9.5. Overall ~8.4 → ~8.5. **First 9.5 in the program.**

**Unanimous — the named blocker is closed.** The 9.4 re-score held the full step back *specifically* on the outstanding CLI/email split; it is now complete (PRs #577 pt.1, #578 pt.2a, #579 pt.2b).

**Verified progress (all three, file:line):**
- **`assignment_grader.py`: 658 → 332 LOC with ZERO top-level function definitions** — a pure re-export-shim layer (41 `# noqa: F401` shims) + the `__main__` CLI entry + user config + docstrings. The grading "god-file" anti-pattern is fully eliminated.
- `run_grading` (206 LOC) + its 3 CLI path constants → new `backend/services/grader_cli.py` (247 LOC), **AST byte-identical verbatim** move (prints kept; T20-exempt CLI; one-way service imports, no cycle).
- `save_emails_to_folder` + `create_outlook_drafts` → `grader_export.py`; `log_pii_sanitization` → `grader_text_prep.py`; `ASSIGNMENT_NAME` → `grading_models.py`. All re-exported from the facade so `backend/grading/pipeline.py` + the test route-callbacks keep resolving. Each move AST byte-identical (verbatim, or modulo the mechanical print→`_logger.info`).
- Verified: shim identity holds (`g.fn is service.fn`); `ruff check backend/` clean; 2285 grading/routes/email/export tests pass; golden + prompt-snapshot nets unchanged.

**Why 9.5 and not 10 (unanimous grounds):** concentration remains inside `grading_pipeline.py` (2,233 LOC): `grade_assignment` ~406 LOC and `grade_multipass` ~363 LOC each still own provider-specific execution (OpenAI/Anthropic/Gemini call + structured/text parse + JSON-fallback + error recovery). That is acceptable for 9.5 after the facade/CLI split, but not 10-level modularity.

## Path beyond 9.5 → 10 (unanimous next lever)
**Provider adapters behind one interface.** Extract the per-provider execution + response normalization (the OpenAI/Anthropic/Gemini switch-blocks + JSON-fallback/recovery) out of `grade_assignment`/`grade_per_question` into provider-specific grading adapters, so those functions become orchestration + policy/post-processing only. Then (from prior notes): typed request/result objects instead of wide dicts, retire the re-export shims (migrate internal callers to `backend.services.*`), and add live/contract SDK smoke tests behind markers.

## Honest note
A genuine, earned full step to the program's first 9.5. The CLI/email split took the grading facade from a 658-LOC god-file to a 332-LOC pure-shim layer with **zero inline logic**, completing the exact named co-requisite the 9.4 re-score recorded as the sole remaining blocker — `run_grading` moved AST byte-identical verbatim, the rest byte-identical modulo mechanical print→logger, all behind the green golden + prompt-snapshot nets. Two independent models (Claude first-hand, Codex via shell) verified the live state; Gemini corroborated. Reconciled 9.5 with unanimous agreement and the same next lever (provider adapters). Overall ~8.4 → ~8.5. This dated section closes the Wave-8 path-to-9.5 (PRs #568–#579).
