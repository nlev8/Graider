#!/usr/bin/env node
/**
 * Focus Communications — Compose & Send
 * Automates sending email + SMS messages to students/parents through the
 * Focus SIS Communications module via Playwright.
 *
 * WORKFLOW:
 *   1. Login via VPortal → ADFS → 2FA
 *   2. Navigate to Focus → Communication → Compose
 *   3. For each message:
 *      a. Select the correct period/section
 *      b. Open student dropdown, select student
 *      c. Fill Subject, CC, email body
 *      d. (Optional) Click SMS tab, fill SMS body
 *      e. Click Send
 *      f. Navigate back to fresh Compose form
 *
 * Input JSON format:
 *   { "messages": [
 *       { "student_name": "Last, First",
 *         "subject": "Missing Assignment: ...",
 *         "email_body": "Dear Parent...",
 *         "sms_body": "Short SMS text",
 *         "cc_emails": ["parent@example.com"] }
 *   ]}
 *
 * Usage:
 *   node focus-comms.js [--dry-run] [--screenshot] <messages.json>
 *   node focus-comms.js --dry-run test-messages.json        # validate only, no browser
 *   node focus-comms.js --screenshot test-messages.json     # full run with screenshots
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');


// ══════════════════════════════════════════════════════════════
// CONSTANTS
// ══════════════════════════════════════════════════════════════

const GRAIDER_DATA_DIR = path.join(process.env.HOME, '.graider_data');
const CREDS_PATH = path.join(GRAIDER_DATA_DIR, 'portal_credentials.json');
const BROWSER_DATA_DIR = path.join(GRAIDER_DATA_DIR, 'focus_browser');
const ROSTER_PATH = path.join(GRAIDER_DATA_DIR, 'focus_roster_import.json');
const SCREENSHOTS_DIR = path.join(GRAIDER_DATA_DIR, 'focus_comms_screenshots');
const ERROR_SCREENSHOT = path.join(GRAIDER_DATA_DIR, 'focus-comms-error.png');

const FOCUS_BASE = 'https://volusia.focusschoolsoftware.com/focus';


// ══════════════════════════════════════════════════════════════
// UTILITIES
// ══════════════════════════════════════════════════════════════

function emit(type, data) {
  const event = Object.assign({ type: type, ts: new Date().toISOString() }, data || {});
  process.stdout.write(JSON.stringify(event) + '\n');
}

let screenshotsEnabled = false;
let screenshotCount = 0;

async function screenshot(page, label) {
  if (!screenshotsEnabled) return;
  screenshotCount++;
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  const filename = String(screenshotCount).padStart(3, '0') + '_' + label.replace(/[^a-zA-Z0-9]/g, '_') + '.png';
  const filepath = path.join(SCREENSHOTS_DIR, filename);
  await page.screenshot({ path: filepath, fullPage: false }).catch(() => {});
}

/**
 * Normalize student name for matching.
 * Focus uses "Last, First Middle" format.
 * Input may be "First Last", "First Middle Last", or "Last, First".
 */
function normalizeName(name) {
  if (!name) return { last: '', first: '', normalized: '' };
  const trimmed = name.trim();

  if (trimmed.includes(',')) {
    const parts = trimmed.split(',').map(p => p.trim());
    return {
      last: parts[0].toLowerCase(),
      first: parts[1] ? parts[1].split(/\s+/)[0].toLowerCase() : '',
      normalized: trimmed.toLowerCase(),
    };
  }

  const parts = trimmed.split(/\s+/);
  if (parts.length >= 2) {
    return {
      last: parts[parts.length - 1].toLowerCase(),
      first: parts[0].toLowerCase(),
      normalized: trimmed.toLowerCase(),
    };
  }

  return { last: trimmed.toLowerCase(), first: '', normalized: trimmed.toLowerCase() };
}

/**
 * Check if two student names match (flexible matching).
 * Handles "Last, First Middle" vs "First Middle Last".
 */
function namesMatch(name1, name2) {
  const n1 = normalizeName(name1);
  const n2 = normalizeName(name2);

  if (n1.normalized === n2.normalized) return true;

  if (n1.last && n2.last && n1.first && n2.first) {
    if (n1.last === n2.last && n1.first === n2.first) return true;
  }

  return false;
}


// ══════════════════════════════════════════════════════════════
// DATA LOADING
// ══════════════════════════════════════════════════════════════

function loadCredentials() {
  if (!fs.existsSync(CREDS_PATH)) {
    emit('error', { message: 'VPortal credentials not configured. Go to Settings > Tools > District Portal.' });
    process.exit(1);
  }
  try {
    const raw = JSON.parse(fs.readFileSync(CREDS_PATH, 'utf-8'));
    const email = raw.email;
    const password = Buffer.from(raw.password, 'base64').toString();
    if (!email || !password) {
      emit('error', { message: 'Credentials file is incomplete.' });
      process.exit(1);
    }
    return { email, password };
  } catch (e) {
    emit('error', { message: 'Error reading credentials: ' + e.message });
    process.exit(1);
  }
}

function loadRoster() {
  if (!fs.existsSync(ROSTER_PATH)) {
    emit('error', { message: 'Roster not found. Run focus-roster-import.js first.' });
    process.exit(1);
  }
  try {
    return JSON.parse(fs.readFileSync(ROSTER_PATH, 'utf-8'));
  } catch (e) {
    emit('error', { message: 'Error reading roster: ' + e.message });
    process.exit(1);
  }
}

/**
 * Find which period a student belongs to.
 * Returns { periodName, periodNum, student } or null.
 */
function findStudentPeriod(studentName, roster) {
  const periods = roster.periods || {};
  for (const [periodName, periodData] of Object.entries(periods)) {
    const students = periodData.students || [];
    for (const student of students) {
      if (namesMatch(studentName, student.name)) {
        // Extract the student's actual course code for this period from their schedule
        // This is needed to pick the correct section when multiple sections share a period number
        var courseCode = '';
        if (student.schedule && Array.isArray(student.schedule)) {
          for (var si = 0; si < student.schedule.length; si++) {
            if (student.schedule[si].period === periodData.period_num) {
              courseCode = student.schedule[si].course || '';
              break;
            }
          }
        }
        return {
          periodName: periodName,
          periodNum: periodData.period_num,
          courseCode: courseCode,
          student: student,
        };
      }
    }
  }
  return null;
}

/**
 * Load and validate messages from the input JSON file.
 */
function loadMessages(filepath) {
  if (!fs.existsSync(filepath)) {
    emit('error', { message: 'Messages file not found: ' + filepath });
    process.exit(1);
  }
  try {
    const data = JSON.parse(fs.readFileSync(filepath, 'utf-8'));
    if (!data.messages || !Array.isArray(data.messages)) {
      emit('error', { message: 'Invalid format: expected { "messages": [...] }' });
      process.exit(1);
    }
    return data.messages;
  } catch (e) {
    emit('error', { message: 'Error reading messages file: ' + e.message });
    process.exit(1);
  }
}

/**
 * Validate all messages against the roster.
 * Returns { valid: [...], errors: [...] }.
 */
