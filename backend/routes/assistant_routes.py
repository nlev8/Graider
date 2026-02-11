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
from datetime import datetime

from flask import Blueprint, request, jsonify, Response, stream_with_context

try:
    import anthropic
except ImportError:
    anthropic = None

from backend.services.assistant_tools import TOOL_DEFINITIONS, execute_tool

assistant_bp = Blueprint('assistant', __name__)

# ═══════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════

GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
CREDS_FILE = os.path.join(GRAIDER_DATA_DIR, "portal_credentials.json")
AUDIT_LOG_FILE = os.path.expanduser("~/.graider_audit.log")

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096

# In-memory conversation store {session_id: {"messages": [...], "last_active": timestamp}}
conversations = {}
CONVERSATION_TTL = 7200  # 2 hours

SETTINGS_FILE = os.path.expanduser("~/.graider_settings.json")


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


def _build_system_prompt():
    """Build the system prompt dynamically, injecting teacher info from settings."""
    teacher_name = ""
    subject = ""
    school_name = ""
    teacher_email = ""
    email_signature = ""
    grade_level = ""

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
        if school_name:
            parts.append(f"School: {school_name}")
        if teacher_email:
            parts.append(f"Email: {teacher_email}")
        if email_signature:
            parts.append(f"Email Signature:\n{email_signature}")
        teacher_context = "\n\nTeacher Information (use this for email signatures, letters, and communications):\n" + "\n".join(parts)

    return f"""You are a helpful teaching assistant built into Graider, an AI-powered grading tool. You help teachers understand student performance, analyze grades, and manage their gradebook.{teacher_context}

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
- lookup_student_info: Look up student roster and contact information — student IDs, local IDs, grade level, period, student email, parent emails, parent phone numbers. Search by name, ID, or list all students in a period. Supports BATCH lookup via student_ids array. Use this when the teacher asks for contact info, emails, parent emails, phone numbers, or student IDs. IMPORTANT: query_grades results include student_id — when you need parent emails for multiple students (e.g., failing students), first use query_grades to get their student_ids, then use lookup_student_info with the student_ids array to get all their contacts in one call.
- get_missing_assignments: Find missing/unsubmitted work. Search by student (what are they missing?), by period (who has missing work?), or by assignment (who hasn't turned in X?). Use this when teacher asks about missing work, incomplete submissions, or which students haven't turned in assignments.
- generate_worksheet: Create downloadable worksheet documents (Cornell Notes, fill-in-blank, short-answer, vocabulary) with built-in answer keys for AI grading. Automatically saved to Grading Setup. When the teacher uploads a textbook page or reading and asks for a worksheet, ALWAYS use this tool. Extract vocab terms, write questions with expected answers, and include summary key points. The worksheet will have an invisible answer key embedded for consistent grading.
- generate_document: Create formatted Word documents with rich typography (headings, bold, italic, lists, tables). Use for study guides, reference sheets, parent letters, lesson outlines, rubrics, or any document. NOT for gradeable worksheets.
- save_document_style: Save the visual formatting of a document (fonts, sizes, colors) as a reusable style. Use when the teacher says they like how a document looks and want that same look for future documents of that type.
- list_document_styles: Check what saved visual styles exist. Use before generating a document to see if a matching style is available.
- create_focus_assignment: Create assignment in Focus gradebook (browser automation)
- export_grades_csv: Export grades as Focus-compatible CSV files

When a teacher asks "why did students do poorly" or "what caused the low grades", ALWAYS use analyze_grade_causes — it provides rubric category breakdown, unanswered question data, and the score impact of omissions. This is your most powerful diagnostic tool.

When a teacher asks "what should I teach next?" or "what lesson would help with these weaknesses?", use recommend_next_lesson — it analyzes performance data and cross-references curriculum standards to suggest targeted lesson topics. You can also call analyze_grade_causes first, then recommend_next_lesson to give a complete diagnostic + prescription response.

DIFFERENTIATION: recommend_next_lesson now returns a class_level_breakdown with separate analysis for advanced, standard, and support periods. Each level gets DOK-appropriate standard recommendations (DOK 1-2 for support, DOK 1-3 for standard, DOK 1-4 for advanced). When presenting lesson recommendations, ALWAYS address each class level separately if the data shows different levels. Suggest scaffolded activities for support classes, grade-level work for standard, and extension/analytical work for advanced.

IEP/504 AWARENESS: recommend_next_lesson also returns accommodation_analysis showing how IEP/504 students performed compared to non-accommodated peers. If there is a score gap or distinct weakness pattern, mention it and suggest modifications (extended time, simplified prompts, graphic organizers, chunked assignments, etc.). Always handle accommodation data sensitively — never list individual IEP student names, only aggregate patterns.

DOCUMENT GENERATION: When generating any document or worksheet, first call list_document_styles to check if a matching saved style exists, and if so, pass the style_name parameter. Use generate_document for non-gradeable documents (study guides, reference sheets, parent letters, lesson outlines). Use generate_worksheet for gradeable assignments. Both support rich formatting: **bold**, *italic*, and ***bold+italic*** in text content. When the teacher says they like a document's formatting, use save_document_style to save it for future reuse.

SAVING DOCUMENTS: After generating a document with generate_document, always ask the teacher: "Would you like me to save this to your assignments in Grading Setup?" If they say yes, call generate_document again with the same content and save_to_builder=true. Worksheets created with generate_worksheet are always saved to Grading Setup automatically."""


