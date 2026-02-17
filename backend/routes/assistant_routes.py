"""
Assistant API Routes
====================
SSE chat endpoint with Anthropic Claude tool use loop.
Handles conversation management and VPortal credential storage.
"""

import os
import io
import json
import time
import base64
import uuid
import tempfile
import threading
import queue
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, Response, stream_with_context

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai as openai_pkg
except ImportError:
    openai_pkg = None

try:
    import google.generativeai as genai_pkg
except ImportError:
    genai_pkg = None

from backend.services.assistant_tools import (
    TOOL_DEFINITIONS, execute_tool,
    _load_standards, _extract_pdf_text, _extract_docx_text,
    DOCUMENTS_DIR,
)

assistant_bp = Blueprint('assistant', __name__)

# ═══════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════

GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
CREDS_FILE = os.path.join(GRAIDER_DATA_DIR, "portal_credentials.json")
AUDIT_LOG_FILE = os.path.expanduser("~/.graider_audit.log")

ASSISTANT_MODELS = {
    # Anthropic
    "haiku": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    "sonnet": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    # OpenAI
    "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    "gpt-4o": {"provider": "openai", "model": "gpt-4o"},
    # Google
    "gemini-flash": {"provider": "gemini", "model": "gemini-2.0-flash"},
    "gemini-pro": {"provider": "gemini", "model": "gemini-2.0-pro-exp-02-05"},
}
DEFAULT_MODEL = "haiku"
MAX_TOKENS = 4096


def _get_assistant_model():
    """Read assistant_model from settings, return {provider, model} dict."""
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
        choice = settings.get("assistant_model", DEFAULT_MODEL)
        return ASSISTANT_MODELS.get(choice, ASSISTANT_MODELS[DEFAULT_MODEL])
    except Exception:
        return ASSISTANT_MODELS[DEFAULT_MODEL]


def _convert_tools_for_openai(anthropic_tools):
    """Convert Anthropic tool definitions to OpenAI function calling format."""
    return [{
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t.get("input_schema", {"type": "object", "properties": {}})
        }
    } for t in anthropic_tools]


def _convert_messages_for_openai(messages, system_prompt):
    """Convert Anthropic-style messages to OpenAI format."""
    oai_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Handle Anthropic tool_result messages (sent as "user" with content list)
        if role == "user" and isinstance(content, list):
            # Check if these are tool results
            if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                for tr in content:
                    oai_messages.append({
                        "role": "tool",
                        "tool_call_id": tr.get("tool_use_id", ""),
                        "content": tr.get("content", "")
                    })
                continue
            # Multimodal content blocks — extract text
            text_parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            oai_messages.append({"role": "user", "content": " ".join(text_parts) if text_parts else str(content)})
            continue

        # Handle assistant messages with tool_use blocks
        if role == "assistant" and isinstance(content, list):
            text_parts = []
            tool_calls = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block.get("input", {}))
                            }
                        })
            msg_dict = {"role": "assistant", "content": " ".join(text_parts) if text_parts else None}
            if tool_calls:
                msg_dict["tool_calls"] = tool_calls
            oai_messages.append(msg_dict)
            continue

        oai_messages.append({"role": role, "content": content if isinstance(content, str) else str(content)})
    return oai_messages


def _convert_tools_for_gemini(anthropic_tools):
    """Convert Anthropic tool definitions to Gemini function declarations."""
    declarations = []
    for t in anthropic_tools:
        schema = t.get("input_schema", {})
        # Gemini doesn't support additionalProperties — strip it
        props = schema.get("properties", {})
        cleaned_props = {}
        for k, v in props.items():
            cleaned = {kk: vv for kk, vv in v.items() if kk != "additionalProperties"}
            cleaned_props[k] = cleaned
        declarations.append(genai_pkg.types.FunctionDeclaration(
            name=t["name"],
            description=t.get("description", ""),
            parameters={
                "type": "object",
                "properties": cleaned_props,
                "required": schema.get("required", [])
            }
        ))
    return declarations

# In-memory conversation store {session_id: {"messages": [...], "last_active": timestamp}}
conversations = {}
CONVERSATION_TTL = 7200  # 2 hours
CONVERSATIONS_FILE = os.path.join(GRAIDER_DATA_DIR, "assistant_conversations.json")


def _persist_conversation(session_id):
    """Save a single conversation to disk so it survives server restarts."""
    try:
        os.makedirs(GRAIDER_DATA_DIR, exist_ok=True)
        # Load existing file
        all_convs = {}
        if os.path.exists(CONVERSATIONS_FILE):
            with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
                all_convs = json.load(f)

        conv = conversations.get(session_id)
        if conv:
            # Only persist text messages (skip binary/image content blocks)
            safe_messages = []
            for m in conv["messages"]:
                if isinstance(m.get("content"), str):
                    safe_messages.append(m)
                elif isinstance(m.get("content"), list):
                    # Keep only text blocks from multimodal messages
                    text_parts = [b for b in m["content"] if isinstance(b, dict) and b.get("type") == "text"]
                    if text_parts:
                        safe_messages.append({"role": m["role"], "content": text_parts[0]["text"]})
            all_convs[session_id] = {
                "messages": safe_messages[-40:],  # Keep last 40 messages max
                "last_active": conv["last_active"],
            }
        else:
            all_convs.pop(session_id, None)

        # Prune old sessions (>24h)
        cutoff = time.time() - 86400
        all_convs = {k: v for k, v in all_convs.items() if v.get("last_active", 0) > cutoff}

        with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_convs, f, indent=2)
    except Exception as e:
        logger.warning("Failed to persist conversation %s: %s", session_id, e)


def _load_conversation(session_id):
    """Load a conversation from disk if it exists."""
    try:
        if os.path.exists(CONVERSATIONS_FILE):
            with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
                all_convs = json.load(f)
            if session_id in all_convs:
                return all_convs[session_id]
    except Exception as e:
        logger.warning("Failed to load conversation %s: %s", session_id, e)
    return None

# Per-session TTS mute flag — set by frontend to stop TTS mid-stream
tts_muted_sessions = set()

# Per-session cancellation flag — stops the tool loop when user clicks Stop
cancelled_sessions = set()

SETTINGS_FILE = os.path.expanduser("~/.graider_settings.json")
RUBRIC_FILE = os.path.expanduser("~/.graider_rubric.json")
MEMORY_FILE = os.path.join(GRAIDER_DATA_DIR, "assistant_memory.json")
ASSISTANT_COSTS_FILE = os.path.join(GRAIDER_DATA_DIR, "assistant_costs.json")

# OpenAI TTS pricing — $0.015 per 1K characters (tts-1 model)
TTS_COST_PER_CHAR = 0.000015
OPENAI_TTS_VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
PERIODS_DIR = os.path.join(GRAIDER_DATA_DIR, "periods")
ACCOMMODATIONS_FILE = os.path.join(GRAIDER_DATA_DIR, "accommodations", "student_accommodations.json")
TEMPLATES_DIR = os.path.join(GRAIDER_DATA_DIR, "assessment_templates")

# Cache user manual text at module level to avoid re-reading on every request
_user_manual_cache = None


def _load_user_manual():
    """Load User_Manual.md for platform knowledge. Cached after first read."""
    global _user_manual_cache
    if _user_manual_cache is not None:
        return _user_manual_cache
    manual_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "User_Manual.md"
    )
    try:
        with open(manual_path, 'r', encoding='utf-8') as f:
            _user_manual_cache = f.read()
    except Exception:
        _user_manual_cache = ""
    return _user_manual_cache


