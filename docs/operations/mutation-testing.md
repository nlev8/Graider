# Mutation Testing — Operator Runbook

## What this is

Mutation testing measures **test quality** by introducing small bugs (mutations) into source code and checking whether your tests catch them. A "survivor" mutation is one that the test suite did NOT detect — meaning that line of code could be quietly broken and CI would stay green. Survivors are an indicator of either weak assertions or untested code paths.

Phase 5d PR 4 added mutmut configured to mutate 6 critical Graider modules:

- `backend/utils/auth_decorators.py`
- `backend/observability/events.py`
- `backend/supabase_client.py`
- `backend/supabase_resilient.py`
- `backend/retry.py`
- `backend/grading/`

**This is NOT a CI gate** — mutmut takes 10-60+ minutes per full run, which is too slow for per-PR enforcement. Run it manually as part of quarterly test-quality audits or after significant test refactoring.

## How to run

```bash
source venv/bin/activate
mutmut run                    # full run on all configured modules
mutmut run backend/grading/   # scoped to one module/path
```

Config lives in `setup.cfg` `[mutmut]` section. Adjust `paths_to_mutate` to widen or narrow scope. The runner uses pytest with these excludes (in `pytest_add_cli_args`):

- `--ignore=tests/load` — load tests need a live server.
- `--ignore=tests/e2e` — Playwright tests need a browser + live frontend.
- `--ignore=tests/characterization` — golden-file tests use stored fixtures that drift.
- `-m "not live"` — tests marked `live` need real API keys.

`mutate_only_covered_lines = True` skips lines that pytest-cov reports as uncovered — mutating uncovered code surfaces test-coverage gaps (which we measure separately via the 32% CI floor), not test-quality gaps.

## How to inspect results

```bash
mutmut results                          # summary table per file
mutmut show 42                          # show mutation #42's diff
mutmut show all                         # show all survivor diffs
mutmut html                             # generate html/index.html report
```

## How to triage survivors

For each surviving mutation, decide:

1. **Survivor reveals a missing test** → write a test that catches the mutated code path. Re-run mutmut to confirm.

2. **Survivor is logging/observability noise** (e.g., a mutated `_logger.debug(...)` call where the test isn't asserting log output) → mark with `# pragma: no mutate` on the relevant line:

   ```python
   _logger.debug("noisy debug")  # pragma: no mutate
   ```

3. **Survivor is a defensive guard against an "impossible" branch** (e.g., `if x is None: raise` where x can never be None per upstream contracts) → mark with `# pragma: no mutate` and add a comment explaining why the branch is unreachable.

4. **Survivor is genuinely benign** (e.g., changing a constant from 60 to 61 still produces correct behavior because the test rounds up) → loosen the test if appropriate; otherwise mark `# pragma: no mutate`.

## Baseline survivor counts (2026-04-25)

Captured from the first successful `mutmut run` after Phase 5d PR 4 landed. Update this table from the most recent `mutmut results` output whenever you run a full audit.

| Module | Total mutations | Killed | Survived | Notes |
|---|---|---|---|---|
| `auth_decorators.py` | _pending_ | _pending_ | _pending_ | First baseline |
| `observability/events.py` | _pending_ | _pending_ | _pending_ | First baseline |
| `supabase_client.py` | _pending_ | _pending_ | _pending_ | First baseline |
| `supabase_resilient.py` | _pending_ | _pending_ | _pending_ | First baseline |
| `retry.py` | _pending_ | _pending_ | _pending_ | First baseline |
| `grading/state.py` | _pending_ | _pending_ | _pending_ | First baseline |
| `grading/thread.py` | _pending_ | _pending_ | _pending_ | First baseline |
| `grading/pipeline.py` | _pending_ | _pending_ | _pending_ | First baseline |
| **Total** | _pending_ | _pending_ | _pending_ | |

> **First baseline run**: this table is filled in once `mutmut run` completes a clean full-suite pass (10-60+ minutes wall-clock with the current 1671-test scope). If the cells still read `_pending_`, the operator should run `mutmut run && mutmut results` and update this file.

### Known first-run gotchas

The first time PR 4 tried to capture a baseline, mutmut's sandbox-vs-real-env differences tripped tests during the **stats** phase (mutmut runs the full suite once before mutating to record coverage; if any test fails there, mutmut aborts before generating mutations). We landed three excludes in `setup.cfg` to address this:

- `--ignore=tests/load` — load tests need a live Flask server; in a sandbox they get 429-rate-limited.
- `--ignore=tests/e2e` and `--ignore=tests/characterization` — same root cause (live server / golden files).
- `-m "not live"` — tests marked `live` need real OpenAI/Anthropic API keys.

If the next stats run still fails, add the failing test to a new exclude. Likely candidates we observed but did not exclude (because they only fail in some sandbox configurations):

- `tests/test_lti.py::TestRSAKeyManagement::test_generates_valid_pem_on_first_call` — depends on filesystem state for the LTI RSA key file.

Reproduce a stats run quickly (no actual mutation) by running the same pytest command mutmut uses:

```bash
source venv/bin/activate
pytest tests/ --ignore=tests/load --ignore=tests/e2e --ignore=tests/characterization -m "not live" -x --quiet --no-header
```

If that exits clean, `mutmut run` should also clear the stats phase.

## When to re-run

- After significant test refactoring on any of the 6 critical modules
- Quarterly as part of test-quality auditing
- Before a major release if test-suite confidence is in question

If survivor count creeps upward run-over-run, that's a signal that test quality is regressing on the critical modules.
