# NotebookLM Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fully remove the dead NotebookLM integration that was partially replaced by the native study-guide generator but never fully excised — backend routes/service, 10 frontend client functions, the entire PlannerTab NotebookLM Materials panel, E2E spec, audit-test entry, requirements.txt dependency, and CLAUDE.md API docs.

**Architecture:** Pure deletion. No new code, no behavior changes to surviving code. The study-guide generator (commit c847ab7) is the replacement and stays untouched. `student_portal_routes.py:621` has a stale comment calling the content-type handler "NotebookLM" but the underlying code serves study_guide/flashcards/slide_deck/mind_map/audio_overview/video_overview/infographic/data_table — all native generator outputs — so only the comment changes.

**Tech Stack:** Python (Flask routes), React/JSX (frontend panel), Playwright (E2E spec), pytest (audit test).

---

## Blast radius

Verified by grep + gitnexus_impact before removal. No additional references outside these files:

**Backend (delete):**
- `backend/routes/notebooklm_routes.py` — Flask blueprint, ~12 endpoints
- `backend/services/notebooklm_service.py` — 449 lines, notebooklm-py wrapper

**Backend (modify):**
- `backend/routes/__init__.py` — remove import (L28), registration (L65), `__all__` entry (L95)
- `backend/routes/student_portal_routes.py:621` — update stale comment only (not removing code)
- `requirements.txt` — remove `notebooklm-py[browser]>=0.3.0` (and its section header comment)

**Frontend (delete):**
- `frontend/e2e/notebooklm-endpoints.spec.js`

**Frontend (modify):**
- `frontend/src/services/api.js` — remove 10 exported functions in the `============ NotebookLM Materials ============` section (lines ~1200–~1285)
- `frontend/src/tabs/PlannerTab.jsx` — remove:
  - State at line ~467 (`// NotebookLM materials state` block)
  - Auth-status effect at line ~954
  - Status-polling effect at line ~961
  - Generation handler at lines ~1257–1347
  - UI panel at lines ~7379–7671 (`{/* NotebookLM Materials */}` through the closing `</div>`)
  - Any referenced state vars used only inside removed code

**Tests/docs (modify):**
- `tests/test_sis_alerting.py` — remove `"backend/services/notebooklm_service.py": 3` entry from `PR_A_EXPECTED_CAPTURES` dict
- `CLAUDE.md` — remove the `### NotebookLM Integration` block under "API Reference"

**Not touched (historical records / per-user cache):**
- `scripts/apply_pr_*_capture.py`, `scripts/apply_batch_c_*.py` — one-shot patchers that have already run. Preserving them for audit trail.
- `docs/exception-audit-2026-04.md`, `docs/superpowers/plans/2026-04-03-study-guide-generator.md`, etc. — historical planning/audit docs.
- `notes/devlog/2026-04-04 - Slide Deck Generator.md` — historical devlog.
- `.claude/settings.local.json` — per-user permission cache. Contains 5 bash-command audit lines (lines 84, 86, 88, 90, 91) that mention `notebooklm` in previously-allowed commands. Not active code; leaving as-is (Claude Code rewrites this file during normal sessions).

---

## Task 1: Verify no hidden usages and create branch

**Files:** none modified

- [ ] **Step 1: Create branch**

```bash
git checkout main && git pull origin main
git checkout -b feat/remove-notebooklm
```

- [ ] **Step 2: Run gitnexus impact on the blueprint**

Run: `gitnexus_impact({target: "notebooklm_bp", direction: "upstream"})`
Expected: Only `backend/routes/__init__.py` as d=1 caller. If any OTHER file appears, STOP — add it to the plan before proceeding.

- [ ] **Step 3: Final scan for stragglers**

```bash
grep -rni "notebooklm\|notebookLM" --include="*.py" --include="*.js" --include="*.jsx" --include="*.ts" --include="*.tsx" --include="*.json" --include="*.txt" --include="*.md" --include="*.yml" --include="*.yaml" . 2>/dev/null | grep -v "^\./docs/superpowers/plans/" | grep -v "^\./notes/" | grep -v "^\./scripts/apply_" | grep -v "^\./docs/exception-audit" | grep -v "node_modules" | grep -v "venv/"
```

Expected output: only lines in the files listed in "Blast radius" above. If any unexpected file appears, STOP — add it to the plan.

---

