# Frontend Build-at-Deploy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the Vite frontend at deploy on Railway/NIXPACKS and stop committing `backend/static/`.

**Architecture:** Add a `[phases.build]` to `nixpacks.toml` that runs `cd frontend && npm ci && npm run build` + asserts the bundle exists; gitignore + untrack `backend/static/`; add a CI check that the bundle stays untracked; fix stale docs.

**Tech Stack:** Railway + NIXPACKS (v1.41.0, confirmed), Vite 5, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-05-25-frontend-build-at-deploy-design.md`

**⚠️ DEPLOY-CONTRACT CHANGE.** Merging triggers a production deploy that newly builds the frontend on Railway. **Hard prerequisite before merge:** `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` set in Railway (build-time). Do NOT auto-merge; merge manually after the prerequisite is confirmed, then watch the deploy. Rollback = Railway deployment rollback.

---

## Task 1: Add the NIXPACKS build phase

**Files:**
- Modify: `nixpacks.toml`

- [ ] **Step 1: Replace `nixpacks.toml` with:**

```toml
providers = ["python", "node"]

# Build the Vite frontend at deploy. The deploy serves backend/static
# directly (Flask static_folder), so it must be produced here — the repo
# no longer commits it. `cd frontend && npm ci` installs the FRONTEND deps
# (the auto root `npm ci` only covers the small root package.json); the
# build emits to ../backend/static per frontend/vite.config.js. The assert
# fails the deploy loudly if no bundle was produced (the /healthz
# healthcheck passes without a frontend, so it can't catch this).
[phases.build]
dependsOn = ["install"]
cmds = [
  "cd frontend && npm ci && npm run build",
  "test -s backend/static/index.html",
]

[start]
cmd = "cd backend && gunicorn app:app --bind 0.0.0.0:$PORT"
```

- [ ] **Step 2: Validate TOML parses**

Run: `python3 -c "import tomllib; tomllib.load(open('nixpacks.toml','rb')); print('toml ok')"`
Expected: `toml ok`

- [ ] **Step 3: Confirm NIXPACKS recognizes the build phase (plan-only, no Docker needed)**

Run: `npx --yes nixpacks plan . 2>/dev/null | grep -A6 -i "build" || echo "PLAN-UNAVAILABLE"`
Expected: a `build` phase listing the `cd frontend && npm ci && npm run build` cmd. If it prints `PLAN-UNAVAILABLE` (npx/nixpacks can't run here), note it and rely on the first Railway build log instead — do NOT treat unavailability as failure.

- [ ] **Step 4: Verify the build itself works locally (Linux-equivalent output not required — just that it builds + emits index.html)**

Run: `cd frontend && npm ci && npm run build && test -s ../backend/static/index.html && echo "BUILD-OK"`
Expected: `BUILD-OK`.

- [ ] **Step 5: Commit**

```bash
git add nixpacks.toml
git commit -m "build(deploy): build frontend in nixpacks build phase + assert bundle exists"
```

---

## Task 2: Stop committing `backend/static/`

**Files:**
- Modify: `.gitignore`
- Untrack: `backend/static/` (keep local copy)

- [ ] **Step 1: Add to `.gitignore`.** Append this line to `.gitignore` (create the file if absent):

```
/backend/static/
```

- [ ] **Step 2: Untrack the committed bundle (keep the working-tree copy)**

Run: `git rm -r --cached backend/static`
Expected: lists the removed-from-index files; `backend/static/` still present on disk.

- [ ] **Step 3: Verify it's now ignored and untracked**

Run: `git check-ignore backend/static/index.html && test -z "$(git ls-files backend/static)" && echo "UNTRACKED-AND-IGNORED"`
Expected: `UNTRACKED-AND-IGNORED`.

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "build(deploy): gitignore + untrack backend/static (built at deploy now)"
```

---

## Task 3: CI guard — keep the bundle untracked

**Files:**
- Modify: `.github/workflows/ci.yml` (the `frontend-build` job)

- [ ] **Step 1: Add an untracked-assert step after the `Build` step.** In the `frontend-build` job, after:

```yaml
      - name: Build
        run: cd frontend && npm run build
```

append:

```yaml

      - name: Assert backend/static is not committed
        run: |
          if [ -n "$(git ls-files backend/static)" ]; then
            echo "::error::backend/static/ is tracked in git. It is built at deploy now and must stay gitignored — run 'git rm -r --cached backend/static' and commit."
            exit 1
          fi
```

- [ ] **Step 2: Validate workflow YAML parses**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok')"`
Expected: `yaml ok`

- [ ] **Step 3: Locally simulate the guard.** In sync (expect pass):

Run: `test -z "$(git ls-files backend/static)" && echo "GUARD-PASS"`
Expected: `GUARD-PASS` (bundle is untracked after Task 2).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(frontend): assert backend/static stays untracked (built at deploy)"
```

---

## Task 4: Fix stale docs

**Files:**
- Modify: `frontend/src/services/supabase.js` (comment only)
- Modify: `CLAUDE.md` (deploy section)

- [ ] **Step 1: Fix the `supabase.js` comment.** Replace the comment block at lines ~20-22 that reads:

```
  // Production (Railway) has VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY
  // set, so this branch is never reached there. CI's frontend build
  // step doesn't set them, hence the dummy fallback.
