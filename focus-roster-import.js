#!/usr/bin/env node
/**
 * Focus Roster Import
 * Logs into Focus SIS via VPortal SSO, runs the "Student Data" saved report,
 * exports the CSV, and writes structured roster + contact data.
 *
 * Reads credentials from ~/.graider_data/portal_credentials.json
 * Reads teacher name from ~/.graider_settings.json (config.teacher_name)
 *
 * Usage:
 *   node focus-roster-import.js
 *
 * Output:
 *   Writes ~/.graider_data/focus_roster_import.json with roster grouped by
 *   teacher's periods, enriched contacts, student schedules, and 504 status.
 *   Prints JSON status lines to stdout for real-time progress reporting.
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const GRAIDER_DATA_DIR = path.join(process.env.HOME, '.graider_data');
const CREDS_PATH = path.join(GRAIDER_DATA_DIR, 'portal_credentials.json');
const SETTINGS_PATH = path.join(process.env.HOME, '.graider_settings.json');
const OUTPUT_PATH = path.join(GRAIDER_DATA_DIR, 'focus_roster_import.json');
const DOWNLOAD_DIR = path.join(GRAIDER_DATA_DIR, 'focus_downloads');
const ERROR_SCREENSHOT_PATH = path.join(GRAIDER_DATA_DIR, 'focus-roster-error.png');

function emit(type, message, data) {
  const line = JSON.stringify({ type, message, data: data || null, ts: new Date().toISOString() });
  process.stdout.write(line + '\n');
}

function loadCredentials() {
  if (!fs.existsSync(CREDS_PATH)) {
    emit('error', 'VPortal credentials not configured. Go to Graider Settings > Tools > District Portal.');
    process.exit(1);
  }
  try {
    const raw = JSON.parse(fs.readFileSync(CREDS_PATH, 'utf-8'));
    const email = raw.email;
    const password = Buffer.from(raw.password, 'base64').toString();
    if (!email || !password) {
      emit('error', 'Credentials file is incomplete.');
      process.exit(1);
    }
    return { email, password };
  } catch (e) {
    emit('error', 'Error reading credentials: ' + e.message);
    process.exit(1);
  }
}

function loadTeacherName() {
  try {
    if (fs.existsSync(SETTINGS_PATH)) {
      const settings = JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf-8'));
      const name = (settings.config && settings.config.teacher_name) || '';
      if (name) {
        // Extract last name for matching (e.g., "Mr. Crionas" -> "Crionas")
        const parts = name.replace(/^(Mr\.|Mrs\.|Ms\.|Dr\.|Miss)\s*/i, '').trim().split(/\s+/);
        return parts[parts.length - 1]; // Last word is the last name
      }
    }
  } catch (e) {
    emit('warning', 'Could not read teacher name from settings: ' + e.message);
  }
  return '';
}

// ══════════════════════════════════════════════════════════════
// CSV PARSING
// ══════════════════════════════════════════════════════════════

function parseCSVLine(line) {
  const fields = [];
  let field = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      inQuotes = !inQuotes;
    } else if (ch === ',' && !inQuotes) {
      fields.push(field.trim());
      field = '';
    } else {
      field += ch;
    }
  }
  fields.push(field.trim());
  return fields;
}

