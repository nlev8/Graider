/**
 * Multi-teacher concurrent simulation.
 * Spawns 3 browser contexts simultaneously and runs them through
 * full workflows to test stability under concurrent use.
 */
import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import { TEACHERS } from '../fixtures/test-data.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROSTERS_DIR = path.resolve(__dirname, '../../load/fixtures/rosters');

/** Helper to click a sidebar tab */
async function clickTab(page, name) {
  await page.locator('nav button', { hasText: name }).click();
  await page.waitForTimeout(300);
}

test.describe('Concurrent Multi-Teacher Simulation', () => {

  test.skip('3 teachers complete full workflows concurrently', async ({ browser }) => {
    // Deeper than originally tracked: not just a header-injection issue.
    // Even with X-Test-Teacher-Id forcing distinct teacher_ids:
    //   1. approval_status (auth_routes.py:110) only bypasses for the
    //      literal `local-dev` — other dev-shim teacher_ids would hit
    //      Supabase admin.get_user_by_id which 500s in CI.
    //   2. _use_supabase (storage.py:115) returns False when Supabase
    //      isn't configured, falling back to the file backend.
    //      _key_to_filepath uses HARDCODED paths (no per-teacher
    //      directory), so all teacher_ids would still share
    //      ~/.graider_settings.json — the race the test was trying to
    //      avoid in the first place.
    // True multi-teacher isolation in CI requires either a Supabase
    // fixture or a per-teacher file-backend path scheme. Tracked in #370.
    test.setTimeout(120_000);

    const results = [];

    const teacherRuns = TEACHERS.map(async (teacher) => {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      const log = (step, status, detail = '') => {
        results.push({ teacher: teacher.name, step, status, detail });
        console.log(`  [${teacher.name}] ${status === 'pass' ? '+' : status === 'skip' ? '-' : 'X'} ${step} ${detail}`);
      };

      try {
        // Step 1: Load app
        await page.goto('http://localhost:3000');
        await page.waitForSelector('nav button', { timeout: 15_000 });
        log('app_load', 'pass');

        // Step 2: Navigate to Settings
        await clickTab(page, 'Settings');
        log('settings_nav', 'pass');

        // Step 3: Fill global notes
        const textareas = page.locator('textarea');
        if (await textareas.count() > 0) {
          await textareas.first().fill(teacher.globalNotes);
          await page.waitForTimeout(600);
          log('set_global_notes', 'pass');
        } else {
          log('set_global_notes', 'skip', 'no textarea found');
        }

        // Step 4: Upload roster
        const rosterPath = path.join(ROSTERS_DIR, teacher.roster);
        const fileInput = page.locator('input[type="file"]');
        if (await fileInput.count() > 0) {
          await fileInput.first().setInputFiles(rosterPath);
          await page.waitForTimeout(2000);
          log('upload_roster', 'pass');
        } else {
          log('upload_roster', 'skip', 'no file input found');
        }

        // Step 5: Analytics — verify no overflow
        await clickTab(page, 'Analytics');
        await page.waitForTimeout(500);
        const scrollCheck = await page.evaluate(() => ({
          bodyW: document.body.scrollWidth,
          winW: window.innerWidth,
        }));
        if (scrollCheck.bodyW <= scrollCheck.winW + 5) {
          log('analytics_no_overflow', 'pass');
        } else {
          log('analytics_no_overflow', 'fail', `body=${scrollCheck.bodyW} window=${scrollCheck.winW}`);
        }

        // Step 6: Planner
        await clickTab(page, 'Planner');
        const titleInput = page.locator('input[placeholder*="Causes"]');
        if (await titleInput.count() > 0) {
          await titleInput.first().fill(teacher.lessonTopic);
          log('planner_topic', 'pass');
        } else {
          log('planner_topic', 'skip', 'title input not found');
        }

        // Step 7: Grade tab
        await clickTab(page, 'Grade');
        log('grade_nav', 'pass');

        // Step 8: Results tab
        await clickTab(page, 'Results');
        log('results_nav', 'pass');

        // Step 9: Builder tab
        await clickTab(page, 'Grading Setup');
        log('builder_nav', 'pass');

        // Step 10: Rapid tab cycle
        const tabNames = ['Grade', 'Results', 'Analytics', 'Planner', 'Settings'];
        for (const tab of tabNames) {
          await page.locator('nav button', { hasText: tab }).click();
          await page.waitForTimeout(150);
        }
        log('rapid_tab_cycle', 'pass');

      } catch (err) {
        log('CRASH', 'fail', err.message.slice(0, 120));
        await page.screenshot({
          path: `tests/reports/e2e/screenshots/fail_${teacher.id}.png`,
          fullPage: true,
        }).catch(() => {});
      } finally {
        await context.close();
      }
    });

    // Run all 3 teachers simultaneously
    await Promise.all(teacherRuns);

    // Summary
    const passed = results.filter(r => r.status === 'pass').length;
    const failed = results.filter(r => r.status === 'fail').length;
    const skipped = results.filter(r => r.status === 'skip').length;
    console.log(`\n  Multi-teacher results: ${passed} pass, ${failed} fail, ${skipped} skip`);

    const failures = results.filter(r => r.status === 'fail');
    expect(failures, 'Some teacher workflows failed').toHaveLength(0);
  });
});
