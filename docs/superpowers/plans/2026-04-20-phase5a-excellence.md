# Phase 5a Excellence Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 7 PRs that close a measurable subset of the Phase 5 excellence-tier gap — security CI, dependency pinning, structured logging, and an LLM adapter seam — without touching Clever/ClassLink/OneRoster contracts.

**Architecture:** Seven sequential PRs, each on its own feature branch merged to main in order. Four categories: CI hygiene (A), dependency management (B1+B2), observability plumbing (C1+C2), architectural seam (D1+D2). Each PR is independently revertable; dependencies across PRs are documented per task.

**Tech Stack:** Python 3.12, Flask, Supabase, pytest, ruff (new), pip-tools (new), Bandit (new), trufflehog (new), existing `backend.retry.with_retry`, existing `backend.utils.logging_utils.JsonFormatter`, existing `sentry_sdk`.

**Spec:** `docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md` (branch `spec/phase5a-excellence`, commit `4a3fd70`). Three Codex review rounds reconciled; final verdict APPROVED.

**Dependency chain between PRs:**
- PR A → everything (trivial, lands first so its green signal protects the rest)
- PR B1 → PR B2 (B1 cleans, B2 freezes)
- PR B2 → PR C2 (C2 adds `ruff` dep; after B2, dep additions require lockfile regen)
- PR C1 → PR C2, PR D1 (C2 migration and D1 metrics both use C1's `emit()` helper)
- PR D1 → PR D2 (D2 extends D1's Protocol)

**Task-to-PR map:**

| Task | PR | Branch |
|---|---|---|
| Task 1 | A | `feat/phase5a-pr-a-security-scan` |
| Task 2 | B1 | `feat/phase5a-pr-b1-dep-audit` |
| Task 3 | B2 | `feat/phase5a-pr-b2-pip-tools` |
| Task 4 | C1 | `feat/phase5a-pr-c1-emit-helper` |
| Task 5 | C2 | `feat/phase5a-pr-c2-print-migration` |
| Task 6 | D1 | `feat/phase5a-pr-d1-llm-adapter` |
| Task 7 | D2 | `feat/phase5a-pr-d2-adapter-streaming` |

---

## File structure summary

**Files created across the phase:**
- `.github/workflows/security-scan.yml` (Task 1)
- `.bandit.yaml` (Task 1)
- `requirements.in`, `requirements-dev.in` (Task 3 — renames, not fresh creates)
- `docs/dependencies.md` (Task 3)
- `backend/observability/events.py` (Task 4)
- `tests/test_observability_events.py` (Task 4)
- `backend/services/llm_adapter/__init__.py` (Task 6)
- `backend/services/llm_adapter/types.py` (Task 6)
- `backend/services/llm_adapter/openai_adapter.py` (Task 6)
- `backend/services/llm_adapter/anthropic_adapter.py` (Task 6)
- `backend/services/llm_adapter/gemini_adapter.py` (Task 6)
- `tests/test_llm_adapter_types.py` (Task 6)
- `tests/test_llm_adapter_openai.py` (Task 6)
- `tests/test_llm_adapter_anthropic.py` (Task 6)
- `tests/test_llm_adapter_gemini.py` (Task 6)
- `backend/services/llm_adapter/streaming.py` (Task 7)
- `tests/test_llm_adapter_streaming.py` (Task 7)

**Files modified across the phase:**
- `README.md` (Task 1, coverage-floor fix)
- `requirements.txt` → split into `.in`+`.txt` (Tasks 2, 3)
- `requirements-dev.txt` → split into `.in`+`.txt` (Tasks 2, 3)
- `.github/workflows/ci.yml` (Task 3 for `--require-hashes` + drift-check job; Task 5 for `ruff-lint` job)
- `pyproject.toml` (Task 5 for ruff config)
- `backend/observability/db_mode.py` (Task 4 refactor; no behavior change)
- ~18 backend files for print migration (Task 5)
- ~15 backend files for LLM call-site migration (Task 6)
- `backend/routes/assistant_routes.py` (Task 7 streaming migration)

---

## Task 1: PR A — Bandit + trufflehog CI + README coverage fix

**Branch:** `feat/phase5a-pr-a-security-scan`
**Spec section:** PR A
**Estimated effort:** 1 day

**Files:**
- Create: `.github/workflows/security-scan.yml`
- Create: `.bandit.yaml`
- Modify: `README.md` (coverage-floor 40 → 32)

---

- [ ] **Step 1: Create branch off main**

```bash
cd /Users/alexc/Downloads/Graider
git checkout main
git pull
git checkout -b feat/phase5a-pr-a-security-scan
```

- [ ] **Step 2: Install Bandit locally and run against backend/ to surface current findings**

```bash
source venv/bin/activate
pip install bandit
bandit -r backend/ --exclude backend/scripts,backend/migrations -l -iii -f yaml -o .bandit-current.yaml
cat .bandit-current.yaml | head -50
```

Expected: YAML file with current findings. Note count. These become the baseline.

- [ ] **Step 3: Create `.bandit.yaml` baseline**

Create the file at repo root:

```yaml
# Bandit baseline for Phase 5a (PR A).
#
# REVIEW CADENCE: this allow-list should be reviewed at the start of every
# new phase plan and refreshed anytime a flagged pattern is either fixed
# (remove from allow-list) or newly introduced during a phase.
#
# REFRESH COMMAND:
#   bandit -r backend/ --exclude backend/scripts,backend/migrations -l -iii -f yaml -o .bandit.yaml --baseline
#
# The -l flag skips LOW severity; -iii flag requires HIGH confidence.
# Effective: medium+ severity AND high confidence only.

# Severity and confidence filters (must match security-scan.yml invocation)
skips: []

# Per-file allow-lists below. Each entry is a {path, issue} pair.
# Entries auto-generated from the initial scan. Regenerate with the refresh
# command above; review the diff before committing.

# (populate from .bandit-current.yaml output above — paste each finding's
#  skip entry here)
```

Populate the `skips:` list from the output of Step 2 (if any findings). If no findings, leave `skips: []` — no baseline needed, every future finding blocks merge.

- [ ] **Step 4: Create `.github/workflows/security-scan.yml`**

```yaml
name: Security Scan

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

concurrency:
  group: security-${{ github.ref }}
  cancel-in-progress: true

jobs:
  bandit:
    name: Bandit SAST
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install Bandit
        run: pip install bandit

      - name: Run Bandit against backend/ (exclude scripts + migrations)
        run: |
          bandit -r backend/ \
            --exclude backend/scripts,backend/migrations \
            -l -iii \
            --baseline .bandit.yaml

  trufflehog:
    name: Secret Scan (trufflehog, verified only, PR diff)
    runs-on: ubuntu-latest
    # Skip the push-to-main variant for this job: a verified secret in a
    # merged commit is historical; the PR-diff variant already blocked
    # merging it, and scanning main afterward just adds noise.
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # required for --since-commit diff mode

      - name: Scan PR diff for verified secrets
        uses: trufflesecurity/trufflehog@main
        with:
          base: ${{ github.event.pull_request.base.sha }}
          head: ${{ github.event.pull_request.head.sha }}
          extra_args: --only-verified
```

- [ ] **Step 5: Run a local smoke test of the Bandit config**

```bash
source venv/bin/activate
bandit -r backend/ --exclude backend/scripts,backend/migrations -l -iii --baseline .bandit.yaml
```

Expected: "No issues identified" (with baseline allow-list covering any pre-existing findings).

- [ ] **Step 6: Update `README.md` coverage-floor reference**

Find the line in README referencing the coverage floor (search for `40%` near "Backend Tests" or "coverage"):

```bash
grep -n "40" README.md | grep -i "cov\|test\|floor"
```

Replace `40%` with `32%`. Add a one-line note that CI enforces this via `--cov-fail-under=32`.

- [ ] **Step 7: Delete the temporary `.bandit-current.yaml` scratch file**

```bash
rm .bandit-current.yaml
```

- [ ] **Step 8: Commit**

```bash
git add .github/workflows/security-scan.yml .bandit.yaml README.md
git commit -m "$(cat <<'EOF'
feat: Phase 5a PR A — Bandit + trufflehog CI + README coverage fix

New security-scan workflow:
  - Bandit on backend/ (exclude scripts, migrations), severity medium+
    HIGH confidence only, baseline-gated via .bandit.yaml
  - trufflehog on PR diff (fetch-depth: 0, --only-verified) — blocks
    merge on confirmed secrets

README: coverage-floor reference updated 40% → 32% to match actual CI
enforcement (--cov-fail-under=32 in ci.yml:49).

Baseline governance: .bandit.yaml includes an explicit review-cadence
and refresh-command comment.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 9: Push + open PR**

```bash
git push -u origin feat/phase5a-pr-a-security-scan
gh pr create --base main --title "feat: Phase 5a PR A — Bandit + trufflehog CI + README coverage fix" --body "$(cat <<'EOF'
## Summary

- Adds `security-scan.yml` workflow: Bandit SAST + trufflehog verified-secrets on PR diff.
- Updates README to reflect the actual CI coverage floor (32%, not 40%).
- Commits a governance-annotated `.bandit.yaml` baseline.

## Spec

docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md § PR A.

## Test plan

- [x] Bandit runs locally against backend/ with no findings (all pre-existing findings in baseline)
- [ ] CI Security Scan workflow runs green on this PR
- [ ] Confirm workflow triggers on a test PR with an intentional (then reverted) verified-secret commit

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 10: Watch CI + merge**

```bash
gh pr checks --watch
```

When all green, operator merges. Proceed to Task 2.

---

## Task 2: PR B1 — Dependency ownership audit

**Branch:** `feat/phase5a-pr-b1-dep-audit`
**Spec section:** PR B1
**Estimated effort:** 1 day
**Prereq:** Task 1 merged.

**Files:**
- Modify: `requirements.txt` (remove non-runtime deps)
- Modify: `requirements-dev.txt` (add them here)
- Modify: `.github/workflows/ci.yml` (remove ad-hoc pytest-cov install)

**Moves (non-runtime deps that currently live in main requirements.txt):**
- `pytest-cov` → dev
- `py2app` → dev (Mac packaging, never hit at runtime)
- `playwright` → dev (E2E)
- `selenium` → dev (E2E)

**Keep in main** (production dependencies):
- Both Gemini SDKs (`google-generativeai`, `google.genai`) — used by live routes + slide_generator. Document with a one-line comment.

---

- [ ] **Step 1: Create branch**

```bash
git checkout main && git pull
git checkout -b feat/phase5a-pr-b1-dep-audit
```

- [ ] **Step 2: Audit current requirements.txt to confirm the moves**

```bash
grep -n "pytest-cov\|py2app\|playwright\|selenium" requirements.txt
grep -n "google-generativeai\|google.genai\|google-genai" requirements.txt
```

Expected: each of the 4 dev deps appears in `requirements.txt` (confirms the move is needed). Both Gemini SDKs should appear.

- [ ] **Step 3: Move the 4 non-runtime deps from `requirements.txt` to `requirements-dev.txt`**

Delete the 4 lines from `requirements.txt`. Add them to `requirements-dev.txt` with preserved version constraints.

Example — before, `requirements.txt` might have:
```
pytest-cov>=4.1
py2app>=0.28
playwright>=1.40
selenium>=4.15
```

After Step 3:
- `requirements.txt` no longer contains these lines.
- `requirements-dev.txt` now contains them (append to the file).

- [ ] **Step 4: Add a comment to `requirements.txt` about dual Gemini SDKs**

At the top of `requirements.txt`, add:

```
# Graider runtime dependencies. Non-runtime dev tooling (pytest-cov,
# py2app, playwright, selenium) lives in requirements-dev.txt.
#
# Dual Gemini SDK note: `google-generativeai` is used for chat-style text
# generation (planner_routes, assistant_routes, slide_generator:155);
# `google.genai` is used for image generation (slide_generator:258).
# Phase 5b's adapter unification will collapse these if possible.
```

- [ ] **Step 5: Remove ad-hoc pytest-cov install from `.github/workflows/ci.yml`**

Locate in `.github/workflows/ci.yml` the `backend-tests` job's install step (currently around lines 33-38):

```yaml
      - name: Install dependencies
        run: |
          pip install -r requirements.txt pytest-cov
          if [ -f requirements-dev.txt ]; then
            pip install -r requirements-dev.txt
          fi
```

Change to:

```yaml
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
```

(pytest-cov is now in requirements-dev.txt, so the ad-hoc install is redundant; requirements-dev.txt existence check is no longer needed since we're requiring it.)

- [ ] **Step 6: Verify locally**

```bash
# Fresh venv to prove requirements.txt alone is sufficient for app boot
python -m venv /tmp/v-b1-prod
/tmp/v-b1-prod/bin/pip install -r requirements.txt
/tmp/v-b1-prod/bin/python -c "from backend.app import app; print('ok')"

# Different fresh venv to prove dev deps still install
python -m venv /tmp/v-b1-dev
/tmp/v-b1-dev/bin/pip install -r requirements.txt -r requirements-dev.txt
/tmp/v-b1-dev/bin/python -c "import pytest_cov, py2app, playwright, selenium; print('ok')"

# Clean up
rm -rf /tmp/v-b1-prod /tmp/v-b1-dev
```

Expected: both `print('ok')` succeed.

- [ ] **Step 7: Run full test suite to verify pytest-cov still works**

```bash
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -q -m "not live" --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e --cov=backend --cov-fail-under=32 2>&1 | tail -5
```

Expected: same pass count as before (~1537 passing, 11 skipped), with coverage report.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt requirements-dev.txt .github/workflows/ci.yml
git commit -m "$(cat <<'EOF'
refactor: Phase 5a PR B1 — dependency ownership audit (runtime vs dev)

Move 4 non-runtime deps from requirements.txt → requirements-dev.txt:
  - pytest-cov (test-only)
  - py2app (Mac packaging, not loaded at runtime)
  - playwright, selenium (E2E testing)

CI: remove ad-hoc `pip install pytest-cov` before requirements-dev install
(now unnecessary since pytest-cov lives in dev requirements).

Documented dual Gemini SDK retention in requirements.txt header comment.

Prereq for Phase 5a PR B2 (pip-tools lockfile) — cleans up the source
manifests before pip-compile freezes them.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 9: Push + open PR + merge**

```bash
git push -u origin feat/phase5a-pr-b1-dep-audit
gh pr create --base main --title "refactor: Phase 5a PR B1 — dependency ownership audit" --body "$(cat <<'EOF'
## Summary

Separates runtime from non-runtime tooling in requirements files before PR B2's pip-compile lockfile work:
- Moves pytest-cov, py2app, playwright, selenium to dev requirements.
- Removes the redundant ad-hoc pytest-cov install from CI.

## Spec

docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md § PR B1.

## Test plan

- [x] Fresh prod-only venv boots the app
- [x] Fresh venv with dev requirements runs the full test suite
- [ ] CI backend-tests passes with updated install step

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr checks --watch
```

Operator merges when green.

---

## Task 3: PR B2 — pip-tools lockfile workflow

**Branch:** `feat/phase5a-pr-b2-pip-tools`
**Spec section:** PR B2
**Estimated effort:** 3-4 days (first `pip-compile` is likely to surface resolver conflicts)
**Prereq:** Task 2 merged.

**Files:**
- Rename: `requirements.txt` → `requirements.in`
- Rename: `requirements-dev.txt` → `requirements-dev.in`
- Create: new `requirements.txt` (pip-compile output, hash-verified)
- Create: new `requirements-dev.txt` (pip-compile output, hash-verified)
- Modify: `.github/workflows/ci.yml` (install with --require-hashes; add `lockfile-drift-check` job)
- Create: `docs/dependencies.md`

---

- [ ] **Step 1: Branch + install pip-tools locally**

```bash
git checkout main && git pull
git checkout -b feat/phase5a-pr-b2-pip-tools
source venv/bin/activate
pip install pip-tools
```

- [ ] **Step 2: Rename requirements files**

```bash
git mv requirements.txt requirements.in
git mv requirements-dev.txt requirements-dev.in
```

- [ ] **Step 3: Compile the production lockfile**

```bash
pip-compile --generate-hashes --output-file=requirements.txt requirements.in
```

Expected: `requirements.txt` is regenerated with every transitive dep pinned `==X.Y.Z` plus `--hash=sha256:...`. May take 1-3 minutes.

If this step fails with a resolver error, the conflict is between declared versions. Investigate, relax one constraint in `requirements.in`, re-run. Budget up to half a day for this.

- [ ] **Step 4: Compile the dev lockfile against the production lockfile**

```bash
pip-compile --generate-hashes --output-file=requirements-dev.txt requirements-dev.in -c requirements.txt
```

The `-c requirements.txt` flag constrains dev deps to versions compatible with the prod lockfile, preventing divergence.

Expected: `requirements-dev.txt` generated successfully.

- [ ] **Step 5: Verify install with --require-hashes from scratch**

```bash
python -m venv /tmp/v-b2-lock
/tmp/v-b2-lock/bin/pip install --require-hashes -r requirements.txt -r requirements-dev.txt
/tmp/v-b2-lock/bin/python -c "from backend.app import app; print('app ok')"
/tmp/v-b2-lock/bin/python -c "import pytest; print('tests ok')"
rm -rf /tmp/v-b2-lock
```

Expected: both prints succeed.

- [ ] **Step 6: Run the full test suite against the locked deps**

```bash
# Using the main venv, refresh it to exactly the lockfile
pip install --require-hashes -r requirements.txt -r requirements-dev.txt --force-reinstall
python -m pytest tests/ -q -m "not live" --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e 2>&1 | tail -5
```

Expected: same pass count as pre-lockfile.

- [ ] **Step 7: Update `.github/workflows/ci.yml` — backend-tests install step**

Change backend-tests job's install step from:

```yaml
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
```

to:

```yaml
      - name: Install dependencies
        run: |
          pip install --require-hashes -r requirements.txt
          pip install --require-hashes -r requirements-dev.txt
```

Also update any other jobs (`migrations-smoke`, `security-scan`) that do `pip install` — add `--require-hashes` there too.

- [ ] **Step 8: Add `lockfile-drift-check` job to `.github/workflows/ci.yml`**

Append to the `jobs:` section:

```yaml
  lockfile-drift-check:
    name: Lockfile Drift Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install pip-tools
        run: pip install pip-tools

      - name: Recompile lockfiles in a tmp dir and diff against committed
        run: |
          cp requirements.txt /tmp/committed-prod.txt
          cp requirements-dev.txt /tmp/committed-dev.txt
          pip-compile --generate-hashes --output-file=requirements.txt requirements.in --quiet
          pip-compile --generate-hashes --output-file=requirements-dev.txt requirements-dev.in -c requirements.txt --quiet
          diff /tmp/committed-prod.txt requirements.txt || (echo "::error::requirements.txt is stale vs requirements.in — run pip-compile locally and commit"; exit 1)
          diff /tmp/committed-dev.txt requirements-dev.txt || (echo "::error::requirements-dev.txt is stale vs requirements-dev.in — run pip-compile locally and commit"; exit 1)
```

- [ ] **Step 9: Create `docs/dependencies.md`**

```markdown
# Dependency Management

Graider uses **pip-tools** for reproducible, hash-verified installs.

## Files

- `requirements.in` — **edited by humans.** Loose version declarations.
- `requirements.txt` — **generated.** Output of `pip-compile` with full pinning + hashes.
- `requirements-dev.in` — **edited by humans.** Dev-only deps (pytest, playwright, etc.).
- `requirements-dev.txt` — **generated.** Constrained against `requirements.txt`.

## Install

```
pip install --require-hashes -r requirements.txt -r requirements-dev.txt
```

## Add a new runtime package

1. Add to `requirements.in` (loose, e.g. `somelib>=1.2`).
2. Run `pip-compile --generate-hashes --output-file=requirements.txt requirements.in`.
3. Run `pip-compile --generate-hashes --output-file=requirements-dev.txt requirements-dev.in -c requirements.txt` (to keep dev aligned).
4. Commit both `.in` and `.txt` files.
5. Open PR. The `lockfile-drift-check` CI job verifies your `.txt` files match what `.in` would regenerate.

## Upgrade a package

Same as above — edit the version pin in `.in`, recompile.

## Resolve a conflict

`pip-compile` will print which pins conflict. Common causes:
- Overly tight pin on a transitive dep — relax the constraint in `.in`.
- Incompatible versions across two direct deps — pick one to pin looser.

## Hash mismatch at install

Means someone hand-edited `.txt` without recompiling. Regenerate both lockfiles with `pip-compile`, commit, retry.
```

- [ ] **Step 10: Commit everything**

```bash
git add requirements.in requirements.txt requirements-dev.in requirements-dev.txt .github/workflows/ci.yml docs/dependencies.md
git commit -m "$(cat <<'EOF'
feat: Phase 5a PR B2 — pip-tools lockfile workflow + drift-check CI

Splits:
  requirements.txt → requirements.in (human) + requirements.txt (compiled+pinned+hashed)
  requirements-dev.txt → requirements-dev.in (human) + requirements-dev.txt (compiled, constrained by prod lock)

CI:
  - All pip install steps now use --require-hashes
  - New job lockfile-drift-check: recompiles .in files, diffs against
    committed .txt, fails if stale. Enforces "edit .in → recompile .txt"
    workflow

Docs:
  - New docs/dependencies.md covering add/upgrade/conflict/install-hash workflows

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 11: Push + open PR + watch CI**

```bash
git push -u origin feat/phase5a-pr-b2-pip-tools
gh pr create --base main --title "feat: Phase 5a PR B2 — pip-tools lockfile workflow" --body "$(cat <<'EOF'
## Summary

- Splits `requirements*.txt` into human-edited `.in` inputs + pip-compile-generated `.txt` outputs with full pinning and hash verification.
- All CI pip installs now use `--require-hashes`.
- New `lockfile-drift-check` CI job fails if someone edits `.in` without regenerating `.txt`.
- Adds `docs/dependencies.md`.

## Spec

docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md § PR B2.

## Test plan

- [x] Fresh venv install with `--require-hashes` succeeds (prod + dev)
- [x] Full test suite passes against locked deps
- [ ] CI backend-tests passes with hashed install
- [ ] lockfile-drift-check passes
- [ ] Railway deploys successfully (hash-verified install on production image)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr checks --watch
```

Operator merges when green.

---

## Task 4: PR C1 — Logging payload contract (`emit()` helper)

**Branch:** `feat/phase5a-pr-c1-emit-helper`
**Spec section:** PR C1
**Estimated effort:** 1 day
**Prereq:** Task 3 merged (so adding any dep goes through the new lockfile flow — note: C1 itself adds no new deps).

**Files:**
- Create: `backend/observability/events.py`
- Create: `tests/test_observability_events.py`
- Modify: `backend/observability/db_mode.py` (refactor to use helper, no behavior change)
- Modify: `docs/observability.md` (document the convention)

---

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b feat/phase5a-pr-c1-emit-helper
```

- [ ] **Step 2: Write the failing test for the helper**

Create `tests/test_observability_events.py`:

```python
"""Tests for the structured-event emit() helper.

emit() writes structured fields as JSON-encoded text inside the logger
record's `message` attribute — the fields are nested inside the outer
log line's `message` field after the JsonFormatter runs.
"""
from __future__ import annotations

import json
import logging

from backend.observability.events import emit


def _capture_records(caplog):
    return [r for r in caplog.records if r.name.startswith("backend.observability.events")]


def test_emit_info_level_serializes_event_and_fields(caplog):
    with caplog.at_level(logging.INFO, logger="backend.observability.events"):
        emit("llm.call.start", model="gpt-4", tokens=0)

    records = _capture_records(caplog)
    assert len(records) == 1
    payload = json.loads(records[0].message)
    assert payload == {
        "event": "llm.call.start",
        "model": "gpt-4",
        "tokens": 0,
    }


def test_emit_warning_level(caplog):
    with caplog.at_level(logging.WARNING, logger="backend.observability.events"):
        emit("llm.call.error", level="warning", model="gpt-4", error_kind="rate_limit")

    records = _capture_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    payload = json.loads(records[0].message)
    assert payload["event"] == "llm.call.error"
    assert payload["error_kind"] == "rate_limit"
    # level should NOT leak into payload — it controls the logger level
    assert "level" not in payload


def test_emit_default_level_is_info(caplog):
    with caplog.at_level(logging.DEBUG, logger="backend.observability.events"):
        emit("test.event")

    records = _capture_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.INFO


def test_emit_unknown_level_raises():
    import pytest
    with pytest.raises(ValueError):
        emit("test.event", level="bogus")
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
source venv/bin/activate
python -m pytest tests/test_observability_events.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.observability.events'` (or similar).

- [ ] **Step 4: Create `backend/observability/events.py`**

```python
"""Structured-event emit() helper for machine-parsed logs.

This module provides the single entry point for emitting machine-parsed
structured events to the logging pipeline. The existing `JsonFormatter`
(backend/utils/logging_utils.py) serializes only a fixed set of outer
fields (timestamp, level, logger, request_id, message, optional exception).
Structured event data is carried INSIDE the `message` field as a
JSON-encoded string — consumers parse `message` as JSON to extract the
`event` name and its fields.

This is the same pattern used by backend/observability/db_mode.py, which
is refactored to use this helper in the same PR (Phase 5a PR C1).

Example output (after the JsonFormatter runs):

    {"timestamp": "2026-04-20T12:34:56Z", "level": "INFO",
     "logger": "backend.observability.events",
     "request_id": "abc-123",
     "message": "{\\"event\\": \\"llm.call.start\\", \\"model\\": \\"gpt-4\\"}"}

To add a new event type: call emit(name, **fields) anywhere. No
formatter changes needed.
"""
from __future__ import annotations

import json
import logging

_logger = logging.getLogger(__name__)

_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def emit(event: str, level: str = "info", **fields) -> None:
    """Emit a structured event as a JSON payload inside the log record's message.

    Args:
        event: short dotted name for the event (e.g. "llm.call.start").
            Becomes the "event" key in the serialized payload.
        level: logging level — one of "debug", "info", "warning", "error",
            "critical". Controls the log level, NOT included in the payload.
        **fields: arbitrary serializable key/value pairs. Included in the
            payload alongside "event".

    Raises:
        ValueError: if level is not a recognized level name.
    """
    level_int = _LEVEL_MAP.get(level.lower())
    if level_int is None:
        raise ValueError(f"unknown log level: {level!r}")

    payload = {"event": event, **fields}
    _logger.log(level_int, json.dumps(payload))
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
python -m pytest tests/test_observability_events.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Refactor `backend/observability/db_mode.py` to use the helper**

Open `backend/observability/db_mode.py`. Locate the current JSON-in-message emission pattern (around lines 63-75 per the spec). It currently does something like:

```python
import json
import logging
_logger = logging.getLogger("backend.db_mode")

def _log_request(auth_source, db_mode, path, method, status):
    event = {
        "event": "request.db_mode",
        "auth_source": auth_source,
        "db_mode": db_mode,
        "path": path,
        "method": method,
        "status": status,
    }
    _logger.info(json.dumps(event))
```

Change the body to use the helper:

```python
from backend.observability.events import emit

def _log_request(auth_source, db_mode, path, method, status):
    emit(
        "request.db_mode",
        auth_source=auth_source,
        db_mode=db_mode,
        path=path,
        method=method,
        status=status,
    )
```

Remove the now-unused `import json` if nothing else in the file needs it.

**Note on the logger name:** `emit()` uses logger `backend.observability.events`, not `backend.db_mode`. If downstream log parsing in BetterStack keys off the logger name, add an alias — or better, the event-name JSON payload is the stable key, so the logger name change is acceptable. Confirm with the operator before landing if BetterStack has a filter on `backend.db_mode` logger name.

- [ ] **Step 7: Run the existing db_mode tests to verify no behavior regression**

```bash
python -m pytest tests/test_db_mode_logger.py -v
```

Expected: all 4 tests pass. If any break due to the logger-name change, update the test's assertion to match the new logger name.

- [ ] **Step 8: Update `docs/observability.md` with the convention**

If `docs/observability.md` exists, add a section:

```markdown
## Structured events (`emit()` helper)

For machine-parsed log events (e.g. traffic split, LLM call metrics),
use `backend.observability.events.emit()`:

```python
from backend.observability.events import emit

emit("llm.call.complete", model="gpt-4", duration_ms=423, tokens=150)
```

The event name and fields are serialized as JSON inside the outer log
line's `message` field — consumers parse `message` as JSON to extract
`event` and its fields.

For human-readable operational messages, continue using standard
`logger.info/warning/exception` calls.
```

If `docs/observability.md` does NOT exist, create it with this section plus a one-paragraph intro referencing `backend/utils/logging_utils.py` for the formatter shape.

- [ ] **Step 9: Run full suite**

```bash
python -m pytest tests/ -q -m "not live" --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e 2>&1 | tail -5
```

Expected: same pass count as before + 4 new (the test_observability_events.py tests).

- [ ] **Step 10: Commit**

```bash
git add backend/observability/events.py tests/test_observability_events.py backend/observability/db_mode.py docs/observability.md
git commit -m "$(cat <<'EOF'
feat: Phase 5a PR C1 — structured-event emit() helper

Adds backend/observability/events.py with a single entry point for
machine-parsed log events. Follows the existing JSON-in-message pattern
used by db_mode.py (structured fields nest inside the JsonFormatter's
`message` field as JSON-encoded text — no formatter extension needed).

Refactors db_mode.py to use the helper instead of calling json.dumps
and logger.info directly. Zero behavior change on the outer log line
shape (other than logger name; see PR description).

Canonical field name is `event` — consistent across helper signature,
serialized payload, tests, and docs.

Prereq for Phase 5a PR C2 (print migration) and PR D1 (llm.call.*
metrics).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 11: Push + open PR + watch CI + merge**

```bash
git push -u origin feat/phase5a-pr-c1-emit-helper
gh pr create --base main --title "feat: Phase 5a PR C1 — structured-event emit() helper" --body "$(cat <<'EOF'
## Summary

Adds `backend/observability/events.py` providing `emit(event, **fields)` as the single entry point for structured events. Uses the existing JSON-in-message pattern — no formatter changes.

Refactors `db_mode.py` to use the helper.

## Spec

docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md § PR C1.

## Reviewer note on logger name change

`db_mode.py` previously logged via `logging.getLogger("backend.db_mode")`. After refactor, it routes through `backend.observability.events`. If BetterStack has a filter on the old logger name, alert me before merge.

## Test plan

- [x] 4 new unit tests for emit() pass
- [x] Existing db_mode tests pass (no behavior regression)
- [x] Full suite green
- [ ] CI all jobs pass

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr checks --watch
```

Operator merges when green.

---

## Task 5: PR C2 — `print()` migration + Ruff T20 lint rule

**Branch:** `feat/phase5a-pr-c2-print-migration`
**Spec section:** PR C2
**Estimated effort:** 2-3 days
**Prereq:** Task 3 merged (adds `ruff` via pip-compile workflow) AND Task 4 merged (`emit()` helper available).

**Files:**
- Modify: `requirements-dev.in` (add `ruff`) + regenerated `requirements-dev.txt`
- Modify: `pyproject.toml` (add `[tool.ruff]` section)
- Modify: `.github/workflows/ci.yml` (add `ruff-lint` job)
- Modify: 18 backend files for print→logger migration (see inventory)

**Inventory (top 4 hotspots; spec lists more):**
- `backend/grading/pipeline.py` (28 prints)
- `backend/services/email_service.py` (22 prints) — **partial migration:** module has both runtime paths (routes call into it — migrate those prints) AND a CLI `if __name__ == "__main__"` block (allow-list that block)
- `backend/app.py` (21 prints) — including startup banner at lines 1908-1917
- `backend/routes/planner_routes.py` (12 prints)

**Allow-list (keep these prints as-is):**
- `backend/services/outlook_sender.py:17-18, 36-38` — intentional stdout JSON IPC protocol
- `backend/services/visualization.py:1164-1195` — local test harness
- `backend/migrations/env.py:29-35, 77-82` — hard-fail CLI errors to stderr
- `backend/services/email_service.py:262-299` — CLI `if __name__ == "__main__"` block
- `backend/scripts/**` — CLI scripts

---

- [ ] **Step 1: Branch + add `ruff` to dev requirements**

```bash
git checkout main && git pull
git checkout -b feat/phase5a-pr-c2-print-migration
source venv/bin/activate

# Add ruff to requirements-dev.in (follow B2's workflow)
echo "ruff>=0.3" >> requirements-dev.in
pip-compile --generate-hashes --output-file=requirements-dev.txt requirements-dev.in -c requirements.txt
pip install --require-hashes -r requirements-dev.txt
```

- [ ] **Step 2: Add ruff config to `pyproject.toml`**

Open `pyproject.toml` (create it if it doesn't exist; if it has only a stub, extend it).

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["T20"]  # flake8-print

[tool.ruff.lint.per-file-ignores]
# Allow intentional prints in these specific locations — do NOT expand
# this list without review. See Phase 5a PR C2.
"backend/services/outlook_sender.py" = ["T20"]  # stdout JSON IPC protocol
"backend/services/visualization.py" = ["T20"]  # local test harness
"backend/services/email_service.py" = ["T20"]  # CLI __main__ block (line 262+)
"backend/migrations/env.py" = ["T20"]  # hard-fail CLI errors to stderr
"backend/scripts/**" = ["T20"]  # CLI scripts
```

- [ ] **Step 3: Run ruff locally to see baseline violation count**

```bash
ruff check backend/
```

Expected: long list of T20 violations across the backend. This is what Step 4+ will fix.

- [ ] **Step 4: Migrate `backend/grading/pipeline.py` prints (28 sites)**

Open `backend/grading/pipeline.py`. For each `print(...)` call:

- Plain status messages → `_logger.info(msg)` (add `import logging; _logger = logging.getLogger(__name__)` if missing at module top)
- Warnings/recoverable errors → `_logger.warning(msg)`
- Unrecoverable errors → `_logger.error(msg)` or `_logger.exception(msg)` inside `except`
- Structured events with fields (token counts, costs) → `emit("pipeline.X", field=value, ...)` via `from backend.observability.events import emit`

Example transformation (for reference):

Before:
```python
print(f"Starting grading for {file_count} files")
# ...
print(f"WARN: missing answer key for question {q_num}")
```

After:
```python
_logger.info("Starting grading for %d files", file_count)
# ...
_logger.warning("missing answer key for question %s", q_num)
```

Verify: `ruff check backend/grading/pipeline.py` returns zero T20 violations.

- [ ] **Step 5: Migrate `backend/services/email_service.py` runtime prints (NOT the __main__ block)**

Open the file. Scope: lines 23, 85, 103, 107, 127, 130, 134, 150, 192, 228-231, 238, 242, 248 are runtime-path prints. Lines 262-299 are the `if __name__ == "__main__":` block — leave those, they're allow-listed.

Apply the same migration pattern as Step 4.

Verify: `ruff check backend/services/email_service.py` returns zero T20 violations outside the allow-listed block.

- [ ] **Step 6: Migrate `backend/app.py` prints**

Open the file. The prints split into:

- Lines 187, 193, 203, 231, 275, 348, 630, 690, 745, 1271, 1495 — runtime paths, migrate.
- Lines 1908-1917 — **startup banner.** Migrate to `_logger.info(banner_line)` per line. The banner typically runs at module load; logger messages at info level still appear in Railway logs.

Verify: `ruff check backend/app.py` returns zero T20 violations.

- [ ] **Step 7: Migrate `backend/routes/planner_routes.py` prints (12 sites)**

Open the file. Sites at lines 102, 480, 572, 794, 1289, 1945, 2318, 2320, 2499, 3725, 4244, 5098.

Apply the migration pattern. Some of these may already be inside except blocks; use `_logger.exception` in those cases.

Verify: `ruff check backend/routes/planner_routes.py` returns zero T20 violations.

- [ ] **Step 8: Migrate the long-tail files (14 more files, ~77 remaining prints)**

Run `ruff check backend/` to enumerate remaining T20 violations — they're now only in the long tail. Address each file.

Expected list of remaining files (derived from spec's count of 18 files total; exact list emerges from the ruff run):
- `backend/accommodations.py`
- `backend/student_history.py`
- `backend/routes/assignment_player_routes.py`
- `backend/routes/email_routes.py`
- `backend/routes/grading_routes.py`
- `backend/routes/settings_routes.py`
- etc.

For each file: add a module-level `_logger = logging.getLogger(__name__)` if missing, then migrate each print using the pattern from Step 4.

After all files: `ruff check backend/` returns zero T20 violations.

- [ ] **Step 9: Add `ruff-lint` CI job to `.github/workflows/ci.yml`**

Append to the `jobs:` section:

```yaml
  ruff-lint:
    name: Ruff Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install Ruff
        run: pip install ruff

      - name: Run Ruff against backend/
        run: ruff check backend/
```

- [ ] **Step 10: Run full test suite to verify no regressions**

```bash
python -m pytest tests/ -q -m "not live" --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e 2>&1 | tail -5
```

Expected: same pass count. Any test that asserts against a printed string (unlikely but possible) needs updating to use the logger's records via `caplog`.

- [ ] **Step 11: Verify the lint rule catches new print()**

Temporarily add a `print("test")` to any non-allow-listed file, run `ruff check backend/`, confirm it fails. Remove the test print.

- [ ] **Step 12: Commit (this is likely multiple commits for reviewability — one per hotspot file, one for the long tail, one for CI + config)**

Suggested commit sequence:

```bash
# Commit 1: ruff + pyproject config
git add requirements-dev.in requirements-dev.txt pyproject.toml
git commit -m "chore: Phase 5a PR C2 — add ruff with T20 print-check rule"

# Commit 2: hotspot migrations (4 commits — one per file)
git add backend/grading/pipeline.py
git commit -m "refactor: Phase 5a PR C2 — migrate pipeline.py prints to logger (28 sites)"

git add backend/services/email_service.py
git commit -m "refactor: Phase 5a PR C2 — migrate email_service runtime prints (CLI block allow-listed)"

git add backend/app.py
git commit -m "refactor: Phase 5a PR C2 — migrate app.py prints (incl. startup banner)"

git add backend/routes/planner_routes.py
git commit -m "refactor: Phase 5a PR C2 — migrate planner_routes.py prints (12 sites)"

# Commit 3: long tail
git add backend/ ':!backend/grading/pipeline.py' ':!backend/services/email_service.py' ':!backend/app.py' ':!backend/routes/planner_routes.py'
git commit -m "refactor: Phase 5a PR C2 — migrate long-tail prints across remaining backend files"

# Commit 4: CI lint gate
git add .github/workflows/ci.yml
git commit -m "ci: Phase 5a PR C2 — add ruff-lint job to block future print() introduction"
```

- [ ] **Step 13: Push + open PR + watch CI + merge**

```bash
git push -u origin feat/phase5a-pr-c2-print-migration
gh pr create --base main --title "refactor: Phase 5a PR C2 — print() migration + Ruff T20 lint" --body "$(cat <<'EOF'
## Summary

Migrates 160 runtime `print()` calls across 18 backend files to `logger.X(...)` (and `emit(...)` for structured events), then blocks future regressions with Ruff's T20 rule.

Allow-listed locations (kept):
- `backend/services/outlook_sender.py` — stdout JSON IPC protocol
- `backend/services/visualization.py` — local test harness
- `backend/services/email_service.py` — CLI `__main__` block (line 262+)
- `backend/migrations/env.py` — hard-fail CLI errors
- `backend/scripts/**` — CLI scripts

Includes a new `ruff-lint` CI job and Ruff configuration in `pyproject.toml`.

## Spec

docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md § PR C2.

## Test plan

- [x] Full test suite passes
- [x] `ruff check backend/` returns zero findings
- [x] Verified that adding a new print() in a non-allow-listed file fails ruff
- [ ] CI ruff-lint + backend-tests pass
- [ ] BetterStack ingests new JSON log lines correctly (spot-check post-merge)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr checks --watch
```

Operator merges when green.

---

## Task 6: PR D1 — LLM provider adapter (non-streaming)

**Branch:** `feat/phase5a-pr-d1-llm-adapter`
**Spec section:** PR D1
**Estimated effort:** 5-6 days (the biggest PR; split into sub-commits)
**Prereq:** Task 4 merged (emit() helper for llm.call.* metrics).

**Files:**
- Create: `backend/services/llm_adapter/__init__.py` — public exports
- Create: `backend/services/llm_adapter/types.py` — `Message`, `ContentPart` union, `LLMRequest`, `LLMResponse`, `ToolDef`, `ToolCall`, `Usage`, `ResponseFormat`
- Create: `backend/services/llm_adapter/openai_adapter.py`
- Create: `backend/services/llm_adapter/anthropic_adapter.py`
- Create: `backend/services/llm_adapter/gemini_adapter.py`
- Create: `tests/test_llm_adapter_types.py`
- Create: `tests/test_llm_adapter_openai.py`
- Create: `tests/test_llm_adapter_anthropic.py`
- Create: `tests/test_llm_adapter_gemini.py`
- Modify: ~15 call sites across `backend/routes/{planner_routes,assignment_routes,assignment_player_routes,grading_routes,lesson_routes}.py`, `backend/app.py`, `backend/services/{grading_service,assistant_tools_behavior,assistant_tools_ai,seo_service,assignment_post_processing,slide_generator}.py`

**Inventory (26 non-streaming sites):** see spec § PR D1.

---

- [ ] **Step 1: Branch + scaffold package**

```bash
git checkout main && git pull
git checkout -b feat/phase5a-pr-d1-llm-adapter
mkdir -p backend/services/llm_adapter
touch backend/services/llm_adapter/__init__.py
```

- [ ] **Step 2: Write the failing test for the type system**

Create `tests/test_llm_adapter_types.py`:

```python
"""Tests for Phase 5a PR D1 adapter type definitions.

Verifies the shapes of Message, ContentPart, LLMRequest, LLMResponse,
and their frozen-dataclass semantics.
"""
from __future__ import annotations

import pytest

from backend.services.llm_adapter.types import (
    ContentPart,
    ImagePart,
    LLMRequest,
    LLMResponse,
    Message,
    TextPart,
    ToolCall,
    ToolResultPart,
    ToolUsePart,
    Usage,
)


def test_textpart_is_content_part():
    p = TextPart(text="hello")
    assert isinstance(p, ContentPart)
    assert p.text == "hello"


def test_imagepart_accepts_url_or_base64():
    p1 = ImagePart(url="https://example.com/img.png", base64=None, mime_type="image/png")
    p2 = ImagePart(url=None, base64="iVBORw0KG...", mime_type="image/png")
    assert p1.url == "https://example.com/img.png"
    assert p2.base64.startswith("iVBORw")


def test_message_with_text_content():
    msg = Message(role="user", content=[TextPart(text="hi")])
    assert msg.role == "user"
    assert len(msg.content) == 1
    assert isinstance(msg.content[0], TextPart)


def test_message_tool_role_has_tool_call_id():
    msg = Message(
        role="tool",
        content=[ToolResultPart(tool_call_id="abc", content="result")],
        tool_call_id="abc",
    )
    assert msg.role == "tool"
    assert msg.tool_call_id == "abc"


def test_llmrequest_minimal():
    req = LLMRequest(
        model="gpt-4",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )
    assert req.model == "gpt-4"
    assert req.system_prompt is None
    assert req.tools is None
    assert req.metadata == {}


def test_llmresponse_shape():
    resp = LLMResponse(
        content_parts=[TextPart(text="hello")],
        tool_calls=[],
        usage=Usage(prompt_tokens=5, completion_tokens=3, cost_usd=0.0001),
        finish_reason="stop",
        provider="openai",
        model="gpt-4",
    )
    assert resp.usage.prompt_tokens == 5
    assert resp.finish_reason == "stop"


def test_llmrequest_is_frozen():
    req = LLMRequest(model="gpt-4", messages=[])
    with pytest.raises(Exception):  # FrozenInstanceError in dataclasses
        req.model = "gpt-3.5"
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
python -m pytest tests/test_llm_adapter_types.py -v
```

Expected: `ImportError: cannot import name 'TextPart' from ...` or similar.

- [ ] **Step 4: Implement `backend/services/llm_adapter/types.py`**

```python
"""Type definitions for the LLM provider adapter layer (Phase 5a PR D1).

See docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md § PR D1
for design rationale. The shapes below are driven by the live repo's
current call sites (multimodal input, tool use, system prompts).

All types are frozen dataclasses — immutable value objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Union


# ---- ContentPart union -------------------------------------------------

@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class ImagePart:
    # Exactly one of url or base64 must be set.
    url: str | None
    base64: str | None
    mime_type: str  # e.g. "image/png", "image/jpeg"


@dataclass(frozen=True)
class ToolUsePart:
    """Assistant-side: the model wants to call a tool."""
    tool_call_id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolResultPart:
    """User-side: result fed back in response to a prior ToolUsePart."""
    tool_call_id: str
    content: str | dict[str, Any]  # stringified result or structured data


# Python doesn't have a real union base class without PEP 604, so use a
# type alias. isinstance() checks work against the concrete types.
ContentPart = Union[TextPart, ImagePart, ToolUsePart, ToolResultPart]


# ---- Message wrapper ---------------------------------------------------

@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant", "tool"]
    content: list[ContentPart]
    # Set when role == "tool"; mirrors the tool_call_id of the
    # corresponding ToolResultPart for providers that need it at the
    # message level (e.g. OpenAI).
    tool_call_id: str | None = None


# ---- Tool definitions --------------------------------------------------

@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]  # JSON Schema


@dataclass(frozen=True)
class ToolCall:
    tool_call_id: str
    name: str
    args: dict[str, Any]


# ---- Response format ---------------------------------------------------

@dataclass(frozen=True)
class ResponseFormat:
    # "text" (default) or "json_object" / "json_schema"
    type: Literal["text", "json_object", "json_schema"]
    schema: dict[str, Any] | None = None  # required if type == "json_schema"


# ---- Usage -------------------------------------------------------------

@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


# ---- Request / Response ------------------------------------------------

DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class LLMRequest:
    model: str
    messages: list[Message]
    system_prompt: str | None = None
    tools: list[ToolDef] | None = None
    response_format: ResponseFormat | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    timeout: float = DEFAULT_TIMEOUT
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    content_parts: list[ContentPart]
    tool_calls: list[ToolCall]
    usage: Usage
    finish_reason: str  # "stop" | "length" | "tool_use" | "content_filter"
    provider: str  # "openai" | "anthropic" | "gemini"
    model: str
```

Also add to `backend/services/llm_adapter/__init__.py`:

```python
"""LLM provider adapter layer (Phase 5a PR D1)."""
from backend.services.llm_adapter.types import (
    ContentPart,
    ImagePart,
    LLMRequest,
    LLMResponse,
    Message,
    ResponseFormat,
    TextPart,
    ToolCall,
    ToolDef,
    ToolResultPart,
    ToolUsePart,
    Usage,
    DEFAULT_TIMEOUT,
)

__all__ = [
    "ContentPart",
    "ImagePart",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "ResponseFormat",
    "TextPart",
    "ToolCall",
    "ToolDef",
    "ToolResultPart",
    "ToolUsePart",
    "Usage",
    "DEFAULT_TIMEOUT",
]
```

- [ ] **Step 5: Run the types test to verify it passes**

```bash
python -m pytest tests/test_llm_adapter_types.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Commit the types foundation**

```bash
git add backend/services/llm_adapter/ tests/test_llm_adapter_types.py
git commit -m "feat: Phase 5a PR D1 — LLM adapter type scaffolding (Message, ContentPart, LLMRequest/Response)"
```

- [ ] **Step 7: Write failing OpenAI adapter test**

Create `tests/test_llm_adapter_openai.py`:

```python
"""Tests for the OpenAI adapter (Phase 5a PR D1)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.llm_adapter.openai_adapter import OpenAIAdapter
from backend.services.llm_adapter.types import (
    LLMRequest,
    Message,
    TextPart,
    ImagePart,
)


def _mock_openai_response(text: str = "hello", finish_reason: str = "stop"):
    choice = MagicMock()
    choice.message.content = text
    choice.message.tool_calls = None
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    usage.total_tokens = 15

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp.model = "gpt-4"
    return resp


@patch("openai.OpenAI")
def test_adapter_maps_simple_text_message(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response()

    adapter = OpenAIAdapter(api_key="test-key")
    req = LLMRequest(
        model="gpt-4",
        messages=[Message(role="user", content=[TextPart(text="hello")])],
    )
    resp = adapter.chat(req)

    assert resp.provider == "openai"
    assert resp.model == "gpt-4"
    assert resp.content_parts == [TextPart(text="hello")]
    assert resp.finish_reason == "stop"
    assert resp.usage.prompt_tokens == 10

    # Verify the mapping sent to OpenAI
    mock_client.chat.completions.create.assert_called_once()
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4"
    assert kwargs["messages"] == [{"role": "user", "content": "hello"}]


@patch("openai.OpenAI")
def test_adapter_maps_system_prompt_to_system_message(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response()

    adapter = OpenAIAdapter(api_key="test-key")
    req = LLMRequest(
        model="gpt-4",
        system_prompt="You are a helpful assistant.",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )
    adapter.chat(req)

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["messages"][0] == {
        "role": "system",
        "content": "You are a helpful assistant.",
    }
    assert kwargs["messages"][1] == {"role": "user", "content": "hi"}


@patch("openai.OpenAI")
def test_adapter_maps_image_part_to_image_url_content(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response()

    adapter = OpenAIAdapter(api_key="test-key")
    req = LLMRequest(
        model="gpt-4",
        messages=[Message(
            role="user",
            content=[
                TextPart(text="What's in this image?"),
                ImagePart(url="https://example.com/x.png", base64=None, mime_type="image/png"),
            ],
        )],
    )
    adapter.chat(req)

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    user_msg = kwargs["messages"][0]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    assert user_msg["content"][0] == {"type": "text", "text": "What's in this image?"}
    assert user_msg["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "https://example.com/x.png"},
    }
```

- [ ] **Step 8: Run the OpenAI test to verify it fails**

```bash
python -m pytest tests/test_llm_adapter_openai.py -v
```

Expected: `ImportError: cannot import name 'OpenAIAdapter' ...`.

- [ ] **Step 9: Implement `backend/services/llm_adapter/openai_adapter.py`**

```python
"""OpenAI adapter for the Phase 5a LLM adapter layer.

Maps LLMRequest/Response to/from openai.chat.completions.create.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from openai import OpenAI

from backend.observability.events import emit
from backend.retry import with_retry
from backend.services.llm_adapter.types import (
    ContentPart,
    ImagePart,
    LLMRequest,
    LLMResponse,
    Message,
    TextPart,
    ToolCall,
    Usage,
)

_logger = logging.getLogger(__name__)


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough per-1K-token pricing. Update as models evolve."""
    # Values accurate as of 2026-04. Conservative estimate — real billing
    # is authoritative, this is for observability only.
    rates = {
        "gpt-4": (0.03, 0.06),
        "gpt-4-turbo": (0.01, 0.03),
        "gpt-4o": (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
    }
    in_rate, out_rate = rates.get(model, (0.01, 0.03))
    return round(prompt_tokens * in_rate / 1000 + completion_tokens * out_rate / 1000, 6)


def _content_to_openai(content: list[ContentPart]) -> str | list[dict[str, Any]]:
    """Map our ContentPart list to OpenAI's message content shape.

    If content is a single TextPart, return a string (OpenAI accepts this
    as a shorthand). Otherwise return the array-of-parts form for
    multimodal input.
    """
    if len(content) == 1 and isinstance(content[0], TextPart):
        return content[0].text

    parts: list[dict[str, Any]] = []
    for p in content:
        if isinstance(p, TextPart):
            parts.append({"type": "text", "text": p.text})
        elif isinstance(p, ImagePart):
            if p.url:
                parts.append({"type": "image_url", "image_url": {"url": p.url}})
            else:
                # base64 data URL
                data_url = f"data:{p.mime_type};base64,{p.base64}"
                parts.append({"type": "image_url", "image_url": {"url": data_url}})
        # ToolUsePart / ToolResultPart are not valid inside message.content
        # for OpenAI — they belong at the tool_calls / tool role level.
        # A message shouldn't mix them with text parts.
    return parts


def _message_to_openai(msg: Message) -> dict[str, Any]:
    result: dict[str, Any] = {"role": msg.role}
    if msg.role == "tool" and msg.tool_call_id:
        result["tool_call_id"] = msg.tool_call_id
    result["content"] = _content_to_openai(msg.content)
    return result


class OpenAIAdapter:
    """Adapter for OpenAI's chat completions API."""

    def __init__(self, api_key: str | None = None):
        self._client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self._provider = "openai"

    def chat(self, request: LLMRequest) -> LLMResponse:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        for msg in request.messages:
            messages.append(_message_to_openai(msg))

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "timeout": request.timeout,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.response_format is not None:
            if request.response_format.type == "json_object":
                kwargs["response_format"] = {"type": "json_object"}
            elif request.response_format.type == "json_schema":
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": request.response_format.schema,
                }
        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in request.tools
            ]

        emit(
            "llm.call.start",
            provider=self._provider,
            model=request.model,
            **{k: v for k, v in request.metadata.items() if isinstance(v, (str, int, float, bool))},
        )
        t0 = time.monotonic()

        try:
            raw = with_retry(
                lambda: self._client.chat.completions.create(**kwargs),
                label=f"openai.chat.completions.create({request.model})",
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            emit(
                "llm.call.error",
                level="warning",
                provider=self._provider,
                model=request.model,
                duration_ms=duration_ms,
                error_kind=type(e).__name__,
            )
            raise

        duration_ms = int((time.monotonic() - t0) * 1000)

        # Map response
        choice = raw.choices[0]
        content_parts: list[ContentPart] = []
        if choice.message.content:
            content_parts.append(TextPart(text=choice.message.content))

        tool_calls: list[ToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                import json as _json
                tool_calls.append(ToolCall(
                    tool_call_id=tc.id,
                    name=tc.function.name,
                    args=_json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments,
                ))

        usage = Usage(
            prompt_tokens=raw.usage.prompt_tokens if raw.usage else 0,
            completion_tokens=raw.usage.completion_tokens if raw.usage else 0,
            cost_usd=_estimate_cost_usd(
                request.model,
                raw.usage.prompt_tokens if raw.usage else 0,
                raw.usage.completion_tokens if raw.usage else 0,
            ),
        )

        emit(
            "llm.call.complete",
            provider=self._provider,
            model=request.model,
            duration_ms=duration_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=usage.cost_usd,
            finish_reason=choice.finish_reason,
        )

        return LLMResponse(
            content_parts=content_parts,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.finish_reason,
            provider=self._provider,
            model=raw.model,
        )
```

Add export in `backend/services/llm_adapter/__init__.py`:

```python
from backend.services.llm_adapter.openai_adapter import OpenAIAdapter
```

And add `"OpenAIAdapter"` to `__all__`.

- [ ] **Step 10: Run OpenAI adapter tests to verify they pass**

```bash
python -m pytest tests/test_llm_adapter_openai.py -v
```

Expected: 3 passed.

- [ ] **Step 11: Commit OpenAI adapter**

```bash
git add backend/services/llm_adapter/openai_adapter.py backend/services/llm_adapter/__init__.py tests/test_llm_adapter_openai.py
git commit -m "feat: Phase 5a PR D1 — OpenAI adapter with request/response mapping"
```

- [ ] **Step 12: Repeat the test-implement-commit cycle for Anthropic adapter**

Create `tests/test_llm_adapter_anthropic.py` following the same pattern as the OpenAI tests, but testing Anthropic's shape: `system=` as a top-level param (not a message), `messages=` with `content` as list-of-blocks, `tools=` with JSON schema.

Key test cases:
- System prompt maps to top-level `system=` param (NOT a message).
- Multimodal image input maps to Anthropic's `{"type": "image", "source": {"type": "base64", "media_type": ..., "data": ...}}` shape for base64, or `{"type": "image", "source": {"type": "url", "url": ...}}` for URL.
- Tool-use response: `ToolUsePart` blocks in the response content are extracted into `tool_calls`.

Implement `backend/services/llm_adapter/anthropic_adapter.py` following the same structure as OpenAI. Map to `anthropic.Anthropic().messages.create(...)`. Response content is a list of blocks (text + tool_use); flatten into `content_parts` + `tool_calls`.

```bash
python -m pytest tests/test_llm_adapter_anthropic.py -v
# Expected: all tests pass
git add backend/services/llm_adapter/anthropic_adapter.py backend/services/llm_adapter/__init__.py tests/test_llm_adapter_anthropic.py
git commit -m "feat: Phase 5a PR D1 — Anthropic adapter with request/response mapping"
```

- [ ] **Step 13: Repeat for Gemini adapter**

Create `tests/test_llm_adapter_gemini.py`. Key test cases:
- `system_prompt` maps to `system_instruction=` at model creation time.
- `messages` map to `contents=` as a list of `{role, parts}` dicts (Gemini uses `role: "user" | "model"`, NOT "assistant" — map "assistant" → "model").
- Multimodal image input maps to `{"inline_data": {"mime_type": ..., "data": base64}}` parts.

Implement `backend/services/llm_adapter/gemini_adapter.py`. Map to `google.generativeai.GenerativeModel(model, system_instruction=sys).generate_content(contents=[...])`.

```bash
python -m pytest tests/test_llm_adapter_gemini.py -v
git add backend/services/llm_adapter/gemini_adapter.py backend/services/llm_adapter/__init__.py tests/test_llm_adapter_gemini.py
git commit -m "feat: Phase 5a PR D1 — Gemini adapter with request/response mapping"
```

- [ ] **Step 14: Migrate the 26 non-streaming call sites**

For each site, the migration pattern is:

**Before** (example from some route):
```python
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
resp = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7,
)
result_text = resp.choices[0].message.content
```

**After:**
```python
from backend.services.llm_adapter import OpenAIAdapter, LLMRequest, Message, TextPart
adapter = OpenAIAdapter()
resp = adapter.chat(LLMRequest(
    model="gpt-4",
    messages=[Message(role="user", content=[TextPart(text=prompt)])],
    temperature=0.7,
))
result_text = resp.content_parts[0].text if resp.content_parts else ""
```

**Migration order (one commit per file):**

1. `backend/routes/assignment_routes.py:148`
2. `backend/routes/assignment_player_routes.py:344` (multimodal — has an image part)
3. `backend/routes/grading_routes.py:768`
4. `backend/routes/lesson_routes.py:463`
5. `backend/services/grading_service.py:235`
6. `backend/services/assistant_tools_behavior.py:599`
7. `backend/services/assistant_tools_ai.py:123`
8. `backend/services/seo_service.py:38`
9. `backend/services/assignment_post_processing.py:1929`
10. `backend/services/slide_generator.py:155` (Gemini text gen)
11. `backend/app.py:1560, 1626` (one commit for both, `:1626` is multimodal)
12. `backend/routes/planner_routes.py` — 14 sites. Subdivide into 3-4 commits to keep diffs reviewable (e.g. "planner_routes: migrate lesson-generation sites", "planner_routes: migrate assessment-generation sites", etc.).

For each site:

- [ ] Write a unit test that mocks `LLMAdapter.chat` and verifies the route/service calls it with the expected `LLMRequest`.
- [ ] Run the test, verify it fails (function not yet using the adapter).
- [ ] Migrate the call site.
- [ ] Run the test, verify it passes.
- [ ] Run full suite to verify no regression.
- [ ] Commit.

**Example commit:**

```bash
git add backend/routes/assignment_routes.py tests/test_assignment_routes_llm_adapter.py
git commit -m "refactor: Phase 5a PR D1 — migrate assignment_routes.py:148 to LLMAdapter"
```

- [ ] **Step 15: Remove direct provider imports from migrated files**

After all 26 sites are migrated, the `openai`, `anthropic`, and `google.generativeai` imports at the top of migrated files are dead code — delete them. Run the full suite after each removal.

**Do NOT remove these imports until ALL migration is done**, or a partially-migrated file will break at import time.

- [ ] **Step 16: Final full-suite verification**

```bash
python -m pytest tests/ -q -m "not live" --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e 2>&1 | tail -5
```

Expected: same pass count as before + adapter unit tests.

- [ ] **Step 17: Push + open PR + watch CI + merge**

```bash
git push -u origin feat/phase5a-pr-d1-llm-adapter
gh pr create --base main --title "feat: Phase 5a PR D1 — LLM provider adapter (non-streaming, 26 sites)" --body "$(cat <<'EOF'
## Summary

Creates `backend/services/llm_adapter/` — a unified request/response model (`LLMRequest`, `LLMResponse`) + three provider adapters (`OpenAIAdapter`, `AnthropicAdapter`, `GeminiAdapter`). Migrates 26 non-streaming LLM call sites.

Request model is first-class on `system_prompt`, `tools`, `response_format`, `max_tokens`, `temperature`, `timeout`. Multi-turn via `list[Message]`. Multimodal via `list[ContentPart]` inside each message.

Every call:
- Times out per-provider (default 60s).
- Retries via existing `backend.retry.with_retry()`.
- Emits `llm.call.start/complete/error` structured events via `backend.observability.events.emit()`.

Excluded from this PR:
- `backend/routes/assistant_routes.py` streaming sites (PR D2).
- `backend/services/slide_generator.py:258` image generation (Phase 5b sibling adapter).
- Circuit breakers (Phase 5b, will wrap the adapter).

## Spec

docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md § PR D1.

## Test plan

- [x] Type definitions round-trip (frozen dataclasses, role semantics)
- [x] Per-provider request-mapping snapshot tests
- [x] Per-provider response-mapping snapshot tests (incl. multimodal, tools)
- [x] Per-call-site unit tests verify adapter is called with expected LLMRequest
- [x] Full test suite passes
- [ ] CI all jobs pass
- [ ] Deploy + smoke-test grading/planner/assistant-tools flows in production

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr checks --watch
```

Operator merges when green.

---

## Task 7: PR D2 — LLM adapter streaming + tool-use (assistant_routes)

**Branch:** `feat/phase5a-pr-d2-adapter-streaming`
**Spec section:** PR D2
**Estimated effort:** 4-5 days
**Prereq:** Task 6 merged.

**Files:**
- Create: `backend/services/llm_adapter/streaming.py` — `StreamEvent` union (`TextDelta`, `ToolCallDelta`, `ToolCallComplete`, `Usage`, `FinishEvent`)
- Create: `tests/test_llm_adapter_streaming.py`
- Modify: `backend/services/llm_adapter/openai_adapter.py` (add `stream_chat`)
- Modify: `backend/services/llm_adapter/anthropic_adapter.py` (add `stream_chat`)
- Modify: `backend/services/llm_adapter/gemini_adapter.py` (add `stream_chat`)
- Modify: `backend/services/llm_adapter/__init__.py` (export stream types)
- Modify: `backend/routes/assistant_routes.py` — migrate 3 streaming sites (lines 1461, 1508, 1620) + extract tool-schema conversion and tool-call reconstruction from the route into per-adapter helpers (currently route-level at ~95-192, 1455-1657).

---

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b feat/phase5a-pr-d2-adapter-streaming
```

- [ ] **Step 2: Write failing tests for stream event types**

Create `tests/test_llm_adapter_streaming.py`:

```python
"""Tests for the streaming stream-event types (Phase 5a PR D2)."""
from __future__ import annotations

import pytest

from backend.services.llm_adapter.streaming import (
    FinishEvent,
    StreamEvent,
    TextDelta,
    ToolCallComplete,
    ToolCallDelta,
    UsageEvent,
)
from backend.services.llm_adapter.types import ToolCall, Usage


def test_text_delta():
    e = TextDelta(text="hello")
    assert isinstance(e, StreamEvent)
    assert e.text == "hello"


def test_tool_call_delta_incremental():
    e = ToolCallDelta(tool_call_id="abc", name="weather", args_delta='{"loc')
    assert e.tool_call_id == "abc"


def test_tool_call_complete():
    tc = ToolCall(tool_call_id="abc", name="weather", args={"loc": "SF"})
    e = ToolCallComplete(tool_call=tc)
    assert e.tool_call.name == "weather"


def test_usage_event_wraps_usage():
    e = UsageEvent(usage=Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.001))
    assert e.usage.prompt_tokens == 10


def test_finish_event():
    e = FinishEvent(finish_reason="tool_use")
    assert e.finish_reason == "tool_use"
```

- [ ] **Step 3: Run to verify fail**

```bash
python -m pytest tests/test_llm_adapter_streaming.py -v
```

Expected: `ImportError`.

- [ ] **Step 4: Implement `backend/services/llm_adapter/streaming.py`**

```python
"""Streaming stream-event types for Phase 5a PR D2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from backend.services.llm_adapter.types import ToolCall, Usage


@dataclass(frozen=True)
class TextDelta:
    """Incremental text chunk from the model's streaming response."""
    text: str


@dataclass(frozen=True)
class ToolCallDelta:
    """Partial tool-call state during streaming.

    Provider-native tool-call streaming emits arg-delta chunks; adapters
    normalize those into this event. Consumers assemble the complete
    tool call by concatenating `args_delta` across all deltas sharing
    the same `tool_call_id`, OR wait for the ToolCallComplete event.
    """
    tool_call_id: str
    name: str | None   # present on the first delta for a given call
    args_delta: str    # JSON fragment


@dataclass(frozen=True)
class ToolCallComplete:
    """Emitted after all deltas for a tool call have assembled."""
    tool_call: ToolCall


@dataclass(frozen=True)
class UsageEvent:
    """Final usage report, emitted at end of stream."""
    usage: Usage


@dataclass(frozen=True)
class FinishEvent:
    """End of stream marker."""
    finish_reason: str  # "stop" | "length" | "tool_use" | "content_filter"


StreamEvent = Union[TextDelta, ToolCallDelta, ToolCallComplete, UsageEvent, FinishEvent]
```

- [ ] **Step 5: Run tests to verify pass**

```bash
python -m pytest tests/test_llm_adapter_streaming.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit streaming types**

```bash
git add backend/services/llm_adapter/streaming.py tests/test_llm_adapter_streaming.py
git commit -m "feat: Phase 5a PR D2 — stream-event types"
```

- [ ] **Step 7: Add `stream_chat` to OpenAI adapter**

In `backend/services/llm_adapter/openai_adapter.py`, add a new method `stream_chat(request: LLMRequest) -> Iterator[StreamEvent]`. Implementation: `self._client.chat.completions.create(..., stream=True)` yields chunks. Normalize:

- Chunks with `choice.delta.content` → `TextDelta(text=content)`
- Chunks with `choice.delta.tool_calls[i]` → `ToolCallDelta(tool_call_id=id, name=name_if_first, args_delta=arguments)`
- Final chunk with `choice.finish_reason` → assemble any accumulated tool calls into `ToolCallComplete`, then emit `UsageEvent` (from separate `stream_options={"include_usage": True}`), then `FinishEvent`.

Write per-event tests against captured cassettes of real OpenAI streams. (Cassette capture: run the real API once in dev, capture the chunk sequence via pytest-recording or pytest-vcr, replay.)

- [ ] **Step 8: Add `stream_chat` to Anthropic adapter**

Anthropic's streaming uses event-based deltas: `message_start`, `content_block_delta`, `content_block_stop`, `message_delta`, `message_stop`. Map:

- `content_block_delta` (type=text_delta) → `TextDelta`
- `content_block_delta` (type=input_json_delta, for tools) → `ToolCallDelta`
- `content_block_stop` where the block was a tool_use → `ToolCallComplete`
- `message_delta` with usage → `UsageEvent`
- `message_stop` → `FinishEvent`

Tests against cassettes of real Anthropic streams.

- [ ] **Step 9: Add `stream_chat` to Gemini adapter**

Gemini's `generate_content(stream=True)` yields chunks with `.text` and potentially `.function_call`. Map to `TextDelta` and `ToolCallDelta` / `ToolCallComplete`. Tests against cassettes.

- [ ] **Step 10: Export stream types from `__init__.py`**

Add to `backend/services/llm_adapter/__init__.py`:

```python
from backend.services.llm_adapter.streaming import (
    FinishEvent,
    StreamEvent,
    TextDelta,
    ToolCallComplete,
    ToolCallDelta,
    UsageEvent,
)
```

Add to `__all__`.

- [ ] **Step 11: Commit adapter streaming implementations**

```bash
git add backend/services/llm_adapter/
git commit -m "feat: Phase 5a PR D2 — stream_chat on OpenAI/Anthropic/Gemini adapters"
```

- [ ] **Step 12: Migrate assistant_routes streaming sites**

Open `backend/routes/assistant_routes.py`. The three streaming sites at lines 1461 (Anthropic), 1508 (OpenAI), 1620 (Gemini) currently:
- Do provider-specific schema conversion and tool-call reconstruction inline (approx lines 95-192, 1455-1657).
- Stream deltas back to the client via SSE.

Migration plan:
1. Replace provider-specific client instantiation with the corresponding adapter.
2. Replace the streaming loop with `for event in adapter.stream_chat(LLMRequest(...))`.
3. Branch on `event` type to emit SSE chunks in the route's current output format.
4. Delete the per-provider tool-schema conversion and tool-call reconstruction from the route — the adapters now own that logic.

Write an integration test that replays a captured stream cassette through the route and asserts the SSE output is byte-identical to pre-refactor.

- [ ] **Step 13: Run full suite**

```bash
python -m pytest tests/ -q -m "not live" --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e 2>&1 | tail -5
```

Expected: same pass count + new streaming tests.

- [ ] **Step 14: Commit assistant_routes migration**

```bash
git add backend/routes/assistant_routes.py tests/test_assistant_routes_streaming.py
git commit -m "refactor: Phase 5a PR D2 — migrate assistant_routes streaming to adapter stream_chat (3 sites)"
```

- [ ] **Step 15: Push + open PR + watch CI + merge**

```bash
git push -u origin feat/phase5a-pr-d2-adapter-streaming
gh pr create --base main --title "feat: Phase 5a PR D2 — LLM adapter streaming + assistant_routes migration" --body "$(cat <<'EOF'
## Summary

Extends the D1 adapter with `stream_chat(request) -> Iterator[StreamEvent]`, migrates the 3 streaming sites in `assistant_routes.py` (Anthropic/OpenAI/Gemini), and moves per-provider tool-schema conversion + tool-call reconstruction out of the route and into the adapters.

## Spec

docs/superpowers/specs/2026-04-20-phase5a-excellence-design.md § PR D2.

## Test plan

- [x] Stream-event type tests pass
- [x] Per-provider stream_chat tests pass against captured cassettes
- [x] assistant_routes integration test: cassette replay → byte-identical SSE output vs pre-refactor
- [x] Full test suite passes
- [ ] CI all jobs pass
- [ ] Production smoke: run the assistant UI, verify streaming + tool-call round-trips work across all 3 providers

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr checks --watch
```

Operator merges when green. **Phase 5a complete.**

---

## Phase 5a completion checklist (post all 7 tasks)

- [ ] All 7 PRs merged to main.
- [ ] Full test suite green on main.
- [ ] Railway deploy stable (3× healthz=200 after each merge).
- [ ] Save memory note at `memory/project_phase5a_complete.md` capturing:
  - PR numbers assigned at merge time
  - Any deviations from this plan (all approved by operator)
  - Dimension-delta observation (6.8 → ~7.3 expected)
- [ ] Update `memory/project_codebase_improvement_roadmap.md` to reflect Phase 5a done; identify Phase 5b scope (pybreaker on adapter, APM tracing, image-generation adapter sibling).
- [ ] Run `npx gitnexus analyze --embeddings` to refresh the code-intelligence index.

---

## Self-review (2026-04-20)

**1. Spec coverage.**

| Spec section | Covered by |
|---|---|
| § PR A Bandit + trufflehog | Task 1 |
| § PR A README coverage-floor fix | Task 1 step 6 |
| § PR A baseline governance | Task 1 step 3 (inline comment in .bandit.yaml) |
| § PR A trufflehog base-SHA fetch | Task 1 step 4 (`fetch-depth: 0`) |
| § PR B1 dep ownership audit | Task 2 |
| § PR B2 pip-tools workflow | Task 3 |
| § PR B2 docs/dependencies.md | Task 3 step 9 |
| § PR C1 emit helper | Task 4 |
| § PR C1 db_mode refactor | Task 4 step 6 |
| § PR C2 print migration | Task 5 |
| § PR C2 Ruff T20 + per-file-ignores | Task 5 steps 2 + 9 |
| § PR D1 adapter scaffolding | Task 6 steps 4, 9, 12, 13 |
| § PR D1 26-site migration | Task 6 step 14 |
| § PR D1 with_retry() integration | Task 6 step 9 |
| § PR D1 emit() metrics | Task 6 step 9 |
| § PR D2 stream types | Task 7 steps 4, 6 |
| § PR D2 per-provider stream_chat | Task 7 steps 7-11 |
| § PR D2 assistant_routes migration | Task 7 step 12 |

No gaps.

**2. Placeholder scan.** All steps contain concrete code or commands. No "TBD" or "similar to Task N". Gemini and Anthropic adapters in Task 6 follow the OpenAI adapter's structure but the plan explicitly tells the implementer to write the code following the spec's provider-specific mapping rules — not a placeholder, an instruction.

**3. Type consistency.** Types used in later tasks:
- `Message`, `ContentPart`, `TextPart`, `ImagePart`, `ToolUsePart`, `ToolResultPart`, `LLMRequest`, `LLMResponse`, `ToolCall`, `ToolDef`, `Usage`, `ResponseFormat` — all defined in Task 6 step 4, used consistently in Task 7.
- `StreamEvent`, `TextDelta`, `ToolCallDelta`, `ToolCallComplete`, `UsageEvent`, `FinishEvent` — defined in Task 7 step 4.
- `emit(event, level='info', **fields)` — defined in Task 4 step 4, used in Task 6 (adapter metrics) consistently.
- `with_retry(fn, label=...)` — existing primitive, referenced in Task 6 step 9.

Field names consistent across tasks. No drift.

Plan ready for execution.
