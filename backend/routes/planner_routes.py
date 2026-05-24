"""
Lesson Planner API routes for Graider.
Handles standards retrieval and lesson plan generation/export.
"""
import os
import sys
import json
import time
import math
import re
import logging
import subprocess
from flask import Blueprint, request, jsonify, g, send_file
from backend.services.openai_context import build_openai_context
from werkzeug.utils import secure_filename
from pathlib import Path
from backend.extensions import limiter
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors
from backend.retry import with_retry
from backend.paths import graider_export_dir

ALLOWED_DOC_EXTENSIONS = {'.docx', '.pdf', '.txt', '.doc', '.rtf', '.png', '.jpg', '.jpeg'}

# Import MODEL_PRICING for token cost tracking
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from assignment_grader import MODEL_PRICING

# Import storage abstraction for saving grading configs to Supabase
try:
    from backend.storage import save as storage_save
except ImportError:
    try:
        from storage import save as storage_save
    except ImportError:
        storage_save = None

# ── Phase 3b1 PR5: shim removed. Post-processing pipeline lives in ──────────
# backend/services/assignment_post_processing.py. Import only the names this
# module still calls directly (names only reached INSIDE the moved orchestrator
# do not need to be re-imported here).
from backend.services.assignment_post_processing import (
    PLANNER_COSTS_FILE,
    _build_question_count_instruction,
    _build_section_categories_prompt,
    _build_subject_boundary_prompt,
    _classify_question_type,
    _extract_usage,
    _hydrate_question,
    _merge_usage,
    _post_process_assignment,
    _record_planner_cost,
    _split_markdown_table,
    _validate_question,
)

# ── Tier 2 PR1: standards loading + matching extracted to ───────────────────
# backend/services/planner_standards.py (pure logic, no Flask). Re-exported
# here so existing `from backend.routes.planner_routes import load_standards`
# (and friends) callers keep resolving. _get_openai_context stays in this
# module because it reads Flask `g`.
from backend.services.planner_standards import (  # noqa: F401
    DATA_DIR,
    DOCUMENTS_DIR,
    _extract_grade_from_code,
    _get_standards_map,
    _grade_matches,
    _load_standards_file,
    load_standards,
    load_support_documents_for_planning,
)

# ── Tier 2 PR2: document / visual / platform-export rendering extracted to ──
# backend/services/planner_export.py (pure logic, no Flask). Re-exported here
# so existing `from backend.routes.planner_routes import _create_visual_for_question`
# (and friends) callers — plus test monkeypatch targets like
# `backend.routes.planner_routes._get_export_dir` — keep resolving unchanged.
# _save_grading_config_for_export stays in this module: it has an inner
# `from flask import g` (best-effort Supabase save) and could not move
# verbatim without violating the no-Flask-import boundary of the service.
from backend.services.planner_export import (  # noqa: F401
    _create_visual_for_question,
    _export_assignment_docx_graider,
    _get_export_dir,
    _question_to_visual_dict,
    generate_qti_xml,
    parse_template_structure,
)
from backend.services.planner_export import build_platform_export
from backend.services.planner_study_aids import (
    generate_study_guide_content,
    generate_flashcards_content,
)
from backend.services.planner_study_aids import generate_slides_payload
from backend.services.planner_content_tools import adjust_reading_level_content
from backend.services.planner_standards import rewrite_for_alignment_content
from backend.services.planner_standards import align_document_to_standards_content
from backend.services.planner_standards import TextExtractionError, extract_text_from_upload
from backend.services.planner_assessments import grade_assessment_answers_logic

# ── Tier 2 PR3: prompt construction extracted to ───────────────────────────
# backend/services/planner_prompts.py (pure string building, no Flask).
# Re-exported here so existing `from backend.routes.planner_routes import
# _build_assignment_prompt` (and friends) callers keep resolving unchanged.
from backend.services.planner_prompts import (  # noqa: F401
    _build_assignment_prompt,
    _build_period_differentiation_block,
)

GEOMETRY_SUBTYPES = {
    'geometry', 'triangle', 'rectangle', 'circle', 'trapezoid',
    'parallelogram', 'rectangular_prism', 'cylinder', 'regular_polygon',
    'pythagorean', 'angles', 'similarity', 'trig'
}


# ── Phase 3c orphan patterns (defined but not currently referenced) ─────────
# Patterns for common theorem setups to detect over-determined or inconsistent
# values. Retained at module level to preserve prior compilation semantics.
import re as _re

_TANGENT_SECANT_RE = _re.compile(
    r'tangent.*(?:external|outside).*?(\d+(?:\.\d+)?).*?(?:whole|secant).*?(\d+(?:\.\d+)?)',
    _re.IGNORECASE | _re.DOTALL,
)
_CHORD_CHORD_RE = _re.compile(
    r'chord.*?(\d+(?:\.\d+)?)\s*[×*·]\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)\s*[×*·]\s*(\d+(?:\.\d+)?)',
    _re.IGNORECASE,
)
_PYTHAGOREAN_RE = _re.compile(
    r'(?:right\s+triangle|hypotenuse|legs?).*?(\d+(?:\.\d+)?).*?(\d+(?:\.\d+)?).*?(\d+(?:\.\d+)?)',
    _re.IGNORECASE | _re.DOTALL,
)


def _get_openai_context():
    """Extract user_id for the post-processing pipeline.

    Returns (user_id, None) — the client slot is kept for call-site
    compatibility but is no longer used now that _auto_fix_flagged_questions
    builds its own LLM adapter internally.
    """
    try:
        user_id = getattr(g, 'user_id', 'local-dev')
        return build_openai_context(user_id)
    except Exception as e:
        _logger.warning("OpenAI context unavailable (non-fatal): %s", e)
        return None, None


planner_bp = Blueprint('planner', __name__)
_logger = logging.getLogger(__name__)

# Standards loading + matching (DATA_DIR, DOCUMENTS_DIR, load_standards,
# _get_standards_map, _load_standards_file, _extract_grade_from_code,
# _grade_matches, load_support_documents_for_planning) extracted to
# backend/services/planner_standards.py — re-imported above (Tier 2 PR1).


@planner_bp.route('/api/get-standards', methods=['POST'])
@require_teacher
@handle_route_errors
def get_standards():
    """Get standards for a specific state, grade, and subject."""
    data = request.json
    state = data.get('state', 'FL')
    grade = data.get('grade', '7')
    subject = data.get('subject', 'Civics')

    # Try to load from JSON files first, filtered by grade
    result = load_standards(state, subject, grade)
    standards = result['standards']

    if standards:
        return jsonify({
            "standards": standards,
            "grade": grade,
            "subject": subject,
            "fallback_used": result.get("fallback_used", False),
            "fallback_framework": result.get("fallback_framework"),
            "no_framework": result.get("no_framework", False),
            "state_note": result.get("state_note"),
        })

    # Fallback to empty if no data file exists
    return jsonify({
        "standards": [],
        "grade": grade,
        "subject": subject,
        "fallback_used": result.get("fallback_used", False),
        "fallback_framework": result.get("fallback_framework"),
        "no_framework": result.get("no_framework", False),
        "state_note": result.get("state_note"),
    })


@planner_bp.route('/api/available-states', methods=['GET'])
def get_available_states():
    """Return list of all supported states with names. No auth required."""
    smap = _get_standards_map()
    states = []
    for code, info in sorted(smap.get('states', {}).items(), key=lambda x: x[1].get('name', '')):
        states.append({'code': code, 'name': info.get('name', code)})
    return jsonify({'states': states})


@planner_bp.route('/api/align-document-to-standards', methods=['POST'])
@require_teacher
@handle_route_errors
def align_document_to_standards():
    """Analyze a document and identify which standards it aligns to."""
    data = request.json
    doc_text = data.get('documentText', '')
    state = data.get('state', 'FL')
    grade = data.get('grade', '7')
    subject = data.get('subject', '')

    if not doc_text or not doc_text.strip():
        return jsonify({"error": "No document text provided"})
    if not subject:
        return jsonify({"error": "Subject is required. Set it in Settings."})

    result = load_standards(state, subject, grade)
    standards = result['standards']
    if not standards:
        return jsonify({"error": f"No standards found for {state} {subject} grade {grade}. Check that a standards file exists in backend/data/."})

    # Build condensed standards reference for AI prompt (limit token usage)
    standards_ref = []
    for s in standards:
        standards_ref.append({
            "code": s.get("code", ""),
            "benchmark": s.get("benchmark", "")[:200],
            "topics": s.get("topics", []),
            "vocabulary": s.get("vocabulary", []),
            "dok": s.get("dok", ""),
        })

    try:
        from backend.api_keys import get_api_key as _gak
        teacher_id = getattr(g, 'user_id', 'local-dev')
        api_key = _gak('openai', teacher_id)

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            return jsonify({"error": "Missing or placeholder OpenAI API Key"})

        return jsonify(align_document_to_standards_content(
            doc_text=doc_text, standards_ref=standards_ref, api_key=api_key,
        ))

    except Exception:
        _logger.exception("Standards alignment failed")
        return jsonify({"error": "An internal error occurred"}), 500


@planner_bp.route('/api/rewrite-for-alignment', methods=['POST'])
@require_teacher
@handle_route_errors
def rewrite_for_alignment():
    """Rewrite specific questions to better align with selected standards."""
    data = request.json
    questions = data.get('questions', [])
    doc_text = data.get('documentText', '')
    grade = data.get('grade', '7')
    subject = data.get('subject', '')
    state = data.get('state', 'FL')

    if not questions:
        return jsonify({"error": "No questions provided for rewriting"})

    result = load_standards(state, subject, grade)
    standards = result['standards']
    standards_by_code = {s.get("code"): s for s in standards} if standards else {}

    # Enrich questions with full standard details
    enriched_questions = []
    for q in questions:
        std_code = q.get('target_standard', '')
        std_detail = standards_by_code.get(std_code, {})
        enriched_questions.append({
            "original_text": q.get('original_text', ''),
            "target_standard_code": std_code,
            "target_benchmark": std_detail.get('benchmark', ''),
            "target_topics": std_detail.get('topics', []),
            "target_vocabulary": std_detail.get('vocabulary', []),
            "essential_questions": std_detail.get('essential_questions', []),
            "rewrite_goal": q.get('rewrite_goal', ''),
        })

    try:
        from backend.api_keys import get_api_key as _gak
        teacher_id = getattr(g, 'user_id', 'local-dev')
        api_key = _gak('openai', teacher_id)

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            return jsonify({"error": "Missing or placeholder OpenAI API Key"})

        return jsonify(rewrite_for_alignment_content(
            enriched_questions=enriched_questions, doc_text=doc_text,
            grade=grade, subject=subject, api_key=api_key,
        ))

    except Exception:
        _logger.exception("Rewrite for alignment failed")
        return jsonify({"error": "An internal error occurred"}), 500


@planner_bp.route('/api/get-lesson-templates', methods=['POST'])
@require_teacher
@handle_route_errors
def get_lesson_templates():
    """Get subject-specific lesson activity templates."""
    data = request.json
    subject = data.get('subject', '').lower().replace(' ', '_').replace('/', '-')

    templates_file = DATA_DIR / 'lesson_templates.json'
    if not templates_file.exists():
        return jsonify({"templates": None, "error": "Templates file not found"})

    try:
        with open(templates_file, 'r') as f:
            all_templates = json.load(f)

        # Try exact match first
        if subject in all_templates:
            return jsonify({"templates": all_templates[subject], "subject": subject})

        # Try partial match (e.g., 'us_history' -> 'social_studies')
        subject_mapping = {
            'us_history': 'social_studies',
            'world_history': 'social_studies',
            'civics': 'social_studies',
            'english-ela': 'social_studies',  # Use social_studies templates as fallback
        }

        mapped_subject = subject_mapping.get(subject)
        if mapped_subject and mapped_subject in all_templates:
            return jsonify({"templates": all_templates[mapped_subject], "subject": mapped_subject})

        # Return all available subjects
        return jsonify({
            "templates": None,
            "available_subjects": list(all_templates.keys()),
            "requested": subject
        })

    except Exception as e:
        _logger.exception("Failed to get lesson templates")
        return jsonify({"error": "An internal error occurred"}), 500


@planner_bp.route('/api/brainstorm-lesson-ideas', methods=['POST'])
@limiter.limit("10 per minute")
@require_teacher
@handle_route_errors
def brainstorm_lesson_ideas():
    """Generate multiple lesson plan ideas/concepts for selected standards."""
    data = request.json
    selected_standards = data.get('standards', [])
    config = data.get('config', {})

    if not selected_standards and not data.get('referenceDocs'):
        return jsonify({"error": "Please select standards or upload reference documents"})

    _subject = config.get('subject', '').strip()
    _grade = config.get('grade', '').strip()
    if not _subject or not _grade:
        from flask import current_app
        current_app.logger.warning(
            f"Brainstorm requested without subject/grade: subject={_subject!r}, grade={_grade!r}")

    try:
        from backend.api_keys import get_api_key
        from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart

        api_key = get_api_key('openai', getattr(g, 'user_id', 'local-dev'))

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        adapter = OpenAIAdapter(api_key=api_key)

        # Load support documents for context
        support_docs = load_support_documents_for_planning()

        # Build available tools instruction
        available_tools = config.get('availableTools', [])
        tools_instruction = ""
        if available_tools:
            tool_names = {
                'microsoft_365': 'Microsoft 365 (Word, Excel, PowerPoint)',
                'microsoft_teams': 'Microsoft Teams',
                'google_classroom': 'Google Classroom',
                'google_slides': 'Google Slides',
                'google_docs': 'Google Docs',
                'canvas': 'Canvas LMS',
                'nearpod': 'Nearpod',
                'edpuzzle': 'Edpuzzle',
                'pear_deck': 'Pear Deck',
                'padlet': 'Padlet',
                'flipgrid': 'Flip/Flipgrid',
                'canva': 'Canva',
                'adobe_express': 'Adobe Express',
                'ixl': 'IXL',
                'desmos': 'Desmos',
                'geogebra': 'GeoGebra',
                'delta_math': 'DeltaMath',
                'fl_math_4_all': 'FL Math 4 All',
                'prodigy': 'Prodigy',
                'zearn': 'Zearn',
                'newsela': 'Newsela',
                'commonlit': 'CommonLit',
                'phet': 'PhET Simulations',
                'dbq_online': 'DBQ Online',
                'cpalms': 'CPALMS',
                'brainpop': 'BrainPOP',
                'edgenuity': 'Edgenuity',
                'everfi': 'EVERFI',
                'progress_learning': 'Progress Learning',
                'hour_of_code': 'Hour of Code',
                'kahoot': 'Kahoot',
                'quizlet': 'Quizlet',
                'blooket': 'Blooket',
                'gimkit': 'Gimkit',
                'khan_academy': 'Khan Academy',
                'youtube': 'YouTube',
            }
            # Handle both preset tools and custom tools (prefixed with "custom:")
            tool_list = []
            for t in available_tools:
                if t.startswith('custom:'):
                    tool_list.append(t[7:])  # Remove "custom:" prefix
                else:
                    tool_list.append(tool_names.get(t, t))
            tools_instruction = f"""
AVAILABLE TECHNOLOGY TOOLS (teacher has access to these):
{', '.join(tool_list)}

IMPORTANT: At least 2-3 of your ideas should incorporate these specific tools. For each technology-enhanced idea, explain exactly HOW to use the tool (e.g., "Create a Nearpod lesson with drag-and-drop activities" or "Use Kahoot for a competitive review game with 15 questions")."""
        else:
            tools_instruction = """
NO TECHNOLOGY TOOLS SELECTED: Focus entirely on non-digital activities using standard classroom materials (whiteboards, paper, manipulatives, discussions, group work)."""

        # Format standards as numbered list for clarity
        standards_text = ""
        for i, s in enumerate(selected_standards, 1):
            standards_text += f"\n{i}. {s}"

        subject_boundary = _build_subject_boundary_prompt(
            config.get('subject', ''), config.get('grade', ''))

        prompt = f"""You are an expert curriculum developer brainstorming lesson plan ideas for a {config.get('grade', '7')}th grade {config.get('subject', 'Social Studies')} class.
{subject_boundary}
{support_docs}

STANDARDS TO COVER (every idea MUST directly address these specific standards):
{standards_text}

IMPORTANT: Read the benchmark text, vocabulary, and learning targets above carefully. Every lesson idea must be DIRECTLY about the specific topic described in the standard(s). Do NOT generate ideas about other topics, time periods, or standards — ONLY the ones listed above.

TEACHER'S ADDITIONAL REQUIREMENTS:
{config.get('requirements', '').strip() or 'None specified'}
NOTE: If the teacher specified additional requirements above, EVERY idea must reflect those requirements. For example, if the teacher says "focus on consequences of the Mexican American War", then all 6 ideas must center on consequences specifically — not just mention the topic generally.
{tools_instruction}

Generate 6 creative and diverse lesson plan ideas that would effectively teach these exact standards. Each idea should represent a DIFFERENT teaching approach.

CRITICAL REQUIREMENTS:
1. Every idea MUST directly teach the specific content described in the standards above — not related or adjacent topics
2. ALL activities must be CONCRETE and ACTIONABLE - things a teacher can actually do tomorrow
3. NEVER invent fictional apps, websites, platforms, or games (no "Math Ninja", "Number Quest", etc.)
4. For technology activities, ONLY use tools from the AVAILABLE TECHNOLOGY TOOLS list above (if any)
5. Focus on activities using standard classroom materials: whiteboards, manipulatives, worksheets, discussions, group work
6. Be SPECIFIC about what students actually do - not vague descriptions
7. For Math: use real problem types, manipulatives (fraction bars, algebra tiles), or proven strategies (number talks, think-pair-share)
8. For Science: use actual lab materials or household items for experiments
9. Avoid buzzwords without substance - every activity must have clear, executable steps

Return JSON with this structure:
{{
    "ideas": [
        {{
            "id": 1,
            "title": "Engaging, descriptive title",
            "approach": "Activity-Based|Discussion|Project|Simulation|Research|Collaborative|Technology-Enhanced|Primary Sources|Game-Based",
            "brief": "1-2 sentence description of the lesson concept",
            "hook": "The engaging opening or hook for students",
            "key_activity": "The main learning activity in 1 sentence",
            "tools_used": "Specific tools from the available list and HOW they will be used (or 'None - hands-on activity' if no tech)",
            "assessment_type": "How learning will be assessed"
        }}
    ]
}}

Make each idea distinct - vary the approaches (hands-on activities, discussions, projects, simulations, research, collaborative work, technology integration, primary source analysis, games/competitions). Be creative and specific to the content."""

        completion = adapter.chat(LLMRequest(
            model="gpt-4o",
            system_prompt="You are an expert curriculum developer. Return valid JSON only.",
            messages=[Message(role="user", content=[TextPart(text=prompt)])],
            response_format=ResponseFormat(type="json_object"),
            metadata={"feature_label": "brainstorm_lesson_ideas"},
        ))

        content = completion.content_parts[0].text if completion.content_parts else "{}"
        ideas = json.loads(content)
        usage = _extract_usage(completion, "gpt-4o")
        _record_planner_cost(usage)
        return jsonify({**ideas, "usage": usage})

    except Exception as e:
        error_msg = str(e)
        _logger.exception("Brainstorm Error")
        # Fallback mock ideas
        mock_ideas = {
            "ideas": [
                {"id": 1, "title": "Interactive Discussion", "approach": "Discussion", "brief": "Engage students in guided discussion.", "hook": "Opening question", "key_activity": "Socratic seminar", "assessment_type": "Participation rubric"},
                {"id": 2, "title": "Hands-On Activity", "approach": "Activity-Based", "brief": "Students learn through doing.", "hook": "Mystery item reveal", "key_activity": "Station rotations", "assessment_type": "Exit ticket"},
                {"id": 3, "title": "Research Project", "approach": "Research", "brief": "Students investigate topics independently.", "hook": "Essential question", "key_activity": "Guided research", "assessment_type": "Presentation"},
            ]
        }
        return jsonify({**mock_ideas, "error": error_msg, "method": "Mock"})


