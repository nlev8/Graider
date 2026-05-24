"""Lesson/assessment generation for the planner. Pure logic extracted from
planner_routes.py (no Flask). Wave 6 Slice 11.
"""
import json
import time

from backend.services.assignment_post_processing import (
    _build_section_categories_prompt,
    _build_subject_boundary_prompt,
    _extract_usage,
    _merge_usage,
    _post_process_assignment,
    _record_planner_cost,
)
from backend.services.planner_prompts import _build_period_differentiation_block
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


def generate_lesson_plan_content(*, selected_standards, config, selected_idea,
                                 generate_variations, reference_docs, api_key, openai_context):
    """Generate a lesson plan (or 3 variations). Returns {"plan"|"variations",
    "method": "AI", "usage"}; raises on any failure (the route catches and
    returns its mock fallback). `openai_context` is the (user_id, client) tuple
    the route resolves via _get_openai_context (used only for Assignment
    post-processing). Wave 6 Slice 11b - extracted from planner_routes.
    """
    from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart

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
                _ctx_uid, _ctx_client = openai_context
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
        return {"variations": variations, "method": "AI", "usage": total_usage}

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
        _ctx_uid, _ctx_client = openai_context
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
    return {"plan": plan, "method": "AI", "usage": usage}


def generate_assessment_content(*, standards, config, assessment_config,
                                content_only, content_sources, api_key, openai_context):
    """Generate a standards-aligned assessment. Returns {"assessment", "method":
    "AI", "usage"[, "warnings"]}; raises on any failure (the route maps it to a
    500 — NO mock fallback). Preserves the wart that the _post_process_assignment
    extra usage is discarded. Wave 6 Slice 11c - extracted from planner_routes.
    """
    from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart

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
    target_period = assessment_config.get('targetPeriod', '')
    section_categories = assessment_config.get('sectionCategories', {})

    # Get global AI notes from config
    global_ai_notes = config.get('globalAINotes', '')

    # Get content sources (lessons/assignments to base questions on)

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
    _ctx_uid, _ctx_client = openai_context
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
    return result
