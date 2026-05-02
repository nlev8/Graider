import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    // Playwright E2E specs live under e2e/ and use the Playwright test
    // runner — they're not Vitest-compatible. Excluding here so
    // `npm test` only runs Vitest unit/integration tests.
    // Match e2e at any depth so the exclude works whether vitest is invoked
    // from frontend/ or from the repo root.
    exclude: ['**/e2e/**', '**/node_modules/**', '**/dist/**'],
  },
})