function validateMessages(messages, roster) {
  const valid = [];
  const errors = [];

  for (var i = 0; i < messages.length; i++) {
    const msg = messages[i];
    const msgLabel = 'Message ' + (i + 1) + ' (' + (msg.student_name || 'unknown') + ')';

    if (!msg.student_name) {
      errors.push(msgLabel + ': missing student_name');
      continue;
    }
    if (!msg.subject) {
      errors.push(msgLabel + ': missing subject');
      continue;
    }
    if (!msg.email_body && !msg.sms_body) {
      errors.push(msgLabel + ': must have email_body or sms_body');
      continue;
    }
    if (msg.sms_body && msg.sms_body.length > 500) {
      errors.push(msgLabel + ': sms_body exceeds 500 chars (' + msg.sms_body.length + ')');
      continue;
    }

    const match = findStudentPeriod(msg.student_name, roster);
    if (!match) {
      errors.push(msgLabel + ': student not found in roster');
      continue;
    }

    valid.push({
      index: i,
      message: msg,
      periodName: match.periodName,
      periodNum: match.periodNum,
      courseCode: match.courseCode || '',
      student: match.student,
    });
  }

  return { valid, errors };
}


// ══════════════════════════════════════════════════════════════
// BROWSER AUTOMATION — Login
// ══════════════════════════════════════════════════════════════

async function login(page, creds) {
  emit('status', { message: 'Opening VPortal...' });
  await page.goto('https://vportal.volusia.k12.fl.us/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  try {
    await page.click('button.btn-saml', { timeout: 5000 });
    emit('status', { message: 'Clicked portal login, waiting for ADFS...' });
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForTimeout(2000);
  } catch (e) {
    emit('status', { message: 'No portal login button, may be past this step...' });
  }

  const currentUrl = page.url().toLowerCase();
  if (currentUrl.includes('adfs') || currentUrl.includes('login')) {
    try {
      emit('status', { message: 'Entering credentials on ADFS...' });
      await page.fill('#userNameInput', creds.email, { timeout: 5000 });
      await page.fill('#passwordInput', creds.password, { timeout: 5000 });
      await page.click('#submitButton');
      emit('status', { message: 'Signing in...' });
      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForTimeout(3000);
    } catch (e) {
      emit('status', { message: 'ADFS form not found, may already be authenticated...' });
    }
  }

  if (page.url().includes('login.microsoftonline.com') || page.url().includes('login.microsoft.com')) {
    emit('status', { message: 'Waiting for 2FA approval — check your phone...' });
    try {
      await page.waitForURL(
        url => !url.includes('login.microsoftonline.com') && !url.includes('login.microsoft.com'),
        { timeout: 120000 }
      );
      emit('status', { message: '2FA approved!' });
    } catch (e) {
      emit('status', { message: '2FA timed out, continuing...' });
    }
  }

  await page.waitForTimeout(2000);
  await screenshot(page, 'after_login');
  emit('status', { message: 'Logged in to VPortal' });
}


// ══════════════════════════════════════════════════════════════
// BROWSER AUTOMATION — Navigate to Communications
// ══════════════════════════════════════════════════════════════

async function navigateToFocus(page) {
  emit('status', { message: 'Navigating to Focus...' });
  await page.goto(
    FOCUS_BASE + '/Modules.php?modname=misc%2FPortal.php',
    { waitUntil: 'domcontentloaded', timeout: 30000 }
  );
  await page.waitForTimeout(3000);
  await screenshot(page, 'focus_portal');
  emit('status', { message: 'In Focus SIS' });
}

/**
 * Navigate to the Communications > Compose page.
 * Uses the left sidebar menu.
 *
 * From the screenshots, the sidebar has icon-only buttons on the far left.
 * Clicking the chat bubble icon (Communication) expands a sub-menu panel showing:
 *   Compose, Templates, Announcements, Inbox, Sent, Scheduled, Drafts,
 *   Polls, Communication, Archive, Settings
 *
 * The sub-menu items appear greyed out initially while the page loads.
 * We need to:
 *   1. Click the Communication sidebar icon to expand the sub-menu
 *   2. Wait for the page to fully load
 *   3. Click "Compose" in the sub-menu
 */
async function navigateToCommunications(page) {
  emit('status', { message: 'Opening Communication menu...' });

  // Click the Communication sidebar icon/group to expand the sub-menu.
  // Try multiple selectors since the sidebar structure varies.
  const sidebarSelectors = [
    'div.site-menu-group-title-text:has-text("Communication")',
    'div.site-menu-group-title:has-text("Communication")',
    // The sidebar icons — Communication is the chat bubble icon
    // From the screenshots, the icon-only sidebar is a column of clickable elements
  ];

  let menuExpanded = false;
  for (const sel of sidebarSelectors) {
    try {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 3000 }).catch(() => false)) {
        await el.click();
        menuExpanded = true;
        emit('status', { message: 'Expanded Communication menu with: ' + sel });
        break;
      }
    } catch (e) {}
  }

  if (!menuExpanded) {
    // Fallback: use evaluate to click any sidebar element that has "Communication" tooltip or text
    emit('status', { message: 'Trying evaluate to find Communication sidebar...' });
    const evalResult = await page.evaluate(() => {
      // Look for sidebar items with Communication text/title/tooltip
      const candidates = document.querySelectorAll('[title*="Communication"], [data-tooltip*="Communication"], [aria-label*="Communication"]');
      for (const el of candidates) {
        if (el.offsetParent !== null) {
          el.click();
          return 'Clicked element with title/tooltip: ' + (el.title || el.getAttribute('data-tooltip') || el.getAttribute('aria-label'));
        }
      }
      // Try any clickable element in the sidebar with Communication text
      const allEls = document.querySelectorAll('a, div, span, button');
      for (const el of allEls) {
        const text = el.textContent.trim();
        if (text === 'Communication' && el.offsetParent !== null) {
          el.click();
          return 'Clicked element with text "Communication"';
        }
      }
      return null;
    });

    if (evalResult) {
      menuExpanded = true;
      emit('status', { message: evalResult });
    }
  }

  if (!menuExpanded) {
    emit('error', { message: 'Could not find Communication menu in sidebar' });
    await screenshot(page, 'comm_menu_not_found');
    throw new Error('Communication menu not found');
  }

  // Wait for the sub-menu items to appear (not a fixed sleep)
  await page.waitForLoadState('domcontentloaded', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(500);
  await screenshot(page, 'comm_menu_open');

  // Click "Compose" sub-menu item
  await clickCompose(page);
}

/**
 * Click the "Compose" sub-menu item under Communication.
 * Used both for initial navigation and to reset between messages.
 *
 * NOTE: The sub-menu items may render as spans/divs (not <a> tags) and appear
 * greyed out while the page loads. We need to wait for them to become clickable.
 */
async function clickCompose(page) {
  emit('status', { message: 'Clicking Compose...' });

  // Brief settle before looking for Compose link
  await page.waitForTimeout(500);

  // Try multiple selectors — the items may be <a>, <span>, or <div> elements
  const composeSelectors = [
    'a:has-text("Compose")',
    'span:has-text("Compose")',
    'div:has-text("Compose"):not(:has(div:has-text("Compose")))',
    'text=Compose',
  ];

  let clicked = false;
  for (const sel of composeSelectors) {
    try {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 3000 }).catch(() => false)) {
        await el.click();
        clicked = true;
        emit('status', { message: 'Clicked Compose with: ' + sel });
        break;
      }
    } catch (e) {}
  }

  if (!clicked) {
    // Last resort: use page.evaluate to find and click the element by text content
    emit('status', { message: 'Trying evaluate click for Compose...' });
    const evalClicked = await page.evaluate(() => {
      // Look through all elements for one whose text is exactly "Compose"
      const all = document.querySelectorAll('a, span, div, li');
      for (const el of all) {
        if (el.textContent.trim() === 'Compose' && el.offsetParent !== null) {
          el.click();
          return true;
        }
      }
      return false;
    });

    if (evalClicked) {
      clicked = true;
      emit('status', { message: 'Clicked Compose via evaluate' });
    }
  }

  if (!clicked) {
    emit('error', { message: 'Could not find Compose menu item' });
    await screenshot(page, 'compose_not_found');
    throw new Error('Compose menu item not found');
  }

  // Wait for the Compose form to actually render (subject input appears)
  try {
    await page.locator('input[placeholder="New Message"], input[name="subject"], input[placeholder*="Subject"]').first().waitFor({ state: 'visible', timeout: 15000 });
  } catch (e) {
    // Fallback: brief wait if subject input not found by selectors
    await page.waitForTimeout(2000);
  }
  await screenshot(page, 'compose_page');
  emit('status', { message: 'Compose page loaded' });
}

