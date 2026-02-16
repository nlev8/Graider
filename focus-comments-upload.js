#!/usr/bin/env node
/**
 * Focus Gradebook Comments Upload
 * Enters grading comments/feedback for students in Focus gradebook via Playwright.
 *
 * The CSV import to Focus only handles numeric scores — comments must be entered
 * through the gradebook UI. This script automates that process.
 *
 * WORKFLOW (based on actual Focus SIS UI):
 *   1. Login via VPortal → ADFS → 2FA
 *   2. Navigate to Gradebook
 *   3. Select period via select[name="side_period"] dropdown
 *   4. Click student name (span.student-name-link) → opens student detail page
 *   5. Find assignment row by matching assignment name text
 *   6. Click the comment cell (div.comment-cell-display input.data-field-comment)
 *   7. Type the comment, tab out to save
 *   8. Click "Gradebook" in sidebar to return to student list
 *   9. Repeat for each student
 *
 * Input JSON format:
 *   { "assignment": "Quiz 1", "comments": [
 *       { "student_id": "12345", "student_name": "Smith, John", "comment": "...", "score": 95 }
 *   ]}
 *
 * Usage:
 *   node focus-comments-upload.js --from-manifest           # use latest Batch Focus export
 *   node focus-comments-upload.js comments.json             # use specific file
 *   node focus-comments-upload.js --dry-run --from-manifest # test without entering data
 *   node focus-comments-upload.js --screenshot              # take screenshots at each step
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const GRAIDER_DATA_DIR = path.join(process.env.HOME, '.graider_data');
const CREDS_PATH = path.join(GRAIDER_DATA_DIR, 'portal_credentials.json');
const BROWSER_DATA_DIR = path.join(GRAIDER_DATA_DIR, 'focus_browser');
const SCREENSHOTS_DIR = path.join(GRAIDER_DATA_DIR, 'focus_screenshots');
const ERROR_SCREENSHOT = path.join(GRAIDER_DATA_DIR, 'focus-comments-error.png');
const FOCUS_EXPORTS_DIR = path.join(process.env.HOME, '.graider_exports', 'focus');

// Focus SIS base URL for Volusia County
const FOCUS_BASE = 'https://volusia.focusschoolsoftware.com/focus';
const FOCUS_GRADEBOOK_URL = FOCUS_BASE + '/Modules.php?modname=Grades/Gradebook.php';


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
 * Focus uses "Last, First Middle" format (e.g., "Long, Eli William").
 * Our data may be "First Last", "First Middle Last", or "Last, First".
 */
