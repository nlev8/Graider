# Graider FERPA Implementation

## Overview

This document details the technical implementation of FERPA (Family Educational Rights and Privacy Act) compliance features in Graider.

---

## 1. PII Sanitization

### Location
`assignment_grader.py` - `sanitize_pii_for_ai()` function

### What Gets Removed

Before any student work is sent to OpenAI's API, the following personally identifiable information (PII) is automatically stripped:

| PII Type | Pattern | Replacement |
|----------|---------|-------------|
| Student Names | First, last, full name | `[STUDENT]` |
| Social Security Numbers | XXX-XX-XXXX | `[SSN-REMOVED]` |
| Student IDs | 7-10 digit numbers | `[ID-REMOVED]` |
| Email Addresses | user@domain.com | `[EMAIL-REMOVED]` |
| Phone Numbers | Various formats | `[PHONE-REMOVED]` |
| Birthdates | MM/DD/YYYY (recent years) | `[DATE-REMOVED]` |
| Street Addresses | Number + street name | `[ADDRESS-REMOVED]` |
| Zip Codes | 5 or 9 digit | `[ZIP-REMOVED]` |

### Code Example

```python
def sanitize_pii_for_ai(student_name: str, content: str) -> tuple:
    """
    FERPA Compliance: Remove all PII before sending to external AI services.
    Returns: (anonymous_id, sanitized_content)
    """
    # Creates consistent anonymous ID from student name hash
    anon_id = f"Student_{hash_val:04d}"

    # Applies all PII removal patterns
    sanitized = content
    sanitized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN-REMOVED]', sanitized)
    # ... additional patterns

    return anon_id, sanitized
```

### Historical Date Preservation

The system preserves historical dates (years before 1980) that are likely part of the assignment content, while removing recent dates that might be birthdates.

---

## 2. Audit Logging

### Location
`backend/app.py` - `audit_log()` function

### Log File
`~/.graider_audit.log`

### What Gets Logged

| Action | Details Logged |
|--------|---------------|
| `START_GRADING` | Subject, grade level |
| `DELETE_RESULT` | Filename (truncated) |
| `DELETE_ALL_DATA` | Items deleted |
| `VIEW_DATA_SUMMARY` | Access timestamp |
| `EXPORT_STUDENT_DATA` | Record count |
| `EXPORT_ALL_DATA` | Record count |

### Log Format

```
2026-01-26T14:30:45.123456 | teacher | START_GRADING | Started grading session for US History grade 8
2026-01-26T14:35:12.789012 | teacher | DELETE_RESULT | Deleted result for file: John_Doe_Assignment1...
```

### Privacy Note

Audit logs do NOT contain actual student data - only action types, timestamps, and anonymized metadata.

---

## 3. Data Management API

### Endpoints

#### GET `/api/ferpa/data-summary`
Returns summary of all stored data:
```json
{
  "results": { "count": 45, "file": "~/.graider_results.json", "exists": true },
  "settings": { "file": "~/.graider_settings.json", "exists": true },
  "audit_log": { "file": "~/.graider_audit.log", "exists": true },
  "data_locations": [...],
  "ferpa_notes": {
    "pii_handling": "Student names are sanitized before AI processing",
    "data_storage": "All data stored locally on teacher's computer",
    "ai_training": "OpenAI API does not train on API-submitted data"
  }
}
```

#### GET `/api/ferpa/audit-log`
Returns recent audit log entries:
```json
{
  "logs": [
    { "timestamp": "2026-01-26T14:30:45", "user": "teacher", "action": "START_GRADING", "details": "..." }
  ],
  "total": 25
}
```

#### GET `/api/ferpa/export-data`
Exports all student data for portability requests:
```json
{
  "export_date": "2026-01-26T14:30:45",
  "record_count": 45,
  "data": [...]
}
```

Optional query parameter: `?student=John%20Doe` to export specific student's data.

#### POST `/api/ferpa/delete-all-data`
Securely deletes all student data:
```json
// Request
{ "confirm": true, "include_settings": false }

// Response
{
  "status": "success",
  "message": "All student data has been securely deleted",
  "deleted": ["Grading results (45 records)"],
  "timestamp": "2026-01-26T14:30:45"
}
```

---

## 4. User Interface

### Settings > Privacy & Data (FERPA)

The Settings tab includes a FERPA compliance section with:

1. **Privacy Features Display**
   - PII Sanitization status
   - Local Storage Only confirmation
   - No AI Training notice
   - Audit Logging status

2. **Data Management Buttons**
   - **View Data Summary**: Shows what data is stored and where
   - **Export All Data**: Downloads JSON file of all records
   - **Delete All Data**: Securely removes all student data (requires confirmation)

### Delete Confirmation

The Delete All Data function requires:
1. Initial confirmation dialog explaining what will be deleted
2. Text input requiring user to type "DELETE"
3. Final API confirmation

---

## 5. Data Storage Locations

| Data Type | Location | Contains PII |
|-----------|----------|--------------|
| Grading Results | `~/.graider_results.json` | Yes (student names, grades) |
| App Settings | `~/.graider_settings.json` | No |
| Audit Log | `~/.graider_audit.log` | No |
| Assignment Configs | `~/.graider_assignments/` | No |
| Exported Grades | Output Folder (user-configured) | Yes |

---

## 6. OpenAI API Compliance

### Data Not Used for Training

Per OpenAI's API Terms of Service:
> "We do not use data submitted via the API to train our models"

This is documented in the Privacy & Data section and in the data summary API response.

### What Goes to OpenAI

Only sanitized content is sent:
- Assignment instructions (no student names)
- Student work with all PII removed
- Grading criteria

### What Never Goes to OpenAI

- Student names (replaced with `[STUDENT]`)
- Email addresses
- Student IDs
- Any other PII

---

## 7. Compliance Checklist

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| PII Sanitization | `sanitize_pii_for_ai()` | ✅ |
| Audit Logging | `audit_log()`, `~/.graider_audit.log` | ✅ |
| Data Deletion | `/api/ferpa/delete-all-data` | ✅ |
| Data Export | `/api/ferpa/export-data` | ✅ |
| Data Summary | `/api/ferpa/data-summary` | ✅ |
| UI Controls | Settings > Privacy & Data | ✅ |
| No Cloud Storage | All data local | ✅ |
| No AI Training | OpenAI API policy | ✅ |

---

## 8. For IT Administrators

### Security Summary

- All student data stored locally on teacher's computer
- HTTPS encryption for AI API calls
- PII stripped before external transmission
- Complete data deletion available on demand
- Audit trail maintained for compliance

### Data Locations for Backup/Deletion

```bash
# All Graider data files
~/.graider_results.json      # Grading results
~/.graider_settings.json     # App settings
~/.graider_audit.log         # Audit trail
~/.graider_assignments/      # Saved assignment configs
~/.graider_email.json        # Email configuration
~/.graider_rubric.json       # Rubric settings
```

### Complete Data Removal

To completely remove all Graider data:
```bash
rm -rf ~/.graider_*
```

---

## 9. Future Enhancements

- [ ] Encryption at rest for stored data
- [ ] Automatic data retention policies (e.g., delete after 30 days)
- [ ] Per-student data export in UI
- [ ] Audit log viewer in UI

---

*Implementation Date: January 2026*
*Last Updated: January 26, 2026*