/**
 * Navigate back to a fresh Compose form between messages.
 */
async function navigateToCompose(page) {
  await clickCompose(page);
}


// ══════════════════════════════════════════════════════════════
// BROWSER AUTOMATION — Compose & Send
// ══════════════════════════════════════════════════════════════

/**
 * Select the correct period/section in the top-right header dropdowns.
 * From the screenshot, the header bar has three dropdowns:
 *   "Teacher" | "GP 3" | "01 - USHADV01 - M/J US HIST ADV"
 * The period/section dropdown is the rightmost one with format "NN - CODE - COURSE NAME".
 *
 * We scan ALL <select> elements on the page and find the one whose options
 * match the "NN - CODE" pattern, then select the option matching our periodNum.
 */
async function selectPeriodSection(page, periodNum, courseCode) {
  emit('status', { message: 'Selecting period ' + periodNum + (courseCode ? ' (course: ' + courseCode + ')' : '') + '...' });

  const padded = String(periodNum).padStart(2, '0');

  // Scan all <select> elements to find the period dropdown
  const allSelects = await page.locator('select').all();
  emit('status', { message: 'Found ' + allSelects.length + ' select elements on page' });

  for (var si = 0; si < allSelects.length; si++) {
    const sel = allSelects[si];
    const opts = await sel.locator('option').all();
    let hasPeriodFormat = false;
    let allMatches = [];  // Collect ALL options matching this period number

    for (const opt of opts) {
      const text = (await opt.textContent().catch(() => '')).trim();
      // Match format like "01 - USHADV01 - M/J US HIST ADV"
      if (/^\d{2}\s*-\s*\w+/.test(text)) {
        hasPeriodFormat = true;
        const optNum = text.split(/[\s-]/)[0].replace(/^0+/, '');
        if (optNum === String(periodNum)) {
          allMatches.push({ text: text, value: await opt.getAttribute('value').catch(() => '') });
        }
      }
    }

    if (hasPeriodFormat && allMatches.length > 0) {
      // If multiple sections for the same period, use courseCode to disambiguate
      var matchOpt = allMatches[0];  // default to first match
      if (allMatches.length > 1 && courseCode) {
        var courseUpper = courseCode.toUpperCase();
        for (var mi = 0; mi < allMatches.length; mi++) {
          if (allMatches[mi].text.toUpperCase().indexOf(courseUpper) !== -1) {
            matchOpt = allMatches[mi];
            emit('status', { message: 'Disambiguated ' + allMatches.length + ' sections using course code ' + courseCode });
            break;
          }
        }
      }
      await sel.selectOption(matchOpt.value);
      emit('status', { message: 'Selected period: ' + matchOpt.text });
      await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
      await page.waitForTimeout(2000);
      await screenshot(page, 'period_selected');
      return true;
    }
  }

  // Fallback: try select[name="side_period"] (gradebook style)
  const periodSelect = page.locator('select[name="side_period"]').first();
  if (await periodSelect.isVisible({ timeout: 2000 }).catch(() => false)) {
    const options = await periodSelect.locator('option').all();
    for (const opt of options) {
      const text = (await opt.textContent().catch(() => '')).trim();
      const optNum = text.split(/[\s-]/)[0].replace(/^0+/, '');
      if (optNum === String(periodNum)) {
        const value = await opt.getAttribute('value').catch(() => '');
        await periodSelect.selectOption(value);
        emit('status', { message: 'Selected period via side_period: ' + text });
        await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
        await page.waitForTimeout(2000);
        await screenshot(page, 'period_selected');
        return true;
      }
    }
  }

  emit('warning', { message: 'Could not find period ' + periodNum + ' in any dropdown' });
  await screenshot(page, 'no_period_dropdown');
  return false;
}

/**
 * Select the recipient type from the dropdown.
 * This dropdown is the small icon/button to the left of the student picker ▼,
 * between the "Once Per Family" select and the recipient input field.
 * It controls who receives the message — students vs parents/guardians.
 *
 * Options: "Students", "Primary Contacts", "Once Per Family",
 *          "Teachers Of", "Students & Primary Contacts"
 *
 * @param {string} recipientType - e.g. "Primary Contacts" or "Students"
 */
async function selectRecipientType(page, recipientType) {
  recipientType = recipientType || 'Primary Contacts';
  emit('status', { message: 'Selecting "' + recipientType + '" recipient type...' });

  // The recipient type is a <select> in the recipient row (at ~y=154, ~x=231).
  // The select has no name attribute, so we find it by scanning all selects for the option text.
  var target = recipientType;
  const selected = await page.evaluate(function(target) {
    var selects = document.querySelectorAll('select');
    for (var i = 0; i < selects.length; i++) {
      var sel = selects[i];
      var rect = sel.getBoundingClientRect();
      if (rect.top < 100 || rect.top > 200) continue;
      for (var j = 0; j < sel.options.length; j++) {
        if (sel.options[j].text === target) {
          sel.selectedIndex = j;
          sel.dispatchEvent(new Event('change', { bubbles: true }));
          return true;
        }
      }
    }
    return false;
  }, target);

  if (selected) {
    emit('status', { message: 'Selected "' + recipientType + '"' });
    await page.waitForTimeout(1500);
    await screenshot(page, 'recipient_type_selected');
    return true;
  }

  emit('warning', { message: 'Could not find "' + recipientType + '" in recipient dropdown' });
  return false;
}


/**
 * Open the student dropdown (two-panel picker).
 *
 * From the screenshot, the recipient row has:
 *   person-icon | group-icon | [recipient input] | blue ▼ | 🔍 | "Letterhead"
 * The blue ▼ opens a two-panel picker:
 *   Left: Filter input, "Check all"/"Clear", student checkboxes "Last, First (CODE)"
 *   Right: Section list like "M/J US HIST ADV 01 01 - USHADV01 - Alexander Crionas"
 */
