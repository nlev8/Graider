var chromium = require('playwright').chromium;
var path = require('path');
var fs = require('fs');
var BROWSER_DATA_DIR = path.join(process.env.HOME, '.graider_data', 'focus_browser');
var CREDS_PATH = path.join(process.env.HOME, '.graider_data', 'portal_credentials.json');
fs.mkdirSync(BROWSER_DATA_DIR, { recursive: true });

(async function() {
  var browser = await chromium.launchPersistentContext(BROWSER_DATA_DIR, {
    headless: false, viewport: { width: 1440, height: 900 },
  });
  var page = browser.pages()[0] || await browser.newPage();

  // Login
  console.log('Opening VPortal...');
  await page.goto('https://vportal.volusia.k12.fl.us/', { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(2000);
  try {
    await page.click('button.btn-saml', { timeout: 5000 });
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForTimeout(2000);
  } catch(e) {}

  var url = page.url().toLowerCase();
  if (url.includes('adfs') || url.includes('login')) {
    try {
      var raw = JSON.parse(fs.readFileSync(CREDS_PATH, 'utf-8'));
      await page.fill('#userNameInput', raw.email, { timeout: 5000 });
      await page.fill('#passwordInput', Buffer.from(raw.password, 'base64').toString(), { timeout: 5000 });
      await page.click('#submitButton');
      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForTimeout(3000);
    } catch(e) {}
  }

  console.log('Logged in. Going to Focus...');
  await page.goto('https://volusia.focusschoolsoftware.com/focus/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3000);

  // Click Gradebook in sidebar — try multiple selectors
  console.log('Clicking Gradebook in sidebar...');
  var clicked = false;
  var selectors = [
    'div.site-menu-group-title-text:has-text("Gradebook")',
    'a:has-text("Gradebook")',
    'text=Gradebook',
  ];
  for (var si = 0; si < selectors.length; si++) {
    try {
      var el = page.locator(selectors[si]).first();
      if (await el.isVisible({ timeout: 2000 })) {
        await el.click();
        clicked = true;
        console.log('Clicked with: ' + selectors[si]);
        break;
      }
    } catch(e) {}
  }
  if (!clicked) {
    console.log('Could not find Gradebook link, taking screenshot...');
    await page.screenshot({ path: path.join(process.env.HOME, '.graider_data', 'focus_portal.png') });
  }
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(function(){});
  await page.waitForTimeout(3000);
  console.log('After Gradebook click. URL: ' + page.url());

  // Find and click Eli Long
  console.log('Looking for Eli Long...');
  var names = await page.locator('span.student-name-link').all();
  console.log('Found ' + names.length + ' student name links');
  for (var i = 0; i < names.length; i++) {
    var text = await names[i].textContent().catch(function() { return ''; });
    if (text.toLowerCase().includes('long')) {
      console.log('Found: ' + text.trim() + ' — clicking...');
      await names[i].evaluate(function(el) { el.click(); });
      await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(function(){});
      await page.waitForTimeout(3000);
      break;
    }
  }

  console.log('Browser open on Eli grades page. Inspect away.');
  await new Promise(function() {});
})();
