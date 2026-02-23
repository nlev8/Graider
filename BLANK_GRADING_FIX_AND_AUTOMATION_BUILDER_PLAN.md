# Playwright Automation Builder + Blank Assignment Grading Fix

---

## Part A: Critical Bug Fix — Blank Assignments Scoring 60 Instead of 0

### Context

Savannah Parker submitted a Cornell Notes assignment with zero student responses (just the blank template with directions) and received a 60. This is caused by 5 compounding bugs that prevent blank detection.

### Root Causes

1. **Template instruction text passes `after_colons` filter** (line 5120) — Direction lines like `"Define the following terms using the reading on pages 12-14."` are 10+ chars, don't start with `_`, and pass the regex. Sets `has_written_responses = True` on blank submissions.
2. **Summary section template text treated as student answer** (lines 1333-1444) — When `assignment_template` is not provided, `_strip_template_lines()` is skipped. Template instruction text like "Summarize the key events..." gets extracted as a response, making `answered_questions >= 1`.
3. **Effort points 20% floor** (line 4641) — `int(effort_points * 0.2) = 3` minimum even with 20+ blanks.
4. **Completeness cap table too short** (line 4652) — Caps max out at key 6 (39 for standard). More blanks don't lower the cap further.
5. **Single-pass prompt anchors AI to 60** (lines 5704-5708) — "3 sections skipped = maximum D (60-69)" causes AI to output exactly 60.
6. **API error fallback awards 70%** (line 4162) — If the API call errors on a blank question, student gets `int(points * 0.7)` for free.

---

### Fix 1: Harden `after_colons` blank detection

**File:** `assignment_grader.py`, lines 5120-5121

**Replace:**
```python
        after_colons = re.findall(r':\s*([^_\n:]{10,})', content)
        after_colons = [a.strip() for a in after_colons if a.strip() and not a.strip().startswith('_')]
```

**With:**
```python
        after_colons = re.findall(r':\s*([^_\n:]{10,})', content)
        # Filter out template instruction text that isn't student writing
        _instruction_patterns = re.compile(
            r'^(define|summarize|explain|describe|write|use|answer|identify|list|compare|analyze|discuss|'
            r'read|complete|fill|circle|match|select|choose|highlight|underline|review|include)\b',
            re.IGNORECASE
        )
        after_colons = [
            a.strip() for a in after_colons
            if a.strip()
            and not a.strip().startswith('_')
            and not _instruction_patterns.match(a.strip())
            and not a.strip().endswith('?')
            and 'complete sentences' not in a.lower()
            and 'using evidence' not in a.lower()
            and 'in your own words' not in a.lower()
            and 'from the reading' not in a.lower()
            and 'pp ' not in a.strip()[:5]  # page references like "pp 348-349"
        ]
```

---

### Fix 2: Zero effort points for 3+ blanks

**File:** `assignment_grader.py`, lines 4640-4641

**Replace:**
```python
    else:
        effort_earned = int(effort_points * 0.2)
```

**With:**
```python
    else:
        effort_earned = 0  # 3+ blanks = no effort credit
```

---

### Fix 3: Force zero when overwhelmingly blank

**File:** `assignment_grader.py`, after line 4482 (after the `answered == 0` guard block)

**Insert after the existing `answered == 0` block (after line 4482):**
```python
        # Force zero if 80%+ of questions are blank — prevents template text inflation
        total_questions = extraction_result.get("total_questions", 0)
        blank_questions_count = len(extraction_result.get("blank_questions", [])) + len(extraction_result.get("missing_sections", []))
        if total_questions > 0 and blank_questions_count / total_questions >= 0.8:
            print(f"  ⚠️  NEARLY BLANK: {blank_questions_count}/{total_questions} questions blank (≥80%)")
            return {
                "score": 0, "letter_grade": "INCOMPLETE",
                "breakdown": {"content_accuracy": 0, "completeness": 0, "writing_quality": 0, "effort_engagement": 0},
                "feedback": f"Your assignment is nearly blank — {blank_questions_count} out of {total_questions} questions have no response. Please complete all sections and resubmit.",
                "student_responses": [], "unanswered_questions": extraction_result.get("blank_questions", []) + extraction_result.get("missing_sections", []),
                "ai_detection": {"flag": "none", "confidence": 0, "reason": "Nearly blank submission."},
                "plagiarism_detection": {"flag": "none", "reason": "Nearly blank submission."},
                "skills_demonstrated": {"strengths": [], "developing": []},
                "excellent_answers": [], "needs_improvement": []
            }
```

