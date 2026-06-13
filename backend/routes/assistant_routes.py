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

from flask import Blueprint, request, jsonify, Response, stream_with_context, g
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors
from backend.extensions import limiter
from backend.paths import graider_export_dir

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai as openai_pkg
except ImportError:
    openai_pkg = None

try:
    from google import genai as genai_pkg
except ImportError:
    genai_pkg = None

from backend.services.assistant_tools import (
    TOOL_DEFINITIONS, execute_tool, _merge_submodules,
    _load_standards,
    DOCUMENTS_DIR,
)
from backend.services.assistant_tools_reports import _extract_pdf_text, _extract_docx_text
import sentry_sdk
import pybreaker

from backend.services.llm_adapter.breakers import get_breaker
from backend.services.llm_adapter import (
    AnthropicAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    LLMRequest,
    Message,
    TextPart,
    ImagePart,
    ToolUsePart,
    ToolResultPart,
    ToolDef,
    TextDelta,
    ToolCallDelta,
    ToolCallComplete,
    UsageEvent,
    FinishEvent,
)

# Import storage abstraction for per-teacher credential isolation
try:
    from backend.storage import load as storage_load, save as storage_save
except ImportError:
    try:
        from storage import load as storage_load, save as storage_save
    except ImportError:
        storage_load = None
        storage_save = None

assistant_bp = Blueprint('assistant', __name__)

# ═══════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════

GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
CREDS_FILE = os.path.join(GRAIDER_DATA_DIR, "portal_credentials.json")  # legacy local-dev path

# Closes GH #245 (Codex review of PR #244): the legacy shared CREDS_FILE
# was overwritten by every real teacher's save and read by every real
# teacher's get/load, leaking VPortal credentials across tenants. Real
# teachers now use per-teacher files keyed by sanitized teacher_id;
# local-dev keeps the legacy shared file for back-compat with subprocess
# launchers that hard-coded the path.
def _portal_credentials_file_for(teacher_id):
    """Return the per-teacher VPortal credentials file path.

    For real teachers: `portal_credentials_{safe_id}.json` under
    GRAIDER_DATA_DIR, isolated per teacher.
    For local-dev: legacy shared file (preserves subprocess workflow).
    """
    if not teacher_id or teacher_id == 'local-dev':
        return CREDS_FILE
    safe_id = str(teacher_id).replace(':', '_').replace('/', '_').replace('\\', '_')
    return os.path.join(GRAIDER_DATA_DIR, f"portal_credentials_{safe_id}.json")
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
        # Check config sub-object first, then top-level for backwards compat
        choice = settings.get("config", {}).get("assistant_model") or settings.get("assistant_model", DEFAULT_MODEL)
        return ASSISTANT_MODELS.get(choice, ASSISTANT_MODELS[DEFAULT_MODEL])
    except Exception:  # noqa: BLE001  # broad catch: returns fallback
        return ASSISTANT_MODELS[DEFAULT_MODEL]


def _wire_messages_to_llm_messages(wire_messages: list) -> list[Message]:
    """Convert the route's Anthropic-wire-format message dicts to typed Message objects.

    The conversation store uses Anthropic wire format throughout (tool_use /
    tool_result blocks in content lists). This function maps those to the
    adapter layer's LLMRequest.Message typed objects so all three adapters
    can use the same LLMRequest.
    """
    result: list[Message] = []
    for msg in wire_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            result.append(Message(role=role, content=[TextPart(text=content)]))
            continue

        # content is a list of blocks
        parts = []
        tool_result_parts = []

        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")

            if btype == "text":
                parts.append(TextPart(text=block.get("text", "")))

            elif btype == "image":
                src = block.get("source", {})
                if src.get("type") == "base64":
                    parts.append(ImagePart(
                        url=None,
                        base64=src.get("data", ""),
                        mime_type=src.get("media_type", "image/png"),
                    ))
                else:
                    parts.append(ImagePart(
                        url=src.get("url", ""),
                        base64=None,
                        mime_type=src.get("media_type", "image/png"),
                    ))

            elif btype == "tool_use":
                # Assistant message with a tool call
                parts.append(ToolUsePart(
                    tool_call_id=block.get("id", ""),
                    name=block.get("name", ""),
                    args=block.get("input", {}),
                ))

            elif btype == "tool_result":
                # User message carrying tool results — collected separately
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    # Sometimes content is a list of text blocks
                    result_content = " ".join(
                        b.get("text", "") for b in result_content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                tool_result_parts.append(ToolResultPart(
                    tool_call_id=block.get("tool_use_id", ""),
                    content=result_content,
                ))

        if tool_result_parts:
            # Tool result messages: one Message per result, role="tool"
            for trp in tool_result_parts:
                result.append(Message(
                    role="tool",
                    content=[trp],
                    tool_call_id=trp.tool_call_id,
                ))
        elif parts:
            result.append(Message(role=role, content=parts))

    return result


def _build_llm_request(
    model: str,
    messages: list,
    system_prompt: str,
    tools: list,
    max_tokens: int,
) -> LLMRequest:
    """Build a typed LLMRequest from Anthropic-wire-format route data."""
    typed_messages = _wire_messages_to_llm_messages(messages)
    typed_tools = [
        ToolDef(
            name=t["name"],
            description=t.get("description", ""),
            input_schema=t.get("input_schema", {"type": "object", "properties": {}}),
        )
        for t in tools
    ]
    return LLMRequest(
        model=model,
        messages=typed_messages,
        system_prompt=system_prompt,
        tools=typed_tools,
        max_tokens=max_tokens,
    )


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
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        logger.warning("Failed to persist conversation %s: %s", session_id, e)


def _load_conversation(session_id):
    """Load a conversation from disk if it exists."""
    try:
        if os.path.exists(CONVERSATIONS_FILE):
            with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
                all_convs = json.load(f)
            if session_id in all_convs:
                return all_convs[session_id]
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        logger.warning("Failed to load conversation %s: %s", session_id, e)
    return None

# Per-session TTS mute flag — set by frontend to stop TTS mid-stream
tts_muted_sessions = set()

# Per-session cancellation flag — stops the tool loop when user clicks Stop
cancelled_sessions = set()

# Phase 5b PR 4 — finalizer idempotency registry.
# Prevents double-cleanup when GeneratorExit races with normal-completion
# yield-from. See docs/superpowers/specs/2026-04-23-phase5b-hardening-design.md § PR 4.
_finalizing_sessions: set = set()
_finalizing_lock = threading.Lock()

# Tracks sessions whose cost has already been recorded. Step 9 of the
# finalizer is the only non-idempotent side effect (it writes a new cost
# row to disk); the other steps (_persist_conversation, tts_stream.close,
# set.discard, conv["messages"] assignment) are all idempotent or wrapped
# in try/except. Guarding step 9 specifically prevents double-billing on
# the GeneratorExit-mid-drain race where the inner finalizer's finally
# releases _finalizing_sessions before the outer except GeneratorExit
# fires the silent wrapper.
_cost_recorded_sessions: set = set()
_COST_RECORDED_CAP = 10000  # simple eviction when this many sessions accumulate

SETTINGS_FILE = os.path.expanduser("~/.graider_settings.json")
RUBRIC_FILE = os.path.expanduser("~/.graider_rubric.json")
MEMORY_FILE = os.path.join(GRAIDER_DATA_DIR, "assistant_memory.json")
ASSISTANT_COSTS_FILE = os.path.join(GRAIDER_DATA_DIR, "assistant_costs.json")

# OpenAI TTS pricing — $0.015 per 1K characters (tts-1 model)
TTS_COST_PER_CHAR = 0.000015
OPENAI_TTS_VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]

# Token cost guardrails
MAX_TOOL_RESPONSE_CHARS = 8000   # Truncate tool results larger than this
COST_WARNING_THRESHOLD = 0.25    # Warn teacher when per-query cost exceeds this
MAX_TOOL_ROUNDS = 5              # Max tool loop iterations — enough for multi-step reasoning
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
    except Exception:  # noqa: BLE001  # broad catch: falls back to default
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
    except Exception as e:  # noqa: BLE001  # broad catch: returns fallback
        return "[Error extracting PDF]"


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
    except Exception as e:  # noqa: BLE001  # broad catch: returns fallback
        return "[Error extracting DOCX]"


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
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        # Best-effort: period metadata is optional context for class-level
        # differentiation. Falls back to defaults.
        logger.debug("Failed to load period class levels: %s", e)
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
    except Exception:  # noqa: BLE001  # broad catch: returns fallback
        return None


