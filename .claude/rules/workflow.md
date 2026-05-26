# Workflow Discipline — How To Work Here

> **Read this before any multi-task subagent-driven execution.** It complements
> `CLAUDE.md` (project facts) and the `superpowers:*` skills (process guides) by
> codifying the local guardrails that prevent errors CI catches *expensively*
> from being caught cheaply, by you, before you push.
>
> CI is the **final** safety net (nine status checks gate every merge). This
> file is the **first** safety net — the per-task hygiene that keeps a red CI
> run from being your first signal.

---

## Per-Task Checklist (mandatory before marking a task done)

Run through this every time, even on "simple" tasks. The checklist is short
because each item exists because *something burned us before*.

- [ ] **TDD red** — failing test runs and fails for the right reason (not import error, not missing file).
- [ ] **TDD green** — same test runs and passes after the implementation.
- [ ] **`pytest -q --ignore=tests/load`** — FULL backend suite, not just files you named. (Inner-loop tests on named files are fast iteration; full-suite is the gate.)
- [ ] **`grep -rln '<every file you modified>' tests/`** — run any test that mentions your files. Catches cross-cutting consumers (contract tests, golden tests, observability pins).
- [ ] **Line-shift scan** — if you extracted, restructured, or inserted lines anywhere in an existing function, scan for tests that pin line numbers in your files (e.g., `test_sis_alerting`). Update pins explicitly with documenting comments.
- [ ] **Spec reviewer says ✅** — scope compliant: nothing missing, nothing extra. (Always dispatched BEFORE the code-quality reviewer.)
- [ ] **Code-quality reviewer says ✅** — `opus` for Class B (auth / identity / FERPA); `sonnet` is acceptable for Class A.
- [ ] **Reviewer issues handled** — every Minor/Important/Critical issue is either fixed inline OR captured as a tracked follow-up with a fix sketch (per CLAUDE.md Principle #11; never "I'll track it" without the sketch).
- [ ] **Commit scope clean** — only the files this task intentionally touched; no AGENTS.md/CLAUDE.md/handoff.md gitnexus noise, no `.claude/scheduled_tasks.lock`, no `flask_session/`.

---

## Hard Rules (non-negotiable)

1. **"Pre-existing failure" claims require proof.** Format:
   ```bash
   git checkout <base-sha> -- <files-under-test>
   source venv/bin/activate && pytest <failing-test> -v
   ```
   Show the pass/fail output. No proof → it's your failure until proven
   otherwise. (Cost of proof: ~10 seconds. Cost of misclassification: a red PR
   and a debug round-trip.)
2. **`pytest -q` is the floor, not the ceiling.** Per-task named-file pytest is
   for fast iteration; the full suite is the gate before marking done. Defer at
   your peril — Layer 3 catches what scoped review can't see.
3. **Line-shifting refactors require pin-test grep.** Function extraction, block
   restructure, or insertion of lines before existing code may move pinned
   `(file, line)` assertions out of their window. `grep -rn '"<your_file>"' tests/`
   and verify every pin still finds the intended capture.
4. **Class B ⇒ opus code-quality reviewer.** Mandatory, not optional. (Class B =
   auth / identity / FERPA right-to-delete / billing / anything outward-facing
   that's hard to roll back.)
5. **Subagent reports are evidence-bearing or rejected.** Actual stdout tails
   (test counts, lint output, build line). "All green" without numbers is not
   evidence — it's a vibe.
6. **Spec compliance review precedes code-quality review.** Always. A code that
   doesn't match the spec isn't worth reviewing for quality.
7. **No `gh pr merge --auto` with a review in flight on a Class B PR.** Per
   CLAUDE.md Principle #13: for Class B, merge manually AFTER the review returns
   clean.

---

## Anti-Patterns (the red-flag table)

These thoughts mean STOP and re-check:

| Thought | Reality |
|---|---|
| "This failure is pre-existing on main" (no proof shown) | It's yours until proven otherwise — proof takes 10 seconds. |
| "All tests in `{named files}` pass" | ≠ "all tests pass." Cross-cutting consumers stay invisible. |
| "The reviewer approved, ship it" | Reviewer reviewed the diff, not the full-suite impact. Run `pytest -q` anyway. |
| "Subagent says DONE, mark complete" | Spot-check the load-bearing claim. Did the test actually run? What were the counts? |
| "Refactor was behavior-preserving" | Line numbers are part of behavior to tests that pin them. |
| "Small follow-up — I'll file an issue" | If it's <15 min in this PR's scope, fix it now. Otherwise file WITH a fix sketch. |
| "Mock makes the test pass" | Did the mock prove behavior or just suppress the error? |
| "Code-quality reviewer ran — done" | Spec compliance review must come FIRST. |
| "I'll just commit the noise this once" | The gitnexus stats / lock files / flask_session noise is NEVER part of a feature commit. |
| "CI will catch it" | CI is the *final* safety net. Catching it locally is ~100x faster + cheaper. |

---

## Verification Loop (the 4 layers)

```
Layer 1 — per-step (inside a task)
  red → green → commit, with actual test output shown

Layer 2 — per-task (subagent loop)
  implementer → spec reviewer → code-quality reviewer → fix loop → mark done
  (Always spec FIRST, then quality. Never quality first.)

Layer 3 — per-task verification gates  ← THE LAYER MOST OFTEN SKIPPED
  pytest -q --ignore=tests/load
  grep -rln '<modified files>' tests/
  pin-test scan if line numbers shifted
  ⇒ catches cross-cutting failures that scoped per-task review cannot see

Layer 4 — per-branch (pre-push)
  final whole-branch code review (opus for Class B)
  local CI mirror: pytest -q + ruff + bandit + frontend test + frontend build
  GitNexus reindex
  evidence ledger in PR body
```

**Layer 3 is the layer that would have caught the SIS_CAPTURES incident in T3,
not T9.** Don't skip it. The cost is seconds; the savings is a CI round-trip.

---

## Universal Definition of Done

### Per task

A task is **DONE** only when ALL of these are true:

1. All TDD steps in the plan are checked off with shown green test output.
2. Full `pytest -q --ignore=tests/load` is green (or any failure is *proven* pre-existing via the Hard Rule #1 protocol).
3. Every test file that `grep -rln '<modified file>' tests/` surfaces is green.
4. If lines shifted in any modified file: pin-test scan run, results clean.
5. Spec reviewer: ✅ (scope compliant, nothing missing, nothing extra).
6. Code-quality reviewer: ✅ (opus for Class B).
7. Every reviewer issue: fixed OR tracked with a fix sketch.
8. Only the task's intended files in the commit (no noise, no scope creep).
9. Working tree clean of unrelated modifications relative to the commit being made.

### Per branch (before push / before opening PR)

1. Every task's per-task DoD is met.
2. Final whole-branch code review (opus for Class B).
3. Local CI mirror passes:
   - `source venv/bin/activate && pytest -q --ignore=tests/load`
   - `ruff check backend/ tests/` (or just on changed files for fast)
   - `bandit -q -r <files-you-changed>`
   - `cd frontend && npx vitest run`
   - `cd frontend && npm run build`
   - Alembic migrations smoke if any migration file changed
   - Mypy strict on critical modules if any of those changed
4. GitNexus index refreshed: `npx gitnexus analyze --embeddings`.
5. PR classification (A vs B) is called out explicitly in the PR body.
6. PR body includes: spec ref, plan ref, the test commands the reviewer can
   run to verify, list of known follow-ups (with severity).
7. Branch protection respected — no admin bypass without explicit, documented
   reason.
8. **Class B specifically:** no `gh pr merge --auto` until review returns clean.

---

## Class A vs Class B (CLAUDE.md Principle #13 reference)

| Class | What it means | Review posture |
|---|---|---|
| **A** — behavior-preserving refactor | Golden net (results) + prompt-snapshot net (wording) + AST byte-identity vs `main` prove behavior is unchanged. | Green CI ≈ provably correct → squash-auto-merge on green is earned. |
| **B** — net-new behavior OR compliance/security/FERPA | Green CI only covers cases you imagined to test. | Code review is a HARD pre-gate. **Create PR → review → fix to clean → THEN merge manually.** No auto-merge with review in flight. |

The tell that forces the classification: **"am I adding logic, or just moving
it?"** Adding/changing logic (especially regexes, scoring, redaction, auth) ⇒
Class B. Moving code verbatim ⇒ Class A.

---

## How This File Integrates With Existing Process

| Layer | Source | This file's role |
|---|---|---|
| Project facts | `CLAUDE.md` | Pointer at top — points readers here. |
| Universal preferences | `~/.claude/CLAUDE.md` | Complementary; this file is project-scoped. |
| Process skills | `superpowers:brainstorming`, `superpowers:writing-plans`, `superpowers:subagent-driven-development`, etc. | This file *enforces* the verification gates those skills assume but don't always check. |
| Subagent dispatch | controller-authored prompts | Include `Read .claude/rules/workflow.md before starting` in every dispatch prompt for multi-task work. |
| CI | `.github/workflows/ci.yml` (9 status checks) | This file's gates *mirror* CI locally so you catch fast, not slow. |

---

## Lessons From Incidents (the changelog of pain)

Each entry: date, one-sentence summary, root cause, rule(s) the entry produced.

### 2026-05-25 — SIS_CAPTURES pin misclassification

**What happened.** Tasks 3 and 4 of the ClassLink Roster Server cert-parity
branch shifted line numbers in `backend/routes/classlink_routes.py` and
`backend/roster_sync.py`. The cross-cutting test
`tests/test_sis_alerting.py::test_every_flagged_sis_catch_captures_to_sentry`
pins `(file, line)` tuples in those files and broke when the captures moved
outside the window=8 search range. The T9 cleanup subagent ran the full suite,
saw the failure, and reported it as *"fails identically on main"* — which the
controller almost accepted at face value. (Verified by manual spot-check that
it was actually introduced by Tasks 3 and 4.) A subsequent fix subagent
re-pointed one pin to the wrong meaning (line 223 covers
`_create_classlink_student_session`'s capture, not `_bg_sync`'s). The final
whole-branch review caught the meaning-drift; the real fix landed two commits
later.

**Root causes (three layers).**

1. **Per-task verification scope was too narrow.** Spec and code-quality
   reviewers ran only the test files I named in their dispatch prompts. The SIS
   alerting test wasn't named in T3 or T4 because nothing in those tasks' diffs
   referenced it — but it pinned line numbers in files those tasks shifted.
   Cross-cutting consumers are invisible to scoped review.
2. **No "pre-existing failure" verification protocol.** The cleanup subagent's
   "fails identically on main" claim was accepted on instinct rather than on
   evidence. The proof (`git checkout <base> -- <files>; pytest <test>`) takes
   10 seconds.
3. **Full-suite gate deferred to T9.** A line-shift regression caught in T3 or
   T4 would have been a 2-minute fix; caught in T9 it required a debug detour
   plus a pin-meaning correction.

**Rules added (codified above):**
- Hard Rule #1: "Pre-existing failure" claims require `git checkout <base>` proof.
- Hard Rule #2: `pytest -q` is the floor for per-task verification, not the ceiling.
- Hard Rule #3: Line-shifting refactors require pin-test grep.
- Per-Task Checklist items 3, 4, 5 (full-suite, grep for cross-cutting, line-shift scan).
- Anti-pattern table: "This failure is pre-existing on main" and "All tests in
  `{named files}` pass."

**Outcome.** The PR (#588) shipped clean. The lesson costs one extra checklist
step on every future task; the missed catch would cost a red PR every time a
refactor shifts a pinned line.

---

*Add new incident entries above this footer, newest first. Keep each entry short
— the rules go in the body above; this section is the audit trail.*