---

### Fix 4: Template text detection in grade_per_question prompt

**File:** `assignment_grader.py`, line 4075 (inside the RULES section of the prompt)

**Replace:**
```python
- If blank/empty, score is 0
```

**With:**
```python
- If blank/empty, score is 0
- If the student answer is template/instruction text (e.g., starts with "Summarize", "Define", "Explain", "Write in complete sentences", "Use evidence from the reading"), this is NOT a student response — it is leftover assignment directions. Score it 0.
```

---

### Fix 5: Extend completeness caps and add zero floor

**File:** `assignment_grader.py`, lines 4647-4654

**Replace:**
```python
    if grading_style == 'strict':
        caps = {0: 100, 1: 85, 2: 75, 3: 65, 4: 55, 5: 45, 6: 35}
    elif grading_style == 'lenient':
        caps = {0: 100, 1: 95, 2: 89, 3: 79, 4: 69, 5: 59, 6: 49}
    else:
        caps = {0: 100, 1: 89, 2: 79, 3: 69, 4: 59, 5: 49, 6: 39}
    capped_count = min(blank_count, max(caps.keys()))
    cap = caps.get(capped_count, caps[max(caps.keys())])
```

**With:**
```python
    if grading_style == 'strict':
        caps = {0: 100, 1: 85, 2: 75, 3: 65, 4: 55, 5: 45, 6: 35, 7: 25, 8: 15}
    elif grading_style == 'lenient':
        caps = {0: 100, 1: 95, 2: 89, 3: 79, 4: 69, 5: 59, 6: 49, 7: 39, 8: 29}
    else:
        caps = {0: 100, 1: 89, 2: 79, 3: 69, 4: 59, 5: 49, 6: 39, 7: 29, 8: 19}
    if blank_count >= len(caps):
        cap = 0  # More blanks than cap table entries → zero
    else:
        cap = caps.get(blank_count, 0)
```

---

### Fix 6: Lower API error fallback from 70% to 0

**File:** `assignment_grader.py`, lines 4162-4168

**Replace:**
```python
    return {
        "grade": {"score": int(points * 0.7), "possible": points,
                  "reasoning": f"Grading error - default score applied ({ai_provider})",
                  "is_correct": True, "quality": "adequate"},
        "excellent": False,
        "improvement_note": ""
    }
```

**With:**
```python
    return {
        "grade": {"score": 0, "possible": points,
                  "reasoning": f"Grading error - could not evaluate response ({ai_provider})",
                  "is_correct": False, "quality": "insufficient"},
        "excellent": False,
        "improvement_note": "This response could not be evaluated due to a grading error."
    }
```

---

### Fix 7: Single-pass prompt — add explicit zero for blank submissions

**File:** `assignment_grader.py`, line 5708 (after the "4+ sections skipped/missing" line in STANDARD scale)

**After the line:**
```python
  * 4+ sections skipped/missing = F (below 60) - shows no effort on written work
```

**Insert:**
```python
  * ALL or nearly all sections blank = 0 (INCOMPLETE) - student did not attempt the assignment
```

Do the same for the strict scale (after line 5702) and lenient scale (after line 5695).

---

## Part B: Playwright Automation Builder

### Context

Graider has 4 one-off Playwright scripts for school portal tasks. Instead of building more one-off scripts, we'll create a generic automation builder that lets teachers create, save, and run any Playwright workflow from within the app — NGL Sync screenshots, Focus grade sync, attendance exports, etc.