## Task 2: Delete backend service + routes files

**Files:**
- Delete: `backend/routes/notebooklm_routes.py`
- Delete: `backend/services/notebooklm_service.py`

- [ ] **Step 1: Delete the two files**

```bash
rm backend/routes/notebooklm_routes.py backend/services/notebooklm_service.py
```

- [ ] **Step 2: Verify they are gone**

```bash
ls backend/routes/notebooklm_routes.py backend/services/notebooklm_service.py 2>&1 || echo OK
```

Expected: `No such file or directory` then `OK`.

---

## Task 3: Remove blueprint wiring in routes/__init__.py

**Files:**
- Modify: `backend/routes/__init__.py`

- [ ] **Step 1: Remove the import line**

Open `backend/routes/__init__.py`. Delete the line:

```python
from .notebooklm_routes import notebooklm_bp
```

- [ ] **Step 2: Remove the blueprint registration**

Delete the line:

```python
    app.register_blueprint(notebooklm_bp)
```

- [ ] **Step 3: Remove the `__all__` entry**

Delete the `'notebooklm_bp',` entry from the module's `__all__` tuple/list.

- [ ] **Step 4: Verify the module still imports cleanly**

```bash
source venv/bin/activate
python -c "from backend.routes import *; print('OK')"
```

Expected: `OK` with no ImportError or NameError.

---

## Task 4: Drop the requirements.txt dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Remove the dependency lines**

Delete BOTH of these lines (the comment header and the package):

```
# NotebookLM Integration (study materials generation)
notebooklm-py[browser]>=0.3.0
```

- [ ] **Step 2: Note for deploy**

The Railway/CI environment will still have `notebooklm-py` installed until a deploy rebuild. That's fine — no code imports it anymore. No action needed here, but document in the PR body that the package will fall out on next rebuild.

---

## Task 5: Update the audit-test floor in tests/test_sis_alerting.py

**Files:**
- Modify: `tests/test_sis_alerting.py`

- [ ] **Step 1: Remove the deleted file's entry**

Open `tests/test_sis_alerting.py`. In `PR_A_EXPECTED_CAPTURES`, delete the line:

```python
    "backend/services/notebooklm_service.py": 3,
```

- [ ] **Step 2: Run the audit-capture suite**

```bash
source venv/bin/activate
python -m pytest tests/test_sis_alerting.py -v
```

Expected: All previously-green tests remain green. The `test_pr_a_non_sis_files_have_expected_captures` test should not fail on the deleted file.

---

## Task 6: Fix the stale comment in student_portal_routes.py

**Files:**
- Modify: `backend/routes/student_portal_routes.py:621`

- [ ] **Step 1: Replace the stale comment**

Change line 621 from:

```python
        # Shared material content (NotebookLM) — return directly
```

To:

```python
        # Shared study-material content (study guide, flashcards, etc.) — return directly
```

- [ ] **Step 2: Verify no code change**

```bash
git diff backend/routes/student_portal_routes.py
```

Expected: only the comment-line change; no functional diff.

---

## Task 7: Remove frontend API client functions

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Remove the NotebookLM Materials section**

In `frontend/src/services/api.js`, delete EVERYTHING from the section header line `// ============ NotebookLM Materials ============` through the end of the last `notebookLM*` exported function (which includes `notebookLMAuthStatus`, `notebookLMLogin`, `notebookLMUploadContext`, `notebookLMCreateNotebook`, `notebookLMGenerate`, `notebookLMStatus`, `notebookLMDownload`, `notebookLMPreview`, `notebookLMCancel`, `notebookLMRetry`).

- [ ] **Step 2: Verify JS parses**

```bash
cd frontend
node -e "require('./src/services/api.js')" 2>&1 | head
```

Expected: either clean exit or a module-not-found that is unrelated to syntax; no SyntaxError.