async function openStudentDropdown(page) {
  emit('status', { message: 'Opening student recipient picker...' });

  // IMPORTANT: There are multiple ▼ buttons on the Compose page:
  //   1. Header "Select Student ▼" — opens a simple student list (NO checkboxes)
  //   2. Recipient row ▼ — opens the TWO-PANEL picker WITH checkboxes and sections
  //   3. Staff row ▼ — opens staff picker
  //
  // We want #2 — the recipient row ▼ (the blue arrow in the first recipient row,
  // between the recipient input field and the 🔍 search icon).
  // It's a div.swift-box-button but NOT the first one on the page.
  //
  // From screenshots, the recipient row is at approximately y=145-165.
  // The header "Select Student" dropdown is at y≈25-35.

  // Find all swift-box-button elements and pick the one in the recipient row area
  const recipientBtn = await page.evaluate(() => {
    var buttons = document.querySelectorAll('div.swift-box-button');
    var candidates = [];
    for (var i = 0; i < buttons.length; i++) {
      var rect = buttons[i].getBoundingClientRect();
      candidates.push({
        index: i,
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        cx: Math.round(rect.x + rect.width / 2),
        cy: Math.round(rect.y + rect.height / 2),
        w: Math.round(rect.width),
        h: Math.round(rect.height),
      });
    }
    // The recipient row ▼ is in the area y=140-170 (below header, in the compose form)
    // Skip any at y < 100 (those are header elements like "Select Student")
    var recipient = null;
    for (var j = 0; j < candidates.length; j++) {
      var c = candidates[j];
      if (c.y > 130 && c.y < 180) {
        recipient = c;
        break;
      }
    }
    return { all: candidates, target: recipient };
  });

  emit('status', { message: 'Found ' + recipientBtn.all.length + ' swift-box-button(s): ' +
    recipientBtn.all.map(function(c) { return '(' + c.x + ',' + c.y + ')'; }).join(', ') });

  if (recipientBtn.target) {
    emit('status', { message: 'Clicking recipient ▼ at (' + recipientBtn.target.cx + ',' + recipientBtn.target.cy + ')' });
    await page.mouse.click(recipientBtn.target.cx, recipientBtn.target.cy);
    await page.waitForTimeout(2000);
    await screenshot(page, 'student_dropdown_open');

    // Verify: the two-panel picker has "Check all" / "Clear" and checkboxes
    const hasCheckAll = await page.evaluate(() => {
      var allEls = document.querySelectorAll('*');
      for (var i = 0; i < allEls.length; i++) {
        if ((allEls[i].textContent || '').trim() === 'Check all') return true;
      }
      return false;
    });

    if (hasCheckAll) {
      emit('status', { message: 'Recipient picker opened (has Check all)' });
      return true;
    }

    // If "Check all" not found, check for Filter input as fallback
    const filterVisible = await page.locator('input[placeholder="Filter..."]').first()
      .isVisible({ timeout: 2000 }).catch(() => false);
    if (filterVisible) {
      emit('status', { message: 'Recipient picker opened (has Filter input)' });
      return true;
    }

    emit('status', { message: 'Recipient ▼ click did not open the right dropdown, trying others...' });
  }

  // Fallback: try each swift-box-button in the y=100-200 range
  for (var i = 0; i < recipientBtn.all.length; i++) {
    var btn = recipientBtn.all[i];
    if (btn.y < 100 || btn.y > 200) continue;
    if (recipientBtn.target && btn.index === recipientBtn.target.index) continue; // already tried

    emit('status', { message: 'Trying swift-box-button [' + btn.index + '] at (' + btn.cx + ',' + btn.cy + ')' });
    await page.mouse.click(btn.cx, btn.cy);
    await page.waitForTimeout(2000);

    const hasCheckAll = await page.evaluate(() => {
      var allEls = document.querySelectorAll('*');
      for (var i = 0; i < allEls.length; i++) {
        if ((allEls[i].textContent || '').trim() === 'Check all') return true;
      }
      return false;
    });
    if (hasCheckAll) {
      emit('status', { message: 'Recipient picker opened via button [' + btn.index + ']' });
      await screenshot(page, 'student_dropdown_open');
      return true;
    }
  }

  emit('warning', { message: 'Could not open recipient picker dropdown' });
  await screenshot(page, 'no_student_dropdown');
  return false;
}

/**
 * Close the recipient picker dropdown and ensure the Email tab is active.
 * Clicking outside the dropdown can accidentally activate other tabs (Sign Up, File, etc.).
 * After closing, we explicitly click the "Email" tab button.
 */
async function closeDropdownAndEnsureEmailTab(page) {
  // Close the recipient picker dropdown by clicking the ▼ button again (toggle off).
  // Avoid Escape key and clicking random areas — those can activate unwanted tabs.
  const closeBtn = await page.evaluate(() => {
    var buttons = document.querySelectorAll('div.swift-box-button');
    for (var i = 0; i < buttons.length; i++) {
      var rect = buttons[i].getBoundingClientRect();
      // The recipient row ▼ is at y≈154
      if (rect.y > 130 && rect.y < 180) {
        return { cx: Math.round(rect.x + rect.width / 2), cy: Math.round(rect.y + rect.height / 2) };
      }
    }
    return null;
  });

  if (closeBtn) {
    await page.mouse.click(closeBtn.cx, closeBtn.cy);
    emit('status', { message: 'Toggled recipient ▼ to close dropdown' });
  } else {
    // Fallback: press Escape
    await page.keyboard.press('Escape');
  }
  await page.waitForTimeout(500);

  // Close any accidentally opened tabs (Sign Up, File, Poll, etc.)
  // Active tabs show as "✉ Email ✕ | ☐ Sign Up ✕" — each has a small ✕ to close it.
  // We find all elements containing ✕ in the tab row area and click those that aren't "Email".
  try {
    const closedTabs = await page.evaluate(() => {
      var closed = [];
      // The tab row is at approximately y=245-265 in the compose form.
      // Look for small clickable elements with ✕ text.
      var allEls = document.querySelectorAll('*');
      for (var i = 0; i < allEls.length; i++) {
        var el = allEls[i];
        var text = (el.textContent || '').trim();
        // Skip if it contains "Email" — we want to keep that tab
        if (text.toLowerCase().includes('email')) continue;
        // Look for the ✕ character in tab-like elements
        if (text === '\u2715' || text === '×' || text === '\u2717') {
          var rect = el.getBoundingClientRect();
          // Tab row area: y between 240 and 270, x between 220 and 500
          if (rect.top > 240 && rect.top < 270 && rect.left > 280 && rect.left < 500 &&
              rect.width < 20 && rect.height < 20) {
            el.click();
            closed.push({ x: Math.round(rect.left), y: Math.round(rect.top), text: text });
          }
        }
      }
      return closed;
    });
    if (closedTabs.length > 0) {
      emit('status', { message: 'Closed ' + closedTabs.length + ' unwanted tab(s) via ✕' });
      await page.waitForTimeout(300);
    }
  } catch (e) {}

  // Ensure Email tab is active — click it to make sure we're on the email compose view
  try {
    var emailTabBtn = page.locator('button:has-text("Email")').first();
    if (await emailTabBtn.isVisible({ timeout: 500 }).catch(() => false)) {
      await emailTabBtn.click();
      emit('status', { message: 'Ensured Email tab is active' });
      await page.waitForTimeout(300);
    }
  } catch (e) {}

  await screenshot(page, 'dropdown_closed');
}

/**
 * Select a student in the two-panel recipient picker dropdown.
 *
 * This dropdown (opened by the recipient row ▼) has:
 *   LEFT PANEL:
 *     - 🔍 "Filter..." input
 *     - "Check all" / "Clear" links, "(0 / N)" count, "Exact filter" checkbox
 *     - Student list WITH checkboxes: "Last, First Middle (CODE)" format
 *   RIGHT PANEL:
 *     - Section list like "M/J US HIST ADV 01 01 - USHADV01 - Teacher Name"
 *     - Selected section is highlighted maroon
 *     - "Match all" checkbox at bottom
 *
 * Workflow:
 *   1. (Optional) Click the correct section in the right panel
 *   2. Type the FULL student name in the "Filter..." input
 *   3. Click the checkbox next to the matching student
 */