### New Files to Create

---

#### 1. `backend/automation/runner.js` — Generic Playwright Workflow Runner

```javascript
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
        else if (Array.isArray(v)) result[k] = v; // substeps handled separately
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

    // Click SAML login button
    try { await page.click('button.btn-saml', { timeout: 5000 }); } catch {}
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});

    const url = page.url();
    if (url.includes('adfs') || url.includes('login')) {
        emit('status', { message: 'Filling login credentials...' });
        await page.fill('#userNameInput', creds.email);
        await page.fill('#passwordInput', creds.password);
        await page.click('#submitButton');
    }

    // Wait for 2FA if needed (up to 2 minutes)
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
    const filename = interpolate(params.filename || `screenshot_${Date.now()}.png`, ctx.vars);
    const filepath = path.join(outputDir, filename);
    const fullPage = params.full_page !== false;
    await page.screenshot({ path: filepath, fullPage });
    emit('status', { message: `Screenshot saved: ${filename}` });
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
    emit('status', { message: `Downloaded: ${filename}` });
    return { file: filepath };
}

async function stepKeyboard(page, params, ctx) {
    const key = params.key;
    if (params.text) {
        await page.keyboard.type(interpolate(params.text, ctx.vars), { delay: params.delay || 10 });
    } else {
        await page.keyboard.press(key);
    }
}

async function stepLoop(page, params, ctx, executeStepFn) {
    const count = params.count || 1;
    const substeps = params.steps || [];
    for (let i = 0; i < count; i++) {
        ctx.vars.index = i + 1;
        for (let j = 0; j < substeps.length; j++) {
            const stepNum = `${ctx._parentStep}.${i + 1}.${j + 1}`;
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
        const stepNum = `${ctx._parentStep}.${j + 1}`;
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
        if (!fn) throw new Error(`Unknown step type: ${step.type}`);

        ctx._parentStep = stepLabel;
        const params = interpolateParams(step.params || {}, ctx.vars);

        // Pass executeStep for recursive types (loop, conditional)
        const result = (step.type === 'loop' || step.type === 'conditional')
            ? await fn(page, params, ctx, executeStep)
            : await fn(page, params, ctx);

        emit('step_done', { step_id: step.id, label, step: stepLabel, result: result || null });
    } catch (err) {
        // Screenshot on error
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

    // Parse --var key=value overrides
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
        // Give user a moment to see the result before closing
        await page.waitForTimeout(2000);
        await browser.close();
    }
}

main();
```

---

#### 2. `backend/automation/picker.js` — Element Picker Script

```javascript
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
    banner.innerHTML = '<strong>Graider Element Picker</strong> — Click any element to capture its selector. Press Esc to stop.';
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
            var cls = el.className.trim().split(/\\s+/).slice(0, 2).join('.');
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
```

---

#### 3. `backend/routes/automation_routes.py` — Flask Blueprint

