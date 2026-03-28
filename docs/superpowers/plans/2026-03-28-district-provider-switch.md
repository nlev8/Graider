# District-Level Provider Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move SIS provider switching from individual teachers to the district admin. When the district admin changes from Clever to OneRoster (or vice versa) at `/district`, automatically clear old roster data for all teachers. Remove the per-teacher 409 exclusivity block from the sync endpoint.

**Architecture:** Add provider-switch detection to `POST /api/district/config`. When `sis_type` changes, call `delete_roster_data()` for all teachers with data from the old provider. Remove the 409 exclusivity check from `oneroster_routes.py`. Remove the per-teacher "Switch provider" buttons from `SettingsTab.jsx` (the district admin handles this now).

**Tech Stack:** Flask/Python backend, Supabase service key for cross-teacher cleanup, React frontend.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/routes/district_routes.py` | MODIFY | Detect provider switch on config save, auto-clear old roster data |
| `backend/routes/oneroster_routes.py` | MODIFY | Remove 409 exclusivity check from sync endpoint |
| `frontend/src/tabs/SettingsTab.jsx` | MODIFY | Remove per-teacher "Switch provider" buttons |
| `tests/test_district_routes.py` | MODIFY | Add test for provider switch cleanup |

---

### Task 1: District Config — Auto-Clear on Provider Switch

**Files:**
- Modify: `backend/routes/district_routes.py`

- [ ] **Step 1: Add provider-switch detection to `POST /api/district/config`**

In `backend/routes/district_routes.py`, find the SIS config save block (around line 198). After `sis_type` is validated and `existing_sis` is loaded, add provider switch detection BEFORE saving the new config.

Find this code (around line 209):
```python
        existing_sis = storage_load(_KEY_SIS_CONFIG, "system") or {}

        merged = {"sis_type": sis_type}
```

Insert between those two lines:

```python
        # PROVIDER SWITCH: if sis_type is changing, clear old roster data
        # for ALL teachers who have data from the old provider
        old_sis_type = existing_sis.get("sis_type")
        if old_sis_type and old_sis_type != sis_type:
            logger.info("District SIS provider switch: %s -> %s. Clearing old roster data.", old_sis_type, sis_type)
            _clear_old_provider_data(old_sis_type)
            audit_log(
                "district_provider_switch",
                f"SIS provider switched from {old_sis_type} to {sis_type}. Old roster data cleared.",
                user="district_admin", teacher_id="system"
            )
```

- [ ] **Step 2: Add `_clear_old_provider_data()` helper function**

Add this function before the route handlers (after the existing helper functions, around line 60):

```python
def _clear_old_provider_data(old_provider):
    """Clear roster data from the old SIS provider for ALL teachers.

    When the district switches from Clever to OneRoster (or vice versa),
    this removes all classes/students/enrollments that came from the old
    provider, so the new provider can sync without conflicts.

    Args:
        old_provider: "clever" or "oneroster" — the provider being replaced
    """
    from backend.supabase_client import get_supabase as _get_sb
    from backend.roster_sync import delete_roster_data

    db = _get_sb()
    if not db:
        logger.warning("Cannot clear old provider data: Supabase not configured")
        return

    # Find all teachers who have classes with the old provider's ID prefix
    try:
        all_classes = db.table("classes").select("teacher_id, clever_section_id").execute()
    except Exception as e:
        logger.warning("Failed to query classes for provider switch: %s", str(e))
        return

    # Determine which teachers have data from the old provider
    teachers_to_clear = set()
    for row in (all_classes.data or []):
        ext_id = row.get("clever_section_id", "") or ""
        teacher_id = row.get("teacher_id", "")
        if not ext_id or not teacher_id:
            continue

        if old_provider == "oneroster" and ext_id.startswith("oneroster:"):
            teachers_to_clear.add(teacher_id)
        elif old_provider == "clever" and not ext_id.startswith("oneroster:"):
            teachers_to_clear.add(teacher_id)

    # Clear roster data for each affected teacher
    cleared = 0
    for tid in teachers_to_clear:
        try:
            delete_roster_data(tid)
            cleared += 1
        except Exception as e:
            logger.warning("Failed to clear roster for teacher %s: %s", tid, str(e))

    logger.info("Provider switch cleanup: cleared roster data for %d/%d teachers",
                cleared, len(teachers_to_clear))
```

- [ ] **Step 3: Commit**

```bash
git add backend/routes/district_routes.py
git commit -m "feat: auto-clear old roster data on district SIS provider switch"
```

---

### Task 2: Remove Per-Teacher Exclusivity Block

**Files:**
- Modify: `backend/routes/oneroster_routes.py`

- [ ] **Step 1: Remove the 409 exclusivity check from `sync_roster()`**

In `backend/routes/oneroster_routes.py`, find the sync endpoint (around line 125). Remove the entire exclusivity check block (lines 140-158):

```python
    # PROVIDER EXCLUSIVITY: Check for existing non-oneroster data
    sb = _get_supabase()
    if sb:
        try:
            existing = (
                sb.table("classes")
                .select("clever_section_id")
                .eq("teacher_id", teacher_id)
                .execute()
            )
            for row in (existing.data or []):
                ext_id = row.get("clever_section_id", "")
                if ext_id and not ext_id.startswith("oneroster:"):
                    return jsonify({
                        "error": "Roster data from another provider (e.g. Clever) already exists. "
                                 "Delete existing roster data before syncing from OneRoster."
                    }), 409
        except Exception as e:
            logger.warning("Provider exclusivity check failed: %s", str(e))