async function selectStudentInDropdown(page, studentName) {
  emit('status', { message: 'Selecting student: ' + studentName });

  const parsed = normalizeName(studentName);

  // Build full filter text — use the original "Last, First" format for precise matching
  // e.g., "Lundell, Luke" to distinguish from siblings like "Lundell, Gianna"
  var filterText = studentName.trim();
  // If name has middle initial/name in "Last, First Middle" format, use "Last, First" for filter
  if (filterText.includes(',')) {
    var parts = filterText.split(',');
    var firstParts = parts[1].trim().split(/\s+/);
    // Use last name + first name (skip middle) for a precise but not over-specific filter
    filterText = parts[0].trim() + ', ' + firstParts[0];
  }

  // Step 1: Type the full student name in the "Filter..." input
  const filterInput = page.locator('input[placeholder="Filter..."]').first();
  if (await filterInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await filterInput.fill('');
    await filterInput.fill(filterText);
    emit('status', { message: 'Typed filter: "' + filterText + '"' });
    await page.waitForTimeout(1000);
    await screenshot(page, 'student_filter_typed');
  } else {
    emit('warning', { message: 'Could not find Filter... input' });
  }

  // Step 2: Click the CHECKBOX next to the matching student.
  //
  // From the screenshots, the checkbox is a small square element to the LEFT of
  // the student name. It's at approximately x=485, and each student row is ~21px tall.
  // Clicking the name text does NOT toggle the checkbox — must click the checkbox itself.
  //
  // Strategy: find the matching student row by text, get its Y coordinate,
  // then use page.mouse.click() on the checkbox position (x≈485) at that Y.
  await page.waitForTimeout(500);

  const studentRow = await page.evaluate((searchInfo) => {
    var target = searchInfo;
    var debugInfo = [];

    var allEls = document.querySelectorAll('*');
    for (var i = 0; i < allEls.length; i++) {
      var el = allEls[i];
      var rect = el.getBoundingClientRect();
      // Student rows in the left panel
      if (rect.left < 460 || rect.left > 800) continue;
      if (rect.top < 220 || rect.top > 500) continue;
      if (rect.height < 10 || rect.height > 40) continue;
      if (rect.width < 80) continue;

      var text = (el.textContent || '').trim();
      if (text.length < 8 || text.length > 100) continue;
      if (!text.includes(',')) continue;

      var namePart = text.replace(/\([^)]+\)/g, '').trim().toLowerCase();

      debugInfo.push(el.tagName + '@(' + Math.round(rect.left) + ',' + Math.round(rect.top) +
        ') ' + Math.round(rect.width) + 'x' + Math.round(rect.height) +
        ' "' + text.substring(0, 50) + '"');

      if (namePart.includes(target.last) && namePart.includes(target.first)) {
        return {
          text: text.substring(0, 80),
          x: Math.round(rect.left),
          y: Math.round(rect.top),
          cy: Math.round(rect.top + rect.height / 2),
          h: Math.round(rect.height),
        };
      }
    }

    return { debug: debugInfo.slice(0, 15), target: target.last + '/' + target.first };
  }, { last: parsed.last, first: parsed.first });

  if (studentRow && studentRow.text) {
    emit('status', { message: 'Found student row: "' + studentRow.text + '" at (' + studentRow.x + ',' + studentRow.y + ')' });

    // Find the checkbox element (span.not-added-label) for this student row and get its
    // coordinates. DO NOT use DOM el.click() — it doesn't register on these custom checkboxes
    // AND its event bubbling activates the "Sign Up" tab underneath the dropdown.
    // Instead, just locate the element and use page.mouse.click() with its coordinates.
    const cbInfo = await page.evaluate((targetY) => {
      // Find the checkbox span.not-added-label near the target Y coordinate
      var labels = document.querySelectorAll('span.not-added-label, span.added-label');
      for (var i = 0; i < labels.length; i++) {
        var el = labels[i];
        var rect = el.getBoundingClientRect();
        if (Math.abs(rect.top + rect.height / 2 - targetY) < 15 && rect.left > 470 && rect.left < 520) {
          return {
            found: true,
            class: el.className,
            cx: Math.round(rect.left + rect.width / 2),
            cy: Math.round(rect.top + rect.height / 2),
          };
        }
      }
      // Fallback: find any small element to the left of the name row
      var allEls = document.querySelectorAll('*');
      for (var j = 0; j < allEls.length; j++) {
        var el2 = allEls[j];
        var rect2 = el2.getBoundingClientRect();
        if (Math.abs(rect2.top + rect2.height / 2 - targetY) > 12) continue;
        if (rect2.left < 475 || rect2.left > 510) continue;
        if (rect2.width < 5 || rect2.width > 25 || rect2.height < 5 || rect2.height > 25) continue;
        return {
          found: true,
          class: (el2.className || '').toString().substring(0, 40),
          cx: Math.round(rect2.left + rect2.width / 2),
          cy: Math.round(rect2.top + rect2.height / 2),
        };
      }
      return null;
    }, studentRow.cy);

    if (cbInfo) {
      emit('status', { message: 'Found checkbox (.' + cbInfo.class + ') at (' + cbInfo.cx + ',' + cbInfo.cy + '), clicking via mouse...' });
      await page.mouse.click(cbInfo.cx, cbInfo.cy);
      await page.waitForTimeout(500);
      await screenshot(page, 'student_checkbox_clicked');

      // Check if it worked by reading the count
      var countText = await page.evaluate(() => {
        var allEls = document.querySelectorAll('*');
        for (var i = 0; i < allEls.length; i++) {
          var text = (allEls[i].textContent || '').trim();
          if (/^\(\d+ \/ \d+\)$/.test(text)) return text;
        }
        return null;
      });
      emit('status', { message: 'Selection count: ' + (countText || 'not found') });

      if (countText && !countText.startsWith('(0')) {
        emit('status', { message: 'Student selected! Count: ' + countText });
        await closeDropdownAndEnsureEmailTab(page);
        return true;
      }
    }

    // If still not working, try clicking the student name LABEL instead of the checkbox.
    // Some implementations toggle via the label, not the checkbox icon.
    emit('status', { message: 'Checkbox clicks failed. Trying to click the student name label...' });
    const nameClicked = await page.evaluate((searchInfo) => {
      var allEls = document.querySelectorAll('span, label, div, a');
      for (var i = 0; i < allEls.length; i++) {
        var el = allEls[i];
        var rect = el.getBoundingClientRect();
        if (rect.top < 220 || rect.top > 300) continue;
        if (rect.left < 490 || rect.left > 780) continue;
        if (rect.height < 10 || rect.height > 30) continue;
        var text = (el.textContent || '').trim().toLowerCase();
        if (text.includes(searchInfo.last) && text.includes(searchInfo.first) &&
            text.length < 80 && text.includes(',')) {
          // Try click, mousedown+mouseup, and dispatchEvent
          el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
          el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
          el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
          return { text: text.substring(0, 60), x: Math.round(rect.left), y: Math.round(rect.top) };
        }
      }
      return null;
    }, { last: parsed.last, first: parsed.first });

    if (nameClicked) {
      emit('status', { message: 'Dispatched click events on label: ' + nameClicked.text });
      await page.waitForTimeout(500);
      await screenshot(page, 'student_label_clicked');

      countText = await page.evaluate(() => {
        var allEls = document.querySelectorAll('*');
        for (var i = 0; i < allEls.length; i++) {
          var text = (allEls[i].textContent || '').trim();
          if (/^\(\d+ \/ \d+\)$/.test(text)) return text;
        }
        return null;
      });
      if (countText && !countText.startsWith('(0')) {
        emit('status', { message: 'Student selected via label! Count: ' + countText });
        await closeDropdownAndEnsureEmailTab(page);
        return true;
      }
    }
  }

  // Debug
  if (studentRow && studentRow.debug) {
    emit('status', { message: 'Row match failed for ' + studentRow.target });
    for (var d = 0; d < studentRow.debug.length; d++) {
      emit('status', { message: '  ' + studentRow.debug[d] });
    }
  }

  emit('warning', { message: 'Could not select student "' + studentName + '" in dropdown' });
  await screenshot(page, 'student_not_found');
  return false;
}