```python
"""
Automation Routes — Playwright Workflow Builder backend.
CRUD for workflow JSON files + subprocess launch + element picker IPC.
"""
import os
import json
import re
import subprocess
import threading
from datetime import datetime

from flask import Blueprint, request, jsonify

automation_bp = Blueprint('automation', __name__)

AUTOMATIONS_DIR = os.path.expanduser("~/.graider_data/automations")
GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNNER_SCRIPT = os.path.join(PROJECT_ROOT, "backend", "automation", "runner.js")
PICKER_SCRIPT = os.path.join(PROJECT_ROOT, "backend", "automation", "picker.js")
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "backend", "automation", "templates")

os.makedirs(AUTOMATIONS_DIR, exist_ok=True)

# ── Run state (same pattern as _focus_comments_state in grading_routes.py:880) ──
_run_state = {
    "process": None,
    "status": "idle",
    "workflow_name": "",
    "current_step": 0,
    "total_steps": 0,
    "step_label": "",
    "message": "",
    "log": [],
}

_picker_state = {
    "process": None,
    "status": "idle",
    "events": [],
}


def _read_runner_output(proc):
    """Background thread: read subprocess NDJSON stdout, update _run_state."""
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            etype = event.get("type", "")
            if etype == "start":
                _run_state["total_steps"] = event.get("total_steps", 0)
            elif etype == "step_start":
                _run_state["current_step"] = int(event.get("step", "0").split(".")[0])
                _run_state["step_label"] = event.get("label", "")
                _run_state["message"] = f"Step {event.get('step', '?')}: {event.get('label', '')}"
            elif etype == "step_done":
                _run_state["message"] = f"Done: {event.get('label', '')}"
            elif etype == "step_error":
                _run_state["message"] = f"Error on '{event.get('label', '')}': {event.get('message', '')}"
            elif etype == "status":
                _run_state["message"] = event.get("message", "")
            elif etype == "done":
                _run_state["status"] = "done"
                _run_state["message"] = event.get("message", "Complete")
            elif etype == "error":
                _run_state["status"] = "error"
                _run_state["message"] = event.get("message", "Unknown error")
            _run_state["log"].append(event)
            if len(_run_state["log"]) > 200:
                _run_state["log"] = _run_state["log"][-100:]
        except json.JSONDecodeError:
            pass

    if _run_state["status"] == "running":
        _run_state["status"] = "done"


def _read_picker_output(proc):
    """Read picker subprocess stdout, accumulate selector events."""
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "selector_picked":
                _picker_state["events"].append(event)
            elif event.get("type") == "done":
                _picker_state["status"] = "done"
        except json.JSONDecodeError:
            pass
    if _picker_state["status"] == "picking":
        _picker_state["status"] = "done"


# ── CRUD ──────────────────────────────────────────────────────

@automation_bp.route('/api/automations', methods=['GET'])
def list_automations():
    """List all saved workflow files."""
    workflows = []
    for filename in sorted(os.listdir(AUTOMATIONS_DIR)):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(AUTOMATIONS_DIR, filename), 'r') as f:
                wf = json.load(f)
            workflows.append({
                "id": wf.get("id", filename.replace('.json', '')),
                "name": wf.get("name", filename),
                "description": wf.get("description", ""),
                "step_count": len(wf.get("steps", [])),
                "updated_at": wf.get("updated_at", ""),
            })
        except Exception:
            pass
    return jsonify({"workflows": workflows})


@automation_bp.route('/api/automations/<workflow_id>', methods=['GET'])
def get_automation(workflow_id):
    """Load a specific workflow JSON."""
    filepath = os.path.join(AUTOMATIONS_DIR, f"{workflow_id}.json")
    if not os.path.exists(filepath):
        return jsonify({"error": "Workflow not found"}), 404
    with open(filepath, 'r') as f:
        return jsonify(json.load(f))


@automation_bp.route('/api/automations', methods=['POST'])
def save_automation():
    """Save or create a workflow."""
    data = request.json
    if not data or not data.get("name"):
        return jsonify({"error": "Workflow name required"}), 400

    wf_id = data.get("id") or re.sub(r'[^a-z0-9]+', '-', data["name"].lower()).strip('-')
    data["id"] = wf_id
    data.setdefault("version", 1)
    data.setdefault("created_at", datetime.now().isoformat())
    data["updated_at"] = datetime.now().isoformat()

    # Assign step IDs if missing
    for i, step in enumerate(data.get("steps", [])):
        step.setdefault("id", f"step-{i+1}")

    filepath = os.path.join(AUTOMATIONS_DIR, f"{wf_id}.json")
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    return jsonify({"status": "saved", "id": wf_id})


@automation_bp.route('/api/automations/<workflow_id>', methods=['DELETE'])
def delete_automation(workflow_id):
    """Delete a workflow file."""
    filepath = os.path.join(AUTOMATIONS_DIR, f"{workflow_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
    return jsonify({"status": "deleted"})


@automation_bp.route('/api/automations/templates', methods=['GET'])
def list_templates():
    """Return built-in template workflows."""
    templates = []
    if os.path.isdir(TEMPLATES_DIR):
        for filename in sorted(os.listdir(TEMPLATES_DIR)):
            if not filename.endswith('.json'):
                continue
            try:
                with open(os.path.join(TEMPLATES_DIR, filename), 'r') as f:
                    wf = json.load(f)
                templates.append({
                    "id": wf.get("id", filename.replace('.json', '')),
                    "name": wf.get("name", filename),
                    "description": wf.get("description", ""),
                    "step_count": len(wf.get("steps", [])),
                    "is_template": True,
                })
            except Exception:
                pass
    return jsonify({"templates": templates})


# ── Run ──────────────────────────────────────────────────────

@automation_bp.route('/api/automations/<workflow_id>/run', methods=['POST'])
def run_automation(workflow_id):
    """Launch workflow as subprocess."""
    if _run_state.get("status") == "running":
        return jsonify({"error": "An automation is already running"}), 409

    workflow_path = os.path.join(AUTOMATIONS_DIR, f"{workflow_id}.json")
    if not os.path.exists(workflow_path):
        return jsonify({"error": "Workflow not found"}), 404

    if not os.path.exists(RUNNER_SCRIPT):
        return jsonify({"error": "runner.js not found"}), 500

    data = request.json or {}
    var_args = []
    for k, v in data.get("vars", {}).items():
        var_args.extend(["--var", f"{k}={v}"])

    _run_state.update({
        "process": None, "status": "running",
        "workflow_name": workflow_id,
        "current_step": 0, "total_steps": 0,
        "step_label": "", "message": "Starting automation...",
        "log": [],
    })

    proc = subprocess.Popen(
        ["node", RUNNER_SCRIPT, workflow_path] + var_args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    _run_state["process"] = proc
    threading.Thread(target=_read_runner_output, args=(proc,), daemon=True).start()
    return jsonify({"status": "started"})


@automation_bp.route('/api/automations/run/status', methods=['GET'])
def run_status():
    """Poll current automation run state."""
    return jsonify({
        "status": _run_state.get("status", "idle"),
        "workflow_name": _run_state.get("workflow_name", ""),
        "current_step": _run_state.get("current_step", 0),
        "total_steps": _run_state.get("total_steps", 0),
        "step_label": _run_state.get("step_label", ""),
        "message": _run_state.get("message", ""),
        "log": _run_state.get("log", [])[-20:],
    })


@automation_bp.route('/api/automations/run/stop', methods=['POST'])
def stop_run():
    """Kill running automation subprocess."""
    proc = _run_state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
    _run_state["status"] = "idle"
    _run_state["message"] = "Stopped by user"
    return jsonify({"status": "stopped"})


# ── Element Picker ───────────────────────────────────────────

@automation_bp.route('/api/automations/picker/start', methods=['POST'])
def start_picker():
    """Launch element picker browser."""
    if _picker_state.get("status") == "picking":
        return jsonify({"error": "Picker already running"}), 409

    if not os.path.exists(PICKER_SCRIPT):
        return jsonify({"error": "picker.js not found"}), 500

    data = request.json or {}
    start_url = data.get("url", "https://vportal.volusia.k12.fl.us/")

    _picker_state.update({"status": "picking", "events": [], "process": None})

    proc = subprocess.Popen(
        ["node", PICKER_SCRIPT, "--url", start_url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    _picker_state["process"] = proc
    threading.Thread(target=_read_picker_output, args=(proc,), daemon=True).start()
    return jsonify({"status": "picker_started"})


@automation_bp.route('/api/automations/picker/events', methods=['GET'])
def picker_events():
    """Drain and return accumulated picker events."""
    events = list(_picker_state.get("events", []))
    _picker_state["events"] = []
    return jsonify({"status": _picker_state.get("status", "idle"), "events": events})


@automation_bp.route('/api/automations/picker/stop', methods=['POST'])
def stop_picker():
    """Close picker browser."""
    proc = _picker_state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
    _picker_state["status"] = "idle"
    return jsonify({"status": "stopped"})
```

