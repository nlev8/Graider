#!/usr/bin/env node
/**
 * Element Picker for Graider Automation Builder.
 * Opens a browser for free navigation. Click the floating button (top-right)
 * or press Option+P (Alt+P) to activate picker mode.
 *
 * Usage:
 *   node picker.js --url https://example.com
 *   node picker.js --url https://example.com --login   (auto-login to VPortal)
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const GRAIDER_DATA_DIR = path.join(process.env.HOME, '.graider_data');
const CREDS_PATH = path.join(GRAIDER_DATA_DIR, 'portal_credentials.json');

function emit(type, data) {
    process.stdout.write(JSON.stringify({ type, ts: new Date().toISOString(), ...data }) + '\n');
}

function loadCredentials() {
    try {
        const data = JSON.parse(fs.readFileSync(CREDS_PATH, 'utf-8'));
        return {
            email: data.email,
            password: Buffer.from(data.password, 'base64').toString()
        };
    } catch (e) {
        emit('error', { message: 'Could not load portal credentials from ' + CREDS_PATH });
        return null;
    }
}

async function doLogin(page) {
    const creds = loadCredentials();
    if (!creds) {
        emit('error', { message: 'Login skipped — no credentials found' });
        return;
    }

    emit('status', { message: 'Navigating to portal for login...' });
    await page.goto('https://vportal.volusia.k12.fl.us/', { waitUntil: 'networkidle', timeout: 30000 });

    try { await page.click('button.btn-saml', { timeout: 5000 }); } catch {}
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});

    const url = page.url();
    if (url.includes('adfs') || url.includes('login')) {
        emit('status', { message: 'Filling login credentials...' });
        await page.fill('#userNameInput', creds.email);
        await page.fill('#passwordInput', creds.password);
        await page.click('#submitButton');
    }

    if (page.url().includes('login.microsoftonline.com')) {
        emit('status', { message: 'Waiting for 2FA approval (up to 2 minutes)...' });
        await page.waitForURL(u => !u.includes('login.microsoftonline.com'), { timeout: 120000 });
    }

    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    emit('status', { message: 'Login complete — navigate to your target, then click the picker button' });
}

// ── Init script injected into EVERY page/navigation via addInitScript ──
// This string runs before any page JS but we defer DOM work until body exists.
const PICKER_INIT_SCRIPT = `
(function() {
    // Only inject into the top-level frame, not iframes
    if (window.top !== window.self) return;
    if (window.__graiderToggleReady) return;

    function boot() {
        if (window.__graiderToggleReady) return;
        window.__graiderToggleReady = true;
        window.__graiderPickerActive = false;
        window.__graiderPickerDone = false;
        window.__graiderLastPick = null;

        var banner = null;
        var lastHovered = null;
        var origOutline = '';

        function getSelector(el) {
            if (el.id) return '#' + el.id;
            var ariaLabel = el.getAttribute('aria-label');
            if (ariaLabel && ariaLabel.length < 60) return '[aria-label="' + ariaLabel.replace(/"/g, '\\\\"') + '"]';
            if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
            var text = (el.textContent || '').trim();
            if (text.length > 0 && text.length < 50 && el.children.length === 0) return 'text=' + text;
            if (el.className && typeof el.className === 'string') {
                var cls = el.className.trim().split(/\\s+/).slice(0, 2).join('.');
                if (cls) return el.tagName.toLowerCase() + '.' + cls;
            }
            return el.tagName.toLowerCase();
        }

        function createFloatingButton() {
            if (document.getElementById('__graider_fab')) return;
            var fab = document.createElement('div');
            fab.id = '__graider_fab';
            fab.style.cssText = 'position:fixed;top:12px;right:12px;z-index:2147483647;width:44px;height:44px;border-radius:10px;background:#6366f1;color:white;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,0.4);font-size:20px;font-family:sans-serif;user-select:none;transition:transform 0.15s ease,background 0.15s ease;';
            fab.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/><path d="M13 13l6 6"/></svg>';
            fab.title = 'Toggle Element Picker (Option+P)';
            fab.addEventListener('mouseenter', function() { fab.style.transform = 'scale(1.1)'; });
            fab.addEventListener('mouseleave', function() { fab.style.transform = 'scale(1)'; });
            fab.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                if (window.__graiderPickerActive) {
                    deactivatePicker();
                } else {
                    activatePicker();
                }
            }, true);
            document.body.appendChild(fab);

            var label = document.createElement('div');
            label.id = '__graider_fab_label';
            label.style.cssText = 'position:fixed;top:60px;right:8px;z-index:2147483647;background:rgba(0,0,0,0.8);color:white;padding:3px 10px;border-radius:6px;font-family:sans-serif;font-size:10px;pointer-events:none;white-space:nowrap;';
            label.textContent = 'Graider Picker';
            document.body.appendChild(label);
            setTimeout(function() { if (label && label.parentNode) label.style.opacity = '0'; }, 4000);
        }

        function activatePicker() {
            window.__graiderPickerActive = true;
            var fab = document.getElementById('__graider_fab');
            if (fab) { fab.style.background = '#ef4444'; fab.title = 'Picker ACTIVE — click to deactivate'; }
            var label = document.getElementById('__graider_fab_label');
            if (label) label.remove();
            banner = document.createElement('div');
            banner.id = '__graider_picker_banner';
            banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483646;background:#6366f1;color:white;padding:8px 16px;font-family:sans-serif;font-size:13px;display:flex;align-items:center;gap:12px;box-shadow:0 2px 8px rgba(0,0,0,0.3);';
            banner.innerHTML = '<strong>PICKER ACTIVE</strong> — Click any element to capture. Press Esc or click the red button to stop.';
            document.body.prepend(banner);
        }

        function deactivatePicker() {
            window.__graiderPickerActive = false;
            if (banner && banner.parentNode) banner.remove();
            banner = null;
            if (lastHovered) {
                lastHovered.style.outline = origOutline;
                lastHovered = null;
            }
            var fab = document.getElementById('__graider_fab');
            if (fab) { fab.style.background = '#6366f1'; fab.title = 'Toggle Element Picker (Option+P)'; }
        }

        document.addEventListener('mouseover', function(e) {
            if (!window.__graiderPickerActive) return;
            if (e.target.closest('#__graider_picker_banner') || e.target.closest('#__graider_fab')) return;
            if (lastHovered) lastHovered.style.outline = origOutline;
            lastHovered = e.target;
            origOutline = e.target.style.outline;
            e.target.style.outline = '3px solid #6366f1';
        }, true);

        document.addEventListener('click', function(e) {
            if (!window.__graiderPickerActive) return;
            if (e.target.closest('#__graider_picker_banner') || e.target.closest('#__graider_fab')) return;
            e.preventDefault();
            e.stopPropagation();
            window.__graiderLastPick = {
                selector: getSelector(e.target),
                text: (e.target.textContent || '').trim().substring(0, 80),
                tag: e.target.tagName.toLowerCase()
            };
        }, true);

        document.addEventListener('keydown', function(e) {
            if (e.altKey && (e.key === 'p' || e.key === 'P' || e.key === '\u03C0')) {
                e.preventDefault();
                if (window.__graiderPickerActive) deactivatePicker();
                else activatePicker();
            } else if (e.key === 'Escape' && window.__graiderPickerActive) {
                deactivatePicker();
            } else if (e.key === 'Q' && e.ctrlKey && e.shiftKey) {
                window.__graiderPickerDone = true;
            }
        });

        createFloatingButton();
    }

    // Wait for body to exist before creating DOM elements
    if (document.body) {
        boot();
    } else if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        // readyState is interactive or complete but body somehow null — poll briefly
        var t = setInterval(function() { if (document.body) { clearInterval(t); boot(); } }, 50);
        setTimeout(function() { clearInterval(t); }, 5000);
    }
})();
`;

async function main() {
    const args = process.argv.slice(2);
    const urlIdx = args.indexOf('--url');
    const startUrl = urlIdx !== -1 ? args[urlIdx + 1] : 'about:blank';
    const doAutoLogin = args.includes('--login');

    emit('picker_started', { url: startUrl, login: doAutoLogin });

    // Use installed Chrome with anti-detection flags. VitalSource (NGL Sync ebook
    // reader) uses nested cross-domain iframes that need third-party cookies and
    // will block navigation if automation is detected.
    const browser = await chromium.launch({
        headless: false,
        channel: 'chrome',
        args: [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
        ],
    });
    const context = await browser.newContext({
        viewport: { width: 1440, height: 900 },
        ignoreHTTPSErrors: true,
        bypassCSP: true,
    });
    // Remove the webdriver flag that sites use to detect automation
    await context.addInitScript(() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
    });

    // Inject the picker script into EVERY page that loads in this context.
    // This survives all navigations, redirects, and new tabs automatically.
    await context.addInitScript(PICKER_INIT_SCRIPT);

    // Also inject into any new pages/tabs that open (popups, window.open, etc.)
    context.on('page', async (newPage) => {
        emit('status', { message: 'New tab detected — picker will auto-inject' });
    });

    const page = await context.newPage();

    // Auto-login if requested
    if (doAutoLogin) {
        try {
            await doLogin(page);
        } catch (err) {
            emit('error', { message: 'Login failed: ' + err.message });
        }
    } else {
        await page.goto(startUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    }

    emit('status', { message: 'Picker button ready (top-right) — click it or press Option+P' });

    // Poll loop: read picked selectors and check for close signal.
    // We no longer need to re-inject — addInitScript handles that.
    while (true) {
        await page.waitForTimeout(500);
        try {
            if (!browser.isConnected()) break;

            // Get the currently active page (in case user opened new tabs)
            var pages = context.pages();
            var activePage = pages[pages.length - 1] || page;

            // Check for picked selectors
            try {
                var pick = await activePage.evaluate(() => {
                    var p = window.__graiderLastPick;
                    window.__graiderLastPick = null;
                    return p;
                });
                if (pick) {
                    emit('selector_picked', { selector: pick.selector, text: pick.text, tag: pick.tag });
                }

                // Check if user wants to close (Ctrl+Shift+Q)
                var done = await activePage.evaluate(() => window.__graiderPickerDone);
                if (done) break;
            } catch {
                // Page might be mid-navigation, that's fine
                continue;
            }
        } catch {
            if (!browser.isConnected()) break;
            continue;
        }
    }

    emit('done', { message: 'Picker closed' });
    await browser.close();
}

main();
