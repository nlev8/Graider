"""
Settings-related API routes for Graider.
Handles rubric configuration, global settings, file uploads, and accommodations.
"""
import os
import json
import csv
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

# Import accommodation module
try:
    from backend.accommodations import (
        load_presets, save_preset, delete_preset,
        load_student_accommodations, set_student_accommodation,
        get_student_accommodation, remove_student_accommodation,
        import_accommodations_from_csv, clear_all_accommodations,
        get_accommodation_stats, export_student_accommodations,
        audit_log_accommodation
    )
except ImportError:
    from accommodations import (
        load_presets, save_preset, delete_preset,
        load_student_accommodations, set_student_accommodation,
        get_student_accommodation, remove_student_accommodation,
        import_accommodations_from_csv, clear_all_accommodations,
        get_accommodation_stats, export_student_accommodations,
        audit_log_accommodation
    )

settings_bp = Blueprint('settings', __name__)

# Data directories
GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
ROSTERS_DIR = os.path.join(GRAIDER_DATA_DIR, "rosters")
PERIODS_DIR = os.path.join(GRAIDER_DATA_DIR, "periods")
DOCUMENTS_DIR = os.path.join(GRAIDER_DATA_DIR, "documents")

# Ensure directories exist
for dir_path in [GRAIDER_DATA_DIR, ROSTERS_DIR, PERIODS_DIR, DOCUMENTS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

ALLOWED_CSV_EXTENSIONS = {'csv', 'xlsx', 'xls'}
ALLOWED_DOC_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt', 'md'}


def parse_student_name(name):
    """Parse various student name formats and return (first, last)."""
    if not name:
        return '', ''

    name = name.strip()

    # Format: "Last; First Middle" (semicolon separator)
    if ';' in name:
        parts = name.split(';', 1)
        last = parts[0].strip()
        first_middle = parts[1].strip() if len(parts) > 1 else ''
        first = first_middle.split()[0] if first_middle else ''
        return first, last

    # Format: "Last, First Middle" (comma separator)
    if ',' in name:
        parts = name.split(',', 1)
        last = parts[0].strip()
        first_middle = parts[1].strip() if len(parts) > 1 else ''
        first = first_middle.split()[0] if first_middle else ''
        return first, last

    # Format: "First Last" or "First Middle Last" (space separated)
    parts = name.split()
    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        return first, last
    elif len(parts) == 1:
        return parts[0], ''

    return '', ''


def get_students_from_period_file(filepath):
    """Extract student list from a period CSV/Excel file."""
    import pandas as pd

    students = []
    try:
        if filepath.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
            name_cols = [c for c in df.columns if any(x in c.lower() for x in ['name', 'student', 'first', 'last'])]
            if name_cols:
                first_col = next((c for c in name_cols if 'first' in c.lower()), None)
                last_col = next((c for c in name_cols if 'last' in c.lower()), None)
                if first_col and last_col:
                    for _, row in df.iterrows():
                        first = str(row[first_col]).strip() if pd.notna(row[first_col]) else ''
                        last = str(row[last_col]).strip() if pd.notna(row[last_col]) else ''
                        if first or last:
                            students.append({"first": first, "last": last, "full": f"{first} {last}".strip()})
                else:
                    name_col = name_cols[0]
                    for _, row in df.iterrows():
                        name = str(row[name_col]).strip() if pd.notna(row[name_col]) else ''
                        if name:
                            first, last = parse_student_name(name)
                            students.append({"first": first, "last": last, "full": name})
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                first_col = next((h for h in reader.fieldnames if 'first' in h.lower()), None)
                last_col = next((h for h in reader.fieldnames if 'last' in h.lower()), None)
                name_col = next((h for h in reader.fieldnames if any(x in h.lower() for x in ['name', 'student'])), None)

                for row in reader:
                    if first_col and last_col:
                        first = row.get(first_col, '').strip()
                        last = row.get(last_col, '').strip()
                        if first or last:
                            students.append({"first": first, "last": last, "full": f"{first} {last}".strip()})
                    elif name_col:
                        name = row.get(name_col, '').strip()
                        if name:
                            first, last = parse_student_name(name)
                            students.append({"first": first, "last": last, "full": name})
    except Exception:
        pass

    return students


@settings_bp.route('/api/save-rubric', methods=['POST'])
def save_rubric():
    """Save rubric configuration to JSON file."""
    data = request.json
    rubric_path = os.path.expanduser("~/.graider_rubric.json")

    try:
        with open(rubric_path, 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)})