```

Replace with a comment:

```python
    # Provider exclusivity is now enforced at the district level.
    # When the district admin switches providers at /district,
    # old roster data is automatically cleared for all teachers.
```

- [ ] **Step 2: Commit**

```bash
git add backend/routes/oneroster_routes.py
git commit -m "fix: remove per-teacher 409 exclusivity check (now handled at district level)"
```

---

### Task 3: Remove Per-Teacher Switch Buttons from Settings UI

**Files:**
- Modify: `frontend/src/tabs/SettingsTab.jsx`

- [ ] **Step 1: Remove "Switch to Clever" and "Switch to OneRoster" buttons**

In `frontend/src/tabs/SettingsTab.jsx`, find and remove:

1. The "Switch to Clever" button (around line 1997-2009) — shown when OneRoster is active
2. The "Switch to OneRoster" button (around line 2749-2761) — shown when Clever is active
3. The switch confirmation dialog (around line 2779) that warns about data deletion

Replace each block with nothing (remove entirely). The district admin handles provider switching at `/district` — teachers shouldn't be switching providers individually.

Also remove the `showSwitchProviderConfirm` state variable if it exists.

**Important:** Keep the rest of the OneRoster and Clever sections intact. Only remove the switch buttons and confirmation dialog.

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/tabs/SettingsTab.jsx
git commit -m "fix: remove per-teacher provider switch buttons (handled at district level now)"
```

---

### Task 4: Tests + Verification

**Files:**
- Modify: `tests/test_district_routes.py`

- [ ] **Step 1: Add test for provider switch cleanup**

Add to `tests/test_district_routes.py`:

```python
class TestProviderSwitch:
    def test_provider_switch_triggers_cleanup(self, client):
        """When district admin changes sis_type, old roster data should be cleared."""
        with client.session_transaction() as sess:
            sess["district_admin"] = True

        # First save as "clever"
        with patch("backend.routes.district_routes.storage_save") as mock_save, \
             patch("backend.routes.district_routes.storage_load") as mock_load, \
             patch("backend.routes.district_routes._clear_old_provider_data") as mock_clear:
            mock_load.return_value = {"sis_type": "clever", "client_id": "old"}
            resp = client.post("/api/district/config",
                               data=json.dumps({"sis": {
                                   "sis_type": "oneroster",
                                   "client_id": "new-id",
                                   "client_secret": "new-secret",
                                   "base_url": "https://example.com",
                               }}),
                               content_type="application/json")
            assert resp.status_code == 200
            # Should have called cleanup for old provider
            mock_clear.assert_called_once_with("clever")

    def test_same_provider_no_cleanup(self, client):
        """Saving same sis_type should NOT trigger cleanup."""
        with client.session_transaction() as sess:
            sess["district_admin"] = True

        with patch("backend.routes.district_routes.storage_save"), \
             patch("backend.routes.district_routes.storage_load") as mock_load, \
             patch("backend.routes.district_routes._clear_old_provider_data") as mock_clear:
            mock_load.return_value = {"sis_type": "oneroster", "client_id": "existing"}
            resp = client.post("/api/district/config",
                               data=json.dumps({"sis": {
                                   "sis_type": "oneroster",
                                   "client_id": "updated-id",
                                   "client_secret": "updated-secret",
                                   "base_url": "https://example.com",
                               }}),
                               content_type="application/json")
            assert resp.status_code == 200
            mock_clear.assert_not_called()
```

- [ ] **Step 2: Run all tests**

Run: `source venv/bin/activate && python -m pytest tests/test_district_routes.py tests/test_oneroster.py tests/test_clever_compliance.py -v`
Expected: All pass

- [ ] **Step 3: Verify frontend build**

Run: `cd frontend && npx vite build 2>&1 | tail -5`

- [ ] **Step 4: Commit**

```bash
git add tests/test_district_routes.py
git commit -m "test: add provider switch cleanup tests"
```

---

## Implementation Notes

### What Changes for Each Role

| Role | Before | After |
|------|--------|-------|
| **District Admin** | No awareness of provider switching | Changing SIS type at `/district` auto-clears old roster data for all teachers |
| **Teacher** | Sees "Switch to Clever/OneRoster" buttons, must manually delete old data | No switch buttons — just sees whichever provider the district configured |
| **OneRoster sync endpoint** | Blocks with 409 if Clever data exists | Syncs freely — old data already cleared at district level |

### Safety

- Provider switch only happens when the district admin explicitly changes `sis_type` in the config
- The cleanup only deletes roster data (classes, students, enrollments, CSV files) — not teacher settings, assignments, rubrics, or grading results
- Audit-logged: `district_provider_switch` action with old and new provider types
- If cleanup fails for a specific teacher, it logs a warning and continues with the rest

### Edge Case: No District Config

If a teacher configured OneRoster manually (no district admin), the old per-teacher exclusivity check is now gone. This means they could theoretically have both Clever and OneRoster data. This is acceptable because:
1. Self-hosted deployments without a district admin are power users who can manage their own data
2. The `clever_section_id` column distinguishes providers by prefix (`oneroster:` vs plain)
3. The sync will overwrite/upsert, not conflict
