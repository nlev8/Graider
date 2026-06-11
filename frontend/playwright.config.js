import { defineConfig } from '@playwright/test'

// E2E_BASE_URL override (hardening sprint PR5): lets a local verification
// run point at a backend spawned on a non-default port (PORT env, see
// backend/app.py) — e.g. a GRAIDER_FAKE_SUPABASE=1 backend on :3100 while
// the regular dev server keeps :3000. CI never sets it; default unchanged.
const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000'

export default defineConfig({
  testDir: './e2e',
  timeout: 45000,
  retries: 1,
  workers: 2,  // Limit parallelism to reduce API contention
  use: {
    baseURL: BASE_URL,
    headless: true,
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
  // Closes audit MINOR (Codex full-codebase audit 2026-05-06, GH #219):
  // Playwright now boots the backend automatically. Locally we reuse a
  // running server if one is already on port 3000 (preserves the dev
  // workflow where you have `python backend/app.py` running in another
  // terminal).
  //
  // The backend serves the Vite-built frontend from backend/static/, so
  // `npm run build` runs first to populate that directory. The Python
  // binary is taken from `PYTHON` env var when set (CI), otherwise the
  // local venv at ../venv/bin/python (matches CLAUDE.md venv path).
  //
  // 2026-05-12 (audit MAJOR #5 Phase 3): `reuseExistingServer`
  // logic extended with an opt-in env var. Default behavior
  // unchanged (`!process.env.CI` reuses locally, forces spawn in
  // CI). The new e2e-nightly workflow spawns ONE backend at the job
  // level and runs BOTH this config and tests/e2e/playwright.config.js
  // against it; setting E2E_REUSE_BACKEND=1 in that workflow tells
  // Playwright to reuse rather than spawn a conflicting second
  // backend. Per Codex review of Phase 3 Stage 3a, keeping the smoke
  // job's "always-fresh-server" semantics unchanged.
  webServer: {
    command: 'npm run build && (cd .. && ${PYTHON:-./venv/bin/python} backend/app.py)',
    url: BASE_URL,
    reuseExistingServer: process.env.E2E_REUSE_BACKEND === '1' || !process.env.CI,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
