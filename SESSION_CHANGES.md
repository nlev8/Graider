# Session Changes — Element Picker & Automation Builder Enhancements

**Date:** 2026-02-23
**Files Modified:** 5 files
**Status:** Uncommitted changes on top of commit `a9f7d19`

---

## Files Changed

### 1. `backend/automation/picker.js` (Major rewrite)

**What changed:**
- **Auto-login support:** Added `--login` CLI flag. When passed, picker auto-logs into VPortal using saved credentials from `~/.graider_data/portal_credentials.json` (same flow as runner.js `stepLogin`)
- **addInitScript injection:** Replaced `page.evaluate()` re-injection loop with `context.addInitScript()` so the picker overlay survives ALL navigations, redirects, new tabs, and login flows automatically
- **Top-level frame only:** Added `if (window.top !== window.self) return;` guard so the picker button doesn't duplicate into iframes (NGL Sync uses nested iframes)
- **Floating button moved to top-right:** `position:fixed;top:12px;right:12px` with `z-index:2147483647`
- **Hotkey changed from F2 to Option+P (Alt+P):** F2 controls screen brightness on MacBook. Also handles the pi symbol case (`\u03C0`) that Mac produces with Option+P
- **Anti-detection for NGL Sync:** `channel: 'chrome'` (uses installed Chrome), `--disable-blink-features=AutomationControlled`, `navigator.webdriver` set to false, `bypassCSP: true`
- **New tab support:** Polls the most recently opened page in the context for picked selectors

### 2. `backend/automation/runner.js` (Minor change)

**What changed:**
- No NGL-specific changes (reverted to keep runner clean and isolated)
- Runner remains unchanged from last commit — all anti-detection flags are picker-only

### 3. `backend/routes/automation_routes.py` (Two additions)

**What changed:**
- **Picker login flag:** `start_picker()` now reads `login` from request JSON and passes `--login` to picker.js subprocess
- **Delete template endpoint:** Added `DELETE /api/automations/templates/<template_id>` route that removes template JSON files from the templates directory

**New code:**
```python
# In start_picker():
auto_login = data.get("login", False)
cmd = ["node", PICKER_SCRIPT, "--url", start_url]
if auto_login:
    cmd.append("--login")

# New route:
@automation_bp.route('/api/automations/templates/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    safe_id = re.sub(r'[^a-z0-9_-]', '', template_id)
    filepath = os.path.join(TEMPLATES_DIR, safe_id + ".json")
    if os.path.exists(filepath):
        os.remove(filepath)
    return jsonify({"status": "deleted"})
```

### 4. `frontend/src/services/api.js` (Two additions)

**What changed:**
- **`startElementPicker(url, login)`:** Added `login` parameter, passes it in request body
- **`deleteTemplate(id)`:** New function — `DELETE /api/automations/templates/:id`
- Added `deleteTemplate` to default export

### 5. `frontend/src/components/AutomationBuilder.jsx` (Multiple UI enhancements)

**What changed:**
- **Auto-login checkbox:** Added `pickerAutoLogin` state (default `true`) and checkbox next to Element Picker button labeled "Auto-login"
- **Auto-apply picked selectors:** When a `selector_picked` event arrives, it auto-populates into the currently selected step's selector field (uses `usePickedSelectorRef` to avoid stale closure in setInterval)
- **Picked selectors persist:** Removed `pickerActive &&` guard — picked selectors list stays visible even after picker closes
- **Clear selector button:** Added red X button next to any `selector` or `condition_selector` field when it has a value, allowing users to clear a wrong pick
- **Template trash icon:** Added `deleteTemplateItem()` handler and Trash2 icon to template cards (matching the existing workflow card layout)

---

## Potential Conflicts to Check

| File | Risk | Details |
|------|------|---------|
| `AutomationBuilder.jsx` | **HIGH** | Other session committed changes in `a9f7d19`. Both sessions edited this file. Verify the template list rendering, picker section, and step config fields are intact. |
| `picker.js` | **HIGH** | Other session also committed changes in `a9f7d19`. Verify the full rewrite didn't lose anything from the other session. |
| `automation_routes.py` | LOW | Only added new code (login flag + delete template route). Unlikely to conflict. |
| `api.js` | LOW | Only added new functions. Unlikely to conflict. |
| `runner.js` | NONE | Reverted my changes — should match HEAD exactly. |
| `backend/static/assets/` | LOW | Frontend was rebuilt. New JS bundle generated. The other session may have also rebuilt. Only the latest build matters. |

## How to Verify

```bash
# See what's uncommitted
git diff --stat

# Review full diff
git diff

# Check for conflict with other session's work
git stash
git log --oneline -3
git stash pop
```