/**
 * Fill the email compose form: Subject, CC, and email body.
 */
async function composeEmail(page, subject, body, ccEmails) {
  emit('status', { message: 'Composing email...' });

  // Fill Subject
  // From the screenshot, the Subject row has: "Subject" label | input with placeholder "New Message" | "Cc" label | CC input
  const subjectSelectors = [
    'input[placeholder="New Message"]',
    'input[name="subject"]',
    'input[placeholder*="Subject"]',
    'input[id*="subject"]',
    'input[name*="subject"]',
  ];

  let subjectFilled = false;
  for (const sel of subjectSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible({ timeout: 2000 }).catch(() => false)) {
      await el.click();
      await el.fill('');
      await el.fill(subject);
      emit('status', { message: 'Subject filled with selector "' + sel + '": ' + subject });
      subjectFilled = true;
      break;
    }
  }

  if (!subjectFilled) {
    // Fallback: find the input element adjacent to "Subject" text via evaluate
    const evalResult = await page.evaluate((subj) => {
      // Find all elements with text "Subject"
      var allEls = document.querySelectorAll('*');
      for (var i = 0; i < allEls.length; i++) {
        var el = allEls[i];
        var text = (el.textContent || '').trim();
        if (text === 'Subject') {
          var rect = el.getBoundingClientRect();
          if (rect.width < 10 || rect.top < 200 || rect.top > 400) continue;
          // Look for an input element near this label (same Y, to the right)
          var inputs = document.querySelectorAll('input[type="text"], input:not([type])');
          for (var j = 0; j < inputs.length; j++) {
            var inp = inputs[j];
            var ir = inp.getBoundingClientRect();
            // Same row (within 15px vertical) and to the right
            if (Math.abs(ir.top - rect.top) < 15 && ir.left > rect.right - 10) {
              inp.focus();
              inp.value = subj;
              inp.dispatchEvent(new Event('input', { bubbles: true }));
              inp.dispatchEvent(new Event('change', { bubbles: true }));
              return 'Found input next to Subject label at (' + Math.round(ir.left) + ',' + Math.round(ir.top) + ')';
            }
          }
        }
      }
      return null;
    }, subject);

    if (evalResult) {
      emit('status', { message: 'Subject filled via evaluate: ' + evalResult });
      subjectFilled = true;
    }
  }

  if (!subjectFilled) {
    emit('warning', { message: 'Could not find Subject field' });
    await screenshot(page, 'no_subject_field');
  }

  // Fill CC (semicolon-separated)
  // From the screenshot, the CC field is next to the "Cc" label, on the same row as Subject
  if (ccEmails && ccEmails.length > 0) {
    const ccStr = ccEmails.join('; ');

    // Find CC input by evaluating the DOM — look for input adjacent to "Cc" text
    let ccFilled = false;
    const ccResult = await page.evaluate((cc) => {
      var allEls = document.querySelectorAll('*');
      for (var i = 0; i < allEls.length; i++) {
        var el = allEls[i];
        var text = (el.textContent || '').trim();
        if (text === 'Cc') {
          var rect = el.getBoundingClientRect();
          if (rect.width < 5 || rect.top < 200 || rect.top > 400) continue;
          var inputs = document.querySelectorAll('input[type="text"], input:not([type])');
          for (var j = 0; j < inputs.length; j++) {
            var inp = inputs[j];
            var ir = inp.getBoundingClientRect();
            if (Math.abs(ir.top - rect.top) < 15 && ir.left > rect.right - 10) {
              inp.focus();
              inp.value = cc;
              inp.dispatchEvent(new Event('input', { bubbles: true }));
              inp.dispatchEvent(new Event('change', { bubbles: true }));
              return 'Found CC input at (' + Math.round(ir.left) + ',' + Math.round(ir.top) + ')';
            }
          }
        }
      }
      return null;
    }, ccStr);

    if (ccResult) {
      emit('status', { message: 'CC filled: ' + ccStr + ' (' + ccResult + ')' });
      ccFilled = true;
    }

    if (!ccFilled) {
      // Try standard selectors as fallback
      const ccSelectors = [
        'input[name="cc"]',
        'input[placeholder*="Cc"]',
        'input[placeholder*="CC"]',
        'input[id*="cc"]',
      ];
      for (const sel of ccSelectors) {
        const el = page.locator(sel).first();
        if (await el.isVisible({ timeout: 1500 }).catch(() => false)) {
          await el.fill('');
          await el.fill(ccStr);
          emit('status', { message: 'CC filled with selector "' + sel + '": ' + ccStr });
          ccFilled = true;
          break;
        }
      }
    }

    if (!ccFilled) {
      emit('warning', { message: 'Could not find CC field, skipping CC' });
    }
  }

  // Fill email body — could be contenteditable div, textarea, or iframe
  const bodySelectors = [
    'div[contenteditable="true"]',
    'textarea[name*="body"]',
    'textarea[name*="message"]',
    'textarea[placeholder*="message"]',
    'textarea[id*="body"]',
  ];

  let bodyFilled = false;
  for (const sel of bodySelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible({ timeout: 2000 }).catch(() => false)) {
      try {
        // For contenteditable, click first then type
        if (sel.includes('contenteditable')) {
          await el.click();
          await page.waitForTimeout(300);
          // Select all existing content and replace
          await page.keyboard.press('Meta+a');
          await page.keyboard.type(body, { delay: 5 });
        } else {
          await el.fill('');
          await el.fill(body);
        }
        emit('status', { message: 'Email body filled (' + body.length + ' chars)' });
        bodyFilled = true;
        break;
      } catch (e) {
        emit('status', { message: 'Failed to fill body with ' + sel + ': ' + e.message });
      }
    }
  }

  // Try iframe-based rich text editor
  if (!bodyFilled) {
    const iframes = page.frameLocator('iframe');
    try {
      const iframeBody = iframes.first().locator('body');
      if (await iframeBody.isVisible({ timeout: 2000 }).catch(() => false)) {
        await iframeBody.click();
        await page.keyboard.press('Meta+a');
        await page.keyboard.type(body, { delay: 5 });
        emit('status', { message: 'Email body filled via iframe (' + body.length + ' chars)' });
        bodyFilled = true;
      }
    } catch (e) {}
  }

  if (!bodyFilled) {
    emit('warning', { message: 'Could not find email body field' });
    await screenshot(page, 'no_body_field');
  }

  await screenshot(page, 'email_composed');
  return subjectFilled && bodyFilled;
}

/**
 * Switch to SMS tab and fill SMS body.
 */
