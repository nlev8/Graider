import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './specs',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // Sequential within file, parallel across files
  retries: 1,
  workers: 3, // Simulate 3 concurrent teachers
  reporter: [
    ['html', { open: 'never', outputFolder: '../reports/e2e' }],
    ['list'],
  ],
  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // 2026-05-13: switched from 'retain-on-failure' to 'on-first-retry'
    // to remove first-attempt capture overhead. retain-on-failure had
    // the same execution cost as `on` (only retention differed), which
    // caused timing regressions in CI (~24m frontend step). on-first-retry
    // only traces retries (which already run anyway), giving zero
    // first-attempt overhead while preserving diagnostic data for real
    // failures.
    trace: 'on-first-retry',
    actionTimeout: 10_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium', viewport: { width: 1440, height: 900 } },
    },
  ],
  // 2026-05-12 (audit MAJOR #5 Phase 3 Task 2): webServer enabled so
  // this project no longer requires an externally-running backend.
  // Mirrors frontend/playwright.config.js pattern with two
  // differences:
  //   - Working directory is tests/e2e/, so `cd ../..` lands at repo
  //     root before launching backend/app.py.
  //   - `npm run build` is NOT included — backend/static/ is expected
  //     to be pre-populated by the workflow (or by a manual
  //     `cd frontend && npm run build` for local dev).
  //
  // `reuseExistingServer: true` skips the command when a backend is
  // already listening on port 3000. The e2e-nightly workflow spawns
  // one backend job-level and runs BOTH this project AND
  // frontend/playwright.config.js against it.
  webServer: {
    command: 'cd ../.. && ${PYTHON:-./venv/bin/python} backend/app.py',
    // Env defaults for the local-dev path so a clean shell
    // (no FLASK_ENV / FLASK_SECRET_KEY exported) can still spawn
    // the backend without it crashing on startup. CI workflows
    // override these via their own env block. Per Codex+Gemini
    // review of Phase 3 Stage 3a.
    env: {
      FLASK_ENV: process.env.FLASK_ENV || 'development',
      FLASK_SECRET_KEY: process.env.FLASK_SECRET_KEY || 'local-dev-only-not-for-production',
    },
    url: 'http://localhost:3000',
    reuseExistingServer: process.env.E2E_REUSE_BACKEND === '1' || !process.env.CI,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