def _extract_text_from_pdf(file_bytes):
    """Extract text from PDF bytes using PyMuPDF."""
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        return "[PDF extraction requires PyMuPDF: pip install pymupdf]"
    except Exception as e:
        return "[Error extracting PDF: " + str(e) + "]"


def _extract_text_from_docx(file_bytes):
    """Extract text from DOCX bytes using python-docx."""
    try:
        from docx import Document
        from docx.text.paragraph import Paragraph
        from docx.table import Table

        doc = Document(io.BytesIO(file_bytes))
        full_text = []
        for element in doc.element.body:
            if element.tag.endswith('p'):
                para = Paragraph(element, doc)
                if para.text.strip():
                    full_text.append(para.text)
            elif element.tag.endswith('tbl'):
                table = Table(element, doc)
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        full_text.append(' | '.join(row_text))
        return '\n'.join(full_text)
    except ImportError:
        return "[DOCX extraction requires python-docx: pip install python-docx]"
    except Exception as e:
        return "[Error extracting DOCX: " + str(e) + "]"


def _build_file_content_blocks(files):
    """Convert uploaded file data into Claude API content blocks.

    Args:
        files: List of dicts with 'filename', 'media_type', 'data' (base64).

    Returns:
        List of content blocks for the Claude API message.
    """
    blocks = []
    for file_info in files:
        media_type = file_info.get("media_type", "application/octet-stream")
        filename = file_info.get("filename", "file")
        data_b64 = file_info.get("data", "")

        if media_type.startswith("image/"):
            blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data_b64
                }
            })
        elif media_type == "application/pdf":
            file_bytes = base64.b64decode(data_b64)
            text = _extract_text_from_pdf(file_bytes)
            blocks.append({
                "type": "text",
                "text": "[PDF Content - " + filename + "]:\n" + text
            })
        elif ("word" in media_type or "officedocument" in media_type
              or filename.lower().endswith(".docx")):
            file_bytes = base64.b64decode(data_b64)
            text = _extract_text_from_docx(file_bytes)
            blocks.append({
                "type": "text",
                "text": "[Document Content - " + filename + "]:\n" + text
            })
        else:
            blocks.append({
                "type": "text",
                "text": "[Unsupported file type: " + filename + " (" + media_type + ")]"
            })

    return blocks


def _load_period_differentiation():
    """Load period class levels from meta files. Returns dict like {'Period 1': 'advanced', ...}."""
    levels = {}
    if not os.path.isdir(PERIODS_DIR):
        return levels
    try:
        import glob as glob_mod
        for meta_file in glob_mod.glob(os.path.join(PERIODS_DIR, "*.meta.json")):
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            period_name = meta.get("period_name", "")
            class_level = meta.get("class_level", "standard")
            if period_name:
                levels[period_name] = class_level
    except Exception:
        pass
    return levels