function clean(val) {
  return (val || '').replace(/"/g, '').trim();
}

/**
 * Parse the "Teacher / Period" column value.
 * Formats:
 *   "04 04 - USH006 - Alexander  Crionas"
 *   "07 07 - S1 - 556 - Reginald Eugene Mays"
 * Returns { periodNum, courseCode, teacher, semester }
 */
function parseTeacherPeriod(value) {
  const parts = value.split(' - ').map(p => p.trim());
  if (parts.length < 3) return null;

  const periodStr = parts[0]; // "04 04"
  const periodNum = parseInt(periodStr.split(' ')[0], 10);
  if (isNaN(periodNum)) return null;

  const teacher = parts[parts.length - 1]; // Last part is always teacher name

  // Middle parts are semester (if present) and course code
  let courseCode = '';
  let semester = '';
  const middleParts = parts.slice(1, -1);
  for (const mp of middleParts) {
    if (/^S\d+$/i.test(mp)) {
      semester = mp;
    } else {
      courseCode = mp;
    }
  }

  return { periodNum, courseCode, teacher, semester };
}

/**
 * Build column index map from CSV headers.
 * Returns an object with indices for each known column.
 */
function buildColumnMap(headers) {
  const h = headers.map(x => x.toLowerCase());
  return {
    name: h.findIndex(x => x.includes('last') && x.includes('first')),
    studentId: h.findIndex(x => x === 'student id' || x.includes('student id')),
    localId: h.findIndex(x => x === 'local id' || x.includes('local id')),
    // Primary contact
    primaryPhone: h.findIndex(x => x.includes('primary contact') && x.includes('cell phone')),
    primaryCallOut: h.findIndex(x => x.includes('primary contact') && x.includes('call out')),
    primaryEmail: h.findIndex(x => x.includes('primary contact') && x.includes('email')),
    primaryFirstName: h.findIndex(x => x.includes('primary contact') && x.includes('first name')),
    primaryLastName: h.findIndex(x => x.includes('primary contact') && x.includes('last name')),
    primaryRelationship: h.findIndex(x => x.includes('primary contact') && x.includes('relationship')),
    // Secondary contact
    secondaryPhone: h.findIndex(x => x.includes('secondary contact') && x.includes('cell phone')),
    secondaryCallOut: h.findIndex(x => x.includes('secondary contact') && x.includes('call out')),
    secondaryFirstName: h.findIndex(x => x.includes('secondary contact') && x.includes('first name')),
    secondaryLastName: h.findIndex(x => x.includes('secondary contact') && x.includes('last name')),
    secondaryRelationship: h.findIndex(x => x.includes('secondary contact') && x.includes('relationship')),
    // Third contact
    thirdPhone: h.findIndex(x => x.includes('third contact') && x.includes('cell phone')),
    thirdCallOut: h.findIndex(x => x.includes('third contact') && x.includes('call out')),
    thirdEmail: h.findIndex(x => x.includes('third contact') && x.includes('email')),
    thirdFirstName: h.findIndex(x => x.includes('third contact') && x.includes('first name')),
    thirdLastName: h.findIndex(x => x.includes('third contact') && x.includes('last name')),
    thirdRelationship: h.findIndex(x => x.includes('third contact') && x.includes('relationship')),
    // Other
    plan504: h.findIndex(x => x.includes('504')),
    teacherPeriod: h.findIndex(x => x.includes('teacher') && x.includes('period')),
  };
}

function getField(fields, idx) {
  return idx >= 0 && idx < fields.length ? clean(fields[idx]) : '';
}

/**
 * Extract a contact object from a CSV row given column indices.
 */
function extractContact(fields, phoneIdx, callOutIdx, emailIdx, firstNameIdx, lastNameIdx, relIdx) {
  const phone = getField(fields, phoneIdx);
  const email = getField(fields, emailIdx);
  const firstName = getField(fields, firstNameIdx);
  const lastName = getField(fields, lastNameIdx);
  const relationship = getField(fields, relIdx);
  const callOut = getField(fields, callOutIdx).toLowerCase() === 'yes';

  // Only return if there's meaningful data
  if (!firstName && !lastName && !phone && !email) return null;

  return { first_name: firstName, last_name: lastName, relationship, phone, email, call_out: callOut };
}

/**
 * Parse the exported CSV with full column awareness.
 * Returns raw row objects (one per CSV row, not deduplicated).
 */
function parseExportedCSV(filepath) {
  emit('progress', 'Parsing exported file: ' + path.basename(filepath));

  const content = fs.readFileSync(filepath, 'utf-8');
  const lines = content.split('\n').map(l => l.trim()).filter(Boolean);

  if (lines.length < 2) {
    emit('warning', 'Export file has no data rows');
    return [];
  }

  const headers = parseCSVLine(lines[0]);
  const col = buildColumnMap(headers);
  emit('progress', 'CSV columns mapped (' + headers.length + ' columns)');

  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const fields = parseCSVLine(lines[i]);
    if (fields.length < 3) continue;

    const name = getField(fields, col.name);
    const studentId = getField(fields, col.studentId);
    if (!name && !studentId) continue;

    const localId = getField(fields, col.localId);
    const has504 = getField(fields, col.plan504).toLowerCase() === 'yes';
    const teacherPeriodRaw = getField(fields, col.teacherPeriod);
    const parsed = teacherPeriodRaw ? parseTeacherPeriod(teacherPeriodRaw) : null;

    // Extract all 3 contacts
    const primaryContact = extractContact(fields,
      col.primaryPhone, col.primaryCallOut, col.primaryEmail,
      col.primaryFirstName, col.primaryLastName, col.primaryRelationship);
    const secondaryContact = extractContact(fields,
      col.secondaryPhone, col.secondaryCallOut, -1,
      col.secondaryFirstName, col.secondaryLastName, col.secondaryRelationship);
    const thirdContact = extractContact(fields,
      col.thirdPhone, col.thirdCallOut, col.thirdEmail,
      col.thirdFirstName, col.thirdLastName, col.thirdRelationship);

    rows.push({
      name,
      student_id: studentId,
      local_id: localId,
      has_504: has504,
      teacher_period: parsed,
      teacher_period_raw: teacherPeriodRaw,
      contacts: {
        primary: primaryContact,
        secondary: secondaryContact,
        third: thirdContact,
      },
    });
  }

  emit('progress', 'Parsed ' + rows.length + ' raw rows from CSV');
  return rows;
}

