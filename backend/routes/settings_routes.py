"""
Settings-related API routes for Graider.
Handles rubric configuration, global settings, and file uploads.
"""
import os
import json
import csv
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

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
    """List all uploaded period files."""
    periods = []
    for f in os.listdir(PERIODS_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(PERIODS_DIR, f), 'r') as mf:
                    metadata = json.load(mf)
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
