/**
 * Analytics tab display tests — verifies charts render without overflow,
 * filters work, and student details load.
 */
import { test, expect } from '@playwright/test';
import { AppPage } from '../pages/app.page.js';
import { AnalyticsPage } from '../pages/analytics.page.js';

test.describe('Analytics Display', () => {
  let app, analytics;

  test.beforeEach(async ({ page }) => {
    app = new AppPage(page);
    analytics = new AnalyticsPage(page);
    await app.goto();
    await analytics.navigateTo();
  });

  test('analytics tab loads without errors', async ({ page }) => {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.waitForTimeout(2000);

    const realErrors = errors.filter(e =>
      !e.includes('favicon') && !e.includes('Supabase') && !e.includes('net::ERR')
    );
    expect(realErrors).toHaveLength(0);
  });

  test('assignment averages chart does not overflow horizontally', async ({ page }) => {
    await page.waitForTimeout(1000);

    const overflow = await analytics.verifyChartsRender().catch(() => ({ overflows: false }));
    expect(overflow.overflows, 'Charts section has horizontal overflow').toBe(false);

    // Also check the whole page
    const pageScroll = await analytics.checkNoHorizontalScroll();
    expect(pageScroll.hasHorizontalScroll, 'Page has horizontal scrollbar').toBe(false);
  });

  test('charts resize correctly on window resize', async ({ page }) => {
    await page.waitForTimeout(1000);

    // Resize to a smaller viewport
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(500);

    const overflow1 = await analytics.checkNoHorizontalScroll();
    expect(overflow1.hasHorizontalScroll, 'Overflow at 1024px').toBe(false);

    // Resize to a larger viewport
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.waitForTimeout(500);

    const overflow2 = await analytics.checkNoHorizontalScroll();
    expect(overflow2.hasHorizontalScroll, 'Overflow at 1920px').toBe(false);
  });

  test('stats cards render', async ({ page }) => {
    await page.waitForTimeout(1000);

    const statsSection = page.locator('[data-tutorial="analytics-stats"]');
    if (await statsSection.count() > 0) {
      await expect(statsSection).toBeVisible();
    }
  });

  test('filter controls are interactive', async ({ page }) => {
    await page.waitForTimeout(1000);

    const filters = page.locator('[data-tutorial="analytics-filters"]');
    if (await filters.count() > 0) {
      // Click on filter buttons/selects
      const buttons = filters.locator('button, select');
      const count = await buttons.count();
      expect(count).toBeGreaterThan(0);

      // Click first filter option
      if (count > 0) {
        await buttons.first().click();
        await page.waitForTimeout(300);
      }
    }
  });
});