---

#### 4. `backend/services/assistant_tools_automation.py` — AI Assistant Tools

```python
"""
Automation Tool Definitions for the AI Assistant.
Allows the assistant to create, list, and run Playwright automations.
"""
import os
import json
import re
from datetime import datetime

AUTOMATIONS_DIR = os.path.expanduser("~/.graider_data/automations")

AUTOMATION_TOOL_DEFINITIONS = [
    {
        "name": "list_automations",
        "description": "List saved Playwright automation workflows. Use when teacher asks 'what automations do I have?' or 'show my browser automations'.",
        "input_schema": {
            "type": "object",
            "properties": {},
        }
    },
    {
        "name": "create_automation",
        "description": "Create a new Playwright automation workflow. The teacher describes what they want and you generate the steps. Use text=VisibleText selectors when the exact CSS selector is unknown. Always start with a login step for authenticated school portals. Step types: login, navigate, click, fill, select, wait, screenshot, extract_text, download, keyboard, loop, conditional.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short display name for the automation"},
                "description": {"type": "string", "description": "What this automation does"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["login", "navigate", "click", "fill", "select", "wait", "screenshot", "extract_text", "download", "keyboard", "loop", "conditional"]},
                            "label": {"type": "string", "description": "Human-readable step description"},
                            "params": {"type": "object", "description": "Step parameters (url, selector, value, count, steps, etc.)"}
                        },
                        "required": ["type", "label"]
                    },
                    "description": "Array of workflow steps"
                },
                "browser_persistent": {"type": "boolean", "description": "Reuse browser session between runs. Default false."},
                "headless": {"type": "boolean", "description": "Run without visible browser. Default false (visible for 2FA)."}
            },
            "required": ["name", "steps"]
        }
    },
    {
        "name": "run_automation",
        "description": "Run a saved automation workflow by name. Returns instructions for monitoring progress in the Automations tab.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name or partial name of the automation to run"}
            },
            "required": ["name"]
        }
    },
]


def list_automations_tool():
    os.makedirs(AUTOMATIONS_DIR, exist_ok=True)
    workflows = []
    for filename in sorted(os.listdir(AUTOMATIONS_DIR)):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(AUTOMATIONS_DIR, filename), 'r') as f:
                wf = json.load(f)
            workflows.append({
                "id": wf.get("id", filename.replace('.json', '')),
                "name": wf.get("name", filename),
                "description": wf.get("description", ""),
                "step_count": len(wf.get("steps", [])),
            })
        except Exception:
            pass
    if not workflows:
        return {"message": "No automations saved yet. I can create one for you — just describe what you want to automate."}
    return {"automations": workflows, "count": len(workflows)}


def create_automation_tool(name, steps, description="", browser_persistent=False, headless=False):
    os.makedirs(AUTOMATIONS_DIR, exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

    for i, step in enumerate(steps):
        step.setdefault("id", f"step-{i+1}")
        step.setdefault("params", {})

    workflow = {
        "id": slug,
        "name": name,
        "description": description,
        "version": 1,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "browser": {
            "headless": headless,
            "persistent_context": browser_persistent,
            "context_dir": f"{slug}_browser" if browser_persistent else None,
        },
        "credentials": "portal",
        "steps": steps,
    }

    filepath = os.path.join(AUTOMATIONS_DIR, f"{slug}.json")
    with open(filepath, 'w') as f:
        json.dump(workflow, f, indent=2)

    return {
        "success": True,
        "id": slug,
        "name": name,
        "step_count": len(steps),
        "message": f"Automation '{name}' created with {len(steps)} steps. Go to the Automations tab to run it, edit steps, or use the element picker to refine selectors.",
    }


def run_automation_tool(name):
    os.makedirs(AUTOMATIONS_DIR, exist_ok=True)
    for filename in sorted(os.listdir(AUTOMATIONS_DIR)):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(AUTOMATIONS_DIR, filename), 'r') as f:
                wf = json.load(f)
            if name.lower() in wf.get("name", "").lower():
                return {
                    "found": True,
                    "workflow_id": wf.get("id"),
                    "workflow_name": wf.get("name"),
                    "step_count": len(wf.get("steps", [])),
                    "message": f"Found automation '{wf['name']}'. Switch to the Automations tab and click the Run button to start it.",
                }
        except Exception:
            pass
    return {"found": False, "error": f"No automation matching '{name}' found. Use create_automation to make one."}


AUTOMATION_TOOL_HANDLERS = {
    "list_automations": list_automations_tool,
    "create_automation": create_automation_tool,
    "run_automation": run_automation_tool,
}
```