(If Node module resolution complains about ESM vs CJS, skip this and rely on Task 11's Vite build to catch syntax errors.)

---

## Task 8: Remove NotebookLM UI from PlannerTab.jsx

**Files:**
- Modify: `frontend/src/tabs/PlannerTab.jsx`

- [ ] **Step 1: Remove the state block**

Delete the block starting with `// NotebookLM materials state` (around line 467) through the end of that grouped state declaration (all `nlm*` / `notebookLM*` useState hooks).

- [ ] **Step 2: Remove the auth-status mount effect**

Delete the `useEffect` block starting with `// Check NotebookLM auth status on mount` (around line 954) through its closing `}, [])` or dependency array.

- [ ] **Step 3: Remove the status-polling effect**

Delete the `useEffect` block starting with `// NotebookLM generation status polling` (around line 961) through its closing `}, [...])`.

- [ ] **Step 4: Remove the generation handler**

Delete the function/block starting with `// NotebookLM materials generation handler` (around line 1257) through its close (around line 1347). This includes `addToast("Creating NotebookLM notebook...")` and all calls to `api.notebookLM*`.

- [ ] **Step 5: Remove the Materials UI panel — EXACT LINE RANGE 7379-7774**

Codex Gate 1 verified the panel spans lines **7379–7774** (not 7671 — that's inside a nested button handler). The wrapping `<div className="glass-card" ...>` opens on line 7380 and its matching close is on line 7774.

Delete lines **7379 through 7774 inclusive**. Tactic for safety:

```bash
# 1. Verify anchors before deleting
sed -n '7379p;7380p;7774p;7775p' frontend/src/tabs/PlannerTab.jsx
```

Expected output:
- 7379: `                      {/* NotebookLM Materials */}`
- 7380: `                      <div className="glass-card" style={...}>`
- 7774: `                      </div>` (matching close of the 7380 `<div>`)
- 7775: `                    </div>` (the NEXT line — sibling container closing, NOT part of the panel)

If those don't match, STOP — line numbers drifted; rerun the grep in Step 6 first to re-anchor.

```bash
# 2. Delete the exact range
sed -i.bak '7379,7774d' frontend/src/tabs/PlannerTab.jsx
rm frontend/src/tabs/PlannerTab.jsx.bak
```

Alternative (if sed feels risky): open the file in the editor, select from the `{/* NotebookLM Materials */}` comment on line 7379 down through the `</div>` on line 7774 (verify by JSX-depth counting `<div>`→+1, `</div>`→−1 starting at depth 1 on line 7380; depth returns to 0 on line 7774), delete.

- [ ] **Step 6: Remove any now-orphaned state setters / handler refs**

Scan the whole file for remaining `nlm` / `notebookLM` identifiers:

```bash
grep -n "nlm\|notebookLM\|NotebookLM" frontend/src/tabs/PlannerTab.jsx
```

Expected: zero matches. If any remain, delete them (they are dead references to removed state/handlers).

- [ ] **Step 7: Run frontend build**

```bash
cd frontend
npm run build
```

Expected: `✓ built in Xs` with zero errors. Unused-import warnings for removed `api.notebookLM*` imports may appear — if so, remove those imports too.

---

## Task 9: Delete E2E spec

**Files:**
- Delete: `frontend/e2e/notebooklm-endpoints.spec.js`

- [ ] **Step 1: Delete the spec**

```bash
rm frontend/e2e/notebooklm-endpoints.spec.js
```

- [ ] **Step 2: Verify no Playwright config references it by name**

```bash
grep -n "notebooklm" frontend/e2e/playwright.config.* 2>&1 || echo OK
```

Expected: `OK` (no matches).

---

## Task 10: Clean CLAUDE.md API reference

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Remove the NotebookLM Integration block**

In `CLAUDE.md`, find the section:

```markdown
### NotebookLM Integration
- `GET /api/notebooklm/auth-status` — Check auth status
- `POST /api/notebooklm/create-notebook` — Create notebook
- `POST /api/notebooklm/generate` — Generate study materials
- `GET /api/notebooklm/download/<type>` — Download generated material
```

Delete the heading and all bullet lines in that section.

---

## Task 11: Run the full backend test suite + SIS contract check

**Files:** none modified

- [ ] **Step 1: Run backend tests with coverage**

```bash
source venv/bin/activate
python -m pytest --cov=backend --cov-fail-under=30 -q --ignore=tests/e2e --ignore=tests/load --ignore=tests/stress
```

Expected: all tests pass; coverage above 30% (removing the 449-line 12%-covered file actually INCREASES the percentage because it removes more uncovered lines than covered ones).

- [ ] **Step 2: Run the SIS contract suite specifically**

```bash
python -m pytest tests/test_sso_contracts.py tests/test_clever_sso_http.py tests/test_classlink_sso_http.py tests/test_oneroster_sso_http.py tests/test_roster_sync.py tests/test_sync_routes.py tests/test_oneroster_gradebook.py -v
```

Expected: 81/81 green (no SIS-compliance regression — zero Clever/ClassLink/OneRoster code was touched).

- [ ] **Step 3: Re-run frontend build to confirm clean**

```bash
cd frontend && npm run build
```

Expected: zero errors, zero warnings related to notebooklm.

---

## Task 12: Commit and open PR

**Files:** all changes above staged.

- [ ] **Step 1: Stage and commit**

```bash
git add -A
git status  # Verify ONLY the files in the Blast Radius section are touched
git commit -m "$(cat <<'EOF'
chore: remove dead NotebookLM integration

NotebookLM was partially replaced by the native study-guide generator in
commit c847ab7, but the backend routes + service, 10 frontend API
clients, the full PlannerTab UI panel (~300 lines), the E2E spec, the
audit-test entry, and the requirements.txt dep were never cleaned up.
Fully excised now:

Backend:
- DELETE backend/routes/notebooklm_routes.py
- DELETE backend/services/notebooklm_service.py
- MODIFY backend/routes/__init__.py (blueprint unwired)
- MODIFY requirements.txt (notebooklm-py dropped)
- MODIFY backend/routes/student_portal_routes.py (stale comment only)

Frontend:
- DELETE frontend/e2e/notebooklm-endpoints.spec.js
- MODIFY frontend/src/services/api.js (10 client functions removed)
- MODIFY frontend/src/tabs/PlannerTab.jsx (state, effects, handlers,
  full Materials panel removed)

Docs/tests:
- MODIFY tests/test_sis_alerting.py (remove service entry from
  PR_A_EXPECTED_CAPTURES)
- MODIFY CLAUDE.md (remove NotebookLM Integration API reference block)

Zero behavior change to surviving code. SIS contract suite 81/81 green.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Push branch**

```bash
git push origin feat/remove-notebooklm
```

- [ ] **Step 3: Open PR**

```bash
gh pr create --title "chore: remove dead NotebookLM integration" --body "$(cat <<'EOF'
## Summary
- Fully removes the dead NotebookLM integration that was partially replaced by the native study-guide generator (commit c847ab7) but never fully cleaned up.
- Zero behavior change to surviving code. SIS contract suite 81/81 green.

## What was removed
**Backend:**
- \`backend/routes/notebooklm_routes.py\` (deleted)
- \`backend/services/notebooklm_service.py\` (449 lines deleted)
- Blueprint registration unwired from \`backend/routes/__init__.py\`
- \`notebooklm-py[browser]\` dropped from \`requirements.txt\`

**Frontend:**
- 10 API client functions in \`frontend/src/services/api.js\`
- Full NotebookLM Materials panel (state + effects + handlers + UI, ~300 lines) in \`frontend/src/tabs/PlannerTab.jsx\`
- \`frontend/e2e/notebooklm-endpoints.spec.js\`

**Docs/tests:**
- \`tests/test_sis_alerting.py\` audit-test entry
- \`CLAUDE.md\` API reference block
- Stale comment in \`backend/routes/student_portal_routes.py\`

## Test plan
- [x] Backend test suite passes with coverage floor >=30%
- [x] SIS contract suite 81/81 green (no Clever/ClassLink/OneRoster code touched)
- [x] Frontend \`npm run build\` clean
- [ ] CI green

## Deploy note
The \`notebooklm-py\` package will fall out of the Railway environment on next rebuild — no code imports it anymore.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 4: Wait for CI green and confirm with user before merging**

Per workflow: await user's explicit "yes" / "merge" before `gh pr merge`.

---

## Self-review

1. **Spec coverage:** Every item in the Blast Radius section has a task. Backend delete (Task 2), blueprint rewiring (Task 3), requirements (Task 4), audit-test (Task 5), stale comment (Task 6), frontend API (Task 7), frontend UI (Task 8), E2E (Task 9), docs (Task 10), full verification (Task 11), commit+PR (Task 12).
2. **Placeholder scan:** No TBD / TODO / "implement later". Every step has concrete commands or exact text to remove.
3. **Type consistency:** N/A (pure deletion).
4. **Risk callouts:** Task 8's state/effect/handler/UI removal is the highest-risk step because PlannerTab.jsx is 7000+ lines; Step 6 of Task 8 grep-scans for orphaned references as the safety net.
