# Assessment: Codebase Review (Feb 25, 2026)

## Executive Summary
The provided `CODEBASE_REVIEW.md` document outlines 5 significant issues within the Graider backend. These findings are accurate, highly critical for the application's stability, security, and scalability, and should be prioritized immediately. The review correctly identifies technical debt that currently prevents the app from being safely deployed or run concurrently by multiple users.

## Detailed Assessment of Findings

### 1. `_normalize_assignment_name` Casing Issue
*   **Validity:** High. Lowercasing a user-facing string that is later used for UI display or assistant responses is a common bug pattern.
*   **Impact:** Causes the pytest suite to fail and results in poor UX (everything appears lowercase in the assistant).
*   **Recommendation:** The proposed fix (adding a `preserve_case` flag or returning a tuple of `(normalized, original)`) is correct. Returning both from the helper is usually the safest architectural choice so callers don't need to pass boolean flags.

### 2. Thread-Unsafe `grading_state` Mutation
*   **Validity:** Critical. Mutating a shared Python dictionary (`grading_state`) simultaneously from Flask request threads (e.g., `/api/clear-results`) and a background grading worker thread (`run_grading_thread`) is a classic race condition.
*   **Impact:** A concurrent read/write or `clear` during an append operation will raise a `RuntimeError` regarding dictionary size changing during iteration, potentially crashing the app or corrupting the CSV database.
*   **Recommendation:** The proposed fix is spot-on. Wrapping the state in a `threading.Lock()` or moving to a thread-safe Queue/Database is mandatory for a web server. Given the current architecture, a `threading.Lock` around mutations to `grading_state` is the fastest, most effective fix.

### 3. Hard-coded Local Paths
*   **Validity:** High. Hard-coding `/Users/alexc/...` means the backend is strictly bound to the original developer's local machine environment.
*   **Impact:** Any other user (or a deployed server) will immediately face `400 Folder Not Found` errors.
*   **Recommendation:** Correct. Moving to a centralized path resolution system that respects the environment or the already existing `~/.graider_global_settings.json` is required to make the project portable.

### 4. `ASSIGNMENT_NAME` Global Constant
*   **Validity:** High. Depending on a massive multi-module app to read a module-level constant (`ASSIGNMENT_NAME = "Cornell Notes - Political Parties"`) breaks modularity. 
*   **Impact:** Exported files, audit logs, and emails will silently use the wrong name and mix data into the wrong folders if the developer forgets to change the constant.
*   **Recommendation:** Correct. Assignment context (name, roster) must be passed as runtime arguments dynamically down the call stack, not imported statically.

### 5. Plaintext SharePoint Password
*   **Validity:** Critical. Storing plaintext passwords in `~/.graider_config.json` is a severe security vulnerability.
*   **Impact:** Although protected by `chmod 600`, any process running as the user or any local file exploit can read the password.
*   **Recommendation:** Correct. Using the OS `keyring` module (e.g., macOS Keychain, Windows Credential Locker) is Python's standard approach for secure secret storage on desktop apps.

## Conclusion
This codebase review is an excellent catch of architectural anti-patterns that accumulated during rapid prototyping. **All 5 items should be implemented.**

**Suggested Implementation Order:**
1.  **Item 1 (Naming Context):** Fix the test suite first (Quickest win).
2.  **Item 3 & 4 (Paths & Constants):** Fix the hardcoded paths and global variable injection so the app can be run dynamically on any machine.
3.  **Item 2 (Concurrency):** Implement the `threading.Lock` to stabilize the API.
4.  **Item 5 (Security):** Refactor the SharePoint watcher to use `keyring`.