// ══════════════════════════════════════════════════════════════
// BROWSER AUTOMATION (login, navigate, report, export)
// ══════════════════════════════════════════════════════════════

async function login(page, creds) {
  emit('progress', 'Opening VPortal...');
  await page.goto('https://vportal.volusia.k12.fl.us/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  try {
    await page.click('button.btn-saml', { timeout: 5000 });
    emit('progress', 'Clicked portal login, waiting for ADFS...');
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForTimeout(2000);
  } catch (e) {
    emit('progress', 'No portal login button found, may already be past this step...');
  }

  const currentUrl = page.url().toLowerCase();
  if (currentUrl.includes('adfs') || currentUrl.includes('login')) {
    try {
      emit('progress', 'Entering credentials on ADFS...');
      await page.fill('#userNameInput', creds.email, { timeout: 5000 });
      await page.fill('#passwordInput', creds.password, { timeout: 5000 });
      await page.click('#submitButton');
      emit('progress', 'Signing in...');
      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForTimeout(3000);
    } catch (e) {
      emit('progress', 'ADFS form not found, may already be authenticated...');
    }
  }

  if (page.url().includes('login.microsoftonline.com') || page.url().includes('login.microsoft.com')) {
    emit('progress', 'Microsoft login detected — complete 2FA in the browser...');
    try {
      await page.waitForURL(
        url => !url.includes('login.microsoftonline.com') && !url.includes('login.microsoft.com'),
        { timeout: 120000 }
      );
      emit('progress', '2FA complete!');
    } catch (e) {
      emit('progress', '2FA timed out, continuing anyway...');
    }
  }

  await page.waitForTimeout(2000);
  emit('progress', 'Logged in to VPortal');
}

async function navigateToFocus(page) {
  emit('progress', 'Navigating to Focus...');
  await page.goto(
    'https://volusia.focusschoolsoftware.com/focus/Modules.php?modname=misc%2FPortal.php',
    { waitUntil: 'domcontentloaded', timeout: 30000 }
  );
  await page.waitForTimeout(3000);
  emit('progress', 'In Focus SIS');
}

async function runSavedReport(page) {
  emit('progress', 'Opening Reports menu...');
  await page.click('div.site-menu-group-title-text:has-text("Reports")', { timeout: 10000 });
  await page.waitForTimeout(1000);

  emit('progress', 'Opening Saved Reports...');
  await page.click('a.site-menu-item:has-text("Saved Reports")', { timeout: 10000 });
  await page.waitForLoadState('domcontentloaded', { timeout: 15000 });
  await page.waitForTimeout(2000);

  emit('progress', 'Looking for Student Data report...');
  const titleInputs = await page.locator('input.data-field-title').all();
  let clicked = false;

  for (const input of titleInputs) {
    const value = await input.inputValue().catch(() => '');
    if (value.trim() === 'Student Data') {
      const row = input.locator('xpath=ancestor::tr');
      const playBtn = row.locator('button.run-report').first();
      if (await playBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await playBtn.click();
        clicked = true;
        emit('progress', 'Clicked play button for "Student Data"');
        break;
      }
      const altBtn = row.locator('button.green, button.ui.green').first();
      if (await altBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await altBtn.click();
        clicked = true;
        emit('progress', 'Clicked green button for "Student Data"');
        break;
      }
    }
  }

  if (!clicked) {
    emit('error', 'Could not find "Student Data" saved report');
    await page.screenshot({ path: ERROR_SCREENSHOT_PATH });
    throw new Error('Could not find Student Data report');
  }

  emit('progress', 'Report running, waiting for data to load...');
  await page.waitForLoadState('domcontentloaded', { timeout: 30000 });
  await page.waitForTimeout(5000);
}