---

### Existing Files to Modify

---

#### 5. `backend/routes/__init__.py` — Register the new blueprint

**Add import at line 23 (after `from .auth_routes import auth_bp`):**
```python
from .automation_routes import automation_bp
```

**Add registration at line 46 (after `app.register_blueprint(auth_bp)`):**
```python
    app.register_blueprint(automation_bp)
```

**Add to `__all__` list (after `'auth_bp'` at line 62):**
```python
    'automation_bp',
```

---

#### 6. `backend/services/assistant_tools.py` — Register automation submodule

**At line 3624 (after the STEM line in the `submodules` list inside `_merge_submodules()`):**

**Add:**
```python
        ("backend.services.assistant_tools_automation", "AUTOMATION_TOOL_DEFINITIONS", "AUTOMATION_TOOL_HANDLERS"),
```

---

#### 7. `frontend/src/App.jsx` — Add Automations tab

**Line 46 (after the resources tab, before assistant):**

**Replace:**
```javascript
  { id: "resources", label: "Resources", icon: "FolderOpen" },
  { id: "assistant", label: "Assistant", icon: "Sparkles" },
```

**With:**
```javascript
  { id: "resources", label: "Resources", icon: "FolderOpen" },
  { id: "automations", label: "Automations", icon: "Cpu" },
  { id: "assistant", label: "Assistant", icon: "Sparkles" },
```

