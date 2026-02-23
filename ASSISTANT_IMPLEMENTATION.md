# Graider Assistant — Precise Code Edits

## Summary

4 new files, 4 modified files. AI chat assistant with SSE streaming, Anthropic tool use, data querying, Focus SIS automation, and VPortal credentials management.

---

## New File 1: `backend/services/assistant_tools.py`

```python
"""
Graider Assistant — Tool Execution Service
==========================================

Implements tool functions that the AI assistant can call to query
local grading data, analytics, and trigger Focus SIS automation.
All data operations are local — no student PII leaves the machine
through these tools.
"""

import os
import json
import csv
import glob
import subprocess
import shutil
import base64
from statistics import mean, median, stdev
from collections import defaultdict

GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
RESULTS_FILE = os.path.expanduser("~/.graider_results.json")
ASSIGNMENTS_DIR = os.path.expanduser("~/.graider_assignments")
MASTER_GRADES_CSV = os.path.join(os.path.expanduser("~/Downloads/Graider"), "Results", "master_grades.csv")
PERIODS_DIR = os.path.join(GRAIDER_DATA_DIR, "periods")
STUDENT_HISTORY_DIR = os.path.join(GRAIDER_DATA_DIR, "student_history")
FOCUS_EXPORTS_DIR = os.path.expanduser("~/.graider_exports/focus")
CREDS_FILE = os.path.join(GRAIDER_DATA_DIR, "portal_credentials.json")

# Ensure export directory exists
os.makedirs(FOCUS_EXPORTS_DIR, exist_ok=True)


def _load_results():
    """Load saved grading results from JSON file."""
    if not os.path.exists(RESULTS_FILE):
        return []
    try:
        with open(RESULTS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []


def _load_master_grades():
    """Load master_grades.csv into list of dicts."""
    if not os.path.exists(MASTER_GRADES_CSV):
        return []
    rows = []
    try:
        with open(MASTER_GRADES_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        pass
    return rows


def _load_period_students(class_period):
    """Load student list for a specific class period from period CSVs."""
    students = {}
    if not os.path.isdir(PERIODS_DIR):
        return students
    for csvfile in glob.glob(os.path.join(PERIODS_DIR, "*.csv")):
        period_name = os.path.basename(csvfile).replace('.csv', '')
        if class_period and class_period.lower() not in period_name.lower():
            continue
        try:
            with open(csvfile, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sid = row.get('Student ID', '')
                    name = row.get('Student', '')
                    students[sid] = {'name': name, 'period': period_name}
        except Exception:
            continue
    return students


# ══════════════════════════════════════════════════════════════
# TOOL 1: query_grades
# ══════════════════════════════════════════════════════════════

def query_grades(student_name=None, assignment=None, period=None,
                 min_score=None, max_score=None, letter_grade=None, limit=20):
    """Search and filter grading results."""
    results = _load_results()
    filtered = []

    for r in results:
        # Apply filters
        if student_name:
            if student_name.lower() not in r.get('student_name', '').lower():
                continue
        if assignment:
            if assignment.lower() not in r.get('assignment', '').lower():
                continue
        if period:
            if period.lower() not in r.get('period', '').lower():
                continue
        if min_score is not None:
            if (r.get('score') or 0) < min_score:
                continue
        if max_score is not None:
            if (r.get('score') or 0) > max_score:
                continue
        if letter_grade:
            if r.get('letter_grade', '').upper() != letter_grade.upper():
                continue

        filtered.append({
            'student_name': r.get('student_name', ''),
            'student_id': r.get('student_id', ''),
            'assignment': r.get('assignment', ''),
            'period': r.get('period', ''),
            'score': r.get('score', 0),
            'letter_grade': r.get('letter_grade', ''),
            'feedback': (r.get('feedback', '') or '')[:200],
            'graded_at': r.get('graded_at', ''),
        })

    # Sort by most recent first
    filtered.sort(key=lambda x: x.get('graded_at', ''), reverse=True)

    total = len(filtered)
    filtered = filtered[:limit]

    return {
        'total_matches': total,
        'showing': len(filtered),
        'results': filtered,
    }


# ══════════════════════════════════════════════════════════════
# TOOL 2: get_student_summary
# ══════════════════════════════════════════════════════════════

def get_student_summary(student_name, student_id=None):
    """Get comprehensive summary for a specific student."""
    results = _load_results()

    # Find all results for this student
    student_results = []
    for r in results:
        name_match = student_name.lower() in r.get('student_name', '').lower()
        id_match = student_id and str(student_id) == str(r.get('student_id', ''))
        if name_match or id_match:
            student_results.append(r)

    if not student_results:
        return {'error': 'Student not found', 'student_name': student_name}

    scores = [r.get('score', 0) for r in student_results]
    avg_score = round(mean(scores), 1) if scores else 0

    # Determine trend
    trend = 'stable'
    if len(scores) >= 3:
        recent_avg = mean(scores[-3:])
        older_avg = mean(scores[:-3]) if len(scores) > 3 else scores[0]
        if recent_avg > older_avg + 5:
            trend = 'improving'
        elif recent_avg < older_avg - 5:
            trend = 'declining'

    # Category breakdown
    categories = defaultdict(list)
    for r in student_results:
        breakdown = r.get('breakdown', {})
        if isinstance(breakdown, dict):
            for cat, val in breakdown.items():
                if isinstance(val, (int, float)):
                    categories[cat].append(val)

    category_averages = {}
    for cat, vals in categories.items():
        category_averages[cat] = round(mean(vals), 1)

    # Skills
    strengths = set()
    weaknesses = set()
    for r in student_results:
        skills = r.get('skills_demonstrated', {})
        if isinstance(skills, dict):
            for s in skills.get('strengths', []):
                strengths.add(s[:80])
            for w in skills.get('areas_for_growth', skills.get('weaknesses', [])):
                weaknesses.add(w[:80])

    # AI detection flags
    ai_flags = []
    for r in student_results:
        ai = r.get('ai_detection', {})
        if isinstance(ai, dict) and ai.get('flag') not in ('none', None, ''):
            ai_flags.append({
                'assignment': r.get('assignment', ''),
                'flag': ai.get('flag', ''),
                'confidence': ai.get('confidence', 0),
            })

    return {
        'student_name': student_results[0].get('student_name', student_name),
        'student_id': student_results[0].get('student_id', ''),
        'total_assignments': len(student_results),
        'average_score': avg_score,
        'trend': trend,
        'highest_score': max(scores) if scores else 0,
        'lowest_score': min(scores) if scores else 0,
        'grades': [
            {
                'assignment': r.get('assignment', ''),
                'score': r.get('score', 0),
                'letter_grade': r.get('letter_grade', ''),
                'graded_at': r.get('graded_at', ''),
            }
            for r in student_results
        ],
        'category_averages': category_averages,
        'strengths': list(strengths)[:5],
        'areas_for_growth': list(weaknesses)[:5],
        'ai_detection_flags': ai_flags,
    }


# ══════════════════════════════════════════════════════════════
# TOOL 3: get_class_analytics
# ══════════════════════════════════════════════════════════════

def get_class_analytics(period=None, class_period=None):
    """Get class-wide analytics."""
    results = _load_results()

    if class_period:
        # Filter by class period
        period_students = _load_period_students(class_period)
        if period_students:
            period_ids = set(period_students.keys())
            results = [r for r in results if r.get('student_id', '') in period_ids]
        else:
            results = [r for r in results if class_period.lower() in r.get('period', '').lower()]

    if period:
        results = [r for r in results if period.lower() in r.get('period', '').lower()]

    if not results:
        return {'error': 'No results found for the specified filters'}

    scores = [r.get('score', 0) for r in results]
    avg = round(mean(scores), 1)

    # Grade distribution
    distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    for r in results:
        lg = (r.get('letter_grade', '') or '')[0:1].upper()
        if lg in distribution:
            distribution[lg] += 1

    # Per-student averages
    student_scores = defaultdict(list)
    for r in results:
        name = r.get('student_name', 'Unknown')
        student_scores[name].append(r.get('score', 0))

    student_averages = []
    for name, s in student_scores.items():
        student_averages.append({'name': name, 'average': round(mean(s), 1), 'count': len(s)})

    student_averages.sort(key=lambda x: x['average'], reverse=True)

    # Students needing attention (below 65 average)
    needs_attention = [s for s in student_averages if s['average'] < 65]

    return {
        'total_results': len(results),
        'unique_students': len(student_scores),
        'class_average': avg,
        'median_score': round(median(scores), 1),
        'highest_score': max(scores),
        'lowest_score': min(scores),
        'std_dev': round(stdev(scores), 1) if len(scores) > 1 else 0,
        'grade_distribution': distribution,
        'top_students': student_averages[:5],
        'needs_attention': needs_attention[:10],
    }


# ══════════════════════════════════════════════════════════════
# TOOL 4: get_assignment_stats
# ══════════════════════════════════════════════════════════════

def get_assignment_stats(assignment_name):
    """Get statistics for a specific assignment."""
    results = _load_results()

    # Filter by assignment (partial match)
    matched = [r for r in results if assignment_name.lower() in r.get('assignment', '').lower()]

    if not matched:
        return {'error': 'No results found for assignment: ' + assignment_name}

    scores = [r.get('score', 0) for r in matched]
    assignment_title = matched[0].get('assignment', assignment_name)

    # Grade distribution
    distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    for r in matched:
        lg = (r.get('letter_grade', '') or '')[0:1].upper()
        if lg in distribution:
            distribution[lg] += 1

    # Score ranges
    ranges = {'90-100': 0, '80-89': 0, '70-79': 0, '60-69': 0, 'Below 60': 0}
    for s in scores:
        if s >= 90:
            ranges['90-100'] += 1
        elif s >= 80:
            ranges['80-89'] += 1
        elif s >= 70:
            ranges['70-79'] += 1
        elif s >= 60:
            ranges['60-69'] += 1
        else:
            ranges['Below 60'] += 1

    return {
        'assignment': assignment_title,
        'total_graded': len(matched),
        'mean': round(mean(scores), 1),
        'median': round(median(scores), 1),
        'std_dev': round(stdev(scores), 1) if len(scores) > 1 else 0,
        'highest': max(scores),
        'lowest': min(scores),
        'grade_distribution': distribution,
        'score_ranges': ranges,
    }


# ══════════════════════════════════════════════════════════════
# TOOL 5: list_assignments
# ══════════════════════════════════════════════════════════════

def list_assignments():
    """List all graded assignments with summary stats."""
    results = _load_results()

    assignment_data = defaultdict(list)
    for r in results:
        name = r.get('assignment', 'Unknown')
        assignment_data[name].append(r.get('score', 0))

    assignments = []
    for name, scores in sorted(assignment_data.items()):
        assignments.append({
            'name': name,
            'count': len(scores),
            'average': round(mean(scores), 1),
            'highest': max(scores),
            'lowest': min(scores),
        })

    # Also check saved assignment configs
    saved_configs = []
    if os.path.isdir(ASSIGNMENTS_DIR):
        for f in os.listdir(ASSIGNMENTS_DIR):
            if f.endswith('.json'):
                saved_configs.append(f.replace('.json', ''))

    return {
        'graded_assignments': assignments,
        'saved_configs': saved_configs,
        'total_results': len(results),
    }


# ══════════════════════════════════════════════════════════════
# TOOL 6: create_focus_assignment
# ══════════════════════════════════════════════════════════════

def create_focus_assignment(name, category=None, points=None, date=None, description=None):
    """Launch Focus automation to create an assignment in the gradebook."""
    node_path = shutil.which('node')
    if not node_path:
        return {'status': 'error', 'message': 'Node.js not found. Install Node.js to use Focus automation.'}

    script_path = os.path.join(os.path.dirname(__file__), '..', '..', 'focus-automation.js')
    script_path = os.path.abspath(script_path)

    if not os.path.exists(script_path):
        return {'status': 'error', 'message': 'focus-automation.js not found at ' + script_path}

    # Check credentials
    if not os.path.exists(CREDS_FILE):
        return {'status': 'error', 'message': 'VPortal credentials not configured. Go to Settings > Tools to set them up.'}

    # Build command
    cmd = [node_path, script_path, 'assignment', '--name', name]
    if category:
        cmd.extend(['--category', category])
    if points:
        cmd.extend(['--points', str(points)])
    if date:
        cmd.extend(['--date', date])
    if description:
        cmd.extend(['--description', description])

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(script_path),
        )
        return {
            'status': 'launched',
            'message': 'Focus automation started for "' + name + '". A browser window will open — check your phone for 2FA approval.',
            'pid': process.pid,
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


# ══════════════════════════════════════════════════════════════
# TOOL 7: export_grades_csv
# ══════════════════════════════════════════════════════════════

def export_grades_csv(assignment=None, period=None):
    """Generate Focus-formatted CSV for grade import."""
    results = _load_results()

    if assignment:
        results = [r for r in results if assignment.lower() in r.get('assignment', '').lower()]
    if period:
        results = [r for r in results if period.lower() in r.get('period', '').lower()]

    if not results:
        return {'status': 'error', 'message': 'No results found for the specified filters.'}

    # Group by period
    by_period = defaultdict(list)
    for r in results:
        p = r.get('period', 'All')
        by_period[p].append(r)

    safe_name = ''.join(c if c.isalnum() or c in ' -_' else '' for c in (assignment or 'export')).strip().replace(' ', '_')

    files_created = []
    for p, items in by_period.items():
        safe_period = p.replace(' ', '_').replace('/', '-')
        filename = safe_name + '_' + safe_period + '.csv'
        filepath = os.path.join(FOCUS_EXPORTS_DIR, filename)

        lines = ['Student ID,Score']
        matched = 0
        unmatched = 0
        for r in items:
            sid = r.get('student_id', '')
            score = r.get('score', 0)
            if sid and sid != 'UNKNOWN':
                lines.append(str(sid) + ',' + str(score))
                matched += 1
            else:
                name = r.get('student_name', 'Unknown')
                lines.append('# ' + name + ',' + str(score))
                unmatched += 1

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        files_created.append({
            'period': p,
            'file': filepath,
            'matched': matched,
            'unmatched': unmatched,
        })

    return {
        'status': 'exported',
        'files': files_created,
        'total_students': sum(f['matched'] + f['unmatched'] for f in files_created),
        'export_dir': FOCUS_EXPORTS_DIR,
    }


# ══════════════════════════════════════════════════════════════
# TOOL DISPATCHER
# ══════════════════════════════════════════════════════════════

TOOL_MAP = {
    'query_grades': query_grades,
    'get_student_summary': get_student_summary,
    'get_class_analytics': get_class_analytics,
    'get_assignment_stats': get_assignment_stats,
    'list_assignments': list_assignments,
    'create_focus_assignment': create_focus_assignment,
    'export_grades_csv': export_grades_csv,
}


def execute_tool(tool_name, tool_input):
    """Execute a tool by name with the given input dict."""
    func = TOOL_MAP.get(tool_name)
    if not func:
        return {'error': 'Unknown tool: ' + tool_name}
    try:
        return func(**tool_input)
    except Exception as e:
        return {'error': 'Tool execution failed: ' + str(e)}


def summarize_result(result):
    """Create a brief summary of a tool result for display."""
    if isinstance(result, dict):
        if 'error' in result:
            return result['error']
        if 'class_average' in result:
            return 'Class average: ' + str(result['class_average']) + '% (' + str(result['unique_students']) + ' students)'
        if 'average_score' in result:
            return result.get('student_name', '') + ': ' + str(result['average_score']) + '% avg (' + str(result['total_assignments']) + ' assignments)'
        if 'total_matches' in result:
            return str(result['total_matches']) + ' results found'
        if 'graded_assignments' in result:
            return str(len(result['graded_assignments'])) + ' assignments, ' + str(result['total_results']) + ' total grades'
        if 'mean' in result:
            return result.get('assignment', '') + ': ' + str(result['mean']) + '% avg (' + str(result['total_graded']) + ' graded)'
        if 'status' in result:
            return result.get('message', result['status'])
    return str(result)[:100]
```

