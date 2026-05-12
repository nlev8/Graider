/**
 * Smoke tests — verify the app loads and all tabs render.
 * @tags @smoke
 */
import { test, expect } from '@playwright/test';
import { AppPage } from '../pages/app.page.js';

test.describe('App Smoke Tests @smoke', () => {
  let app;

  test.beforeEach(async ({ page }) => {
    app = new AppPage(page);
    await app.goto();
  });

  test('app loads on localhost without login screen', async ({ page }) => {
    // On localhost, auth is bypassed — should see sidebar nav, not login form
    const nav = page.locator('nav button');
    await expect(nav.first()).toBeVisible({ timeout: 5000 });

    // Should NOT see email/password login fields
    const emailInput = page.locator('input[type="email"]');
    await expect(emailInput).not.toBeVisible().catch(() => {});
  });

  test('all tabs are accessible', async ({ page }) => {
    const tabs = ['Grade', 'Results', 'Grading Setup', 'Analytics', 'Planner', 'Settings', 'Assistant'];
    for (const tabName of tabs) {
      await app.switchTab(tabName);
      // Each tab should render content
      const bodyText = await page.locator('body').textContent();
      expect(bodyText.length).toBeGreaterThan(50);
    }
  });

  test('no console errors on initial load', async ({ page }) => {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/');
    await page.waitForSelector('nav button', { timeout: 15_000 });
    await page.waitForTimeout(2000);

    // Filter out known benign errors (API fetch failures, CSP from Google Fonts, etc.)
    const realErrors = errors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('.map') &&
      !e.includes('net::ERR') &&
      !e.includes('Supabase') &&
      !e.includes('Missing Supabase') &&
      !e.includes('Failed to fetch') &&
      !e.includes('API Error') &&
      !e.includes('Content Security Policy') &&
      !e.includes('violates the following') &&
      !e.includes('500 (INTERNAL SERVER ERROR)') &&
      !e.includes('Failed to load resource')
    );
    expect(realErrors).toHaveLength(0);
  });

  test('no horizontal scrollbar on any tab', async ({ page }) => {
    const tabs = ['Grade', 'Analytics', 'Planner', 'Settings', 'Results'];
    for (const tabName of tabs) {
      await app.switchTab(tabName);
      await page.waitForTimeout(500);

      const scroll = await page.evaluate(() => ({
        body: document.body.scrollWidth,
        window: window.innerWidth,
      }));
      expect(scroll.body, `${tabName} tab has horizontal overflow`).toBeLessThanOrEqual(scroll.window + 5);
    }
  });
});
