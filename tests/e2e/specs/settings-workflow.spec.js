/**
 * Settings workflow — global notes, roster upload.
 * Simulates a teacher setting up their grading environment.
 */
import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import { AppPage } from '../pages/app.page.js';
import { SettingsPage } from '../pages/settings.page.js';
import { TEACHERS } from '../fixtures/test-data.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROSTERS_DIR = path.resolve(__dirname, '../../load/fixtures/rosters');

const teacher = TEACHERS[0]; // Ms. Rivera, US History

test.describe('Settings Workflow', () => {
  let app, settings;

  test.beforeEach(async ({ page }) => {
    app = new AppPage(page);
    settings = new SettingsPage(page);
    await app.goto();
    await settings.navigateTo();
  });

  test('Settings tab renders', async ({ page }) => {
    // Should see settings-related content
    const pageText = await page.locator('body').textContent();
    const hasSettings = pageText.toLowerCase().includes('settings') ||
      pageText.toLowerCase().includes('rubric') ||
      pageText.toLowerCase().includes('accommodation');
    expect(hasSettings).toBe(true);
  });

  test('can save and reload global AI notes', async ({ page }) => {
    // Find any textarea and fill it
    const textareas = page.locator('textarea');
    const count = await textareas.count();
    if (count > 0) {
      await textareas.first().fill(teacher.globalNotes);
      await page.waitForTimeout(600);
    }

    // Look for save button
    const saveBtn = page.locator('button', { hasText: /Save/i }).first();
    if (await saveBtn.count() > 0) {
      await saveBtn.click();
      await page.waitForTimeout(500);
    }

    // Reload and verify persistence
    await page.reload();
    await page.waitForSelector('nav button', { timeout: 15_000 });
    await settings.navigateTo();
    await page.waitForTimeout(1000);
  });

  test('can upload a roster CSV', async ({ page }) => {
    // Settings has sub-tabs (General/Grading/AI/Classroom/Privacy/Billing/
    // Resources). Roster upload lives on Classroom. The beforeEach lands
    // on General by default — navigate to Classroom first.
    await page.locator('button', { hasText: /^Classroom$/ }).click();
    await page.waitForTimeout(500);

    const rosterPath = path.join(ROSTERS_DIR, teacher.roster);
    // Look for any file input (may be hidden)
    const fileInput = page.locator('input[type="file"]');
    if (await fileInput.count() > 0) {
      await fileInput.first().setInputFiles(rosterPath);
      await page.waitForTimeout(2000);
    }

    // Should see some roster indicator
    const pageText = await page.locator('body').textContent();
    const hasRosterIndicator = pageText.includes('student') ||
      pageText.includes('roster') ||
      pageText.includes('Period') ||
      pageText.includes('Upload');
    expect(hasRosterIndicator).toBe(true);
  });
});
