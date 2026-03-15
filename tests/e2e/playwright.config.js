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
    trace: 'retain-on-failure',
    actionTimeout: 10_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium', viewport: { width: 1440, height: 900 } },
    },
  ],
  // Optionally start dev server
  // webServer: {
  //   command: 'cd ../../backend && FLASK_ENV=development python app.py',
  //   url: 'http://localhost:3000',
  //   reuseExistingServer: true,
  //   timeout: 15_000,
  // },
});
