#!/usr/bin/env node
/**
 * Focus Assignment/Assessment Automation
 * Creates assignments and assessments in Focus gradebook via Playwright.
 *
 * Reads VPortal credentials from ~/.graider_data/portal_credentials.json
 * (set via Graider Settings > Tools > District Portal)
 *
 * Usage:
 *   node focus-automation.js assignment --name "Quiz 1" --category "Assessments" --points 100 --date "02/10/2026"
 *   node focus-automation.js assessment --name "Unit Test" --points 100 --date "02/15/2026"
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// Load credentials from local config
const CREDS_PATH = path.join(process.env.HOME, '.graider_data', 'portal_credentials.json');

function loadCredentials() {
  if (!fs.existsSync(CREDS_PATH)) {
    console.error('Error: VPortal credentials not configured.');
    console.error('Go to Graider Settings > Tools > District Portal to save your credentials.');
    process.exit(1);
  }

  try {
    const data = JSON.parse(fs.readFileSync(CREDS_PATH, 'utf-8'));
    const email = data.email;
    const password = Buffer.from(data.password, 'base64').toString();
    if (!email || !password) {
      console.error('Error: Credentials file is incomplete.');
      process.exit(1);
    }
    return { email, password };
  } catch (e) {
    console.error('Error reading credentials:', e.message);
    process.exit(1);
  }
}

async function login(page, creds) {
  console.log('Navigating to VPortal...');
  await page.goto('https://vportal.volusia.k12.fl.us/');

  console.log('Entering credentials...');
  await page.fill('input[type="email"], input[name="loginfmt"]', creds.email);
  await page.click('input[type="submit"], button[type="submit"]');
  await page.waitForTimeout(1000);

  await page.fill('input[type="password"], input[name="passwd"]', creds.password);
  await page.click('input[type="submit"], button[type="submit"]');

  console.log('Waiting for 2FA - check your phone...');
  console.log('Waiting up to 60 seconds for 2FA approval...');

  try {
    await page.waitForURL('**/proofup**', { timeout: 60000 });
    console.log('2FA approved! Handling stay signed in prompt...');
    await page.click('input[type="submit"][value="Yes"], input[value="Yes"]');
  } catch (e) {
    console.log('Checking if already logged in...');
  }

  await page.waitForTimeout(2000);
  console.log('Logged in to VPortal');
}

async function navigateToFocus(page) {
  console.log('Navigating to Focus...');

  const focusLink = page.locator('a:has-text("Focus"), a[title*="Focus"], div:has-text("Focus")').first();

  if (await focusLink.isVisible().catch(() => false)) {
    await focusLink.click();
    console.log('Clicked Focus tile');
  } else {
    console.log('Trying direct Focus URL...');
    await page.goto('https://focus.volusia.k12.fl.us/focus/');
  }

  await page.waitForTimeout(3000);
  console.log('In Focus');
}

async function createAssignment(page, { name, category, points, date, description }) {
  console.log('Creating assignment: ' + name);

  console.log('Opening Gradebook...');
  const gradebookLink = page.locator('a:has-text("Gradebook"), button:has-text("Gradebook"), a[href*="gradebook"]').first();
  await gradebookLink.click();
  await page.waitForTimeout(2000);

  console.log('Opening new assignment form...');
  const addAssignmentBtn = page.locator(
    'button:has-text("Add Assignment"), ' +
    'button:has-text("New Assignment"), ' +
    'a:has-text("Add Assignment"), ' +
    'button[title*="Add Assignment"]'
  ).first();
  await addAssignmentBtn.click();
  await page.waitForTimeout(1500);

  console.log('Filling assignment details...');

  const nameField = page.locator('input[name*="name"], input[id*="name"], input[placeholder*="name"]').first();
  await nameField.fill(name);
  console.log('  Name: ' + name);

  if (category) {
    const categoryDropdown = page.locator('select[name*="category"], select[id*="category"], select[name*="type"]').first();
    await categoryDropdown.selectOption({ label: category });
    console.log('  Category: ' + category);
  }

  if (points) {
    const pointsField = page.locator('input[name*="points"], input[id*="points"], input[name*="score"]').first();
    await pointsField.fill(points.toString());
    console.log('  Points: ' + points);
  }

  if (date) {
    const dateField = page.locator('input[name*="date"], input[id*="date"], input[type="date"]').first();
    await dateField.fill(date);
    console.log('  Date: ' + date);
  }

  if (description) {
    const descField = page.locator('textarea[name*="description"], textarea[id*="description"]').first();
    if (await descField.isVisible().catch(() => false)) {
      await descField.fill(description);
      console.log('  Description: ' + description.substring(0, 50) + '...');
    }
  }

  console.log('Assignment form filled (ready for manual review/save)');
}