```

with:

```
  // The frontend is built at deploy (Railway/NIXPACKS), so VITE_SUPABASE_URL
  // + VITE_SUPABASE_ANON_KEY MUST be set as Railway build-time variables —
  // otherwise the deployed bundle falls through to the dummy values below and
  // auth breaks. CI's frontend build doesn't set them, hence the dummy
  // fallback there is expected.
```

- [ ] **Step 2: Update CLAUDE.md deploy note.** Find the line in the Deployment section describing the frontend build (currently: *"Frontend: Built with `cd frontend && npm run build`, output goes to `backend/static/`. Deployed with the backend via Railway."*) and replace it with:

```
- **Frontend**: Built **at deploy** by Railway/NIXPACKS (`nixpacks.toml` `[phases.build]` runs `cd frontend && npm run build` → `backend/static/`). `backend/static/` is **gitignored** (no longer committed). Requires `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` set as Railway build variables. For local dev, run `cd frontend && npm run build` to populate `backend/static/`, or use `npm run dev` (Vite dev server, port 5180, proxies `/api`).
```

- [ ] **Step 3: Verify supabase.js still parses (build smoke)**

Run: `cd frontend && npx vite build >/dev/null 2>&1 && echo "VITE-OK"; cd ..; git checkout -- backend/static 2>/dev/null; git clean -fdq backend/static 2>/dev/null; true`
Expected: `VITE-OK` (comment change didn't break the build). The checkout/clean restores the (gitignored, untracked) working copy state — harmless.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/supabase.js CLAUDE.md
git commit -m "docs: reflect build-at-deploy + Railway VITE_ requirement"
```

---

## Task 5: PR, verify CI, gated merge, watch deploy

**Files:** none (PR + deploy verification)

- [ ] **Step 1: Push + open PR**

```bash
git push -u origin chore/frontend-build-at-deploy
gh pr create --base main --title "build(deploy): build frontend at deploy; stop committing backend/static" \
  --body "Implements docs/superpowers/specs/2026-05-25-frontend-build-at-deploy-design.md. Root-cause fix for committed-bundle staleness + cross-OS build non-determinism: NIXPACKS [phases.build] builds the frontend at deploy; backend/static gitignored. DEPLOY-CONTRACT CHANGE — requires VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY set in Railway before merge. Supersedes the closed Approach-A guard (#584)."
```

- [ ] **Step 2: Confirm CI green.** `Frontend Build` (build + vitest + untracked-assert), `Frontend E2E Smoke` (builds fresh via playwright webServer), `Backend Tests`, and the rest must pass.

Run (after settle): `gh pr checks <PR#>` → all required pass.

- [ ] **Step 3: HARD GATE — confirm the Railway prerequisite with the maintainer.** Do not merge until the maintainer confirms `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` are set in Railway (build-time). This is a human confirmation, not a code check.

- [ ] **Step 4: Merge manually (NOT auto).** `gh pr merge <PR#> --squash --delete-branch`.

- [ ] **Step 5: Watch the Railway deploy build log.** Confirm it shows the `vite build` running and the `test -s backend/static/index.html` assert passing. If the build fails, the deploy won't promote (good) — diagnose from the log.

- [ ] **Step 6: Post-deploy app verification.** Load the production app: `/` serves the SPA (not a 404), and login uses the real Supabase project (view-source / network shows the real `VITE_SUPABASE_URL`, not `dummy.supabase.co`). If broken, **roll back** the Railway deployment immediately.

- [ ] **Step 7: Clean up superseded artifacts.** The Approach-A guard spec/plan
  (`docs/superpowers/specs/2026-05-25-frontend-bundle-staleness-ci-guard-design.md` and the matching
  plan) are superseded — leave them (history) but they're referenced as closed in this spec §8. No action needed unless the maintainer wants them deleted.

---

## Self-Review (completed during plan authoring)

- **Spec coverage:** D1 → Task 1; D2 → Task 2; D3 → Task 1 (assert in build cmds); D4 → Task 5 Step 3 (hard gate); D5 → Task 3; doc fixes (§4.5) → Task 4; risks/verification (§5/§7) → Task 1 Steps 3-4 + Task 5 Steps 2,5,6.
- **Placeholder scan:** none — exact file contents + commands. (`<PR#>` is a runtime value.)
- **Consistency:** `[phases.build]` cmds, `backend/static` path, the untracked-assert (`git ls-files backend/static`), and the `VITE_` var names are identical across spec + plan.
- **Highest-risk ordering:** the Railway `VITE_` prerequisite is a hard human gate BEFORE merge (Task 5 Step 3); merge is manual; the deploy is actively watched with rollback ready (Steps 5-6).
