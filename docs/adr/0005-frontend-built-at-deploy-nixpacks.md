# ADR 0005 — Frontend built at deploy by Railway/NIXPACKS; `backend/static/` gitignored

- **Status:** Accepted
- **Date recorded:** 2026-06-10 (decision predates this record)

## Context

The Flask app serves the Vite-built SPA directly from `backend/static/`.
Originally the build output was committed to the repo, which meant every
frontend change produced huge binary-ish diffs, PRs conflicted on bundle
files, and a stale committed bundle could silently ship.

A subtler hazard: the SPA needs `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY`
inlined at build time. A build that runs without them "succeeds" but ships
the `https://dummy.supabase.co` fallback literal — auth breaks silently, and
`/healthz` cannot catch it because it only checks the *backend* Supabase
client.

## Decision

1. **`backend/static/` is gitignored; the bundle is produced at deploy** by
   the NIXPACKS `[phases.build]` in `nixpacks.toml` (`cd frontend && npm ci
   && npm run build` → `../backend/static` per `frontend/vite.config.js`).
2. **The build fails loud, not silent**, via four guards in the build phase:
   assert `VITE_*` vars are present in the build env; force-feed them into
   the `npm run build` subshell (covers env inheritance + busts the layer
   cache when values change); assert `backend/static/index.html` is
   non-empty; grep the built JS for the *real* configured URL (the dummy
   literal is always present, so the check greps *for* the real value, not
   against the dummy).
3. **Non-web services opt out per-service:** worker/beat services share the
   repo and this `nixpacks.toml` but set `SKIP_FRONTEND_BUILD=true`; a guard
   prefix makes each build cmd a no-op so those services neither pay the
   build cost nor need `VITE_*` vars.
4. CI enforces the gitignore: the Frontend Build job asserts
   `backend/static` is not committed (`.github/workflows/ci.yml`).

## Consequences

- Local dev must populate `backend/static/` explicitly (`cd frontend && npm
  run build`) or use the Vite dev server (`npm run dev`, port 5180, proxies
  `/api`).
- `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` are required **build**
  variables on the Railway web service; forgetting them fails the deploy at
  build time (by design) instead of shipping broken auth.
- Deploys are slower (every deploy rebuilds the frontend), accepted in
  exchange for a repo with no build artifacts and no stale-bundle class of
  incident.

## Evidence

- `nixpacks.toml` (header comment documents all four guards and the
  `SKIP_FRONTEND_BUILD` opt-out)
- `CLAUDE.md` § "Deployment"
- `.github/workflows/ci.yml` Frontend Build job ("Assert backend/static is
  not committed" step)
