# CI/CD Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a CI/CD pipeline that prevents broken code from reaching production — GitHub Actions test gate, branch protection on main, and a PR-based deploy workflow so one bad commit can't take down the app for Volusia County teachers.

**Architecture:** Consolidate the two existing workflow files (`test.yml` + `ci.yml`) into a single `ci.yml` that runs backend tests + frontend build. Fix the currently-failing test (`test_admin_routes.py:125`). Enable GitHub branch protection requiring CI to pass before merging to main. Railway already auto-deploys from main, so the protection rule is the gate.

**Tech Stack:** GitHub Actions, pytest, Node 20, Vite, Railway (Nixpacks), GitHub branch protection API

**Review history:**
- Rev 1: Initial plan
- Rev 2: Root-caused failing test (hardcoded date, not endpoint bug), added PR branch trigger, documented branch protection rollback, added job name stability note, added README.md update step

---

## Current State

| Item | Status | Problem |
|------|--------|---------|
| `test.yml` | Exists, FAILING | Python 3.14 (not stable), test_admin_routes fails (410 vs 200) |
| `ci.yml` | Exists, FAILING | Python 3.12, redundant with test.yml, no coverage |
| Branch protection | OFF | Anyone can push broken code to main |
| Railway deploy | Auto on main push | No gate — deploys even when tests fail |
| Test suite | 49 files, 40% coverage floor | Tests pass locally but fail in CI due to missing env setup |

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `.github/workflows/ci.yml` | **Rewrite** | Consolidated CI: backend tests + frontend build + coverage |
| `.github/workflows/test.yml` | **Delete** | Redundant — consolidated into ci.yml |
| `tests/test_admin_routes.py` | **Fix** | Fix failing test (410 vs 200 on admin claim) |
| `CLAUDE.md` | **Modify** | Document the new PR-based deploy workflow |

---

### Task 1: Fix the failing test in CI

The CI pipeline is useless until the test suite passes. The failure is in `test_admin_routes.py:125` — `test_claim_valid_code_succeeds` expects HTTP 200 but gets 410 (Gone).

**Root cause (verified):** The test hardcodes `"created_at": "2026-03-25T00:00:00+00:00"` (line 110). The endpoint has a 7-day TTL check — if `now - created_at > 7 days`, it returns 410. Since it's now April 2, that date is 8 days old, so the invite is expired. **The endpoint is correct; the test uses a stale hardcoded date.**

**Files:**
- Modify: `tests/test_admin_routes.py:108-112`

- [ ] **Step 1: Fix the test — use a dynamic timestamp**

In `tests/test_admin_routes.py`, find the `test_claim_valid_code_succeeds` method (~line 106). Change the `invite` dict from:

```python
        invite = {
            "school": "Lincoln High",
            "created_at": "2026-03-25T00:00:00+00:00",
            "manual_teachers": [],
        }
```

to:

```python
        from datetime import datetime, timezone
        invite = {
            "school": "Lincoln High",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "manual_teachers": [],
        }
```

This ensures the invite is always "just created" regardless of when the test runs.

- [ ] **Step 3: Run the test locally**

```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
python -m pytest tests/test_admin_routes.py::TestAdminClaim::test_claim_valid_code_succeeds -v
```

Expected: PASS

- [ ] **Step 4: Run the full test suite with the same CI command**

```bash
python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -x --cov=backend --cov-report=term-missing --cov-fail-under=40
```

Expected: All tests pass, coverage >= 40%

If additional tests fail, fix them in this task. The goal is a green test suite.

- [ ] **Step 5: Commit**

```bash
git add tests/test_admin_routes.py
git commit -m "fix: repair test_claim_valid_code_succeeds for CI (410 → proper mock setup)"
```

---

### Task 2: Consolidate into a single CI workflow

**Files:**
- Rewrite: `.github/workflows/ci.yml`
- Delete: `.github/workflows/test.yml`

- [ ] **Step 1: Delete the redundant test.yml**