async function exportReport(page) {
  emit('progress', 'Exporting report as CSV...');
  fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });

  const exportBtn = page.locator(
    'img[src*="excel"], img[src*="csv"], img[src*="spreadsheet"], ' +
    'a:has(img[src*="excel"]), a:has(img[src*="csv"]), ' +
    'a:has(img[src*="spreadsheet"])'
  ).first();

  if (await exportBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
    const download = await Promise.all([
      page.waitForEvent('download', { timeout: 30000 }),
      exportBtn.click(),
    ]).then(([dl]) => dl).catch(() => null);

    if (download) {
      const downloadPath = path.join(DOWNLOAD_DIR, download.suggestedFilename() || 'student_data.csv');
      await download.saveAs(downloadPath);
      emit('progress', 'Downloaded: ' + path.basename(downloadPath));
      return downloadPath;
    }
  }

  emit('progress', 'Trying alternate export approach...');
  const exportLink = page.locator(
    'a:has-text("Export"), button:has-text("Export"), ' +
    '.export-button, [title*="Export"], [title*="CSV"]'
  ).first();

  if (await exportLink.isVisible({ timeout: 3000 }).catch(() => false)) {
    const download = await Promise.all([
      page.waitForEvent('download', { timeout: 30000 }),
      exportLink.click(),
    ]).then(([dl]) => dl).catch(() => null);

    if (download) {
      const downloadPath = path.join(DOWNLOAD_DIR, download.suggestedFilename() || 'student_data.csv');
      await download.saveAs(downloadPath);
      emit('progress', 'Downloaded: ' + path.basename(downloadPath));
      return downloadPath;
    }
  }

  emit('progress', 'Export download failed');
  return null;
}

// ══════════════════════════════════════════════════════════════
// DATA PROCESSING
// ══════════════════════════════════════════════════════════════

/**
 * Process raw CSV rows into structured output grouped by teacher's periods.
 * - Filters rows to the configured teacher
 * - Groups students by period number
 * - Deduplicates students (merges semester splits)
 * - Builds each student's full schedule from ALL their rows
 * - Collects all parent emails/phones for backward-compatible arrays
 */
function processRows(rawRows, teacherLastName) {
  // Step 1: Build a lookup of all rows per student (for schedules)
  const studentRows = {};
  for (const row of rawRows) {
    const key = row.student_id || row.name;
    if (!studentRows[key]) studentRows[key] = [];
    studentRows[key].push(row);
  }

  // Step 2: Filter to teacher's rows only
  const teacherLower = teacherLastName.toLowerCase();
  const teacherRows = rawRows.filter(r => {
    if (!r.teacher_period) return false;
    return r.teacher_period.teacher.toLowerCase().includes(teacherLower);
  });

  emit('progress', 'Found ' + teacherRows.length + ' rows for teacher "' + teacherLastName + '"');

  if (teacherRows.length === 0) {
    // List available teachers for debugging
    const teachers = new Set();
    for (const r of rawRows) {
      if (r.teacher_period) teachers.add(r.teacher_period.teacher);
    }
    emit('warning', 'Available teachers: ' + Array.from(teachers).join(', '));
    return {};
  }

  // Step 3: Group teacher's rows by period number, dedup students
  const periods = {};

  for (const row of teacherRows) {
    const tp = row.teacher_period;
    const periodKey = 'Period ' + tp.periodNum;

    if (!periods[periodKey]) {
      periods[periodKey] = {
        period_num: tp.periodNum,
        course_codes: new Set(),
        studentMap: {},
      };
    }

    periods[periodKey].course_codes.add(tp.courseCode);

    const sid = row.student_id || row.name;
    if (!periods[periodKey].studentMap[sid]) {
      // Build schedule from ALL of this student's rows (not just teacher's)
      const allStudentRows = studentRows[sid] || [];
      const schedule = [];
      const seenScheduleKeys = new Set();

      for (const sr of allStudentRows) {
        if (!sr.teacher_period) continue;
        const stp = sr.teacher_period;
        // Skip semester duplicates for same period+course+teacher
        const schedKey = stp.periodNum + '-' + stp.courseCode + '-' + stp.teacher;
        if (seenScheduleKeys.has(schedKey)) continue;
        seenScheduleKeys.add(schedKey);

        schedule.push({
          period: stp.periodNum,
          course: stp.courseCode,
          teacher: stp.teacher,
          semester: stp.semester || '',
        });
      }
      schedule.sort((a, b) => a.period - b.period);

      // Collect all parent emails and phones (backward-compatible flat arrays)
      const allEmails = [];
      const allPhones = [];
      const contacts = row.contacts;

      if (contacts.primary) {
        if (contacts.primary.email && !allEmails.includes(contacts.primary.email))
          allEmails.push(contacts.primary.email);
        if (contacts.primary.phone && !allPhones.includes(contacts.primary.phone))
          allPhones.push(contacts.primary.phone);
      }
      if (contacts.secondary) {
        if (contacts.secondary.email && !allEmails.includes(contacts.secondary.email))
          allEmails.push(contacts.secondary.email);
        if (contacts.secondary.phone && !allPhones.includes(contacts.secondary.phone))
          allPhones.push(contacts.secondary.phone);
      }
      if (contacts.third) {
        if (contacts.third.email && !allEmails.includes(contacts.third.email))
          allEmails.push(contacts.third.email);
        if (contacts.third.phone && !allPhones.includes(contacts.third.phone))
          allPhones.push(contacts.third.phone);
      }

      periods[periodKey].studentMap[sid] = {
        name: row.name,
        student_id: row.student_id,
        local_id: row.local_id,
        has_504: row.has_504,
        parent_emails: allEmails,
        parent_phones: allPhones,
        contacts: {
          primary: contacts.primary,
          secondary: contacts.secondary,
          third: contacts.third,
        },
        schedule,
      };
    }
  }

  // Step 4: Convert to output format
  const output = {};
  for (const [periodKey, pData] of Object.entries(periods)) {
    output[periodKey] = {
      period_num: pData.period_num,
      course_codes: Array.from(pData.course_codes),
      students: Object.values(pData.studentMap),
    };
  }

  return output;
}