def _load_resource_names():
    """Load just filenames + descriptions of uploaded resources (no content).

    Returns list of strings like "filename.docx — Pacing guide (curriculum)".
    Full content is fetched on demand via read_resource tool.
    """
    if not os.path.isdir(DOCUMENTS_DIR):
        return []
    names = []
    try:
        for fname in sorted(os.listdir(DOCUMENTS_DIR)):
            if fname.endswith('.meta.json'):
                continue
            fpath = os.path.join(DOCUMENTS_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            meta_path = fpath + ".meta.json"
            meta = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                except Exception as e:  # noqa: BLE001  # broad catch: error is logged
                    # Best-effort: malformed metadata uses defaults below.
                    logger.debug("Failed to load doc metadata %s: %s", meta_path, e)
            doc_type = meta.get("doc_type", "general")
            description = meta.get("description", "")
            entry = fname
            if description:
                entry += f" — {description}"
            entry += f" ({doc_type})"
            names.append(entry)
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        # Best-effort: directory enumeration failed. Returns whatever names
        # were collected before the failure.
        logger.debug("Failed to enumerate support documents: %s", e)
    return names


# Cap total injected resource text at 120K chars (~30K tokens)
MAX_RESOURCE_INJECTION = 120000


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
                except Exception as e:  # noqa: BLE001  # broad catch: error is logged
                    # Best-effort: malformed metadata uses defaults below.
                    logger.debug("Failed to load doc metadata %s: %s", meta_path, e)

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
            except Exception:  # noqa: BLE001  # broad catch: error is logged
                logger.debug("attachment text extraction failed", exc_info=True)
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

    except Exception:  # noqa: BLE001  # broad catch: returns fallback
        return ""

    return "\n\n".join(sections)


def _load_rubric():
    """Load grading rubric settings."""
    try:
        if os.path.exists(RUBRIC_FILE):
            with open(RUBRIC_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        # User-visible behavior change: silent rubric load failure means the
        # assistant loses the teacher's custom rubric block from the system
        # prompt and falls back to default grading context. Sentry must see
        # this so the corrupted config gets fixed instead of teachers
        # wondering why grading behaves differently.
        # Per Codex review: log basename only (this line ships at WARNING
        # in production; absolute paths leak host/home-path details).
        logger.warning("Failed to load rubric file (%s): %s",
                       os.path.basename(RUBRIC_FILE), e)
        sentry_sdk.capture_exception(e)
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
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        # Best-effort: returns whatever templates were loaded successfully.
        logger.debug("Failed to enumerate platform templates: %s", e)
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
    output_folder = graider_export_dir("Results")
    settings_file = os.path.expanduser("~/.graider_global_settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                gs = json.load(f)
            output_folder = gs.get('output_folder', output_folder)
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            # Best-effort: malformed settings file uses the existing
            # output_folder value (caller-supplied or default).
            logger.debug("Failed to load output_folder from settings file: %s", e)

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
                        logger.debug("Non-numeric %s value skipped in category breakdown", cat)

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

    except Exception:  # noqa: BLE001  # broad catch: returns fallback
        return ""


def _base_assistant_system_prompt(teacher_context):
    """Build the base Graider assistant system prompt (before the per-teacher context
    injections). Returns the prompt string. Extracted verbatim (the f-string literal is
    byte-identical) from _build_system_prompt (Code Quality 6→7 split)."""
    return f"""You are a helpful teaching assistant built into Graider, an AI-powered grading tool. You help teachers understand student performance, analyze grades, and manage their gradebook.{teacher_context}

Key guidelines:
- Be concise and teacher-friendly. Use markdown formatting (bold, lists) when helpful.
- When asked about grades or students, use the available tools to query actual data — never guess or make up numbers.
- Respect FERPA: minimize personally identifiable information in your responses. Use first names only when discussing individual students. Never share data outside this conversation.
- When showing multiple students, use tables for clarity.
- NEVER truncate, abbreviate, or omit tool results. Always display ALL entries returned by a tool. If a tool returns 10 items, show all 10 with complete data. Never write "[Truncated]" or "please specify for full details".
- If data is unavailable, say so clearly and suggest what the teacher can do (e.g., "Grade some assignments first").
- For Focus automation, always confirm what will be created before triggering it.
- All student data stays local on the teacher's machine. Tool results come from local files only.
- When drafting emails or communications, use the teacher's name, subject, school, and email signature from the teacher information above. Always sign off with their configured signature.
- CRITICAL: When the teacher tells you to send a message and provides the facts (e.g., "his assignments are all blank", "she has 5 missing assignments"), trust what the teacher says and compose the message immediately. Do NOT look up or verify the teacher's claims with extra tool calls. The teacher knows their students — just write the email with the information they gave you and send it. Only use lookup tools if the teacher explicitly asks you to find out information (e.g., "check which assignments are missing").

Available tools:
- query_grades: Search/filter grades by student, assignment, period, score range
- get_student_summary: Deep dive into one student's performance and trends
- get_class_analytics: Class-wide stats, grade distribution, top/bottom performers
- get_assignment_stats: Statistics for a specific assignment
- list_assignments: Show all graded assignments
- scan_submissions_folder: Scan the assignments folder to see what files have been submitted. Shows top assignments by submission count, graded/ungraded counts, and student counts. Deduplicates multiple uploads. Use when asked about submissions, folder contents, or 'what's been turned in' — this scans actual files, not grading results. IMPORTANT: Always display ALL results returned by this tool — NEVER truncate, abbreviate, or omit any entries. Show every assignment with its full name and all numbers. Use a simple numbered list format, not tables.
- analyze_grade_causes: Deep analysis of WHY students got low grades — rubric category breakdowns, unanswered/omitted questions, score impact of omissions, weakest categories. Use this when asked about causes of low grades, common mistakes, or what students struggled with.
- get_feedback_patterns: Analyze feedback text and skills across an assignment — common strengths, areas for growth, feedback samples from high/low scorers. Use when asked about patterns or common issues.
- compare_periods: Compare performance across class periods — averages, grade distributions, category breakdowns, omission rates per period.
- recommend_next_lesson: Analyze weaknesses and recommend what to teach next. Now includes DIFFERENTIATED recommendations by class level (advanced/standard/support) with DOK-appropriate standards, and IEP/504 accommodation analysis. Use when teacher asks "what should I teach next?", "how should I differentiate?", or "what lesson would help?"
- lookup_student_info: Look up student roster and contact information — student IDs, local IDs, grade level, period, course codes, student email, parent emails, parent phone numbers, 504 plan status, detailed contacts (up to 3 with names, relationships, and roles), and full student schedule (all periods with teachers and courses). Search by name, ID, or list all students in a period. Supports BATCH lookup via student_ids array. Use this when the teacher asks for contact info, emails, parent emails, phone numbers, student IDs, who a student's other teachers are, or 504/accommodation status. IMPORTANT: query_grades results include student_id — when you need parent emails for multiple students (e.g., failing students), first use query_grades to get their student_ids, then use lookup_student_info with the student_ids array to get all their contacts in one call.
- get_missing_assignments: Find missing/unsubmitted work. Four modes: (1) by student_name — what assignments are they missing? (2) by period — who in that period has missing work? (3) by assignment_name — who hasn't turned in X? (4) NO params or period="all" — compact summary of ALL periods showing zero-submission students. IMPORTANT: When the teacher asks "who hasn't submitted anything" or "students with zero submissions", call with NO parameters (or period="all") to get the all-periods summary in ONE call. Do NOT call once per period.
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
- get_recent_lessons: List saved lesson plans by unit. Shows topics, standards covered, vocabulary, and objectives from past lessons. Use when the teacher asks "what have we been working on", references past lessons, or when you need lesson context for generating content the teacher explicitly requested.
- save_memory: Save important facts about the teacher or their classes for future conversations. Use when the teacher shares preferences, class structure, or workflow habits.

RESOURCE TOOLS:
- list_resources: List all uploaded supporting documents with metadata.
- read_resource: Read the full text content of a specific uploaded document. Use if you need to re-read or if document content was truncated in the system context above.

TEACHING CALENDAR TOOLS:
- get_calendar: Read the teaching calendar for a date range. Shows scheduled lessons and holidays. AUTHORITATIVE — if it returns lessons, those ARE what the teacher is teaching. Never say "nothing is scheduled" when scheduled_lessons is non-empty. When asked about a specific day (e.g. "Tuesday"), query that exact date. When generating worksheets for a date, the worksheet topic MUST match the scheduled lesson for that date. Defaults to the next 7 days.
- schedule_lesson: Place a saved lesson onto the calendar on a specific date. For multi-day lessons, you MUST call this once for EACH school day from start through end date — do not stop early. Use incrementing day_number (1, 2, 3...) and skip weekends/holidays. If the teacher says "Wed-Fri", that means Wednesday AND Thursday AND Friday — all three days. Always count the days explicitly before scheduling to ensure none are missed.
- add_calendar_holiday: Mark a date (or date range) as a holiday or break. Use when the teacher says "we're off next Friday", "add Spring Break March 16-20", or "mark Monday as a teacher workday".

When generating worksheets or quizzes, ALWAYS call get_standards first to find relevant standards, and get_recent_lessons to see what's been taught. Use the vocabulary, learning targets, and topics from both to create accurate, curriculum-aligned content. Adapt difficulty based on class differentiation levels below.

When scheduling multi-day lessons, FIRST enumerate every school day from start through end date (skip weekends and holidays), THEN schedule each one. Double-check your count matches the teacher's request before confirming. Use get_calendar first to check for conflicts.

CRITICAL: The teaching calendar is the SOURCE OF TRUTH for what the teacher is teaching on any given day. If get_calendar returns a scheduled lesson for a date, that lesson IS what the teacher is teaching — use its title, unit, and topic for any worksheet/document generation. When the calendar has NO lessons scheduled, get_calendar AUTOMATICALLY returns structured curriculum_map data (unit, benchmarks, vocabulary, textbook chapters, resources) parsed from the uploaded curriculum map. Present ALL of this structured data to the teacher — never summarize or omit fields.

When get_calendar returns a "curriculum_map" object, present EVERY field:
1. Unit name and week numbers
2. Exact date range
3. EVERY benchmark with its full code and description text — quote them verbatim
4. The COMPLETE vocabulary list — list every term
5. Textbook chapters and page numbers exactly as returned
6. ALL resources: Nearpod activities, Nearpod lessons, videos, and DBQs with their exact titles
Then ALSO check the UPLOADED REFERENCE DOCUMENTS in your system context for additional details from other uploaded files (standards framework, pacing guides, school calendars) and include any relevant supplementary information.
Never say "feel free to ask for more details" — the data is already there. Present it all.

STANDARDS & RESOURCES: Curriculum standards are indexed in your context above — use get_standards with a topic keyword for full details (vocabulary, learning targets, essential questions). Uploaded reference documents have their full content in the UPLOADED REFERENCE DOCUMENTS section above. Always cross-reference ALL uploaded resources when answering curriculum questions. Never make up standard codes or curriculum requirements — use only what's in your context or returned by tools.

EDTECH QUIZ GENERATORS (zero-cost, no AI API calls):
- generate_kahoot_quiz: Create Kahoot-compatible .xlsx quiz from standards/grades/content. Questions built from vocabulary and sample assessments.
- generate_blooket_set: Create Blooket-compatible .csv question set with MC questions.
- generate_gimkit_kit: Create Gimkit-compatible .csv (Question, Correct Answer, Incorrect Answer 1-3).
- generate_quizlet_set: Create Quizlet-compatible .txt flashcard set (tab-separated term/definition).
- generate_nearpod_questions: Create formatted .docx with questions for Nearpod copy-paste.
- generate_canvas_qti: Create Canvas QTI 1.2 .xml for LMS import.

ONLY generate a quiz when the teacher EXPLICITLY asks you to create, generate, or make one (e.g., "create a Kahoot quiz", "generate a Blooket set", "make me a quiz for Friday"). Do NOT generate a quiz just because the teacher mentions that a quiz or test will happen — "we'll have a quiz Friday" is NOT a request to generate one. If unsure whether they want you to generate or just schedule, ASK. These tools pull from standards vocabulary, sample assessments, and grade weakness data — zero cost, no AI API needed. All accept optional topic, assignment_name (weak areas), question_count, and difficulty parameters.

PARENT SURVEY TOOLS:
- create_parent_survey: Create an anonymous parent survey with 4-5 questions about communication, support, and availability. Returns a shareable link (/survey/CODE). Parents click the link, rate on a 1-5 star scale, and optionally leave written feedback.
- get_survey_results: View survey results with per-question averages, star distributions, and written comments. Omit join_code to list all surveys.
- compile_survey_report: Generate a detailed report with overall averages, per-question breakdowns, and all written feedback. Use when the teacher wants a summary of parent feedback.

ADVANCED ANALYTICS:
- get_grade_trends: Track student/class scores over time with direction (improving/declining/stable). Use for individual student or class-wide trends.
- get_rubric_weakness: Find consistently weakest rubric categories across ALL assignments. Shows gap between strongest and weakest categories.
- flag_at_risk_students: Combine declining trends + missing work + low rubric categories into risk scores. Use when asked "who should I be worried about?" or "which students need help?"
- compare_assignments: Side-by-side stats for two assignments (mean, median, distribution, category shifts, who improved/declined).
- get_grade_distribution: Histogram-ready A/B/C/D/F counts and percentages. Can group by assignment or period. Use for admin reports and data meetings.
- detect_score_outliers: Flag scores >2 standard deviations from class mean — catches possible mis-grades, cheating, or data entry errors before publishing.

PLANNING & CLASSROOM:
- suggest_remediation: Map student weaknesses to concrete activities using the teacher's enabled edtech tools. Recommends specific Kahoot/Blooket/worksheet activities.
- align_to_standards: Show which standards a topic covers and which remain unassessed. Use for curriculum mapping.
- get_pacing_status: Compare calendar progress vs total standards — ahead/behind/on-track. Shows coverage percentage.
- generate_bell_ringer: Quick 2-3 question warm-up from yesterday's lesson vocab/standards. Zero cost.
- generate_exit_ticket: 2-3 quick check questions from today's lesson or a specified topic. Zero cost.
- suggest_grouping: Create student groups by performance — heterogeneous (mixed) or homogeneous (similar). Uses grade data for balanced grouping.
- generate_sub_plans: Build substitute teacher plans from calendar + saved lessons. Generates structured plans with objectives, vocabulary, and procedures.

COMMUNICATION & REPORTING:
- generate_progress_report: Structured progress report data for a student or period. Use with generate_document for a printable Word doc.
- generate_report_card_comments: Template-based comments from score patterns (NOT AI-generated). Deterministic templates filled with real data.
- draft_student_feedback: Structured feedback: strengths, growth areas, specific examples, next steps from full grade history.
- generate_parent_conference_notes: Conference agenda with performance data, talking points, and action items.

STUDENT INFO:
- get_student_accommodations: Pull specific IEP/504 presets, notes, and grading impact for a student. Use when asked about a student's accommodations.
- get_student_streak: Show consecutive improvement/decline streaks with assignment-by-assignment history and direction indicators.
- remove_student_from_roster: Preview removing a student from ALL records. Returns a PREVIEW of what will be deleted, does NOT delete anything. After showing the preview and the teacher confirms, call confirm_student_removal to execute. NEVER claim a student was removed without a successful confirm_student_removal response.
- confirm_student_removal: Execute a pending student removal after teacher confirmation. Takes no parameters. Call ONLY after remove_student_from_roster has shown a preview and the teacher has approved.
- export_student_data: Export all data for a student (grades, history, accommodations) as JSON + PDF. Use for parent requests, transfers, FERPA compliance.
- import_student_data: Import a student's exported data file (JSON) into Graider. Use when a student transfers in from another Graider teacher.

COMMUNICATIONS:
- send_focus_comms: DEFAULT method for contacting parents or students. Sends email and/or SMS through Focus SIS using the teacher's school account. Only fall back to send_parent_emails (Outlook) if the teacher explicitly requests Outlook.
  - Email only: provide email_subject + email_body, omit sms_body
  - SMS only: provide email_subject + sms_body, DO NOT provide email_body (omit it entirely, do not pass empty string)
  - Email + SMS: provide all three. The sms_body should be a SHORT notification (e.g. "Please check your email for a message regarding [subject]. -Mr./Ms. [Teacher]") pointing parents to the full email.
  - When the teacher says "send a message" or "contact parents", default to email ONLY (no SMS). Only include sms_body if the teacher explicitly asks for SMS (e.g., "send email and text", "also text them", "send SMS").
  - recipient_type: "Primary Contacts" (default) sends to parents/guardians. "Students" sends directly to the student. Use "Students" when the teacher says "send to [student name]" or "email [student name]" without mentioning parents. Use "Primary Contacts" when the teacher says "contact parents" or "send to [student]'s parents".
- send_parent_emails: Send emails to parents via Outlook automation. Use ONLY if the teacher specifically asks for Outlook.

SENDING FLOW — when the teacher asks you to send a message/email/SMS, follow these steps EXACTLY:
CRITICAL: You MUST actually call the tools below. NEVER generate a preview from memory or prior conversation context. Every send request requires fresh tool calls, even if you sent to the same student earlier in this conversation.
CRITICAL: Always use the student name from the CURRENT message. If the teacher previously discussed Cayden but now asks about London, the student is LONDON — not Cayden. Do NOT carry over student names from earlier messages.
RECIPIENT RULE: Determine who the message is FOR:
- "send an email to [student]" or "message [student]" → recipient_type="Students", address the email to the STUDENT (e.g., "Dear Charles")
- "contact [student]'s parents" or "send to parents" or "notify parents" → recipient_type="Primary Contacts", address the email to the PARENT by name
- If unclear, default to "Primary Contacts"
Step 1: Extract the EXACT student name from the teacher's CURRENT message — not from earlier in the conversation. If the teacher says "email London Samuel's parents", the student is "London Samuel", NOT any student mentioned previously. Call lookup_student_info with this exact name. Do NOT call query_grades or other research tools — compose the email using ONLY the facts from the teacher's current message.
Step 2: Call send_focus_comms with the email based on the teacher's stated facts. You MUST call this tool — do NOT fabricate a preview. Set recipient_type based on the RECIPIENT RULE above.
Step 3: Show the preview returned by send_focus_comms and ask "Would you like me to send this?"
Step 4: When the teacher confirms (e.g., "yes", "send it", "looks good"), call confirm_and_send — this triggers the actual Playwright automation to send the messages.
Step 5: NEVER claim messages were sent until confirm_and_send returns a success response with status "started".
- confirm_and_send: Execute the pending send after teacher confirmation. Takes no parameters. Call ONLY after showing a preview and getting teacher approval.

BEHAVIOR TRACKING:
- get_behavior_summary: Get behavior correction and praise counts for a student or class period. Shows daily breakdown, notes, and trends. Use when the teacher asks "how has [student] behaved?" or "show behavior for Period 3". If default 7-day window returns no data, retry with days=30 or days=90 before giving up.
- generate_behavior_email: Generate a professional behavior email to a student's parents. Supports two modes:
  - use_behavior_data=true: Fetches companion app data (corrections, praise, dates, notes) from Supabase and includes it in the email.
  - use_behavior_data=false: Drafts the email using ONLY the information the teacher provided in the chat (passed via custom_note). No companion app data is fetched.
  IMPORTANT: When the teacher asks you to draft an email about a student, you MUST first ask: "Would you like me to include behavior data from the Companion app, or should I draft using just the information you've shared here?" Then set use_behavior_data accordingly. If they choose no companion data, pass all the context from the conversation into custom_note.
- send_behavior_email: Preview a behavior email via Resend or Focus portal. Returns a PREVIEW, does NOT send. After showing the preview and the teacher confirms, call confirm_and_send to actually send. NEVER claim the email was sent until confirm_and_send returns status "started".
- debug_behavior: Diagnostic tool — shows teacher_id, total session/event counts, and stored student names. Use this FIRST if behavior data retrieval fails, to diagnose why.
CRITICAL: If behavior tools return errors about missing data, call debug_behavior to diagnose, then report findings to the teacher. NEVER fabricate a behavior email without real data from the tools — the email MUST reference actual tracked incidents, not placeholders."""


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
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            # Best-effort: settings load failure leaves these vars at their
            # caller-default values.
            logger.debug("Failed to load assistant settings/config: %s", e)

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

    prompt = _base_assistant_system_prompt(teacher_context)

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
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        # Best-effort: persistent memory load failure means the assistant
        # answers without saved facts. Functional, just less personalized.
        logger.debug("Failed to inject persistent memory facts: %s", e)

    # Standards: only inject a compact index (codes + short benchmarks).
    # Full details (vocabulary, topics, learning targets) fetched on demand via get_standards tool.
    all_standards = _load_standards()
    if all_standards:
        compact = []
        for s in all_standards:
            code = s.get("code", "")
            benchmark = s.get("benchmark", "")
            dok = s.get("dok", "")
            compact.append(f"{code} (DOK {dok}): {benchmark}")
        prompt += f"\n\n## CURRICULUM STANDARDS INDEX ({len(all_standards)} standards)\n"
        prompt += "Compact index — use get_standards tool with a topic keyword for full details (vocabulary, learning targets, essential questions).\n"
        prompt += "\n".join(compact)

    # Inject full resource content so the AI can answer directly without tool calls
    resource_content = _load_resource_content()
    if resource_content:
        prompt += "\n\n## UPLOADED REFERENCE DOCUMENTS\n"
        prompt += "The teacher has uploaded these documents. Their full content is included below — use it directly to answer questions about curriculum, pacing, and scheduling.\n\n"
        prompt += resource_content
    else:
        resource_names = _load_resource_names()
        if resource_names:
            prompt += "\n\n## UPLOADED REFERENCE DOCUMENTS\n"
            prompt += "The teacher has uploaded these documents. Use read_resource(filename) to access their content.\n"
            prompt += "\n".join(f"- {r}" for r in resource_names)

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

    # Platform docs: do NOT inject the full user manual (~12K tokens).
    # The assistant can answer most questions from its tool descriptions and context.
    # Only inject a short note so it knows it can reference docs if asked.
    prompt += "\n\nPLATFORM HELP: If asked how-to or troubleshooting questions about Graider, use read_resource with filename 'User_Manual.md' to look up the answer. Do NOT guess — check the docs."

    return prompt


def _audit_log(action, details=""):
    """Write to the FERPA audit log.

    Round-2 Codex HIGH fold (PR #227): delegates to the central
    `backend.utils.audit.audit_log` so the redaction helper is applied
    uniformly. Previously this function wrote to AUDIT_LOG_FILE directly,
    bypassing `_redact_for_audit()`.
    """
    from backend.utils.audit import audit_log as _central_audit_log
    _central_audit_log(action, details, user="teacher")


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
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        logger.error("Failed to record assistant cost: %s", e)

    return {
        "claude_cost": round(claude_cost, 6),
        "tts_cost": round(tts_cost, 6),
        "total_cost": total_cost,
    }


def _finalize_assistant_stream(
    *,
    session_id: str,
    conv: dict,
    messages: list,
    tts_stream,
    sentence_buffer,
    audio_out_queue,
    total_input_tokens: int,
    total_output_tokens: int,
    total_tts_chars: int,
    active_model: str,
    cancelled: bool,
):
    """Idempotent cleanup for the assistant SSE stream. Yields SSE audio_chunk
    frames in normal-completion mode; silent in disconnect mode.

    See docs/superpowers/specs/2026-04-23-phase5b-hardening-design.md § PR 4
    for the full 9-responsibility behavior spec. Disconnect mode skips
    step 3 (sentence buffer flush), step 4 (tts wait_for_flush), step 6
    (audio-chunk yields), and step 9's cost SSE frame — other steps run
    regardless of client connectivity.
    """
    # Round 7 idempotency guard — first call wins.
    with _finalizing_lock:
        if session_id in _finalizing_sessions:
            return
        _finalizing_sessions.add(session_id)

    try:
        # 1. conv["messages"] = messages
        conv["messages"] = messages

        # 2. _persist_conversation(session_id)
        try:
            _persist_conversation(session_id)
        except Exception:
            logger.exception("_persist_conversation failed for %s", session_id)

        # 3. Sentence buffer flush + send — NORMAL MODE ONLY
        if not cancelled and tts_stream is not None:
            if session_id not in tts_muted_sessions and sentence_buffer:
                remaining = sentence_buffer.flush()
                if remaining:
                    text_to_speak = remaining + " "
                    try:
                        tts_stream.send_text(text_to_speak)
                        total_tts_chars += len(text_to_speak)
                    except Exception:  # noqa: BLE001  # broad catch: error is logged
                        logger.debug("tts_stream.send_text failed on finalize", exc_info=True)

        # 4. tts_stream.flush() + wait_for_flush — NORMAL MODE ONLY
        # Skipped in disconnect to avoid blocking a Gunicorn worker for up to
        # 15 seconds flushing audio that no one will receive (Gemini Round 7).
        if not cancelled and tts_stream is not None:
            try:
                tts_stream.flush()
                tts_stream.wait_for_flush(timeout=15.0)
            except Exception:  # noqa: BLE001  # broad catch: error is logged
                logger.debug("tts_stream.flush/wait_for_flush raised", exc_info=True)

        # 5. tts_stream.close() — both modes
        if tts_stream is not None:
            try:
                tts_stream.close()
            except Exception:  # noqa: BLE001  # broad catch: error is logged
                logger.debug("tts_stream.close raised", exc_info=True)

        # 6. Audio-queue drain + yield — NORMAL MODE ONLY
        if not cancelled and tts_stream is not None:
            if audio_out_queue and session_id not in tts_muted_sessions:
                while True:
                    try:
                        chunk = audio_out_queue.get(timeout=3.0)
                        if chunk is None:
                            break
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': chunk})}\n\n"
                    except queue.Empty:
                        break

        # 7. tts_muted_sessions.discard(session_id)
        tts_muted_sessions.discard(session_id)

        # 8. cancelled_sessions.discard(session_id)
        cancelled_sessions.discard(session_id)

        # 9. Cost record + (normal mode only) yield cost SSE frame.
        # At-most-once semantics via _cost_recorded_sessions guard — critical
        # for the GeneratorExit-mid-drain race where the inner finalizer's
        # finally releases _finalizing_sessions before the outer silent
        # wrapper fires. Without this guard, a disconnect during step 6
        # (audio drain) would record cost twice.
        if total_input_tokens > 0 or total_tts_chars > 0:
            with _finalizing_lock:
                already_recorded = session_id in _cost_recorded_sessions
                if not already_recorded:
                    _cost_recorded_sessions.add(session_id)
                    # Simple eviction: if the set grows past the cap, clear it.
                    # Cost records are per-request; the cap is generous enough
                    # that eviction is a rare no-op in practice.
                    if len(_cost_recorded_sessions) > _COST_RECORDED_CAP:
                        _cost_recorded_sessions.clear()
                        _cost_recorded_sessions.add(session_id)
            if not already_recorded:
                try:
                    cost_info = _record_assistant_cost(
                        total_input_tokens, total_output_tokens,
                        active_model, total_tts_chars,
                    )
                    if cost_info.get("total_cost", 0) > COST_WARNING_THRESHOLD:
                        cost_info["high_cost"] = True
                    if not cancelled:
                        yield f"data: {json.dumps({'type': 'cost', 'input_tokens': total_input_tokens, 'output_tokens': total_output_tokens, 'tts_chars': total_tts_chars, **cost_info})}\n\n"
                except Exception:
                    logger.exception("_record_assistant_cost failed")

        # Observability marker
        try:
            from backend.observability.events import emit as _emit
            _emit(
                "assistant.stream.finalized",
                session_id=session_id,
                cancelled=cancelled,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                total_tts_chars=total_tts_chars,
                active_model=active_model,
            )
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            # Best-effort: telemetry emit failure must not block stream
            # finalization. The user-facing flow is unaffected.
            logger.debug("Failed to emit assistant.stream.finalized event: %s", e)
    finally:
        with _finalizing_lock:
            _finalizing_sessions.discard(session_id)


def _finalize_assistant_stream_silent(**kwargs):
    """Run finalize's state cleanup but discard any SSE yields.

    For the GeneratorExit disconnect path where `yield from` is illegal.
    """
    for _ in _finalize_assistant_stream(**kwargs):
        pass


def _cleanup_stale_sessions():
    """Remove conversations older than TTL."""
    now = time.time()
    stale = [sid for sid, conv in conversations.items()
             if now - conv["last_active"] > CONVERSATION_TTL]
    for sid in stale:
        del conversations[sid]


# ── Send-tool user-message name guard ──────────────────────

# Words that are commonly capitalized but are NOT student names.
_IGNORE_WORDS = frozenset([
    "dear", "please", "hello", "hi", "hey", "good", "morning", "afternoon",
    "evening", "send", "email", "message", "text", "draft", "write", "contact",
    "parents", "parent", "mother", "father", "mom", "dad", "guardian",
    "about", "regarding", "concerning", "class", "period", "grade", "school",
    "behavior", "assignment", "homework", "classwork", "test", "quiz",
    "mr", "mrs", "ms", "miss", "dr", "teacher", "student", "focus",
    "the", "and", "his", "her", "their", "from", "with", "for", "that",
    "this", "have", "has", "been", "was", "are", "will", "can", "would",
    "should", "could", "also", "still", "just", "now", "today", "tomorrow",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "during", "after", "before", "since", "into", "like", "not", "but",
    "insistence", "constant", "refusal", "talking", "back", "silent", "remain",
    "defiance", "disrespect", "loud", "rowdy", "playing", "games",
    "yes", "no", "ok", "okay", "sure", "looks", "it", "do", "go", "so",
    "got", "get", "let", "me", "my", "an", "on", "up", "at", "to", "of",
    "is", "am", "be", "by", "or", "if", "as", "we", "us", "all", "any",
    "out", "off", "did", "does", "done", "need", "want", "make", "take",
    "them", "they", "she", "he", "who", "what", "when", "how", "why",
    "new", "old", "one", "two", "three", "more", "much", "very", "too",
    "then", "than", "here", "there", "some", "each", "every", "only",
    "well", "real", "really", "right", "wrong", "way", "thing", "things",
    "work", "working", "missing", "late", "report", "note", "notes",
    "being", "keep", "kept", "stop", "stopped", "see", "saw", "come",
    "came", "know", "knew", "tell", "told", "think", "thought", "try",
])


def _extract_message_names(text):
    """Extract potential student name words from a user message.

    Returns a list of lowercased words that look like name parts
    (words not in the ignore list, any casing). Returns [] if none found.
    """
    import re
    # Strip possessives and punctuation, split into words (Unicode-aware)
    cleaned = re.sub(r"['\u2019]s\b", "", text)
    words = re.findall(r"[A-Za-z\u00C0-\u024F]+", cleaned)

    name_words = []
    for w in words:
        low = w.lower()
        if len(w) >= 2 and low not in _IGNORE_WORDS:
            name_words.append(low)
    return name_words


def _student_name_in_message(student_name, user_message):
    """Check if a student name from a tool call has word overlap with the user message.

    Returns True if:
      - The user message contains no extractable names (confirmation like "yes", "send it")
      - At least one word from student_name appears in the extracted message names

    Returns False if:
      - The user message has extractable names but NONE overlap with student_name
    """
    message_names = _extract_message_names(user_message)
    if not message_names:
        return True

    import re
    student_words = [w.lower() for w in re.findall(r"[A-Za-z\u00C0-\u024F]+", student_name) if len(w) >= 2]
    if not student_words:
        return True

    return any(sw in message_names for sw in student_words)


_SEND_TOOL_NAMES = frozenset(["send_focus_comms", "send_behavior_email", "send_parent_emails"])


def _check_send_tool_guard(tool_name, tool_input, resolved_students, last_user_text):
    """Pre-execution guard for send tools. Returns None to proceed or an error dict to block.

    Three layers:
      1. Require lookup_student_info before sending to specific students
      2. Tool's student name must appear in the user's current message
      3. Tool's student name must match the most recent lookup result
    """
    if tool_name not in _SEND_TOOL_NAMES:
        return None

    # Normalize student names from both parameter formats
    student_names = tool_input.get("student_names") or []
    if isinstance(student_names, str):
        student_names = [student_names]
    single_name = tool_input.get("student_name", "")
    if single_name:
        student_names.append(single_name)

    if not student_names:
        return None

    # Layer 1: Require lookup
    if not resolved_students:
        return {
            "error": "You must call lookup_student_info before sending messages. "
            "Call lookup_student_info for '" + student_names[0] + "' first to verify the correct student, "
            "then call " + tool_name + " again."
        }

    # Layer 2: User-message name match
    if last_user_text:
        for sn in student_names:
            if not _student_name_in_message(sn, last_user_text):
                return {
                    "error": "Student name mismatch: you are trying to send to '" + sn + "' but the user's message "
                    "does not mention this student. Re-read the user's CURRENT message, extract the correct student name, "
                    "call lookup_student_info with that name, then try again."
                }

    # Layer 3: Cross-tool mismatch
    resolved_names = [s["name"].lower().strip() for s in resolved_students]
    for sn in student_names:
        sn_lower = sn.lower().strip()
        match_found = any(sn_lower in rn or rn in sn_lower for rn in resolved_names)
        if not match_found and resolved_names:
            return {
                "error": "Student name mismatch: you are trying to send to '" + sn + "' but the most recent lookup resolved '" + resolved_students[0]["name"] + "'. "
                "Please call lookup_student_info for '" + sn + "' first to verify the correct student."
            }

    return None


def _execute_tool_round(*, tool_use_blocks, session_id, teacher_id, _last_user_text,
                        _round_idx, full_response_text, executed_tools_this_turn,
                        _flush_audio_queue):
    """Execute one round of tool calls and stream their SSE frames.

    Extracted verbatim from ``_run_assistant_stream``'s per-round body (CQ7
    <300 LOC split, golden net: tests/test_assistant_chat_golden.py). Body is
    byte-identical (de-indented by 12). Yields the same tool_start/tool_result
    SSE frames as before and returns the (assistant_content, tool_results) pair
    the caller appends to the conversation. ``_flush_audio_queue`` is passed in
    as the caller's nested audio-flush generator.
    """
    # Build the assistant message with all content blocks (Anthropic format for conversation store)
    assistant_content = []
    if full_response_text:
        assistant_content.append({"type": "text", "text": full_response_text})

    tool_results = []
    # Track resolved students across tool calls in this round
    # so we can detect mismatches (e.g., lookup returns "London" but
    # send_focus_comms uses "Cayden" from earlier conversation context)
    _resolved_students = []  # [{name, student_id}] from lookup_student_info

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
        logger.info("TOOL DISPATCH: name=%s, round=%d", tb["name"], _round_idx)
        # Inject teacher_id for tools that need per-teacher context
        # Uses teacher_id captured at top of assistant_chat() (line ~1145)
        tool_input["teacher_id"] = teacher_id

        # ── Pre-execution guards (must short-circuit before execute_tool) ──

        result = None  # None = no guard triggered, proceed to execute

        # Block confirmation tools from executing in the same turn as their preview tool
        from backend.services.assistant_tool_guards import GUARDED_ACTIONS
        _confirmation_tools = {entry["confirm_tool"] for entry in GUARDED_ACTIONS.values() if entry.get("type") == "preview_confirm"}
        _preview_tools_this_turn = [e["name"] for e in executed_tools_this_turn if GUARDED_ACTIONS.get(e["name"], {}).get("type") == "preview_confirm"]
        if tb["name"] in _confirmation_tools and _preview_tools_this_turn:
            result = {
                "error": "Cannot confirm in the same turn as the preview. "
                "Show the preview to the teacher and wait for their confirmation before calling " + tb["name"] + "."
            }

        # Send-tool guards: require lookup + user-message name match
        if result is None:
            result = _check_send_tool_guard(
                tb["name"], tool_input, _resolved_students, _last_user_text
            )

        # ── Execute tool (only if no guard blocked it) ──
        if result is None:
            result = execute_tool(tb["name"], tool_input)

        # Record execution for post-response claim checking
        executed_tools_this_turn.append({"name": tb["name"], "result": result})

        # Inject verification message for guarded tools
        from backend.services.assistant_tool_guards import get_verification_message
        _verification_msg = get_verification_message(tb["name"], result)

        # Cross-tool guardrail: track students from lookup calls
        if tb["name"] == "lookup_student_info" and isinstance(result, dict):
            students = result.get("students", [])
            if isinstance(students, list) and students:
                _resolved_students = [{"name": s.get("name", ""), "student_id": s.get("student_id", "")} for s in students]

        result_str = json.dumps(result)
        if _verification_msg:
            logger.info("VERIFICATION INJECTED for %s: %s", tb["name"], _verification_msg[:100])
            result_str = result_str + "\n\n" + _verification_msg
        if len(result_str) > MAX_TOOL_RESPONSE_CHARS:
            result_str = result_str[:MAX_TOOL_RESPONSE_CHARS] + '... [TRUNCATED from ' + str(len(result_str)) + ' chars. Use a more specific query for full details.]'

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
            if result.get('NOT_SENT'):
                event_data['pending_send'] = True
                # Include payload so frontend can send directly.
                # GH #280 fix: per-tenant pending file path
                # (was a global file that leaked across tenants).
                from backend.utils.pending_send import pending_send_path
                _teacher_id = getattr(g, 'user_id', 'local-dev')
                pending_path = pending_send_path(_teacher_id)
                try:
                    if os.path.exists(pending_path):
                        with open(pending_path, 'r') as _pf:
                            event_data['pending_payload'] = json.load(_pf)
                except Exception as e:  # noqa: BLE001  # broad catch: error is logged
                    # Best-effort: missing pending payload
                    # falls back to the event without it.
                    logger.debug("Failed to load pending payload: %s", e)

        yield f"data: {json.dumps(event_data)}\n\n"

        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tb["id"],
            "content": result_str
        })
    return assistant_content, tool_results


def _setup_voice_mode(voice_mode):
    """Initialize TTS streaming for voice mode, or return all-None if disabled.

    Extracted verbatim from ``_run_assistant_stream``'s voice-setup block
    (CQ8 ≤200 LOC split). Body is byte-identical (de-indented by 4).
    The nested ``_drain_audio`` helper is unchanged — it still closes over
    the ``tts_stream`` / ``audio_out_queue`` locals created here.

    Returns (tts_stream, sentence_buffer, audio_out_queue, audio_thread).
    """
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
                    settings = json.load(f)
                voice_choice = settings.get("config", {}).get("assistant_voice") or settings.get("assistant_voice")
            except Exception as e:  # noqa: BLE001  # broad catch: error is logged
                # Best-effort: settings load failure leaves voice_choice
                # at its prior value (caller-default or earlier fallback).
                logger.debug("Failed to load voice from settings: %s", e)
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
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            logging.getLogger(__name__).warning(
                "Voice mode unavailable: %s", e
            )
            tts_stream = None

    return tts_stream, sentence_buffer, audio_out_queue, audio_thread


def _stream_one_round(*, active_model, active_provider, api_key, messages, system_prompt,
                      session_id, tts_stream, sentence_buffer, _flush_audio_queue):
    """Stream one LLM round and yield SSE text/tool-delta events.

    Extracted verbatim from ``_run_assistant_stream``'s per-round adapter
    streaming block (CQ8 ≤200 LOC split). Body is byte-identical (de-indented
    by 12). Yields ``text_delta`` and audio SSE frames; accumulates token/TTS
    deltas locally and returns them as the generator's StopIteration value so
    the caller can update its running totals:

        (full_response_text, tool_use_blocks, deferred_tool_starts,
         delta_input_tokens, delta_output_tokens, delta_tts_chars)

    The ``_flush_audio_queue`` nested generator is passed in from the caller
    (same pattern as ``_execute_tool_round``).
    """
    full_response_text = ""
    tool_use_blocks = []
    deferred_tool_starts = []  # Yield after TTS flush so voice finishes first

    # Ensure all submodule tools are registered before passing to API
    _merge_submodules()

    # ── ADAPTER STREAMING (all providers) ──
    llm_req = _build_llm_request(
        model=active_model,
        messages=messages,
        system_prompt=system_prompt,
        tools=TOOL_DEFINITIONS,
        max_tokens=MAX_TOKENS,
    )

    if active_provider == "anthropic":
        _stream_adapter = AnthropicAdapter(api_key=api_key)
    elif active_provider == "openai":
        _stream_adapter = OpenAIAdapter(api_key=api_key)
    elif active_provider == "gemini":
        _stream_adapter = GeminiAdapter(api_key=api_key)
    else:
        raise ValueError(f"Unknown provider: {active_provider}")

    # in-progress tool call: tool_call_id -> {id, name, args_fragments}
    _pending_tool: dict[str, dict] = {}

    # Local accumulators — returned as deltas; caller updates its totals.
    _delta_in = 0
    _delta_out = 0
    _delta_tts = 0

    for stream_event in _stream_adapter.stream_chat(llm_req):
        if session_id in cancelled_sessions:
            break

        if isinstance(stream_event, TextDelta):
            full_response_text += stream_event.text
            yield f"data: {json.dumps({'type': 'text_delta', 'content': stream_event.text})}\n\n"
            if tts_stream and sentence_buffer and session_id not in tts_muted_sessions:
                for sent in sentence_buffer.add(stream_event.text):
                    text_to_speak = sent + " "
                    tts_stream.send_text(text_to_speak)
                    _delta_tts += len(text_to_speak)

        elif isinstance(stream_event, ToolCallDelta):
            tcid = stream_event.tool_call_id
            if tcid not in _pending_tool:
                _pending_tool[tcid] = {"id": tcid, "name": "", "args_json": ""}
            if stream_event.name:
                _pending_tool[tcid]["name"] = stream_event.name
                # Defer tool_start SSE until after TTS flush
                deferred_tool_starts.append({
                    'type': 'tool_start',
                    'tool': stream_event.name,
                    'id': tcid,
                })
            _pending_tool[tcid]["args_json"] += stream_event.args_delta

        elif isinstance(stream_event, ToolCallComplete):
            tc = stream_event.tool_call
            tool_use_blocks.append({
                "id": tc.tool_call_id,
                "name": tc.name,
                "input_json": json.dumps(tc.args),
            })

        elif isinstance(stream_event, UsageEvent):
            _delta_in += stream_event.usage.prompt_tokens
            _delta_out += stream_event.usage.completion_tokens

        # FinishEvent — nothing to do; finish_reason recorded if needed

        yield from _flush_audio_queue()

    return full_response_text, tool_use_blocks, deferred_tool_starts, _delta_in, _delta_out, _delta_tts


def _run_assistant_stream(*, session_id, conv, voice_mode, model_info, api_key, teacher_id):
    """Module-level SSE generator for the assistant chat stream.

    Lifted verbatim from the former nested ``generate()`` closure inside
    ``assistant_chat`` (CQ7 <300 LOC split, golden net:
    tests/test_assistant_chat_golden.py). The body is byte-identical to the
    closure (de-indented by 4); the former closure captures (session_id, conv,
    voice_mode, model_info, api_key, teacher_id) are now keyword-only params.

    CQ8 split (≤200 LOC): voice-mode setup extracted to ``_setup_voice_mode``;
    per-round adapter streaming extracted to ``_stream_one_round``.
    """
    # Clear any stale cancel flag for this session
    cancelled_sessions.discard(session_id)

    messages = list(conv["messages"])

    # Extract the last user message text for send-tool name guard
    _last_user_text = ""
    for _msg in reversed(messages):
        if isinstance(_msg, dict) and _msg.get("role") == "user":
            _content = _msg.get("content", "")
            if isinstance(_content, str):
                _last_user_text = _content
            elif isinstance(_content, list):
                for _block in _content:
                    if isinstance(_block, dict) and _block.get("type") == "text":
                        _last_user_text = _block.get("text", "")
                        break
            break

    # Voice mode: set up TTS streaming
    tts_stream, sentence_buffer, audio_out_queue, audio_thread = _setup_voice_mode(voice_mode)

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
    max_rounds = MAX_TOOL_ROUNDS
    executed_tools_this_turn = []  # Track all tool calls across rounds for claim checking
    try:
        for _round_idx in range(max_rounds):
            try:
                # Per-round cost check — warn and stop if getting expensive
                if _round_idx > 0 and total_input_tokens > 0:
                    from assignment_grader import MODEL_PRICING
                    _pricing = MODEL_PRICING.get(active_model, {"input": 0, "output": 0})
                    _est_cost = (total_input_tokens * _pricing["input"] + total_output_tokens * _pricing["output"]) / 1_000_000
                    if _est_cost > COST_WARNING_THRESHOLD:
                        yield f"data: {json.dumps({'type': 'cost_warning', 'estimated_cost': round(_est_cost, 4), 'rounds_used': _round_idx})}\n\n"
                        break  # Stop the tool loop — too expensive

                # ── ADAPTER STREAMING (all providers) ──
                (full_response_text, tool_use_blocks, deferred_tool_starts,
                 _delta_in, _delta_out, _delta_tts) = yield from _stream_one_round(
                    active_model=active_model,
                    active_provider=active_provider,
                    api_key=api_key,
                    messages=messages,
                    system_prompt=system_prompt,
                    session_id=session_id,
                    tts_stream=tts_stream,
                    sentence_buffer=sentence_buffer,
                    _flush_audio_queue=_flush_audio_queue,
                )
                total_input_tokens += _delta_in
                total_output_tokens += _delta_out
                total_tts_chars += _delta_tts

                # ── POST-STREAM (shared across all providers) ──

                # If cancelled or no tool calls, we're done
                if session_id in cancelled_sessions:
                    if full_response_text:
                        conv["messages"].append({"role": "assistant", "content": full_response_text})
                    break

                if not tool_use_blocks:
                    # Post-response claim check: detect if AI claims actions it didn't perform
                    from backend.services.assistant_tool_guards import check_false_claims
                    logger.info("CLAIM CHECK: response=%r, tools=%s", full_response_text[:200], [t["name"] for t in executed_tools_this_turn])
                    _claim_correction = check_false_claims(full_response_text, executed_tools_this_turn)
                    logger.info("CLAIM CHECK RESULT: %r", _claim_correction)
                    if _claim_correction:
                        logger.warning("False claim detected in assistant response, appending correction")
                        yield f"data: {json.dumps({'type': 'text', 'content': _claim_correction})}\n\n"
                        full_response_text += _claim_correction
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
                    tts_stream.wait_for_flush(timeout=15.0)
                    yield from _flush_audio_queue()

                # Now that voice audio is fully sent, notify frontend about tool calls
                for ts_event in deferred_tool_starts:
                    yield f"data: {json.dumps(ts_event)}\n\n"

                assistant_content, tool_results = yield from _execute_tool_round(
                    tool_use_blocks=tool_use_blocks,
                    session_id=session_id,
                    teacher_id=teacher_id,
                    _last_user_text=_last_user_text,
                    _round_idx=_round_idx,
                    full_response_text=full_response_text,
                    executed_tools_this_turn=executed_tools_this_turn,
                    _flush_audio_queue=_flush_audio_queue,
                )
                if session_id in cancelled_sessions:
                    break

                # Add assistant message and tool results to conversation (stored in Anthropic format)
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            except Exception as e:  # noqa: BLE001  # broad catch: error is logged
                logger.warning("Assistant stream error (%s): %s", active_provider, e)
                if "APIError" in type(e).__name__ or "AuthenticationError" in type(e).__name__:
                    content = f"The {active_provider} provider returned an error. Please try again."
                else:
                    content = "The assistant hit an error. Please try again."
                yield f"data: {json.dumps({'type': 'error', 'content': content})}\n\n"
                break


        # Normal completion — finalizer replaces inline cleanup.
        # Disconnect mode is handled by the GeneratorExit branch below.
        yield from _finalize_assistant_stream(
            session_id=session_id,
            conv=conv,
            messages=messages,
            tts_stream=tts_stream,
            sentence_buffer=sentence_buffer,
            audio_out_queue=audio_out_queue,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tts_chars=total_tts_chars,
            active_model=active_model,
            cancelled=False,
        )
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except GeneratorExit:
        # Client disconnected. Run state cleanup without yields (yield-from
        # is illegal while handling GeneratorExit).
        logger.info("assistant stream closed by client (session=%s)", session_id)
        _finalize_assistant_stream_silent(
            session_id=session_id,
            conv=conv,
            messages=messages,
            tts_stream=tts_stream,
            sentence_buffer=sentence_buffer,
            audio_out_queue=audio_out_queue,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tts_chars=total_tts_chars,
            active_model=active_model,
            cancelled=True,
        )
        raise


# ═══════════════════════════════════════════════════════
# CHAT ENDPOINT (SSE STREAMING)
# ═══════════════════════════════════════════════════════

@assistant_bp.route('/api/assistant/chat', methods=['POST'])
@limiter.limit("20 per minute")
@require_teacher
@handle_route_errors
def assistant_chat():
    """Stream chat responses with tool use via SSE."""
    model_info = _get_assistant_model()
    provider = model_info["provider"]

    # Validate provider SDK + API key (BYOK-aware)
    from backend.api_keys import get_api_key
    teacher_id = getattr(g, 'user_id', 'local-dev')
    if provider == "anthropic":
        if anthropic is None:
            return jsonify({"error": "anthropic package not installed. Run: pip install anthropic"}), 500
        api_key = get_api_key('anthropic', teacher_id)
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY not set in .env"}), 500
    elif provider == "openai":
        if openai_pkg is None:
            return jsonify({"error": "openai package not installed. Run: pip install openai"}), 500
        api_key = get_api_key('openai', teacher_id)
        if not api_key:
            return jsonify({"error": "OPENAI_API_KEY not set in .env"}), 500
    elif provider == "gemini":
        if genai_pkg is None:
            return jsonify({"error": "google-genai package not installed. Run: pip install google-genai"}), 500
        api_key = get_api_key('gemini', teacher_id)
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY not set in .env"}), 500
    else:
        return jsonify({"error": f"Unknown provider: {provider}"}), 500

    # Phase 5b PR 1 — SSE preflight breaker check.
    # Returns a clean 503 + Retry-After for the common case when the breaker
    # is already OPEN. The TOCTOU fallback (breaker flips closed→open mid-
    # iteration) is handled by the existing SSE error-frame handler inside
    # generate()'s except branch — no frontend change required.
    _preflight_breaker = get_breaker(provider, model_info["model"])
    if _preflight_breaker.current_state == pybreaker.STATE_OPEN:
        resp = jsonify({
            "error": "LLM provider temporarily unavailable — circuit breaker open",
            "retry_after_seconds": 60,
        })
        resp.status_code = 503
        resp.headers["Retry-After"] = "60"
        return resp

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

    # teacher_id already captured at top of function (line ~1145) from g.user_id
    # Log it so we can diagnose production issues
    import logging
    logging.getLogger(__name__).info("assistant_chat: teacher_id=%s host=%s", teacher_id, request.host)

    return Response(
        stream_with_context(_run_assistant_stream(
            session_id=session_id,
            conv=conv,
            voice_mode=voice_mode,
            model_info=model_info,
            api_key=api_key,
            teacher_id=teacher_id,
        )),
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
@require_teacher
@handle_route_errors
def clear_conversation():
    """Clear conversation history for a session."""
    data = request.json or {}
    session_id = data.get("session_id")
    if session_id:
        conversations.pop(session_id, None)
        _persist_conversation(session_id)  # Removes from disk file
    return jsonify({"status": "cleared"})


@assistant_bp.route('/api/assistant/mute-tts', methods=['POST'])
@require_teacher
@handle_route_errors
def mute_tts():
    """Mute TTS for a session — stops sending text to TTS mid-stream."""
    data = request.json or {}
    session_id = data.get("session_id")
    if session_id:
        tts_muted_sessions.add(session_id)
    return jsonify({"status": "muted"})


@assistant_bp.route('/api/assistant/cancel', methods=['POST'])
@require_teacher
@handle_route_errors
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
@require_teacher
@handle_route_errors
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
@require_teacher
@handle_route_errors
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
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            sentry_sdk.capture_exception(e)
    return jsonify({"memories": [], "count": 0})


@assistant_bp.route('/api/assistant/memory', methods=['DELETE'])
@require_teacher
@handle_route_errors
def clear_memory():
    """Clear all saved assistant memories."""
    if os.path.exists(MEMORY_FILE):
        try:
            os.remove(MEMORY_FILE)
        except Exception as e:
            logger.exception("Failed to clear memory")
            return jsonify({"error": "An internal error occurred"}), 500
    _audit_log("memory_cleared", "All assistant memories cleared")
    return jsonify({"status": "cleared"})


# ═══════════════════════════════════════════════════════
# VPORTAL CREDENTIALS
# ═══════════════════════════════════════════════════════

@assistant_bp.route('/api/assistant/credentials', methods=['POST'])
@require_teacher
@handle_route_errors
def save_credentials():
    """Save VPortal credentials (base64 obfuscated, per-teacher in Supabase)."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = data.get('email', '')
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    teacher_id = getattr(g, 'user_id', 'local-dev')
    encoded = base64.b64encode(password.encode()).decode()
    creds_data = {"email": email, "password": encoded}

    # Primary: Supabase per-teacher (storage.py marks 'portal_credentials'
    # as a sensitive key — no file write/read fallback for real teachers
    # within storage.py itself).
    if storage_save:
        storage_save('portal_credentials', creds_data, teacher_id)

    # Per-teacher file fallback for subprocess access (local-dev keeps
    # the legacy shared path; real teachers get an isolated per-teacher
    # file). Closes GH #245.
    os.makedirs(GRAIDER_DATA_DIR, exist_ok=True)
    with open(_portal_credentials_file_for(teacher_id), 'w') as f:
        json.dump(creds_data, f)

    _audit_log("credentials_saved", "VPortal credentials updated")
    return jsonify({"status": "saved"})


@assistant_bp.route('/api/assistant/credentials', methods=['GET'])
@require_teacher
@handle_route_errors
def get_credentials():
    """Check if VPortal credentials are configured (never returns password)."""
    teacher_id = getattr(g, 'user_id', 'local-dev')

    # Primary: Supabase per-teacher
    if storage_load:
        data = storage_load('portal_credentials', teacher_id)
        if data and data.get('email'):
            return jsonify({"configured": True, "email": data.get("email", "")})

    # Per-teacher file fallback (closes GH #245 — was previously a
    # shared CREDS_FILE that leaked email across teachers).
    creds_file = _portal_credentials_file_for(teacher_id)
    if os.path.exists(creds_file):
        try:
            with open(creds_file, 'r') as f:
                data = json.load(f)
            return jsonify({"configured": True, "email": data.get("email", "")})
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            sentry_sdk.capture_exception(e)
    return jsonify({"configured": False})


def load_portal_credentials(teacher_id='local-dev'):
    """Load VPortal credentials for a specific teacher.

    Returns (email, password) tuple, or (None, None) if not configured.
    Used by subprocess launchers to write temp creds files.

    Per-teacher file isolation closes GH #245 — was previously a shared
    CREDS_FILE that returned another teacher's password under Supabase
    miss.
    """
    # Primary: Supabase per-teacher
    if storage_load:
        data = storage_load('portal_credentials', teacher_id)
        if data and data.get('email') and data.get('password'):
            email = data['email']
            password = base64.b64decode(data['password']).decode()
            return email, password

    # Per-teacher file fallback
    creds_file = _portal_credentials_file_for(teacher_id)
    if os.path.exists(creds_file):
        try:
            with open(creds_file, 'r') as f:
                data = json.load(f)
            email = data.get('email', '')
            password = base64.b64decode(data.get('password', '')).decode()
            if email and password:
                return email, password
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            # Best-effort: malformed creds file falls through to (None, None);
            # caller handles the missing-creds case explicitly.
            logger.debug("Failed to load credentials from file: %s", e)
    return None, None


def write_temp_creds_file(teacher_id='local-dev'):
    """Write a temp creds file for subprocess access. Returns True if creds available.

    Writes to the per-teacher path so concurrent subprocess launchers
    for different teachers don't clobber each other's credentials
    (closes GH #245).
    """
    email, password = load_portal_credentials(teacher_id)
    if not email or not password:
        return False
    os.makedirs(GRAIDER_DATA_DIR, exist_ok=True)
    encoded = base64.b64encode(password.encode()).decode()
    with open(_portal_credentials_file_for(teacher_id), 'w') as f:
        json.dump({"email": email, "password": encoded}, f)
    return True


# ═══════════════════════════════════════════════════════
# VOICE CONFIGURATION
# ═══════════════════════════════════════════════════════

@assistant_bp.route('/api/assistant/voice-config', methods=['GET'])
@require_teacher
@handle_route_errors
def get_voice_config():
    """Return voice TTS configuration status."""
    from backend.api_keys import get_api_key
    api_key = get_api_key('openai', getattr(g, 'user_id', 'local-dev'))
    voice = os.environ.get("OPENAI_TTS_VOICE", "nova")
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
        voice = settings.get("config", {}).get("assistant_voice") or settings.get("assistant_voice", voice)
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        # Best-effort: settings load failure keeps `voice` at the
        # caller-default value.
        logger.debug("Failed to load voice from settings: %s", e)
    return jsonify({
        "enabled": bool(api_key),
        "voice": voice,
        "voice_name": voice.capitalize(),
        "voices": OPENAI_TTS_VOICES,
    })