---

## New File 2: `backend/routes/assistant_routes.py`

```python
"""
Graider Assistant — Chat Endpoint
==================================

SSE-streaming chat endpoint using Anthropic Claude with tool use.
The assistant can query local grading data, analytics, and trigger
Focus SIS automation.
"""

import os
import json
import time
import uuid
import base64
import logging
from flask import Blueprint, request, Response, jsonify, stream_with_context

assistant_bp = Blueprint('assistant', __name__)
logger = logging.getLogger(__name__)

GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
CREDS_FILE = os.path.join(GRAIDER_DATA_DIR, "portal_credentials.json")
AUDIT_LOG = os.path.expanduser("~/.graider_audit.log")

os.makedirs(GRAIDER_DATA_DIR, exist_ok=True)

# In-memory conversation store
conversations = {}
session_timestamps = {}

SYSTEM_PROMPT = (
    "You are Graider Assistant, an AI helper for a teacher using the Graider grading platform. "
    "You help analyze student performance, answer questions about grades and trends, "
    "and can trigger actions like creating assignments in Focus SIS or exporting grade CSVs.\n\n"
    "RULES:\n"
    "- Be concise but helpful. Use markdown formatting when useful.\n"
    "- Use tools to look up data rather than guessing.\n"
    "- When asked about a student, use get_student_summary.\n"
    "- When asked about class performance, use get_class_analytics.\n"
    "- When asked about a specific assignment, use get_assignment_stats.\n"
    "- For general grade searches, use query_grades.\n"
    "- When asked to create an assignment in Focus, use create_focus_assignment.\n"
    "- When asked to export grades, use export_grades_csv.\n"
    "- Format numbers clearly (e.g., 82.3%, not 82.33333).\n"
    "- Present data in tables when there are multiple rows.\n"
    "- If no data is found, say so clearly and suggest what the teacher can do.\n"
)

TOOLS = [
    {
        "name": "query_grades",
        "description": "Search and filter grading results. Returns matching student grades with scores, letter grades, and feedback.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {"type": "string", "description": "Filter by student name (partial match)"},
                "assignment": {"type": "string", "description": "Filter by assignment name (partial match)"},
                "period": {"type": "string", "description": "Filter by class period (e.g., 'Period 3')"},
                "min_score": {"type": "number", "description": "Minimum score filter"},
                "max_score": {"type": "number", "description": "Maximum score filter"},
                "letter_grade": {"type": "string", "description": "Filter by letter grade (A, B, C, D, F)"},
                "limit": {"type": "integer", "description": "Max results to return (default 20)"},
            },
        },
    },
    {
        "name": "get_student_summary",
        "description": "Get comprehensive summary for a specific student including all grades, average, trend, category breakdowns, strengths, and weaknesses.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {"type": "string", "description": "Student name to look up (partial match)"},
                "student_id": {"type": "string", "description": "Student ID if known"},
            },
            "required": ["student_name"],
        },
    },
    {
        "name": "get_class_analytics",
        "description": "Get class-wide analytics: averages, grade distribution, top/bottom performers, students needing attention.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "Filter by grading period or quarter (e.g., 'Q3')"},
                "class_period": {"type": "string", "description": "Filter by class period (e.g., 'Period 3')"},
            },
        },
    },
    {
        "name": "get_assignment_stats",
        "description": "Get statistics for a specific assignment: mean, median, distribution, highest/lowest scores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment_name": {"type": "string", "description": "Assignment name (partial match supported)"},
            },
            "required": ["assignment_name"],
        },
    },
    {
        "name": "list_assignments",
        "description": "List all graded assignments with count, average score, highest, and lowest.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "create_focus_assignment",
        "description": "Trigger Focus SIS automation to create a new assignment in the gradebook. Opens a browser window and requires 2FA approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Assignment name"},
                "category": {"type": "string", "description": "Category (e.g., Assessments, Classwork, Homework)"},
                "points": {"type": "integer", "description": "Point value"},
                "date": {"type": "string", "description": "Due date in MM/DD/YYYY format"},
                "description": {"type": "string", "description": "Assignment description"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "export_grades_csv",
        "description": "Generate a Focus-formatted CSV file for grade import. Returns file path and summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment": {"type": "string", "description": "Assignment name to export grades for"},
                "period": {"type": "string", "description": "Class period to filter by"},
            },
        },
    },
]


def _cleanup_stale_sessions():
    """Remove conversation sessions older than 2 hours."""
    cutoff = time.time() - 7200
    stale = [sid for sid, ts in session_timestamps.items() if ts < cutoff]
    for sid in stale:
        conversations.pop(sid, None)
        session_timestamps.pop(sid, None)


def _audit_log(session_id, user_query, tools_called):
    """Log assistant interaction for FERPA audit trail."""
    try:
        with open(AUDIT_LOG, 'a') as f:
            entry = json.dumps({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'assistant_chat',
                'session_id': session_id[:8],
                'query_length': len(user_query),
                'tools_called': tools_called,
            })
            f.write(entry + '\n')
    except Exception:
        pass


@assistant_bp.route('/api/assistant/chat', methods=['POST'])
def assistant_chat():
    """SSE-streaming chat endpoint with Anthropic tool use."""
    import anthropic
    from backend.services.assistant_tools import execute_tool, summarize_result

    data = request.json or {}
    messages = data.get('messages', [])
    session_id = data.get('session_id', str(uuid.uuid4()))

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    # Clean up old sessions periodically
    _cleanup_stale_sessions()

    # Initialize or retrieve conversation
    if session_id not in conversations:
        conversations[session_id] = []
    session_timestamps[session_id] = time.time()

    # Append new user messages
    for msg in messages:
        conversations[session_id].append(msg)

    client = anthropic.Anthropic(api_key=api_key)
    tools_called = []

    def generate():
        nonlocal tools_called
        try:
            max_tool_rounds = 5
            for _round in range(max_tool_rounds):
                with client.messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    messages=conversations[session_id],
                    tools=TOOLS,
                ) as stream:
                    for event in stream:
                        if event.type == "content_block_start":
                            if hasattr(event, 'content_block'):
                                if event.content_block.type == "tool_use":
                                    yield 'data: ' + json.dumps({
                                        'type': 'tool_start',
                                        'tool': event.content_block.name,
                                        'id': event.content_block.id,
                                    }) + '\n\n'
                        elif event.type == "content_block_delta":
                            if hasattr(event.delta, 'text'):
                                yield 'data: ' + json.dumps({
                                    'type': 'text_delta',
                                    'content': event.delta.text,
                                }) + '\n\n'

                    final_message = stream.get_final_message()

                # Store assistant response
                conversations[session_id].append({
                    "role": "assistant",
                    "content": [block.model_dump() for block in final_message.content],
                })

                # Check for tool use
                tool_use_blocks = [b for b in final_message.content if b.type == "tool_use"]

                if not tool_use_blocks:
                    yield 'data: ' + json.dumps({'type': 'done'}) + '\n\n'
                    break

                # Execute tools
                tool_results = []
                for tool_block in tool_use_blocks:
                    tools_called.append(tool_block.name)
                    result = execute_tool(tool_block.name, tool_block.input)

                    yield 'data: ' + json.dumps({
                        'type': 'tool_result',
                        'tool': tool_block.name,
                        'result_preview': summarize_result(result),
                    }) + '\n\n'

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": json.dumps(result),
                    })

                # Feed tool results back
                conversations[session_id].append({
                    "role": "user",
                    "content": tool_results,
                })

            else:
                yield 'data: ' + json.dumps({
                    'type': 'error',
                    'message': 'Too many tool rounds. Please try a simpler question.',
                }) + '\n\n'

        except Exception as e:
            logger.error('Assistant chat error: %s', str(e))
            yield 'data: ' + json.dumps({
                'type': 'error',
                'message': str(e),
            }) + '\n\n'

        # Audit log
        user_query = ''
        for msg in messages:
            if msg.get('role') == 'user' and isinstance(msg.get('content'), str):
                user_query = msg['content']
                break
        _audit_log(session_id, user_query, tools_called)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@assistant_bp.route('/api/assistant/clear', methods=['POST'])
def clear_assistant():
    """Clear conversation history for a session."""
    session_id = (request.json or {}).get('session_id', '')
    conversations.pop(session_id, None)
    session_timestamps.pop(session_id, None)
    return jsonify({"status": "cleared"})


# ══════════════════════════════════════════════════════════════
# DISTRICT PORTAL CREDENTIALS
# ══════════════════════════════════════════════════════════════

@assistant_bp.route('/api/assistant/credentials', methods=['POST'])
def save_credentials():
    """Save district portal credentials (base64 obfuscated)."""
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    encoded_pw = base64.b64encode(password.encode()).decode()
    with open(CREDS_FILE, 'w') as f:
        json.dump({"email": email, "password": encoded_pw}, f)

    return jsonify({"status": "saved"})


@assistant_bp.route('/api/assistant/credentials')
def get_credentials():
    """Check if portal credentials are configured (never returns password)."""
    if os.path.exists(CREDS_FILE):
        try:
            with open(CREDS_FILE, 'r') as f:
                data = json.load(f)
            return jsonify({"configured": True, "email": data.get("email", "")})
        except Exception:
            return jsonify({"configured": False})
    return jsonify({"configured": False})
```

