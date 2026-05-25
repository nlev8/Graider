# Frontend Bundle-Staleness CI Guard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a CI guard that fails when committed `backend/static/` is stale vs a fresh Vite build, and pin the canonical build to Node 24.

**Architecture:** Fold a `git diff --exit-code backend/static/` check into the existing required "Frontend Build" job (which already runs `npm ci` + `npm run build`), and standardize the Node version via `.nvmrc` = 24 across the frontend CI jobs. No new CI job → no branch-protection change.

**Tech Stack:** GitHub Actions (`.github/workflows/ci.yml`), `actions/setup-node@v4`, Vite 5, `.nvmrc`.

**Spec:** `docs/superpowers/specs/2026-05-25-frontend-bundle-staleness-ci-guard-design.md`

**PR class:** CI/tooling (not app behavior). The PR's own CI run is the proof the guard works on the current bundle. Standard review; merge on green.

---

## Task 1: Pin canonical Node version

**Files:**
- Create: `.nvmrc`
- Modify: `frontend/package.json`

- [ ] **Step 1: Create `.nvmrc`** at the repo root with exactly:

```
24
```

- [ ] **Step 2: Add an `engines` pin to `frontend/package.json`.** Read the file, then add a top-level `"engines"` key (alongside `"name"`/`"version"`/`"scripts"`), preserving valid JSON (watch trailing commas):

```json
  "engines": {
    "node": "24.x"
  },
```

- [ ] **Step 3: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('frontend/package.json')); print('valid')"`
Expected: `valid`

- [ ] **Step 4: Commit**

```bash
git add .nvmrc frontend/package.json
git commit -m "build(frontend): pin canonical Node to 24 (.nvmrc + engines)"
```

---

## Task 2: Point both frontend CI jobs at `.nvmrc`

**Files:**
- Modify: `.github/workflows/ci.yml` (the `frontend-build` `setup-node` block ~L60-65, and the `frontend-e2e-smoke` `setup-node` block ~L122-127)

- [ ] **Step 1: Update the `Frontend Build` job's `Set up Node` step.** Replace:

```yaml
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
```

with:

```yaml
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version-file: .nvmrc
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
```

- [ ] **Step 2: Update the `Frontend E2E Smoke` job's `Set up Node` step.** There is a second, identical `node-version: '20'` `setup-node` block in the `frontend-e2e-smoke` job — apply the **same** change (`node-version: '20'` → `node-version-file: .nvmrc`), leaving its `cache`/`cache-dependency-path` lines intact.

- [ ] **Step 3: Verify exactly two edits landed and no `node-version: '20'` remains**

Run: `grep -n "node-version" .github/workflows/ci.yml`
Expected: two `node-version-file: .nvmrc` lines; **no** remaining `node-version: '20'` in the two frontend jobs. (Note: the `Set up Python` step uses `python-version` — unrelated, leave it.)

- [ ] **Step 4: Validate the workflow YAML parses**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok')"`
Expected: `yaml ok`

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(frontend): build both frontend jobs with .nvmrc Node (24)"
```

---

## Task 3: Add the staleness guard step

**Files:**
- Modify: `.github/workflows/ci.yml` (the `frontend-build` job)

- [ ] **Step 1: Add the guard step immediately after the `Build` step.** In the `frontend-build` job, after:

```yaml
      - name: Build
        run: cd frontend && npm run build
```

append:

```yaml

      - name: Verify committed frontend bundle is current
        run: |
          if ! git diff --exit-code -- backend/static; then
            echo "::error::backend/static is stale: a fresh Vite build changed the committed bundle. The deploy serves backend/static directly (no build at deploy), so run 'cd frontend && npm run build' (Node per .nvmrc) and commit backend/static, then push."
            exit 1
          fi
```

- [ ] **Step 2: Validate the workflow YAML parses**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok')"`
Expected: `yaml ok`