@planner_bp.route('/api/generate-lesson-plan', methods=['POST'])
@limiter.limit("10 per minute")
@require_teacher
@handle_route_errors
def generate_lesson_plan():
    """Generate a lesson plan using AI."""
    data = request.json
    selected_standards = data.get('standards', [])
    config = data.get('config', {})
    selected_idea = data.get('selectedIdea')  # Optional: from brainstorming
    generate_variations = data.get('generateVariations', False)  # Generate multiple variations
    reference_docs = data.get('referenceDocs', [])  # Uploaded reference documents

    if not selected_standards and not data.get('referenceDocs'):
        return jsonify({"error": "Please select standards or upload reference documents"})

    _subject = config.get('subject', '').strip()
    _grade = config.get('grade', '').strip()
    if not _subject or not _grade:
        from flask import current_app
        current_app.logger.warning(
            f"Lesson plan requested without subject/grade: subject={_subject!r}, grade={_grade!r}")

    try:
        from backend.api_keys import get_api_key as _gak
        from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart
        api_key = _gak('openai', getattr(g, 'user_id', 'local-dev'))

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        adapter = OpenAIAdapter(api_key=api_key)

        period_length = config.get('periodLength', 50)
        content_type = config.get('type', 'Lesson Plan')

        # Load support documents (curriculum guides, standards)
        support_docs = load_support_documents_for_planning()

        # Build available tools instruction (same mapping as brainstorm)
        available_tools = config.get('availableTools', [])
        tools_instruction = ""
        if available_tools:
            tool_names = {
                'microsoft_365': 'Microsoft 365 (Word, Excel, PowerPoint)',
                'microsoft_teams': 'Microsoft Teams',
                'google_classroom': 'Google Classroom',
                'google_slides': 'Google Slides',
                'google_docs': 'Google Docs',
                'canvas': 'Canvas LMS',
                'nearpod': 'Nearpod',
                'edpuzzle': 'Edpuzzle',
                'pear_deck': 'Pear Deck',
                'padlet': 'Padlet',
                'flipgrid': 'Flip/Flipgrid',
                'canva': 'Canva',
                'adobe_express': 'Adobe Express',
                'ixl': 'IXL',
                'desmos': 'Desmos',
                'geogebra': 'GeoGebra',
                'delta_math': 'DeltaMath',
                'fl_math_4_all': 'FL Math 4 All',
                'prodigy': 'Prodigy',
                'zearn': 'Zearn',
                'newsela': 'Newsela',
                'commonlit': 'CommonLit',
                'phet': 'PhET Simulations',
                'dbq_online': 'DBQ Online',
                'cpalms': 'CPALMS',
                'brainpop': 'BrainPOP',
                'edgenuity': 'Edgenuity',
                'everfi': 'EVERFI',
                'progress_learning': 'Progress Learning',
                'hour_of_code': 'Hour of Code',
                'kahoot': 'Kahoot',
                'quizlet': 'Quizlet',
                'blooket': 'Blooket',
                'gimkit': 'Gimkit',
                'khan_academy': 'Khan Academy',
                'youtube': 'YouTube',
            }
            tool_list = []
            for t in available_tools:
                if t.startswith('custom:'):
                    tool_list.append(t[7:])
                else:
                    tool_list.append(tool_names.get(t, t))
            tools_instruction = f"""

AVAILABLE TECHNOLOGY TOOLS (teacher has access to these - ONLY use these for tech activities):
{', '.join(tool_list)}
"""
        else:
            tools_instruction = """

NO TECHNOLOGY TOOLS: Focus entirely on non-digital activities (whiteboards, paper, manipulatives, discussions, group work).
"""

        # Build idea-specific guidance if a brainstormed idea was selected
        idea_guidance = ""
        if selected_idea:
            idea_guidance = f"""
IMPORTANT: Base this plan on the following concept:
- Title/Theme: {selected_idea.get('title', '')}
- Teaching Approach: {selected_idea.get('approach', '')}
- Concept: {selected_idea.get('brief', '')}
- Opening Hook: {selected_idea.get('hook', '')}
- Key Activity: {selected_idea.get('key_activity', '')}
- Assessment Type: {selected_idea.get('assessment_type', '')}

Develop this specific concept into a complete, detailed lesson plan.
"""

        # Handle title - if empty, instruct AI to generate based on standards
        provided_title = config.get('title', '').strip()
        if provided_title:
            title_instruction = f'Title: "{provided_title}"'
        else:
            title_instruction = "Title: Generate a descriptive, engaging title based on the standards and content below."

        # Build subject boundary constraint for prompt injection
        subject_boundary = _build_subject_boundary_prompt(
            config.get('subject', ''), config.get('grade', ''))

        # Build reference documents block
        ref_docs_block = ''
        if reference_docs:
            ref_docs_block = "\n=== REFERENCE DOCUMENTS (use this content to inform your plan) ===\n"
            for doc in reference_docs:
                doc_name = doc.get('filename', 'Document')
                doc_text = doc.get('text', '')[:6000]
                ref_docs_block += f"--- {doc_name} ---\n{doc_text}\n\n"
            ref_docs_block += "Use the content, vocabulary, examples, and concepts from these reference documents when creating activities, questions, and explanations.\n"

        # Build content-type-specific prompt, JSON structure, and instructions
        common_header = f"""You are an expert curriculum developer creating a COMPLETE, READY-TO-USE {content_type} for a {config.get('grade', '7')}th grade {config.get('subject', 'Civics')} class.
{subject_boundary}
{support_docs}
{idea_guidance}
{tools_instruction}
{title_instruction}
Standards to Cover:
{', '.join(selected_standards)}

Additional Requirements:
{config.get('requirements', 'None specified')}
{ref_docs_block}"""
        teacher_notes_block = f"""
TEACHER'S ADDITIONAL INSTRUCTIONS (MUST FOLLOW):
{config.get('globalAINotes', '')}
""" if config.get('globalAINotes') else ''

        # Build section categories instruction for assignments
        assignment_section_cats = config.get('sectionCategories', {})
        assignment_sections_block = ''
        if assignment_section_cats and any(assignment_section_cats.values()):
            assignment_sections_block = '\n' + _build_section_categories_prompt(assignment_section_cats, config.get('subject', ''), question_type_counts=config.get('questionTypeCounts')) + '\n'

        if content_type == 'Assignment':
            total_q = config.get('totalQuestions', 10)
            per_section = config.get('questionsPerSection', 0)
            # Compute per-section distribution from enabled categories
            enabled_cats = [k for k, v in assignment_section_cats.items() if v] if assignment_section_cats else ['multiple_choice', 'short_answer']
            num_sections = max(len(enabled_cats), 1)
            if per_section > 0:
                per_sec = per_section
            else:
                per_sec = max(total_q // num_sections, 2)
                remainder = total_q - (per_sec * num_sections)
            question_target = f"\nQUESTION COUNT: Generate exactly {total_q} questions total."
            question_target += f" Distribute them across your sections — aim for {per_sec} questions per section."
            question_target += f" You MUST have at least {total_q} questions in the final JSON.\n"

            prompt = common_header + f"""
Create a complete, ready-to-use assignment that directly assesses the standards listed above.
The assignment should be appropriate for grade {config.get('grade', '7')} students.
{question_target}
{assignment_sections_block}
CRITICAL REQUIREMENTS:
1. THE ASSIGNMENT MUST BE 100% SELF-CONTAINED — every resource referenced (tables, charts, reading passages, data) MUST be included in the JSON
2. For Math: use REAL numbers and actual problems, not placeholders
3. Include clear, specific answer keys for every question
4. ONLY include section types that the teacher has enabled above — do NOT add vocabulary or matching sections unless explicitly enabled
5. All questions must be answerable based on the standards content
6. For math/computation questions: SELF-CHECK that all given numeric values are consistent. Verify the numbers satisfy any stated theorem or formula BEFORE including the question. Never give more numeric values than needed to solve the problem.
7. Every question must be solvable with ONLY the given information — no hidden assumptions or missing data.
8. For ELA/reading questions: If a question asks students to analyze, cite, or refer to a passage/text/excerpt, the FULL passage MUST be included in the "question" field. NEVER reference a passage that is not embedded. "According to the passage..." is only valid if the passage text precedes it in the question field.
9. For science questions: Use ONE consistent unit system (metric or imperial) per question unless the question is explicitly about unit conversion. All numeric values must be physically possible (no negative mass, no temperatures below absolute zero, no pH outside 0-14).

Return JSON with this structure:
{{
    "title": "Assignment title",
    "overview": "2-3 sentence summary of what this assignment covers",
    "instructions": "Clear student instructions",
    "time_estimate": "Estimated completion time",
    "total_points": 100,
    "sections": [
        {{
            "name": "Section name (e.g., Part A: Vocabulary)",
            "type": "multiple_choice|fill_blank|short_answer|matching|essay|true_false|math_equation|data_table",
            "points": 20,
            "questions": [
                {{
                    "number": 1,
                    "question": "The question text",
                    "question_type": "short_answer",
                    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
                    "answer": "The correct answer",
                    "points": 2
                }}
            ]
        }}
    ],
    "answer_key": {{
        "section_name": ["answer1", "answer2"]
    }},
    "rubric": {{
        "criteria": [
            {{"name": "Criterion", "points": 10, "description": "What earns full points"}}
        ]
    }}
}}
{teacher_notes_block}

QUESTION TYPE GUIDANCE:
- For most questions, DO NOT set question_type — the system assigns it automatically from your text and structure.
- Write geometry dimensions clearly in question text: "Find the area of a triangle with base 8 cm and height 5 cm"
- Write equations clearly: "Graph y = 2x + 1 on the coordinate plane"
- For multiple choice, include "options" array. For matching, include "terms" and "definitions".
- ONLY set question_type explicitly for these complex types that need structured data:
  data_table (include headers, row_labels, expected_data with ALL values filled, editable_columns for calculation tables),
  box_plot (include data array), dot_plot (include data),
  stem_and_leaf (include data), bar_chart (include chart_data),
  transformations (include original_vertices, transformation_type, transform_params),
  fraction_model (include model_type, denominator, correct_numerator),
  probability_tree, tape_diagram, venn_diagram,
  protractor (include mode, target_angle),
  multiselect (include options, correct indices),
  multi_part (include parts array),
  grid_match (include row_labels, column_labels, correct matrix),
  inline_dropdown (include dropdowns array)

Make the questions SPECIFIC with real content tied to the standards. Include a variety of question types. For STEM subjects, include geometry and graphing questions with dimensions in the question text.

"""

        elif content_type == 'Project':
            prompt = common_header + f"""
Create a complete, ready-to-use project-based learning experience for grade {config.get('grade', '7')} students.
Duration: {config.get('duration', 1)} day(s), Class Period: {period_length} minutes

CRITICAL REQUIREMENTS:
1. All phases must be CONCRETE and ACTIONABLE
2. Include specific deliverables students must produce
3. Include a detailed rubric with clear criteria
4. Specify REAL materials and resources needed
5. Be SPECIFIC about what students do at each phase

Return JSON with this structure:
{{
    "title": "Project title",
    "overview": "2-3 sentence summary",
    "essential_questions": ["Question 1", "Question 2"],
    "driving_question": "The central question students will investigate",
    "total_points": 100,
    "phases": [
        {{
            "phase": 1,
            "name": "Phase name (e.g., Research & Planning)",
            "duration": "2 days",
            "description": "What students do in this phase",
            "tasks": ["Specific task 1", "Specific task 2"],
            "deliverable": "What students submit at end of this phase",
            "teacher_checkpoints": ["What teacher checks"]
        }}
    ],
    "milestones": [
        {{"name": "Milestone name", "due": "Day X", "description": "What should be completed"}}
    ],
    "final_deliverable": {{
        "format": "Poster/Presentation/Report/etc",
        "requirements": ["Requirement 1", "Requirement 2"],
        "presentation_time": "5-7 minutes"
    }},
    "rubric": {{
        "criteria": [
            {{"name": "Criterion", "points": 25, "description": "What earns full points", "levels": {{"excellent": "...", "proficient": "...", "developing": "...", "beginning": "..."}}}}
        ]
    }},
    "materials": ["Material 1", "Material 2"],
    "resources": ["Resource 1", "Resource 2"]
}}
{teacher_notes_block}
Make the project SPECIFIC and DETAILED with real-world connections to the standards."""

        else:
            # Lesson Plan / Unit Plan — keep existing prompt
            prompt = common_header + f"""
Duration: {config.get('duration', 1)} day(s)
Class Period Length: {period_length} minutes

Create a COMPREHENSIVE, DETAILED plan that a teacher can use immediately without any additional preparation.

CRITICAL REQUIREMENTS - FOLLOW THESE EXACTLY:
1. ALL activities must be CONCRETE and ACTIONABLE - executable tomorrow with no additional prep
2. NEVER invent fictional apps, websites, platforms, or games
3. For technology activities, ONLY use tools from the AVAILABLE TECHNOLOGY TOOLS list (if provided above)
4. Focus on proven teaching strategies: think-pair-share, jigsaw, gallery walk, Socratic seminar, station rotations, number talks
5. Specify REAL materials: whiteboards, markers, index cards, graph paper, rulers, manipulatives, printed worksheets
6. For Math: include actual example problems with numbers, not placeholders
7. For Science: use real lab materials or common household items
8. Be SPECIFIC about what students physically do at each step
9. Avoid vague phrases like "interactive digital platform" or "engaging online tool"
10. Every activity description must answer: What materials? What do students do? What does the teacher do?

Return JSON with this structure:
{{
    "title": "Full descriptive title",
    "overview": "2-3 sentence summary",
    "essential_questions": ["Question 1", "Question 2"],
    "days": [
        {{
            "day": 1,
            "topic": "Specific topic",
            "objective": "Students will be able to...",
            "standards_addressed": ["Standards covered"],
            "vocabulary": [{{"term": "word", "definition": "definition"}}],
            "timing": [
                {{"minutes": "0-5", "duration": "5 min", "activity": "Bell Ringer", "description": "Details"}}
            ],
            "bell_ringer": {{
                "prompt": "Question or task",
                "expected_responses": ["Possible answers"],
                "discussion_points": ["Follow-up questions"]
            }},
            "direct_instruction": {{
                "key_points": ["Main concepts"],
                "examples": ["Examples to share"],
                "check_for_understanding": ["Questions to ask"]
            }},
            "activity": {{
                "name": "Activity name",
                "description": "Step-by-step instructions",
                "grouping": "Individual/Pairs/Groups",
                "student_tasks": ["Step 1", "Step 2"],
                "teacher_role": "What teacher does",
                "differentiation": {{
                    "struggling": "Support strategies",
                    "advanced": "Extension activities"
                }}
            }},
            "assessment": {{
                "type": "Formative/Summative",
                "description": "How learning is assessed",
                "criteria": ["What demonstrates mastery"],
                "exit_ticket": "Exit ticket question"
            }},
            "materials": ["Item 1", "Item 2"],
            "homework": "Assignment or null",
            "teacher_notes": "Tips and notes"
        }}
    ],
    "unit_assessment": {{
        "type": "Test/Project/etc",
        "description": "Description",
        "components": ["What it includes"],
        "rubric_criteria": ["Grading criteria"]
    }},
    "resources": ["Resource 1", "Resource 2"]
}}
{teacher_notes_block}
Make the content SPECIFIC and DETAILED with real examples and facts."""

        # If generating variations, create 3 different versions
        if generate_variations:
            variations = []

            if content_type == 'Assignment':
                approaches = [
                    ("Multiple Choice & Short Answer", "Focus on recall and comprehension with multiple choice, true/false, fill-in-the-blank, and short answer questions."),
                    ("Application & Analysis", "Focus on applying concepts to new scenarios, data analysis, and problem-solving questions."),
                    ("Extended Response & Essay", "Focus on open-ended questions, essay prompts, and critical thinking responses.")
                ]
            elif content_type == 'Project':
                approaches = [
                    ("Individual Research", "Student works independently on research, analysis, and presentation of findings."),
                    ("Group Collaboration", "Students work in teams with defined roles and shared deliverables."),
                    ("Creative Expression", "Students demonstrate learning through creative media — poster, video, infographic, etc.")
                ]
            else:
                approaches = [
                    ("Activity-Based", "Focus on hands-on activities, station rotations, and interactive learning experiences."),
                    ("Discussion & Analysis", "Focus on Socratic questioning, primary source analysis, and class discussions."),
                    ("Project-Based", "Focus on student-created projects, research, and presentations.")
                ]

            total_usage = {"model": "gpt-4o", "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0}
            for approach_name, approach_desc in approaches:
                variation_prompt = prompt + f"\n\nIMPORTANT: Use a {approach_name} approach. {approach_desc}"

                completion = adapter.chat(LLMRequest(
                    model="gpt-4o",
                    system_prompt="You are an expert curriculum developer. Return valid JSON only.",
                    messages=[Message(role="user", content=[TextPart(text=variation_prompt)])],
                    response_format=ResponseFormat(type="json_object"),
                    metadata={"feature_label": "generate_lesson_plan_variation"},
                ))

                u = _extract_usage(completion, "gpt-4o")
                if u:
                    for k in ["input_tokens", "output_tokens", "total_tokens", "cost"]:
                        total_usage[k] += u[k]

                content = completion.content_parts[0].text if completion.content_parts else "{}"
                plan = json.loads(content)
                if content_type == 'Assignment':
                    target_q = config.get('totalQuestions', 10)
                    lp_std_codes = [s.split(':')[0].strip() for s in selected_standards if ':' in s]
                    _ctx_uid, _ctx_client = _get_openai_context()
                    plan, extra_usage = _post_process_assignment(
                        plan, target_q, target_total_points=100,
                        subject=config.get('subject'), grade=config.get('grade'),
                        valid_standard_codes=lp_std_codes if lp_std_codes else None,
                        user_id=_ctx_uid, client=_ctx_client)
                    if extra_usage:
                        for k in ["input_tokens", "output_tokens", "total_tokens", "cost"]:
                            total_usage[k] += extra_usage.get(k, 0)
                else:
                    if plan.get('days') and plan.get('sections'):
                        del plan['sections']
                plan['approach'] = approach_name
                variations.append(plan)

            total_usage["cost"] = round(total_usage["cost"], 6)
            total_usage["cost_display"] = f"${total_usage['cost']:.4f}"
            _record_planner_cost(total_usage)
            return jsonify({"variations": variations, "method": "AI", "usage": total_usage})

        # Single plan generation
        completion = adapter.chat(LLMRequest(
            model="gpt-4o",
            system_prompt="You are an expert curriculum developer. Return valid JSON only.",
            messages=[Message(role="user", content=[TextPart(text=prompt)])],
            response_format=ResponseFormat(type="json_object"),
            metadata={"feature_label": "generate_lesson_plan"},
        ))

        content = completion.content_parts[0].text if completion.content_parts else "{}"
        plan = json.loads(content)

        if content_type == 'Assignment':
            target_q = config.get('totalQuestions', 10)
            lp_std_codes = [s.split(':')[0].strip() for s in selected_standards if ':' in s]
            _ctx_uid, _ctx_client = _get_openai_context()
            plan, extra_usage = _post_process_assignment(
                plan, target_q, target_total_points=100,
                subject=config.get('subject'), grade=config.get('grade'),
                valid_standard_codes=lp_std_codes if lp_std_codes else None,
                user_id=_ctx_uid, client=_ctx_client)
        else:
            extra_usage = None
            # Strip stray sections/questions from non-assignment types so
            # the frontend never misidentifies a lesson plan as an assignment
            if plan.get('days') and plan.get('sections'):
                del plan['sections']

        usage = _extract_usage(completion, "gpt-4o")
        usage = _merge_usage(usage, extra_usage)
        _record_planner_cost(usage)
        return jsonify({"plan": plan, "method": "AI", "usage": usage})

    except Exception as e:
        error_msg = str(e)
        # Keep as warning (recoverable — falls back to mock) but add exc_info for traceback.
        _logger.warning("OpenAI API Error — falling back to Mock Mode", exc_info=True)

        # Fallback Mock Plan
        content_type = config.get('type', 'Unit Plan')

        mock_plan = {
            "title": f"{config.get('title', 'Unit Plan')} ({content_type} - Mock)",
            "overview": f"GENERATED IN MOCK MODE. Error: {error_msg}",
            "days": [],
            "unit_assessment": "Mock Assessment"
        }

        if content_type == 'Assignment':
            mock_plan['days'] = [{
                "day": 1,
                "topic": "Assignment: Core Concepts",
                "objective": "Students will demonstrate understanding.",
                "vocabulary": ["Key Term 1", "Key Term 2"],
                "bell_ringer": "Review instructions.",
                "activity": "Complete the assignment.",
                "assessment": "Graded submission.",
                "materials": ["Worksheet", "Resources"]
            }]
        else:
            mock_plan['days'] = [
                {
                    "day": i + 1,
                    "topic": f"Mock Topic {i + 1}",
                    "objective": "Students will understand key concepts.",
                    "vocabulary": ["Term 1", "Term 2"],
                    "bell_ringer": "Prompt on board.",
                    "activity": "Group activity.",
                    "assessment": "Exit Ticket.",
                    "materials": ["Textbook", "Worksheet"]
                } for i in range(int(config.get('duration', 5)))
            ]

        return jsonify({"plan": mock_plan, "method": "Mock", "error": error_msg})


@planner_bp.route('/api/generate-assignment-from-lesson', methods=['POST'])
@limiter.limit("10 per minute")
@require_teacher
@handle_route_errors
def generate_assignment_from_lesson():
    """Generate an assignment based on an existing lesson plan."""
    data = request.json
    lesson_plan = data.get('lessonPlan', {})
    config = data.get('config', {})
    assignment_type = data.get('assignmentType', 'assignment')

    # Validate assignment_type
    if assignment_type not in ('assignment', 'project', 'essay'):
        assignment_type = 'assignment'

    _subject = config.get('subject', '').strip()
    _grade = config.get('grade', '').strip()
    if not _subject or not _grade:
        from flask import current_app
        current_app.logger.warning(
            f"Assignment-from-lesson requested without subject/grade: subject={_subject!r}, grade={_grade!r}")

    config_standards = config.get('standards', [])
    reference_docs = config.get('referenceDocs', [])
    global_ai_notes = config.get('globalAINotes', '')
    content_only = config.get('contentOnly', False)

    if not lesson_plan:
        return jsonify({"error": "No lesson plan provided"})

    try:
        from backend.api_keys import get_api_key as _gak
        from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart
        api_key = _gak('openai', getattr(g, 'user_id', 'local-dev'))

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        adapter = OpenAIAdapter(api_key=api_key)

        # Extract lesson details for context
        lesson_title = lesson_plan.get('title', 'Untitled Lesson')
        lesson_overview = lesson_plan.get('overview', '')
        essential_questions = lesson_plan.get('essential_questions', [])
        days = lesson_plan.get('days', [])

        # Gather vocabulary, objectives, and key content from all days
        all_vocabulary = []
        all_objectives = []
        all_key_points = []

        for day in days:
            vocab = day.get('vocabulary', [])
            for v in vocab:
                if isinstance(v, dict):
                    all_vocabulary.append(f"{v.get('term', '')}: {v.get('definition', '')}")
                else:
                    all_vocabulary.append(str(v))

            if day.get('objective'):
                all_objectives.append(day['objective'])

            di = day.get('direct_instruction', {})
            if isinstance(di, dict) and di.get('key_points'):
                all_key_points.extend(di['key_points'])

        # Check for essay/project — use dedicated prompts (no section categories)
        dedicated_prompt = _build_assignment_prompt(lesson_plan, config, assignment_type)
        if dedicated_prompt is not None:
            completion = adapter.chat(LLMRequest(
                model="gpt-4o",
                system_prompt="You are an expert teacher. Return valid JSON only.",
                messages=[Message(role="user", content=[TextPart(text=dedicated_prompt)])],
                response_format=ResponseFormat(type="json_object"),
                temperature=0.7,
                metadata={"feature_label": "generate_essay_or_project"},
            ))

            content = completion.content_parts[0].text if completion.content_parts else "{}"
            result = json.loads(content)

            # Wrap essay/project in sections format for frontend compatibility
            if assignment_type == 'essay':
                result['sections'] = [{
                    'name': 'Essay Response',
                    'type': 'essay',
                    'questions': [{
                        'question': result.get('essay_prompt', ''),
                        'answer': 'See rubric for grading criteria.',
                        'points': result.get('total_points', 100),
                        'type': 'extended_response',
                    }],
                }]
            elif assignment_type == 'project':
                result['sections'] = [{
                    'name': 'Project Requirements',
                    'type': 'project',
                    'questions': [{
                        'question': result.get('project_description', ''),
                        'answer': 'See rubric and milestones for grading criteria.',
                        'points': result.get('total_points', 100),
                        'type': 'extended_response',
                    }],
                }]

            return jsonify({"assignment": result})

        # IMPORTANT: Essay and project types use dedicated prompts above and return early.
        # The code below (section categories, question types, multi-section JSON schema)
        # only applies to assignment_type == 'assignment'. Do NOT remove this early return
        # or essay/project will revert to generating multi-section worksheets.

        # Assignment type templates
        subject = config.get('subject', '').lower()
        is_stem = any(s in subject for s in ['math', 'algebra', 'geometry', 'calculus', 'science', 'physics', 'chemistry', 'biology'])

        type_instructions = {
            'assignment': "Create an assignment with a MIX of question types based on the section categories specified below. Use the section toggles to determine format — if multiple choice is enabled, include MC questions; if extended writing is enabled, include essay/written response questions; etc.",
            'project': "Create a multi-day project assignment with clear requirements, milestones, and a rubric. Include specific deliverables and evaluation criteria.",
            'essay': "Create an essay prompt with a clear thesis question, required length, and grading criteria. Include pre-writing guidance and evaluation rubric."
        }

        type_instruction = type_instructions.get(assignment_type, type_instructions['assignment'])

        if is_stem:
            type_instruction += " IMPORTANT: For Math/Science subjects, align with Florida FAST assessment format. Include multiple_choice questions (4 answer choices, one correct) and short_answer questions. For math, use math_equation type for solving/simplifying. If the lesson involves data or measurements, include data_table questions with actual numeric values. EVERY table referenced in a question MUST use question_type 'data_table' with column_headers, row_labels, and expected_data — NEVER put table data as raw text inside the question string."

        # Apply section category constraints from the UI
        section_categories = config.get('sectionCategories', {})
        if section_categories and any(section_categories.values()):
            section_prompt = _build_section_categories_prompt(section_categories, config.get('subject', ''), question_type_counts=config.get('questionTypeCounts'))
            type_instruction += "\n\n" + section_prompt

        # Build available tools instruction
        available_tools = config.get('availableTools', [])
        tools_instruction = ""
        if available_tools:
            tool_names = {
                'microsoft_365': 'Microsoft 365 (Word, Excel, PowerPoint)',
                'microsoft_teams': 'Microsoft Teams',
                'google_classroom': 'Google Classroom',
                'google_slides': 'Google Slides',
                'google_docs': 'Google Docs',
                'canvas': 'Canvas LMS',
                'nearpod': 'Nearpod',
                'edpuzzle': 'Edpuzzle',
                'pear_deck': 'Pear Deck',
                'padlet': 'Padlet',
                'flipgrid': 'Flip/Flipgrid',
                'canva': 'Canva',
                'adobe_express': 'Adobe Express',
                'ixl': 'IXL',
                'desmos': 'Desmos',
                'geogebra': 'GeoGebra',
                'delta_math': 'DeltaMath',
                'fl_math_4_all': 'FL Math 4 All',
                'prodigy': 'Prodigy',
                'zearn': 'Zearn',
                'newsela': 'Newsela',
                'commonlit': 'CommonLit',
                'phet': 'PhET Simulations',
                'dbq_online': 'DBQ Online',
                'cpalms': 'CPALMS',
                'brainpop': 'BrainPOP',
                'edgenuity': 'Edgenuity',
                'everfi': 'EVERFI',
                'progress_learning': 'Progress Learning',
                'hour_of_code': 'Hour of Code',
                'kahoot': 'Kahoot',
                'quizlet': 'Quizlet',
                'blooket': 'Blooket',
                'gimkit': 'Gimkit',
                'khan_academy': 'Khan Academy',
                'youtube': 'YouTube',
            }
            tool_list = []
            for t in available_tools:
                if t.startswith('custom:'):
                    tool_list.append(t[7:])
                else:
                    tool_list.append(tool_names.get(t, t))
            tools_instruction = f"""
AVAILABLE TECHNOLOGY TOOLS (student has access to these):
{', '.join(tool_list)}

CRITICAL: When an assignment requires digital creation (infographics, presentations, videos, graphs, etc.):
- ALWAYS specify which tool from the list above to use (e.g., "Using Canva, create an infographic...")
- Include the specific tool name in the question text
- If multiple tools could work, pick the most appropriate one and name it explicitly
"""
        else:
            tools_instruction = """
NO TECHNOLOGY TOOLS SPECIFIED: Focus on paper-based or physical deliverables only.
"""

        subject_boundary = _build_subject_boundary_prompt(
            config.get('subject', ''), config.get('grade', ''))

        # Build standards text block
        standards_text = ""
        if config_standards:
            standards_text = "\nSTANDARDS TO ASSESS (align questions to these standards):"
            for i, s in enumerate(config_standards, 1):
                if isinstance(s, dict):
                    code = s.get('code', '')
                    benchmark = s.get('benchmark', '')
                    standards_text += f"\n{i}. {code}: {benchmark}"
                else:
                    standards_text += f"\n{i}. {s}"

        # Build reference documents block
        ref_docs_block = ""
        if reference_docs:
            if content_only and config_standards:
                # Standards selected BUT teacher wants questions ONLY from their content
                ref_docs_block = "\n=== SOURCE DOCUMENTS (create ALL questions from this content) ===\n"
                ref_docs_block += "CRITICAL: The teacher has selected standards for structure and DOK levels, "
                ref_docs_block += "but wants ALL questions to come directly from the content in these documents. "
                ref_docs_block += "Every question must be answerable using ONLY information found in these documents. "
                ref_docs_block += "Use the standards to guide question format, rigor level (DOK), and cognitive demand — "
                ref_docs_block += "but do NOT create questions about topics not covered in the documents.\n\n"
                for doc in reference_docs:
                    doc_name = doc.get('filename', 'Document')
                    doc_text = doc.get('text', '')[:6000]
                    ref_docs_block += f"--- {doc_name} ---\n{doc_text}\n\n"
            elif config_standards:
                # Standards active, resources supplementary (default behavior)
                ref_docs_block = "\n=== REFERENCE DOCUMENTS (supplementary content for question context) ===\n"
                for doc in reference_docs:
                    doc_name = doc.get('filename', 'Document')
                    doc_text = doc.get('text', '')[:6000]
                    ref_docs_block += f"--- {doc_name} ---\n{doc_text}\n\n"
                ref_docs_block += "Use the content, vocabulary, examples, and concepts from these reference documents when creating questions, while aligning to the standards above.\n"
            else:
                # NO standards — create questions ONLY from the uploaded resources
                ref_docs_block = "\n=== SOURCE DOCUMENTS (create ALL questions from this content) ===\n"
                ref_docs_block += "CRITICAL: Since no curriculum standards are selected, generate ALL questions directly from the content in these documents. "
                ref_docs_block += "Every question must be answerable using information found in these documents. "
                ref_docs_block += "Do NOT create questions about topics not covered in the documents.\n\n"
                for doc in reference_docs:
                    doc_name = doc.get('filename', 'Document')
                    doc_text = doc.get('text', '')[:6000]
                    ref_docs_block += f"--- {doc_name} ---\n{doc_text}\n\n"

        prompt = f"""You are an expert teacher creating an assessment/assignment based on a lesson plan.
{subject_boundary}
{tools_instruction}
{standards_text}
{ref_docs_block}
LESSON PLAN DETAILS:
Title: {lesson_title}
Overview: {lesson_overview}

Essential Questions:
{chr(10).join(f'- {q}' for q in essential_questions) if essential_questions else 'None specified'}

Learning Objectives:
{chr(10).join(f'- {obj}' for obj in all_objectives) if all_objectives else 'None specified'}

Key Content Points:
{chr(10).join(f'- {kp}' for kp in all_key_points[:10]) if all_key_points else 'None specified'}

Vocabulary:
{chr(10).join(f'- {v}' for v in all_vocabulary[:15]) if all_vocabulary else 'None specified'}

ASSIGNMENT TYPE: {assignment_type.title()}
{type_instruction}
{_build_question_count_instruction(config)}

Create a complete, ready-to-use assignment that:
1. Directly assesses the lesson objectives
2. Uses the vocabulary and key concepts from the lesson
3. Aligns with the essential questions
4. Is appropriate for grade {config.get('grade', '7')} students

CRITICAL REQUIREMENTS:
- THE ASSIGNMENT MUST BE 100% SELF-CONTAINED. Every resource referenced in the instructions (tables, charts, data sets, reading passages, maps, diagrams, timelines, primary sources) MUST be fully included in the assignment JSON. NEVER tell students to "complete the data table" or "analyze the chart" without providing the actual table data or chart data in the question object. If a question references a table, include "expected_data" with headers and pre-filled data. If it references a reading passage, include the full passage text in the question field.
- For data_table questions: ALWAYS include "column_headers" (array of header strings), "row_labels" (array of row labels), and "expected_data" (2D array with ALL correct numeric/text values — NEVER leave cells empty or use placeholders). For calculation tables where some columns are GIVEN and others are for the student to CALCULATE, include "editable_columns" (array of 0-based column indices the student fills in). Given columns will be pre-filled for the student.
- CRITICAL: NEVER put table data as plain text or markdown pipes (| x | y |) inside the "question" string. If a question involves a table, use question_type "data_table" with structured data fields. Tables rendered as text are unreadable.
- For Math: Use REAL numbers and actual problems (e.g., "Solve: 3/4 + 1/2 = ?"), not placeholders
- All questions must be answerable based on the lesson content
- Include clear, specific answer keys
- Word problems should use realistic scenarios (shopping, cooking, sports) not fictional games or apps
- Avoid vague or overly complex language for the grade level
- NEVER use vague instructions like "analyze the data" without providing the data inline
- For math/computation questions: SELF-CHECK that all given numeric values are consistent. If a problem states theorem values (e.g., tangent squared = external times whole), verify the numbers satisfy the equation BEFORE including the question. Never give more numeric values than needed to solve the problem (over-determined systems confuse students).
- Word problems must clearly map to a single geometric/algebraic setup. Avoid mixing 2D circle theorems with 3D physical scenarios (towers, cables) unless the mapping is explicit and unambiguous.
- Every question must be solvable with ONLY the given information — no hidden assumptions or missing data required.
- For ELA/reading questions: If a question asks students to analyze, cite, or refer to a passage/text/excerpt, the FULL passage MUST be included in the "question" field. NEVER say "according to the passage" or "refer to the text" without embedding the actual passage text before the question. Quotations longer than one sentence must include attribution (author or source).
- For science questions: Use ONE consistent unit system (metric or imperial) per question — do NOT mix systems unless the question is explicitly about unit conversion. All values must be physically plausible (no negative mass, no temperatures below absolute zero, no pH outside 0-14, no percentages above 100% for concentrations/efficiency).

QUESTION TYPE GUIDANCE:
- For most questions, DO NOT set question_type — the system assigns it automatically from your text and structure.
- Write geometry dimensions clearly in question text: "Find the area of a triangle with base 8 cm and height 5 cm"
- Write equations clearly: "Graph y = 2x + 1 on the coordinate plane"
- For multiple choice, include "options" array. For matching, include "terms" and "definitions".
- For data_table: ONLY use when students must FILL IN values. Include "column_headers", "row_labels", "expected_data" (2D array with ALL correct values — NEVER leave cells empty). For calculation tables where some columns are GIVEN data and others are for the student to CALCULATE, also include "editable_columns" (array of column indices the student fills in). Columns NOT in editable_columns will be pre-filled for the student.
- ONLY set question_type explicitly for these complex types that need structured data:
  data_table (include headers, row_labels, expected_data, editable_columns),
  box_plot (include data array), dot_plot (include data),
  stem_and_leaf (include data), bar_chart (include chart_data),
  transformations (include original_vertices, transformation_type, transform_params),
  fraction_model (include model_type, denominator, correct_numerator),
  probability_tree, tape_diagram, venn_diagram,
  protractor (include mode, target_angle),
  multiselect (include options, correct indices),
  multi_part (include parts array),
  grid_match (include row_labels, column_labels, correct matrix),
  inline_dropdown (include dropdowns array)
- Students CANNOT draw/sketch. Use interactive components or ask them to upload a photo of handwritten work.
- NEVER say "View the graph" or "See the diagram" — the system renders visuals from data fields.

Return JSON with this structure:
{{
    "title": "Assignment title",
    "type": "{assignment_type}",
    "instructions": "Clear student instructions",
    "time_estimate": "Estimated completion time",
    "total_points": 100,
    "sections": [
        {{
            "name": "Section name (e.g., Part A: Vocabulary)",
            "type": "multiple_choice|fill_blank|short_answer|matching|essay|true_false|math_equation|data_table|coordinates",
            "points": 20,
            "questions": [
                {{
                    "number": 1,
                    "question": "The question text",
                    "question_type": "short_answer",  // or "math_equation", "data_table", "coordinates"
                    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],  // for multiple choice
                    "answer": "The correct answer",  // for most types
                    "expected_data": [[1, 2], [3, 4]],  // for data_table type — ALL cells must have real values
                    "editable_columns": [1],  // for data_table calculation tables — column indices students fill in
                    "tolerance": 0.05,  // for data_table (optional, default 5%)
                    "tolerance_km": 50,  // for coordinates (optional, default 50km)
                    "points": 2
                }}
            ]
        }}
    ],
    "answer_key": {{
        "section_name": ["answer1", "answer2", ...]
    }},
    "rubric": {{
        "criteria": [
            {{"name": "Criterion", "points": 10, "description": "What earns full points"}}
        ]
    }}
}}

SUBJECT-SPECIFIC GUIDANCE:

For MATH subjects:
- Include at least one "math_equation" section where students solve and write expressions
- Write geometry dimensions in text: "Find the area of a triangle with base 8 cm and height 5 cm"
- Write equations in text: "Graph y = 2x + 1 on the coordinate plane"

For ELA / READING subjects:
- Passage-based questions MUST embed the full passage in the "question" field BEFORE the question prompt.
  Example MC question JSON:
  {{"question": "Read the following passage:\\n\\nThe morning sun crept over the rooftops, casting long shadows across the empty schoolyard. Maria clutched her notebook and hesitated at the gate. Three years in this country and the words still tangled on her tongue like knots in wet rope. But today was different. Today she had a story to tell.\\n\\nThe author uses the simile 'like knots in wet rope' to convey that Maria —", "options": ["A) is frustrated by the rainy weather", "B) struggles to express herself in English", "C) is nervous about her school assignment", "D) feels tangled in a difficult situation"], "answer": "B", "dok": 2, "points": 1}}
- For vocabulary-in-context questions, include the sentence with the target word:
  {{"question": "In the sentence 'The committee voted to ratify the new policy despite vocal opposition,' what does the word 'ratify' most likely mean?", "options": ["A) reject", "B) formally approve", "C) discuss publicly", "D) delay indefinitely"], "answer": "B", "dok": 2, "points": 1}}
- Extended response must give the source text first, then the prompt with a rubric:
  {{"question": "Read the following excerpt from Frederick Douglass's 'Narrative of the Life of Frederick Douglass':\\n\\n'I did not, when a slave, understand the deep meaning of those rude and apparently incoherent songs. I was myself within the circle; and neither saw nor heard as those without might see and hear.'\\n\\nExplain how Douglass uses contrast to develop his central idea about the experience of slavery. Use at least two pieces of textual evidence to support your analysis.", "answer": "Strong response addresses Douglass's contrast between inside/outside perspective, quotes specific language, and explains how the rhetorical strategy develops the theme of misunderstanding slavery from the outside.", "dok": 3, "points": 4}}
- For matching sections, use literary/rhetorical terms:
  {{"question": "Match each literary device to its correct definition.", "terms": ["Metaphor", "Alliteration", "Foreshadowing", "Irony"], "definitions": ["Repetition of initial consonant sounds", "A hint about future events in a story", "A comparison without using like or as", "A contrast between expectation and reality"], "answer": {{"Metaphor": "A comparison without using like or as", "Alliteration": "Repetition of initial consonant sounds", "Foreshadowing": "A hint about future events in a story", "Irony": "A contrast between expectation and reality"}}, "dok": 1, "points": 2}}

For SCIENCE subjects:
The portal has interactive visual components — use them instead of referencing diagrams/figures.
NEVER say "refer to the diagram" or "look at the figure." Use structured data fields and the system renders the visual.

- DATA TABLE (question_type: "data_table") — for lab data, measurements, classification, calculations:
  Calculation table (some columns given, student calculates others):
  {{"question": "A student measured the time for a ball to roll down ramps of different heights. Complete the data table by calculating average speed (distance ÷ time) for each trial.", "question_type": "data_table", "column_headers": ["Ramp Height (cm)", "Distance (m)", "Time (s)", "Avg Speed (m/s)"], "row_labels": ["Trial 1", "Trial 2", "Trial 3", "Trial 4"], "expected_data": [[10, 2.0, 4.0, 0.50], [20, 2.0, 2.8, 0.71], [30, 2.0, 2.3, 0.87], [40, 2.0, 2.0, 1.00]], "editable_columns": [3], "answer": "speed = distance / time", "dok": 2, "points": 3}}

  Classification table:
  {{"question": "Classify each substance as an element, compound, or mixture.", "question_type": "data_table", "column_headers": ["Substance", "Classification", "Reasoning"], "row_labels": ["Oxygen (O₂)", "Water (H₂O)", "Salt water", "Iron (Fe)"], "expected_data": [["Oxygen (O₂)", "Element", "Single type of atom"], ["Water (H₂O)", "Compound", "Two elements chemically bonded"], ["Salt water", "Mixture", "Separable by evaporation"], ["Iron (Fe)", "Element", "Single type of atom"]], "answer": "See expected_data", "dok": 2, "points": 3}}

- BAR CHART (question_type: "bar_chart") — for comparing measurements, experiment results:
  {{"question": "The bar chart shows average monthly rainfall in Jacksonville, FL. Which month had the greatest increase compared to the previous month?", "question_type": "bar_chart", "chart_data": {{"labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"], "values": [3.3, 3.0, 3.9, 2.8, 3.6, 5.7], "title": "Average Monthly Rainfall (inches)"}}, "answer": "June (increased 2.1 inches from May)", "dok": 2, "points": 2}}

- DOT PLOT (question_type: "dot_plot") — for frequency distributions, repeated measurements:
  {{"question": "A student measured 15 leaf lengths (cm): 5, 6, 6, 7, 7, 7, 8, 8, 8, 8, 9, 9, 9, 10, 10. Create a dot plot showing the frequency of each length.", "question_type": "dot_plot", "minVal": 4, "maxVal": 11, "step": 1, "correct_dots": {{"5": 1, "6": 2, "7": 3, "8": 4, "9": 3, "10": 2}}, "answer": "Roughly normal distribution centered at 8 cm", "dok": 2, "points": 2}}

- BOX PLOT (question_type: "box_plot") — for data spread, comparing datasets:
  {{"question": "Calculate the five-number summary for each class's test scores.", "question_type": "box_plot", "data": [[65, 70, 72, 75, 78, 80, 82, 85, 88, 92], [55, 60, 68, 72, 75, 75, 80, 85, 90, 95]], "data_labels": ["Class A", "Class B"], "expected_values": {{"Class A": {{"min": 65, "q1": 72, "median": 79, "q3": 85, "max": 92}}, "Class B": {{"min": 55, "q1": 68, "median": 75, "q3": 85, "max": 95}}}}, "answer": "Class B has greater spread (range 40 vs 27) but lower median", "dok": 3, "points": 3}}

- COORDINATE PLANE (question_type: "coordinate_plane") — for plotting experimental data:
  {{"question": "A student recorded distance (m) over time (s): (0,0), (1,2), (2,4), (3,6), (4,8). Plot these points. What relationship do they show?", "question_type": "coordinate_plane", "x_range": [0, 6], "y_range": [0, 10], "points_to_plot": [[0,0], [1,2], [2,4], [3,6], [4,8]], "answer": "Linear/proportional — constant speed of 2 m/s", "dok": 2, "points": 3}}

- FUNCTION GRAPH (question_type: "function_graph") — for graphing physics equations:
  {{"question": "A ball thrown upward has height h = 20t - 5t². Graph this function. When does it reach maximum height?", "question_type": "function_graph", "x_range": [0, 5], "y_range": [0, 25], "correct_expressions": ["20x - 5x^2"], "answer": "Maximum height at t = 2 seconds (h = 20 m)", "dok": 3, "points": 3}}

- NUMBER LINE (question_type: "number_line") — for pH scale, temperature, ordering:
  {{"question": "Place these substances on the pH scale: lemon juice (pH 2), pure water (pH 7), baking soda (pH 9), stomach acid (pH 1.5), bleach (pH 13).", "question_type": "number_line", "min_val": 0, "max_val": 14, "points_to_plot": [1.5, 2, 7, 9, 13], "answer": "Stomach acid (1.5), lemon juice (2), water (7), baking soda (9), bleach (13)", "dok": 1, "points": 2}}

- VENN DIAGRAM (question_type: "venn_diagram") — for classification, comparing:
  {{"question": "Classify these characteristics as Plant Cells Only, Animal Cells Only, or Both: cell wall, cell membrane, chloroplasts, mitochondria, nucleus, large central vacuole, lysosomes, cytoplasm.", "question_type": "venn_diagram", "sets": 2, "labels": ["Plant Cells Only", "Animal Cells Only"], "mode": "element", "answer": "Plant Only: cell wall, chloroplasts, large central vacuole. Animal Only: lysosomes. Both: cell membrane, mitochondria, nucleus, cytoplasm", "dok": 2, "points": 3}}

- Experiment-based MC (describe full setup, no diagram references):
  {{"question": "A student places three identical plants in separate rooms. Plant A receives 12 hours of sunlight, Plant B receives 6 hours, and Plant C receives 0 hours. All plants receive the same water and soil. After 2 weeks, the student measures each plant's height. What is the independent variable?", "options": ["A) The height of the plants", "B) The amount of water given", "C) The number of hours of sunlight", "D) The type of plant used"], "answer": "C", "dok": 2, "points": 1}}

- Calculation with units (metric preferred for FL science):
  {{"question": "A block with a mass of 2.5 kg is pushed with a force of 10 N. Using F = ma, calculate the acceleration. Show your work.", "answer": "a = F/m = 10 N / 2.5 kg = 4 m/s²", "dok": 2, "points": 2}}

CRITICAL RULES FOR SCIENCE:
- Use ONE unit system per question (metric preferred). All values must be physically plausible.
- NEVER reference a diagram, figure, or image. Use the interactive components above instead.
- For classification → use data_table or venn_diagram
- For data analysis → use bar_chart, dot_plot, box_plot, or data_table
- For graphing relationships → use coordinate_plane or function_graph
- For ordering/scales → use number_line

For SOCIAL STUDIES / HISTORY subjects:
- Primary source questions MUST embed the source text, not reference it externally:
  {{"question": "Read the following excerpt from the Declaration of Independence (1776):\\n\\n'We hold these truths to be self-evident, that all men are created equal, that they are endowed by their Creator with certain unalienable Rights, that among these are Life, Liberty and the pursuit of Happiness. — That to secure these rights, Governments are instituted among Men, deriving their just powers from the consent of the governed.'\\n\\nBased on this excerpt, which Enlightenment idea MOST influenced the founders?", "options": ["A) Divine right of kings", "B) Social contract theory", "C) Mercantilism", "D) Manifest destiny"], "answer": "B", "dok": 2, "points": 1}}
- Cause-and-effect questions should be specific, not vague:
  {{"question": "Which event was a DIRECT cause of the United States entering World War I in 1917?", "options": ["A) The assassination of Archduke Franz Ferdinand", "B) Germany's unrestricted submarine warfare against American ships", "C) The Treaty of Versailles", "D) The formation of the League of Nations"], "answer": "B", "dok": 2, "points": 1}}
- Extended response with document analysis:
  {{"question": "Read the following quote from President Abraham Lincoln's Gettysburg Address (1863):\\n\\n'Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal. Now we are engaged in a great civil war, testing whether that nation, or any nation so conceived and so dedicated, can long endure.'\\n\\nExplain how Lincoln connects the founding ideals of the United States to the purpose of the Civil War. In your response, identify at least one specific founding ideal Lincoln references and explain why he believed the war was necessary to preserve it.", "answer": "Strong response identifies equality and/or liberty as founding ideals, explains Lincoln frames the Civil War as a test of whether democratic self-government can survive, and connects the 'proposition that all men are created equal' to the broader struggle over slavery and union.", "dok": 3, "points": 4}}
- Matching for key terms/events:
  {{"question": "Match each amendment to the right it protects.", "terms": ["1st Amendment", "2nd Amendment", "4th Amendment", "5th Amendment"], "definitions": ["Right to bear arms", "Freedom of speech, religion, and press", "Protection against self-incrimination", "Protection against unreasonable searches"], "answer": {{"1st Amendment": "Freedom of speech, religion, and press", "2nd Amendment": "Right to bear arms", "4th Amendment": "Protection against unreasonable searches", "5th Amendment": "Protection against self-incrimination"}}, "dok": 1, "points": 2}}

For GEOGRAPHY subjects:
- Include a "coordinates" section for map/location questions
- Location-based questions should test real places with coordinates:
  {{"question": "What is the capital city located nearest to the coordinates 30.4°N, 84.3°W?", "answer": "Tallahassee, Florida", "dok": 1, "points": 1}}
- Map analysis with data_table for comparison:
  {{"question": "Complete the table comparing physical features of Florida's five geographic regions.", "question_type": "data_table", "column_headers": ["Region", "Major Landform", "Elevation Range", "Key Water Feature"], "row_labels": ["Northwest", "Northeast", "Central", "Southwest", "Southeast"], "expected_data": [["Northwest", "Rolling hills", "50-100 m", "Apalachicola River"], ["Northeast", "Coastal plains", "0-30 m", "St. Johns River"], ["Central", "Lake region", "20-50 m", "Lake Okeechobee"], ["Southwest", "Low coastal plain", "0-15 m", "Everglades"], ["Southeast", "Coastal ridge", "0-5 m", "Biscayne Bay"]], "answer": "Students identify correct landforms, elevation ranges, and water features for each region", "dok": 2, "points": 3}}
{f'''
TEACHER ADDITIONAL REQUIREMENTS (MUST FOLLOW — every question/activity must reflect these):
{config.get('requirements', '').strip()}
''' if config.get('requirements', '').strip() else ''}
{f'''
TEACHER'S ADDITIONAL INSTRUCTIONS (MUST FOLLOW):
{config.get('globalAINotes', '')}
''' if config.get('globalAINotes') else ''}
Make the questions specific to the lesson content. Include a variety of question types appropriate for the assignment type.

"""

        completion = adapter.chat(LLMRequest(
            model="gpt-4o",
            system_prompt="You are an expert teacher. Return valid JSON only.",
            messages=[Message(role="user", content=[TextPart(text=prompt)])],
            response_format=ResponseFormat(type="json_object"),
            metadata={"feature_label": "generate_assignment_from_lesson"},
        ))

        content = completion.content_parts[0].text if completion.content_parts else "{}"
        assignment = json.loads(content)
        target_q = config.get('totalQuestions', 10)
        _ctx_uid, _ctx_client = _get_openai_context()
        assignment, extra_usage = _post_process_assignment(
            assignment, target_q, target_total_points=100,
            subject=config.get('subject'), grade=config.get('grade'),
            user_id=_ctx_uid, client=_ctx_client)
        # Embed context for portal grading (so AI grading has full 18-factor access)
        assignment['grade_level'] = config.get('grade', config.get('grade_level', '7'))
        assignment['subject'] = config.get('subject', 'General')
        usage = _extract_usage(completion, "gpt-4o")
        usage = _merge_usage(usage, extra_usage)
        _record_planner_cost(usage)
        return jsonify({"assignment": assignment, "method": "AI", "usage": usage, "content_only_mode": content_only})

    except Exception as e:
        error_msg = str(e)
        _logger.exception("Assignment Generation Error")

        # Detect network-blocked AI provider
        error_lower = error_msg.lower()
        if any(kw in error_lower for kw in ['connection', 'timeout', 'unreachable', 'refused', 'apiconnectionerror', 'connecttimeout', 'name resolution']):
            return jsonify({
                "error": "Unable to connect to the AI provider. This may be due to network restrictions on your school's network. "
                         "Try again from a different network or contact your IT department to allow access to OpenAI/Anthropic services.",
                "network_error": True,
            }), 503

        # Fallback mock assignment
        mock_assignment = {
            "title": f"{assignment_type.title()} - {lesson_plan.get('title', 'Lesson')}",
            "type": assignment_type,
            "instructions": "Complete all sections. Show your work.",
            "time_estimate": "30-45 minutes",
            "total_points": 100,
            "sections": [
                {
                    "name": "Part A: Key Concepts",
                    "type": "short_answer",
                    "points": 50,
                    "questions": [
                        {"number": 1, "question": "Explain the main concept from the lesson.", "points": 25},
                        {"number": 2, "question": "Give an example that demonstrates your understanding.", "points": 25}
                    ]
                },
                {
                    "name": "Part B: Vocabulary",
                    "type": "matching",
                    "points": 50,
                    "questions": [
                        {"number": 1, "question": "Match terms to definitions", "points": 50}
                    ]
                }
            ],
            "error": error_msg,
            "method": "Mock"
        }
        return jsonify({"assignment": mock_assignment, "method": "Mock", "error": error_msg})


@planner_bp.route('/api/export-lesson-plan', methods=['POST'])
@require_teacher
@handle_route_errors
def export_lesson_plan():
    """Export the lesson plan to a Word document."""
    data = request.json
    plan = data.get('plan', data)

    if not isinstance(plan, dict) or not any(
        plan.get(k) for k in (
            'overview', 'essential_questions', 'days',
            'unit_assessment', 'resources', 'sections',
        )
    ):
        return jsonify({"error": "Nothing to export: the lesson plan has no content."}), 400

    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()

        # Helper functions
        def format_vocab(vocab_list):
            if not vocab_list:
                return ""
            items = []
            for v in vocab_list:
                if isinstance(v, dict):
                    term = v.get('term', '')
                    defn = v.get('definition', '')
                    items.append(f"{term}: {defn}" if defn else term)
                else:
                    items.append(str(v))
            return '\n'.join(items)

        def format_bell_ringer(br):
            if not br:
                return ""
            if isinstance(br, str):
                return br
            prompt = br.get('prompt', '')
            responses = br.get('expected_responses', [])
            result = prompt
            if responses:
                result += "\n\nExpected Responses:\n" + '\n'.join(f"- {r}" for r in responses)
            return result

        def format_activity(act):
            if not act:
                return ""
            if isinstance(act, str):
                return act
            parts = []
            if act.get('name'):
                parts.append(f"Activity: {act['name']}")
            if act.get('description'):
                parts.append(act['description'])
            if act.get('grouping'):
                parts.append(f"Grouping: {act['grouping']}")
            if act.get('student_tasks'):
                parts.append("\nStudent Tasks:")
                for i, t in enumerate(act['student_tasks'], 1):
                    parts.append(f"  {i}. {t}")
            if act.get('differentiation'):
                diff = act['differentiation']
                if diff.get('struggling'):
                    parts.append(f"\nSupport for Struggling: {diff['struggling']}")
                if diff.get('advanced'):
                    parts.append(f"Extension for Advanced: {diff['advanced']}")
            return '\n'.join(parts)

        def format_assessment(asmt):
            if not asmt:
                return ""
            if isinstance(asmt, str):
                return asmt
            parts = []
            if asmt.get('type'):
                parts.append(f"Type: {asmt['type']}")
            if asmt.get('description'):
                parts.append(asmt['description'])
            if asmt.get('exit_ticket'):
                parts.append(f"\nExit Ticket: \"{asmt['exit_ticket']}\"")
            return '\n'.join(parts)

        # Title
        title = doc.add_heading(plan.get('title', 'Lesson Plan'), 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Overview
        if plan.get('overview'):
            doc.add_heading('Overview', level=1)
            doc.add_paragraph(plan['overview'])

        # Essential Questions
        if plan.get('essential_questions'):
            doc.add_heading('Essential Questions', level=1)
            for q in plan['essential_questions']:
                doc.add_paragraph(f"* {q}")

        # Daily Plans
        if plan.get('days'):
            doc.add_heading('Daily Lesson Plans', level=1)

            for day in plan['days']:
                doc.add_heading(f"Day {day.get('day')}: {day.get('topic')}", level=2)

                if day.get('objective'):
                    p = doc.add_paragraph()
                    p.add_run('Learning Objective: ').bold = True
                    p.add_run(day['objective'])

                if day.get('standards_addressed'):
                    p = doc.add_paragraph()
                    p.add_run('Standards: ').bold = True
                    p.add_run(', '.join(day['standards_addressed']))

                if day.get('timing'):
                    doc.add_heading('Lesson Timing', level=3)
                    for t in day['timing']:
                        time_str = t.get('minutes') or t.get('duration', '')
                        doc.add_paragraph(f"{time_str} - {t.get('activity', '')}: {t.get('description', '')}")

                vocab_text = format_vocab(day.get('vocabulary'))
                if vocab_text:
                    doc.add_heading('Vocabulary', level=3)
                    doc.add_paragraph(vocab_text)

                br_text = format_bell_ringer(day.get('bell_ringer'))
                if br_text:
                    doc.add_heading('Bell Ringer', level=3)
                    doc.add_paragraph(br_text)

                if day.get('direct_instruction'):
                    di = day['direct_instruction']
                    doc.add_heading('Direct Instruction', level=3)
                    if di.get('key_points'):
                        doc.add_paragraph('Key Points:')
                        for kp in di['key_points']:
                            doc.add_paragraph(f"* {kp}")
                    if di.get('check_for_understanding'):
                        doc.add_paragraph('\nCheck for Understanding:')
                        for q in di['check_for_understanding']:
                            doc.add_paragraph(f"* \"{q}\"")

                act_text = format_activity(day.get('activity'))
                if act_text:
                    doc.add_heading('Main Activity', level=3)
                    doc.add_paragraph(act_text)

                asmt_text = format_assessment(day.get('assessment'))
                if asmt_text:
                    doc.add_heading('Assessment', level=3)
                    doc.add_paragraph(asmt_text)

                if day.get('materials'):
                    doc.add_heading('Materials', level=3)
                    doc.add_paragraph(', '.join(day['materials']))

                if day.get('homework'):
                    doc.add_heading('Homework', level=3)
                    doc.add_paragraph(day['homework'])

                if day.get('teacher_notes'):
                    doc.add_heading('Teacher Notes', level=3)
                    doc.add_paragraph(day['teacher_notes'])

                doc.add_paragraph()

        # Unit Assessment
        if plan.get('unit_assessment'):
            doc.add_heading('Summative Assessment', level=1)
            ua = plan['unit_assessment']
            if isinstance(ua, dict):
                if ua.get('type'):
                    doc.add_paragraph(f"Type: {ua['type']}")
                if ua.get('description'):
                    doc.add_paragraph(ua['description'])
                if ua.get('components'):
                    doc.add_paragraph('\nComponents:')
                    for c in ua['components']:
                        doc.add_paragraph(f"* {c}")
            else:
                doc.add_paragraph(str(ua))

        # Resources
        if plan.get('resources'):
            doc.add_heading('Resources', level=1)
            for r in plan['resources']:
                doc.add_paragraph(f"* {r}")

        # Save file
        filename = f"Lesson_Plan_{int(time.time())}.docx"
        output_folder = graider_export_dir()
        os.makedirs(output_folder, exist_ok=True)
        filepath = os.path.join(output_folder, filename)
        doc.save(filepath)

        # Open the file
        if sys.platform == 'darwin':
            subprocess.run(['open', filepath], check=False)

        return jsonify({"status": "success", "path": filepath})

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


def _save_grading_config_for_export(assignment):
    """Auto-save a grading config so the Graider extraction pipeline can find expected answers.

    Builds gradingNotes from the answer key and saves to ~/.graider_assignments/.
    """
    try:
        title = assignment.get('title', 'Untitled')
        safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
        if not safe_title:
            return

        config_dir = os.path.expanduser("~/.graider_assignments")
        os.makedirs(config_dir, exist_ok=True)

        # Build grading notes from answers
        grading_lines = []
        sections = assignment.get('sections', [])
        answer_key = assignment.get('answer_key', {})

        # Try answer_key dict first (assessment format)
        if answer_key:
            for q_num, answer_data in sorted(answer_key.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
                if isinstance(answer_data, dict):
                    ans = answer_data.get('answer', '')
                else:
                    ans = str(answer_data)
                grading_lines.append(f"Q{q_num}: {ans}")
        else:
            # Fall back to extracting from sections (assignment format)
            q_idx = 1
            for section in sections:
                for q in section.get('questions', []):
                    answer = q.get('answer', '')
                    if answer:
                        grading_lines.append(f"Q{q.get('number', q_idx)}: {answer}")
                    q_idx += 1

        # Build plain-text and HTML representations for grading setup display
        doc_lines = [title, '', 'Name: ' + '_' * 50, 'Date: ' + '_' * 50,
                     'Period: ' + '_' * 50, '']
        html_parts = [
            '<style>',
            'body { font-family: Georgia, serif; line-height: 1.6; }',
            'table { border-collapse: collapse; width: 100%; margin: 15px 0; }',
            'td, th { border: 1px solid #ccc; padding: 8px 12px; text-align: left; }',
            'th { background: #f5f5f5; font-weight: bold; }',
            'p { margin: 10px 0; }',
            'h1, h2, h3 { margin: 20px 0 10px 0; }',
            '</style>',
            '<h1><strong>' + title + '</strong></h1>',
            '<p><strong>Name: </strong>' + '_' * 50 + '</p>',
            '<p><strong>Date: </strong>' + '_' * 50 + '</p>',
            '<p><strong>Period: </strong>' + '_' * 50 + '</p>',
        ]
        instructions = assignment.get('instructions', '')
        if instructions:
            doc_lines.append(instructions)
            doc_lines.append('')
            html_parts.append('<p><em>' + instructions + '</em></p>')
        q_num = 1
        for section in sections:
            sec_title = section.get('title', '')
            if sec_title:
                doc_lines.append(sec_title.upper())
                html_parts.append('<h2><strong>' + sec_title.upper() + '</strong></h2>')
            for q in section.get('questions', []):
                qtype = q.get('question_type', '')
                if qtype == 'vocab_term':
                    term = q.get('term', q.get('question', ''))
                    doc_lines.append(term + ': ' + '_' * 60)
                    html_parts.append('<table><tr><td><p><strong>' + term + ':</strong> ' + '_' * 60 + '</p></td></tr></table>')
                elif qtype in ('fill_in_blank', 'fitb'):
                    pts = str(q.get('points', 5))
                    qtxt = q.get('question', '')
                    doc_lines.append(str(q_num) + ') ' + qtxt + '  (' + pts + ' pts)')
                    doc_lines.append('Answer: ' + '_' * 55)
                    html_parts.append(
                        '<table><tr><td><p>[GRAIDER:QUESTION:' + str(q_num) + ']<strong>  '
                        + str(q_num) + ') ' + qtxt + '</strong>  (' + pts + ' pts)</p></td></tr>'
                        + '<tr><td><p><strong>Answer:</strong></p><p><em>Type your answer here...</em></p></td></tr></table>'
                    )
                else:
                    pts = str(q.get('points', 10))
                    qtxt = q.get('question', '')
                    doc_lines.append(str(q_num) + ') ' + qtxt + '  (' + pts + ' pts)')
                    doc_lines.append('Response: ' + '_' * 55)
                    doc_lines.append('_' * 65)
                    html_parts.append(
                        '<table><tr><td><p>[GRAIDER:QUESTION:' + str(q_num) + ']<strong>  '
                        + str(q_num) + ') ' + qtxt + '</strong>  (' + pts + ' pts)</p></td></tr>'
                        + '<tr><td><p><strong>Your Answer:</strong></p><p><em>Type your answer here...</em></p></td></tr></table>'
                    )
                doc_lines.append('')
                q_num += 1

        doc_text = '\n'.join(doc_lines)
        doc_html = '\n'.join(html_parts)

        config = {
            "title": title,
            "gradingNotes": "\n".join(grading_lines),
            "tableStructured": True,
            "tableVersion": "v1",
            "totalPoints": assignment.get('total_points', 100),
            "subject": assignment.get('subject', ''),
            "grade": assignment.get('grade', ''),
            "importedDoc": {
                "text": doc_text,
                "html": doc_html,
                "filename": safe_title + "_Student.docx",
                "loading": False
            },
        }

        config_path = os.path.join(config_dir, f"{safe_title}.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        # Also save to Supabase storage if available
        if storage_save:
            try:
                from flask import g
                teacher_id = getattr(g, 'user_id', 'local-dev')
                storage_save(f'assignment:{safe_title}', config, teacher_id)
            except Exception:
                pass  # Local save succeeded, Supabase is best-effort

        _logger.info("Saved grading config: %s", config_path)
    except Exception as e:
        _logger.warning("Could not save grading config: %s", e)


@planner_bp.route('/api/export-generated-assignment', methods=['POST'])
@require_teacher
@handle_route_errors
def export_generated_assignment():
    """Export a generated assignment to PDF or DOCX (with Graider tables) format."""
    data = request.json
    assignment = data.get('assignment', {})

    if not isinstance(assignment, dict) or not assignment.get('sections'):
        return jsonify({"error": "Nothing to export: the assignment has no questions."}), 400

    format_type = data.get('format', 'pdf')  # Default to PDF now
    include_answers = data.get('include_answers', False)

    title = assignment.get('title', 'Assignment')
    instructions = assignment.get('instructions', '')
    sections = assignment.get('sections', [])
    total_points = assignment.get('total_points', 100)
    time_estimate = assignment.get('time_estimate', '')
    teacher_name = data.get('teacher_name', '')
    subject_name = data.get('subject', '')

    # Inject teacher/subject into assignment for export functions
    if teacher_name:
        assignment['teacher_name'] = teacher_name
    if subject_name:
        assignment['subject'] = subject_name

    # DOCX with Graider tables for student worksheets
    if format_type == 'docx' and not include_answers:
        try:
            safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
            output_folder = graider_export_dir("Assignments")
            os.makedirs(output_folder, exist_ok=True)
            filepath = _export_assignment_docx_graider(assignment, output_folder, safe_title)
            _save_grading_config_for_export(assignment)
            if sys.platform == 'darwin':
                subprocess.run(['open', filepath], check=False)
            return jsonify({"status": "success", "path": filepath})
        except Exception as e:
            _logger.exception("Request failed: %s", request.path)
            return jsonify({"error": "An internal error occurred"}), 500

    # PDF path (answer keys and fallback)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.colors import black, gray, lightgrey, red, green
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Image,
            Table, TableStyle, PageBreak, KeepTogether, Flowable
        )
        from reportlab.lib.colors import white as rl_white
        import io

        # Bubble circle for MC/TF answer sheets
        class _BubbleCircle(Flowable):
            """Draws a circle bubble — empty (outline) or filled (solid black)."""
            def __init__(self, filled=False, size=9):
                Flowable.__init__(self)
                self.filled = filled
                self.size = size
                self.width = size + 4
                self.height = size + 4
            def draw(self):
                r = self.size / 2
                cx = r + 2
                cy = r + 2
                from reportlab.lib.colors import Color
                self.canv.setStrokeColor(Color(0.3, 0.3, 0.3))
                self.canv.setLineWidth(1.2)
                if self.filled:
                    self.canv.setFillColor(black)
                    self.canv.circle(cx, cy, r, fill=1)
                else:
                    self.canv.setFillColor(rl_white)
                    self.canv.circle(cx, cy, r, fill=1, stroke=1)

        # Set up styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'],
            alignment=TA_CENTER, fontSize=18, spaceAfter=6
        )
        heading_style = ParagraphStyle(
            'CustomHeading', parent=styles['Heading2'],
            fontSize=14, spaceAfter=6, spaceBefore=12
        )
        normal_style = styles['Normal']
        bold_style = ParagraphStyle(
            'Bold', parent=styles['Normal'],
            fontName='Helvetica-Bold'
        )
        center_style = ParagraphStyle(
            'Center', parent=styles['Normal'],
            alignment=TA_CENTER
        )
        answer_style = ParagraphStyle(
            'Answer', parent=styles['Normal'],
            fontName='Helvetica-Bold', textColor=green
        )

        # Helper: convert Unicode subscript/superscript to ReportLab XML tags
        _sub_map = str.maketrans('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎', '0123456789+-=()')
        _sup_map = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾', '0123456789+-=()')
        def _fix_sub_sup(text):
            """Replace Unicode sub/superscript chars with ReportLab <sub>/<sup> tags."""
            if not text:
                return text
            import re as _re
            # Subscripts: ₀-₉ and related
            def _replace_sub(m):
                return '<sub>' + m.group(0).translate(_sub_map) + '</sub>'
            def _replace_sup(m):
                return '<sup>' + m.group(0).translate(_sup_map) + '</sup>'
            text = _re.sub('[₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎]+', _replace_sub, text)
            text = _re.sub('[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾]+', _replace_sup, text)
            return text

        # Build the PDF
        safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
        suffix = "_ANSWER_KEY" if include_answers else "_Student"
        filename = f"{safe_title}{suffix}.pdf"
        output_folder = graider_export_dir("Assignments")
        os.makedirs(output_folder, exist_ok=True)
        filepath = os.path.join(output_folder, filename)

        doc = SimpleDocTemplate(
            filepath, pagesize=letter,
            topMargin=0.5*inch, bottomMargin=0.5*inch,
            leftMargin=0.75*inch, rightMargin=0.75*inch
        )

        story = []

        # Teacher name / subject header
        _teacher = assignment.get('teacher_name', '')
        _subject = assignment.get('subject', '')
        if _teacher or _subject:
            header_parts = []
            if _teacher:
                header_parts.append(_teacher)
            if _subject:
                header_parts.append(_subject)
            header_text = "  |  ".join(header_parts)
            header_style = ParagraphStyle(
                'TeacherHeader', parent=styles['Normal'],
                alignment=TA_CENTER, fontSize=11, textColor=gray
            )
            story.append(Paragraph(header_text, header_style))
            story.append(Spacer(1, 0.05*inch))

        # Title
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.1*inch))

        # Name/Date/Period or Answer Key header
        if include_answers:
            story.append(Paragraph(
                "<b>ANSWER KEY - FOR TEACHER USE ONLY</b>",
                center_style
            ))
        else:
            story.append(Paragraph(
                "Name: _______________________  Date: _______________  Period: _____",
                center_style
            ))

        # Total points only (no time limit on assignments)
        if total_points:
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph(f"Total Points: {total_points}", center_style))

        story.append(Spacer(1, 0.15*inch))

        # Instructions
        if instructions:
            story.append(Paragraph(f"<b>Instructions:</b> {instructions}", normal_style))
            story.append(Spacer(1, 0.15*inch))

        question_num = 1

        # Process sections
        for section in sections:
            section_name = section.get('name', 'Section')
            section_points = section.get('points', 0)
            section_type = section.get('type', 'short_answer')
            questions = section.get('questions', [])

            # Section header
            pts_text = f" ({section_points} points)" if section_points else ""
            story.append(Paragraph(f"<b>{section_name}</b>{pts_text}", heading_style))
            story.append(Spacer(1, 0.1*inch))  # Space between section header and questions

            for q in questions:
                q_number = q.get('number', question_num)
                q_text = _fix_sub_sup(q.get('question', ''))
                q_points = q.get('points', 0)
                q_options = [_fix_sub_sup(o) for o in q.get('options', [])]
                q_answer = q.get('answer', '')
                q_type = q.get('question_type', section_type)
                q_visual = q.get('visual_type', None)  # number_line, coordinate_plane, etc.

                # Question text — detect and render inline markdown tables
                pts_text = f" ({q_points} pts)" if q_points else ""
                table_parts = _split_markdown_table(q_text)
                if table_parts:
                    # Text before table
                    before_text = table_parts['before'].strip()
                    combined_before = f"<b>Question {q_number}:</b> {before_text}{pts_text}" if before_text else f"<b>Question {q_number}:</b>{pts_text}"
                    story.append(Paragraph(combined_before, normal_style))
                    story.append(Spacer(1, 0.05*inch))
                    # Render the table
                    md_table = table_parts['table']
                    t_data = [md_table['headers']] + md_table['rows']
                    col_count = len(md_table['headers'])
                    col_w = min(1.2*inch, (6.5*inch) / max(col_count, 1))
                    from reportlab.lib import colors as rl_colors
                    tbl = Table(t_data, colWidths=[col_w]*col_count)
                    tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.Color(0.9, 0.9, 0.95)),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.Color(0.6, 0.6, 0.6)),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ]))
                    story.append(tbl)
                    # Text after table
                    if table_parts.get('after', '').strip():
                        story.append(Paragraph(table_parts['after'].strip(), normal_style))
                    story.append(Spacer(1, 0.05*inch))
                else:
                    story.append(Paragraph(
                        f"<b>Question {q_number}:</b> {q_text}{pts_text}",
                        normal_style
                    ))
                    story.append(Spacer(1, 0.05*inch))

                # Multiple choice options with bubble circles
                if q_options and q_type != 'matching':
                    is_tf = q_type in ('true_false', 'tf')
                    # Determine correct answer index for answer key
                    correct_idx = None
                    if include_answers and q_answer:
                        if is_tf:
                            for oi, opt in enumerate(q_options):
                                if opt.lower().strip() == str(q_answer).lower().strip():
                                    correct_idx = oi
                                    break
                        else:
                            from backend.services.worksheet_generator import _normalize_correct_answer_to_letter
                            letter = _normalize_correct_answer_to_letter(q_answer, q_options)
                            if letter:
                                correct_idx = ord(letter) - ord('A')

                    for oi, opt in enumerate(q_options):
                        is_filled = (include_answers and correct_idx is not None and oi == correct_idx)
                        bubble = _BubbleCircle(filled=is_filled, size=9)
                        opt_para = Paragraph(opt, normal_style)
                        row_table = Table(
                            [[bubble, opt_para]],
                            colWidths=[0.5*inch, 5.5*inch],
                        )
                        row_table.setStyle(TableStyle([
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                            ('LEFTPADDING', (0, 0), (0, 0), 20),
                            ('LEFTPADDING', (1, 0), (1, 0), 0),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                            ('TOPPADDING', (0, 0), (-1, -1), 2),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                        ]))
                        story.append(row_table)

                # Matching question: render terms and definitions columns
                q_terms = q.get('terms', [])
                q_definitions = q.get('definitions', [])
                if (q_type == 'matching' or (q_terms and q_definitions)):
                    q_terms = [_fix_sub_sup(str(t)) for t in q_terms]
                    q_definitions = [_fix_sub_sup(str(d)) for d in q_definitions]
                    from reportlab.lib import colors as rl_colors
                    import random as _random
                    # Shuffle definitions for student version
                    shuffled_defs = list(q_definitions)
                    if not include_answers:
                        _random.seed(q_number)  # Deterministic shuffle per question
                        _random.shuffle(shuffled_defs)
                    # Build two-column table: numbered terms | lettered definitions
                    # Use Paragraph objects for definitions so they word-wrap
                    def_style = ParagraphStyle('MatchDef', parent=normal_style, fontSize=10)
                    term_style = ParagraphStyle('MatchTerm', parent=normal_style, fontSize=10)
                    max_rows = max(len(q_terms), len(shuffled_defs))
                    match_data = [['', 'Terms', '', 'Definitions']]
                    for ri in range(max_rows):
                        term_num = str(ri + 1) + '.' if ri < len(q_terms) else ''
                        term_text = Paragraph(q_terms[ri], term_style) if ri < len(q_terms) else ''
                        def_letter = chr(65 + ri) + '.' if ri < len(shuffled_defs) else ''
                        def_text = Paragraph(shuffled_defs[ri], def_style) if ri < len(shuffled_defs) else ''
                        match_data.append([term_num, term_text, def_letter, def_text])
                    col_widths = [0.3*inch, 2.2*inch, 0.3*inch, 3.5*inch]
                    match_tbl = Table(match_data, colWidths=col_widths)
                    match_tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.Color(0.9, 0.9, 0.95)),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                        ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.Color(0.6, 0.6, 0.6)),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ]))
                    story.append(Spacer(1, 0.05*inch))
                    story.append(match_tbl)
                    story.append(Spacer(1, 0.05*inch))

                # Add visual elements based on question type
                if q_visual or q_type in ['number_line', 'coordinate_plane', 'graph',
                                          'geometry', 'triangle', 'rectangle', 'regular_polygon',
                                          'circle', 'trapezoid', 'parallelogram',
                                          'rectangular_prism', 'cylinder',
                                          'pythagorean', 'trig', 'angles', 'similarity',
                                          'box_plot', 'bar_chart', 'function_graph',
                                          'dot_plot', 'stem_and_leaf', 'unit_circle',
                                          'transformations', 'fraction_model',
                                          'probability_tree', 'tape_diagram',
                                          'venn_diagram', 'protractor', 'angle_protractor',
                                          'histogram', 'pie_chart']:
                    visual_image = _create_visual_for_question(q, include_answers)
                    if visual_image:
                        story.append(Spacer(1, 0.1*inch))
                        story.append(visual_image)
                        story.append(Spacer(1, 0.1*inch))

                # Answer section
                if include_answers:
                    # MC/TF: filled bubble already shows the answer — skip text label
                    if q_options and q_type != 'matching':
                        pass  # Bubble is already filled above
                    elif q_type == 'matching' or (q_terms and q_definitions):
                        if isinstance(q_answer, dict):
                            ans_parts = [f"{k} → {v}" for k, v in q_answer.items()]
                            ans_text = "ANSWERS: " + " | ".join(ans_parts)
                        else:
                            ans_text = f"ANSWER: {q_answer}"
                        story.append(Paragraph(f"<b>{_fix_sub_sup(str(ans_text))}</b>", answer_style))
                    elif q_type == 'coordinates' and isinstance(q_answer, dict):
                        ans_text = f"ANSWER: Lat: {q_answer.get('lat', 0)}, Lng: {q_answer.get('lng', 0)}"
                        story.append(Paragraph(f"<b>{_fix_sub_sup(str(ans_text))}</b>", answer_style))
                    else:
                        ans_text = f"ANSWER: {q_answer}"
                        story.append(Paragraph(f"<b>{_fix_sub_sup(str(ans_text))}</b>", answer_style))

                    if q_type == 'math_equation':
                        story.append(Paragraph("<i>(Equivalent forms accepted)</i>", normal_style))
                    elif q_type == 'coordinates':
                        tolerance_km = q.get('tolerance_km', 50)
                        story.append(Paragraph(f"<i>(Acceptable within {tolerance_km} km)</i>", normal_style))
                else:
                    # Answer space for students
                    if q_type == 'matching' or (q_terms and q_definitions):
                        pass  # Match table already has answer blanks
                    elif q_type == 'math_equation':
                        story.append(Paragraph("Show your work:", normal_style))
                        for _ in range(3):
                            story.append(Paragraph("_" * 85, normal_style))
                        story.append(Paragraph("<b>Final Answer:</b> " + "_" * 50, normal_style))
                    elif q_type == 'coordinates':
                        story.append(Paragraph(
                            "<b>Latitude:</b> _______________°  <b>Longitude:</b> _______________°",
                            normal_style
                        ))
                    elif q_type == 'data_table':
                        # Create empty table — handle both normalized and raw AI field names
                        headers = q.get('headers', q.get('column_headers', ['Column 1', 'Column 2', 'Column 3']))
                        row_labels = q.get('row_labels', [])
                        expected = q.get('expected_data', [])
                        num_rows = q.get('num_rows', len(expected) if expected else 5)
                        if row_labels:
                            table_data = [[''] + headers]
                            for ri in range(num_rows):
                                label = row_labels[ri] if ri < len(row_labels) else ''
                                table_data.append([label] + [''] * len(headers))
                        else:
                            table_data = [headers] + [[''] * len(headers) for _ in range(num_rows)]
                        col_count = len(table_data[0])
                        t = Table(table_data, colWidths=[1.5*inch] * col_count)
                        t.setStyle(TableStyle([
                            ('GRID', (0, 0), (-1, -1), 1, black),
                            ('BACKGROUND', (0, 0), (-1, 0), lightgrey),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('FONTSIZE', (0, 0), (-1, -1), 10),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                            ('TOPPADDING', (0, 0), (-1, -1), 12),
                        ]))
                        story.append(t)
                    elif section_type in ['essay', 'extended_response']:
                        for _ in range(8):
                            story.append(Paragraph("_" * 85, normal_style))
                    elif section_type == 'short_answer':
                        for _ in range(3):
                            story.append(Paragraph("_" * 85, normal_style))
                    elif section_type in ['multiple_choice', 'true_false']:
                        pass  # Bubbles are the answer — no separate answer line needed
                    else:
                        for _ in range(2):
                            story.append(Paragraph("_" * 85, normal_style))

                story.append(Spacer(1, 0.15*inch))
                question_num += 1

        # Rubric for teacher version
        if include_answers and assignment.get('rubric', {}).get('criteria'):
            story.append(PageBreak())
            story.append(Paragraph("<b>Grading Rubric</b>", heading_style))
            for criterion in assignment['rubric']['criteria']:
                story.append(Paragraph(
                    f"<b>{criterion.get('name', 'Criterion')}:</b> "
                    f"{criterion.get('points', 0)} points - {criterion.get('description', '')}",
                    normal_style
                ))
                story.append(Spacer(1, 0.05*inch))

        # Build PDF
        doc.build(story)

        # Open the file
        if sys.platform == 'darwin':
            subprocess.run(['open', filepath], check=False)

        return jsonify({"status": "success", "path": filepath})

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


