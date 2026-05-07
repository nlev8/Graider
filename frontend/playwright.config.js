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
  // terminal); CI always spawns a fresh process.
  //
  // The backend serves the Vite-built frontend from backend/static/, so
  // `npm run build` runs first to populate that directory. The Python
  // binary is taken from `PYTHON` env var when set (CI), otherwise the
  // local venv at ../venv/bin/python (matches CLAUDE.md venv path).
  webServer: {
    command: 'npm run build && (cd .. && ${PYTHON:-./venv/bin/python} backend/app.py)',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
