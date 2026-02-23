# Assessment of AUTOMATION_BUILDER_PLAN.md

## 1. Overall Concept & Feasibility
The plan to build a generic JSON-driven Playwright engine is technically sound, highly detailed, and addresses the brittleness of maintaining one-off scripts. Using a Node.js runner that communicates with the Python Flask backend via streaming NDJSON over `stdout` is an elegant, lightweight approach to Inter-Process Communication (IPC).

## 2. Architectural Strengths
*   **JSON-Driven Execution**: By separating the step definitions (JSON) from the execution engine (`runner.js`), the tool becomes highly extensible. It allows the AI assistant to easily generate and modify automations without writing or editing Python/JS code directly.
*   **Element Picker Tool**: Injecting an overlay script via Playwright to intuitively capture DOM selectors is an excellent UX addition. 
*   **AI Integration**: Exposing `create_automation`, `list_automations`, and `run_automation` directly to the AI Assistant via `assistant_tools_automation.py` neatly ties the new feature into Graider's core "vibe coding/agentic" paradigm.

## 3. Areas of Concern & Missing Details
*   **Node.js & NPM Dependencies**: The Python backend relies on `subprocess.Popen(["node", ...])`. It assumes `node` is available in the system PATH and that `playwright` is installed in the local environment. The plan lacks instructions to update `package.json` in the backend or run `npm install playwright` (or `npx playwright install` for browser binaries).
*   **Orphaned Processes**: The subprocess management uses `proc.terminate()` when stopped by the user, which is good. However, if the Flask server crashes or is forcefully terminated (e.g., `Ctrl+C`), the Node.js runner and Playwright chromium processes might be left orphaned and running in the background. Consider adding Python `atexit` hooks to ensure cleanup of `_run_state["process"]`.
*   **Global State Limits**: `_run_state` and `_picker_state` are shared global dictionaries in `automation_routes.py`. This inherently restricts the app to running one automation and one picker instance at a time across the entire backend. Since Graider is a personal, locally-hosted tool, this is acceptable, but it would fail in a multi-user server environment.

## 4. Security
*   **Credential Storage**: `runner.js` loads passwords from `portal_credentials.json`, expecting base64 encoding. While base64 provides *no* cryptographic security, it's sufficient for basic obfuscation in a strictly local, single-user environment.

## 5. Element Picker Resilience
*   The `getSelector` heuristic in `picker.js` is quite basic. While relying on `id`, `name`, `aria-label`, and `text=` is generally a good fallback chain, many modern educational portals (SPAs) use dynamically generated `id`s (e.g., `input-1a2b3c`). The picker might inadvertently capture a dynamic ID, causing the step to fail on subsequent runs. 

## Recommendation
**Approved for implementation** with the following minor adjustments:
1.  **Dependency Management**: Add explicit instructions to install `playwright` (`npm init -y` && `npm install playwright`) in the environment where `runner.js` executes.
2.  **Process Cleanup**: Add standard OS signal handling or `atexit` hooks in Python to gracefully kill the Playwright sub-processes when Graider shuts down.
