#!/usr/bin/env node
/**
 * Generic Playwright workflow runner for Graider.
 * Executes a workflow JSON file with step-by-step browser automation.
 * Usage: node runner.js /path/to/workflow.json [--var key=value ...]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const GRAIDER_DATA_DIR = path.join(process.env.HOME, '.graider_data');
const CREDS_PATH = path.join(GRAIDER_DATA_DIR, 'portal_credentials.json');
const SCREENSHOTS_DIR = path.join(GRAIDER_DATA_DIR, 'automation_screenshots');

function emit(type, data) {
    process.stdout.write(JSON.stringify({ type, ts: new Date().toISOString(), ...data }) + '\n');
}

function interpolate(str, vars) {
    if (typeof str !== 'string') return str;
    return str.replace(/\{(\w+)\}/g, (_, key) => {
        return vars[key] !== undefined ? String(vars[key]) : `{${key}}`;
    });
}

function interpolateParams(params, vars) {
    const result = {};
    for (const [k, v] of Object.entries(params)) {
        if (typeof v === 'string') result[k] = interpolate(v, vars);
        else if (Array.isArray(v)) result[k] = v;
        else result[k] = v;
    }
    return result;
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
        process.exit(1);
    }
}

// ── Step Executors ──────────────────────────────────────────

async function stepLogin(page, params, ctx) {
    const creds = loadCredentials();
    const portalUrl = params.portal_url || 'https://vportal.volusia.k12.fl.us/';
    emit('status', { message: 'Navigating to portal...' });
    await page.goto(portalUrl, { waitUntil: 'networkidle', timeout: 30000 });

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
    emit('status', { message: 'Login complete' });
}

async function stepNavigate(page, params, ctx) {
    const waitUntil = params.wait_until || 'networkidle';
    await page.goto(interpolate(params.url, ctx.vars), { waitUntil, timeout: 30000 });
}

async function stepClick(page, params, ctx) {
    const selector = interpolate(params.selector, ctx.vars);
    const timeout = params.timeout || 10000;
    await page.locator(selector).first().click({ timeout });
}

async function stepFill(page, params, ctx) {
    const selector = interpolate(params.selector, ctx.vars);
    const value = interpolate(params.value, ctx.vars);
    if (params.clear_first !== false) {
        await page.locator(selector).first().fill('');
    }
    await page.locator(selector).first().fill(value);
}

async function stepSelect(page, params, ctx) {
    const selector = interpolate(params.selector, ctx.vars);
    const option = interpolate(params.option, ctx.vars);
    await page.locator(selector).first().selectOption({ label: option });
}

async function stepWait(page, params, ctx) {
    if (params.ms) {
        await page.waitForTimeout(params.ms);
    }
    if (params.selector) {
        const state = params.state || 'visible';
        await page.locator(interpolate(params.selector, ctx.vars)).first().waitFor({
            state, timeout: params.timeout || 15000
        });
    }
    if (!params.ms && !params.selector) {
        await page.waitForLoadState('networkidle', { timeout: 15000 });
    }
}

async function stepScreenshot(page, params, ctx) {
    const outputDir = interpolate(params.output_dir || SCREENSHOTS_DIR, ctx.vars);
    fs.mkdirSync(outputDir, { recursive: true });
    const filename = interpolate(params.filename || ('screenshot_' + Date.now() + '.png'), ctx.vars);
    const filepath = path.join(outputDir, filename);
    const fullPage = params.full_page !== false;
    await page.screenshot({ path: filepath, fullPage });
    emit('status', { message: 'Screenshot saved: ' + filename });
    return { file: filepath };
}

async function stepExtractText(page, params, ctx) {
    const selector = interpolate(params.selector, ctx.vars);
    const text = await page.locator(selector).first().textContent({ timeout: 10000 });
    const varName = params.variable || 'extracted_text';
    ctx.vars[varName] = (text || '').trim();
    return { variable: varName, value: ctx.vars[varName] };
}

async function stepDownload(page, params, ctx) {
    const selector = interpolate(params.selector, ctx.vars);
    const outputDir = interpolate(params.output_dir || path.join(GRAIDER_DATA_DIR, 'downloads'), ctx.vars);
    fs.mkdirSync(outputDir, { recursive: true });
    const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 30000 }),
        page.locator(selector).first().click()
    ]);
    const filename = download.suggestedFilename();
    const filepath = path.join(outputDir, filename);
    await download.saveAs(filepath);
    emit('status', { message: 'Downloaded: ' + filename });
    return { file: filepath };
}

async function stepKeyboard(page, params, ctx) {
    if (params.text) {
        await page.keyboard.type(interpolate(params.text, ctx.vars), { delay: params.delay || 10 });
    } else if (params.key) {
        await page.keyboard.press(params.key);
    }
}

async function stepLoop(page, params, ctx, executeStepFn) {
    const count = params.count || 1;
    const substeps = params.steps || [];
    for (let i = 0; i < count; i++) {
        ctx.vars.index = i + 1;
        for (let j = 0; j < substeps.length; j++) {
            const stepNum = ctx._parentStep + '.' + (i + 1) + '.' + (j + 1);
            await executeStepFn(page, substeps[j], ctx, stepNum, substeps.length);
        }
    }
}

async function stepConditional(page, params, ctx, executeStepFn) {
    const selector = interpolate(params.condition_selector, ctx.vars);
    let found = false;
    try {
        found = await page.locator(selector).first().isVisible({ timeout: 3000 });
    } catch {}
    const substeps = found ? (params.steps_if_found || []) : (params.steps_if_not_found || []);
    for (let j = 0; j < substeps.length; j++) {
        const stepNum = ctx._parentStep + '.' + (j + 1);
        await executeStepFn(page, substeps[j], ctx, stepNum, substeps.length);
    }
}

// ── Dispatcher ──────────────────────────────────────────────

const EXECUTORS = {
    login: stepLogin, navigate: stepNavigate, click: stepClick,
    fill: stepFill, select: stepSelect, wait: stepWait,
    screenshot: stepScreenshot, extract_text: stepExtractText,
    download: stepDownload, keyboard: stepKeyboard,
    loop: stepLoop, conditional: stepConditional,
};

async function executeStep(page, step, ctx, stepLabel, totalSiblings) {
    const label = step.label || step.type;
    emit('step_start', { step_id: step.id, label, step: stepLabel });

    try {
        const fn = EXECUTORS[step.type];
        if (!fn) throw new Error('Unknown step type: ' + step.type);

        ctx._parentStep = stepLabel;
        const params = interpolateParams(step.params || {}, ctx.vars);

        const result = (step.type === 'loop' || step.type === 'conditional')
            ? await fn(page, params, ctx, executeStep)
            : await fn(page, params, ctx);

        emit('step_done', { step_id: step.id, label, step: stepLabel, result: result || null });
    } catch (err) {
        try {
            const errPath = path.join(GRAIDER_DATA_DIR, 'automation_error.png');
            await page.screenshot({ path: errPath });
        } catch {}
        emit('step_error', { step_id: step.id, label, message: err.message });
        throw err;
    }
}

// ── Main ────────────────────────────────────────────────────

async function main() {
    const workflowPath = process.argv[2];
    if (!workflowPath) {
        console.error('Usage: node runner.js <workflow.json> [--var key=value ...]');
        process.exit(1);
    }

    const workflow = JSON.parse(fs.readFileSync(workflowPath, 'utf-8'));

    const vars = {};
    for (let i = 3; i < process.argv.length; i++) {
        if (process.argv[i] === '--var' && process.argv[i + 1]) {
            const [k, ...vParts] = process.argv[i + 1].split('=');
            vars[k] = vParts.join('=');
            i++;
        }
    }

    const ctx = { vars, workflow, _parentStep: '0' };
    const browserCfg = workflow.browser || {};

    let browser, page;
    if (browserCfg.persistent_context && browserCfg.context_dir) {
        const contextDir = path.join(GRAIDER_DATA_DIR, browserCfg.context_dir);
        fs.mkdirSync(contextDir, { recursive: true });
        browser = await chromium.launchPersistentContext(contextDir, {
            headless: browserCfg.headless === true,
            args: ['--start-maximized'],
            viewport: { width: 1440, height: 900 },
        });
        page = browser.pages()[0] || await browser.newPage();
    } else {
        browser = await chromium.launch({ headless: browserCfg.headless === true });
        const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
        page = await context.newPage();
    }

    emit('start', { workflow_name: workflow.name, total_steps: workflow.steps.length });

    try {
        for (let i = 0; i < workflow.steps.length; i++) {
            await executeStep(page, workflow.steps[i], ctx, String(i + 1), workflow.steps.length);
        }
        emit('done', { workflow_name: workflow.name, message: 'Workflow completed successfully' });
    } catch (err) {
        emit('error', { message: err.message });
    } finally {
        await page.waitForTimeout(2000);
        await browser.close();
    }
}

main();
