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
  // Don't start server — assume it's already running
  // Run: cd backend && python app.py (in another terminal)
})
