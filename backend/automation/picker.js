#!/usr/bin/env node
/**
 * Element Picker for Graider Automation Builder.
 * Opens a browser, injects a hover/click overlay, emits picked selectors as NDJSON.
 * Usage: node picker.js --url https://example.com
 */
const { chromium } = require('playwright');

function emit(type, data) {
    process.stdout.write(JSON.stringify({ type, ts: new Date().toISOString(), ...data }) + '\n');
}

const OVERLAY_SCRIPT = `
(function() {
    if (window.__graiderPickerActive) return;
    window.__graiderPickerActive = true;

    var banner = document.createElement('div');
    banner.id = '__graider_picker_banner';
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;background:#6366f1;color:white;padding:10px 16px;font-family:sans-serif;font-size:14px;display:flex;align-items:center;gap:12px;box-shadow:0 2px 8px rgba(0,0,0,0.3);';
    banner.innerHTML = '<strong>Graider Element Picker</strong> \\u2014 Click any element to capture its selector. Press Esc to stop.';
    document.body.prepend(banner);

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
            var cls = el.className.trim().split(/\\\\s+/).slice(0, 2).join('.');
            if (cls) return el.tagName.toLowerCase() + '.' + cls;
        }
        return el.tagName.toLowerCase();
    }

    document.addEventListener('mouseover', function(e) {
        if (e.target.id === '__graider_picker_banner' || e.target.closest('#__graider_picker_banner')) return;
        if (lastHovered) lastHovered.style.outline = origOutline;
        lastHovered = e.target;
        origOutline = e.target.style.outline;
        e.target.style.outline = '3px solid #6366f1';
    }, true);

    document.addEventListener('click', function(e) {
        if (e.target.id === '__graider_picker_banner' || e.target.closest('#__graider_picker_banner')) return;
        e.preventDefault();
        e.stopPropagation();
        window.__graiderLastPick = {
            selector: getSelector(e.target),
            text: (e.target.textContent || '').trim().substring(0, 80),
            tag: e.target.tagName.toLowerCase()
        };
    }, true);

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') window.__graiderPickerDone = true;
    });
})();
`;

async function main() {
    const args = process.argv.slice(2);
    const urlIdx = args.indexOf('--url');
    const startUrl = urlIdx !== -1 ? args[urlIdx + 1] : 'about:blank';

    emit('picker_started', { url: startUrl });

    const browser = await chromium.launch({ headless: false });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();

    await context.addInitScript(OVERLAY_SCRIPT);
    await page.goto(startUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });

    while (true) {
        await page.waitForTimeout(300);
        try {
            var pick = await page.evaluate(() => {
                var p = window.__graiderLastPick;
                window.__graiderLastPick = null;
                return p;
            });
            if (pick) {
                emit('selector_picked', { selector: pick.selector, text: pick.text, tag: pick.tag });
            }
            var done = await page.evaluate(() => window.__graiderPickerDone);
            if (done) break;
            if (!browser.isConnected()) break;
        } catch {
            break;
        }
    }

    emit('done', { message: 'Picker closed' });
    await browser.close();
}

main();
