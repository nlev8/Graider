import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 45000,
  retries: 1,
  workers: 2,  // Limit parallelism to reduce API contention
  use: {
    baseURL: 'http://localhost:3000',
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
  // 2026-05-12 (audit MAJOR #5 Phase 3): `reuseExistingServer` flipped
  // from `!process.env.CI` to `true`. The new e2e-nightly workflow
  // spawns the backend at the job level so both this config and the
  // sibling tests/e2e/playwright.config.js can share one backend
  // process; without `true` in CI, Playwright would attempt to spawn
  // a second backend on port 3000 and conflict. Falls back to
  // spawning via the command below when no backend is already up
  // (local dev path).
  webServer: {
    command: 'npm run build && (cd .. && ${PYTHON:-./venv/bin/python} backend/app.py)',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