async function composeSMS(page, smsBody, smsOnly) {
  if (!smsBody) return true;

  emit('status', { message: 'Composing SMS...' });

  // Click the SMS tab
  const smsTabSelectors = [
    'a:has-text("SMS")',
    'button:has-text("SMS")',
    'div:has-text("SMS"):not(:has(div))',
    'li:has-text("SMS")',
    '.tab:has-text("SMS")',
    'a[data-tab="sms"]',
    '[role="tab"]:has-text("SMS")',
  ];

  let smsTabClicked = false;
  for (const sel of smsTabSelectors) {
    try {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 2000 }).catch(() => false)) {
        await el.click();
        emit('status', { message: 'Clicked SMS tab with: ' + sel });
        smsTabClicked = true;
        await page.waitForTimeout(1000);
        break;
      }
    } catch (e) {}
  }

  if (!smsTabClicked) {
    emit('warning', { message: 'Could not find SMS tab' });
    await screenshot(page, 'no_sms_tab');
    return false;
  }

  // Fill SMS body — this is a contenteditable div (rich text editor), not a textarea.
  // From the screenshot, the SMS panel shows:
  //   toolbar: "Insert Field" | image icons | undo/redo
  //   body: contenteditable div with placeholder "Type a short message to be sent by SMS text."
  //   footer: "0/500 characters"

  let smsFilled = false;

  // Strategy 1: find the contenteditable div in the SMS panel
  // There may be multiple contenteditable divs — the SMS one appears AFTER clicking the SMS tab
  // and is distinct from the email body contenteditable.
  // We look for a contenteditable that's currently visible and in the compose area.
  const ceEls = page.locator('div[contenteditable="true"]');
  const ceCount = await ceEls.count().catch(() => 0);
  emit('status', { message: 'Found ' + ceCount + ' contenteditable div(s)' });

  // Click the last visible contenteditable (the SMS one, since it appears after the email one)
  for (var ci = ceCount - 1; ci >= 0; ci--) {
    const ce = ceEls.nth(ci);
    if (await ce.isVisible({ timeout: 1500 }).catch(() => false)) {
      try {
        await ce.click();
        await page.waitForTimeout(300);
        await page.keyboard.press('Meta+a');
        await page.keyboard.type(smsBody, { delay: 5 });
        emit('status', { message: 'SMS body filled via contenteditable (' + smsBody.length + ' chars)' });
        smsFilled = true;
        break;
      } catch (e) {
        emit('status', { message: 'Failed to fill SMS contenteditable [' + ci + ']: ' + e.message });
      }
    }
  }

  // Strategy 2: try textarea/input as fallback
  if (!smsFilled) {
    const smsSelectors = [
      'textarea[name*="sms"]',
      'textarea[placeholder*="SMS"]',
      'textarea[placeholder*="text message"]',
      'textarea',
    ];
    for (const sel of smsSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1000 }).catch(() => false)) {
        await el.fill('');
        await el.fill(smsBody);
        emit('status', { message: 'SMS body filled via ' + sel + ' (' + smsBody.length + ' chars)' });
        smsFilled = true;
        break;
      }
    }
  }

  if (!smsFilled) {
    emit('warning', { message: 'Could not find SMS body field' });
    await screenshot(page, 'no_sms_field');
  }

  await screenshot(page, 'sms_composed');

  // Switch back to email tab so the form shows the full message (skip for SMS-only)
  if (!smsOnly) {
    const emailTabSelectors = [
      'a:has-text("Email")',
      'button:has-text("Email")',
      'li:has-text("Email")',
      '.tab:has-text("Email")',
      'a[data-tab="email"]',
      '[role="tab"]:has-text("Email")',
    ];
    for (const sel of emailTabSelectors) {
      try {
        const el = page.locator(sel).first();
        if (await el.isVisible({ timeout: 1000 }).catch(() => false)) {
          await el.click();
          await page.waitForTimeout(500);
          break;
        }
      } catch (e) {}
    }
  }

  return smsFilled;
}

/**
 * Click the Send button and handle any confirmation dialog.
 * NOTE: Currently a no-op — logs what it would do but does NOT actually send.
 * Remove the early return to enable actual sending.
 */
async function clickSend(page, dryRun) {
  if (dryRun) {
    emit('status', { message: '[DRY RUN] Would click Send — skipping' });
    await screenshot(page, 'dry_run_would_send');
    return true;
  }

  emit('status', { message: 'Clicking Send...' });
  await screenshot(page, 'before_send');

  const sendSelectors = [
    'button:has-text("Send")',
    'input[type="submit"][value*="Send"]',
    'a:has-text("Send")',
    'button[title*="Send"]',
    '.send-button',
    'button.primary:has-text("Send")',
  ];

  for (const sel of sendSelectors) {
    try {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 2000 }).catch(() => false)) {
        await el.click();
        emit('status', { message: 'Clicked Send with: ' + sel });
        await page.waitForTimeout(2000);

        // Handle confirmation dialog if one appears
        // The dialog has "Go Back" and "Send" buttons. We need to click the
        // "Send" button inside the dialog, not the toolbar Send button.
        // First check if a dialog/modal appeared by looking for "Go Back" text.
        const goBackBtn = page.locator('button:has-text("Go Back")').first();
        if (await goBackBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          emit('status', { message: 'Confirmation dialog detected, clicking Send...' });
          await screenshot(page, 'confirmation_dialog');
          // Find the Send button that is a sibling of Go Back (in the dialog)
          // Use evaluate to find and click the right one
          const clicked = await page.evaluate(function() {
            var buttons = document.querySelectorAll('button');
            var goBackFound = false;
            var dialogContainer = null;
            for (var i = 0; i < buttons.length; i++) {
              if (buttons[i].textContent.trim() === 'Go Back') {
                goBackFound = true;
                dialogContainer = buttons[i].closest('.modal, .dialog, [role="dialog"], .popup, .overlay, .swift-dialog') || buttons[i].parentElement;
                break;
              }
            }
            if (!goBackFound || !dialogContainer) return false;
            // Find Send button in the same container
            var containerBtns = dialogContainer.querySelectorAll('button');
            for (var j = 0; j < containerBtns.length; j++) {
              var txt = containerBtns[j].textContent.trim();
              if (txt === 'Send' || txt === 'send') {
                containerBtns[j].click();
                return true;
              }
            }
            // Fallback: look in parent of parent
            var parent = dialogContainer.parentElement;
            if (parent) {
              var pBtns = parent.querySelectorAll('button');
              for (var k = 0; k < pBtns.length; k++) {
                var t = pBtns[k].textContent.trim();
                if (t === 'Send' || t === 'send') {
                  pBtns[k].click();
                  return true;
                }
              }
            }
            return false;
          });
          if (clicked) {
            emit('status', { message: 'Confirmed send in dialog' });
          } else {
            // Fallback: try clicking any visible Send button that isn't the original
            emit('status', { message: 'Fallback: clicking all visible Send buttons...' });
            var allSendBtns = await page.locator('button:has-text("Send")').all();
            for (var si = allSendBtns.length - 1; si >= 0; si--) {
              if (await allSendBtns[si].isVisible().catch(function() { return false; })) {
                await allSendBtns[si].click();
                emit('status', { message: 'Clicked Send button index ' + si });
                break;
              }
            }
          }
          await page.waitForTimeout(2000);
        } else {
          // Also check for OK/Yes/Confirm style dialogs
          var confirmBtn = page.locator('button:has-text("OK"), button:has-text("Yes"), button:has-text("Confirm")').first();
          if (await confirmBtn.isVisible({ timeout: 1000 }).catch(function() { return false; })) {
            await confirmBtn.click();
            emit('status', { message: 'Confirmed send dialog (OK/Yes)' });
            await page.waitForTimeout(1000);
          }
        }

        await screenshot(page, 'after_send');
        return true;
      }
    } catch (e) {}
  }

  emit('warning', { message: 'Could not find Send button' });
  await screenshot(page, 'no_send_button');
  return false;
}

