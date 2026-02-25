# Graider Codebase Review (February 25, 2026)

## Test Status
- `venv/bin/python -m pytest -q` → **fails**; 4 tests in `tests/test_helpers.py::TestNormalizeAssignmentName` fail because `_normalize_assignment_name` lowercases the normalized value instead of preserving teacher-facing casing.

## Findings

### 1. `_normalize_assignment_name` destroys casing (backend/services/assistant_tools.py:88-97)
- The helper lowercases its return value, yet downstream helpers/tests expect the original display casing for matching and UI copy. This causes the failing pytest suite above and also means “Chapter 1 Notes” or “Bill of Rights Quiz” show up in all-lowercase in any assistant response built from `assign_display`.
- **Fix:** Keep the normalized key strictly for comparison (e.g., return both normalized + display) or add a `preserve_case` flag so the function can serve both purposes.

### 2. Global `grading_state` is unsynchronized across threads (backend/app.py:236-271, 328-1707; backend/routes/grading_routes.py:41-193)
- The Flask routes mutate the shared `grading_state` dict at the same time the background grading thread modifies it (e.g., `/api/clear-results` replaces `grading_state["results"]` while `run_grading_thread` appends to it around lines 1523-1600). There is no lock, so clearing results during an active or recently finished run can drop entries mid-write, corrupt `master_grades.csv`, or raise `RuntimeError` if a request iterates the dict while it’s resizing.
- **Fix:** Wrap all reads/writes in a `threading.Lock` or move grading state into a concurrency-safe object (database, queue, etc.). At minimum, guard mutating endpoints so they block while `grading_state["is_running"]` is true and after `run_grading_thread` flushes pending writes.

### 3. Result paths are hard-coded to one person’s home directory (backend/app.py:1731-1734, backend/routes/grading_routes.py:122-190)
- `/api/grade` defaults to `/Users/alexc/...` for assignments, outputs, and roster. On any other machine, a request that omits those fields immediately returns 400 (“folder not found”), even though the user may have configured paths in settings. Separately, `/api/clear-results` ignores whatever output folder was used and always wipes `~/Downloads/Graider/Results`, so regrades from another directory keep ghost entries in `master_grades.csv`.
- **Fix:** Source defaults from the persisted settings file (`~/.graider_global_settings.json`) or environment variables, and have every endpoint accept/use the same resolved path instead of hard-coding one user’s laptop paths.

### 4. Assignment metadata is trapped in a global constant (assignment_grader.py:2281-2299, 6414-6423, 6452-6465)
- `ASSIGNMENT_NAME` is a hard-coded string (“Cornell Notes - Political Parties”) that must be edited manually before every run. Export helpers (`generate_email_content`, `create_outlook_drafts`, audit logs, etc.) always use that constant, even though `run_grading_thread` already auto-detects the actual assignment via configs and filenames. Forgetting to edit the constant makes every export/email/audit mislabeled and mixes multiple assignments into the wrong folder.
- **Fix:** Treat assignment name as runtime data—derive it from the matched config or the submitted filename, and thread that through the export/email helpers instead of relying on a module-level constant.

### 5. SharePoint watcher stores raw passwords on disk (sharepoint_watcher.py:48-76)
- `save_config` writes the teacher’s Microsoft password straight into `~/.graider_config.json` (only `chmod 600` for protection). Anyone with filesystem access can read it, and there is no encryption/keychain usage despite the inline TODO.
- **Fix:** Use the OS keychain/Keyring for credential storage or require an app-specific password/token instead of storing the real password. At minimum, encrypt the file with a user-provided key.

## Recommendations
1. Fix `_normalize_assignment_name` and re-run `venv/bin/python -m pytest -q` until the suite passes.
2. Introduce a synchronization strategy for `grading_state` (lock or persistence layer) before allowing multiple concurrent API calls.
3. Centralize path configuration so every route reads the same settings, and remove developer-specific defaults.
4. Replace `ASSIGNMENT_NAME`/`ROSTER_FILE` constants with configurable values wired through the UI/backend pipeline.
5. Move SharePoint credentials to a secure secret store.
