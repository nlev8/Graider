"""Lesson/assessment generation for the planner. Pure logic extracted from
planner_routes.py (no Flask). Wave 6 Slice 11.
"""
import json

from backend.services.assignment_post_processing import (
    _build_subject_boundary_prompt,
    _extract_usage,
    _record_planner_cost,
)
from backend.services.planner_standards import load_support_documents_for_planning


def brainstorm_lesson_ideas_content(*, selected_standards, config, api_key):
    """Generate lesson-plan ideas for the selected standards. Raises on any failure
    (missing key, AI error, bad JSON); the route catches and returns its mock
    fallback. Wave 6 Slice 11a - extracted from planner_routes.
    """
    from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart

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
    return {**ideas, "usage": usage}