/**
 * Orchestrate sending a single message: select period, pick student, compose, send.
 */
async function sendOneMessage(page, entry, dryRun, currentPeriod) {
  const msg = entry.message;
  const studentName = msg.student_name;
  const periodNum = entry.periodNum;
  const courseCode = entry.courseCode || '';

  emit('status', { message: 'Processing: ' + studentName + ' (Period ' + periodNum + (courseCode ? ', ' + courseCode : '') + ')' });

  // Step 1: Select period/section if different from current
  // Track both period number and course code to handle multiple sections per period
  var currentKey = currentPeriod ? (currentPeriod.num + ':' + (currentPeriod.course || '')) : '';
  var targetKey = periodNum + ':' + courseCode;
  if (currentKey !== targetKey) {
    await selectPeriodSection(page, periodNum, courseCode);
  }

  // Step 2: Select recipient type (Students, Primary Contacts, etc.)
  await selectRecipientType(page, msg.recipient_type || 'Primary Contacts');

  // Step 3: Open student dropdown and select student
  const dropdownOpened = await openStudentDropdown(page);
  if (!dropdownOpened) {
    return { success: false, error: 'Could not open student dropdown' };
  }

  const studentSelected = await selectStudentInDropdown(page, studentName);
  if (!studentSelected) {
    return { success: false, error: 'Could not select student in dropdown' };
  }

  // Step 4: Compose email (skip for SMS-only)
  if (msg.email_body) {
    const emailOk = await composeEmail(page, msg.subject, msg.email_body, msg.cc_emails);
    if (!emailOk) {
      return { success: false, error: 'Failed to compose email' };
    }
  }

  // Step 5: Compose SMS (if provided)
  if (msg.sms_body) {
    await composeSMS(page, msg.sms_body, !msg.email_body);
  }

  // Step 6: Send (or skip in dry-run / send-disabled mode)
  const sent = await clickSend(page, dryRun);
  if (!sent) {
    return { success: false, error: 'Failed to click Send' };
  }

  return { success: true };
}


// ══════════════════════════════════════════════════════════════
// MAIN
// ══════════════════════════════════════════════════════════════

async function main() {
  // Parse CLI args
  const args = process.argv.slice(2);
  let dryRun = false;
  let messagesFile = null;

  for (const arg of args) {
    if (arg === '--dry-run') {
      dryRun = true;
    } else if (arg === '--screenshot') {
      screenshotsEnabled = true;
    } else if (!arg.startsWith('--')) {
      messagesFile = arg;
    }
  }

  if (!messagesFile) {
    console.error('Usage: node focus-comms.js [--dry-run] [--screenshot] <messages.json>');
    process.exit(1);
  }

  emit('status', { message: 'Starting Focus Communications...' });
  if (dryRun) emit('status', { message: 'DRY RUN mode — no messages will be sent' });
  if (screenshotsEnabled) emit('status', { message: 'Screenshots enabled → ' + SCREENSHOTS_DIR });

  // Load data
  const roster = loadRoster();
  const messages = loadMessages(messagesFile);
  emit('status', { message: 'Loaded ' + messages.length + ' message(s) from ' + path.basename(messagesFile) });

  // Validate all messages against roster
  const { valid, errors } = validateMessages(messages, roster);

  if (errors.length > 0) {
    emit('warning', { message: errors.length + ' validation error(s):' });
    for (const err of errors) {
      emit('warning', { message: '  ' + err });
    }
  }

  if (valid.length === 0) {
    emit('error', { message: 'No valid messages to send' });
    process.exit(1);
  }

  emit('status', { message: valid.length + ' valid message(s) to process' });

  // Group by period+course for efficient processing (minimize section switches)
  valid.sort(function(a, b) {
    if (a.periodNum !== b.periodNum) return a.periodNum - b.periodNum;
    return (a.courseCode || '').localeCompare(b.courseCode || '');
  });

  // If dry-run with no --screenshot, just validate and exit
  if (dryRun && !screenshotsEnabled) {
    emit('status', { message: 'Dry run validation complete. Messages:' });
    for (const entry of valid) {
      emit('status', {
        message: '  ' + entry.message.student_name + ' (Period ' + entry.periodNum + '): ' + entry.message.subject,
      });
    }
    emit('done', {
      message: 'Dry run complete',
      total: messages.length,
      valid: valid.length,
      errors: errors.length,
    });
    return;
  }

  // Load credentials and launch browser
  const creds = loadCredentials();
  fs.mkdirSync(BROWSER_DATA_DIR, { recursive: true });

  const browser = await chromium.launchPersistentContext(BROWSER_DATA_DIR, {
    headless: false,
    viewport: { width: 1440, height: 900 },
  });
  const page = browser.pages()[0] || await browser.newPage();

  const results = { sent: 0, failed: 0, skipped: errors.length };
  let currentPeriod = null;

  try {
    // Login and navigate to Communications
    await login(page, creds);
    await navigateToFocus(page);
    await navigateToCommunications(page);

    // Process each message
    for (var i = 0; i < valid.length; i++) {
      const entry = valid[i];
      const msgNum = i + 1;

      emit('progress', {
        message: 'Message ' + msgNum + '/' + valid.length + ': ' + entry.message.student_name,
        current: msgNum,
        total: valid.length,
        student: entry.message.student_name,
      });

      // Verify we're still on Focus
      const currentUrl = page.url();
      if (!currentUrl.includes('focusschoolsoftware.com')) {
        emit('warning', { message: 'Session may have expired, re-navigating to Focus...' });
        await navigateToFocus(page);
        await navigateToCommunications(page);
        currentPeriod = null;
      }

      try {
        const result = await sendOneMessage(page, entry, dryRun, currentPeriod);
        if (result.success) {
          results.sent++;
          currentPeriod = { num: entry.periodNum, course: entry.courseCode || '' };
          emit('status', { message: 'Message ' + msgNum + ' processed successfully' });
        } else {
          results.failed++;
          emit('error', { message: 'Message ' + msgNum + ' failed: ' + result.error, student: entry.message.student_name });
        }
      } catch (e) {
        results.failed++;
        emit('error', { message: 'Message ' + msgNum + ' error: ' + e.message, student: entry.message.student_name });
        await page.screenshot({ path: ERROR_SCREENSHOT }).catch(() => {});
      }

      // Navigate to fresh Compose form for next message
      if (i < valid.length - 1) {
        try {
          await navigateToCompose(page);
        } catch (e) {
          emit('warning', { message: 'Could not reset Compose form: ' + e.message });
          // Try full re-navigation
          await navigateToCommunications(page);
          currentPeriod = null;
        }
      }
    }

    // Done
    emit('done', {
      message: 'Communications complete',
      sent: results.sent,
      failed: results.failed,
      skipped: results.skipped,
      total: messages.length,
    });

  } catch (error) {
    emit('error', { message: 'Fatal error: ' + error.message });
    await page.screenshot({ path: ERROR_SCREENSHOT }).catch(() => {});
    emit('error', { message: 'Screenshot saved to ' + ERROR_SCREENSHOT });
  } finally {
    try {
      emit('status', { message: 'Browser will stay open for 30 seconds...' });
      await page.waitForTimeout(30000);
      await browser.close();
    } catch (e) {
      // Browser may have been closed manually
    }
  }
}

main();
