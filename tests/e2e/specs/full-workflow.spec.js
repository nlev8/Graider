/**
 * Full teacher workflow — end-to-end from setup to analytics.
 * Simulates a teacher's typical session across all tabs.
 */
import { test, expect } from '@playwright/test';
import path from 'path';
import { TEACHERS } from '../fixtures/test-data.js';

const teacher = TEACHERS[0]; // Ms. Rivera

/** Helper to click a sidebar tab */
async function clickTab(page, name) {
  await page.locator('nav button', { hasText: name }).click();
  await page.waitForTimeout(400);
}

test.describe('Full Teacher Workflow', () => {

  test('complete teacher session: settings -> builder -> grade -> results -> analytics', async ({ page }) => {
    test.setTimeout(90_000);

    // 1. Load App
    await page.goto('/');
    await page.waitForSelector('nav button', { timeout: 15_000 });

    // 2. Settings
    await clickTab(page, 'Settings');
    const textareas = page.locator('textarea');
    if (await textareas.count() > 0) {
      await textareas.first().fill(teacher.globalNotes);
      await page.waitForTimeout(600);
    }

    // 3. Builder
    await clickTab(page, 'Grading Setup');
    const builderContent = await page.locator('body').textContent();
    expect(builderContent.length).toBeGreaterThan(100);

    // 4. Grade Tab
    await clickTab(page, 'Grade');
    const gradeContent = await page.locator('body').textContent();
    expect(gradeContent.toLowerCase()).toContain('grad');

    // 5. Results Tab
    await clickTab(page, 'Results');
    const resultsContent = await page.locator('body').textContent();
    expect(resultsContent.length).toBeGreaterThan(50);

    // 6. Analytics Tab
    await clickTab(page, 'Analytics');
    await page.waitForTimeout(1000);

    // Verify no horizontal overflow (regression test)
    const scroll = await page.evaluate(() => ({
      bodyW: document.body.scrollWidth,
      winW: window.innerWidth,
    }));
    expect(scroll.bodyW).toBeLessThanOrEqual(scroll.winW + 5);

    // 7. Planner Tab
    await clickTab(page, 'Planner');
    const titleInput = page.locator('input[placeholder*="Causes"]');
    if (await titleInput.count() > 0) {
      await titleInput.first().fill(teacher.lessonTopic);
    }

    // 8. Assistant Tab
    await clickTab(page, 'Assistant');
    const assistantContent = await page.locator('body').textContent();
    expect(assistantContent.length).toBeGreaterThan(50);

    // 9. Rapid cycle all tabs for stability
    const allTabs = ['Grade', 'Results', 'Analytics', 'Planner', 'Settings', 'Assistant'];
    for (const tab of allTabs) {
      await clickTab(page, tab);
      const body = await page.locator('body').textContent();
      expect(body.length).toBeGreaterThan(50);
    }
  });

  test('app handles rapid tab switching without crashing', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('nav button', { timeout: 15_000 });

    const tabs = ['Grade', 'Results', 'Analytics', 'Planner', 'Settings', 'Assistant'];

    // Rapid fire — switch tabs every 100ms, 3 rounds
    for (let round = 0; round < 3; round++) {
      for (const tab of tabs) {
        await page.locator('nav button', { hasText: tab }).click();
        await page.waitForTimeout(100);
      }
    }

    // App should still be responsive
    await clickTab(page, 'Grade');
    const body = await page.locator('body').textContent();
    expect(body.length).toBeGreaterThan(50);
  });

  test('app handles viewport resize gracefully', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('nav button', { timeout: 15_000 });

    const viewports = [
      { width: 1920, height: 1080 },
      { width: 1440, height: 900 },
      { width: 1024, height: 768 },
    ];

    for (const vp of viewports) {
      await page.setViewportSize(vp);
      await page.waitForTimeout(300);

      const scroll = await page.evaluate(() => ({
        bodyW: document.body.scrollWidth,
        winW: window.innerWidth,
      }));
      expect(
        scroll.bodyW,
        `Horizontal overflow at ${vp.width}x${vp.height}`
      ).toBeLessThanOrEqual(scroll.winW + 5);
    }
  });
});