---

## New File 3: `frontend/src/components/AssistantChat.jsx`

```jsx
import { useState, useEffect, useRef } from 'react'
import { Icon } from './Icon'
import { getAuthHeaders } from '../services/api'

const API_BASE = ''

const SUGGESTED_PROMPTS = [
  { label: 'Class average', text: "What's the class average across all assignments?" },
  { label: 'Students needing help', text: 'Which students need the most attention right now?' },
  { label: 'Assignment stats', text: 'Show me statistics for the most recent assignment.' },
  { label: 'List assignments', text: 'List all graded assignments with their averages.' },
]

function renderMarkdown(text) {
  if (!text) return ''
  // Basic markdown: bold, italic, inline code, headers, lists
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // Code blocks
  html = html.replace(/```([\s\S]*?)```/g, '<pre style="background:rgba(0,0,0,0.3);padding:10px;border-radius:6px;overflow-x:auto;font-size:0.85em;margin:8px 0">$1</pre>')
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code style="background:rgba(0,0,0,0.3);padding:2px 5px;border-radius:3px;font-size:0.9em">$1</code>')
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // Headers
  html = html.replace(/^### (.+)$/gm, '<div style="font-size:1rem;font-weight:700;margin:12px 0 6px">$1</div>')
  html = html.replace(/^## (.+)$/gm, '<div style="font-size:1.1rem;font-weight:700;margin:14px 0 8px">$1</div>')
  // List items
  html = html.replace(/^- (.+)$/gm, '<div style="padding-left:16px">\u2022 $1</div>')
  html = html.replace(/^\d+\. (.+)$/gm, '<div style="padding-left:16px">$1</div>')
  // Tables (simple pipe tables)
  html = html.replace(/^\|(.+)\|$/gm, function(match, inner) {
    var cells = inner.split('|').map(function(c) { return c.trim() })
    if (cells.every(function(c) { return /^[-:]+$/.test(c) })) return ''
    var row = cells.map(function(c) {
      return '<td style="padding:4px 10px;border:1px solid var(--glass-border)">' + c + '</td>'
    }).join('')
    return '<tr>' + row + '</tr>'
  })
  html = html.replace(/(<tr>[\s\S]*?<\/tr>)/g, '<table style="border-collapse:collapse;margin:8px 0;font-size:0.85em">$1</table>')
  // Line breaks
  html = html.replace(/\n/g, '<br/>')
  return html
}

export default function AssistantChat({ addToast }) {
  var messagesRef = useRef([])
  var _s = useState([])
  var messages = _s[0]
  var setMessages = _s[1]
  var _i = useState('')
  var input = _i[0]
  var setInput = _i[1]
  var _st = useState(false)
  var isStreaming = _st[0]
  var setIsStreaming = _st[1]
  var sessionIdRef = useRef(crypto.randomUUID())
  var messagesEndRef = useRef(null)
  var inputRef = useRef(null)

  useEffect(function() {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  useEffect(function() {
    if (inputRef.current && !isStreaming) {
      inputRef.current.focus()
    }
  }, [isStreaming])

  function sendMessage(text) {
    var messageText = text || input.trim()
    if (!messageText || isStreaming) return

    var userMessage = { role: 'user', content: messageText }
    var newMessages = messages.concat([userMessage, { role: 'assistant', content: '', toolCalls: [] }])
    setMessages(newMessages)
    messagesRef.current = newMessages
    setInput('')
    setIsStreaming(true)

    getAuthHeaders().then(function(authHeaders) {
      fetch(API_BASE + '/api/assistant/chat', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders),
        body: JSON.stringify({
          messages: [userMessage],
          session_id: sessionIdRef.current,
        }),
      }).then(function(response) {
        if (!response.ok) {
          throw new Error('HTTP ' + response.status)
        }
        var reader = response.body.getReader()
        var decoder = new TextDecoder()
        var buffer = ''

        function readChunk() {
          reader.read().then(function(result) {
            if (result.done) {
              setIsStreaming(false)
              return
            }

            buffer += decoder.decode(result.value, { stream: true })
            var lines = buffer.split('\n')
            buffer = lines.pop()

            for (var li = 0; li < lines.length; li++) {
              var line = lines[li]
              if (line.indexOf('data: ') !== 0) continue
              var jsonStr = line.slice(6)
              if (!jsonStr) continue

              try {
                var event = JSON.parse(jsonStr)

                if (event.type === 'text_delta') {
                  setMessages(function(prev) {
                    var updated = prev.slice()
                    var last = updated[updated.length - 1]
                    updated[updated.length - 1] = Object.assign({}, last, {
                      content: (last.content || '') + event.content,
                    })
                    return updated
                  })
                } else if (event.type === 'tool_start') {
                  setMessages(function(prev) {
                    var updated = prev.slice()
                    var last = updated[updated.length - 1]
                    updated[updated.length - 1] = Object.assign({}, last, {
                      toolCalls: (last.toolCalls || []).concat([{
                        tool: event.tool,
                        id: event.id,
                        status: 'running',
                      }]),
                    })
                    return updated
                  })
                } else if (event.type === 'tool_result') {
                  setMessages(function(prev) {
                    var updated = prev.slice()
                    var last = updated[updated.length - 1]
                    var tools = (last.toolCalls || []).slice()
                    for (var ti = tools.length - 1; ti >= 0; ti--) {
                      if (tools[ti].tool === event.tool && tools[ti].status === 'running') {
                        tools[ti] = Object.assign({}, tools[ti], {
                          status: 'done',
                          preview: event.result_preview,
                        })
                        break
                      }
                    }
                    updated[updated.length - 1] = Object.assign({}, last, { toolCalls: tools })
                    return updated
                  })
                } else if (event.type === 'error') {
                  addToast('Assistant error: ' + event.message, 'error')
                }
              } catch (parseErr) {
                // Skip malformed events
              }
            }

            readChunk()
          }).catch(function(err) {
            addToast('Stream error: ' + err.message, 'error')
            setIsStreaming(false)
          })
        }

        readChunk()
      }).catch(function(err) {
        addToast('Failed to connect to assistant: ' + err.message, 'error')
        setIsStreaming(false)
      })
    })
  }

  function clearChat() {
    getAuthHeaders().then(function(authHeaders) {
      fetch(API_BASE + '/api/assistant/clear', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders),
        body: JSON.stringify({ session_id: sessionIdRef.current }),
      })
    })
    setMessages([])
    sessionIdRef.current = crypto.randomUUID()
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  var toolNameMap = {
    query_grades: 'Searching grades',
    get_student_summary: 'Looking up student',
    get_class_analytics: 'Analyzing class data',
    get_assignment_stats: 'Getting assignment stats',
    list_assignments: 'Listing assignments',
    create_focus_assignment: 'Creating Focus assignment',
    export_grades_csv: 'Exporting CSV',
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      maxHeight: 'calc(100vh - 80px)',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '15px 20px',
        borderBottom: '1px solid var(--glass-border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Icon name="MessageCircle" size={22} style={{ color: 'var(--accent-primary)' }} />
          <span style={{ fontSize: '1.1rem', fontWeight: 700 }}>Graider Assistant</span>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearChat}
            className="btn btn-secondary"
            style={{ fontSize: '0.8rem', padding: '6px 12px' }}
          >
            <Icon name="Trash2" size={14} />
            Clear
          </button>
        )}
      </div>

      {/* Messages Area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        {messages.length === 0 && (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '20px',
            color: 'var(--text-secondary)',
          }}>
            <Icon name="Sparkles" size={48} style={{ color: 'var(--accent-primary)', opacity: 0.5 }} />
            <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>Ask me anything about your grades</div>
            <div style={{ fontSize: '0.85rem', textAlign: 'center', maxWidth: '400px' }}>
              I can look up student performance, class analytics, assignment statistics, create Focus assignments, and export grade CSVs.
            </div>
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '8px',
              justifyContent: 'center',
              marginTop: '10px',
            }}>
              {SUGGESTED_PROMPTS.map(function(prompt) {
                return (
                  <button
                    key={prompt.label}
                    onClick={function() { sendMessage(prompt.text) }}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '20px',
                      border: '1px solid var(--glass-border)',
                      background: 'var(--glass-bg)',
                      color: 'var(--text-primary)',
                      cursor: 'pointer',
                      fontSize: '0.85rem',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={function(e) { e.target.style.background = 'rgba(99,102,241,0.15)' }}
                    onMouseLeave={function(e) { e.target.style.background = 'var(--glass-bg)' }}
                  >
                    {prompt.label}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {messages.map(function(msg, idx) {
          var isUser = msg.role === 'user'
          return (
            <div key={idx} style={{
              display: 'flex',
              justifyContent: isUser ? 'flex-end' : 'flex-start',
              maxWidth: '100%',
            }}>
              <div style={{
                maxWidth: '80%',
                padding: '12px 16px',
                borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                background: isUser
                  ? 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))'
                  : 'var(--glass-bg)',
                border: isUser ? 'none' : '1px solid var(--glass-border)',
                color: isUser ? 'white' : 'var(--text-primary)',
                fontSize: '0.9rem',
                lineHeight: '1.5',
                wordBreak: 'break-word',
              }}>
                {/* Tool call indicators */}
                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div style={{ marginBottom: msg.content ? '10px' : '0', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {msg.toolCalls.map(function(tc, ti) {
                      return (
                        <div key={ti} style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '4px 10px',
                          borderRadius: '12px',
                          background: tc.status === 'running' ? 'rgba(99,102,241,0.15)' : 'rgba(16,185,129,0.15)',
                          fontSize: '0.75rem',
                          color: tc.status === 'running' ? 'var(--accent-primary)' : '#10b981',
                        }}>
                          {tc.status === 'running'
                            ? React.createElement(Icon, { name: 'Loader2', size: 12, className: 'spin' })
                            : React.createElement(Icon, { name: 'CheckCircle', size: 12 })
                          }
                          <span>{toolNameMap[tc.tool] || tc.tool}</span>
                          {tc.preview && (
                            <span style={{ opacity: 0.7 }}>{' \u2014 ' + tc.preview}</span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
                {/* Message content */}
                {isUser
                  ? msg.content
                  : React.createElement('div', {
                      dangerouslySetInnerHTML: { __html: renderMarkdown(msg.content) },
                    })
                }
                {/* Streaming cursor */}
                {!isUser && isStreaming && idx === messages.length - 1 && !msg.content && msg.toolCalls && msg.toolCalls.length > 0 && msg.toolCalls.every(function(tc) { return tc.status === 'done' }) && (
                  <span style={{ opacity: 0.5 }}>Thinking...</span>
                )}
              </div>
            </div>
          )
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div style={{
        padding: '15px 20px',
        borderTop: '1px solid var(--glass-border)',
        display: 'flex',
        gap: '10px',
        alignItems: 'flex-end',
      }}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={function(e) { setInput(e.target.value) }}
          onKeyDown={handleKeyDown}
          placeholder="Ask about grades, students, or class performance..."
          disabled={isStreaming}
          rows={1}
          style={{
            flex: 1,
            padding: '10px 14px',
            borderRadius: '12px',
            border: '1px solid var(--input-border)',
            background: 'var(--input-bg)',
            color: 'var(--text-primary)',
            fontSize: '0.9rem',
            resize: 'none',
            minHeight: '42px',
            maxHeight: '120px',
            fontFamily: 'inherit',
            outline: 'none',
          }}
          onInput={function(e) {
            e.target.style.height = 'auto'
            e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
          }}
        />
        <button
          onClick={function() { sendMessage() }}
          disabled={isStreaming || !input.trim()}
          style={{
            padding: '10px 16px',
            borderRadius: '12px',
            border: 'none',
            background: isStreaming || !input.trim()
              ? 'var(--glass-bg)'
              : 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
            color: isStreaming || !input.trim() ? 'var(--text-muted)' : 'white',
            cursor: isStreaming || !input.trim() ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.9rem',
            fontWeight: 600,
            transition: 'all 0.2s',
          }}
        >
          <Icon name={isStreaming ? 'Loader2' : 'Send'} size={18} />
        </button>
      </div>
    </div>
  )
}
```