**Add import near the top (after other component imports):**
```javascript
import AutomationBuilder from "./components/AutomationBuilder";
```

**Add tab panel (in the main content area, after the resources tab panel and before the assistant tab panel):**
```jsx
{activeTab === "automations" && (
  <div className="fade-in">
    <AutomationBuilder addToast={addToast} />
  </div>
)}
```

---

#### 8. `frontend/src/services/api.js` — Add automation API functions

**Add at the end of the file:**
```javascript
// ============ Automations ============

export async function listAutomations() {
  return fetchApi('/api/automations')
}

export async function getAutomation(id) {
  return fetchApi('/api/automations/' + id)
}

export async function saveAutomation(workflow) {
  return fetchApi('/api/automations', {
    method: 'POST',
    body: JSON.stringify(workflow),
  })
}

export async function deleteAutomation(id) {
  return fetchApi('/api/automations/' + id, { method: 'DELETE' })
}

export async function listAutomationTemplates() {
  return fetchApi('/api/automations/templates')
}

export async function runAutomation(id, vars) {
  return fetchApi('/api/automations/' + id + '/run', {
    method: 'POST',
    body: JSON.stringify({ vars: vars || {} }),
  })
}

export async function getAutomationRunStatus() {
  return fetchApi('/api/automations/run/status')
}

export async function stopAutomationRun() {
  return fetchApi('/api/automations/run/stop', { method: 'POST' })
}

export async function startElementPicker(url) {
  return fetchApi('/api/automations/picker/start', {
    method: 'POST',
    body: JSON.stringify({ url: url || 'https://vportal.volusia.k12.fl.us/' }),
  })
}

export async function getPickerEvents() {
  return fetchApi('/api/automations/picker/events')
}

export async function stopElementPicker() {
  return fetchApi('/api/automations/picker/stop', { method: 'POST' })
}
```

---

#### 9. `frontend/src/components/AutomationBuilder.jsx` — Full Builder Component

