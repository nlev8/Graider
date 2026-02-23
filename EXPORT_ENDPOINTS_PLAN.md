# Graider Export Endpoints + OpenClaw Skill — Precise Code Edits

## Summary

5 backend endpoints, 6 frontend API functions, 3 frontend UI additions, 1 OpenClaw skill, 3 Playwright scripts.

**Files to modify**: 4 existing
**Files to create**: 4 new
**Estimated new lines**: ~800 backend, ~120 frontend API, ~200 frontend UI, ~400 OpenClaw

---

## Phase 1: Parent Contacts Import

### File: `backend/routes/settings_routes.py`

#### Edit 1A: Add openpyxl import (line 5, after `import csv`)

```python
# AFTER line 7: from flask import Blueprint, request, jsonify
# ADD:
import re
from datetime import datetime
```

> `re` is already potentially imported elsewhere; `datetime` is used in the export endpoints too. `openpyxl` is imported inside the endpoint to avoid load-time dependency.

#### Edit 1B: Add PARENT_CONTACTS data dir constant (after line 37)

```python
# AFTER line 37: DOCUMENTS_DIR = os.path.join(GRAIDER_DATA_DIR, "documents")
# ADD:
PARENT_CONTACTS_FILE = os.path.join(GRAIDER_DATA_DIR, "parent_contacts.json")
EXPORTS_DIR = os.path.expanduser("~/.graider_exports")
```

#### Edit 1C: Add exports dir to makedirs loop (modify line 40)

```python
# CHANGE line 40:
# FROM:
for dir_path in [GRAIDER_DATA_DIR, ROSTERS_DIR, PERIODS_DIR, DOCUMENTS_DIR]:
# TO:
for dir_path in [GRAIDER_DATA_DIR, ROSTERS_DIR, PERIODS_DIR, DOCUMENTS_DIR, EXPORTS_DIR]:
```

#### Edit 1D: Add parent contacts endpoints (after line 533, before accommodations section)

Insert after the `delete_document` route (line 533), before the accommodations section comment (line 535):