def _audit_log(action, details=""):
    """Write to the FERPA audit log."""
    try:
        timestamp = datetime.now().isoformat()
        entry = f"{timestamp} | teacher | {action} | {details}\n"
        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(entry)
    except Exception:
        pass


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
    if anthropic is None:
        return jsonify({"error": "anthropic package not installed. Run: pip install anthropic"}), 500

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set in .env"}), 500

    data = request.json
    if not data or not data.get("messages"):
        return jsonify({"error": "messages required"}), 400

    session_id = data.get("session_id", str(uuid.uuid4()))
    user_messages = data["messages"]
    uploaded_files = data.get("files", [])

    # Cleanup stale sessions periodically
    _cleanup_stale_sessions()

    # Get or create conversation
    if session_id not in conversations:
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
        client = anthropic.Anthropic(api_key=api_key)
        messages = list(conv["messages"])

        # Tool use loop — may need multiple rounds
        max_rounds = 5
        for _ in range(max_rounds):
            try:
                full_response_text = ""
                tool_use_blocks = []

                with client.messages.stream(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=_build_system_prompt(),
                    messages=messages,
                    tools=TOOL_DEFINITIONS
                ) as stream:
                    for event in stream:
                        if event.type == "content_block_start":
                            if hasattr(event.content_block, 'type'):
                                if event.content_block.type == "tool_use":
                                    tool_use_blocks.append({
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                        "input_json": ""
                                    })
                                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': event.content_block.name, 'id': event.content_block.id})}\n\n"

                        elif event.type == "content_block_delta":
                            if hasattr(event.delta, 'text'):
                                full_response_text += event.delta.text
                                yield f"data: {json.dumps({'type': 'text_delta', 'content': event.delta.text})}\n\n"
                            elif hasattr(event.delta, 'partial_json'):
                                if tool_use_blocks:
                                    tool_use_blocks[-1]["input_json"] += event.delta.partial_json

                # If no tool calls, we're done
                if not tool_use_blocks:
                    conv["messages"].append({"role": "assistant", "content": full_response_text})
                    break

                # Build the assistant message with all content blocks
                assistant_content = []
                if full_response_text:
                    assistant_content.append({"type": "text", "text": full_response_text})

                tool_results = []
                for tb in tool_use_blocks:
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

                    # Execute the tool
                    _audit_log("tool_call", f"tool={tb['name']} session={session_id}")
                    result = execute_tool(tb["name"], tool_input)
                    result_str = json.dumps(result)

                    # Send tool result preview to client
                    preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
                    event_data = {'type': 'tool_result', 'tool': tb['name'], 'id': tb['id'], 'result_preview': preview}

                    # Include download URL(s) from any tool that generates files
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

                # Add assistant message and tool results to conversation
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            except anthropic.APIError as e:
                yield f"data: {json.dumps({'type': 'error', 'content': f'API error: {str(e)}'})}\n\n"
                break
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {str(e)}'})}\n\n"
                break

        # Update stored conversation with the final messages
        conv["messages"] = messages

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
    if session_id and session_id in conversations:
        del conversations[session_id]
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