---

## New File 4: `focus-automation.js`

Extract from `focus-automation.md` with credentials reading from `~/.graider_data/portal_credentials.json` instead of hardcoded values.

```javascript
#!/usr/bin/env node
/**
 * Focus Assignment/Assessment Automation
 * Creates assignments and assessments in Focus gradebook
 *
 * Usage:
 *   node focus-automation.js assignment --name "Quiz 1" --category "Assessments" --points 100 --date "02/10/2026"
 *   node focus-automation.js assessment --name "Unit Test" --points 100 --date "02/15/2026"
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// Read credentials from secure storage
const CREDS_PATH = path.join(process.env.HOME, '.graider_data', 'portal_credentials.json');

function loadCredentials() {
  if (!fs.existsSync(CREDS_PATH)) {
    console.error('Error: Portal credentials not configured.');
    console.error('Go to Graider Settings > Tools to enter your VPortal credentials.');
    process.exit(1);
  }
  const data = JSON.parse(fs.readFileSync(CREDS_PATH, 'utf-8'));
  return {
    email: data.email,
    password: Buffer.from(data.password, 'base64').toString(),
  };
}

async function login(page) {
  const creds = loadCredentials();
  console.log('Navigating to VPortal...');
  await page.goto('https://vportal.volusia.k12.fl.us/');

  console.log('Entering credentials...');
  await page.fill('input[type="email"], input[name="loginfmt"]', creds.email);
  await page.click('input[type="submit"], button[type="submit"]');
  await page.waitForTimeout(1000);

  await page.fill('input[type="password"], input[name="passwd"]', creds.password);
  await page.click('input[type="submit"], button[type="submit"]');

  console.log('Waiting for 2FA - check your phone...');
  console.log('Waiting up to 60 seconds for 2FA approval...');

  try {
    await page.waitForURL('**/proofup**', { timeout: 60000 });
    console.log('2FA approved!');
    await page.click('input[type="submit"][value="Yes"], input[value="Yes"]');
  } catch (e) {
    console.log('Checking if already logged in...');
  }

  await page.waitForTimeout(2000);
  console.log('Logged in to VPortal');
}

async function navigateToFocus(page) {
  console.log('Navigating to Focus...');

  const focusLink = page.locator('a:has-text("Focus"), a[title*="Focus"], div:has-text("Focus")').first();

  if (await focusLink.isVisible().catch(() => false)) {
    await focusLink.click();
    console.log('Clicked Focus tile');
  } else {
    console.log('Trying direct Focus URL...');
    await page.goto('https://focus.volusia.k12.fl.us/focus/');
  }

  await page.waitForTimeout(3000);
  console.log('In Focus');
}

async function createAssignment(page, { name, category, points, date, description }) {
  console.log('Creating assignment: ' + name);

  console.log('Opening Gradebook...');
  const gradebookLink = page.locator('a:has-text("Gradebook"), button:has-text("Gradebook"), a[href*="gradebook"]').first();
  await gradebookLink.click();
  await page.waitForTimeout(2000);

  console.log('Opening new assignment form...');
  const addAssignmentBtn = page.locator(
    'button:has-text("Add Assignment"), ' +
    'button:has-text("New Assignment"), ' +
    'a:has-text("Add Assignment"), ' +
    'button[title*="Add Assignment"]'
  ).first();
  await addAssignmentBtn.click();
  await page.waitForTimeout(1500);

  console.log('Filling assignment details...');

  const nameField = page.locator('input[name*="name"], input[id*="name"], input[placeholder*="name"]').first();
  await nameField.fill(name);
  console.log('  Name: ' + name);

  if (category) {
    const categoryDropdown = page.locator('select[name*="category"], select[id*="category"], select[name*="type"]').first();
    await categoryDropdown.selectOption({ label: category });
    console.log('  Category: ' + category);
  }

  if (points) {
    const pointsField = page.locator('input[name*="points"], input[id*="points"], input[name*="score"]').first();
    await pointsField.fill(points.toString());
    console.log('  Points: ' + points);
  }

  if (date) {
    const dateField = page.locator('input[name*="date"], input[id*="date"], input[type="date"]').first();
    await dateField.fill(date);
    console.log('  Date: ' + date);
  }

  if (description) {
    const descField = page.locator('textarea[name*="description"], textarea[id*="description"]').first();
    if (await descField.isVisible().catch(() => false)) {
      await descField.fill(description);
      console.log('  Description: ' + description.substring(0, 50) + '...');
    }
  }

  console.log('Assignment form filled (ready for manual review/save)');
}

async function createAssessment(page, { name, points, date, description }) {
  console.log('Creating assessment: ' + name);

  console.log('Opening Gradebook...');
  const gradebookLink = page.locator('a:has-text("Gradebook"), button:has-text("Gradebook"), a[href*="gradebook"]').first();
  await gradebookLink.click();
  await page.waitForTimeout(2000);

  console.log('Opening new assessment form...');
  const addAssessmentBtn = page.locator(
    'button:has-text("Add Assessment"), ' +
    'button:has-text("New Assessment"), ' +
    'a:has-text("Add Assessment")'
  ).first();

  if (await addAssessmentBtn.isVisible().catch(() => false)) {
    await addAssessmentBtn.click();
  } else {
    console.log('No separate assessment button, using assignment form...');
    const addAssignmentBtn = page.locator('button:has-text("Add Assignment"), a:has-text("Add Assignment")').first();
    await addAssignmentBtn.click();
  }

  await page.waitForTimeout(1500);

  console.log('Filling assessment details...');

  const nameField = page.locator('input[name*="name"], input[id*="name"]').first();
  await nameField.fill(name);
  console.log('  Name: ' + name);

  const categoryDropdown = page.locator('select[name*="category"], select[id*="category"]').first();
  if (await categoryDropdown.isVisible().catch(() => false)) {
    try {
      await categoryDropdown.selectOption({ label: 'Assessment' });
      console.log('  Category: Assessment');
    } catch (e) {
      console.log('  (No Assessment category found)');
    }
  }

  if (points) {
    const pointsField = page.locator('input[name*="points"], input[id*="points"]').first();
    await pointsField.fill(points.toString());
    console.log('  Points: ' + points);
  }

  if (date) {
    const dateField = page.locator('input[name*="date"], input[id*="date"], input[type="date"]').first();
    await dateField.fill(date);
    console.log('  Date: ' + date);
  }

  if (description) {
    const descField = page.locator('textarea[name*="description"], textarea[id*="description"]').first();
    if (await descField.isVisible().catch(() => false)) {
      await descField.fill(description);
    }
  }

  console.log('Assessment form filled (ready for manual review/save)');
}

// CLI argument parsing
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || !['assignment', 'assessment'].includes(command)) {
    console.error('Usage: node focus-automation.js <assignment|assessment> [options]');
    console.error('');
    console.error('Options:');
    console.error('  --name "Assignment Name"     (required)');
    console.error('  --category "Category"        (optional)');
    console.error('  --points 100                 (optional)');
    console.error('  --date "MM/DD/YYYY"          (optional)');
    console.error('  --description "Description"  (optional)');
    process.exit(1);
  }

  const getArg = (flag) => {
    const idx = args.indexOf(flag);
    return idx !== -1 && args[idx + 1] ? args[idx + 1] : null;
  };

  const name = getArg('--name');
  const category = getArg('--category');
  const points = getArg('--points') ? parseInt(getArg('--points')) : null;
  const date = getArg('--date');
  const description = getArg('--description');

  if (!name) {
    console.error('Error: --name is required');
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await login(page);
    await navigateToFocus(page);

    if (command === 'assignment') {
      await createAssignment(page, { name, category, points, date, description });
    } else if (command === 'assessment') {
      await createAssessment(page, { name, points, date, description });
    }

    console.log('');
    console.log('Form ready for review. Browser will stay open for 2 minutes...');
    console.log('Review the details and click Save manually.');
    await page.waitForTimeout(120000);

  } catch (error) {
    console.error('Error:', error.message);
    await page.screenshot({ path: 'focus-error.png' });
    console.error('Screenshot saved to focus-error.png');
  } finally {
    await browser.close();
  }
}

main();
```