@settings_bp.route('/api/load-rubric')
def load_rubric():
    """Load rubric configuration from JSON file."""
    rubric_path = os.path.expanduser("~/.graider_rubric.json")

    if not os.path.exists(rubric_path):
        return jsonify({"rubric": None})

    try:
        with open(rubric_path, 'r') as f:
            data = json.load(f)
        return jsonify({"rubric": data})
    except Exception as e:
        return jsonify({"error": str(e)})


@settings_bp.route('/api/save-global-settings', methods=['POST'])
def save_global_settings():
    """Save global AI notes and settings."""
    data = request.json
    settings_path = os.path.expanduser("~/.graider_settings.json")

    try:
        with open(settings_path, 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)})


@settings_bp.route('/api/load-global-settings')
def load_global_settings():
    """Load global AI notes and settings."""
    settings_path = os.path.expanduser("~/.graider_settings.json")

    if not os.path.exists(settings_path):
        return jsonify({"settings": None})

    try:
        with open(settings_path, 'r') as f:
            data = json.load(f)
        return jsonify({"settings": data})
    except Exception as e:
        return jsonify({"error": str(e)})


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def parse_csv_headers(filepath):
    """Parse CSV and detect column mappings."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader, [])
            # Count rows
            row_count = sum(1 for _ in reader)
        return {'headers': headers, 'row_count': row_count}
    except Exception as e:
        return {'error': str(e)}


@settings_bp.route('/api/upload-roster', methods=['POST'])
def upload_roster():
    """Upload and process a roster CSV file."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename, ALLOWED_CSV_EXTENSIONS):
        return jsonify({"error": "Invalid file type. Use CSV, XLS, or XLSX"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(ROSTERS_DIR, filename)
    file.save(filepath)

    # Parse and analyze the CSV
    result = parse_csv_headers(filepath)
    if 'error' in result:
        return jsonify({"error": result['error']}), 400

    # Save roster metadata
    metadata = {
        'filename': filename,
        'filepath': filepath,
        'headers': result['headers'],
        'row_count': result['row_count'],
        'column_mapping': {}  # Will be set by frontend
    }

    metadata_path = os.path.join(ROSTERS_DIR, f"{filename}.meta.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return jsonify({
        "status": "uploaded",
        "filename": filename,
        "headers": result['headers'],
        "row_count": result['row_count']
    })


@settings_bp.route('/api/save-roster-mapping', methods=['POST'])
def save_roster_mapping():
    """Save column mapping for a roster file."""
    data = request.json
    filename = data.get('filename')
    mapping = data.get('mapping', {})

    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    metadata_path = os.path.join(ROSTERS_DIR, f"{filename}.meta.json")
    if not os.path.exists(metadata_path):
        return jsonify({"error": "Roster metadata not found"}), 404

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    metadata['column_mapping'] = mapping
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return jsonify({"status": "saved"})


@settings_bp.route('/api/list-rosters')
def list_rosters():
    """List all uploaded roster files."""
    rosters = []
    for f in os.listdir(ROSTERS_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(ROSTERS_DIR, f), 'r') as mf:
                    metadata = json.load(mf)
                    rosters.append(metadata)
            except:
                pass
    return jsonify({"rosters": rosters})


@settings_bp.route('/api/delete-roster', methods=['POST'])
def delete_roster():
    """Delete a roster file."""
    data = request.json
    filename = data.get('filename')

    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    filepath = os.path.join(ROSTERS_DIR, secure_filename(filename))
    metadata_path = os.path.join(ROSTERS_DIR, f"{secure_filename(filename)}.meta.json")

    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/api/upload-period', methods=['POST'])
def upload_period():
    """Upload a period/class CSV file."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    period_name = request.form.get('period_name', 'Period')

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename, ALLOWED_CSV_EXTENSIONS):
        return jsonify({"error": "Invalid file type. Use CSV, XLS, or XLSX"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(PERIODS_DIR, filename)
    file.save(filepath)

    result = parse_csv_headers(filepath)
    if 'error' in result:
        return jsonify({"error": result['error']}), 400

    metadata = {
        'filename': filename,
        'filepath': filepath,
        'period_name': period_name,
        'headers': result['headers'],
        'row_count': result['row_count'],
        'column_mapping': {}
    }

    metadata_path = os.path.join(PERIODS_DIR, f"{filename}.meta.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return jsonify({
        "status": "uploaded",
        "filename": filename,
        "period_name": period_name,
        "headers": result['headers'],
        "row_count": result['row_count']
    })


@settings_bp.route('/api/list-periods')
def list_periods():
    """List all uploaded period files with their students."""
    periods = []
    for f in os.listdir(PERIODS_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(PERIODS_DIR, f), 'r') as mf:
                    metadata = json.load(mf)
                    # Load students for this period
                    period_file = os.path.join(PERIODS_DIR, metadata.get('filename', ''))
                    if os.path.exists(period_file):
                        metadata['students'] = get_students_from_period_file(period_file)
                    else:
                        metadata['students'] = []
                    periods.append(metadata)
            except:
                pass
    return jsonify({"periods": periods})


@settings_bp.route('/api/delete-period', methods=['POST'])
def delete_period():
    """Delete a period file."""
    data = request.json
    filename = data.get('filename')

    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    filepath = os.path.join(PERIODS_DIR, secure_filename(filename))
    metadata_path = os.path.join(PERIODS_DIR, f"{secure_filename(filename)}.meta.json")

    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/api/get-period-students', methods=['POST'])
def get_period_students():
    """Get student names from a period CSV file."""
    data = request.json
    filename = data.get('filename')

    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    filepath = os.path.join(PERIODS_DIR, secure_filename(filename))

    if not os.path.exists(filepath):
        return jsonify({"error": "Period file not found"}), 404

    try:
        students = get_students_from_period_file(filepath)
        return jsonify({"students": students, "count": len(students)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/api/upload-document', methods=['POST'])
def upload_document():
    """Upload a supporting document for lesson planning/grading."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    doc_type = request.form.get('doc_type', 'general')  # 'curriculum', 'rubric', 'standards', 'general'
    description = request.form.get('description', '')

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename, ALLOWED_DOC_EXTENSIONS):
        return jsonify({"error": "Invalid file type. Use PDF, DOCX, DOC, TXT, or MD"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    file.save(filepath)

    metadata = {
        'filename': filename,
        'filepath': filepath,
        'doc_type': doc_type,
        'description': description,
        'size': os.path.getsize(filepath)
    }

    metadata_path = os.path.join(DOCUMENTS_DIR, f"{filename}.meta.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return jsonify({
        "status": "uploaded",
        "filename": filename,
        "doc_type": doc_type
    })


@settings_bp.route('/api/list-documents')
def list_documents():
    """List all uploaded supporting documents."""
    documents = []
    for f in os.listdir(DOCUMENTS_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(DOCUMENTS_DIR, f), 'r') as mf:
                    metadata = json.load(mf)
                    documents.append(metadata)
            except:
                pass
    return jsonify({"documents": documents})


@settings_bp.route('/api/delete-document', methods=['POST'])
def delete_document():
    """Delete a supporting document."""
    data = request.json
    filename = data.get('filename')

    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    filepath = os.path.join(DOCUMENTS_DIR, secure_filename(filename))
    metadata_path = os.path.join(DOCUMENTS_DIR, f"{secure_filename(filename)}.meta.json")

    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# ACCOMMODATION MANAGEMENT (FERPA COMPLIANT)
# ══════════════════════════════════════════════════════════════
#
# FERPA Compliance Notes:
# - All accommodation data stored locally only (~/.graider_data/accommodations/)
# - Student IDs are never sent to AI - only accommodation TYPE
# - All access is audit logged
# - Data can be exported/deleted per FERPA requirements
# ══════════════════════════════════════════════════════════════

@settings_bp.route('/api/accommodation-presets')
def get_accommodation_presets():
    """Get all available accommodation presets (default + custom)."""
    presets = load_presets()
    return jsonify({"presets": list(presets.values())})


@settings_bp.route('/api/accommodation-presets', methods=['POST'])
def create_accommodation_preset():
    """Create or update a custom accommodation preset."""
    data = request.json
    if not data.get('name') or not data.get('ai_instructions'):
        return jsonify({"error": "Name and AI instructions required"}), 400

    if save_preset(data):
        return jsonify({"status": "saved", "preset": data})
    else:
        return jsonify({"error": "Failed to save preset"}), 500


@settings_bp.route('/api/accommodation-presets/<preset_id>', methods=['DELETE'])
def delete_accommodation_preset(preset_id):
    """Delete a custom accommodation preset."""
    if delete_preset(preset_id):
        return jsonify({"status": "deleted"})
    else:
        return jsonify({"error": "Cannot delete default presets or preset not found"}), 400


@settings_bp.route('/api/student-accommodations')
def get_all_student_accommodations():
    """
    Get all student accommodation mappings.
    FERPA: Returns student IDs with their accommodation settings.
    Data is stored and displayed locally only.
    """
    mappings = load_student_accommodations()
    presets = load_presets()

    # Enrich with preset details for display
    enriched = {}
    for student_id, data in mappings.items():
        preset_details = []
        for preset_id in data.get("presets", []):
            if preset_id in presets:
                preset_details.append({
                    "id": preset_id,
                    "name": presets[preset_id].get("name", preset_id),
                    "icon": presets[preset_id].get("icon", "FileText")
                })

        enriched[student_id] = {
            "presets": preset_details,
            "custom_notes": data.get("custom_notes", ""),
            "updated": data.get("updated", "")
        }

    return jsonify({"accommodations": enriched, "count": len(enriched)})


@settings_bp.route('/api/student-accommodations/<student_id>', methods=['GET'])
def get_single_student_accommodation(student_id):
    """Get accommodation settings for a specific student."""
    accommodation = get_student_accommodation(student_id)
    if accommodation:
        return jsonify({"accommodation": accommodation})
    else:
        return jsonify({"accommodation": None})


@settings_bp.route('/api/student-accommodations/<student_id>', methods=['POST'])
def set_single_student_accommodation(student_id):
    """Set accommodation presets for a student."""
    data = request.json
    preset_ids = data.get('presets', [])
    custom_notes = data.get('custom_notes', '')

    if set_student_accommodation(student_id, preset_ids, custom_notes):
        audit_log_accommodation("API_SET", f"Set accommodation for {student_id[:6]}...")
        return jsonify({"status": "saved"})
    else:
        return jsonify({"error": "Failed to save accommodation"}), 500


@settings_bp.route('/api/student-accommodations/<student_id>', methods=['DELETE'])
def delete_student_accommodation(student_id):
    """Remove accommodation settings for a student."""
    if remove_student_accommodation(student_id):
        return jsonify({"status": "deleted"})
    else:
        return jsonify({"error": "Student not found or deletion failed"}), 404


@settings_bp.route('/api/import-accommodations', methods=['POST'])
def import_accommodations():
    """
    Import accommodations from CSV file.
    Expected columns: student_id, accommodation_type, accommodation_notes (optional)
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    id_col = request.form.get('id_column', 'student_id')
    accommodation_col = request.form.get('accommodation_column', 'accommodation_type')
    notes_col = request.form.get('notes_column', 'accommodation_notes')

    try:
        # Parse CSV
        content = file.read().decode('utf-8')
        reader = csv.DictReader(content.splitlines())
        csv_data = list(reader)

        result = import_accommodations_from_csv(csv_data, id_col, accommodation_col, notes_col)

        return jsonify({
            "status": "imported",
            "imported": result["imported"],
            "skipped": result["skipped"],
            "total": result["total"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/api/export-accommodations')
def export_accommodations():
    """
    Export all accommodation data for backup.
    FERPA: Supports data portability requirements.
    """
    data = export_student_accommodations()
    return jsonify({
        "accommodations": data,
        "exported_at": __import__('datetime').datetime.now().isoformat()
    })


@settings_bp.route('/api/clear-accommodations', methods=['POST'])
def clear_accommodations():
    """
    Delete all student accommodation data.
    FERPA: Supports data deletion requirements.
    """
    if clear_all_accommodations():
        return jsonify({"status": "cleared"})
    else:
        return jsonify({"error": "Failed to clear accommodations"}), 500


@settings_bp.route('/api/accommodation-stats')
def accommodation_stats():
    """Get statistics about accommodation usage."""
    stats = get_accommodation_stats()
    return jsonify(stats)


# ============ API Keys Management ============

API_KEYS_FILE = os.path.join(GRAIDER_DATA_DIR, ".api_keys.json")


def load_api_keys():
    """Load API keys from secure storage."""
    if os.path.exists(API_KEYS_FILE):
        try:
            with open(API_KEYS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_api_keys_to_file(keys):
    """Save API keys to secure storage."""
    # Set restrictive permissions on the file
    with open(API_KEYS_FILE, 'w') as f:
        json.dump(keys, f)
    os.chmod(API_KEYS_FILE, 0o600)  # Owner read/write only


@settings_bp.route('/api/save-api-keys', methods=['POST'])
def save_api_keys():
    """Save API keys securely."""
    data = request.json
    openai_key = data.get('openai_key')
    anthropic_key = data.get('anthropic_key')

    # Load existing keys
    keys = load_api_keys()

    # Update keys if provided
    if openai_key:
        keys['openai'] = openai_key
    if anthropic_key:
        keys['anthropic'] = anthropic_key

    # Save to file
    save_api_keys_to_file(keys)

    # Also update .env file for immediate use
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    env_lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_lines = f.readlines()

    # Update or add keys in .env
    openai_found = False
    anthropic_found = False
    new_lines = []
    for line in env_lines:
        if line.startswith('OPENAI_API_KEY=') and openai_key:
            new_lines.append(f'OPENAI_API_KEY={openai_key}\n')
            openai_found = True
        elif line.startswith('ANTHROPIC_API_KEY=') and anthropic_key:
            new_lines.append(f'ANTHROPIC_API_KEY={anthropic_key}\n')
            anthropic_found = True
        else:
            new_lines.append(line)

    if openai_key and not openai_found:
        new_lines.append(f'OPENAI_API_KEY={openai_key}\n')
    if anthropic_key and not anthropic_found:
        new_lines.append(f'ANTHROPIC_API_KEY={anthropic_key}\n')

    with open(env_path, 'w') as f:
        f.writelines(new_lines)

    return jsonify({
        "status": "success",
        "openai_configured": bool(keys.get('openai')),
        "anthropic_configured": bool(keys.get('anthropic'))
    })


@settings_bp.route('/api/check-api-keys')
def check_api_keys():
    """Check which API keys are configured (without exposing the keys)."""
    keys = load_api_keys()

    # Also check .env file
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    openai_in_env = False
    anthropic_in_env = False

    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            content = f.read()
            openai_in_env = 'OPENAI_API_KEY=' in content and 'your-key-here' not in content
            anthropic_in_env = 'ANTHROPIC_API_KEY=' in content

    return jsonify({
        "openai_configured": bool(keys.get('openai')) or openai_in_env,
        "anthropic_configured": bool(keys.get('anthropic')) or anthropic_in_env
    })