```bash
cd /Users/alexc/Downloads/Graider
rm .github/workflows/test.yml
```

- [ ] **Step 2: Rewrite ci.yml as the single consolidated workflow**

Write `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    # Runs on PRs targeting main from ANY branch
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend-tests:
    name: Backend Tests
    runs-on: ubuntu-latest

    env:
      FLASK_ENV: testing
      FLASK_SECRET_KEY: ci-test-secret-key

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt pytest-cov

      - name: Run tests with coverage
        run: |
          python -m pytest tests/ -q \
            --ignore=tests/load \
            --ignore=tests/stress \
            --ignore=tests/e2e \
            -x \
            -m "not live" \
            --cov=backend \
            --cov-report=term-missing \
            --cov-fail-under=40

  frontend-build:
    name: Frontend Build
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Build
        run: cd frontend && npm run build
```

Key changes from the old workflows:
- **Python 3.12** (stable) instead of 3.14 (pre-release)
- **`-m "not live"`** to skip tests requiring API keys
- **`FLASK_SECRET_KEY`** set for session-dependent tests
- **`concurrency`** cancels in-progress runs on same branch (saves minutes)
- **Two parallel jobs** (backend + frontend) instead of sequential steps
- **Single workflow** instead of two redundant files

- [ ] **Step 3: Verify the workflow YAML is valid**

```bash
cd /Users/alexc/Downloads/Graider
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('Valid YAML')"
```

Expected: `Valid YAML`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git rm .github/workflows/test.yml
git commit -m "ci: consolidate into single workflow, fix Python version, add concurrency"
```

---

### Task 3: Enable branch protection on main

This is the critical gate. Without it, `git push origin main` bypasses CI entirely.

**Files:**
- No files — GitHub API configuration only

- [ ] **Step 1: Enable branch protection via GitHub CLI**

```bash
gh api repos/nlev8/Graider/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Backend Tests","Frontend Build"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='null' \
  --field restrictions='null' \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

This enforces:
- **Required status checks**: Both `Backend Tests` and `Frontend Build` must pass
- **Strict**: Branch must be up-to-date with main before merging
- **No force pushes**: Prevents history rewriting on main
- **No PR reviews required**: Solo developer, don't need self-approval friction
- **Admins not exempt**: Even the repo owner must pass CI (set `enforce_admins=true` if you want this; `false` lets you emergency-push if CI is broken)

- [ ] **Step 2: Verify protection is active**

```bash
gh api repos/nlev8/Graider/branches/main/protection --jq '.required_status_checks.contexts[]'
```

Expected output:
```
Backend Tests
Frontend Build
```

**If the `gh api` command fails:** Check that the GitHub CLI is authenticated with `repo` scope: `gh auth status`. If scope is insufficient, re-authenticate: `gh auth login --scopes repo`.

**Rollback:** To remove branch protection (e.g., emergency hotfix):
```bash
gh api repos/nlev8/Graider/branches/main/protection --method DELETE
```
Re-enable afterward by re-running the Step 1 command.

**Job name stability:** The required status check names (`Backend Tests`, `Frontend Build`) must match the `name:` field in each job in `ci.yml` exactly. If you ever rename a job, you must also update the branch protection rule or merges will be blocked. To update:
```bash
gh api repos/nlev8/Graider/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["New Job Name 1","New Job Name 2"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='null' \
  --field restrictions='null' \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

- [ ] **Step 3: Test the protection by verifying direct push behavior**

After protection is enabled, the workflow for deploys becomes:
1. Create a branch: `git checkout -b feature/my-change`
2. Push the branch: `git push -u origin feature/my-change`
3. Create a PR: `gh pr create --title "..." --body "..."`
4. CI runs automatically on the PR
5. If CI passes, merge the PR (which triggers Railway deploy)
6. If CI fails, fix and push — CI re-runs

Verify this works by creating a test branch:

```bash
git checkout -b test/verify-ci
echo "# CI test" >> /dev/null
git commit --allow-empty -m "test: verify CI pipeline"
git push -u origin test/verify-ci
gh pr create --title "test: verify CI pipeline" --body "Testing branch protection. Will close after CI runs."
```

Wait for CI to run, then check:
```bash
gh pr checks test/verify-ci
```

Expected: Both checks pass. Then clean up:
```bash
gh pr close test/verify-ci
git checkout main
git branch -d test/verify-ci
git push origin --delete test/verify-ci
```

---

### Task 4: Update CLAUDE.md and README.md with the new deploy workflow

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Update the Deployment section in CLAUDE.md**

In `CLAUDE.md`, find the `## Deployment` section and replace it with:

```markdown
## Deployment

- **Backend (app.graider.live)**: Railway — auto-deploys when PRs merge to `main`. Direct pushes to main are blocked by branch protection.
- **Landing page (graider.live)**: Vercel — deploy with `cd landing && npx vercel --prod`. Separate Vercel project.
- **Frontend**: Built with `cd frontend && npm run build`, output goes to `backend/static/`. Deployed with the backend via Railway.

### CI/CD Pipeline

All changes go through Pull Requests:

1. Create branch: `git checkout -b feature/my-change`
2. Push: `git push -u origin feature/my-change`
3. Create PR: `gh pr create --title "..." --body "..."`
4. CI runs automatically (backend tests + frontend build)
5. Merge when CI passes → Railway auto-deploys

**Branch protection on `main` requires:**
- `Backend Tests` job passes (pytest with 40% coverage floor)
- `Frontend Build` job passes (Vite build succeeds)

**Emergency bypass:** Repo admins can merge without CI if `enforce_admins` is false. Use only for critical hotfixes — fix CI immediately after.

**CI job names are locked:** The branch protection rule references `Backend Tests` and `Frontend Build` by exact name. If you rename a job in `.github/workflows/ci.yml`, update the branch protection rule too or merges will be blocked. See `docs/superpowers/plans/2026-04-02-cicd-pipeline.md` Task 3 for the update command.
```

- [ ] **Step 2: Add Contributing / CI section to README.md**

Find `README.md` in the project root. Add a `## Contributing` section (or append to an existing one) with:

```markdown
## Contributing

### CI Pipeline

This project uses GitHub Actions for continuous integration. Branch protection on `main` requires all checks to pass before merging.

**Required checks:**
- **Backend Tests** — runs `pytest` with 40% coverage floor (excludes load/stress/e2e tests)
- **Frontend Build** — runs `npm run build` via Vite

**Workflow:**
1. Create a feature branch: `git checkout -b feature/my-change`
2. Push and open a PR: `git push -u origin feature/my-change && gh pr create`
3. CI runs automatically — both jobs must pass
4. Merge the PR → Railway auto-deploys to production

**Running tests locally:**
```bash
source venv/bin/activate
python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -m "not live"
cd frontend && npm run build
```

**Note:** Do not push directly to `main`. Direct pushes are blocked by branch protection.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update CLAUDE.md and README.md with PR-based deploy workflow and CI instructions"
```

---

## Summary

| Task | What | Risk |
|------|------|------|
| 1 | Fix failing test (hardcoded date → dynamic) | Low — 1-line test fix |
| 2 | Consolidate to single ci.yml, fix Python version | Low — workflow config only |
| 3 | Enable branch protection on main | **Medium** — changes deploy workflow permanently |
| 4 | Document workflow in CLAUDE.md + README.md | None |

**Before:** `git push origin main` → broken code deploys to production → teachers can't grade.
**After:** PR → CI must pass → merge → Railway deploys known-good code.

**Important note for Task 3:** Once branch protection is enabled, you can no longer `git push origin main` directly. All changes must go through PRs. To temporarily disable protection for an emergency hotfix:
```bash
gh api repos/nlev8/Graider/branches/main/protection --method DELETE
```
Re-enable immediately after by re-running the Task 3 Step 1 command.