---

## Modified File 1: `backend/routes/__init__.py`

### Edit 1: Add import (after line 20)

```python
# AFTER: from .lesson_routes import lesson_bp
# ADD:
from .assistant_routes import assistant_bp
```

### Edit 2: Register blueprint (after line 40)

```python
# AFTER: app.register_blueprint(lesson_bp)
# ADD:
    app.register_blueprint(assistant_bp)
```

### Edit 3: Add to __all__ (after line 53)

```python
# CHANGE __all__ to include:
    'assistant_bp',
```

---

## Modified File 2: `frontend/src/App.jsx`

### Edit 1: Add tab to TABS array (line 37, after resources)

```javascript
// AFTER: { id: "resources", label: "Resources", icon: "FolderOpen" },
// ADD:
  { id: "assistant", label: "Assistant", icon: "MessageCircle" },
```

### Edit 2: Add component import (near top imports)

```javascript
// AFTER other component imports
import AssistantChat from './components/AssistantChat'
```

### Edit 3: Add tab content rendering (after resources tab block, before settings tab)

Find the closing of the resources tab (search for the `{activeTab === "resources"` block end) and add:

```javascript
                {activeTab === "assistant" && (
                  <AssistantChat addToast={addToast} />
                )}
```

### Edit 4: Add VPortal credentials to Settings > Tools tab

