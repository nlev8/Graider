# Focus Automation Script

Playwright script to automate assignment/assessment creation in Focus gradebook.

## Setup (One-time)

```bash
# Install Playwright
npm install playwright

# Install Chromium browser
npx playwright install chromium
```

## Usage

### Create Assignment
```bash
node focus-automation.js assignment --name "Quiz 1" --category "Assessments" --points 100 --date "02/10/2026"
```

### Create Assessment
```bash
node focus-automation.js assessment --name "Unit Test" --points 100 --date "02/15/2026"
```

### With Description
```bash
node focus-automation.js assignment --name "Homework 3" --category "Classwork" --points 50 --date "02/12/2026" --description "Read chapters 4-5"
```

## Options

- `--name` (required) - Assignment/assessment name
- `--category` (optional) - Category like "Assessments", "Classwork", etc.
- `--points` (optional) - Point value
- `--date` (optional) - Due date in MM/DD/YYYY format
- `--description` (optional) - Description text

## How It Works

1. Logs into VPortal with your credentials
2. Waits for 2FA approval (check phone ending in 40)
3. Navigates to Focus gradebook
4. Fills out assignment/assessment form
5. Leaves browser open for manual review/save

## Script Code

```javascript
#!/usr/bin/env node
/**
 * Focus Assignment/Assessment Automation
 * Creates assignments and assessments in Focus gradebook
 * 
 * Usage:
 *   node focus-automation.js assignment --name "Quiz 1" --category "Assessments" --points 100 --date "02/10/2026"
 *   node focus-automation.js assessment --name "Unit Test" --points 100 --date "02/15/2026"
 */

const { chromium } = require('playwright');

// Credentials
const VPORTAL_EMAIL = 'acrionas@volusia.k12.fl.us';
const VPORTAL_PASSWORD = 'Rasmusmylove1!!';

async function login(page) {
  console.log('Navigating to VPortal...');
  await page.goto('https://vportal.volusia.k12.fl.us/');
  
  console.log('Entering credentials...');
  await page.fill('input[type="email"], input[name="loginfmt"]', VPORTAL_EMAIL);
  await page.click('input[type="submit"], button[type="submit"]');
  await page.waitForTimeout(1000);
  
  await page.fill('input[type="password"], input[name="passwd"]', VPORTAL_PASSWORD);
  await page.click('input[type="submit"], button[type="submit"]');
  
  console.log('⚠️  Waiting for 2FA - check your phone ending in 40');
  console.log('Waiting up to 60 seconds for 2FA approval...');
  
  try {
    await page.waitForURL('**/proofup**', { timeout: 60000 });
    console.log('2FA approved! Handling stay signed in prompt...');
    await page.click('input[type="submit"][value="Yes"], input[value="Yes"]');
  } catch (e) {
    console.log('Checking if already logged in...');
  }
  
  await page.waitForTimeout(2000);
  console.log('✓ Logged in to VPortal');
}

async function navigateToFocus(page) {
  console.log('Navigating to Focus...');
  
  // Look for Focus link/tile in VPortal
  const focusLink = page.locator('a:has-text("Focus"), a[title*="Focus"], div:has-text("Focus")').first();
  
  if (await focusLink.isVisible().catch(() => false)) {
    await focusLink.click();
    console.log('Clicked Focus tile');
  } else {
    // Try direct URL
    console.log('Trying direct Focus URL...');
    await page.goto('https://focus.volusia.k12.fl.us/focus/');
  }
  
  await page.waitForTimeout(3000);
  console.log('✓ In Focus');
}

async function createAssignment(page, { name, category, points, date, description }) {
  console.log(`Creating assignment: ${name}`);
  
  // Navigate to gradebook/assignments section
  console.log('Opening Gradebook...');
  const gradebookLink = page.locator('a:has-text("Gradebook"), button:has-text("Gradebook"), a[href*="gradebook"]').first();
  await gradebookLink.click();
  await page.waitForTimeout(2000);
  
  // Look for "Add Assignment" or "New Assignment" button
  console.log('Opening new assignment form...');
  const addAssignmentBtn = page.locator(
    'button:has-text("Add Assignment"), ' +
    'button:has-text("New Assignment"), ' +
    'a:has-text("Add Assignment"), ' +
    'button[title*="Add Assignment"]'
  ).first();
  await addAssignmentBtn.click();
  await page.waitForTimeout(1500);
  
  // Fill assignment details
  console.log('Filling assignment details...');
  
  // Assignment name
  const nameField = page.locator('input[name*="name"], input[id*="name"], input[placeholder*="name"]').first();
  await nameField.fill(name);
  console.log(`  Name: ${name}`);
  
  // Category/Type dropdown
  if (category) {
    const categoryDropdown = page.locator('select[name*="category"], select[id*="category"], select[name*="type"]').first();
    await categoryDropdown.selectOption({ label: category });
    console.log(`  Category: ${category}`);
  }
  
  // Points
  if (points) {
    const pointsField = page.locator('input[name*="points"], input[id*="points"], input[name*="score"]').first();
    await pointsField.fill(points.toString());
    console.log(`  Points: ${points}`);
  }
  
  // Date
  if (date) {
    const dateField = page.locator('input[name*="date"], input[id*="date"], input[type="date"]').first();
    await dateField.fill(date);
    console.log(`  Date: ${date}`);
  }
  
  // Description (if exists)
  if (description) {
    const descField = page.locator('textarea[name*="description"], textarea[id*="description"]').first();
    if (await descField.isVisible().catch(() => false)) {
      await descField.fill(description);
      console.log(`  Description: ${description.substring(0, 50)}...`);
    }
  }
  
  console.log('✓ Assignment form filled (ready for manual review/save)');
}

async function createAssessment(page, { name, points, date, description }) {
  console.log(`Creating assessment: ${name}`);
  
  // Similar to assignment but may have different fields
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
  
  // If no specific assessment button, use regular assignment button
  if (await addAssessmentBtn.isVisible().catch(() => false)) {
    await addAssessmentBtn.click();
  } else {
    console.log('No separate assessment button, using assignment form...');
    const addAssignmentBtn = page.locator('button:has-text("Add Assignment"), a:has-text("Add Assignment")').first();
    await addAssignmentBtn.click();
  }
  
  await page.waitForTimeout(1500);
  
  // Fill assessment details (similar to assignment)
  console.log('Filling assessment details...');
  
  const nameField = page.locator('input[name*="name"], input[id*="name"]').first();
  await nameField.fill(name);
  console.log(`  Name: ${name}`);
  
  // Try to select "Assessment" category if exists
  const categoryDropdown = page.locator('select[name*="category"], select[id*="category"]').first();
  if (await categoryDropdown.isVisible().catch(() => false)) {
    try {
      await categoryDropdown.selectOption({ label: 'Assessment' });
      console.log(`  Category: Assessment`);
    } catch (e) {
      console.log('  (No Assessment category found in dropdown)');
    }
  }
  
  if (points) {
    const pointsField = page.locator('input[name*="points"], input[id*="points"]').first();
    await pointsField.fill(points.toString());
    console.log(`  Points: ${points}`);
  }
  
  if (date) {
    const dateField = page.locator('input[name*="date"], input[id*="date"], input[type="date"]').first();
    await dateField.fill(date);
    console.log(`  Date: ${date}`);
  }
  
  if (description) {
    const descField = page.locator('textarea[name*="description"], textarea[id*="description"]').first();
    if (await descField.isVisible().catch(() => false)) {
      await descField.fill(description);
      console.log(`  Description: ${description.substring(0, 50)}...`);
    }
  }
  
  console.log('✓ Assessment form filled (ready for manual review/save)');
}

// CLI argument parsing
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  
  if (!command || !['assignment', 'assessment'].includes(command)) {
    console.error('Usage: node focus-automation.js <assignment|assessment> [options]');
    console.error('\nOptions:');
    console.error('  --name "Assignment Name"     (required)');
    console.error('  --category "Category"        (optional, e.g., "Assessments", "Classwork")');
    console.error('  --points 100                 (optional)');
    console.error('  --date "MM/DD/YYYY"          (optional)');
    console.error('  --description "Description"  (optional)');
    console.error('\nExamples:');
    console.error('  node focus-automation.js assignment --name "Quiz 1" --category "Assessments" --points 100 --date "02/10/2026"');
    console.error('  node focus-automation.js assessment --name "Unit Test" --points 100 --date "02/15/2026"');
    process.exit(1);
  }
  
  // Parse arguments
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
  
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  try {
    await login(page);
    await navigateToFocus(page);
    
    if (command === 'assignment') {
      await createAssignment(page, { name, category, points, date, description });
    } else if (command === 'assessment') {
      await createAssessment(page, { name, points, date, description });
    }
    
    console.log('\n✓ Form ready for review. Browser will stay open for 2 minutes...');
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
```

## Notes

- Script handles VPortal login and 2FA automatically
- Leaves browser open for manual review before saving
- Takes screenshot on errors (focus-error.png)
- Browser stays open for 2 minutes to verify form
