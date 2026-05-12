/**
 * Planner workflow — standards browsing, lesson generation UI.
 */
import { test, expect } from '@playwright/test';
import { AppPage } from '../pages/app.page.js';
import { PlannerPage } from '../pages/planner.page.js';
import { TEACHERS } from '../fixtures/test-data.js';

const teacher = TEACHERS[0];

test.describe('Planner Workflow', () => {
  let app, planner;

  test.beforeEach(async ({ page }) => {
    app = new AppPage(page);
    planner = new PlannerPage(page);
    await app.goto();
    await planner.navigateTo();
  });

  test('planner tab renders with standards', async ({ page }) => {
    const hasStandards = await planner.hasStandards();
    expect(hasStandards).toBe(true);
  });

  test('can interact with title input', async ({ page }) => {
    const inputs = page.locator('input, textarea, select');
    const count = await inputs.count();
    expect(count).toBeGreaterThan(0);
    await planner.setTitle(teacher.lessonTopic);
  });

  test('generate/create button is present', async ({ page }) => {
    const hasBtn = await planner.hasGenerateButton();
    expect(hasBtn).toBe(true);
  });
});