In the integration/tools settings tab, after the "Add Custom Tool" section (around line 11650), before the tab closing `</>`:

```jsx
                    {/* District Portal Credentials */}
                    <div style={{ marginTop: "30px" }}>
                      <h3
                        style={{
                          fontSize: "1.1rem",
                          fontWeight: 700,
                          marginBottom: "8px",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <Icon name="Shield" size={20} style={{ color: "#f59e0b" }} />
                        District Portal (VPortal)
                      </h3>
                      <p
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-muted)",
                          marginBottom: "15px",
                        }}
                      >
                        Enter your VPortal credentials to enable Focus SIS automation (assignment creation, grade import).
                        Credentials are stored locally and never sent to any AI service.
                      </p>

                      <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxWidth: "400px" }}>
                        <div>
                          <label style={{ fontSize: "0.85rem", color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Email</label>
                          <input
                            type="email"
                            className="input"
                            value={portalEmail}
                            onChange={function(e) { setPortalEmail(e.target.value) }}
                            placeholder="your.email@volusia.k12.fl.us"
                          />
                        </div>
                        <div>
                          <label style={{ fontSize: "0.85rem", color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Password</label>
                          <input
                            type="password"
                            className="input"
                            value={portalPassword}
                            onChange={function(e) { setPortalPassword(e.target.value) }}
                            placeholder={portalConfigured ? "********" : "Enter password"}
                          />
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <button
                            onClick={async function() {
                              if (!portalEmail || !portalPassword) {
                                addToast("Email and password are required", "error");
                                return;
                              }
                              try {
                                var authHeaders = await api.getAuthHeaders();
                                var res = await fetch("/api/assistant/credentials", {
                                  method: "POST",
                                  headers: Object.assign({ "Content-Type": "application/json" }, authHeaders),
                                  body: JSON.stringify({ email: portalEmail, password: portalPassword }),
                                });
                                var data = await res.json();
                                if (data.status === "saved") {
                                  addToast("Portal credentials saved", "success");
                                  setPortalConfigured(true);
                                  setPortalPassword("");
                                } else {
                                  addToast(data.error || "Failed to save", "error");
                                }
                              } catch (err) {
                                addToast("Error: " + err.message, "error");
                              }
                            }}
                            className="btn btn-primary"
                            style={{ fontSize: "0.85rem" }}
                          >
                            <Icon name="Save" size={16} />
                            Save Credentials
                          </button>
                          {portalConfigured && (
                            <span style={{ fontSize: "0.8rem", color: "#10b981", display: "flex", alignItems: "center", gap: "4px" }}>
                              <Icon name="CheckCircle" size={14} />
                              Configured
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
```

