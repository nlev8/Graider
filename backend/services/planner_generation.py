"""Lesson/assessment generation for the planner. Pure logic extracted from
planner_routes.py (no Flask). Wave 6 Slice 11.
"""
import json

from backend.services.assignment_post_processing import (
    _build_subject_boundary_prompt,
    _extract_usage,
    _merge_usage,
    _post_process_assignment,
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