async function createAssessment(page, { name, points, date, description }) {
  console.log('Creating assessment: ' + name);

  console.log('Opening Gradebook...');
  const gradebookLink = page.locator('a:has-text("Gradebook"), button:has-text("Gradebook"), a[href*="gradebook"]').first();
  await gradebookLink.click();
  await page.waitForTimeout(2000);

  console.log('Opening new assessment form...');
  const addAssessmentBtn = page.locator(
    'button:has-text("Add Assessment"), ' +
    'button:has-text("New Assessment"), ' +
    'a:has-text("Add Assessment")'
  ).first();

  if (await addAssessmentBtn.isVisible().catch(() => false)) {
    await addAssessmentBtn.click();
  } else {
    console.log('No separate assessment button, using assignment form...');
    const addAssignmentBtn = page.locator('button:has-text("Add Assignment"), a:has-text("Add Assignment")').first();
    await addAssignmentBtn.click();
  }

  await page.waitForTimeout(1500);

  console.log('Filling assessment details...');

  const nameField = page.locator('input[name*="name"], input[id*="name"]').first();
  await nameField.fill(name);
  console.log('  Name: ' + name);

  const categoryDropdown = page.locator('select[name*="category"], select[id*="category"]').first();
  if (await categoryDropdown.isVisible().catch(() => false)) {
    try {
      await categoryDropdown.selectOption({ label: 'Assessment' });
      console.log('  Category: Assessment');
    } catch (e) {
      console.log('  (No Assessment category found in dropdown)');
    }
  }

  if (points) {
    const pointsField = page.locator('input[name*="points"], input[id*="points"]').first();
    await pointsField.fill(points.toString());
    console.log('  Points: ' + points);
  }

  if (date) {
    const dateField = page.locator('input[name*="date"], input[id*="date"], input[type="date"]').first();
    await dateField.fill(date);
    console.log('  Date: ' + date);
  }

  if (description) {
    const descField = page.locator('textarea[name*="description"], textarea[id*="description"]').first();
    if (await descField.isVisible().catch(() => false)) {
      await descField.fill(description);
      console.log('  Description: ' + description.substring(0, 50) + '...');
    }
  }

  console.log('Assessment form filled (ready for manual review/save)');
}

// CLI argument parsing
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || !['assignment', 'assessment'].includes(command)) {
    console.error('Usage: node focus-automation.js <assignment|assessment> [options]');
    console.error('');
    console.error('Options:');
    console.error('  --name "Assignment Name"     (required)');
    console.error('  --category "Category"        (optional, e.g., "Assessments", "Classwork")');
    console.error('  --points 100                 (optional)');
    console.error('  --date "MM/DD/YYYY"          (optional)');
    console.error('  --description "Description"  (optional)');
    console.error('');
    console.error('Examples:');
    console.error('  node focus-automation.js assignment --name "Quiz 1" --category "Assessments" --points 100 --date "02/10/2026"');
    console.error('  node focus-automation.js assessment --name "Unit Test" --points 100 --date "02/15/2026"');
    process.exit(1);
  }

  const getArg = (flag) => {
    const idx = args.indexOf(flag);
    return idx !== -1 && args[idx + 1] ? args[idx + 1] : null;
  };

  const name = getArg('--name');
  const category = getArg('--category');
  const points = getArg('--points') ? parseInt(getArg('--points')) : null;
  const date = getArg('--date');
  const description = getArg('--description');

  if (!name) {
    console.error('Error: --name is required');
    process.exit(1);
  }

  const creds = loadCredentials();
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await login(page, creds);
    await navigateToFocus(page);

    if (command === 'assignment') {
      await createAssignment(page, { name, category, points, date, description });
    } else if (command === 'assessment') {
      await createAssessment(page, { name, points, date, description });
    }

    console.log('');
    console.log('Form ready for review. Browser will stay open for 2 minutes...');
    console.log('Review the details and click Save manually.');
    await page.waitForTimeout(120000); // 2 minutes

  } catch (error) {
    console.error('Error:', error.message);
    await page.screenshot({ path: 'focus-error.png' });
    console.error('Screenshot saved to focus-error.png');
  } finally {
    await browser.close();
  }
}

main();