- [ ] **Step 3: Locally simulate the guard logic — IN SYNC case (expect pass).** From the synced `main` working tree:

Run:
```bash
cd frontend && npm run build && cd ..
git diff --exit-code -- backend/static && echo "GUARD-PASS: bundle in sync"
```
Expected: `GUARD-PASS: bundle in sync` (exit 0). If this fails, the committed bundle doesn't match a local Node-24 build — STOP and report (it means the canonical build needs re-committing).

- [ ] **Step 4: Locally simulate the guard logic — STALE case (expect catch).**

Run:
```bash
printf '\n<!-- staleness probe -->' >> backend/static/index.html
if ! git diff --exit-code -- backend/static >/dev/null; then echo "GUARD-CATCHES-STALE: ok"; fi
git checkout -- backend/static/   # restore
```
Expected: `GUARD-CATCHES-STALE: ok`, then a clean `backend/static/`.

- [ ] **Step 5: Confirm working tree clean afterward**

Run: `git status --short backend/static/`
Expected: no output (restored).

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(frontend): fail when committed backend/static is stale vs fresh build"
```

---

## Task 4: PR + verify the guard in real CI

**Files:** none (verification only)

- [ ] **Step 1: Push branch + open PR**

```bash
git push -u origin chore/frontend-bundle-staleness-guard
gh pr create --base main --title "ci(frontend): guard against stale committed backend/static bundle + pin Node 24" \
  --body "Implements docs/superpowers/specs/2026-05-25-frontend-bundle-staleness-ci-guard-design.md. Folds a git-diff staleness check into the existing Frontend Build job and pins the canonical build to Node 24 via .nvmrc. Approach C (build-at-deploy) deferred as a follow-up."
```

- [ ] **Step 2: Confirm CI is green — specifically the guard's own behavior.** The PR's `Frontend Build` job must pass, which proves: Node-24 build succeeds, the vitest count-floor still passes on Node 24, AND the new guard step passes (committed bundle == Node-24 CI build). `Frontend E2E Smoke` must pass on Node 24.

Run (after CI settles): `gh pr checks <PR#>`
Expected: all required checks pass. If `Frontend Build` fails ONLY on the guard step, the committed bundle differs from the CI Node-24 build → pull/commit the CI-built bundle (CI is authoritative per spec §4.3) and re-push.

- [ ] **Step 3: Merge on green** (standard review; CI/tooling change). `gh pr merge <PR#> --squash --delete-branch`.

- [ ] **Step 4: File the Approach-C follow-up** (root-cause fix; out of scope here):

```bash
gh issue create --title "Frontend: build at deploy instead of committing backend/static (retire the staleness guard)" \
  --body "Follow-up to the bundle-staleness guard (spec 2026-05-25-frontend-bundle-staleness-ci-guard-design.md §5). Move the Vite build into the Railway/NIXPACKS deploy (or deploy a CI-built artifact) and gitignore backend/static, eliminating the committed-artifact synchronization class entirely. Both Codex and Gemini ranked this the superior long-term architecture; deferred because it changes the deploy contract and needs careful Railway/NIXPACKS build testing."
```

---

## Self-Review (completed during plan authoring)

- **Spec coverage:** D1/D2 (guard in Frontend Build) → Task 3; D3 (Node 24 pin) → Tasks 1–2; D4 (defer C) → Task 4 Step 4; determinism (§4.3) → canonical Node via `.nvmrc` (Tasks 1–2) + local in-sync/stale simulations (Task 3 Steps 3–4); verification (§6) → Task 3 Steps 3–5 + Task 4 Step 2.
- **Placeholder scan:** none — every step has exact content/commands. (`<PR#>` is a runtime value, not a placeholder.)
- **Consistency:** `.nvmrc` = `24`, `engines` = `24.x`, both `setup-node` → `node-version-file: .nvmrc`, guard uses `git diff --exit-code -- backend/static` consistently across spec + plan.