# =============================================================================
# ASSESSMENT GENERATION
# =============================================================================

@planner_bp.route('/api/generate-assessment', methods=['POST'])
@limiter.limit("10 per minute")
@require_teacher
@handle_route_errors
def generate_assessment():
    """
    Generate a standards-aligned assessment with DOK level distribution.

    Request body:
    {
        "standards": [{"code": "SS.8.A.1.1", "benchmark": "...", "dok": 2, ...}],
        "config": {
            "grade": "8",
            "subject": "US History",
            "teacher_name": "Mr. Smith"
        },
        "assessmentConfig": {
            "type": "quiz",  // quiz, test, benchmark, formative
            "title": "Chapter 5 Assessment",
            "totalQuestions": 15,
            "questionTypes": {
                "multiple_choice": 10,
                "short_answer": 3,
                "extended_response": 2
            },
            "dokDistribution": {
                "1": 3,   // 3 DOK 1 questions
                "2": 6,   // 6 DOK 2 questions
                "3": 4,   // 4 DOK 3 questions
                "4": 2    // 2 DOK 4 questions
            },
            "includeAnswerKey": true,
            "includeStandardsReference": true
        }
    }
    """
    data = request.json
    standards = data.get('standards', [])
    config = data.get('config', {})
    assessment_config = data.get('assessmentConfig', {})
    content_only = config.get('contentOnly', False)

    # Normalize standards: accept both dicts and plain code strings
    normalized = []
    for s in standards:
        if isinstance(s, str):
            normalized.append({'code': s})
        elif isinstance(s, dict):
            normalized.append(s)
    standards = normalized

    if not standards:
        return jsonify({"error": "No standards provided"})

    _subject = config.get('subject', '').strip()
    _grade = config.get('grade', '').strip()
    if not _subject or not _grade:
        from flask import current_app
        current_app.logger.warning(
            f"Assessment requested without subject/grade: subject={_subject!r}, grade={_grade!r}")

    try:
        from backend.api_keys import get_api_key as _gak
        from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart
        api_key = _gak('openai', getattr(g, 'user_id', 'local-dev'))

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        adapter = OpenAIAdapter(api_key=api_key)

        # Extract assessment configuration
        assessment_type = assessment_config.get('type', 'quiz')
        title = assessment_config.get('title', f'{config.get("subject", "Subject")} Assessment')
        total_questions = assessment_config.get('totalQuestions', 15)
        total_points = assessment_config.get('totalPoints', 30)
        question_types = assessment_config.get('questionTypes', {
            'multiple_choice': 10,
            'short_answer': 3,
            'extended_response': 2,
            'true_false': 0,
            'matching': 0,
            'math_equation': 0,
            'data_table': 0
        })
        points_per_type = assessment_config.get('pointsPerType', {
            'multiple_choice': 1,
            'short_answer': 2,
            'extended_response': 4,
            'true_false': 1,
            'matching': 1,
            'math_equation': 2,
            'data_table': 3
        })
        dok_distribution = assessment_config.get('dokDistribution', {
            '1': 3, '2': 6, '3': 4, '4': 2
        })
        include_answer_key = assessment_config.get('includeAnswerKey', True)
        include_standards_ref = assessment_config.get('includeStandardsReference', True)
        target_period = assessment_config.get('targetPeriod', '')
        section_categories = assessment_config.get('sectionCategories', {})

        # Get global AI notes from config
        global_ai_notes = config.get('globalAINotes', '')

        # Get content sources (lessons/assignments to base questions on)
        content_sources = data.get('contentSources', [])

        # Build content sources context
        source_content = ""
        if content_sources:
            source_content = "\n=== INSTRUCTIONAL CONTENT TO BASE QUESTIONS ON ===\n"
            source_content += "Generate questions that test the specific content, vocabulary, examples, and activities from these lessons/assignments:\n\n"

            for source in content_sources:
                if source.get('type') == 'lesson':
                    lesson = source.get('content', {})
                    source_content += f"--- LESSON: {lesson.get('title', 'Untitled')} ---\n"
                    source_content += f"Overview: {lesson.get('overview', '')}\n"

                    objectives = lesson.get('learning_objectives', [])
                    if objectives:
                        source_content += f"Learning Objectives: {', '.join(objectives)}\n"

                    questions = lesson.get('essential_questions', [])
                    if questions:
                        source_content += f"Essential Questions: {', '.join(questions)}\n"

                    # Include activities from each day
                    for day in lesson.get('days', []):
                        source_content += f"\nDay {day.get('day', '?')}: {day.get('focus', '')}\n"
                        for activity in day.get('activities', []):
                            source_content += f"  - {activity.get('name', '')}: {activity.get('description', '')}\n"

                    source_content += "\n"

                elif source.get('type') == 'assignment':
                    assignment = source.get('content', {})
                    source_content += f"--- ASSIGNMENT: {assignment.get('title', 'Untitled')} ---\n"
                    source_content += f"Instructions: {assignment.get('instructions', '')}\n"
                    for q in assignment.get('questions', []):
                        source_content += f"  - {q.get('marker', '')}: {q.get('prompt', '')}\n"
                    source_content += "\n"

                elif source.get('type') == 'document':
                    doc_content = source.get('content', {})
                    doc_text = doc_content.get('text', '')[:6000]
                    doc_name = doc_content.get('filename', 'Uploaded Document')
                    source_content += f"--- REFERENCE DOCUMENT: {doc_name} ---\n"
                    source_content += doc_text + "\n\n"

            source_content += "=== END INSTRUCTIONAL CONTENT ===\n\n"
            if content_only:
                source_content += "CRITICAL: The teacher wants ALL questions to come ONLY from the content above. "
                source_content += "Every question must be answerable using ONLY information found in these documents/lessons. "
                source_content += "Use the selected standards to guide question format, rigor level (DOK), and cognitive demand — "
                source_content += "but do NOT create questions about topics not covered in the content above.\n\n"
            else:
                source_content += "IMPORTANT: Questions must directly relate to the content above. Reference specific vocabulary, examples, and concepts from the lessons.\n\n"

        # Build standards context
        standards_context = []
        for std in standards:
            std_info = f"""
Standard: {std.get('code', 'N/A')}
Benchmark: {std.get('benchmark', 'N/A')}
DOK Level: {std.get('dok', 2)}
Topics: {', '.join(std.get('topics', []))}
Vocabulary: {', '.join(std.get('vocabulary', [])[:10])}
Learning Targets: {chr(10).join('- ' + lt for lt in std.get('learning_targets', [])[:3])}
Sample Assessment: {std.get('sample_assessment', 'N/A')}
"""
            standards_context.append(std_info)

        # DOK level descriptions for the prompt
        dok_descriptions = """
DOK LEVEL DESCRIPTIONS (Webb's Depth of Knowledge):

DOK 1 - Recall & Reproduction:
- Recall facts, terms, definitions
- Identify, recognize, list, name
- Simple one-step procedures
- Math example: "What is the value of 3² + 4²?"
- ELA example: "What is the definition of a metaphor?"
- Science example: "What is the chemical symbol for water?"
- Social Studies example: "What year did the Civil War begin?"

DOK 2 - Skills & Concepts:
- Compare, contrast, classify, organize
- Make observations, collect data
- Explain relationships, cause/effect
- Math example: "Compare the slopes of y = 2x + 1 and y = 3x - 4. Which line is steeper?"
- ELA example: "How does the author's use of dialogue in paragraph 3 reveal the character's motivation?"
- Science example: "Based on the data table, describe the relationship between ramp height and average speed."
- Social Studies example: "Compare the economies of the North and South before the Civil War."

DOK 3 - Strategic Thinking:
- Analyze, evaluate, synthesize
- Draw conclusions, cite evidence
- Develop a logical argument
- Math example: "A store offers 20% off plus an additional 10% at checkout. A customer claims this is the same as 30% off. Use mathematics to prove or disprove this claim."
- ELA example: "Using evidence from the text, analyze how the author's word choice creates a tone of urgency in the final paragraph."
- Science example: "Design an experiment to test whether salt concentration affects the boiling point of water. Identify your variables and explain your procedure."
- Social Studies example: "Using evidence from both documents, explain how economic differences contributed to sectional tensions leading to the Civil War."

DOK 4 - Extended Thinking:
- Design, create, connect across content
- Research, investigate over time
- Apply concepts to new situations
- Math example: "Design a budget for a school fundraiser that must raise at least $500. Include revenue projections, expenses, and a break-even analysis with supporting calculations."
- ELA example: "Write an argumentative essay evaluating whether social media has a net positive or negative effect on teen literacy. Cite at least three sources."
- Science example: "Propose a solution to reduce nutrient runoff in Florida's waterways. Explain the science behind your solution and predict its environmental impact."
- Social Studies example: "Analyze how Civil War-era economic patterns continue to influence regional differences in the United States today. Support your argument with historical and modern evidence."
"""

        # Question type instructions
        question_type_instructions = """
QUESTION TYPE GUIDANCE:
- For most questions, DO NOT set question_type — the system assigns it from your text and structure.
- Include "options" for multiple choice, "terms"/"definitions" for matching.
- Write geometry dimensions clearly in text: "Find the area of a triangle with base 8 cm and height 5 cm"
- Write equations clearly: "Graph y = 2x + 1 on the coordinate plane"
- ONLY set question_type explicitly for complex types needing structured data:
  data_table (include column_headers, row_labels, expected_data with ALL values, editable_columns for calculation tables),
  box_plot (include data), dot_plot (include data), stem_and_leaf (include data),
  bar_chart (include chart_data), transformations, fraction_model, probability_tree,
  tape_diagram, venn_diagram, protractor,
  multiselect (include options + correct indices array),
  multi_part (include parts array with label, question_type, question, options, answer),
  grid_match (include row_labels, column_labels, correct 2D array),
  inline_dropdown (include dropdowns array with options + correct index)
- Every question MUST include: "dok" (1-4), "standard" (code), "points", and answer.
"""

        # Build subject-specific question examples
        subject_lower = config.get('subject', '').lower()
        subject_question_examples = ""
        if any(kw in subject_lower for kw in ['ela', 'english', 'reading', 'language arts', 'literature', 'writing']):
            subject_question_examples = """
SUBJECT-SPECIFIC QUESTION EXAMPLES (ELA/Reading — follow these patterns):

Passage-based MC (MUST embed the full passage):
{"question": "Read the following passage:\\n\\nThe morning sun crept over the rooftops, casting long shadows across the empty schoolyard. Maria clutched her notebook and hesitated at the gate. Three years in this country and the words still tangled on her tongue like knots in wet rope. But today was different. Today she had a story to tell.\\n\\nThe author uses the simile 'like knots in wet rope' to convey that Maria —", "options": ["A) is frustrated by the rainy weather", "B) struggles to express herself in English", "C) is nervous about her school assignment", "D) feels tangled in a difficult situation"], "answer": "B", "dok": 2, "points": 1}

Vocabulary in context:
{"question": "In the sentence 'The committee voted to ratify the new policy despite vocal opposition,' what does 'ratify' most likely mean?", "options": ["A) reject", "B) formally approve", "C) discuss publicly", "D) delay indefinitely"], "answer": "B", "dok": 2, "points": 1}

Extended response with source text:
{"question": "Read the following excerpt from Frederick Douglass's 'Narrative of the Life of Frederick Douglass':\\n\\n'I did not, when a slave, understand the deep meaning of those rude and apparently incoherent songs. I was myself within the circle; and neither saw nor heard as those without might see and hear.'\\n\\nExplain how Douglass uses contrast to develop his central idea about the experience of slavery. Use at least two pieces of textual evidence.", "answer": "Strong response addresses inside/outside perspective contrast, quotes specific language, explains how the strategy develops the theme.", "dok": 3, "points": 4}

Matching (literary/rhetorical terms):
{"question": "Match each literary device to its definition.", "terms": ["Metaphor", "Alliteration", "Foreshadowing", "Irony"], "definitions": ["Repetition of initial consonant sounds", "A hint about future events", "A comparison without like or as", "A contrast between expectation and reality"], "dok": 1, "points": 2}

CRITICAL: EVERY passage-based question must have the passage text INSIDE the question field. Never say 'according to the passage' without providing it.
"""
        elif any(kw in subject_lower for kw in ['science', 'biology', 'chemistry', 'physics', 'earth', 'environmental']):
            subject_question_examples = """
SUBJECT-SPECIFIC QUESTION EXAMPLES (Science — follow these patterns):

The portal has interactive visual components you MUST use instead of asking students to "look at a diagram."
NEVER reference a figure, diagram, or image that isn't provided as structured data. Use the components below.

=== DATA TABLE (question_type: "data_table") ===
Use for: lab data, experiment results, classification, measurements, calculations.
Students see headers and row labels and fill in the values.

Lab data collection (calculation table — given columns pre-filled, student calculates others):
{"question": "A student measured the time it takes for a ball to roll down ramps of different heights. Complete the data table by calculating the average speed (distance ÷ time) for each trial.", "question_type": "data_table", "column_headers": ["Ramp Height (cm)", "Distance (m)", "Time (s)", "Avg Speed (m/s)"], "row_labels": ["Trial 1", "Trial 2", "Trial 3", "Trial 4"], "expected_data": [[10, 2.0, 4.0, 0.50], [20, 2.0, 2.8, 0.71], [30, 2.0, 2.3, 0.87], [40, 2.0, 2.0, 1.00]], "editable_columns": [3], "answer": "Students calculate speed = distance / time for each trial", "dok": 2, "points": 3}

Classification table:
{"question": "Classify each substance as an element, compound, or mixture by completing the table.", "question_type": "data_table", "column_headers": ["Substance", "Classification", "Reasoning"], "row_labels": ["Oxygen (O₂)", "Water (H₂O)", "Salt water", "Iron (Fe)", "Carbon dioxide (CO₂)"], "expected_data": [["Oxygen (O₂)", "Element", "Single type of atom"], ["Water (H₂O)", "Compound", "Two elements chemically bonded"], ["Salt water", "Mixture", "Can be separated by evaporation"], ["Iron (Fe)", "Element", "Single type of atom"], ["Carbon dioxide (CO₂)", "Compound", "Two elements chemically bonded"]], "answer": "See expected_data", "dok": 2, "points": 3}

=== BAR CHART (question_type: "bar_chart") ===
Use for: comparing measurements, experiment results, population data, rainfall, temperatures.
The chart displays automatically from the data — students answer a text question about it.

{"question": "The bar chart shows the average monthly rainfall in Jacksonville, FL from January to June. Which month had the greatest increase in rainfall compared to the previous month? Explain your reasoning.", "question_type": "bar_chart", "chart_data": {"labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"], "values": [3.3, 3.0, 3.9, 2.8, 3.6, 5.7], "title": "Average Monthly Rainfall (inches)"}, "answer": "June — increased by 2.1 inches from May (5.7 - 3.6 = 2.1), the largest single-month increase", "dok": 2, "points": 2}

=== DOT PLOT (question_type: "dot_plot") ===
Use for: frequency distributions, repeated measurements, class survey data.
Students click to place dots above values on a number line.

{"question": "A student measured the length of 15 leaves from a tree (in cm): 5, 6, 6, 7, 7, 7, 8, 8, 8, 8, 9, 9, 9, 10, 10. Create a dot plot showing the frequency of each leaf length.", "question_type": "dot_plot", "minVal": 4, "maxVal": 11, "step": 1, "correct_dots": {"5": 1, "6": 2, "7": 3, "8": 4, "9": 3, "10": 2}, "answer": "Dot plot shows a roughly normal distribution centered at 8 cm", "dok": 2, "points": 2}

=== BOX PLOT (question_type: "box_plot") ===
Use for: data spread analysis, comparing datasets, identifying outliers.
Students fill in the five-number summary values.

{"question": "The following data shows test scores for two classes. Calculate the five-number summary (min, Q1, median, Q3, max) for each class and compare their distributions.", "question_type": "box_plot", "data": [[65, 70, 72, 75, 78, 80, 82, 85, 88, 92], [55, 60, 68, 72, 75, 75, 80, 85, 90, 95]], "data_labels": ["Class A", "Class B"], "expected_values": {"Class A": {"min": 65, "q1": 72, "median": 79, "q3": 85, "max": 92}, "Class B": {"min": 55, "q1": 68, "median": 75, "q3": 85, "max": 95}}, "answer": "Class B has greater spread (range 40 vs 27) but lower median (75 vs 79)", "dok": 3, "points": 3}

=== COORDINATE PLANE (question_type: "coordinate_plane") ===
Use for: plotting experimental data points, graphing relationships, distance/position.
Students click to place points on an x-y grid.

{"question": "A student recorded the distance (m) a toy car traveled over time (s): (0,0), (1,2), (2,4), (3,6), (4,8). Plot these data points on the coordinate plane. What type of relationship do the data show?", "question_type": "coordinate_plane", "x_range": [0, 6], "y_range": [0, 10], "points_to_plot": [[0,0], [1,2], [2,4], [3,6], [4,8]], "answer": "Linear/proportional relationship — distance increases by 2 m every second (constant speed of 2 m/s)", "dok": 2, "points": 3}

=== FUNCTION GRAPH (question_type: "function_graph") ===
Use for: graphing physics equations, linear relationships, exponential growth/decay.
Students type equations and see them graphed live.

{"question": "A ball is thrown upward with an initial velocity of 20 m/s. Its height (in meters) over time can be modeled by h = 20t - 5t². Graph this function. At what time does the ball reach its maximum height?", "question_type": "function_graph", "x_range": [0, 5], "y_range": [0, 25], "correct_expressions": ["20x - 5x^2"], "answer": "Maximum height at t = 2 seconds (h = 20 meters)", "dok": 3, "points": 3}

=== NUMBER LINE (question_type: "number_line") ===
Use for: pH scale, temperature, timelines, ordering values.
Students click to place points on a linear scale.

{"question": "Place the following substances on the pH scale based on their approximate pH values: lemon juice (pH 2), pure water (pH 7), baking soda (pH 9), stomach acid (pH 1.5), bleach (pH 13).", "question_type": "number_line", "min_val": 0, "max_val": 14, "points_to_plot": [1.5, 2, 7, 9, 13], "answer": "Stomach acid (1.5), lemon juice (2), pure water (7), baking soda (9), bleach (13)", "dok": 1, "points": 2}

=== VENN DIAGRAM (question_type: "venn_diagram") ===
Use for: classification, comparing organisms/elements/processes, set relationships.
Students fill in values or labels in overlapping regions.

{"question": "Use the Venn diagram to classify the following characteristics as belonging to Plant Cells Only, Animal Cells Only, or Both: cell wall, cell membrane, chloroplasts, mitochondria, nucleus, large central vacuole, lysosomes, cytoplasm.", "question_type": "venn_diagram", "sets": 2, "labels": ["Plant Cells Only", "Animal Cells Only"], "mode": "element", "answer": "Plant Only: cell wall, chloroplasts, large central vacuole. Animal Only: lysosomes. Both: cell membrane, mitochondria, nucleus, cytoplasm", "dok": 2, "points": 3}

=== STANDARD TYPES (no special question_type needed) ===

Experiment-based MC (describe the full setup):
{"question": "A student places three identical plants in separate rooms. Plant A receives 12 hours of sunlight, Plant B receives 6 hours, and Plant C receives 0 hours. All plants receive the same amount of water and soil. After 2 weeks, the student measures the height of each plant. What is the independent variable in this experiment?", "options": ["A) The height of the plants", "B) The amount of water given", "C) The number of hours of sunlight", "D) The type of plant used"], "answer": "C", "dok": 2, "points": 1}

Calculation with units (use metric, show work):
{"question": "A block with a mass of 2.5 kg is pushed with a force of 10 N across a frictionless surface. Using Newton's second law (F = ma), calculate the acceleration of the block. Show your work.", "answer": "a = F/m = 10 N / 2.5 kg = 4 m/s²", "dok": 2, "points": 2}

Vocabulary matching (science terms):
{"question": "Match each term to its correct definition.", "terms": ["Independent variable", "Dependent variable", "Control group", "Hypothesis"], "definitions": ["The group that does not receive the experimental treatment", "The factor that is measured in an experiment", "A testable prediction about the outcome", "The factor that the scientist changes on purpose"], "answer": {"Independent variable": "The factor that the scientist changes on purpose", "Dependent variable": "The factor that is measured in an experiment", "Control group": "The group that does not receive the experimental treatment", "Hypothesis": "A testable prediction about the outcome"}, "dok": 1, "points": 2}

CRITICAL RULES FOR SCIENCE QUESTIONS:
- Use ONE consistent unit system per question (metric preferred for FL science). All values must be physically plausible.
- NEVER reference a diagram, figure, image, or illustration. Use the interactive components above instead.
- For classification tasks, use data_table or venn_diagram — not "draw a chart" or "create a diagram."
- For data analysis, ALWAYS include the actual data using bar_chart, dot_plot, box_plot, or data_table.
- For graphing relationships, use coordinate_plane (plotting points) or function_graph (typing equations).
- For ordering/scales, use number_line.
"""
        elif any(kw in subject_lower for kw in ['social studies', 'history', 'civics', 'government', 'economics', 'world history', 'us history', 'american history']):
            subject_question_examples = """
SUBJECT-SPECIFIC QUESTION EXAMPLES (Social Studies/History — follow these patterns):

Primary source MC (MUST embed the source text):
{"question": "Read the following excerpt from the Declaration of Independence (1776):\\n\\n'We hold these truths to be self-evident, that all men are created equal, that they are endowed by their Creator with certain unalienable Rights, that among these are Life, Liberty and the pursuit of Happiness. — That to secure these rights, Governments are instituted among Men, deriving their just powers from the consent of the governed.'\\n\\nWhich Enlightenment idea MOST influenced the founders?", "options": ["A) Divine right of kings", "B) Social contract theory", "C) Mercantilism", "D) Manifest destiny"], "answer": "B", "dok": 2, "points": 1}

Cause-and-effect MC (be specific, not vague):
{"question": "Which event was a DIRECT cause of the United States entering World War I in 1917?", "options": ["A) The assassination of Archduke Franz Ferdinand", "B) Germany's unrestricted submarine warfare against American ships", "C) The Treaty of Versailles", "D) The formation of the League of Nations"], "answer": "B", "dok": 2, "points": 1}

Document-based extended response:
{"question": "Read the following quote from Lincoln's Gettysburg Address (1863):\\n\\n'Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal. Now we are engaged in a great civil war, testing whether that nation, or any nation so conceived and so dedicated, can long endure.'\\n\\nExplain how Lincoln connects the founding ideals to the purpose of the Civil War. Identify at least one founding ideal and explain why Lincoln believed the war was necessary to preserve it.", "answer": "Strong response identifies equality/liberty as founding ideals, explains Lincoln frames the war as a test of democratic self-government, connects 'all men are created equal' to the struggle over slavery.", "dok": 3, "points": 4}

Amendment matching:
{"question": "Match each amendment to the right it protects.", "terms": ["1st Amendment", "2nd Amendment", "4th Amendment", "5th Amendment"], "definitions": ["Right to bear arms", "Freedom of speech, religion, and press", "Protection against self-incrimination", "Protection against unreasonable searches"], "dok": 1, "points": 2}

CRITICAL: Primary source and document-based questions MUST embed the full source text in the question field. Never reference a document that isn't provided inline.
"""
        elif any(kw in subject_lower for kw in ['geography', 'world geography']):
            subject_question_examples = """
SUBJECT-SPECIFIC QUESTION EXAMPLES (Geography — follow these patterns):

Location/coordinates question:
{"question": "What is the capital city located nearest to the coordinates 30.4°N, 84.3°W?", "answer": "Tallahassee, Florida", "dok": 1, "points": 1}

Region comparison data table:
{"question": "Complete the table comparing physical features of Florida's geographic regions.", "question_type": "data_table", "column_headers": ["Region", "Major Landform", "Elevation Range", "Key Water Feature"], "row_labels": ["Northwest", "Central", "Southeast"], "expected_data": [["Northwest", "Rolling hills", "50-100 m", "Apalachicola River"], ["Central", "Lake region", "20-50 m", "Lake Okeechobee"], ["Southeast", "Coastal ridge", "0-5 m", "Biscayne Bay"]], "answer": "Students identify correct landforms, elevations, and water features", "dok": 2, "points": 3}

Map analysis MC:
{"question": "A geographer is studying population density along Florida's coast. Which factor BEST explains why population density is higher on the southeastern coast than the northwestern coast?", "options": ["A) The southeastern coast has more rainfall", "B) The southeastern coast has warmer average winter temperatures and established tourism infrastructure", "C) The northwestern coast has more hurricanes", "D) The southeastern coast was settled first by European colonists"], "answer": "B", "dok": 3, "points": 1}

CRITICAL: Include real geographic data and coordinates. Use the portal's interactive coordinate_plane or data_table components rather than asking students to draw maps.
"""
        # For math or unrecognized subjects, no extra examples needed (math already has them in question_type_instructions)

        input_standard_codes = [s.get('code', '') for s in standards if s.get('code')]
        subject_boundary = _build_subject_boundary_prompt(
            config.get('subject', ''), config.get('grade', ''), input_standard_codes)

        prompt = f"""You are an expert assessment developer creating a standards-aligned {assessment_type} for grade {config.get('grade', '8')} {config.get('subject', 'students')}.
{subject_boundary}
{dok_descriptions}
{source_content}
STANDARDS TO ASSESS:
{''.join(standards_context)}

ASSESSMENT REQUIREMENTS:
- Title: {title}
- Type: {assessment_type.upper()}
- Total Questions: {total_questions}
- Target Total Points: {total_points}

QUESTION TYPE DISTRIBUTION (with point values per question):
{chr(10).join(f'- {qtype.replace("_", " ").title()}: {count} questions @ {points_per_type.get(qtype, 1)} points each' for qtype, count in question_types.items() if count > 0)}

DOK LEVEL DISTRIBUTION:
- DOK 1 (Recall): {dok_distribution.get('1', 0)} questions
- DOK 2 (Skills/Concepts): {dok_distribution.get('2', 0)} questions
- DOK 3 (Strategic Thinking): {dok_distribution.get('3', 0)} questions
- DOK 4 (Extended Thinking): {dok_distribution.get('4', 0)} questions

{question_type_instructions}
{subject_question_examples}
CRITICAL REQUIREMENTS:
1. EVERY question MUST include: "dok" (1-4), "standard" (code), "points", and appropriate answer format
2. STRICTLY use the point values specified above for each question type - this is not optional
3. Questions must DIRECTLY assess the benchmarks provided - not tangentially related content
4. DOK levels must match the cognitive demand - DOK 1 = recall, DOK 3 = analysis with evidence
5. Multiple choice distractors should be plausible but clearly incorrect
6. Include varied question stems (What, How, Why, Analyze, Compare, Evaluate)
7. Extended response questions need detailed rubrics with point breakdowns
8. All questions must be answerable based on the standards content
9. Use grade-appropriate vocabulary and complexity
10. The total_points field MUST equal exactly {total_points}
11. The portal has no drawing canvas. For questions that require hand-drawn work (diagrams, constructions, graphs), tell the student to "show your work on paper and upload a photo" using the image upload option. For most math/geometry, prefer using the interactive visual components (geometry renderer, coordinate plane, number line, protractor) instead of asking students to draw. Only use image upload when no interactive component fits.
12. NEVER generate project, activity, or tool-based prompts. Students complete this assessment entirely within the online portal. Do NOT ask students to use external tools (Canva, Google Slides, PowerPoint, Desmos, GeoGebra, etc.), create physical products (posters, infographics, models, presentations, brochures, dioramas), collaborate with classmates, or perform tasks that cannot be answered with text, numbers, or the portal's interactive components. Every question must be directly answerable on screen.
13. For math/computation questions: SELF-CHECK that all given numeric values are consistent. If a problem states theorem values (e.g., tangent squared = external times whole), verify the numbers satisfy the equation BEFORE including the question. Never give more numeric values than needed to solve the problem (over-determined systems confuse students).
14. Word problems must clearly map to a single geometric/algebraic setup. Avoid mixing 2D circle theorems with 3D physical scenarios (towers, cables) unless the mapping is explicit and unambiguous.
15. Every question must be solvable with ONLY the given information — no hidden assumptions or missing data required.
16. For ELA/reading questions: If a question asks students to analyze, cite, or refer to a passage/text/excerpt, the FULL passage MUST be included in the "question" field. NEVER say "according to the passage" or "refer to the text" without embedding the actual passage text before the question. Quotations longer than one sentence must include attribution (author or source).
17. For science questions: Use ONE consistent unit system (metric or imperial) per question — do NOT mix systems unless the question is explicitly about unit conversion. All values must be physically plausible (no negative mass, no temperatures below absolute zero, no pH outside 0-14, no percentages above 100% for concentrations/efficiency). If referencing a figure, diagram, or lab setup, include the data in structured fields — never reference a visual that doesn't exist.

SECTION CATEGORIES TO INCLUDE:
{_build_section_categories_prompt(section_categories, config.get('subject', ''), question_type_counts=config.get('questionTypeCounts'))}

{f"TEACHER'S ADDITIONAL REQUIREMENTS (MUST FOLLOW — every question must reflect these):" + chr(10) + config.get('requirements', '').strip() + chr(10) if config.get('requirements', '').strip() else ''}
{f"TEACHER'S GLOBAL INSTRUCTIONS (MUST FOLLOW):" + chr(10) + global_ai_notes + chr(10) if global_ai_notes else ''}
{_build_period_differentiation_block(target_period)}
Generate a complete assessment in this JSON format:
{{
    "title": "{title}",
    "type": "{assessment_type}",
    "grade": "{config.get('grade', '8')}",
    "subject": "{config.get('subject', 'Subject')}",
    "standards_assessed": ["SS.8.A.1.1", "SS.8.A.1.2"],
    "total_points": {total_points},
    "time_estimate": "45 minutes",
    "instructions": "Clear student instructions...",
    "sections": [
        {{
            "name": "Part A: Multiple Choice",
            "instructions": "Select the best answer for each question.",
            "questions": [...]
        }},
        {{
            "name": "Part B: Short Answer",
            "instructions": "Answer each question in 2-3 complete sentences.",
            "questions": [...]
        }}
    ],
    "answer_key": {{
        "1": {{"answer": "B", "explanation": "..."}},
        "2": {{"answer": "...", "key_points": ["point1", "point2"]}}
    }},
    "dok_summary": {{
        "dok_1_count": 3,
        "dok_2_count": 6,
        "dok_3_count": 4,
        "dok_4_count": 2
    }},
    "standards_alignment": {{
        "SS.8.A.1.1": [1, 3, 5, 8],
        "SS.8.A.1.2": [2, 4, 6, 7, 9, 10]
    }}
}}"""

        completion = adapter.chat(LLMRequest(
            model="gpt-4o",
            system_prompt="You are an expert assessment developer. Create rigorous, standards-aligned assessments. Return valid JSON only.",
            messages=[Message(role="user", content=[TextPart(text=prompt)])],
            response_format=ResponseFormat(type="json_object"),
            temperature=0.7,
            metadata={"feature_label": "generate_assessment"},
        ))

        content = completion.content_parts[0].text if completion.content_parts else "{}"
        assessment = json.loads(content)
        _ctx_uid, _ctx_client = _get_openai_context()
        assessment, _ = _post_process_assignment(
            assessment, target_total_points=total_points,
            subject=config.get('subject'), grade=config.get('grade'),
            valid_standard_codes=input_standard_codes,
            user_id=_ctx_uid, client=_ctx_client)

        # Collect any quality warnings attached to questions
        quality_warnings = []
        for sIdx, section in enumerate(assessment.get('sections', [])):
            for qIdx, q in enumerate(section.get('questions', [])):
                if q.get('warning'):
                    quality_warnings.append({
                        "section_index": sIdx,
                        "question_index": qIdx,
                        "issue": q['warning'],
                        "severity": q.get('warning_severity', 'warning'),
                    })

        # Add metadata for portal grading context
        assessment['generated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        assessment['teacher'] = config.get('teacher_name', '')
        assessment['grade_level'] = config.get('grade', '8')
        assessment['subject'] = config.get('subject', 'General')

        usage = _extract_usage(completion, "gpt-4o")
        _record_planner_cost(usage)
        result = {"assessment": assessment, "method": "AI", "usage": usage}
        if quality_warnings:
            result["warnings"] = quality_warnings
        return jsonify(result)

    except Exception as e:
        error_msg = str(e)
        _logger.exception("Assessment Generation Error")
        return jsonify({"error": f"Failed to generate assessment: {error_msg}"}), 500


@planner_bp.route('/api/export-assessment', methods=['POST'])
@require_teacher
@handle_route_errors
def export_assessment():
    """Export assessment to Word document with Graider table extraction tags."""
    data = request.json
    assessment = data.get('assessment', {})
    include_answer_key = data.get('includeAnswerKey', False)

    if not assessment:
        return jsonify({"error": "No assessment data provided"})

    try:
        from docx import Document
        from docx.shared import Inches, Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from backend.services.worksheet_generator import _add_graider_table, _add_graider_marker
        import tempfile
        import base64

        doc = Document()

        # Graider table style dict (blue header, white text)
        graider_style = {
            "table_header_bg": "#4472C4",
            "table_header_text_color": "#FFFFFF",
        }

        # Title
        title = doc.add_heading(assessment.get('title', 'Assessment'), 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Header info
        header_info = doc.add_paragraph()
        header_info.add_run(f"Subject: {assessment.get('subject', '')}").bold = True
        header_info.add_run(f"    Grade: {assessment.get('grade', '')}")
        header_info.add_run(f"    Time: {assessment.get('time_estimate', '')}")
        header_info.add_run(f"    Total Points: {assessment.get('total_points', '')}")

        # Student info line
        doc.add_paragraph("Name: _________________________    Date: _____________    Period: _____")

        # Instructions
        if assessment.get('instructions'):
            inst = doc.add_paragraph()
            inst.add_run("Instructions: ").bold = True
            inst.add_run(assessment.get('instructions'))

        doc.add_paragraph()  # Space

        # Sections
        for section in assessment.get('sections', []):
            # Section header
            sec_head = doc.add_heading(section.get('name', 'Section'), level=1)

            if section.get('instructions'):
                sec_inst = doc.add_paragraph()
                sec_inst.add_run(section.get('instructions')).italic = True

            # Questions
            for q in section.get('questions', []):
                q_num = q.get('number', '')
                q_text = q.get('question', '')
                q_points = q.get('points', 1)
                q_type = q.get('type', section.get('type', ''))

                if q.get('options'):
                    # MC/TF: render question + options as paragraphs, then small Graider table
                    q_para = doc.add_paragraph()
                    q_para.add_run(f"{q_num}. ").bold = True
                    q_para.add_run(f"{q_text} ")
                    q_para.add_run(f"({q_points} pt{'s' if q_points > 1 else ''})").italic = True

                    for opt in q.get('options', []):
                        opt_para = doc.add_paragraph(f"    {opt}")
                        opt_para.paragraph_format.space_before = Pt(2)
                        opt_para.paragraph_format.space_after = Pt(2)

                    _add_graider_table(doc, f"Answer for Question {q_num}",
                                       f"GRAIDER:QUESTION:{q_num}", q_points,
                                       graider_style, 720)  # 0.5 inch

                elif q.get('terms') and q.get('definitions'):
                    # Matching: two-column table with draw-a-line instruction
                    q_para = doc.add_paragraph()
                    q_para.add_run(f"{q_num}. ").bold = True
                    q_para.add_run(f"{q_text} ")
                    q_para.add_run(f"({q_points} pt{'s' if q_points > 1 else ''})").italic = True

                    inst_para = doc.add_paragraph()
                    inst_para.add_run("Directions: ").bold = True
                    inst_para.add_run("Draw a line from each term to its matching definition.")
                    inst_para.italic = True

                    terms = q.get('terms', [])
                    definitions = q.get('definitions', [])
                    max_len = max(len(terms), len(definitions))

                    tbl = doc.add_table(rows=max_len + 1, cols=3)
                    tbl.style = 'Table Grid'

                    # Header row
                    tbl.rows[0].cells[0].text = "Term"
                    tbl.rows[0].cells[1].text = ""
                    tbl.rows[0].cells[2].text = "Definition"
                    for cell in tbl.rows[0].cells:
                        for paragraph in cell.paragraphs:
                            for run_obj in paragraph.runs:
                                run_obj.bold = True

                    # Set narrow middle column for drawing lines
                    for row in tbl.rows:
                        row.cells[1].width = Inches(0.5)

                    for i in range(max_len):
                        if i < len(terms):
                            tbl.rows[i + 1].cells[0].text = f"{i + 1}. {terms[i]}"
                        if i < len(definitions):
                            letter_char = chr(65 + i)
                            tbl.rows[i + 1].cells[2].text = f"{letter_char}. {definitions[i]}"

                    doc.add_paragraph()  # Space after table

                elif q_type == 'extended_response':
                    # Extended response: Graider table with 3" height
                    _add_graider_table(doc, f"{q_num}. {q_text} ({q_points} pts)",
                                       f"GRAIDER:QUESTION:{q_num}", q_points,
                                       graider_style, 4320)  # 3 inches

                else:
                    # Short answer / default: Graider table with 1.5" height
                    _add_graider_table(doc, f"{q_num}. {q_text} ({q_points} pts)",
                                       f"GRAIDER:QUESTION:{q_num}", q_points,
                                       graider_style, 2160)  # 1.5 inches

        # Add Graider marker before answer key
        _add_graider_marker(doc)

        # Answer Key (separate page) — no Graider tables
        if include_answer_key:
            doc.add_page_break()
            doc.add_heading("Answer Key", 0)

            answer_key = assessment.get('answer_key', {})
            for q_num, answer_data in sorted(answer_key.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
                ans_para = doc.add_paragraph()
                ans_para.add_run(f"{q_num}. ").bold = True

                if isinstance(answer_data, dict):
                    ans_para.add_run(str(answer_data.get('answer', '')))
                    if answer_data.get('explanation'):
                        ans_para.add_run(f" - {answer_data.get('explanation')}")
                else:
                    ans_para.add_run(str(answer_data))

        # Auto-save grading config for structured extraction
        _save_grading_config_for_export(assessment)

        # Save to temp file and encode
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            doc.save(tmp.name)
            tmp.seek(0)
            with open(tmp.name, 'rb') as f:
                doc_bytes = f.read()
            os.unlink(tmp.name)

        doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')

        # Generate filename
        safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
        filename = f"{safe_title.replace(' ', '_')}.docx"

        return jsonify({
            "document": doc_base64,
            "filename": filename,
            "format": "docx"
        })

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


# =============================================================================
# ASSESSMENT PLATFORM TEMPLATES
# =============================================================================

TEMPLATES_DIR = os.path.expanduser("~/.graider_data/assessment_templates")


@planner_bp.route('/api/upload-assessment-template', methods=['POST'])
@require_teacher
@handle_route_errors
def upload_assessment_template():
    """Upload a sample template from an assessment platform (e.g., Wayground, Canvas)."""
    import uuid

    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    platform = request.form.get('platform', 'custom')
    name = request.form.get('name', 'Untitled Template')

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ''
    if ext not in ALLOWED_DOC_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 400

    # Create templates directory if it doesn't exist
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

    # Generate unique ID
    template_id = str(uuid.uuid4())[:8]

    # Save the file
    filename = f"{template_id}_{platform}{ext}"
    filepath = os.path.join(TEMPLATES_DIR, secure_filename(filename))
    file.save(filepath)

    # Parse the template to understand its structure
    template_structure = parse_template_structure(filepath, ext)

    # Save metadata
    metadata = {
        "id": template_id,
        "name": name,
        "platform": platform,
        "filename": filename,
        "filepath": filepath,
        "original_filename": file.filename,
        "extension": ext,
        "structure": template_structure,
        "created_at": time.strftime('%Y-%m-%d %H:%M:%S')
    }

    metadata_path = os.path.join(TEMPLATES_DIR, f"{template_id}.meta.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return jsonify({
        "success": True,
        "template": metadata,
        "message": f"Template '{name}' uploaded successfully"
    })


@planner_bp.route('/api/assessment-templates', methods=['GET'])
@require_teacher
@handle_route_errors
def get_assessment_templates():
    """Get all uploaded assessment templates."""
    templates = []

    if not os.path.exists(TEMPLATES_DIR):
        return jsonify({"templates": []})

    for f in os.listdir(TEMPLATES_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(TEMPLATES_DIR, f), 'r') as mf:
                    metadata = json.load(mf)
                    templates.append(metadata)
            except Exception:
                pass

    # Sort by creation date (newest first)
    templates.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    return jsonify({"templates": templates})


@planner_bp.route('/api/assessment-template/<template_id>', methods=['DELETE'])
@require_teacher
@handle_route_errors
def delete_assessment_template(template_id):
    """Delete an assessment template."""
    if not os.path.exists(TEMPLATES_DIR):
        return jsonify({"error": "Template not found"}), 404

    # Find and delete metadata and file
    meta_path = os.path.join(TEMPLATES_DIR, f"{template_id}.meta.json")

    if not os.path.exists(meta_path):
        return jsonify({"error": "Template not found"}), 404

    try:
        with open(meta_path, 'r') as f:
            metadata = json.load(f)

        # Delete the template file
        if metadata.get('filepath') and os.path.exists(metadata['filepath']):
            os.remove(metadata['filepath'])

        # Delete metadata
        os.remove(meta_path)

        return jsonify({"success": True, "message": "Template deleted"})

    except Exception as e:
        _logger.exception("Failed to delete template")
        return jsonify({"error": "An internal error occurred"}), 500


@planner_bp.route('/api/export-assessment-platform', methods=['POST'])
@require_teacher
@handle_route_errors
def export_assessment_for_platform():
    """Export assessment in a specific platform's format."""
    data = request.json
    assessment = data.get('assessment', {})
    platform = data.get('platform', 'csv')
    template_id = data.get('templateId')

    if not assessment:
        return jsonify({"error": "No assessment data provided"}), 400

    try:
        # Get template structure if provided
        template_structure = None
        if template_id:
            meta_path = os.path.join(TEMPLATES_DIR, f"{template_id}.meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    template_meta = json.load(f)
                    template_structure = template_meta.get('structure', {})

        result = build_platform_export(assessment, platform, template_structure)
        if result is None:
            return jsonify({"error": f"Unknown platform: {platform}"}), 400
        return jsonify(result)

    except Exception as e:
        _logger.exception("Platform export error")
        return jsonify({"error": "An internal error occurred"}), 500


@planner_bp.route('/api/grade-assessment-answers', methods=['POST'])
@require_teacher
@handle_route_errors
def grade_assessment_answers():
    """
    Grade student answers against the assessment using AI for open-ended questions.
    Returns detailed feedback for each question.
    """
    try:
        data = request.json
        assessment = data.get('assessment', {})
        answers = data.get('answers', {})

        if not assessment or not answers:
            return jsonify({"error": "Missing assessment or answers"}), 400

        return jsonify(grade_assessment_answers_logic(assessment, answers))

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@planner_bp.route('/api/regenerate-questions', methods=['POST'])
@require_teacher
@handle_route_errors
def regenerate_questions():
    """Regenerate specific questions in an assessment/assignment using AI.

    Expects:
      questions_to_replace: [{section_index, question_index, question_type, points, dok, standard}, ...]
      existing_questions: [str, ...] — question texts to avoid duplicating
      config: {grade, subject, globalAINotes}
    Returns:
      replacements: [{section_index, question_index, question: {...}}, ...]
      usage: cost/token info
    """
    data = request.json
    questions_to_replace = data.get('questions_to_replace', [])
    existing_questions = data.get('existing_questions', [])
    config = data.get('config', {})

    if not questions_to_replace:
        return jsonify({"error": "No questions specified for regeneration"}), 400

    _subject = config.get('subject', '').strip()
    _grade = config.get('grade', config.get('grade_level', '')).strip()
    if not _subject or not _grade:
        from flask import current_app
        current_app.logger.warning(
            f"Regenerate requested without subject/grade: subject={_subject!r}, grade={_grade!r}")

    try:
        from backend.api_keys import get_api_key as _gak
        from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart
        adapter = OpenAIAdapter(api_key=_gak('openai', getattr(g, 'user_id', 'local-dev')))

        grade = config.get('grade', '')
        subject = config.get('subject', '')
        global_notes = config.get('globalAINotes', '')

        # Build replacement specs
        specs = []
        for i, q in enumerate(questions_to_replace):
            spec = f"{i + 1}. Type: {q.get('question_type', 'short_answer')}"
            if q.get('points'):
                spec += f", Points: {q['points']}"
            if q.get('dok'):
                spec += f", DOK level: {q['dok']}"
            if q.get('standard'):
                spec += f", Standard: {q['standard']}"
            specs.append(spec)

        existing_list = "\n".join(f"- {q}" for q in existing_questions[:50]) if existing_questions else "None"

        regen_standard_codes = list(set(
            q.get('standard', '') for q in questions_to_replace if q.get('standard')
        ))
        subject_boundary = _build_subject_boundary_prompt(subject, grade, regen_standard_codes)

        prompt = f"""Generate {len(questions_to_replace)} replacement question(s) for a grade {grade} {subject} assessment.
{subject_boundary}
Each replacement must match the specified type, DOK level, and point value exactly.
Cognitive rigor (DOK) is fixed by the specifications above; teacher instructions modify vocabulary and scaffolding tone only — they MUST NOT change DOK.
DO NOT duplicate any of these existing questions:
{existing_list}

{f'Teacher instructions: {global_notes}' if global_notes else ''}
{f"Teacher's additional requirements (MUST reflect in every question): {config.get('requirements', '').strip()}" if config.get('requirements', '').strip() else ''}

Replacement specifications:
{chr(10).join(specs)}

Return a JSON object with a "questions" array. Each element must include:
- "question": the question text
- "answer": the correct answer
- "points": point value
- "question_type": exact type as specified
- "dok": DOK level as specified
- "number": sequential number starting from 1

For multiple_choice questions, include an "options" array of 4 strings (A) through D) format.
For true_false questions, answer must be "True" or "False".
For matching questions, include "terms" and "definitions" arrays.
For math questions, include step-by-step solution in the answer.

Make questions grade-appropriate, clear, and assessable by AI grading systems."""

        completion = adapter.chat(LLMRequest(
            model="gpt-4o",
            system_prompt="You are an expert assessment developer. Generate high-quality assessment questions that are clear, unambiguous, and appropriate for AI-based grading. Always return valid JSON.",
            messages=[Message(role="user", content=[TextPart(text=prompt)])],
            response_format=ResponseFormat(type="json_object"),
            temperature=0.8,
            metadata={"feature_label": "regenerate_questions"},
        ))

        content = completion.content_parts[0].text if completion.content_parts else "{}"
        result = json.loads(content)
        new_questions = result.get('questions', [])

        # Post-process each replacement through the standard pipeline
        replacements = []
        for i, q_spec in enumerate(questions_to_replace):
            if i < len(new_questions):
                new_q = new_questions[i]
                # Preserve DOK and standard from original spec
                new_q['dok'] = q_spec.get('dok', new_q.get('dok', 1))
                new_q['standard'] = q_spec.get('standard', new_q.get('standard', ''))
                # Run through classification and hydration pipeline
                _classify_question_type(new_q)
                _hydrate_question(new_q)
                _validate_question(new_q)
                replacements.append({
                    "section_index": q_spec['section_index'],
                    "question_index": q_spec['question_index'],
                    "question": new_q,
                })

        usage = _extract_usage(completion, "gpt-4o")
        _record_planner_cost(usage)

        return jsonify({"replacements": replacements, "usage": usage})

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@planner_bp.route('/api/planner/costs', methods=['GET'])
@require_teacher
@handle_route_errors
def get_planner_costs():
    """Return planner API cost summary."""
    try:
        with open(PLANNER_COSTS_FILE, 'r') as f:
            return jsonify(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"total": {"input_tokens": 0, "output_tokens": 0, "total_cost": 0, "api_calls": 0}, "daily": {}})


@planner_bp.route('/api/adjust-reading-level', methods=['POST'])
@require_teacher
@handle_route_errors
def adjust_reading_level():
    """Rewrite text at a target reading level while preserving key terms."""
    from backend.api_keys import get_api_key as _gak
    teacher_id = getattr(g, 'user_id', 'local-dev')
    api_key = _gak('openai', teacher_id)

    if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
        return jsonify({"error": "Missing or placeholder OpenAI API Key"})

    data = request.json or {}
    text = data.get('text', '').strip()
    target_level = data.get('target_level', '6')
    subject = data.get('subject', '')
    preserve_terms = data.get('preserve_terms', [])

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        return jsonify(adjust_reading_level_content(
            text=text, target_level=target_level, subject=subject,
            preserve_terms=preserve_terms, api_key=api_key,
        ))
    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@planner_bp.route('/api/extract-text', methods=['POST'])
@require_teacher
@handle_route_errors
def extract_text_from_file():
    """Extract plain text from uploaded documents (docx, pdf, txt) or images (png, jpg, etc.)."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    filename = file.filename.lower() if file.filename else ''
    ext = os.path.splitext(filename)[1].lower() if filename else ''
    if ext not in ALLOWED_DOC_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 400

    file_data = file.read()

    # Images need an OpenAI key (vision). Resolve it route-side (Flask g) and own
    # the missing-key 400 here; non-image types never touch the key, preserving
    # the original no-extra-key-lookup behavior.
    api_key = None
    if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
        from backend.api_keys import get_api_key as _gak
        teacher_id = getattr(g, 'user_id', 'local-dev')
        api_key = _gak('openai', teacher_id)
        if not api_key:
            return jsonify({"error": "OpenAI API key required for image text extraction"}), 400

    try:
        text = extract_text_from_upload(file_data=file_data, filename=filename, api_key=api_key)
        return jsonify({"text": text})
    except TextExtractionError as te:
        return jsonify({"error": str(te)}), 400
    except Exception:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


# ══════════════════════════════════════════════════════════════
# STUDY GUIDE GENERATION
# ══════════════════════════════════════════════════════════════

@planner_bp.route('/api/generate-study-guide', methods=['POST'])
@require_teacher
@handle_route_errors
def generate_study_guide():
    """Generate a structured study guide from content using Gemini Flash."""
    data = request.get_json(silent=True) or {}

    content = data.get('content', '').strip()
    title = data.get('title', 'Study Guide')
    subject = data.get('subject', '')
    grade = data.get('grade', '')
    instructions = data.get('instructions', '')
    global_ai_notes = data.get('globalAINotes', '')
    lesson_plan = data.get('lessonPlan')

    if not content and not lesson_plan:
        return jsonify({"error": "Provide content or a lesson plan to generate a study guide."}), 400

    user_id = getattr(g, 'user_id', 'local-dev')

    try:
        study_guide = generate_study_guide_content(
            content=content, subject=subject, grade=grade,
            instructions=instructions, global_ai_notes=global_ai_notes,
            lesson_plan=lesson_plan, user_id=user_id,
        )
        return jsonify({
            "study_guide": study_guide,
            "title": study_guide.get("title", title),
        })

    except json.JSONDecodeError as e:
        _logger.error("Study guide JSON parse failed: %s", e)
        return jsonify({"error": "Failed to parse study guide. Please try again."}), 500
    except Exception as e:
        _logger.exception("Study guide generation failed")
        return jsonify({"error": f"Generation failed: {str(e)[:200]}"}), 500


# ══════════════════════════════════════════════════════════════
# STUDY GUIDE EXPORT
# ══════════════════════════════════════════════════════════════

# Wave 6 Slice 1: study-aid render helpers extracted to
# backend/services/planner_export.py. Re-imported here so the export route
# bodies and tests that patch _get_export_dir on this module keep working.
from backend.services.planner_export import (  # noqa: F401  (re-export shim)
    _export_study_guide_docx,
    _export_study_guide_pdf,
    _export_flashcards_pdf,
    _export_flashcards_docx,
)


@planner_bp.route('/api/export-study-guide', methods=['POST'])
@require_teacher
@handle_route_errors
def export_study_guide():
    """Export a study guide to DOCX or PDF."""
    data = request.get_json(silent=True) or {}
    study_guide = data.get('study_guide')
    fmt = data.get('format', 'docx').lower()

    if not study_guide:
        return jsonify({"error": "No study guide data provided."}), 400

    title = study_guide.get("title", "Study Guide")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:80]
    export_dir = _get_export_dir()

    try:
        if fmt == 'pdf':
            filepath = os.path.join(export_dir, f"{safe_title}.pdf")
            _export_study_guide_pdf(study_guide, filepath)
            mimetype = 'application/pdf'
        else:
            filepath = os.path.join(export_dir, f"{safe_title}.docx")
            _export_study_guide_docx(study_guide, filepath)
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        return send_file(filepath, mimetype=mimetype, as_attachment=True,
                         download_name=os.path.basename(filepath))

    except Exception as e:
        _logger.exception("Study guide export failed")
        return jsonify({"error": f"Export failed: {str(e)[:200]}"}), 500


# ══════════════════════════════════════════════════════════════
# FLASHCARD GENERATION
# ══════════════════════════════════════════════════════════════

@planner_bp.route('/api/generate-flashcards', methods=['POST'])
@require_teacher
@handle_route_errors
def generate_flashcards():
    """Generate flashcards from content using Gemini Flash."""
    data = request.get_json(silent=True) or {}

    content = data.get('content', '').strip()
    title = data.get('title', 'Flashcards')
    subject = data.get('subject', '')
    grade = data.get('grade', '')
    instructions = data.get('instructions', '')
    global_ai_notes = data.get('globalAINotes', '')
    lesson_plan = data.get('lessonPlan')
    card_count = data.get('cardCount', 15)

    if not content and not lesson_plan:
        return jsonify({"error": "Provide content or a lesson plan to generate flashcards."}), 400

    user_id = getattr(g, 'user_id', 'local-dev')

    try:
        flashcards = generate_flashcards_content(
            content=content, subject=subject, grade=grade,
            instructions=instructions, global_ai_notes=global_ai_notes,
            lesson_plan=lesson_plan, card_count=card_count, user_id=user_id,
        )
        return jsonify({
            "flashcards": flashcards,
            "title": flashcards.get("title", title),
        })

    except json.JSONDecodeError as e:
        _logger.error("Flashcard JSON parse failed: %s", e)
        return jsonify({"error": "Failed to parse flashcards. Please try again."}), 500
    except Exception as e:
        _logger.exception("Flashcard generation failed")
        return jsonify({"error": "Generation failed: " + str(e)[:200]}), 500


@planner_bp.route('/api/export-flashcards', methods=['POST'])
@require_teacher
@handle_route_errors
def export_flashcards():
    """Export flashcards to PDF or DOCX."""
    data = request.get_json(silent=True) or {}
    flashcards = data.get('flashcards')
    fmt = data.get('format', 'pdf').lower()

    if not flashcards:
        return jsonify({"error": "No flashcard data provided."}), 400

    title = flashcards.get("title", "Flashcards")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:80]
    export_dir = _get_export_dir()

    try:
        if fmt == 'docx':
            filepath = os.path.join(export_dir, safe_title + ".docx")
            _export_flashcards_docx(flashcards, filepath)
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            filepath = os.path.join(export_dir, safe_title + ".pdf")
            _export_flashcards_pdf(flashcards, filepath)
            mimetype = 'application/pdf'

        return send_file(filepath, mimetype=mimetype, as_attachment=True,
                         download_name=os.path.basename(filepath))

    except Exception as e:
        _logger.exception("Flashcard export failed")
        return jsonify({"error": "Export failed: " + str(e)[:200]}), 500


# ══════════════════════════════════════════════════════════════
# SLIDE DECK GENERATION
# ══════════════════════════════════════════════════════════════

@planner_bp.route('/api/generate-slides', methods=['POST'])
@require_teacher
@handle_route_errors
def generate_slides():
    """Generate a slide deck from content using Gemini Flash."""
    data = request.get_json(silent=True) or {}

    content = data.get('content', '').strip()
    title = data.get('title', 'Slide Deck')
    subject = data.get('subject', '')
    grade = data.get('grade', '')
    instructions = data.get('instructions', '')
    global_ai_notes = data.get('globalAINotes', '')
    lesson_plan = data.get('lessonPlan')
    slide_count = min(data.get('slideCount', 10), 20)
    max_images = min(data.get('maxImages', 5), 10)
    generate_images = data.get('generateImages', True)
    deck_format = data.get('deckFormat', 'detailed')

    if not content and not lesson_plan:
        return jsonify({"error": "Provide content or a lesson plan to generate slides."}), 400

    user_id = getattr(g, 'user_id', 'local-dev')

    try:
        return jsonify(generate_slides_payload(
            content=content, title=title, subject=subject, grade=grade,
            instructions=instructions, global_ai_notes=global_ai_notes,
            lesson_plan=lesson_plan, slide_count=slide_count, max_images=max_images,
            generate_images=generate_images, deck_format=deck_format, user_id=user_id,
        ))

    except json.JSONDecodeError as e:
        _logger.error("Slide content JSON parse failed: %s", e)
        return jsonify({"error": "Failed to parse slide content. Please try again."}), 500
    except Exception as e:
        _logger.exception("Slide generation failed")
        return jsonify({"error": "Generation failed: " + str(e)[:200]}), 500


@planner_bp.route('/api/export-slides', methods=['POST'])
@require_teacher
@handle_route_errors
def export_slides():
    """Export generated slides as PowerPoint (.pptx)."""
    data = request.get_json(silent=True) or {}
    slide_data = data.get('slides')

    if not slide_data or not slide_data.get('slides'):
        return jsonify({"error": "No slide data provided."}), 400

    title = slide_data.get("title", "Slide Deck")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:80]
    export_dir = _get_export_dir()

    try:
        import base64
        from backend.services.slide_generator import assemble_pptx

        # Decode image data from base64
        images = {}
        for k, v in slide_data.get("_image_data", {}).items():
            try:
                images[int(k)] = base64.b64decode(v)
            except Exception:
                pass

        filepath = os.path.join(export_dir, safe_title + ".pptx")
        assemble_pptx(
            slide_data["slides"], slide_data.get("theme", {}),
            title, images, filepath
        )

        return send_file(
            filepath,
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            as_attachment=True,
            download_name=safe_title + ".pptx",
        )

    except Exception as e:
        _logger.exception("Slide export failed")
        return jsonify({"error": "Export failed: " + str(e)[:200]}), 500