def _load_accommodation_summary():
    """Load aggregate accommodation stats (FERPA-safe: counts only, no student names)."""
    if not os.path.exists(ACCOMMODATIONS_FILE):
        return None
    try:
        with open(ACCOMMODATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            return None
        total_students = len(data)
        preset_counts = {}
        for student_data in data.values():
            presets = student_data.get("presets", [])
            for p in presets:
                preset_counts[p] = preset_counts.get(p, 0) + 1
        return {"total_students": total_students, "preset_counts": preset_counts}
    except Exception:
        return None


# Cap total injected resource text at 80K chars (~20K tokens)
MAX_RESOURCE_INJECTION = 80000


def _load_resource_content():
    """Load text content from all uploaded documents for system prompt injection.

    Returns a formatted string with each document's content, or empty string
    if no documents exist. Respects MAX_RESOURCE_INJECTION total char limit.
    """
    if not os.path.isdir(DOCUMENTS_DIR):
        return ""

    sections = []
    total_chars = 0

    try:
        for fname in sorted(os.listdir(DOCUMENTS_DIR)):
            if fname.endswith('.meta.json'):
                continue
            fpath = os.path.join(DOCUMENTS_DIR, fname)
            if not os.path.isfile(fpath):
                continue

            # Load metadata for context
            meta_path = fpath + ".meta.json"
            meta = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                except Exception:
                    pass

            doc_type = meta.get("doc_type", "general")
            description = meta.get("description", "")
            ext = os.path.splitext(fname)[1].lower()

            # Extract text
            content = ""
            try:
                if ext == '.pdf':
                    content, _ = _extract_pdf_text(fpath)
                elif ext in ('.docx', '.doc'):
                    content = _extract_docx_text(fpath)
                elif ext in ('.txt', '.md'):
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
            except Exception:
                continue

            if not content or content.startswith("[Error") or content.startswith("[PDF extraction"):
                continue

            # Check total size budget
            if total_chars + len(content) > MAX_RESOURCE_INJECTION:
                remaining = MAX_RESOURCE_INJECTION - total_chars
                if remaining > 500:
                    content = content[:remaining] + "\n[... truncated due to size limit]"
                else:
                    break

            header = f"### {fname}"
            if description:
                header += f" — {description}"
            header += f" ({doc_type})"

            sections.append(f"{header}\n{content}")
            total_chars += len(content)

    except Exception:
        return ""

    return "\n\n".join(sections)


def _load_rubric():
    """Load grading rubric settings."""
    try:
        if os.path.exists(RUBRIC_FILE):
            with open(RUBRIC_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _load_assessment_templates():
    """Load assessment template metadata (e.g., Wayground quiz format)."""
    templates = []
    try:
        if not os.path.exists(TEMPLATES_DIR):
            return templates
        for fname in os.listdir(TEMPLATES_DIR):
            if not fname.endswith('.meta.json'):
                continue
            meta_path = os.path.join(TEMPLATES_DIR, fname)
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            structure = meta.get("structure", {})
            # Extract unique question types from sample rows
            question_types = set()
            for row in structure.get("sample_rows", []):
                if len(row) > 1 and row[1] and not row[1].startswith("Question Type"):
                    question_types.add(row[1])
            templates.append({
                "name": meta.get("name", fname),
                "platform": meta.get("platform", "unknown"),
                "extension": meta.get("extension", ""),
                "columns": structure.get("columns", []),
                "sample_rows": structure.get("sample_rows", [])[1:],  # Skip header-description row
                "question_types": sorted(question_types) if question_types else [],
            })
    except Exception:
        pass
    return templates


def _load_analytics_snapshot():
    """Build a compact analytics summary from master_grades.csv for the system prompt.

    Returns a short text block with class averages, rubric category performance,
    student trends, and attention flags — enough for proactive recommendations
    without needing a tool call.
    """
    import csv
    from collections import defaultdict

    # Locate master_grades.csv
    output_folder = os.path.expanduser("~/Downloads/Graider/Results")
    settings_file = os.path.expanduser("~/.graider_global_settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                gs = json.load(f)
            output_folder = gs.get('output_folder', output_folder)
        except Exception:
            pass

    master_file = os.path.join(output_folder, "master_grades.csv")
    if not os.path.exists(master_file):
        return ""

    try:
        students = defaultdict(list)
        categories = defaultdict(lambda: {"content": [], "completeness": [], "writing": [], "effort": []})
        all_scores = []

        # Map CSV column names to internal keys
        col_map = {
            "name": "Student Name",
            "score": "Overall Score",
            "approval": "Approved",
            "content": "Content Accuracy",
            "completeness": "Completeness",
            "writing": "Writing Quality",
            "effort": "Effort Engagement",
        }

        with open(master_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rejected grades
                if row.get(col_map["approval"], "").lower() == "rejected":
                    continue
                try:
                    score = float(row.get(col_map["score"], 0))
                except (ValueError, TypeError):
                    continue
                name = row.get(col_map["name"], "").strip()
                if not name:
                    continue
                all_scores.append(score)
                students[name].append(score)
                # Category breakdowns
                for cat in ["content", "completeness", "writing", "effort"]:
                    try:
                        val = float(row.get(col_map[cat], 0))
                        if val > 0:
                            categories[name][cat].append(val)
                    except (ValueError, TypeError):
                        pass

        if not all_scores:
            return ""

        # Class-wide stats
        class_avg = round(sum(all_scores) / len(all_scores), 1)
        total_students = len(students)
        total_assignments = len(all_scores)

        # Category multipliers (same as analytics_routes.py)
        multipliers = {"content": 2.5, "completeness": 4, "writing": 5, "effort": 6.67}
        class_cats = {}
        for cat, mult in multipliers.items():
            all_vals = []
            for name in categories:
                vals = categories[name][cat]
                if vals:
                    all_vals.append(sum(vals) / len(vals) * mult)
            class_cats[cat] = round(sum(all_vals) / len(all_vals), 1) if all_vals else 0

        # Find weakest and strongest categories
        cat_labels = {"content": "Content Accuracy", "completeness": "Completeness",
                      "writing": "Writing Quality", "effort": "Effort & Engagement"}
        sorted_cats = sorted(class_cats.items(), key=lambda x: x[1])
        weakest = sorted_cats[0] if sorted_cats else None
        strongest = sorted_cats[-1] if sorted_cats else None

        # Student trends (improving/declining counts)
        improving = 0
        declining = 0
        attention_students = []
        for name, scores in students.items():
            avg = round(sum(scores) / len(scores), 1)
            if len(scores) >= 3:
                first_half = scores[:len(scores) // 2]
                second_half = scores[len(scores) // 2:]
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                if second_avg - first_avg >= 3:
                    improving += 1
                elif first_avg - second_avg >= 3:
                    declining += 1
            if avg < 70:
                attention_students.append(name)

        # Build compact summary
        lines = []
        lines.append(f"Class Overview: {total_students} students, {total_assignments} graded assignments, class average {class_avg}%")

        cat_line = ", ".join(f"{cat_labels[c]}: {v}%" for c, v in sorted_cats)
        lines.append(f"Rubric Categories: {cat_line}")

        if weakest and strongest and weakest[0] != strongest[0]:
            lines.append(f"Strongest: {cat_labels[strongest[0]]} ({strongest[1]}%). Weakest: {cat_labels[weakest[0]]} ({weakest[1]}%)")

        trend_parts = []
        if improving:
            trend_parts.append(f"{improving} improving")
        if declining:
            trend_parts.append(f"{declining} declining")
        if attention_students:
            trend_parts.append(f"{len(attention_students)} below 70%")
        if trend_parts:
            lines.append(f"Student Trends: {', '.join(trend_parts)}")

        return "\n".join(lines)

    except Exception:
        return ""


def _build_system_prompt():
    """Build the system prompt dynamically, injecting teacher info from settings."""
    teacher_name = ""
    subject = ""
    school_name = ""
    teacher_email = ""
    email_signature = ""
    grade_level = ""
    state = ""
    grading_period = ""
    global_ai_notes = ""
    available_tools = []

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            config = settings.get('config', {})
            teacher_name = config.get('teacher_name', '')
            subject = config.get('subject', '')
            school_name = config.get('school_name', '')
            teacher_email = config.get('teacher_email', '')
            email_signature = config.get('email_signature', '')
            grade_level = config.get('grade_level', '')
            state = config.get('state', '')
            grading_period = config.get('grading_period', '')
            global_ai_notes = settings.get('globalAINotes', '')
            available_tools = config.get('availableTools', [])
        except Exception:
            pass

    teacher_context = ""
    if teacher_name or subject or school_name:
        parts = []
        if teacher_name:
            parts.append(f"Teacher: {teacher_name}")
        if subject:
            parts.append(f"Subject: {subject}")
        if grade_level:
            parts.append(f"Grade Level: {grade_level}")
        if state:
            parts.append(f"State: {state}")
        if grading_period:
            parts.append(f"Grading Period: {grading_period}")
        if school_name:
            parts.append(f"School: {school_name}")
        if teacher_email:
            parts.append(f"Email: {teacher_email}")
        if email_signature:
            parts.append(f"Email Signature:\n{email_signature}")
        teacher_context = "\n\nTeacher Information (use this for email signatures, letters, and communications):\n" + "\n".join(parts)

    prompt = f"""You are a helpful teaching assistant built into Graider, an AI-powered grading tool. You help teachers understand student performance, analyze grades, and manage their gradebook.{teacher_context}

Key guidelines:
- Be concise and teacher-friendly. Use markdown formatting (bold, lists, tables) when helpful.
- When asked about grades or students, use the available tools to query actual data — never guess or make up numbers.
- Respect FERPA: minimize personally identifiable information in your responses. Use first names only when discussing individual students. Never share data outside this conversation.
- When showing multiple students, use tables for clarity.
- If data is unavailable, say so clearly and suggest what the teacher can do (e.g., "Grade some assignments first").
- For Focus automation, always confirm what will be created before triggering it.
- All student data stays local on the teacher's machine. Tool results come from local files only.
- When drafting emails or communications, use the teacher's name, subject, school, and email signature from the teacher information above. Always sign off with their configured signature.

Available tools:
- query_grades: Search/filter grades by student, assignment, period, score range
- get_student_summary: Deep dive into one student's performance and trends
- get_class_analytics: Class-wide stats, grade distribution, top/bottom performers
- get_assignment_stats: Statistics for a specific assignment
- list_assignments: Show all graded assignments
- analyze_grade_causes: Deep analysis of WHY students got low grades — rubric category breakdowns, unanswered/omitted questions, score impact of omissions, weakest categories. Use this when asked about causes of low grades, common mistakes, or what students struggled with.
- get_feedback_patterns: Analyze feedback text and skills across an assignment — common strengths, areas for growth, feedback samples from high/low scorers. Use when asked about patterns or common issues.
- compare_periods: Compare performance across class periods — averages, grade distributions, category breakdowns, omission rates per period.
- recommend_next_lesson: Analyze weaknesses and recommend what to teach next. Now includes DIFFERENTIATED recommendations by class level (advanced/standard/support) with DOK-appropriate standards, and IEP/504 accommodation analysis. Use when teacher asks "what should I teach next?", "how should I differentiate?", or "what lesson would help?"
- lookup_student_info: Look up student roster and contact information — student IDs, local IDs, grade level, period, course codes, student email, parent emails, parent phone numbers, 504 plan status, detailed contacts (up to 3 with names, relationships, and roles), and full student schedule (all periods with teachers and courses). Search by name, ID, or list all students in a period. Supports BATCH lookup via student_ids array. Use this when the teacher asks for contact info, emails, parent emails, phone numbers, student IDs, who a student's other teachers are, or 504/accommodation status. IMPORTANT: query_grades results include student_id — when you need parent emails for multiple students (e.g., failing students), first use query_grades to get their student_ids, then use lookup_student_info with the student_ids array to get all their contacts in one call.
- get_missing_assignments: Find missing/unsubmitted work. Search by student (what are they missing?), by period (who has missing work?), or by assignment (who hasn't turned in X?). Use this when teacher asks about missing work, incomplete submissions, or which students haven't turned in assignments.
- generate_worksheet: Create downloadable worksheet documents (Cornell Notes, fill-in-blank, short-answer, vocabulary) with built-in answer keys for AI grading. Automatically saved to Grading Setup. When the teacher uploads a textbook page or reading and asks for a worksheet, ALWAYS use this tool. Extract vocab terms, write questions with expected answers, and include summary key points. The worksheet will have an invisible answer key embedded for consistent grading.
- generate_document: Create formatted Word documents with rich typography (headings, bold, italic, lists, tables). Use for study guides, reference sheets, parent letters, lesson outlines, rubrics, or any document. NOT for gradeable worksheets.
- save_document_style: Save the visual formatting of a document (fonts, sizes, colors) as a reusable style. Use when the teacher says they like how a document looks and want that same look for future documents of that type.
- list_document_styles: Check what saved visual styles exist. Use before generating a document to see if a matching style is available.
- generate_csv: Generate a downloadable spreadsheet (XLSX or CSV). Use .xlsx for Wayground quizzes (required format) and polished spreadsheets. When generating for Wayground, use .xlsx and match the exact column structure from the Assessment Templates section (Question Text, Question Type, Option 1-5, Correct Answer, Time in seconds, Image Link, Answer explanation).
- create_focus_assignment: Create assignment in Focus gradebook (browser automation)
- export_grades_csv: Export grades as Focus-compatible CSV files

When a teacher asks "why did students do poorly" or "what caused the low grades", ALWAYS use analyze_grade_causes — it provides rubric category breakdown, unanswered question data, and the score impact of omissions. This is your most powerful diagnostic tool.

When a teacher asks "what should I teach next?" or "what lesson would help with these weaknesses?", use recommend_next_lesson — it analyzes performance data and cross-references curriculum standards to suggest targeted lesson topics. You can also call analyze_grade_causes first, then recommend_next_lesson to give a complete diagnostic + prescription response.

DIFFERENTIATION: recommend_next_lesson now returns a class_level_breakdown with separate analysis for advanced, standard, and support periods. Each level gets DOK-appropriate standard recommendations (DOK 1-2 for support, DOK 1-3 for standard, DOK 1-4 for advanced). When presenting lesson recommendations, ALWAYS address each class level separately if the data shows different levels. Suggest scaffolded activities for support classes, grade-level work for standard, and extension/analytical work for advanced.

IEP/504 AWARENESS: recommend_next_lesson also returns accommodation_analysis showing how IEP/504 students performed compared to non-accommodated peers. If there is a score gap or distinct weakness pattern, mention it and suggest modifications (extended time, simplified prompts, graphic organizers, chunked assignments, etc.). Always handle accommodation data sensitively — never list individual IEP student names, only aggregate patterns.

DOCUMENT GENERATION: When generating any document or worksheet, first call list_document_styles to check if a matching saved style exists, and if so, pass the style_name parameter. Use generate_document for non-gradeable documents (study guides, reference sheets, parent letters, lesson outlines). Use generate_worksheet for gradeable assignments. Both support rich formatting: **bold**, *italic*, and ***bold+italic*** in text content. When the teacher says they like a document's formatting, use save_document_style to save it for future reuse.

SAVING DOCUMENTS: After generating a document with generate_document, always ask the teacher: "Would you like me to save this to your assignments in Grading Setup?" If they say yes, call generate_document again with the same content and save_to_builder=true. Worksheets created with generate_worksheet are always saved to Grading Setup automatically.

CURRICULUM & LESSON TOOLS:
- get_standards: Look up curriculum standards for the teacher's state and subject. Returns ALL standards when no topic filter, or filter by keyword and DOK level. Use for full details (vocabulary, learning targets, essential questions).
- list_all_standards: Get a compact index of ALL curriculum standards (codes, short benchmarks, DOK levels). Use this first to see the full scope of standards before drilling into specifics with get_standards.
- get_recent_lessons: List saved lesson plans by unit. Shows topics, standards covered, vocabulary, and objectives from past lessons. Use when the teacher says "create a quiz for this unit", "what have we been working on", or references past lessons.
- save_memory: Save important facts about the teacher or their classes for future conversations. Use when the teacher shares preferences, class structure, or workflow habits.

RESOURCE TOOLS:
- list_resources: List all uploaded supporting documents (pacing guides, curriculum docs, rubrics). Discover what reference materials are available.
- read_resource: Read the full text content of a specific uploaded document. Use for curriculum guides, pacing calendars, or any reference material the teacher has uploaded.

TEACHING CALENDAR TOOLS:
- get_calendar: Read the teaching calendar for a date range. Shows scheduled lessons and holidays. AUTHORITATIVE — if it returns lessons, those ARE what the teacher is teaching. Never say "nothing is scheduled" when scheduled_lessons is non-empty. When asked about a specific day (e.g. "Tuesday"), query that exact date. When generating worksheets for a date, the worksheet topic MUST match the scheduled lesson for that date. Defaults to the next 7 days.
- schedule_lesson: Place a saved lesson onto the calendar on a specific date. For multi-day lessons, call once per day with incrementing day_number and consecutive school-day dates. Use when the teacher says "schedule Unit 3 starting Monday" or "put the Revolution lesson on the calendar for next week". Always confirm dates before scheduling.
- add_calendar_holiday: Mark a date (or date range) as a holiday or break. Use when the teacher says "we're off next Friday", "add Spring Break March 16-20", or "mark Monday as a teacher workday".

When generating worksheets or quizzes, ALWAYS call get_standards first to find relevant standards, and get_recent_lessons to see what's been taught. Use the vocabulary, learning targets, and topics from both to create accurate, curriculum-aligned content. Adapt difficulty based on class differentiation levels below.

When scheduling multi-day lessons, skip weekends and holidays. Use get_calendar first to check for conflicts, then schedule each day sequentially on school days only.

CRITICAL: The teaching calendar is the SOURCE OF TRUTH for what the teacher is teaching on any given day. If get_calendar returns a scheduled lesson for a date, that lesson IS what the teacher is teaching — use its title, unit, and topic for any worksheet/document generation. The pacing guide and curriculum map are REFERENCE materials for planning; the calendar is what's ACTUALLY scheduled. Never override calendar entries with pacing guide suggestions.

STANDARDS & RESOURCES: The full curriculum standards and uploaded reference documents (pacing guides, calendars, curriculum docs) are included in your context above. Use them directly when generating curriculum-aligned content — you already know all the standards and have the pacing guide content. Reference specific standard codes. For additional standard details (learning targets, essential questions), use get_standards with a topic keyword. Never make up standard codes or curriculum requirements — use only what's in your context or returned by tools."""

    # Inject global AI notes (teacher's custom grading/teaching instructions)
    if global_ai_notes:
        prompt += f"\n\n## TEACHER'S INSTRUCTIONS\n{global_ai_notes}"

    # Inject class differentiation
    period_levels = _load_period_differentiation()
    if period_levels:
        level_groups = {}
        for period, level in sorted(period_levels.items()):
            level_groups.setdefault(level, []).append(period)
        diff_lines = []
        dok_map = {"advanced": "DOK 1-4", "standard": "DOK 1-3", "support": "DOK 1-2"}
        for level in ["advanced", "standard", "support"]:
            periods = level_groups.get(level, [])
            if periods:
                dok = dok_map.get(level, "DOK 1-3")
                diff_lines.append(f"- {', '.join(periods)}: {level.capitalize()} ({dok})")
        if diff_lines:
            prompt += "\n\n## CLASS DIFFERENTIATION\n" + "\n".join(diff_lines)

    # Inject accommodation summary (FERPA-safe: aggregate counts only)
    accomm = _load_accommodation_summary()
    if accomm:
        prompt += f"\n\n## ACCOMMODATIONS IN USE\n- {accomm['total_students']} students have IEP/504 accommodations"
        if accomm["preset_counts"]:
            top_presets = sorted(accomm["preset_counts"].items(), key=lambda x: -x[1])[:5]
            preset_str = ", ".join(f"{name.replace('_', ' ')} ({count})" for name, count in top_presets)
            prompt += f"\n- Common presets: {preset_str}"

    # Inject persistent memories from previous conversations
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                memories = json.load(f)
            if isinstance(memories, list) and memories:
                facts = []
                for m in memories:
                    fact = m.get("fact", m) if isinstance(m, dict) else str(m)
                    facts.append(f"- {fact}")
                prompt += "\n\n## PERSISTENT MEMORY\nThese are facts you've saved from previous conversations with this teacher:\n"
                prompt += "\n".join(facts)
                prompt += "\nUse these to personalize your responses. Save new important facts with the save_memory tool."
    except Exception:
        pass

    # Inject full curriculum standards so the assistant always knows the scope
    all_standards = _load_standards()
    if all_standards:
        std_lines = []
        for s in all_standards:
            code = s.get("code", "")
            benchmark = s.get("benchmark", "")
            dok = s.get("dok", "")
            topics = ", ".join(s.get("topics", []))
            vocab = ", ".join(s.get("vocabulary", []))
            line = f"- **{code}** (DOK {dok}): {benchmark}"
            if topics:
                line += f"  Topics: {topics}"
            if vocab:
                line += f"  Vocabulary: {vocab}"
            std_lines.append(line)
        prompt += "\n\n## CURRICULUM STANDARDS\n"
        prompt += f"All {len(all_standards)} standards for {subject} ({state}, grade {grade_level}):\n"
        prompt += "\n".join(std_lines)
        prompt += "\n\nThese are the COMPLETE standards for this subject. Reference specific codes when creating aligned content. Use get_standards tool for additional details like learning targets and essential questions."

    # Inject uploaded resource documents so the assistant has full context
    resource_content = _load_resource_content()
    if resource_content:
        prompt += "\n\n## UPLOADED REFERENCE DOCUMENTS\n"
        prompt += "The teacher has uploaded the following reference materials. Use these to answer questions about pacing, curriculum sequence, calendar scheduling, and content planning.\n"
        prompt += resource_content

    # Inject rubric settings (grading categories, weights, style)
    rubric_data = _load_rubric()
    if rubric_data:
        prompt += "\n\n## GRADING RUBRIC\n"
        prompt += f"Grading Style: {rubric_data.get('gradingStyle', 'standard')}\n"
        cats = rubric_data.get("categories", [])
        if cats:
            prompt += "Categories:\n"
            for c in cats:
                prompt += f"- {c.get('name', '')}: {c.get('description', '')} — {c.get('points', 0)} pts, weight {c.get('weight', 0)}%\n"
        if rubric_data.get("generous"):
            prompt += "Mode: Generous grading enabled (benefit of the doubt on borderline scores)\n"

    # Inject live analytics snapshot so the assistant can proactively reference performance
    analytics_snapshot = _load_analytics_snapshot()
    if analytics_snapshot:
        prompt += "\n\n## CURRENT CLASS PERFORMANCE\n"
        prompt += "Live snapshot from graded assignments. Use this to proactively offer insights and recommendations without waiting for a tool call. For deeper analysis, use tools like analyze_grade_causes or get_student_summary.\n"
        prompt += analytics_snapshot

    # Inject available ed-tech tools
    if available_tools:
        prompt += "\n\n## AVAILABLE ED-TECH TOOLS\n"
        prompt += "The teacher has these tools enabled. Reference them in lesson plans, activity suggestions, and assessment recommendations:\n"
        for tool in available_tools:
            # Custom tools like "custom:Wayground" get formatted nicely
            if tool.startswith("custom:"):
                prompt += f"- {tool.split(':', 1)[1]} (custom platform)\n"
            else:
                prompt += f"- {tool.replace('_', ' ').title()}\n"

    # Inject assessment templates (e.g., Wayground quiz format)
    templates = _load_assessment_templates()
    if templates:
        prompt += "\n\n## ASSESSMENT TEMPLATES\n"
        prompt += "These are the quiz/assessment CSV/XLSX templates the teacher has uploaded. When asked to generate a quiz for one of these platforms, produce output matching the EXACT column structure shown.\n"
        for t in templates:
            prompt += f"\n### {t['name']} ({t['platform']})\n"
            prompt += f"Format: {t['extension']}\n"
            prompt += f"Columns: {' | '.join(t['columns'])}\n"
            if t.get("question_types"):
                prompt += f"Supported question types: {', '.join(t['question_types'])}\n"
            if t.get("sample_rows"):
                prompt += "Example rows:\n"
                for row in t["sample_rows"][:2]:
                    prompt += f"  {' | '.join(str(v) for v in row)}\n"
            prompt += f"\nWhen generating quizzes for {t['platform']}, output a CSV/table with these exact columns. For Correct Answer: use the option number (1-5) for Multiple Choice, comma-separated numbers for Checkbox, leave blank for Open-Ended/Poll/Draw/Fill-in-the-Blank.\n"

    # Append platform documentation for how-to and feature questions
    manual = _load_user_manual()
    if manual:
        prompt += "\n\n## PLATFORM DOCUMENTATION\n\nWhen users ask about Graider features, how-to questions, settings, troubleshooting, or any platform-related question, use the documentation below to provide accurate, specific answers. Reference exact menu paths and steps.\n\n" + manual

    return prompt


def _audit_log(action, details=""):
    """Write to the FERPA audit log."""
    try:
        timestamp = datetime.now().isoformat()
        entry = f"{timestamp} | teacher | {action} | {details}\n"
        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(entry)
    except Exception:
        pass


logger = logging.getLogger(__name__)


def _record_assistant_cost(input_tokens, output_tokens, model, tts_chars=0):
    """Record assistant API usage to persistent JSON file."""
    from assignment_grader import MODEL_PRICING

    pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
    claude_cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    tts_cost = tts_chars * TTS_COST_PER_CHAR
    total_cost = round(claude_cost + tts_cost, 6)
    today = datetime.now().strftime("%Y-%m-%d")

    zero_entry = {
        "claude_input_tokens": 0,
        "claude_output_tokens": 0,
        "claude_cost": 0,
        "tts_chars": 0,
        "tts_cost": 0,
        "total_cost": 0,
        "api_calls": 0,
    }

    try:
        os.makedirs(os.path.dirname(ASSISTANT_COSTS_FILE), exist_ok=True)
        try:
            with open(ASSISTANT_COSTS_FILE, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"total": dict(zero_entry), "daily": {}}

        # Ensure keys exist (handles files from older versions)
        if "total" not in data:
            data["total"] = dict(zero_entry)
        if "daily" not in data:
            data["daily"] = {}

        # Update totals
        t = data["total"]
        t["claude_input_tokens"] = t.get("claude_input_tokens", 0) + input_tokens
        t["claude_output_tokens"] = t.get("claude_output_tokens", 0) + output_tokens
        t["claude_cost"] = round(t.get("claude_cost", 0) + claude_cost, 6)
        t["tts_chars"] = t.get("tts_chars", 0) + tts_chars
        t["tts_cost"] = round(t.get("tts_cost", 0) + tts_cost, 6)
        t["total_cost"] = round(t.get("total_cost", 0) + total_cost, 6)
        t["api_calls"] = t.get("api_calls", 0) + 1

        # Update daily entry
        if today not in data["daily"]:
            data["daily"][today] = dict(zero_entry)
        d = data["daily"][today]
        d["claude_input_tokens"] = d.get("claude_input_tokens", 0) + input_tokens
        d["claude_output_tokens"] = d.get("claude_output_tokens", 0) + output_tokens
        d["claude_cost"] = round(d.get("claude_cost", 0) + claude_cost, 6)
        d["tts_chars"] = d.get("tts_chars", 0) + tts_chars
        d["tts_cost"] = round(d.get("tts_cost", 0) + tts_cost, 6)
        d["total_cost"] = round(d.get("total_cost", 0) + total_cost, 6)
        d["api_calls"] = d.get("api_calls", 0) + 1

        with open(ASSISTANT_COSTS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error("Failed to record assistant cost: %s", e)

    return {
        "claude_cost": round(claude_cost, 6),
        "tts_cost": round(tts_cost, 6),
        "total_cost": total_cost,
    }


def _cleanup_stale_sessions():
    """Remove conversations older than TTL."""
    now = time.time()
    stale = [sid for sid, conv in conversations.items()
             if now - conv["last_active"] > CONVERSATION_TTL]
    for sid in stale:
        del conversations[sid]


# ═══════════════════════════════════════════════════════
# CHAT ENDPOINT (SSE STREAMING)
# ═══════════════════════════════════════════════════════

@assistant_bp.route('/api/assistant/chat', methods=['POST'])
def assistant_chat():
    """Stream chat responses with tool use via SSE."""
    model_info = _get_assistant_model()
    provider = model_info["provider"]

    # Validate provider SDK + API key
    if provider == "anthropic":
        if anthropic is None:
            return jsonify({"error": "anthropic package not installed. Run: pip install anthropic"}), 500
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY not set in .env"}), 500
    elif provider == "openai":
        if openai_pkg is None:
            return jsonify({"error": "openai package not installed. Run: pip install openai"}), 500
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"error": "OPENAI_API_KEY not set in .env"}), 500
    elif provider == "gemini":
        if genai_pkg is None:
            return jsonify({"error": "google-generativeai package not installed. Run: pip install google-generativeai"}), 500
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY not set in .env"}), 500
    else:
        return jsonify({"error": f"Unknown provider: {provider}"}), 500

    data = request.json
    if not data or not data.get("messages"):
        return jsonify({"error": "messages required"}), 400

    session_id = data.get("session_id", str(uuid.uuid4()))
    user_messages = data["messages"]
    uploaded_files = data.get("files", [])
    voice_mode = data.get("voice_mode", False)

    # Cleanup stale sessions periodically
    _cleanup_stale_sessions()

    # Get or create conversation — restore from disk if server restarted
    if session_id not in conversations:
        restored = _load_conversation(session_id)
        if restored:
            conversations[session_id] = restored
            logger.info("Restored conversation %s from disk (%d messages)", session_id, len(restored.get("messages", [])))
        else:
            conversations[session_id] = {"messages": [], "last_active": time.time()}

    conv = conversations[session_id]
    conv["last_active"] = time.time()

    # Build content blocks for files if any were uploaded
    file_content_blocks = _build_file_content_blocks(uploaded_files) if uploaded_files else []

    # Append new user message(s)
    for msg in user_messages:
        if msg.get("role") == "user":
            if file_content_blocks:
                # Multimodal message: files + text
                content_blocks = list(file_content_blocks)
                content_blocks.append({"type": "text", "text": msg["content"]})
                conv["messages"].append({"role": "user", "content": content_blocks})
            else:
                conv["messages"].append({"role": "user", "content": msg["content"]})

    _audit_log("assistant_query", f"session={session_id}")

    def generate():
        # Clear any stale cancel flag for this session
        cancelled_sessions.discard(session_id)

        messages = list(conv["messages"])

        # Voice mode: set up TTS streaming
        tts_stream = None
        sentence_buffer = None
        audio_out_queue = None
        audio_thread = None

        if voice_mode:
            try:
                from backend.services.openai_tts_service import (
                    OpenAITTSStream, SentenceBuffer
                )
                voice_choice = None
                try:
                    with open(SETTINGS_FILE, 'r') as f:
                        voice_choice = json.load(f).get("assistant_voice")
                except Exception:
                    pass
                tts_stream = OpenAITTSStream(voice=voice_choice)
                tts_stream.connect()
                sentence_buffer = SentenceBuffer()
                audio_out_queue = queue.Queue()

                def _drain_audio():
                    for b64 in tts_stream.iter_audio():
                        audio_out_queue.put(b64)
                    audio_out_queue.put(None)

                audio_thread = threading.Thread(
                    target=_drain_audio, daemon=True
                )
                audio_thread.start()
            except Exception as e:
                logging.getLogger(__name__).warning(
                    "Voice mode unavailable: %s", e
                )
                tts_stream = None

        def _flush_audio_queue():
            """Yield any available audio chunks from the queue."""
            if not audio_out_queue:
                return
            while not audio_out_queue.empty():
                try:
                    chunk = audio_out_queue.get_nowait()
                    if chunk is not None:
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': chunk})}\n\n"
                except queue.Empty:
                    break

        # Cost tracking accumulators
        total_input_tokens = 0
        total_output_tokens = 0
        total_tts_chars = 0

        # Tool use loop — may need multiple rounds
        active_model_info = model_info
        active_model = active_model_info["model"]
        active_provider = active_model_info["provider"]
        system_prompt = _build_system_prompt()
        max_rounds = 5
        for _ in range(max_rounds):
            try:
                full_response_text = ""
                tool_use_blocks = []
                deferred_tool_starts = []  # Yield after TTS flush so voice finishes first

                # ── ANTHROPIC STREAMING ──
                if active_provider == "anthropic":
                    client = anthropic.Anthropic(api_key=api_key)
                    with client.messages.stream(
                        model=active_model,
                        max_tokens=MAX_TOKENS,
                        system=system_prompt,
                        messages=messages,
                        tools=TOOL_DEFINITIONS
                    ) as stream:
                        for event in stream:
                            if session_id in cancelled_sessions:
                                break
                            if event.type == "content_block_start":
                                if hasattr(event.content_block, 'type') and event.content_block.type == "tool_use":
                                    tool_use_blocks.append({
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                        "input_json": ""
                                    })
                                    # Defer tool_start until after TTS flush so voice finishes its sentence
                                    deferred_tool_starts.append({'type': 'tool_start', 'tool': event.content_block.name, 'id': event.content_block.id})
                            elif event.type == "content_block_delta":
                                if hasattr(event.delta, 'text'):
                                    full_response_text += event.delta.text
                                    yield f"data: {json.dumps({'type': 'text_delta', 'content': event.delta.text})}\n\n"
                                    if tts_stream and sentence_buffer and session_id not in tts_muted_sessions:
                                        for sent in sentence_buffer.add(event.delta.text):
                                            text_to_speak = sent + " "
                                            tts_stream.send_text(text_to_speak)
                                            total_tts_chars += len(text_to_speak)
                                elif hasattr(event.delta, 'partial_json'):
                                    if tool_use_blocks:
                                        tool_use_blocks[-1]["input_json"] += event.delta.partial_json
                            yield from _flush_audio_queue()

                    try:
                        final_msg = stream.get_final_message()
                        if final_msg and hasattr(final_msg, 'usage') and final_msg.usage:
                            total_input_tokens += final_msg.usage.input_tokens or 0
                            total_output_tokens += final_msg.usage.output_tokens or 0
                    except Exception:
                        pass

                # ── OPENAI STREAMING ──
                elif active_provider == "openai":
                    oai_client = openai_pkg.OpenAI(api_key=api_key)
                    oai_messages = _convert_messages_for_openai(messages, system_prompt)
                    oai_tools = _convert_tools_for_openai(TOOL_DEFINITIONS)

                    stream = oai_client.chat.completions.create(
                        model=active_model,
                        messages=oai_messages,
                        tools=oai_tools,
                        max_tokens=MAX_TOKENS,
                        stream=True
                    )

                    # Accumulate tool call deltas by index
                    pending_tool_calls = {}  # index -> {id, name, arguments}
                    for chunk in stream:
                        if session_id in cancelled_sessions:
                            break
                        choice = chunk.choices[0] if chunk.choices else None
                        if not choice:
                            continue
                        delta = choice.delta

                        # Text content
                        if delta and delta.content:
                            full_response_text += delta.content
                            yield f"data: {json.dumps({'type': 'text_delta', 'content': delta.content})}\n\n"
                            if tts_stream and sentence_buffer and session_id not in tts_muted_sessions:
                                for sent in sentence_buffer.add(delta.content):
                                    text_to_speak = sent + " "
                                    tts_stream.send_text(text_to_speak)
                                    total_tts_chars += len(text_to_speak)

                        # Tool call deltas
                        if delta and delta.tool_calls:
                            for tc_delta in delta.tool_calls:
                                idx = tc_delta.index
                                if idx not in pending_tool_calls:
                                    pending_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                                if tc_delta.id:
                                    pending_tool_calls[idx]["id"] = tc_delta.id
                                if tc_delta.function and tc_delta.function.name:
                                    pending_tool_calls[idx]["name"] = tc_delta.function.name
                                    # Defer tool_start until after TTS flush
                                    deferred_tool_starts.append({'type': 'tool_start', 'tool': tc_delta.function.name, 'id': tc_delta.id or pending_tool_calls[idx]['id']})
                                if tc_delta.function and tc_delta.function.arguments:
                                    pending_tool_calls[idx]["arguments"] += tc_delta.function.arguments

                        yield from _flush_audio_queue()

                        # Capture usage from final chunk
                        if chunk.usage:
                            total_input_tokens += chunk.usage.prompt_tokens or 0
                            total_output_tokens += chunk.usage.completion_tokens or 0

                    # Convert accumulated tool calls to tool_use_blocks
                    for idx in sorted(pending_tool_calls.keys()):
                        tc = pending_tool_calls[idx]
                        if tc["name"]:
                            tool_use_blocks.append({
                                "id": tc["id"] or f"call_{idx}",
                                "name": tc["name"],
                                "input_json": tc["arguments"]
                            })

                # ── GEMINI STREAMING ──
                elif active_provider == "gemini":
                    genai_pkg.configure(api_key=api_key)
                    gemini_tools = _convert_tools_for_gemini(TOOL_DEFINITIONS)
                    gemini_model = genai_pkg.GenerativeModel(
                        active_model,
                        system_instruction=system_prompt,
                        tools=[genai_pkg.types.Tool(function_declarations=gemini_tools)]
                    )

                    # Build Gemini chat history from messages
                    gemini_history = []
                    for msg in messages:
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        gemini_role = "model" if role == "assistant" else "user"

                        if isinstance(content, list):
                            # Handle tool results
                            parts = []
                            for block in content:
                                if isinstance(block, dict):
                                    if block.get("type") == "tool_result":
                                        parts.append(genai_pkg.types.Part.from_function_response(
                                            name="tool_response",
                                            response={"result": block.get("content", "")}
                                        ))
                                    elif block.get("type") == "text":
                                        parts.append(block["text"])
                                    elif block.get("type") == "tool_use":
                                        parts.append(genai_pkg.types.Part.from_function_response(
                                            name=block.get("name", ""),
                                            response=block.get("input", {})
                                        ))
                            if parts:
                                gemini_history.append({"role": gemini_role, "parts": parts})
                        else:
                            gemini_history.append({"role": gemini_role, "parts": [content]})

                    # Start chat and send last user message
                    chat = gemini_model.start_chat(history=gemini_history[:-1] if gemini_history else [])
                    last_parts = gemini_history[-1]["parts"] if gemini_history else ["Hello"]

                    response = chat.send_message(last_parts, stream=True)
                    for chunk in response:
                        if session_id in cancelled_sessions:
                            break
                        if chunk.text:
                            full_response_text += chunk.text
                            yield f"data: {json.dumps({'type': 'text_delta', 'content': chunk.text})}\n\n"
                            if tts_stream and sentence_buffer and session_id not in tts_muted_sessions:
                                for sent in sentence_buffer.add(chunk.text):
                                    text_to_speak = sent + " "
                                    tts_stream.send_text(text_to_speak)
                                    total_tts_chars += len(text_to_speak)
                        yield from _flush_audio_queue()

                    # Check for function calls in the final response
                    try:
                        for candidate in response.candidates:
                            for part in candidate.content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    fc = part.function_call
                                    tool_id = f"gemini_{fc.name}_{uuid.uuid4().hex[:8]}"
                                    tool_use_blocks.append({
                                        "id": tool_id,
                                        "name": fc.name,
                                        "input_json": json.dumps(dict(fc.args)) if fc.args else "{}"
                                    })
                                    # Defer tool_start until after TTS flush
                                    deferred_tool_starts.append({'type': 'tool_start', 'tool': fc.name, 'id': tool_id})
                    except Exception:
                        pass

                    # Capture token usage
                    try:
                        if hasattr(response, 'usage_metadata') and response.usage_metadata:
                            total_input_tokens += getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
                            total_output_tokens += getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
                    except Exception:
                        pass

                # ── POST-STREAM (shared across all providers) ──

                # If cancelled or no tool calls, we're done
                if session_id in cancelled_sessions:
                    if full_response_text:
                        conv["messages"].append({"role": "assistant", "content": full_response_text})
                    break

                if not tool_use_blocks:
                    conv["messages"].append({"role": "assistant", "content": full_response_text})
                    break

                # Flush TTS sentence buffer and wait for ALL audio to be generated
                # before tool execution, so the voice finishes its sentence first
                if tts_stream and sentence_buffer and session_id not in tts_muted_sessions:
                    remaining = sentence_buffer.flush()
                    if remaining:
                        text_to_speak = remaining + " "
                        tts_stream.send_text(text_to_speak)
                        total_tts_chars += len(text_to_speak)
                    tts_stream.flush()
                    tts_stream.wait_for_flush(timeout=5.0)
                    yield from _flush_audio_queue()

                # Now that voice audio is fully sent, notify frontend about tool calls
                for ts_event in deferred_tool_starts:
                    yield f"data: {json.dumps(ts_event)}\n\n"

                # Build the assistant message with all content blocks (Anthropic format for conversation store)
                assistant_content = []
                if full_response_text:
                    assistant_content.append({"type": "text", "text": full_response_text})

                tool_results = []
                for tb in tool_use_blocks:
                    if session_id in cancelled_sessions:
                        break

                    try:
                        tool_input = json.loads(tb["input_json"]) if tb["input_json"] else {}
                    except json.JSONDecodeError:
                        tool_input = {}

                    assistant_content.append({
                        "type": "tool_use",
                        "id": tb["id"],
                        "name": tb["name"],
                        "input": tool_input
                    })

                    yield from _flush_audio_queue()

                    _audit_log("tool_call", f"tool={tb['name']} session={session_id}")
                    result = execute_tool(tb["name"], tool_input)
                    result_str = json.dumps(result)

                    yield from _flush_audio_queue()

                    preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
                    event_data = {'type': 'tool_result', 'tool': tb['name'], 'id': tb['id'], 'result_preview': preview}

                    if isinstance(result, dict):
                        dl_url = result.get('download_url')
                        dl_name = result.get('filename')
                        if dl_url:
                            event_data['download_url'] = dl_url
                            event_data['download_filename'] = dl_name
                        dl_urls = result.get('download_urls')
                        if dl_urls:
                            event_data['download_urls'] = dl_urls

                    yield f"data: {json.dumps(event_data)}\n\n"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tb["id"],
                        "content": result_str
                    })

                if session_id in cancelled_sessions:
                    break

                # Add assistant message and tool results to conversation (stored in Anthropic format)
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            except Exception as e:
                error_msg = str(e)
                if "APIError" in type(e).__name__ or "AuthenticationError" in type(e).__name__:
                    error_msg = f"API error ({active_provider}): {error_msg}"
                yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
                break

        # Update stored conversation with the final messages and persist to disk
        conv["messages"] = messages
        _persist_conversation(session_id)

        # Flush remaining TTS audio (skip if muted)
        if tts_stream:
            if session_id not in tts_muted_sessions and sentence_buffer:
                remaining = sentence_buffer.flush()
                if remaining:
                    text_to_speak = remaining + " "
                    tts_stream.send_text(text_to_speak)
                    total_tts_chars += len(text_to_speak)
                tts_stream.flush()
                tts_stream.wait_for_flush(timeout=5.0)
            tts_stream.close()
            # Drain final audio chunks (only if not muted)
            if audio_out_queue and session_id not in tts_muted_sessions:
                while True:
                    try:
                        chunk = audio_out_queue.get(timeout=3.0)
                        if chunk is None:
                            break
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': chunk})}\n\n"
                    except queue.Empty:
                        break
            # Clear mute flag for next request
            tts_muted_sessions.discard(session_id)

        # Clear cancel flag
        cancelled_sessions.discard(session_id)

        # Record and send cost summary
        if total_input_tokens > 0 or total_tts_chars > 0:
            cost_info = _record_assistant_cost(
                total_input_tokens, total_output_tokens,
                active_model, total_tts_chars
            )
            yield f"data: {json.dumps({'type': 'cost', 'input_tokens': total_input_tokens, 'output_tokens': total_output_tokens, 'tts_chars': total_tts_chars, **cost_info})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


# ═══════════════════════════════════════════════════════
# CONVERSATION MANAGEMENT
# ═══════════════════════════════════════════════════════

@assistant_bp.route('/api/assistant/clear', methods=['POST'])
def clear_conversation():
    """Clear conversation history for a session."""
    data = request.json or {}
    session_id = data.get("session_id")
    if session_id:
        conversations.pop(session_id, None)
        _persist_conversation(session_id)  # Removes from disk file
    return jsonify({"status": "cleared"})


@assistant_bp.route('/api/assistant/mute-tts', methods=['POST'])
def mute_tts():
    """Mute TTS for a session — stops sending text to TTS mid-stream."""
    data = request.json or {}
    session_id = data.get("session_id")
    if session_id:
        tts_muted_sessions.add(session_id)
    return jsonify({"status": "muted"})


@assistant_bp.route('/api/assistant/cancel', methods=['POST'])
def cancel_stream():
    """Cancel an active assistant stream — stops tool execution loop."""
    data = request.json or {}
    session_id = data.get("session_id")
    if session_id:
        cancelled_sessions.add(session_id)
        tts_muted_sessions.add(session_id)  # Also mute TTS
    return jsonify({"status": "cancelled"})


# ═══════════════════════════════════════════════════════
# COST TRACKING
# ═══════════════════════════════════════════════════════

@assistant_bp.route('/api/assistant/costs', methods=['GET'])
def get_assistant_costs():
    """Return assistant API cost summary (total + daily breakdown)."""
    try:
        with open(ASSISTANT_COSTS_FILE, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({
            "total": {
                "claude_input_tokens": 0,
                "claude_output_tokens": 0,
                "claude_cost": 0,
                "tts_chars": 0,
                "tts_cost": 0,
                "total_cost": 0,
                "api_calls": 0,
            },
            "daily": {}
        })


# ═══════════════════════════════════════════════════════
# PERSISTENT MEMORY
# ═══════════════════════════════════════════════════════

@assistant_bp.route('/api/assistant/memory', methods=['GET'])
def get_memory():
    """Return all saved assistant memories."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                memories = json.load(f)
            if isinstance(memories, list):
                facts = []
                for m in memories:
                    fact = m.get("fact", m) if isinstance(m, dict) else str(m)
                    facts.append(fact)
                return jsonify({"memories": facts, "count": len(facts)})
        except Exception:
            pass
    return jsonify({"memories": [], "count": 0})


@assistant_bp.route('/api/assistant/memory', methods=['DELETE'])
def clear_memory():
    """Clear all saved assistant memories."""
    if os.path.exists(MEMORY_FILE):
        try:
            os.remove(MEMORY_FILE)
        except Exception as e:
            return jsonify({"error": f"Failed to clear memory: {str(e)}"}), 500
    _audit_log("memory_cleared", "All assistant memories cleared")
    return jsonify({"status": "cleared"})


# ═══════════════════════════════════════════════════════
# VPORTAL CREDENTIALS
# ═══════════════════════════════════════════════════════

@assistant_bp.route('/api/assistant/credentials', methods=['POST'])
def save_credentials():
    """Save VPortal credentials (base64 obfuscated)."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = data.get('email', '')
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    os.makedirs(GRAIDER_DATA_DIR, exist_ok=True)

    encoded = base64.b64encode(password.encode()).decode()
    with open(CREDS_FILE, 'w') as f:
        json.dump({"email": email, "password": encoded}, f)

    _audit_log("credentials_saved", "VPortal credentials updated")
    return jsonify({"status": "saved"})


@assistant_bp.route('/api/assistant/credentials', methods=['GET'])
def get_credentials():
    """Check if VPortal credentials are configured (never returns password)."""
    if os.path.exists(CREDS_FILE):
        try:
            with open(CREDS_FILE, 'r') as f:
                data = json.load(f)
            return jsonify({"configured": True, "email": data.get("email", "")})
        except Exception:
            pass
    return jsonify({"configured": False})


# ═══════════════════════════════════════════════════════
# VOICE CONFIGURATION
# ═══════════════════════════════════════════════════════

@assistant_bp.route('/api/assistant/voice-config', methods=['GET'])
def get_voice_config():
    """Return voice TTS configuration status."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    voice = os.environ.get("OPENAI_TTS_VOICE", "nova")
    try:
        with open(SETTINGS_FILE, 'r') as f:
            voice = json.load(f).get("assistant_voice", voice)
    except Exception:
        pass
    return jsonify({
        "enabled": bool(api_key),
        "voice": voice,
        "voice_name": voice.capitalize(),
        "voices": OPENAI_TTS_VOICES,
    })