### Edit 5: Add state variables for portal credentials

Near other state declarations:

```javascript
  const [portalEmail, setPortalEmail] = useState('');
  const [portalPassword, setPortalPassword] = useState('');
  const [portalConfigured, setPortalConfigured] = useState(false);
```

### Edit 6: Load portal credential status on mount

In an existing `useEffect` that runs on mount, or add:

```javascript
  useEffect(function() {
    fetch('/api/assistant/credentials')
      .then(function(r) { return r.json() })
      .then(function(data) {
        if (data.configured) {
          setPortalConfigured(true);
          setPortalEmail(data.email || '');
        }
      })
      .catch(function() {});
  }, []);
```

---

## Modified File 3: `frontend/src/services/api.js`

### Edit: Add assistant functions (before the default export)

```javascript
// ============ Assistant ============

export async function sendAssistantMessage(messages, sessionId) {
  const authHeaders = await getAuthHeaders()
  return fetch(API_BASE + '/api/assistant/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify({ messages, session_id: sessionId }),
  })
}

export async function clearAssistantSession(sessionId) {
  return fetchApi('/api/assistant/clear', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  })
}
```

Add to default export object:

```javascript
  sendAssistantMessage,
  clearAssistantSession,
```

---

## Verification Checklist

1. [ ] `python backend/app.py` — no import errors
2. [ ] All 8 tabs render (Grade, Results, Builder, Analytics, Planner, Resources, Assistant, Settings)
3. [ ] Assistant tab shows empty state with suggested prompts
4. [ ] Click "Class average" prompt — streams a response using `get_class_analytics` tool
5. [ ] Ask "How is [student name] doing?" — uses `get_student_summary` tool
6. [ ] Ask "Show students below 60 on Cornell Notes" — uses `query_grades` tool
7. [ ] Settings > Tools shows VPortal credential fields
8. [ ] Saving credentials shows "Configured" indicator
9. [ ] `focus-automation.js` reads from `~/.graider_data/portal_credentials.json`
10. [ ] No console errors in browser DevTools
11. [ ] Existing tabs still work normally
