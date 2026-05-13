# Handoff: React mount failure in CI's chromium

**Audit MAJOR #5 Phase 3 Stage 3a follow-up. Filed 2026-05-12.**

## Goal

Root-cause and fix the 29 spec failures in `e2e-nightly` so the workflow surfaces real regressions instead of passing trivially via `continue-on-error: true`.

## TL;DR

- Workflow infra is sound; merged via PRs #358 + #359 + #360 + #361.
- Run [25758117445](https://github.com/nlev8/Graider/actions/runs/25758117445) succeeded structurally: backend spawn, preflight, both Playwright projects discovered + ran tests, artifact uploaded.
- **Result**: 46/56 frontend/e2e pass; 10 fail. **0/19 tests/e2e pass**.
- **All 29 failures have identical shape**: `page.goto('/')` returns in ~320ms with status `load`, but React never mounts. Failure screenshots are blank dark blue (page background only, no `<div id="root">` content). The 46 passing frontend specs are API-only tests that don't navigate to UI — they prove chromium launches and HTTP works in CI.
- **Tracking issue**: https://github.com/nlev8/Graider/issues/362

## Local reproduction state

All 75 specs PASS locally against the same Vite-built frontend + backend:

```bash
# From repo root
cd /Users/alexc/Downloads/Graider

# Backend should be running on :3000:
curl -fsS http://localhost:3000/   # → HTTP 200

# Frontend stage-3a specs (56 tests):
cd frontend && PYTHON=python3 E2E_REUSE_BACKEND=1 npx playwright test \
  e2e/publish-flow.spec.js e2e/teacher-dashboard.spec.js \
  e2e/assistant-chat.spec.js e2e/automation-builder.spec.js \
  e2e/resource-management.spec.js e2e/teacher-settings-save.spec.js \
  e2e/clever-accommodations.spec.js --workers=1 --reporter=line
# Expected: 56 passed (~1.2m)

# tests/e2e specs (19 tests):
cd ../tests/e2e && PYTHON=python3 E2E_REUSE_BACKEND=1 \
  npx playwright test --workers=1 --reporter=line
# Expected: 19 passed (~1.0m)
```

So **specs are correct**. Issue is CI-environment-specific.

## Disproved hypotheses (do NOT retry)

1. **State-poisoning between frontend/e2e and tests/e2e runs** — disproved. Running them back-to-back locally (same order as CI) → all pass.
2. **HOME=/tmp/graider-e2e-home overriding chromium lookup** — disproved. In CI's Linux ubuntu runner, chromium installed into `$HOME/.cache/ms-playwright/` correctly because the install step ran with HOME already overridden. 46 frontend specs ran successfully in CI proving chromium launched. (My local repro with the same HOME override failed for a *different* reason — my macOS chromium path is `~/Library/Caches/...` not `~/.cache/...` — and that's why my "repro" briefly looked successful but was actually invalid.)
3. **Asset 404 in CI** — partially disproved. Served HTML references `/assets/index-*.js`. Couldn't directly verify the asset 200s in CI (backend was killed by Stop step), but local repro confirms backend serves it correctly when invoked the same way.
4. **Stale tests/e2e specs not in git** — fixed by PR #361 (the 6 specs were gitignored). After fix, CI sees and discovers them (19 tests found per run 25758117445).

## Most likely remaining causes (ranked)

1. **Linux chrome-headless-shell vs macOS chrome-headless-shell** — different chromium binaries on different platforms. The headless-shell variant on Linux x86_64 may have a different JS execution profile than Mac arm64. Plausible if the React bundle uses a feature with platform-specific behavior. **Test by running the bundle in real Linux chromium-headless instead of headless-shell.**
2. **GitHub ubuntu runner missing a system library** — even though `npx playwright install --with-deps chromium` ran successfully, there could be a missing transitive lib that breaks JS execution silently. Test by checking the actual chromium stderr in CI (currently not captured).
3. **Vite build in CI produces different bundle than local macOS build** — Vite cross-compilation has been known to produce subtly different chunks for the same source on different platforms. Test by computing the hash of `backend/static/assets/index-*.js` in CI and local + diffing.

## Concrete next step

The trace artifact captures action snapshots + screenshots + videos but **NOT** console events (those require explicit `page.on('console', ...)`). Without console capture, the JS error that prevents React from mounting is invisible.

### Option A — minimal probe (recommended)

Add a one-off debug spec that captures everything chromium says, then run only this spec via `workflow_dispatch`:

```javascript
// tests/e2e/specs/_debug-console-trap.spec.js  (or in frontend/e2e/)
import { test, expect } from '@playwright/test';

test('debug: capture all browser output on goto(/)', async ({ page }) => {
  const events = [];
  page.on('console', m => events.push(`CONSOLE ${m.type()}: ${m.text()}`));
  page.on('pageerror', e => events.push(`PAGEERROR: ${e.message}\n${e.stack}`));
  page.on('requestfailed', r => events.push(`REQFAIL: ${r.url()} → ${r.failure()?.errorText}`));
  page.on('response', r => {
    if (r.status() >= 400) events.push(`HTTP ${r.status()}: ${r.url()}`);
  });

  await page.goto('/');
  await page.waitForTimeout(8000);  // Give React 8s to mount, capturing events

  console.log('=== BROWSER EVENT LOG ===');
  for (const e of events) console.log(e);
  console.log('=== END ===');

  // Always pass — this is a probe, not a gate
  expect(true).toBe(true);
});
```

Add the spec to the Stage 3a allowlist temporarily, push, `workflow_dispatch`, read the workflow logs. The console output will identify the root cause.

### Option B — config-level instrumentation (heavier, persistent)

Add `globalSetup` to one playwright config that registers the listeners on every test. Persistent across runs but pollutes test output.

### Option C — fix-forward without root-cause

Trim the Stage 3a allowlist to only the 46 specs that pass in CI (the API-only ones). Ship immediate value. Defer the 29 UI-driven specs to Stage 3b or until root cause is fixed. Removes false-confidence problem (continue-on-error currently hides real failures).

## Action items (suggested order)

1. [ ] Apply Option A: write the debug probe spec
2. [ ] PR + merge + `workflow_dispatch`
3. [ ] Read CI logs for the probe's `=== BROWSER EVENT LOG ===` section
4. [ ] Identify and fix the underlying issue
5. [ ] Verify all 75 specs pass in CI
6. [ ] Remove `continue-on-error: true` from both Playwright run steps in `e2e-nightly.yml`
7. [ ] Close issue #362

## Reference

- **Plan**: `docs/superpowers/plans/2026-05-11-audit-major5-e2e-promotion.md` (Phase 3 section + revision log)
- **Tracking issue**: https://github.com/nlev8/Graider/issues/362 (has investigation comments from 2026-05-12)
- **Last CI run**: https://github.com/nlev8/Graider/actions/runs/25758117445
- **Workflow file**: `.github/workflows/e2e-nightly.yml`
- **Allowlist**: 13 specs in Phase 3 plan's Stage 3a section; categorization in #357
- **Hotfix history**: #359 (runner.temp), #360 (path filters), #361 (gitignore)

## What was learned about the e2e workflow

Useful artifacts that survived the investigation:
- The workflow's preflight curl loop (handles backend slow-start)
- `Stop backend (detect mid-test crash)` step (catches false-greens)
- `E2E_REUSE_BACKEND=1` env-var opt-in (preserves smoke job semantics)
- HOME isolation env var (works in CI; my local repro of this was invalid)

Don't touch these — they're correct and Codex+Gemini-reviewed.
