# Frontend Build-at-Deploy (retire the committed bundle) — Design Spec

**Date:** 2026-05-25
**Status:** Approved (brainstorm + 3-AI consult + deploy-log verification) — ready for implementation plan
**Author:** Claude (3-AI consult: Codex 5.5-high decisional + Gemini advisory)

---

## 1. Goal

Build the React/Vite frontend **at deploy time on Railway/NIXPACKS** and **stop committing
`backend/static/`** — eliminating the committed-build-artifact problem class entirely: bundle
staleness (the #582/#583 incident) *and* cross-OS build non-determinism (which killed the CI
staleness guard).

## 2. Background (verified, not inferred)

**Confirmed from a real Railway deploy build log (2026-05-25):** the NIXPACKS build runs
`pip install -r requirements.txt`, root `npm ci` (root `package.json` only — "added 2 packages"),
`COPY . /app`, then `cd backend && gunicorn app:app`. **There is no `npm run build` / vite step.**
Therefore Railway **serves the committed `backend/static/`**; the frontend is not built at deploy.

Consequences that motivated this change:
- Frontend source can only reach production by a **manual** `npm run build` + commit of
  `backend/static/`. This drifted 9 days / 24 commits behind source (the #582/#583 incident);
  #583's bundle commit was *necessary*, not optional.
- A CI "committed bundle == fresh build" guard (Approach A) is **unworkable**: the Vite bundle is
  **not byte-deterministic across OS** — a macOS-committed `index` chunk (`index-B_LOblC4.js`)
  differs from a Linux CI build (`index-D3ha6CKq.js`) for identical source, so the guard red-flags
  every PR. (Verified in CI on PR #584, now closed.)
- Both consult models (Codex, Gemini) ranked **build-at-deploy** the correct root-cause fix.

**Stale doc note:** `frontend/src/services/supabase.js:20-22` claims "Production (Railway) has
VITE_… set" — currently inaccurate (Railway doesn't build the frontend, so those vars are inert; the
committed bundle's Supabase config comes from the committer's local `frontend/.env`). After this
change the comment becomes accurate **iff** the Railway `VITE_` vars are set (see §4 / §6).

## 3. Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Build the frontend in `nixpacks.toml` `[phases.build]` | Version-controlled, explicit, reviewed; least deploy-contract change. (Consult #1. Rejected: root `package.json` build script — implicit; Railway dashboard cmd — not in repo; Dockerfile — overkill.) |
| D2 | gitignore + `git rm --cached backend/static` | Committed build artifacts are the root cause; keeping them reintroduces drift and can mask a broken deploy build. |
| D3 | Build-time assert `test -s backend/static/index.html` | Fail the deploy loudly if the build didn't produce a bundle (the `/healthz` healthcheck passes without a frontend, so it can't catch this). |
| D4 | Set `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` in Railway **before** merge | Vite inlines these at build; the Railway build env currently lacks them (confirmed: not in the build ARG/ENV list), so without this the deploy ships dummy-Supabase / broken auth. |
| D5 | CI: keep Frontend Build (build + vitest); add a "`backend/static` is untracked" check | Platform-independent replacement for the dead staleness guard — prevents anyone re-committing the bundle. |

## 4. Design

### 4.1 `nixpacks.toml`
```toml
providers = ["python", "node"]

[phases.build]
dependsOn = ["install"]
cmds = [
  "cd frontend && npm ci && npm run build",
  "test -s backend/static/index.html",
]

[start]
cmd = "cd backend && gunicorn app:app --bind 0.0.0.0:$PORT"
```
- `node` is available via `providers`; `cd frontend && npm ci` installs the **frontend** deps
  (the auto root `npm ci` only covers the small root `package.json`). `npm run build` emits to
  `../backend/static` (per `frontend/vite.config.js` `outDir`, `emptyOutDir: true`).
