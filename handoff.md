# Handoff: 2026-05-14/16 — 19 PRs merged, tracker empty, dimensions re-scored 7.7/10, Clever→10 plan ready

> **State: GREEN / idle, with a clear next move.** Tracker empty, tree clean, GitNexus index fresh, dimension scorecard freshly re-measured by 3 independent models. The next actionable is **Task A of the Clever→10 plan** (a real, scoped correctness defect — not debt). Read §5 (disproved hypotheses) and §8 (heuristics) before touching e2e, frontend deploy, GitNexus, or Codex subagents.

## 1. Goal

Autonomous issue/PR sprint on Graider: clear the tracker, ship every fix through the 9 required CI checks, keep `handoff.md` honest, and answer "where are we on the quality dimensions" with measured (not assumed) data. **Achieved** — tracker empty, dimensions re-scored by Codex+Claude+Gemini and reconciled, next plan scoped.

## 2. TL;DR

- **19 PRs merged (#374–#393)**, all auto-deployed via Railway (+#373 closed by #374). Code: #374–#382, #386 (e2e), #388 (light-mode). Docs/ops: handoff refreshes, #384 plan-sweep, #390 GitNexus correction, #391 gitnexus stat block, **#393 dimension re-score + Clever→10 plan**.
- **Dimensions re-measured at HEAD `a25fcc5`'s parent `63384d3`** (3 independent code-verified models): reconciled **7.7/10** conservative floor (Codex 8.1 / Claude 8.1 / Gemini 7.8), baseline was 5.9. Measured backend coverage **63.37%**.
- **Tracker empty.** Working tree clean (only untracked `.claude/scheduled_tasks.lock`, `tests/reports/`). No in-flight branches.
- **GitNexus index fresh** (reindexed this session — the "reboot needed" claim was a debunked misdiagnosis; see §5.A). MCP `gitnexus_*` tools are DOWN this session (server stopped for the reindex); they auto-return next session.
- **Next move is decided & scoped:** Task A of `docs/superpowers/plans/2026-05-16-clever-compliance-10.md` — the only actual *defect* on the board (multi-enrolled Clever student can land in the wrong class session), as opposed to the debt everywhere else.
- Local `main` at **`a25fcc5`**.

## 3. Current state

### Dimension scorecard (shipped in #393, `a25fcc5`)

`docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` — March baseline preserved untouched; dated 3-model reconciled section appended.

| Dim | Mar-20 | Codex | Claude | Gemini | **Reconciled** |
|---|--:|--:|--:|--:|--:|
| Security | 5 | 8.6 | 9 | 8 | **8** |
| Error Handling | 7 | 8.3 | 8 | 8 | **8** |
| Code Quality | 5 | 7.2 | 7 | 7 | **7** |
| Architecture | 6 | 7.6 | 8 | 7 | **7** |
| Test Coverage | 6 | 8.4 | 8 | 8 | **8** |
| Documentation | 7 | 7.5 | 8 | 8 | **7** |
| Debugging/Obs | 5 | 8.0 | 8 | 8 | **8** |
| Data Integrity | 5 | 8.0 | 8 | 7 | **7** |
| Operational Safety | 5 | 8.5 | 8 | 8 | **8** |
| Clever Compliance | 8 | 8.7 | 9 | 9 | **9** |
| **Overall** | **5.9** | 8.1 | 8.1 | 7.8 | **7.7** |

Reconciliation rule: conservative floor — lower wins on splits unless strongly disconfirmed; unverifiable items uncredited; divergences documented in the doc (not averaged).

### PRs merged — code work (issue closures)

#374 hmac OAuth (#373) `ede4a5a` · #375 import_student_data scope (#339) `7c5cb73` · #376 sync_all_to_cloud (#341) `ee333a0` · #377 anthropic emit_json (#343) `e7d5a5c` · #378 503-not-500 (#355) `bfa9f1b` · #379 scan_submissions cov (#348) `55d7643` · #381 storage tenant-shard + dev-shim bypass (#353,#370p2) `b991ed0` · #382 transient classify (#224) `129a49f` · #386 multi-teacher e2e unskip+seed (#370p2) `52b08c3` · #388 light-mode Portal panel `879f8e7`. Docs: #380/#383/#385/#387/#389/#390/#391/#392/#393.

### Plans

`2026-05-16-clever-compliance-10.md` — **NOT STARTED**, on `main`. 4 recent plans CLOSED (#384). audit-major5 STATUS fixed (#392). ~65 older March/April plan docs have stale checkboxes but shipped features (janitorial only — not work).

### Follow-up issues filed

None. Nothing exceeded PR scope.

## 4. Local repro / verify-what-works

```bash
cd /Users/alexc/Downloads/Graider
git checkout main && git pull --ff-only          # expect HEAD = a25fcc5
git status --short                                # ONLY: .claude/scheduled_tasks.lock, tests/reports/
gh issue list --state open --limit 50             # expect 0 rows
grep -rl "test.skip" tests/e2e/specs/             # expect multi-teacher.spec.js ABSENT

# Dimension scorecard (the answer to "where are we"):
sed -n '/2026-05-16 Re-Score/,/Next concrete plan/p' \
  docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md

# Backend run (sentry_sdk error users hit = WRONG INTERPRETER, not a bug):
source venv/bin/activate && python -m backend.app   # from repo root

# GitNexus index health (FRESH — do NOT reboot, see §5.A):
python3 -c "import json;print(json.load(open('.gitnexus/meta.json'))['stats'])"
# ~ {'nodes':17586,'edges':49463,'embeddings':10653}; mtime 2026-05-16
```

## 5. Disproved hypotheses (READ — the highest-value section)

### A. "GitNexus needs a laptop reboot — zombie holds the LevelDB lock" — FALSE, propagated ≥4 handoffs
Live check: PID 67783 gone, zero `U`-state procs, `.gitnexus/lbug` is the 131 MB *data file* not a lock. It was the normal `gitnexus mcp` server; `kill -TERM` stopped it in 3 s (a real zombie ignores TERM — that's the test). Reindexed fine (~5 min, embeddings 7,331→10,653). `npx gitnexus analyze` **exits 1** on a benign `mutex lock failed` teardown crash *after* "indexed successfully" + meta.json write — trust meta.json, never the exit code. Corrected at root in #390/#391.

### B. "The Codex re-score agent is hung (~52 min, no completion notification)" — FALSE
It finished in **~3.6 min** (`completed_at`/`duration_ms:219046` in `~/.codex/sessions/2026/05/16/rollout-*.jsonl`). The **codex-rescue wrapper never relayed the completion notification**. Lesson: a missing agent notification ≠ a hung agent. To recover Codex output: find the newest `~/.codex/sessions/**/rollout-*.jsonl`, parse it (`json.loads` per line, payloads are `{timestamp,type,payload}`, final answer in `response_item`/`event_msg` text), `rfind("| Dimension")`. Do NOT cat the file (607 KB) or tail the subagent JSONL into context.

### C. multi-teacher.spec.js RED ([run 25964874545](https://github.com/nlev8/Graider/actions/runs/25964874545), 12/3)
❌ "just needs the X-Test-Teacher-Id header" / ❌ "Analytics nav button missing" (stack trace lied — button was behind a modal) / ❌ "another local-dev literal". ✅ Root cause via the **Playwright failure SCREENSHOT**: OnboardingWizard modal; sharded tenants unseeded. Fixed at workflow-seed layer (#386). GREEN [25965070445](https://github.com/nlev8/Graider/actions/runs/25965070445).

### D. "Clever Library certification ⇒ Clever Compliance is 10/10" — rejected
External cert tests Clever's bar, not the internal baseline gaps. Held at 9; the 2 finite gaps verified in-code and scoped (Task A/B). Don't inflate a dimension on an external badge.

### E. sentry_sdk `ModuleNotFoundError` — NOT a code bug
Pinned dep, installed in venv; user ran non-venv Python. Guarding the import would mask a misconfig (rejected).

## 6. Most likely remaining risks (nothing failing — forward-looking)

1. **Code Quality / Architecture concentrated complexity** (unanimous biggest lever) — App.jsx cut 57% but LOC *relocated*: PlannerTab.jsx 7,405 / SettingsTab.jsx 6,534 / assignment_grader.py 7,444 (≈ baseline). Two publish paths unconsolidated (~85 refs). Biggest *score* lift but multi-week + needs a design spike first (don't repeat the relocation mistake).
2. **Join-code dedup DB `UNIQUE` constraint unprovable from repo** — code catches `23505` but only the baseline migration exists. Race = mitigated-not-proven (caps Data Integrity at 7).
3. **~13 conditionally-skipped `frontend/e2e/*` specs** — unverified whether intentional; not tracked.
4. **Frontend deploy footgun** — must commit rebuilt `backend/static/` bundle (Railway = gunicorn-only, CI rebuilds but doesn't commit back).

## 7. Concrete next step

**Task A — multi-enrollment Clever student-SSO disambiguation.** The only actual *defect* (not debt) on the board. Plan: `docs/superpowers/plans/2026-05-16-clever-compliance-10.md` (Task A section, TDD steps written).

- Defect: `backend/routes/clever_routes.py:177-185` — `sb.table("students").select("*").eq("student_id_number", clever_id)` → first-row-wins when a Clever student exists under multiple teachers; self-documented as "not fully correct". Bounded to the student's *own* enrollments (NOT a cross-student leak — state severity accurately).
- TDD: RED test `tests/test_clever_student_session_multi_enrollment.py` (single-enrollment unchanged; >1 → `needs_class_selection` payload; finalize endpoint issues scoped session) → implement `students ⋈ class_students ⋈ classes` enumeration + `POST /api/clever/select-class` finalize + minimal picker in the Clever student callback (theme-aware `var(--glass-bg)`, never hardcode color — heuristic #6) → GREEN → PR → merge.
- Then **Task B** (per-district token resolution, backend-only, fast follow), then the **decomposition design-spike** (gate before the multi-week complexity sprint — define "reduces coupling" vs "relocates LOC").

## 8. Heuristics earned (carry forward)

1. **Verify-before-implement** for issues >2 wks: grep `Closes GH #N`/`fix(#N)` + run regression test. ~half of 16 were already-shipped.
2. **Bulk-flip + STATUS-stamp** to retro-close executed plans.
3. **`backend/app.py` does `load_dotenv(override=True)`** at import — `monkeypatch.setenv` loses; pass via header.
4. **`_supabase_raw` poisoning** — mock `_sb_load`/`_sb_save` whenever setting a fake `SUPABASE_URL`.
5. **e2e per-tenant sharding needs a per-tenant onboarding seed**; symptom (locator timeout on obscured button) lies — read the Playwright screenshot first.
6. **Frontend fixes must commit the rebuilt `backend/static/` bundle** (Railway gunicorn-only). Theme bugs = hardcoded color where `var(--*)` belongs (`--card-bg-light` dark-only; `--glass-bg` theme-aware).
7. **GitNexus needs no reboot** — `kill -TERM` the mcp PIDs → `analyze --embeddings` → ignore benign post-success exit-1 → verify meta.json. Re-verify carried-over operational claims with a live check before repeating them.
8. **`gh pr merge --auto` does NOT arm on an already-green PR** (no pending→green transition) — leaves `autoMerge=false`, PR sits MERGEABLE/CLEAN unmerged. Checks pending → `--auto` works; already green → direct `gh pr merge --squash`. Base merge ⇒ stacked PR goes `BEHIND` → `gh pr update-branch`.
9. **A missing subagent completion-notification ≠ a hung agent.** Codex finished in 3.6 min but the wrapper never relayed it; result was in `~/.codex/sessions/**/rollout-*.jsonl` (§5.B). Check the session file before declaring a Codex agent hung; don't block indefinitely.
10. **Don't inflate a scorecard dimension on external validation** (Clever cert ≠ internal 10). Conservative-floor reconciliation (lower wins on splits, uncredit unverifiable) beats averaging — and use ≥3 independent code-verifying models so one model's optimism can't set the record.

## 9. References

- PRs: [#374](https://github.com/nlev8/Graider/pull/374) → [#393](https://github.com/nlev8/Graider/pull/393); main `a25fcc5`
- Scorecard: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` (baseline + 2026-05-16 reconciled section)
- Next plan: `docs/superpowers/plans/2026-05-16-clever-compliance-10.md` (Task A → B; STATUS NOT STARTED)
- Issues closed: #217 #218 #224 #229 #234 #245 #247 #249 #253 #339 #341 #343 #348 #353 #355 #370 #373
- e2e debug runs: [25964874545](https://github.com/nlev8/Graider/actions/runs/25964874545) RED → [25965070445](https://github.com/nlev8/Graider/actions/runs/25965070445) GREEN
- Codex re-score session: `~/.codex/sessions/2026/05/16/rollout-2026-05-16T13-34-04-*.jsonl` (duration_ms 219046)
- Key files: `backend/routes/clever_routes.py:156-205` (Task A), `backend/clever.py:204` + `backend/api_keys.py` (Task B), `backend/storage.py:48-60`, `frontend/src/styles/globals.css`
- CLAUDE.md Rule #12 — committable artifact (measured scorecard + RED→GREEN + 10 heuristics qualify).