This is the main UI component (see separate file creation). Contains:
- **List View**: Card grid of saved workflows + templates with Run/Edit/Delete
- **Builder View**: Step list (left) + step config form (right) with element picker integration
- **Run View**: Progress bar + scrolling log + Stop button

The component will be ~400-500 lines and follow the same inline styles + `var(--*)` CSS variable pattern used throughout the app.

---

### Pre-Built Templates

#### `backend/automation/templates/ngl_screenshot.json`
```json
{
  "id": "ngl-screenshot",
  "name": "NGL Sync — Screenshot Textbook Pages",
  "description": "Opens NGL Sync and captures screenshots of consecutive textbook pages.",
  "browser": { "headless": false, "persistent_context": false },
  "credentials": "portal",
  "steps": [
    { "id": "s1", "type": "login", "label": "Log in to VPortal", "params": {} },
    { "id": "s2", "type": "navigate", "label": "Open NGL Sync", "params": { "url": "{ngl_url}" } },
    { "id": "s3", "type": "wait", "label": "Wait for page to load", "params": { "ms": 3000 } },
    { "id": "s4", "type": "loop", "label": "Screenshot pages", "params": {
      "count": 10,
      "steps": [
        { "id": "s4a", "type": "screenshot", "label": "Capture page", "params": { "filename": "page_{index}.png", "output_dir": "~/Downloads/Graider/Exports/ngl/" } },
        { "id": "s4b", "type": "click", "label": "Next page", "params": { "selector": "text=Next" } },
        { "id": "s4c", "type": "wait", "label": "Wait for render", "params": { "ms": 1500 } }
      ]
    }}
  ]
}
```

#### `backend/automation/templates/focus_gradebook_screenshot.json`
```json
{
  "id": "focus-gradebook-screenshot",
  "name": "Focus — Screenshot Gradebook",
  "description": "Opens Focus gradebook and captures a screenshot of each period.",
  "browser": { "headless": false, "persistent_context": false },
  "credentials": "portal",
  "steps": [
    { "id": "s1", "type": "login", "label": "Log in to VPortal", "params": {} },
    { "id": "s2", "type": "navigate", "label": "Open Focus Gradebook", "params": { "url": "https://volusia.focusschoolsoftware.com/focus/Modules.php?modname=Grades/Gradebook.php" } },
    { "id": "s3", "type": "wait", "label": "Wait for gradebook", "params": { "selector": "span.student-name-link" } },
    { "id": "s4", "type": "screenshot", "label": "Capture gradebook", "params": { "filename": "gradebook_{index}.png", "full_page": true } }
  ]
}
```

---

### Implementation Order

1. **Part A: Blank grading fix** — all 7 fixes in `assignment_grader.py` (highest priority, ship first)
2. `backend/automation/runner.js` — the core engine
3. `backend/routes/automation_routes.py` — Flask CRUD + subprocess routes
4. `backend/routes/__init__.py` — register blueprint
5. `frontend/src/services/api.js` — add API functions
6. `frontend/src/components/AutomationBuilder.jsx` — full component
7. `frontend/src/App.jsx` — add tab + import
8. `backend/automation/picker.js` — element picker
9. `backend/services/assistant_tools_automation.py` — AI tools
10. `backend/services/assistant_tools.py` — register submodule
11. `backend/automation/templates/*.json` — pre-built templates
12. Frontend build + test

### Verification

**Grading fix:**
1. Submit a blank Cornell Notes template → should score 0 with "INCOMPLETE"
2. Submit a template with only 1 of 10 questions answered → should score very low (not 60)
3. Submit a normal completed assignment → scores should be unchanged

**Automation builder:**
1. `node backend/automation/runner.js test_workflow.json` → verify NDJSON output + screenshots saved
2. Create/save/load/delete workflows via API
3. Element picker: launch → click elements → verify selectors returned
4. End-to-end: build a workflow in UI → run it → verify progress + output
5. Assistant: "create an automation that screenshots 5 textbook pages" → verify workflow JSON saved