```python
# ══════════════════════════════════════════════════════════════
# PARENT CONTACTS IMPORT (from class_list Excel)
# ══════════════════════════════════════════════════════════════

def _is_email(value):
    """Detect if a string looks like an email address."""
    return bool(value and '@' in str(value))


def _clean_phone(value):
    """Return phone string or None."""
    if not value:
        return None
    s = str(value).strip()
    if '@' in s or not s:
        return None
    return s


def _parse_class_list_sheet(ws, sheet_name):
    """
    Parse one sheet of the class_list Excel file.
    Returns list of student dicts with contact info.

    Expected format:
    - Row 1: Course title
    - Row 2: Student count
    - Row 3: blank
    - Row 4: Headers (Last, First M | Student ID | Grade | 6 contact columns)
    - Row 5+: Student data
    """
    students = []

    # Find header row (contains "Last, First")
    header_row = None
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
        if row and row[0] and 'Last' in str(row[0]) and 'First' in str(row[0]):
            header_row = row_idx
            break

    if header_row is None:
        return students

    # Parse student rows after header
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        name_cell = row[0] if len(row) > 0 else None
        id_cell = row[1] if len(row) > 1 else None

        if not name_cell or not id_cell:
            continue

        name_str = str(name_cell).strip()
        if not name_str:
            continue

        # Parse "Last, First Middle" format
        if ',' in name_str:
            parts = name_str.split(',', 1)
            last_name = parts[0].strip()
            first_middle = parts[1].strip() if len(parts) > 1 else ''
        else:
            last_name = name_str
            first_middle = ''

        # Student ID: strip last 2 digits (grade code) to get 7-digit roster ID
        raw_id = str(int(float(str(id_cell)))) if id_cell else ''
        roster_id = raw_id[:-2] if len(raw_id) >= 9 else raw_id

        # Scan all 6 contact columns (indices 3-8)
        emails = set()
        phones = []
        for col_idx in range(3, min(9, len(row))):
            val = row[col_idx]
            if not val:
                continue
            val_str = str(val).strip()
            if _is_email(val_str):
                emails.add(val_str.lower())
            elif val_str:
                phone = _clean_phone(val_str)
                if phone and phone not in phones:
                    phones.append(phone)

        student_name = (first_middle + ' ' + last_name).strip() if first_middle else last_name

        students.append({
            'student_name': student_name,
            'last_name': last_name,
            'first_middle': first_middle,
            'period': sheet_name,
            'roster_id': roster_id,
            'raw_student_id': raw_id,
            'parent_emails': sorted(emails),
            'parent_phones': phones,
        })

    return students


@settings_bp.route('/api/import-parent-contacts', methods=['POST'])
def import_parent_contacts():
    """
    Import parent contact info from class_list Excel file.
    Expected format: Multi-sheet xlsx, one sheet per period.
    Headers at row 4: Last, First M | Student ID | Grade | 6 contact columns.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({"error": "Please upload an Excel file (.xlsx)"}), 400

    try:
        import openpyxl

        # Save temporarily
        tmp_path = os.path.join(GRAIDER_DATA_DIR, "tmp_class_list.xlsx")
        file.save(tmp_path)

        wb = openpyxl.load_workbook(tmp_path, read_only=True, data_only=True)

        contacts = {}
        total_students = 0
        period_counts = {}

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            students = _parse_class_list_sheet(ws, sheet_name)
            period_counts[sheet_name] = len(students)
            total_students += len(students)

            for s in students:
                rid = s['roster_id']
                if rid in contacts:
                    # Merge contacts if student appears in multiple sheets
                    existing = contacts[rid]
                    existing['parent_emails'] = sorted(
                        set(existing['parent_emails']) | set(s['parent_emails'])
                    )
                    for p in s['parent_phones']:
                        if p not in existing['parent_phones']:
                            existing['parent_phones'].append(p)
                else:
                    contacts[rid] = {
                        'student_name': s['student_name'],
                        'period': s['period'],
                        'parent_emails': s['parent_emails'],
                        'parent_phones': s['parent_phones'],
                    }

        wb.close()

        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        # Save to JSON
        with open(PARENT_CONTACTS_FILE, 'w') as f:
            json.dump(contacts, f, indent=2)

        # Count stats
        with_email = sum(1 for c in contacts.values() if c['parent_emails'])
        without_email = sum(1 for c in contacts.values() if not c['parent_emails'])

        return jsonify({
            "status": "imported",
            "total_students": total_students,
            "unique_students": len(contacts),
            "with_email": with_email,
            "without_email": without_email,
            "periods": period_counts,
        })

    except ImportError:
        return jsonify({"error": "openpyxl not installed. Run: pip install openpyxl"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/api/parent-contacts')
def get_parent_contacts():
    """Return stored parent contacts with summary stats."""
    if not os.path.exists(PARENT_CONTACTS_FILE):
        return jsonify({"contacts": {}, "count": 0, "with_email": 0})

    try:
        with open(PARENT_CONTACTS_FILE, 'r') as f:
            contacts = json.load(f)

        with_email = sum(1 for c in contacts.values() if c.get('parent_emails'))

        # Group by period
        period_stats = {}
        for c in contacts.values():
            period = c.get('period', 'Unknown')
            if period not in period_stats:
                period_stats[period] = {'total': 0, 'with_email': 0}
            period_stats[period]['total'] += 1
            if c.get('parent_emails'):
                period_stats[period]['with_email'] += 1

        return jsonify({
            "contacts": contacts,
            "count": len(contacts),
            "with_email": with_email,
            "without_email": len(contacts) - with_email,
            "period_stats": period_stats,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

---

## Phase 2: Focus Grade Batch Export

### File: `backend/routes/grading_routes.py`

#### Edit 2A: Add datetime import (after line 2)

```python
# AFTER line 9: import csv
# ADD:
import json
from datetime import datetime
```

> Note: `json` is already imported inline in several functions — this moves it to top-level.

#### Edit 2B: Add EXPORTS_DIR constant (after line 12)

```python
# AFTER line 12: grading_bp = Blueprint('grading', __name__)
# ADD:
EXPORTS_DIR = os.path.expanduser("~/.graider_exports")
FOCUS_EXPORTS_DIR = os.path.join(EXPORTS_DIR, "focus")
OUTLOOK_EXPORTS_DIR = os.path.join(EXPORTS_DIR, "outlook")

for _dir in [EXPORTS_DIR, FOCUS_EXPORTS_DIR, OUTLOOK_EXPORTS_DIR]:
    os.makedirs(_dir, exist_ok=True)