// ══════════════════════════════════════════════════════════════
// MAIN
// ══════════════════════════════════════════════════════════════

async function main() {
  emit('status', 'Starting Focus Roster Import...');

  const creds = loadCredentials();
  const teacherLastName = loadTeacherName();

  if (!teacherLastName) {
    emit('error', 'Teacher name not configured. Go to Graider Settings and set your Teacher Name.');
    process.exit(1);
  }

  emit('progress', 'Teacher filter: "' + teacherLastName + '"');
  fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    acceptDownloads: true,
  });
  const page = await context.newPage();

  try {
    await login(page, creds);
    await navigateToFocus(page);
    await runSavedReport(page);

    const csvPath = await exportReport(page);

    if (!csvPath || !fs.existsSync(csvPath)) {
      emit('error', 'Could not download report CSV');
      await page.screenshot({ path: ERROR_SCREENSHOT_PATH });
      return;
    }

    const rawRows = parseExportedCSV(csvPath);

    if (rawRows.length === 0) {
      emit('error', 'No student data found in CSV');
      await page.screenshot({ path: ERROR_SCREENSHOT_PATH });
      return;
    }

    // Process and filter to teacher's periods
    const periods = processRows(rawRows, teacherLastName);

    if (Object.keys(periods).length === 0) {
      emit('error', 'No periods found for teacher "' + teacherLastName + '"');
      await page.screenshot({ path: ERROR_SCREENSHOT_PATH });
      return;
    }

    // Build summary
    let totalStudents = 0;
    let totalContacts = 0;
    const periodSummary = {};

    for (const [periodKey, pData] of Object.entries(periods)) {
      const count = pData.students.length;
      totalStudents += count;
      totalContacts += pData.students.filter(s =>
        s.parent_emails.length > 0 || s.parent_phones.length > 0
      ).length;
      periodSummary[periodKey] = count + ' students (' + pData.course_codes.join(', ') + ')';
    }

    // Write output file
    const output = {
      imported_at: new Date().toISOString(),
      teacher_filter: teacherLastName,
      periods,
    };

    fs.writeFileSync(OUTPUT_PATH, JSON.stringify(output, null, 2));

    emit('complete', 'Import complete', {
      periods: Object.keys(periods).length,
      total_students: totalStudents,
      total_contacts: totalContacts,
      period_summary: periodSummary,
      output_path: OUTPUT_PATH,
    });

  } catch (error) {
    emit('error', 'Import failed: ' + error.message);
    const activePage = context.pages()[context.pages().length - 1] || page;
    await activePage.screenshot({ path: ERROR_SCREENSHOT_PATH }).catch(() => {});
    emit('error', 'Screenshot saved to ' + ERROR_SCREENSHOT_PATH);
  } finally {
    await page.waitForTimeout(5000);
    await browser.close();
  }
}

main();
