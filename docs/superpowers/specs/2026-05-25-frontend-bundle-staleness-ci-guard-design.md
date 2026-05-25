# Frontend Bundle-Staleness CI Guard — Design Spec

**Date:** 2026-05-25
**Status:** Approved (brainstorm + 3-AI consult complete) — ready for implementation plan
**Author:** Claude (3-AI consult: Codex 5.5-high decisional + Gemini advisory)

---

## 1. Goal

Make CI **fail** when the committed `backend/static/` frontend bundle is stale relative to the
frontend source — so a frontend change can never again merge without its built bundle, silently
failing to deploy.

## 2. Background & the problem

The React/Vite frontend builds to `backend/static/`, which is **committed to git** and served
**directly** by Flask at runtime (`Flask(__name__, static_folder='static', static_url_path='')`).
The Railway/NIXPACKS deploy runs only gunicorn — **it does not rebuild the frontend** — so the
committed bundle *is* the deployed frontend.

Because the rebuild-and-commit step is manual, `backend/static/` fell **9 days / 24 `frontend/src`
commits** behind source (caught 2026-05-25), silently shipping none of them — including a
user-facing crash fix (#487) and the ClassLink auth fix (#582), until a manual rebuild (#583).
Nothing in CI detected the drift.

## 3. Decisions (brainstorm + consult)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Approach A — strict byte-diff guard, now** | Both models: verifies served == source exactly; catches "forgot to rebuild" *and* "wrong/partial bundle". (Heuristic "src changed but static didn't" rejected by both as too weak.) |
| D2 | **Fold into the existing "Frontend Build" job** | That job already runs `npm ci` + `npm run build`; reusing it avoids adding a new required check (branch protection pins 9 checks by name). |
| D3 | **Pin canonical Node = 24** (not the current CI 20) | Node 20 is EOL (May 2026); 24 is current LTS, is what local dev uses, **and is what the merged #583 bundle was built with** — so the guard passes on the current bundle with no rebuild dance. |
| D4 | **Approach C (build-at-deploy, stop committing the bundle) deferred** | Both models rank C the superior long-term architecture, but it changes the deploy contract (NIXPACKS/Railway build) and needs its own careful PR. Filed as follow-up; out of scope here. |

## 4. Design

### 4.1 Node version pinning
- Add **`.nvmrc`** at repo root containing `24`.
- Add `engines: { "node": "24.x" }` to `frontend/package.json` (documents + npm-warns on mismatch).
- Update **both** CI `setup-node` blocks (the `Frontend Build` job and the `Frontend E2E Smoke` job)
  from `node-version: '20'` to `node-version-file: .nvmrc`, keeping `cache: 'npm'` +
  `cache-dependency-path: frontend/package-lock.json`. This makes CI's build environment canonical
  and identical to local (`.nvmrc`).

### 4.2 The guard step
In the `Frontend Build` job, immediately **after** the `Build` step (`cd frontend && npm run build`),
add:

```yaml
      - name: Verify committed frontend bundle is current
        run: |
          if ! git diff --exit-code -- backend/static; then
            echo "::error::backend/static is stale: a fresh Vite build changed the committed bundle. The deploy serves backend/static directly (no build at deploy), so run 'cd frontend && npm run build' (Node per .nvmrc) and commit backend/static, then push."
            exit 1
          fi
```

`npm run build` overwrites `backend/static/`; `git diff --exit-code` then fails (nonzero) iff the
fresh build differs from what was committed.

### 4.3 Determinism handling
- **One canonical build environment** (Node 24 via `.nvmrc`, deps via `npm ci` lockfile) eliminates
  cross-version drift — the only sanctioned builder is Node 24.
- The Vite production build emits **no sourcemaps** (verified: no `*.map` in `backend/static/assets/`),
  so the "absolute paths in sourcemaps" flakiness the consult flagged does not apply.
- **CI is authoritative.** If the committed bundle ever fails the guard, the fix is always: build
  with the `.nvmrc` Node version and commit `backend/static/` (never "normalize" or weaken the diff).

### 4.4 First-run expectation
#583's bundle was built with Node 24, so the Node-24 CI build should reproduce it and the guard
should pass on the first run. If a CI Node-24 *patch* difference produces a mismatch, the guard PR's
own CI run reveals it; resolve by committing the CI-built bundle once (CI is authoritative).

## 5. Out of scope (follow-up)
- **Approach C** — gitignore `backend/static/` and build the frontend at deploy time (NIXPACKS build
  phase / Railway build command) and/or deploy a CI-built artifact. The root-cause fix; tracked as a
  separate follow-up because it changes the deploy contract.
- A pre-commit hook (developer convenience; CI remains the authority) — not needed.
- CI auto-commit/bot-PR of the bundle — rejected (mutates reviewed code / messy history).

## 6. Testing & verification
- **Local guard-logic check (no CI needed):** from clean `main`, `cd frontend && npm run build` →
  `git diff --exit-code backend/static/` exits **0** (in sync). Then deliberately dirty the bundle
  (e.g., `echo x >> backend/static/index.html`) → `git diff --exit-code backend/static/` exits
  **nonzero** (proves the guard catches staleness). Restore afterward.
- **CI proof (the guard PR's own run):** `Frontend Build` must be green on Node 24 — i.e. the build
  succeeds, the vitest count-floor still passes on Node 24, AND the new guard step passes (committed
  bundle matches a Node-24 build). `Frontend E2E Smoke` must be green on Node 24.

## 7. Risks
- **Node 20 → 24 bump may surface a build/test incompatibility in CI.** Low: Vite 5 + Vitest support
  Node 24, and local Node 24 builds + #583's bundle came from Node 24. Verified by the PR's CI run; if
  vitest fails on 24, narrow scope by pinning `.nvmrc`=20 instead and doing a one-time Node-20 bundle
  rebuild (fallback).

## 8. References
- Consult prompt: `/tmp/bundle_guard_consult.md` (this session).
- The incident: PRs #582 (source fix) + #583 (manual bundle rebuild that shipped the 9-day backlog).
- CI: `.github/workflows/ci.yml` (`frontend-build` ~L53–83, `frontend-e2e-smoke` ~L85–161).