- Each `cmds` entry runs from the app root (`/app`); cmd 1 `cd`s in a subshell, so cmd 2's
  `test -s backend/static/index.html` correctly resolves from `/app`.
- Build output written to `backend/static/` persists into the runtime image (default NIXPACKS
  behavior copies the app dir); gunicorn then serves it. `railway.json`/`Procfile` start commands
  are unchanged.

### 4.2 Stop committing the bundle
- `.gitignore`: add `/backend/static/`.
- `git rm -r --cached backend/static` (untrack; keep the local working copy so local `backend/app.py`
  can still serve it).

### 4.3 CI (`.github/workflows/ci.yml`)
- **Keep** the `Frontend Build` job (builds + vitest count-floor) as the source-level gate.
- **Add** a step asserting the bundle is no longer tracked:
  `test -z "$(git ls-files backend/static)"` → fails if someone re-commits `backend/static/`.
- `Frontend E2E Smoke` is unaffected — playwright's `webServer` already runs `npm run build` before
  spawning the backend. `Backend Tests` is unaffected — no backend test requires a built
  `index.html` (no test GETs `/`).

### 4.4 Local dev
Developers populate `backend/static/` locally with `cd frontend && npm run build` (now gitignored),
or use the Vite dev server (`npm run dev`, port 5180, proxies `/api` → :3000). Documented in CLAUDE.md.

### 4.5 Doc fixes
- Update `frontend/src/services/supabase.js:20-22` comment to reflect build-at-deploy + the Railway
  `VITE_` requirement.
- Update CLAUDE.md deploy section: frontend now built at deploy; `backend/static/` is gitignored.

## 5. Risks & mitigations
- **Cannot pre-test the Railway build locally** (no `nixpacks` CLI / Docker). Mitigations:
  `npx nixpacks plan .` pre-merge to confirm the build phase is recognized (plan-only, no Docker);
  the build-time `index.html` assert; post-deploy verification; Railway rollback ready.
- **`VITE_` misconfig → dummy Supabase / broken auth, fails silently** (assert + healthcheck won't
  catch it). Mitigation: D4 prerequisite (set the two vars in Railway **before** merge) + post-deploy
  manual check that `/` serves the SPA and login hits the real Supabase (not `dummy.supabase.co`).
- **NIXPACKS phase assumptions** (node available at build, output persists). Consult says fine; the
  deploy build log confirms `nixpacks-v1.41.0` is the active builder (so Codex's "Railpack migration"
  concern is moot here). First-deploy log is the proof.

## 6. Pre-deploy checklist (owner: maintainer — MUST precede merge)
1. In Railway → service → Variables, set **`VITE_SUPABASE_URL`** and **`VITE_SUPABASE_ANON_KEY`**
   (same values as your local `frontend/.env`). These must be available at **build** time.
2. Confirm the first deploy after merge: build log shows `vite build` + the `index.html` assert
   passing; the app at `/` serves the SPA; login uses real Supabase. Roll back if not.

## 7. Verification
- **Pre-merge local:** `cd frontend && npm ci && npm run build && test -s ../backend/static/index.html`
  succeeds; `git check-ignore backend/static/index.html` confirms ignored; `git ls-files backend/static`
  is empty after `git rm --cached`. `npx nixpacks plan .` shows the `build` phase running the frontend build.
- **CI (the PR's run):** `Frontend Build` green (build + vitest + untracked-assert); `Frontend E2E
  Smoke` green (builds fresh); `Backend Tests` green.
- **Deploy (the real test):** Railway build log shows the vite build + assert; manual app check + rollback ready.

## 8. References
- Consult prompt: `/tmp/nixpacks_consult.md` (this session).
- Verified deploy build log (2026-05-25, shows no frontend build) — user-provided.
- Closed dead end: PR #584 (Approach A guard) + spec/plan
  `2026-05-25-frontend-bundle-staleness-ci-guard-*` (superseded by this).
- Incident: PRs #582 (source fix), #583 (manual bundle rebuild).