function normalizeName(name) {
  if (!name) return { last: '', first: '', normalized: '' };
  const trimmed = name.trim();

  // "Last, First Middle" format (Focus format)
  if (trimmed.includes(',')) {
    const parts = trimmed.split(',').map(p => p.trim());
    return {
      last: parts[0].toLowerCase(),
      first: parts[1] ? parts[1].split(/\s+/)[0].toLowerCase() : '',
      normalized: trimmed.toLowerCase(),
    };
  }

  // "First Middle Last" or "First Last" format
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
 * Handles "Long, Eli William" (Focus) vs "Eli William Long" (Graider).
 */
function namesMatch(name1, name2) {
  const n1 = normalizeName(name1);
  const n2 = normalizeName(name2);

  // Exact normalized match
  if (n1.normalized === n2.normalized) return true;

  // Last name + first name match (handles "Last, First" vs "First Last")
  if (n1.last && n2.last && n1.first && n2.first) {
    if (n1.last === n2.last && n1.first === n2.first) return true;
  }

  return false;
}

/**
 * Match by student ID — checks if the row contains a hidden input with the student ID.
 */
async function matchByStudentId(row, studentId) {
  if (!studentId) return false;
  const idInput = row.locator('input[data-field="student_id"]').first();
  const val = await idInput.getAttribute('data-bottom-tooltip').catch(() => '');
  return val === studentId;
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

function loadComments(filepath) {
  if (!fs.existsSync(filepath)) {
    emit('error', { message: 'Comments file not found: ' + filepath });
    process.exit(1);
  }
  try {
    const data = JSON.parse(fs.readFileSync(filepath, 'utf-8'));
    if (Array.isArray(data)) {
      return { assignment: 'Assignment', comments: data, byPeriod: { 'All': data } };
    }
    if (data.comments && Array.isArray(data.comments)) {
      // Group by period if comments have period fields
      var byPeriod = data.byPeriod || {};
      if (Object.keys(byPeriod).length === 0) {
        for (var ci = 0; ci < data.comments.length; ci++) {
          var period = data.comments[ci].period || 'All';
          if (!byPeriod[period]) byPeriod[period] = [];
          byPeriod[period].push(data.comments[ci]);
        }
      }
      return { assignment: data.assignment || 'Assignment', comments: data.comments, byPeriod: byPeriod };
    }
    emit('error', { message: 'Invalid comments file format.' });
    process.exit(1);
  } catch (e) {
    emit('error', { message: 'Error reading comments file: ' + e.message });
    process.exit(1);
  }
}

function loadFromManifest() {
  const manifestPath = path.join(FOCUS_EXPORTS_DIR, 'comments_manifest.json');
  if (!fs.existsSync(manifestPath)) {
    emit('error', { message: 'No comments manifest found. Run "Batch Focus" export first.' });
    process.exit(1);
  }

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
  const allComments = [];
  const byPeriod = {};

  for (const period of (manifest.periods || [])) {
    const filePath = path.join(FOCUS_EXPORTS_DIR, period.file);
    if (fs.existsSync(filePath)) {
      const periodComments = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      byPeriod[period.period] = [];
      for (const c of periodComments) {
        c.period = period.period;
        allComments.push(c);
        byPeriod[period.period].push(c);
      }
    }
  }

  return {
    assignment: manifest.assignment || 'Assignment',
    comments: allComments,
    byPeriod: byPeriod,
  };
}


// ══════════════════════════════════════════════════════════════
// BROWSER AUTOMATION — Login
// ══════════════════════════════════════════════════════════════

async function login(page, creds) {
  emit('status', { message: 'Opening VPortal...' });
  await page.goto('https://vportal.volusia.k12.fl.us/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // Click the SAML/SSO login button if present
  try {
    await page.click('button.btn-saml', { timeout: 5000 });
    emit('status', { message: 'Clicked portal login, waiting for ADFS...' });
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForTimeout(2000);
  } catch (e) {
    emit('status', { message: 'No portal login button, may be past this step...' });
  }

  // Handle ADFS login form
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

  // Handle Microsoft 2FA
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
// BROWSER AUTOMATION — Focus Gradebook Navigation
// ══════════════════════════════════════════════════════════════

async function navigateToGradebook(page) {
  emit('status', { message: 'Navigating to Focus Gradebook...' });

  // The direct URL may redirect to Portal. Click the sidebar "Gradebook" link instead.
  // First, make sure we're on Focus
  const currentUrl = page.url();
  if (!currentUrl.includes('focusschoolsoftware.com')) {
    await page.goto(FOCUS_BASE, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
  }

  // Click the "Gradebook" link in the left sidebar
  // From the screenshot: it's a div.site-menu-group-title-text with text "Gradebook"
  const gbLink = page.locator('div.site-menu-sidebar a').filter({ hasText: /^Gradebook$/ }).first();
  if (await gbLink.isVisible({ timeout: 5000 }).catch(() => false)) {
    await gbLink.click();
    emit('status', { message: 'Clicked Gradebook in sidebar...' });
  } else {
    // Fallback: try direct URL
    emit('status', { message: 'Sidebar link not found, trying direct URL...' });
    await page.goto(FOCUS_GRADEBOOK_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  }

  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3000);

  // Verify we see the gradebook table (student rows should be visible)
  const hasStudents = await page.locator('span.student-name-link').first()
    .isVisible({ timeout: 5000 }).catch(() => false);

  if (!hasStudents) {
    emit('status', { message: 'Gradebook table not visible yet, trying direct URL...' });
    await page.goto(FOCUS_GRADEBOOK_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
  }

  await screenshot(page, 'gradebook_loaded');
  emit('status', { message: 'Gradebook page loaded' });
}

/**
 * Select a period/section using the top-right dropdown.
 * Focus uses select[name="side_period"] which auto-submits form #site_session.
 * Period options look like: "01 - USHADV01 - M/J US HIST ADV"
 * Our period names look like: "Period 1" or just "1"
 */
/**
 * Get all dropdown options matching a period number.
 * Returns array of { text, value } for all sections in that period.
 * E.g., Period 5 may have "05 - USH605ADV" AND "05 - GUSH005".
 */
async function getSectionsForPeriod(page, periodName) {
  const periodSelect = page.locator('select[name="side_period"]').first();
  if (!await periodSelect.isVisible({ timeout: 5000 }).catch(() => false)) {
    return [];
  }

  const options = await periodSelect.locator('option').all();
  const optionData = [];
  for (const opt of options) {
    const text = await opt.textContent().catch(() => '');
    const value = await opt.getAttribute('value').catch(() => '');
    optionData.push({ text: text.trim(), value: value });
  }

  const periodNum = periodName.replace(/[^0-9]/g, '');
  var matches = [];
  for (var i = 0; i < optionData.length; i++) {
    var optNum = optionData[i].text.split(/[\s-]/)[0].replace(/^0+/, '');
    if (optNum === periodNum) {
      matches.push(optionData[i]);
    }
  }

  // Fallback: partial text match
  if (matches.length === 0) {
    for (var j = 0; j < optionData.length; j++) {
      if (optionData[j].text.includes(periodName) || optionData[j].text.includes('Period ' + periodNum)) {
        matches.push(optionData[j]);
      }
    }
  }

  return matches;
}

/**
 * Select a specific section by its dropdown value.
 */
async function selectSectionByValue(page, sectionOption) {
  const periodSelect = page.locator('select[name="side_period"]').first();
  if (!await periodSelect.isVisible({ timeout: 5000 }).catch(() => false)) {
    return false;
  }
  await periodSelect.selectOption(sectionOption.value);
  emit('status', { message: 'Selected: ' + sectionOption.text });
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3000);
  await screenshot(page, 'section_selected');
  return true;
}

async function selectSection(page, periodName) {
  emit('status', { message: 'Selecting section for: ' + periodName });
  var sections = await getSectionsForPeriod(page, periodName);
  if (sections.length === 0) {
    emit('status', { message: 'Could not match period "' + periodName + '" in dropdown' });
    return false;
  }
  emit('status', { message: 'Found ' + sections.length + ' section(s) for ' + periodName + ': ' + sections.map(function(s) { return s.text; }).join(' | ') });
  return await selectSectionByValue(page, sections[0]);
}

/**
 * Get all student name links from the gradebook list view.
 * Returns array of { element, name, studentId }.
 * Focus student names are span.student-name-link elements.
 */
async function getStudentNameLinks(page) {
  const students = [];

  // Student name links in the gradebook table
  // From DevTools: span.student-name-link inside a record row
  const nameLinks = await page.locator('span.student-name-link').all();

  if (nameLinks.length > 0) {
    for (const link of nameLinks) {
      const text = await link.textContent().catch(() => '');
      if (text.trim()) {
        // Clean name: remove emoji/icons that Focus appends (e.g., pen icons, stars)
        const cleanName = text.trim().replace(/[^\w\s,'-]/g, '').trim();
        // Try to get student ID from nearby hidden input in the row
        const row = link.locator('xpath=ancestor::tr').first();
        let sid = '';
        try {
          const idInput = row.locator('input[data-field="student_id"]').first();
          sid = await idInput.getAttribute('data-bottom-tooltip').catch(() => '');
          if (!sid) {
            sid = await idInput.getAttribute('value').catch(() => '');
          }
        } catch (e) {
          // no student ID available
        }
        // The clickable element is the span itself (it acts as a link in Focus)
        // But we also grab the parent row for alternative click strategies
        students.push({ element: link, row: row, name: cleanName, studentId: sid });
      }
    }
    emit('status', { message: 'Found ' + students.length + ' students via student-name-link' });
    if (students.length > 0) {
      const sample = students.slice(0, 3).map(s => s.name + (s.studentId ? ' [' + s.studentId + ']' : ''));
      emit('status', { message: 'Sample: ' + sample.join(', ') });
    }
    return students;
  }

  // Fallback: look for student names in table rows with student_id inputs
  emit('status', { message: 'No student-name-link found, trying table row fallback...' });
  const rows = await page.locator('tr:has(input[data-field="student_id"])').all();
  for (const row of rows) {
    const nameEl = row.locator('td').first();
    const text = await nameEl.textContent().catch(() => '');
    let sid = '';
    try {
      const idInput = row.locator('input[data-field="student_id"]').first();
      sid = await idInput.getAttribute('data-bottom-tooltip').catch(() => '');
    } catch (e) {}
    if (text.trim()) {
      students.push({ element: nameEl, name: text.trim(), studentId: sid });
    }
  }

  emit('status', { message: 'Found ' + students.length + ' students via fallback' });
  return students;
}

/**
 * On the student detail page, find the assignment row and click its comment cell.
 * The student detail page shows all assignments in a table.
 * Assignment names are links in the first column.
 * Comment cells are: div.comment-cell-display with input.data-field-comment
 */
async function findAndFillComment(page, assignmentName, commentText) {
  await page.waitForTimeout(1500);
  await screenshot(page, 'student_detail_page');

  // On the student detail page, assignments are listed in table rows.
  // Each row has: icon cells, Assignment name (as a link), Points, Percent, Grade, Comment, etc.
  // We need to find the row with the matching assignment name, then click its Comment cell.

  // Get all assignment links on the student detail page.
  // Each assignment row has an <a> tag with the assignment name.
  // We match against the link text, NOT the full row text, to avoid
  // false matches from grade/points data in other cells.
  let targetRow = null;
  const assignLower = assignmentName.toLowerCase().trim();

  // Scan for assignment rows. Focus uses a complex table structure —
  // try multiple strategies to find assignment name links and their parent rows.
  var candidates = [];

  // Strategy 1: Use page.evaluate to find all links and debug the DOM
  var debugInfo = await page.evaluate(function() {
    var info = { tables: 0, trs: 0, links: 0, iframes: 0, samples: [] };
    info.tables = document.querySelectorAll('table').length;
    info.trs = document.querySelectorAll('table tr').length;
    info.links = document.querySelectorAll('a').length;
    info.iframes = document.querySelectorAll('iframe').length;
    // Find all links that look like assignment names
    var allLinks = document.querySelectorAll('a');
    for (var i = 0; i < allLinks.length && info.samples.length < 15; i++) {
      var text = (allLinks[i].textContent || '').trim();
      if (text.length > 5 && text.length < 200) {
        info.samples.push(text.substring(0, 80));
      }
    }
    return info;
  });
  emit('status', { message: 'DOM: ' + debugInfo.tables + ' tables, ' + debugInfo.trs + ' trs, ' + debugInfo.links + ' links, ' + debugInfo.iframes + ' iframes' });
  emit('status', { message: 'Link samples: ' + debugInfo.samples.join(' | ') });

  // Check for iframes — Focus renders gradebook content inside iframes
  var frames = page.frames();
  var targetFrame = page;
  for (var fi = 0; fi < frames.length; fi++) {
    var frameName = frames[fi].name() || '';
    var frameUrl = frames[fi].url() || '';
    // Look for the frame containing assignment data
    var hasAssignmentCol = await frames[fi].locator('text=Assignment').first()
      .isVisible({ timeout: 500 }).catch(function() { return false; });
    var frameRowCount = await frames[fi].locator('table tr').count().catch(function() { return 0; });
    emit('status', { message: 'Frame ' + fi + ': name="' + frameName + '" rows=' + frameRowCount + ' hasAssignment=' + hasAssignmentCol + ' url=' + frameUrl.substring(0, 80) });
    if (hasAssignmentCol && frameRowCount > 3) {
      targetFrame = frames[fi];
      emit('status', { message: 'Using frame ' + fi + ' for assignment matching' });
      break;
    }
  }

  // Now scan rows in the target frame using Playwright locators (which pierce iframes).
  // IMPORTANT: Do NOT use evaluate() here — it runs JS in a single frame context
  // and cannot see content inside iframes. Playwright's locator methods (.textContent(),
  // .isVisible(), etc.) automatically pierce iframes and work cross-frame.

  // Focus renders assignment names as <span class="data-field-assignment_title">
  // inside <div class="assignment-name-link"> (NOT <a> tags).

  // Focus renders assignment names as <span class="data-field-assignment_title">
  // inside <div class="assignment-name-link">, NOT as <a> tags.
  // Find all assignment title spans and map each to its parent <tr> row.
  var titleSpans = await targetFrame.locator('span.data-field-assignment_title').all();
  emit('status', { message: 'Found ' + titleSpans.length + ' assignment title spans' });

  for (var si2 = 0; si2 < titleSpans.length; si2++) {
    var span = titleSpans[si2];
    var spanText = await span.textContent({ timeout: 2000 }).catch(function() { return ''; });
    spanText = (spanText || '').trim();
    if (spanText && spanText.length > 3) {
      // Navigate up to the parent <tr> for this assignment
      var parentRow = span.locator('xpath=ancestor::tr').first();
      candidates.push({ row: parentRow, name: spanText, nameLower: spanText.toLowerCase() });
    }
  }

  // Fallback: if no span-based candidates, try div.assignment-name-link text
  if (candidates.length === 0) {
    var assignDivs = await targetFrame.locator('div.assignment-name-link').all();
    emit('status', { message: 'Fallback: found ' + assignDivs.length + ' assignment-name-link divs' });
    for (var di = 0; di < assignDivs.length; di++) {
      var divText = await assignDivs[di].textContent({ timeout: 2000 }).catch(function() { return ''; });
      divText = (divText || '').trim();
      if (divText && divText.length > 3) {
        var divRow = assignDivs[di].locator('xpath=ancestor::tr').first();
        candidates.push({ row: divRow, name: divText, nameLower: divText.toLowerCase() });
      }
    }
  }

  var candNames = candidates.map(function(c) { return c.name; });
  emit('status', { message: 'Found ' + candidates.length + ' assignments: ' + candNames.join(' | ') });
  emit('status', { message: 'Matching target: "' + assignmentName + '"' });

  // Pass 1: Exact match (assignment link text equals or contains our full name)
  for (var ci = 0; ci < candidates.length; ci++) {
    var c = candidates[ci];
    if (c.nameLower === assignLower || c.nameLower.includes(assignLower) || assignLower.includes(c.nameLower)) {
      targetRow = c.row;
      emit('status', { message: 'Exact match: "' + c.name + '"' });
      break;
    }
  }

  // Pass 2: Normalized match (strip punctuation, extra spaces, common prefixes)
  if (!targetRow) {
    var normalize = function(s) {
      return s.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
    };
    var assignNorm = normalize(assignmentName);
    for (var ci2 = 0; ci2 < candidates.length; ci2++) {
      var c2 = candidates[ci2];
      var candNorm = normalize(c2.name);
      if (candNorm === assignNorm || candNorm.includes(assignNorm) || assignNorm.includes(candNorm)) {
        targetRow = c2.row;
        emit('status', { message: 'Normalized match: "' + c2.name + '"' });
        break;
      }
    }
  }

  // Pass 3: Best word-overlap match using Jaccard similarity.
  // Requires >60% overlap AND the best score among all candidates.
  // This prevents "Cornell Notes Slavery and Resistance" from matching
  // "Cornell Notes The Growth of the Cotton Industry and Slavery pp 344-345"
  // because the latter has many unmatched words, lowering its Jaccard score.
  if (!targetRow) {
    var stopWords = ['the', 'and', 'for', 'from', 'with', 'that', 'this', 'are', 'was', 'were', 'has', 'have', 'had'];
    var getSignificantWords = function(s) {
      return s.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(function(w) {
        return w.length > 2 && stopWords.indexOf(w) === -1;
      });
    };
    var assignWords = getSignificantWords(assignmentName);
    var bestScore = 0;
    var bestCandidate = null;

    for (var ci3 = 0; ci3 < candidates.length; ci3++) {
      var c3 = candidates[ci3];
      var candWords = getSignificantWords(c3.name);

      // Count words from our assignment found in candidate (with fuzzy matching)
      var matchedFromAssign = 0;
      for (var wi = 0; wi < assignWords.length; wi++) {
        var aw = assignWords[wi];
        // Exact match first
        if (candWords.indexOf(aw) !== -1) {
          matchedFromAssign++;
        } else {
          // Fuzzy: match if one word starts with the other, or edit distance <= 2
          for (var cwi = 0; cwi < candWords.length; cwi++) {
            var cw = candWords[cwi];
            if (aw.length >= 4 && cw.length >= 4) {
              // Prefix match (e.g., "resist" matches "resistence" and "resistance")
              var minLen = Math.min(aw.length, cw.length);
              var shared = 0;
              for (var chi = 0; chi < minLen; chi++) {
                if (aw[chi] === cw[chi]) shared++; else break;
              }
              if (shared >= Math.max(minLen - 2, Math.floor(minLen * 0.7))) {
                matchedFromAssign++;
                break;
              }
            }
          }
        }
      }

      // Jaccard-like: intersection / union
      // Union = unique words from both sides
      var allWordsSet = {};
      assignWords.forEach(function(w) { allWordsSet[w] = true; });
      candWords.forEach(function(w) { allWordsSet[w] = true; });
      var unionSize = Object.keys(allWordsSet).length;
      var jaccardScore = unionSize > 0 ? matchedFromAssign / unionSize : 0;

      // Also compute recall: what fraction of our words matched
      var recall = assignWords.length > 0 ? matchedFromAssign / assignWords.length : 0;

      if (jaccardScore > bestScore && recall >= 0.5) {
        bestScore = jaccardScore;
        bestCandidate = c3;
      }
    }

    if (bestCandidate && bestScore >= 0.4) {
      targetRow = bestCandidate.row;
      emit('status', { message: 'Best word match (score ' + bestScore.toFixed(2) + '): "' + bestCandidate.name + '"' });
    }
  }

  if (!targetRow) {
    emit('status', { message: 'Assignment "' + assignmentName + '" not found on student detail page' });
    await screenshot(page, 'assignment_not_found');
    return false;
  }

  // Now find the Comment cell in this row.
  // From the screenshot: the Comment column has cells with blue dashed borders.
  // The DevTools showed: div.comment-cell-display.record input.data-field-comment

  // The comment cell is: td.comment-cell > div[data-field="comment"]
  // Click the div to activate it, then type the comment and Tab to save.
  const commentDiv = targetRow.locator('td.comment-cell div[data-field="comment"]').first();

  if (await commentDiv.isVisible({ timeout: 3000 }).catch(() => false)) {
    emit('status', { message: 'Found comment div (td.comment-cell div[data-field="comment"])' });
    await commentDiv.click();
    await page.waitForTimeout(500);

    // After clicking, the div may become an editable input or a focused field appears
    // Try typing into whatever is now focused
    const activeEl = page.locator('input:focus, textarea:focus, div[contenteditable="true"]:focus').first();
    if (await activeEl.isVisible({ timeout: 1500 }).catch(() => false)) {
      await activeEl.fill('');
      await activeEl.fill(commentText);
      await screenshot(page, 'comment_typed');
      await page.keyboard.press('Tab');
      await page.waitForTimeout(1500);
      emit('status', { message: 'Comment entered and saved' });
      return true;
    }

    // The div itself might accept input — try filling it directly
    try {
      await commentDiv.fill('');
      await commentDiv.fill(commentText);
      await screenshot(page, 'comment_typed_div_fill');
      await page.keyboard.press('Tab');
      await page.waitForTimeout(1500);
      emit('status', { message: 'Comment entered (div fill) and saved' });
      return true;
    } catch (e) {
      // fill() may not work on non-input elements
    }

    // Try typing with keyboard
    await commentDiv.click();
    await page.waitForTimeout(300);
    await page.keyboard.press('Control+A');
    await page.keyboard.type(commentText, { delay: 5 });
    await screenshot(page, 'comment_typed_keyboard');
    await page.keyboard.press('Tab');
    await page.waitForTimeout(1500);
    emit('status', { message: 'Comment entered (keyboard type) and saved' });
    return true;
  }

  // Fallback: try td.comment-cell directly
  const commentTd = targetRow.locator('td.comment-cell').first();
  if (await commentTd.isVisible({ timeout: 2000 }).catch(() => false)) {
    emit('status', { message: 'Found td.comment-cell, clicking...' });
    await commentTd.click();
    await page.waitForTimeout(500);

    const activeEl = page.locator('input:focus, textarea:focus').first();
    if (await activeEl.isVisible({ timeout: 1500 }).catch(() => false)) {
      await activeEl.fill('');
      await activeEl.fill(commentText);
      await page.keyboard.press('Tab');
      await page.waitForTimeout(1500);
      emit('status', { message: 'Comment entered (td.comment-cell) and saved' });
      return true;
    }
  }

  emit('status', { message: 'Could not find comment input for assignment' });
  await screenshot(page, 'no_comment_input');
  return false;
}

/**
 * Navigate back to the gradebook list view from a student detail page.
 * Click "Gradebook" in the left sidebar.
 */
async function returnToGradebookList(page) {
  // Click the Gradebook link in the sidebar
  const gbLink = page.locator('div.site-menu-sidebar a:has-text("Gradebook")').first();
  if (await gbLink.isVisible({ timeout: 3000 }).catch(() => false)) {
    await gbLink.click();
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);
    return;
  }

  // Fallback: use browser back
  await page.goBack({ waitUntil: 'networkidle', timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
}


// ══════════════════════════════════════════════════════════════
// MAIN COMMENT ENTRY LOOP
// ══════════════════════════════════════════════════════════════

async function processSection(page, periodComments, assignmentName, globalOffset, globalTotal) {
  let entered = 0;
  let failed = 0;
  let skipped = 0;
  let notFoundStudents = [];  // students not found in this section (may be in alternate section)

  for (let i = 0; i < periodComments.length; i++) {
    const comment = periodComments[i];
    const studentName = comment.student_name || '';
    const studentId = comment.student_id || '';
    const commentText = comment.comment || '';
    const globalIdx = globalOffset + i;

    if (!commentText || !commentText.trim()) {
      skipped++;
      emit('progress', {
        current: globalIdx + 1, total: globalTotal,
        student: studentName, message: 'Skipped (no comment)',
        entered: entered,
      });
      continue;
    }

    emit('progress', {
      current: globalIdx + 1, total: globalTotal,
      student: studentName, message: 'Finding student in gradebook...',
      entered: entered,
    });

    // Get the current student name links from the gradebook list
    const studentLinks = await getStudentNameLinks(page);

    if (studentLinks.length === 0) {
      failed++;
      emit('progress', {
        current: globalIdx + 1, total: globalTotal,
        student: studentName, message: 'No students visible in gradebook',
        entered: entered,
      });
      continue;
    }

    // Find matching student
    let matched = null;

    // Strategy 1: Match by student ID
    if (studentId) {
      for (const s of studentLinks) {
        if (s.studentId === studentId) {
          matched = s;
          break;
        }
      }
    }

    // Strategy 2: Match by name
    if (!matched) {
      for (const s of studentLinks) {
        if (namesMatch(s.name, studentName)) {
          matched = s;
          break;
        }
      }
    }

    if (!matched) {
      notFoundStudents.push(comment);
      emit('progress', {
        current: globalIdx + 1, total: globalTotal,
        student: studentName, message: 'Student not found in this section — will retry alternate',
        entered: entered,
      });
      continue;
    }

    emit('progress', {
      current: globalIdx + 1, total: globalTotal,
      student: studentName, message: 'Opening student detail page...',
      entered: entered,
    });

    // Click the student name to open their detail page.
    // From DevTools: the name is inside span.student-name-link which contains
    // an input[data-field="student_name"]. The span itself has a click handler.
    // Strategy: try multiple click approaches until the page URL changes.
    const urlBefore = page.url();
    let navigated = false;

    // Focus uses AJAX navigation — clicking the student name loads the student
    // detail view in-page. The detail page shows the student's name as a header
    // and has a "Percent of Grade" table + individual assignment rows.
    // We detect success by looking for "Percent of Grade" text which only appears
    // on the student detail page, NOT on the main gradebook list.

    // Click the span.student-name-link using JS click (proven to work)
    emit('status', { message: 'Clicking student name via JS...' });
    await matched.element.evaluate(function(el) { el.click(); }).catch(function() {});
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(function() {});
    await page.waitForTimeout(3000);

    // Check if we're on the student detail page
    let onDetailPage = await page.locator('text=Percent of Grade').first()
      .isVisible({ timeout: 3000 }).catch(function() { return false; });

    if (!onDetailPage) {
      // Try regular click
      emit('status', { message: 'JS click did not open detail, trying regular click...' });
      await matched.element.click().catch(function() {});
      await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(function() {});
      await page.waitForTimeout(3000);
      onDetailPage = await page.locator('text=Percent of Grade').first()
        .isVisible({ timeout: 3000 }).catch(function() { return false; });
    }

    if (!onDetailPage && matched.studentId) {
      // Try direct URL with student_id
      emit('status', { message: 'Trying direct URL for student ' + matched.studentId + '...' });
      var studentUrl = FOCUS_BASE + '/Modules.php?modname=Grades/Gradebook.php&student_id=' + matched.studentId;
      await page.goto(studentUrl, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(function() {});
      await page.waitForTimeout(3000);
      onDetailPage = await page.locator('text=Percent of Grade').first()
        .isVisible({ timeout: 3000 }).catch(function() { return false; });
    }

    if (!onDetailPage) {
      emit('status', { message: 'Could not navigate to student detail page' });
      await screenshot(page, 'navigation_failed');
      failed++;
      emit('progress', {
        current: globalIdx + 1, total: globalTotal,
        student: studentName, message: 'Could not open student page',
        entered: entered,
      });
      continue;
    }

    emit('status', { message: 'On student detail page' });
    await screenshot(page, 'after_student_click');

    // Find the assignment and enter the comment
    const success = await findAndFillComment(page, assignmentName, commentText);

    if (success) {
      entered++;
      emit('progress', {
        current: globalIdx + 1, total: globalTotal,
        student: studentName, message: 'Comment saved!',
        entered: entered,
      });
    } else {
      failed++;
      emit('progress', {
        current: globalIdx + 1, total: globalTotal,
        student: studentName, message: 'Failed to enter comment',
        entered: entered,
      });
    }

    // Return to gradebook list for the next student
    await returnToGradebookList(page);
    await page.waitForTimeout(1000);
  }

  return { entered, failed, skipped, notFoundStudents };
}


// ══════════════════════════════════════════════════════════════
// MAIN
// ══════════════════════════════════════════════════════════════

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const fromManifest = args.includes('--from-manifest');
  screenshotsEnabled = args.includes('--screenshot');
  const filteredArgs = args.filter(a => !a.startsWith('--'));

  // Load comment data
  let data;
  if (fromManifest) {
    data = loadFromManifest();
  } else if (filteredArgs.length > 0) {
    data = loadComments(filteredArgs[0]);
  } else {
    emit('error', { message: 'Usage: node focus-comments-upload.js [--dry-run] [--screenshot] [--from-manifest | comments.json]' });
    process.exit(1);
  }

  const comments = data.comments || [];
  const assignment = data.assignment || 'Assignment';
  const byPeriod = data.byPeriod || {};

  if (comments.length === 0) {
    emit('error', { message: 'No comments to upload.' });
    process.exit(1);
  }

  // Sort periods: numbered periods first (Period 1, 2, ...), then empty/unknown last
  const periods = Object.keys(byPeriod).sort(function(a, b) {
    var aNum = parseInt(a.replace(/[^0-9]/g, '')) || 999;
    var bNum = parseInt(b.replace(/[^0-9]/g, '')) || 999;
    return aNum - bNum;
  });
  emit('status', {
    message: 'Loaded ' + comments.length + ' comments for "' + assignment + '" across ' + periods.length + ' period(s): ' + periods.join(', '),
  });

  // Dry run — just log what would happen
  if (dryRun) {
    emit('status', { message: 'DRY RUN — would upload ' + comments.length + ' comments' });
    for (let i = 0; i < comments.length; i++) {
      const c = comments[i];
      emit('progress', {
        current: i + 1, total: comments.length,
        student: c.student_name || c.student_id,
        message: '[dry-run] ' + (c.comment || '').substring(0, 80),
        entered: i + 1,
      });
    }
    emit('done', { entered: comments.length, failed: 0, skipped: 0, total: comments.length });
    process.exit(0);
  }

  // Load credentials and launch browser
  const creds = loadCredentials();

  fs.mkdirSync(BROWSER_DATA_DIR, { recursive: true });
  const browser = await chromium.launchPersistentContext(BROWSER_DATA_DIR, {
    headless: false,
    viewport: { width: 1440, height: 900 },
  });

  const page = browser.pages()[0] || await browser.newPage();

  let totalEntered = 0;
  let totalFailed = 0;
  let totalSkipped = 0;
  let globalOffset = 0;

  try {
    await login(page, creds);
    await navigateToGradebook(page);

    // Process each period/section
    for (const periodName of periods) {
      const periodComments = byPeriod[periodName];
      if (!periodComments || periodComments.length === 0) continue;

      emit('status', { message: 'Processing ' + periodName + ' (' + periodComments.length + ' students)...' });

      // Select the section in the top-right period dropdown
      // Skip for empty period names or 'All' (no switch needed)
      var sections = [];
      if (periodName && periodName !== 'All' && /\d/.test(periodName)) {
        sections = await getSectionsForPeriod(page, periodName);
        if (sections.length === 0) {
          emit('status', { message: 'Could not find sections for ' + periodName + ' — trying with current view' });
        } else {
          await selectSectionByValue(page, sections[0]);
        }
      } else if (!periodName || periodName === '') {
        emit('status', { message: 'Skipping period switch (no period assigned) — will try in current view' });
      }

      await screenshot(page, 'section_' + periodName.replace(/[^a-zA-Z0-9]/g, ''));

      // Enter comments for each student in the first section
      const result = await processSection(page, periodComments, assignment, globalOffset, comments.length);
      totalEntered += result.entered;
      totalFailed += result.failed;
      totalSkipped += result.skipped;

      // If some students weren't found and there are alternate sections for this period,
      // retry them in each alternate section (e.g., Period 5 has USH605ADV + GUSH005)
      var retryStudents = result.notFoundStudents || [];
      for (var altIdx = 1; altIdx < sections.length && retryStudents.length > 0; altIdx++) {
        emit('status', { message: retryStudents.length + ' student(s) not found — trying alternate section: ' + sections[altIdx].text });
        await selectSectionByValue(page, sections[altIdx]);
        var retryResult = await processSection(page, retryStudents, assignment, globalOffset, comments.length);
        totalEntered += retryResult.entered;
        totalSkipped += retryResult.skipped;
        // Students found in this alternate section reduce the not-found count
        totalFailed -= retryResult.entered + retryResult.skipped;
        retryStudents = retryResult.notFoundStudents || [];
      }

      // Any students still not found after all sections are true failures
      totalFailed += retryStudents.length;
      if (retryStudents.length > 0) {
        var names = retryStudents.map(function(c) { return c.student_name; }).join(', ');
        emit('status', { message: retryStudents.length + ' student(s) not found in any section: ' + names });
      }

      globalOffset += periodComments.length;
    }

    const msg = 'Entered ' + totalEntered + ' comments, ' + totalSkipped + ' skipped, ' + totalFailed + ' failed';
    emit('done', {
      entered: totalEntered,
      skipped: totalSkipped,
      failed: totalFailed,
      total: comments.length,
      message: msg,
    });

    emit('status', { message: 'Done! Browser stays open for 30 seconds to verify results...' });
    await page.waitForTimeout(30000);

  } catch (error) {
    emit('error', { message: 'Fatal error: ' + error.message });
    try {
      await page.screenshot({ path: ERROR_SCREENSHOT });
      emit('status', { message: 'Error screenshot saved to ' + ERROR_SCREENSHOT });
    } catch (e) {
      // ignore screenshot failure
    }
  } finally {
    await browser.close();
  }
}

main();
