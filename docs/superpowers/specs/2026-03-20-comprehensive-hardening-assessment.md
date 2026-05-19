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