```

#### Edit 2C: Add batch focus export endpoint (after line 545, before student history section)

Insert after the existing `export_focus_csv` route (ends ~line 545), before the student history section:

```python
@grading_bp.route('/api/export-focus-batch', methods=['POST'])
def export_focus_batch():
    """
    Export grades as per-period CSV files for Focus SIS bulk import.

    Format per file: "Student ID,Score" (space in header per Focus requirement).
    Files written to ~/.graider_exports/focus/

    Input JSON: { results?, assignment? }
    Defaults to grading_state["results"] if results not provided.
    """
    data = request.json or {}
    results = data.get('results') or (grading_state.get("results", []) if grading_state else [])
    assignment = data.get('assignment', 'Assignment')

    if not results:
        return jsonify({"error": "No results to export"}), 400

    # Group by period
    by_period = {}
    for r in results:
        period = r.get('period', 'All')
        if period not in by_period:
            by_period[period] = []
        by_period[period].append(r)

    safe_assignment = ''.join(
        c if c.isalnum() or c in ' -_' else '' for c in assignment
    ).strip().replace(' ', '_')

    period_results = []
    for period, period_items in by_period.items():
        safe_period = period.replace(' ', '_').replace('/', '-')
        filename = f"{safe_assignment}_{safe_period}.csv"
        filepath = os.path.join(FOCUS_EXPORTS_DIR, filename)

        matched = 0
        unmatched = 0
        csv_lines = ['Student ID,Score']  # Note: space in "Student ID" per Focus

        for r in period_items:
            student_id = r.get('student_id', '')
            score = r.get('score', 0)
            if student_id:
                csv_lines.append(f"{student_id},{score}")
                matched += 1
            else:
                # Comment out unmatched students
                name = r.get('student_name', 'Unknown')
                csv_lines.append(f"# {name},{score}")
                unmatched += 1

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(csv_lines))

        period_results.append({
            "period": period,
            "file": filename,
            "count": matched,
            "unmatched": unmatched,
        })

    # Write manifest
    manifest = {
        "assignment": assignment,
        "exported_at": datetime.now().isoformat(),
        "periods": period_results,
        "export_dir": FOCUS_EXPORTS_DIR,
    }

    manifest_path = os.path.join(FOCUS_EXPORTS_DIR, "manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return jsonify(manifest)
```

---

## Phase 3: Focus Comments Export

### File: `backend/routes/grading_routes.py`

#### Edit 3A: Add comments export endpoint (immediately after the batch export above)

```python
@grading_bp.route('/api/export-focus-comments', methods=['POST'])
def export_focus_comments():
    """
    Export per-student comments/feedback for Focus SIS.
    Writes per-period JSON files to ~/.graider_exports/focus/

    Input JSON: { results?, assignment? }
    """
    data = request.json or {}
    results = data.get('results') or (grading_state.get("results", []) if grading_state else [])
    assignment = data.get('assignment', 'Assignment')

    if not results:
        return jsonify({"error": "No results to export"}), 400

    # Group by period
    by_period = {}
    for r in results:
        period = r.get('period', 'All')
        if period not in by_period:
            by_period[period] = []
        by_period[period].append({
            "student_id": r.get('student_id', ''),
            "student_name": r.get('student_name', ''),
            "comment": r.get('feedback', ''),
            "score": r.get('score', 0),
            "letter_grade": r.get('letter_grade', ''),
        })

    safe_assignment = ''.join(
        c if c.isalnum() or c in ' -_' else '' for c in assignment
    ).strip().replace(' ', '_')

    period_results = []
    for period, students in by_period.items():
        safe_period = period.replace(' ', '_').replace('/', '-')
        filename = f"comments_{safe_assignment}_{safe_period}.json"
        filepath = os.path.join(FOCUS_EXPORTS_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(students, f, indent=2)

        period_results.append({
            "period": period,
            "file": filename,
            "count": len(students),
        })

    manifest = {
        "assignment": assignment,
        "type": "comments",
        "exported_at": datetime.now().isoformat(),
        "periods": period_results,
        "export_dir": FOCUS_EXPORTS_DIR,
    }

    manifest_path = os.path.join(FOCUS_EXPORTS_DIR, "comments_manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return jsonify(manifest)
```

---

## Phase 4: Outlook Email Export

### File: `backend/routes/email_routes.py`

#### Edit 4A: Add imports at top (after line 2)

```python
# AFTER line 2: from collections import defaultdict
# ADD:
import os
import json
from datetime import datetime
```

#### Edit 4B: Add Outlook export endpoint (after line 172, at end of file)

```python
# ══════════════════════════════════════════════════════════════
# OUTLOOK EMAIL EXPORT
# ══════════════════════════════════════════════════════════════

GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
PARENT_CONTACTS_FILE = os.path.join(GRAIDER_DATA_DIR, "parent_contacts.json")
OUTLOOK_EXPORTS_DIR = os.path.expanduser("~/.graider_exports/outlook")
os.makedirs(OUTLOOK_EXPORTS_DIR, exist_ok=True)


@email_bp.route('/api/export-outlook-emails', methods=['POST'])
def export_outlook_emails():
    """
    Build email payloads for parent notification via Outlook.
    Matches students to parent emails via parent_contacts.json.

    Writes JSON to ~/.graider_exports/outlook/

    Input JSON: {
        results?,           # defaults to grading_state results
        teacher_name?,      # defaults to saved config
        email_signature?,   # custom signature
        include_secondary?  # include CC for secondary contacts (default true)
    }
    """
    try:
        data = request.json or {}

        # Load parent contacts
        if not os.path.exists(PARENT_CONTACTS_FILE):
            return jsonify({"error": "No parent contacts imported. Upload class list in Settings first."}), 400

        with open(PARENT_CONTACTS_FILE, 'r') as f:
            contacts = json.load(f)

        # Get results - try request body first, then grading state
        results = data.get('results', [])
        if not results:
            # Try to load from grading state via the grading module
            try:
                results_file = os.path.expanduser("~/.graider_results.json")
                if os.path.exists(results_file):
                    with open(results_file, 'r') as f:
                        results = json.load(f)
            except Exception:
                pass

        if not results:
            return jsonify({"error": "No results to export"}), 400

        teacher_name = data.get('teacher_name', 'Your Teacher')
        email_signature = data.get('email_signature', '')
        include_secondary = data.get('include_secondary', True)
        assignment = data.get('assignment') or results[0].get('assignment', 'Assignment')

        # Try to load teacher config
        try:
            from backend.services.email_service import GraiderEmailer
            emailer = GraiderEmailer()
            if not teacher_name or teacher_name == 'Your Teacher':
                teacher_name = emailer.config.get('teacher_name', teacher_name)
        except Exception:
            pass

        emails = []
        no_contact = []

        for r in results:
            student_id = r.get('student_id', '')
            student_name = r.get('student_name', 'Student')
            score = r.get('score', 0)
            letter_grade = r.get('letter_grade', '')
            feedback = r.get('feedback', '')
            period = r.get('period', '')
            first_name = student_name.split()[0] if student_name else 'Student'
            last_name = student_name.split()[-1] if student_name and len(student_name.split()) > 1 else ''

            # Look up parent contact by student_id
            contact = contacts.get(student_id, {})
            parent_emails = contact.get('parent_emails', [])

            if not parent_emails:
                no_contact.append(student_name)
                continue

            # Build email
            to_email = parent_emails[0]
            cc_emails = parent_emails[1:] if include_secondary and len(parent_emails) > 1 else []

            subject = f"Grade for {assignment}: {letter_grade}"

            family_name = last_name or first_name
            body = f"Dear {family_name} family,\n\n"
            body += f"Here is {first_name}'s grade and feedback for {assignment}:\n\n"
            body += f"{'=' * 40}\n"
            body += f"GRADE: {score}/100 ({letter_grade})\n"
            body += f"{'=' * 40}\n\n"
            body += f"FEEDBACK:\n{feedback}\n"
            body += f"\n{'=' * 40}\n"
            body += f"\nIf you have any questions, please don't hesitate to reach out.\n\n"

            if email_signature:
                body += email_signature
            else:
                body += teacher_name

            emails.append({
                "to": to_email,
                "cc": ', '.join(cc_emails) if cc_emails else '',
                "subject": subject,
                "body": body,
                "student_name": student_name,
                "student_id": student_id,
                "period": period,
            })

        # Write to file
        safe_assignment = ''.join(
            c if c.isalnum() or c in ' -_' else '' for c in assignment
        ).strip().replace(' ', '_')

        output = {
            "assignment": assignment,
            "exported_at": datetime.now().isoformat(),
            "emails": emails,
            "count": len(emails),
            "no_contact": no_contact,
            "export_dir": OUTLOOK_EXPORTS_DIR,
        }

        output_path = os.path.join(OUTLOOK_EXPORTS_DIR, f"emails_{safe_assignment}.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        return jsonify(output)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

---

## Phase 5: Frontend API Functions

### File: `frontend/src/services/api.js`

#### Edit 5A: Add new export functions (after line 651, before the `export default`)

Insert before line 653 (`export default {`):

```javascript
// ============ Parent Contacts ============

export async function importParentContacts(file) {
  const formData = new FormData()
  formData.append('file', file)

  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/import-parent-contacts', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })
  return response.json()
}

export async function getParentContacts() {
  return fetchApi('/api/parent-contacts')
}

// ============ Focus Batch Export ============

export async function exportFocusBatch(results = null, assignment = null) {
  return fetchApi('/api/export-focus-batch', {
    method: 'POST',
    body: JSON.stringify({ results, assignment }),
  })
}

export async function exportFocusComments(results = null, assignment = null) {
  return fetchApi('/api/export-focus-comments', {
    method: 'POST',
    body: JSON.stringify({ results, assignment }),
  })
}

// ============ Outlook Email Export ============

export async function exportOutlookEmails(data = {}) {
  return fetchApi('/api/export-outlook-emails', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
```

#### Edit 5B: Add to default export object (inside `export default {` block)

```javascript
  // Parent Contacts & Exports
  importParentContacts,
  getParentContacts,
  exportFocusBatch,
  exportFocusComments,
  exportOutlookEmails,
```

Add these lines after the `migrateStudentNames,` line (line 736).

---

## Phase 6: Frontend UI Changes

### File: `frontend/src/App.jsx`

#### Edit 6A: Add state variables (after line 642)

After `const [focusExportLoading, setFocusExportLoading] = useState(false);` (line 642), add:

```javascript
  // Parent contacts state
  const [parentContacts, setParentContacts] = useState(null);
  const [uploadingParentContacts, setUploadingParentContacts] = useState(false);
  const parentContactsInputRef = useRef(null);
  // Batch export state
  const [batchExportLoading, setBatchExportLoading] = useState(false);
  const [outlookExportLoading, setOutlookExportLoading] = useState(false);
```

> Note: `parentContactsInputRef` also needs to be a useRef — add it near the other refs (line 1362-1363 area). Actually, since we're declaring it inline with useState, we need a separate useRef call. Let's add the ref after line 1363:

After line 1363 (`const periodInputRef = useRef(null);`), add:

```javascript
  const parentContactsInputRef = useRef(null);
```

And remove the `const parentContactsInputRef = useRef(null);` from the state block (edit 6A above) — keep it with the other refs. So edit 6A becomes:

```javascript
  // Parent contacts state
  const [parentContacts, setParentContacts] = useState(null);
  const [uploadingParentContacts, setUploadingParentContacts] = useState(false);
  // Batch export state
  const [batchExportLoading, setBatchExportLoading] = useState(false);
  const [outlookExportLoading, setOutlookExportLoading] = useState(false);
```

#### Edit 6B: Add Parent Contacts section in Settings > Classroom tab

Insert **before** the closing `</>` and `)}` of the classroom tab (at line 11651-11652), just before the `{/* Privacy Tab */}` comment. The exact insertion point is after line 11650 (`</div>`), before line 11651 (`</>`):

```jsx
                    {/* Parent Contacts Upload */}
                    <div style={{ marginTop: "30px" }}>
                      <h3
                        style={{
                          fontSize: "1.1rem",
                          fontWeight: 700,
                          marginBottom: "15px",
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <Icon
                          name="Contact"
                          size={20}
                          style={{ color: "#f59e0b" }}
                        />
                        Parent Contacts
                      </h3>
                      <p
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-secondary)",
                          marginBottom: "15px",
                        }}
                      >
                        Upload class list Excel file with parent email and phone
                        columns. Used for Focus export and Outlook email generation.
                      </p>

                      <input
                        ref={parentContactsInputRef}
                        type="file"
                        accept=".xlsx,.xls"
                        style={{ display: "none" }}
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          setUploadingParentContacts(true);
                          try {
                            const result = await api.importParentContacts(file);
                            if (result.error) {
                              addToast(result.error, "error");
                            } else {
                              addToast(
                                "Imported " + result.unique_students + " students (" + result.with_email + " with email)",
                                "success"
                              );
                              const contactsData = await api.getParentContacts();
                              setParentContacts(contactsData);
                            }
                          } catch (err) {
                            addToast("Import failed: " + err.message, "error");
                          }
                          setUploadingParentContacts(false);
                          e.target.value = "";
                        }}
                      />

                      <button
                        onClick={() => parentContactsInputRef.current?.click()}
                        className="btn btn-secondary"
                        disabled={uploadingParentContacts}
                        style={{ marginBottom: "15px" }}
                      >
                        <Icon name="Upload" size={18} />
                        {uploadingParentContacts ? "Importing..." : "Upload Class List (.xlsx)"}
                      </button>

                      {parentContacts && parentContacts.count > 0 && (
                        <div
                          style={{
                            padding: "12px 15px",
                            background: "var(--input-bg)",
                            borderRadius: "8px",
                            border: "1px solid var(--glass-border)",
                            fontSize: "0.85rem",
                          }}
                        >
                          <div style={{ fontWeight: 600, marginBottom: "8px" }}>
                            {parentContacts.count} students loaded
                          </div>
                          <div style={{ color: "var(--text-secondary)" }}>
                            {parentContacts.with_email} with parent email
                            {parentContacts.without_email > 0 && (
                              <span style={{ color: "#f59e0b" }}>
                                {" "} ({parentContacts.without_email} missing email)
                              </span>
                            )}
                          </div>
                          {parentContacts.period_stats && (
                            <div style={{ marginTop: "8px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                              {Object.entries(parentContacts.period_stats).map(function(entry) {
                                return (
                                  <span
                                    key={entry[0]}
                                    style={{
                                      padding: "2px 8px",
                                      background: "rgba(99,102,241,0.15)",
                                      borderRadius: "4px",
                                      fontSize: "0.75rem",
                                    }}
                                  >
                                    {entry[0]}: {entry[1].total}
                                  </span>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
```

#### Edit 6C: Add export buttons in Results tab action bar

In the Results tab, after the existing "Focus Export" button (line 7644-7645), add two more buttons. Insert after the closing `</button>` of the Focus Export button (after line 7645):

```jsx
                          <button
                            onClick={async () => {
                              setBatchExportLoading(true);
                              try {
                                const assignment = resultsAssignmentFilter || (status.results[0] && status.results[0].assignment) || 'Assignment';
                                const resultsToExport = resultsAssignmentFilter
                                  ? status.results.filter(function(r) { return r.assignment === resultsAssignmentFilter; })
                                  : status.results;

                                const batchRes = await api.exportFocusBatch(resultsToExport, assignment);
                                const commentsRes = await api.exportFocusComments(resultsToExport, assignment);

                                if (batchRes.error) {
                                  addToast(batchRes.error, "error");
                                } else {
                                  var totalCount = batchRes.periods.reduce(function(sum, p) { return sum + p.count; }, 0);
                                  addToast(
                                    "Exported " + totalCount + " grades + comments to " + batchRes.periods.length + " period files in ~/.graider_exports/focus/",
                                    "success"
                                  );
                                }
                              } catch (err) {
                                addToast("Batch export error: " + err.message, "error");
                              } finally {
                                setBatchExportLoading(false);
                              }
                            }}
                            className="btn btn-secondary"
                            disabled={batchExportLoading || status.results.length === 0}
                            title="Export per-period CSVs + comments to ~/.graider_exports/focus/"
                          >
                            <Icon name="FolderDown" size={18} />
                            {batchExportLoading ? "Exporting..." : "Batch Focus"}
                          </button>
                          <button
                            onClick={async () => {
                              setOutlookExportLoading(true);
                              try {
                                const assignment = resultsAssignmentFilter || (status.results[0] && status.results[0].assignment) || 'Assignment';
                                const resultsToExport = resultsAssignmentFilter
                                  ? status.results.filter(function(r) { return r.assignment === resultsAssignmentFilter; })
                                  : status.results;

                                var result = await api.exportOutlookEmails({
                                  results: resultsToExport,
                                  assignment: assignment,
                                });

                                if (result.error) {
                                  addToast(result.error, "error");
                                } else {
                                  var msg = "Generated " + result.count + " parent emails";
                                  if (result.no_contact && result.no_contact.length > 0) {
                                    msg += " (" + result.no_contact.length + " students missing parent email)";
                                  }
                                  addToast(msg, "success");
                                }
                              } catch (err) {
                                addToast("Outlook export error: " + err.message, "error");
                              } finally {
                                setOutlookExportLoading(false);
                              }
                            }}
                            className="btn btn-secondary"
                            disabled={outlookExportLoading || status.results.length === 0}
                            title="Generate parent emails from contacts in ~/.graider_exports/outlook/"
                          >
                            <Icon name="Mail" size={18} />
                            {outlookExportLoading ? "Generating..." : "Parent Emails"}
                          </button>
```

---

## Phase 7: OpenClaw Skill

### File: `~/.openclaw/skills/graider/SKILL.md` (CREATE)

```markdown
# Graider — AI Grading Assistant

Graider is a locally-running Flask + React app that grades student assignments
using OpenAI/Anthropic APIs and exports results to Focus SIS and Outlook.

## API Reference (all endpoints at http://localhost:3000)

### Export Endpoints

**POST /api/export-focus-batch**
Export per-period CSV files for Focus SIS grade import.
```bash
curl -X POST http://localhost:3000/api/export-focus-batch \
  -H "Content-Type: application/json" \
  -d '{"assignment": "Civil War DBQ"}'
```
Output: `~/.graider_exports/focus/{assignment}_{period}.csv`
Manifest: `~/.graider_exports/focus/manifest.json`

**POST /api/export-focus-comments**
Export per-period student comments JSON for Focus SIS.
```bash
curl -X POST http://localhost:3000/api/export-focus-comments \
  -H "Content-Type: application/json" \
  -d '{"assignment": "Civil War DBQ"}'
```
Output: `~/.graider_exports/focus/comments_{assignment}_{period}.json`
Manifest: `~/.graider_exports/focus/comments_manifest.json`

**POST /api/export-outlook-emails**
Generate parent email payloads matched via imported contacts.
```bash
curl -X POST http://localhost:3000/api/export-outlook-emails \
  -H "Content-Type: application/json" \
  -d '{"assignment": "Civil War DBQ", "teacher_name": "Mr. C"}'
```
Output: `~/.graider_exports/outlook/emails_{assignment}.json`

**POST /api/export-focus-csv**
Single CSV export with AI name-to-ID matching (existing endpoint).

**GET /api/parent-contacts**
Returns imported parent contact data.

**GET /api/status**
Returns current grading state including all results.

### File Locations

| Path | Contents |
|------|----------|
| `~/.graider_exports/focus/` | Per-period CSVs and comment JSONs |
| `~/.graider_exports/focus/manifest.json` | Batch export manifest |
| `~/.graider_exports/outlook/` | Email payload JSONs |
| `~/.graider_data/parent_contacts.json` | Imported parent contacts |
| `~/.graider_results.json` | Saved grading results |

### Focus SIS CSV Format

```csv
Student ID,Score
1932550,85
1920798,92
```

- Header must be `Student ID,Score` (with space)
- IDs are 7-digit roster IDs
- One file per period

### Focus Workflow (Grade Import)

1. Log in to Focus at the school's Focus portal
2. Navigate to Grades > Gradebook
3. Select the correct course/period
4. Click the assignment column (or create new assignment)
5. Click "Import Grades" or gear icon > Import
6. Upload the period CSV file
7. Map columns: Student ID → Student ID, Score → Score
8. Click Import/Submit
9. Repeat for each period

### Focus Workflow (Comment Paste)

1. In Gradebook, click on a student's grade cell
2. In the detail popup, find the Comment field
3. Paste the comment from the comments JSON
4. Save
5. Repeat per student

### Outlook Email Workflow

1. Open Outlook (web or desktop)
2. For each email in the export JSON:
   - New Message
   - To: `email.to`
   - CC: `email.cc` (if present)
   - Subject: `email.subject`
   - Body: `email.body`
   - Send

### Playwright Scripts

Available in `~/.openclaw/skills/graider/`:
- `focus-import.js` — Automates Focus grade CSV import
- `focus-comments.js` — Automates Focus comment pasting
- `outlook-emails.js` — Automates Outlook email sending

Run with: `node ~/.openclaw/skills/graider/<script>.js`
First run with `--setup` to save browser login session.
```

### File: `~/.openclaw/skills/graider/focus-import.js` (CREATE)

```javascript
/**
 * Focus SIS Grade Import Automation
 *
 * Reads manifest from ~/.graider_exports/focus/manifest.json
 * For each period: navigates to assignment, uploads CSV, submits.
 *
 * Usage:
 *   node focus-import.js --setup    # First run: save login session
 *   node focus-import.js            # Import grades using saved session
 *
 * Prerequisites:
 *   npm install playwright
 *
 * NOTE: Selectors are placeholders — update after first manual run.
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const MANIFEST_PATH = path.join(
  process.env.HOME, '.graider_exports', 'focus', 'manifest.json'
);
const SESSION_DIR = path.join(
  process.env.HOME, '.openclaw', 'skills', 'graider', '.browser-state'
);

// TODO: Set your school's Focus URL
const FOCUS_URL = process.env.FOCUS_URL || 'https://focus.school.edu';

async function setup() {
  console.log('Opening browser for manual login...');
  console.log('Log in to Focus, then close the browser window.');

  const context = await chromium.launchPersistentContext(SESSION_DIR, {
    headless: false,
  });
  const page = await context.newPage();
  await page.goto(FOCUS_URL);

  // Wait for user to close
  await new Promise((resolve) => {
    context.on('close', resolve);
  });
  console.log('Session saved to', SESSION_DIR);
}

async function importGrades() {
  if (!fs.existsSync(MANIFEST_PATH)) {
    console.error('No manifest found. Run Graider batch export first.');
    process.exit(1);
  }

  const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf-8'));
  console.log(`Importing grades for: ${manifest.assignment}`);
  console.log(`Periods: ${manifest.periods.length}`);

  const context = await chromium.launchPersistentContext(SESSION_DIR, {
    headless: false,
  });
  const page = await context.newPage();

  for (const period of manifest.periods) {
    console.log(`\n--- ${period.period} (${period.count} students) ---`);
    const csvPath = path.join(manifest.export_dir, period.file);

    if (!fs.existsSync(csvPath)) {
      console.error(`  CSV not found: ${csvPath}`);
      continue;
    }

    // TODO: Navigate to the correct period's gradebook
    // await page.goto(`${FOCUS_URL}/gradebook?period=${period.period}`);

    // TODO: Click on the assignment column or create it
    // await page.click('[data-assignment="..."]');

    // TODO: Click Import Grades
    // await page.click('button:has-text("Import")');

    // TODO: Upload the CSV file
    // const fileInput = await page.$('input[type="file"]');
    // await fileInput.setInputFiles(csvPath);

    // TODO: Map columns and submit
    // await page.click('button:has-text("Submit")');

    console.log(`  Would upload: ${csvPath}`);
    console.log(`  ${period.count} grades, ${period.unmatched} unmatched`);
  }

  await context.close();
  console.log('\nDone.');
}

const args = process.argv.slice(2);
if (args.includes('--setup')) {
  setup().catch(console.error);
} else {
  importGrades().catch(console.error);
}
```

### File: `~/.openclaw/skills/graider/focus-comments.js` (CREATE)

```javascript
/**
 * Focus SIS Comment Paste Automation
 *
 * Reads comments manifest from ~/.graider_exports/focus/comments_manifest.json
 * For each period/student: navigates to grade cell, pastes comment.
 *
 * Usage:
 *   node focus-comments.js --setup    # Save login session
 *   node focus-comments.js            # Paste comments
 *
 * NOTE: Selectors are placeholders — update after first manual run.
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const MANIFEST_PATH = path.join(
  process.env.HOME, '.graider_exports', 'focus', 'comments_manifest.json'
);
const SESSION_DIR = path.join(
  process.env.HOME, '.openclaw', 'skills', 'graider', '.browser-state'
);

const FOCUS_URL = process.env.FOCUS_URL || 'https://focus.school.edu';

async function setup() {
  console.log('Opening browser for manual login...');
  const context = await chromium.launchPersistentContext(SESSION_DIR, {
    headless: false,
  });
  const page = await context.newPage();
  await page.goto(FOCUS_URL);
  await new Promise((resolve) => context.on('close', resolve));
  console.log('Session saved.');
}

async function pasteComments() {
  if (!fs.existsSync(MANIFEST_PATH)) {
    console.error('No comments manifest found. Run Graider comments export first.');
    process.exit(1);
  }

  const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf-8'));
  console.log(`Pasting comments for: ${manifest.assignment}`);

  const context = await chromium.launchPersistentContext(SESSION_DIR, {
    headless: false,
  });
  const page = await context.newPage();

  for (const period of manifest.periods) {
    const commentsPath = path.join(manifest.export_dir, period.file);
    if (!fs.existsSync(commentsPath)) {
      console.error(`Comments file not found: ${commentsPath}`);
      continue;
    }

    const students = JSON.parse(fs.readFileSync(commentsPath, 'utf-8'));
    console.log(`\n--- ${period.period} (${students.length} students) ---`);

    for (const student of students) {
      if (!student.comment) continue;

      // TODO: Navigate to student's grade cell
      // TODO: Find comment textarea
      // TODO: Paste comment
      // TODO: Save

      console.log(`  ${student.student_name}: ${student.comment.substring(0, 50)}...`);
    }
  }

  await context.close();
  console.log('\nDone.');
}

const args = process.argv.slice(2);
if (args.includes('--setup')) {
  setup().catch(console.error);
} else {
  pasteComments().catch(console.error);
}
```

### File: `~/.openclaw/skills/graider/outlook-emails.js` (CREATE)

```javascript
/**
 * Outlook Email Automation
 *
 * Reads email payloads from ~/.graider_exports/outlook/emails_*.json
 * For each email: creates new message, fills To/CC/Subject/Body, sends.
 *
 * Usage:
 *   node outlook-emails.js --setup              # Save login session
 *   node outlook-emails.js                       # Send all emails
 *   node outlook-emails.js --draft               # Create drafts only
 *   node outlook-emails.js --file emails_X.json  # Specific file
 *
 * NOTE: Selectors are placeholders — update after first manual run.
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const EXPORTS_DIR = path.join(process.env.HOME, '.graider_exports', 'outlook');
const SESSION_DIR = path.join(
  process.env.HOME, '.openclaw', 'skills', 'graider', '.browser-state'
);

const OUTLOOK_URL = 'https://outlook.office.com/mail/';

async function setup() {
  console.log('Opening browser for Outlook login...');
  const context = await chromium.launchPersistentContext(SESSION_DIR, {
    headless: false,
  });
  const page = await context.newPage();
  await page.goto(OUTLOOK_URL);
  await new Promise((resolve) => context.on('close', resolve));
  console.log('Session saved.');
}

async function sendEmails(draftOnly, specificFile) {
  // Find email file
  let emailFile;
  if (specificFile) {
    emailFile = path.join(EXPORTS_DIR, specificFile);
  } else {
    // Use most recent
    const files = fs.readdirSync(EXPORTS_DIR)
      .filter((f) => f.startsWith('emails_') && f.endsWith('.json'))
      .sort()
      .reverse();
    if (files.length === 0) {
      console.error('No email files found in', EXPORTS_DIR);
      process.exit(1);
    }
    emailFile = path.join(EXPORTS_DIR, files[0]);
  }

  const data = JSON.parse(fs.readFileSync(emailFile, 'utf-8'));
  console.log(`${draftOnly ? 'Drafting' : 'Sending'} ${data.count} emails for: ${data.assignment}`);

  if (data.no_contact && data.no_contact.length > 0) {
    console.log(`\nStudents without parent email (${data.no_contact.length}):`);
    data.no_contact.forEach((name) => console.log(`  - ${name}`));
  }

  const context = await chromium.launchPersistentContext(SESSION_DIR, {
    headless: false,
  });
  const page = await context.newPage();
  await page.goto(OUTLOOK_URL);
  await page.waitForLoadState('networkidle');

  for (let i = 0; i < data.emails.length; i++) {
    const email = data.emails[i];
    console.log(`\n[${i + 1}/${data.emails.length}] ${email.student_name} → ${email.to}`);

    // TODO: Click New Message
    // await page.click('[aria-label="New mail"]');
    // await page.waitForTimeout(1000);

    // TODO: Fill To field
    // await page.fill('[aria-label="To"]', email.to);

    // TODO: Fill CC if present
    // if (email.cc) {
    //   await page.click('[aria-label="Show CC"]');  // expand CC
    //   await page.fill('[aria-label="CC"]', email.cc);
    // }

    // TODO: Fill Subject
    // await page.fill('[aria-label="Add a subject"]', email.subject);

    // TODO: Fill Body
    // await page.click('[aria-label="Message body"]');
    // await page.keyboard.type(email.body);

    // TODO: Send or save draft
    // if (!draftOnly) {
    //   await page.click('[aria-label="Send"]');
    // } else {
    //   await page.keyboard.press('Escape');  // saves as draft
    // }

    // await page.waitForTimeout(2000);
    console.log(`  Subject: ${email.subject}`);
  }

  await context.close();
  console.log('\nDone.');
}

const args = process.argv.slice(2);
if (args.includes('--setup')) {
  setup().catch(console.error);
} else {
  const draftOnly = args.includes('--draft');
  const fileIdx = args.indexOf('--file');
  const specificFile = fileIdx >= 0 ? args[fileIdx + 1] : null;
  sendEmails(draftOnly, specificFile).catch(console.error);
}
```

---

## Verification Checklist

After implementation:

1. **Parent Contacts Import**: Settings > Classroom > upload `class_list (1).xlsx` → expect 7 periods, ~152 students, counts displayed
2. **GET /api/parent-contacts**: Returns JSON with per-period stats
3. **Batch Focus Export**: Results tab > "Batch Focus" button → check `~/.graider_exports/focus/` for per-period CSVs
4. **CSV Format**: Each file has header `Student ID,Score` (with space), 7-digit IDs
5. **Comments Export**: Called alongside batch → check `comments_manifest.json`
6. **Parent Emails Export**: Results tab > "Parent Emails" button → check `~/.graider_exports/outlook/emails_*.json`
7. **No Contact List**: Mikael Bailey should appear in `no_contact` (no parent email in class list)
8. **OpenClaw Skill**: `cat ~/.openclaw/skills/graider/SKILL.md` is readable
9. **Playwright Scripts**: All 3 files exist and have valid JS syntax
10. **No regressions**: Existing Focus Export modal still works

---

## Risk Notes

- **Student ID mapping**: The class list has 9-digit IDs (`193255006`) where last 2 = grade. We strip last 2 to get 7-digit roster IDs (`1932550`). This assumes all IDs follow this pattern. If some schools use different formats, the stripping logic may need adjustment.
- **Mixed contact columns**: Some cells have emails where phones are expected and vice versa. The `@` detection handles this, but very unusual formats (e.g., phone numbers containing `@`) could mismatch.
- **Playwright selectors**: All scripts have `TODO` placeholder selectors. These must be filled in during the first manual run against the actual Focus and Outlook interfaces.
- **File size**: `email_routes.py` grows from 172 to ~310 lines. `settings_routes.py` grows from 818 to ~990 lines. `grading_routes.py` grows from 810 to ~920 lines. All within the 500-line-per-file guideline concern but the routes files are already above that threshold.
