# CI/CD Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a CI/CD pipeline that prevents broken code from reaching production — GitHub Actions test gate, branch protection on main, and a PR-based deploy workflow so one bad commit can't take down the app for Volusia County teachers.

**Architecture:** Consolidate the two existing workflow files (`test.yml` + `ci.yml`) into a single `ci.yml` that runs backend tests + frontend build. Fix the currently-failing test (`test_admin_routes.py:125`). Enable GitHub branch protection requiring CI to pass before merging to main. Railway already auto-deploys from main, so the protection rule is the gate.

**Tech Stack:** GitHub Actions, pytest, Node 20, Vite, Railway (Nixpacks), GitHub branch protection API

**Review history:**
- Rev 1: Initial plan

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

The CI pipeline is useless until the test suite passes. The failure is in `test_admin_routes.py:125` — `test_claim_valid_code_succeeds` expects HTTP 200 but gets 410 (Gone). This means the admin claim endpoint returns 410 when the invite code has already been consumed or expired.

**Files:**
- Modify: `tests/test_admin_routes.py`

- [ ] **Step 1: Read the failing test and the endpoint it tests**

Read `tests/test_admin_routes.py` around line 125 to understand the test setup. Then read the admin claim endpoint in `backend/routes/admin_routes.py` to understand when it returns 410.

- [ ] **Step 2: Fix the test**

The test likely needs to set up a valid, unconsumed invite code before claiming it. Read the actual test fixture and the claim endpoint logic, then fix the test so it creates a fresh invite code that hasn't been consumed.

Common causes:
- The test fixture creates an invite code that's already marked as `used`
- The mock Supabase returns data indicating the code is expired
- The claim endpoint checks for code existence and the mock doesn't set it up correctly

After reading the code, make the minimal fix. Do NOT change the endpoint — fix the test.

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

### Task 4: Update CLAUDE.md with the new deploy workflow

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the Deployment section**

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
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with PR-based deploy workflow"
```

---

## Summary

| Task | What | Risk |
|------|------|------|
| 1 | Fix failing test so CI goes green | Low — test fix only |
| 2 | Consolidate to single ci.yml, fix Python version | Low — workflow config only |
| 3 | Enable branch protection on main | **Medium** — changes deploy workflow permanently |
| 4 | Document the new workflow in CLAUDE.md | None |

**Before:** `git push origin main` → broken code deploys to production → teachers can't grade.
**After:** PR → CI must pass → merge → Railway deploys known-good code.

**Important note for Task 3:** Once branch protection is enabled, you can no longer `git push origin main` directly. All changes must go through PRs. If you need to emergency-push, you can temporarily disable protection via `gh api repos/nlev8/Graider/branches/main/protection --method DELETE`. Make sure you understand this before enabling it.
