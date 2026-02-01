"""
Lesson Planner API routes for Graider.
Handles standards retrieval and lesson plan generation/export.
"""
import os
import json
import time
import subprocess
from flask import Blueprint, request, jsonify
from pathlib import Path

planner_bp = Blueprint('planner', __name__)

# Path to standards data
DATA_DIR = Path(__file__).parent.parent / 'data'
DOCUMENTS_DIR = os.path.expanduser("~/.graider_data/documents")


def load_support_documents_for_planning() -> str:
    """Load curriculum guides, standards, and other planning documents."""
    if not os.path.exists(DOCUMENTS_DIR):
        return ""

    docs_content = []
    total_chars = 0
    max_chars = 12000  # Increased limit for richer planning context

    # Document types useful for lesson planning (prioritized)
    planning_doc_types = ['curriculum', 'standards', 'pacing_guide', 'textbook', 'assessment', 'general']

    for f in os.listdir(DOCUMENTS_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(DOCUMENTS_DIR, f), 'r') as mf:
                    metadata = json.load(mf)

                doc_type = metadata.get('doc_type', 'general')
                filepath = metadata.get('filepath', '')
                description = metadata.get('description', '')

                # Include all planning-relevant document types
                if doc_type not in planning_doc_types:
                    continue

                if not os.path.exists(filepath):
                    continue

                content = ""
                if filepath.endswith('.txt') or filepath.endswith('.md'):
                    with open(filepath, 'r', encoding='utf-8') as df:
                        content = df.read()
                elif filepath.endswith('.docx'):
                    try:
                        from docx import Document
                        doc = Document(filepath)
                        content = '\n'.join([p.text for p in doc.paragraphs])
                    except:
                        continue
                elif filepath.endswith('.pdf'):
                    try:
                        import fitz
                        pdf = fitz.open(filepath)
                        content = '\n'.join([page.get_text() for page in pdf])
                        pdf.close()
                    except:
                        continue

                if content and total_chars + len(content) < max_chars:
                    doc_label = doc_type.upper()
                    if description:
                        doc_label += f" - {description}"
                    # Use more content per document (up to 4000 chars)
                    chunk = content[:4000]
                    docs_content.append(f"[{doc_label}]\n{chunk}")
                    total_chars += len(chunk)

            except Exception as e:
                continue

    if not docs_content:
        return ""

    return "\n\nREFERENCE DOCUMENTS:\n" + "\n\n".join(docs_content)


def load_standards(state, subject, grade=None):
    """Load standards from JSON file, optionally filtered by grade."""
    # Clean subject name for filename (replace spaces with underscores, slashes with hyphens)
    subject_clean = subject.lower().replace(' ', '_').replace('/', '-')
    filename = f"standards_{state.lower()}_{subject_clean}.json"
    filepath = DATA_DIR / filename

    if filepath.exists():
        with open(filepath, 'r') as f:
            data = json.load(f)
            standards = data.get('standards', [])
            file_grade = data.get('grade', '')  # e.g., "7", "8", "9-10", "6-8"

            # Filter by grade if provided
            if grade and standards:
                # First check if the file's grade field matches
                # Handle grade ranges like "6-8", "9-10", "9-12"
                if file_grade:
                    if '-' in str(file_grade):
                        # Grade range - check if requested grade is in range
                        parts = str(file_grade).split('-')
                        try:
                            min_grade = int(parts[0])
                            max_grade = int(parts[1])
                            requested = int(grade) if grade.isdigit() else 0
                            if min_grade <= requested <= max_grade:
                                # Grade is in range - return all standards
                                return standards
                        except (ValueError, IndexError):
                            pass
                    elif str(file_grade) == str(grade):
                        # Exact match - return all standards
                        return standards

                # Fall back to filtering by code pattern
                filtered = []
                for s in standards:
                    code = s.get('code', '')
                    # Extract grade from code patterns like MA.6.xxx, SC.7.xxx, SS.8.xxx
                    # Also handle K for kindergarten and high school (9-12)
                    parts = code.split('.')
                    if len(parts) >= 2:
                        code_grade = parts[1]
                        # Match grade (handle K, 1-12)
                        if code_grade == grade or code_grade == f"0{grade}":
                            filtered.append(s)
                        # For kindergarten
                        elif grade == 'K' and code_grade in ['K', '0', '00']:
                            filtered.append(s)
                        # For high school codes like "912" - match grades 9, 10, 11, 12
                        elif code_grade == '912' and grade in ['9', '10', '11', '12']:
                            filtered.append(s)
                return filtered  # Return empty if no matches for this grade
            return standards
    return []


@planner_bp.route('/api/get-standards', methods=['POST'])
def get_standards():
    """Get standards for a specific state, grade, and subject."""
    data = request.json
    state = data.get('state', 'FL')
    grade = data.get('grade', '7')
    subject = data.get('subject', 'Civics')

    # Try to load from JSON files first, filtered by grade
    standards = load_standards(state, subject, grade)

    if standards:
        return jsonify({"standards": standards, "grade": grade, "subject": subject})

    # Fallback to empty if no data file exists
    return jsonify({"standards": [], "grade": grade, "subject": subject})


@planner_bp.route('/api/get-lesson-templates', methods=['POST'])
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
        return jsonify({"error": str(e)})


@planner_bp.route('/api/brainstorm-lesson-ideas', methods=['POST'])
def brainstorm_lesson_ideas():
    """Generate multiple lesson plan ideas/concepts for selected standards."""
    data = request.json
    selected_standards = data.get('standards', [])
    config = data.get('config', {})

    if not selected_standards:
        return jsonify({"error": "No standards selected"})

    try:
        from openai import OpenAI
        from dotenv import load_dotenv

        app_dir = Path(__file__).parent.parent.parent
        load_dotenv(app_dir / '.env', override=True)
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        client = OpenAI(api_key=api_key)

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

        prompt = f"""You are an expert curriculum developer brainstorming lesson plan ideas for a {config.get('grade', '7')}th grade {config.get('subject', 'Social Studies')} class.
{support_docs}

Standards to Cover:
{', '.join(selected_standards)}
{tools_instruction}

Generate 6 creative and diverse lesson plan ideas that would effectively teach these standards. Each idea should represent a DIFFERENT teaching approach.

CRITICAL REQUIREMENTS:
1. ALL activities must be CONCRETE and ACTIONABLE - things a teacher can actually do tomorrow
2. NEVER invent fictional apps, websites, platforms, or games (no "Math Ninja", "Number Quest", etc.)
3. For technology activities, ONLY use tools from the AVAILABLE TECHNOLOGY TOOLS list above (if any)
4. Focus on activities using standard classroom materials: whiteboards, manipulatives, worksheets, discussions, group work
5. Be SPECIFIC about what students actually do - not vague descriptions
6. For Math: use real problem types, manipulatives (fraction bars, algebra tiles), or proven strategies (number talks, think-pair-share)
7. For Science: use actual lab materials or household items for experiments
8. Avoid buzzwords without substance - every activity must have clear, executable steps

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

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert curriculum developer. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        content = completion.choices[0].message.content
        ideas = json.loads(content)
        return jsonify(ideas)

    except Exception as e:
        error_msg = str(e)
        print(f"Brainstorm Error: {error_msg}")
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
def generate_lesson_plan():
    """Generate a lesson plan using AI."""
    data = request.json
    selected_standards = data.get('standards', [])
    config = data.get('config', {})
    selected_idea = data.get('selectedIdea')  # Optional: from brainstorming
    generate_variations = data.get('generateVariations', False)  # Generate multiple variations

    if not selected_standards:
        return jsonify({"error": "No standards selected"})

    try:
        from openai import OpenAI
        from dotenv import load_dotenv

        # Load .env from the app directory
        app_dir = Path(__file__).parent.parent.parent
        load_dotenv(app_dir / '.env', override=True)
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        client = OpenAI(api_key=api_key)

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

        prompt = f"""
You are an expert curriculum developer creating a COMPLETE, READY-TO-USE {content_type} for a {config.get('grade', '7')}th grade {config.get('subject', 'Civics')} class.
{support_docs}
{idea_guidance}
{tools_instruction}
{title_instruction}
Duration: {config.get('duration', 1)} day(s)
Class Period Length: {period_length} minutes

Standards to Cover:
{', '.join(selected_standards)}

Additional Requirements:
{config.get('requirements', 'None specified')}

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
{f'''
TEACHER'S ADDITIONAL INSTRUCTIONS (MUST FOLLOW):
{config.get('globalAINotes', '')}
''' if config.get('globalAINotes') else ''}
Make the content SPECIFIC and DETAILED with real examples and facts."""

        # If generating variations, create 3 different versions
        if generate_variations:
            variations = []
            approaches = [
                ("Activity-Based", "Focus on hands-on activities, station rotations, and interactive learning experiences."),
                ("Discussion & Analysis", "Focus on Socratic questioning, primary source analysis, and class discussions."),
                ("Project-Based", "Focus on student-created projects, research, and presentations.")
            ]

            for approach_name, approach_desc in approaches:
                variation_prompt = prompt + f"\n\nIMPORTANT: Use a {approach_name} approach. {approach_desc}"

                completion = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are an expert curriculum developer. Return valid JSON only."},
                        {"role": "user", "content": variation_prompt}
                    ],
                    response_format={"type": "json_object"}
                )

                content = completion.choices[0].message.content
                plan = json.loads(content)
                plan['approach'] = approach_name
                variations.append(plan)

            return jsonify({"variations": variations, "method": "AI"})

        # Single plan generation
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert curriculum developer. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        content = completion.choices[0].message.content
        plan = json.loads(content)
        return jsonify({"plan": plan, "method": "AI"})

    except Exception as e:
        error_msg = str(e)
        print(f"OpenAI API Error: {error_msg}. Falling back to Mock Mode.")

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
def generate_assignment_from_lesson():
    """Generate an assignment based on an existing lesson plan."""
    data = request.json
    lesson_plan = data.get('lessonPlan', {})
    config = data.get('config', {})
    assignment_type = data.get('assignmentType', 'worksheet')  # worksheet, quiz, project, homework

    if not lesson_plan:
        return jsonify({"error": "No lesson plan provided"})

    try:
        from openai import OpenAI
        from dotenv import load_dotenv

        app_dir = Path(__file__).parent.parent.parent
        load_dotenv(app_dir / '.env', override=True)
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        client = OpenAI(api_key=api_key)

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

        # Assignment type templates
        type_instructions = {
            'worksheet': "Create a practice worksheet with fill-in-the-blank, short answer, and matching questions.",
            'quiz': "Create a quiz with multiple choice, true/false, and short answer questions to assess understanding.",
            'project': "Create a creative project assignment with clear requirements, rubric, and deliverables.",
            'homework': "Create a homework assignment that reinforces the lesson content with practice problems or reading questions.",
            'essay': "Create an essay prompt with a clear thesis question, requirements, and grading criteria.",
            'lab': "Create a lab activity or investigation with hypothesis, procedure, data collection, and analysis questions."
        }

        type_instruction = type_instructions.get(assignment_type, type_instructions['worksheet'])

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

        prompt = f"""You are an expert teacher creating an assessment/assignment based on a lesson plan.
{tools_instruction}
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

Create a complete, ready-to-use assignment that:
1. Directly assesses the lesson objectives
2. Uses the vocabulary and key concepts from the lesson
3. Aligns with the essential questions
4. Is appropriate for grade {config.get('grade', '7')} students

CRITICAL REQUIREMENTS:
- For Math: Use REAL numbers and actual problems (e.g., "Solve: 3/4 + 1/2 = ?"), not placeholders
- All questions must be answerable based on the lesson content
- Include clear, specific answer keys
- Word problems should use realistic scenarios (shopping, cooking, sports) not fictional games or apps
- Avoid vague or overly complex language for the grade level

SPECIAL STEM QUESTION TYPES (use when appropriate):

1. MATH EQUATIONS (type: "math_equation"):
   - Student writes a mathematical expression/equation as their answer
   - System can check symbolic equivalence (2x+4 equals 4+2x)
   - Use for: solving equations, simplifying expressions, writing formulas
   - Include "answer" as the correct expression (e.g., "x = 5" or "3/4")

2. DATA TABLES (type: "data_table"):
   - Student fills in a table with numerical data
   - System grades with tolerance (±5% for measurements)
   - Use for: science labs, statistics, recording observations
   - Include "expected_data" with the correct values and "tolerance" (default 0.05)

3. COORDINATES (type: "coordinates"):
   - Student provides geographic coordinates (latitude, longitude)
   - System grades based on distance (within X km is correct)
   - Use for: geography, map skills, location identification
   - Include "answer" as {{"lat": 25.7617, "lng": -80.1918}} and "tolerance_km" (default 50)

VISUAL/GRAPHICAL QUESTION TYPES (include actual data for rendering):

4. BAR CHART (type: "bar_chart"):
   - Display a bar graph and ask interpretation questions
   - MUST include "chart_data" with labels and values
   - Example: {{"chart_data": {{"labels": ["Mon", "Tue", "Wed", "Thu", "Fri"], "values": [12, 19, 8, 15, 22], "title": "Daily Sales", "y_label": "Number Sold"}}}}

5. BOX PLOT (type: "box_plot"):
   - Student identifies min, Q1, median, Q3, max, range, IQR
   - MUST include "data" array with the dataset
   - Example: {{"data": [[45, 52, 58, 60, 65, 70, 72, 78, 85, 92]], "labels": ["Class Scores"]}}

6. NUMBER LINE (type: "number_line"):
   - Student plots points on a number line
   - Include "min_val", "max_val", and "points_to_plot"
   - Example: {{"min_val": -10, "max_val": 10, "points_to_plot": [-3, 0, 5]}}

7. COORDINATE PLANE (type: "coordinate_plane"):
   - Student plots points on an x-y grid (4 quadrants)
   - Include "min_val", "max_val", and "points_to_plot" as [x, y] pairs
   - Example: {{"min_val": -5, "max_val": 5, "points_to_plot": [[2, 3], [-1, 4], [0, -2]]}}

8. GEOMETRY (type: "geometry" or "triangle" or "rectangle"):
   - Student calculates area of shapes with given dimensions
   - Include "base", "height", and "question_type" (triangle or rectangle)
   - Example: {{"base": 6, "height": 4, "question_type": "triangle"}}

CRITICAL RULES FOR VISUAL QUESTIONS (MUST FOLLOW):

1. ONLY USE THESE VISUAL TYPES - no others exist in the system:
   - bar_chart (with chart_data)
   - box_plot (with data array)
   - number_line (with min_val, max_val, points_to_plot)
   - coordinate_plane (with points_to_plot as [x,y] pairs)
   - geometry/triangle/rectangle (with base and height)

2. NEVER mention or reference:
   - "See attached graph" - there are no attachments
   - "Look at the diagram below" without providing the data
   - Line graphs, pie charts, scatter plots, or histograms (not supported)
   - Any visual that doesn't have its data in the question object

3. EVERY visual question MUST include:
   - "question_type": one of the supported types above
   - The required data fields for that type
   - Example: {{"question_type": "bar_chart", "chart_data": {{"labels": [...], "values": [...], "title": "..."}}}}

4. If you want to ask about data interpretation without a visual:
   - Describe the data in words within the question text
   - Use "short_answer" type
   - Example: "A store sold 12 apples on Monday, 19 on Tuesday, and 8 on Wednesday. Which day had the most sales?"

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
                    "expected_data": [[1, 2], [3, 4]],  // for data_table type
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
- For MATH subjects: Include at least one "math_equation" section where students solve and write expressions
- For SCIENCE subjects: Include a "data_table" section for lab data, measurements, or observations
- For GEOGRAPHY subjects: Include a "coordinates" section for map/location questions
{f'''
TEACHER'S ADDITIONAL INSTRUCTIONS (MUST FOLLOW):
{config.get('globalAINotes', '')}
''' if config.get('globalAINotes') else ''}
Make the questions specific to the lesson content. Include a variety of question types appropriate for the assignment type."""

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert teacher. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        content = completion.choices[0].message.content
        assignment = json.loads(content)
        return jsonify({"assignment": assignment, "method": "AI"})

    except Exception as e:
        error_msg = str(e)
        print(f"Assignment Generation Error: {error_msg}")

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
def export_lesson_plan():
    """Export the lesson plan to a Word document."""
    data = request.json
    plan = data.get('plan', data)

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
        output_folder = os.path.expanduser("~/Downloads/Graider")
        os.makedirs(output_folder, exist_ok=True)
        filepath = os.path.join(output_folder, filename)
        doc.save(filepath)

        # Open the file
        subprocess.run(['open', filepath])

        return jsonify({"status": "success", "path": filepath})

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error exporting plan: {e}")
        return jsonify({"error": str(e)})


@planner_bp.route('/api/export-generated-assignment', methods=['POST'])
def export_generated_assignment():
    """Export a generated assignment to PDF format with visual elements."""
    data = request.json
    assignment = data.get('assignment', {})
    format_type = data.get('format', 'pdf')  # Default to PDF now
    include_answers = data.get('include_answers', False)

    title = assignment.get('title', 'Assignment')
    instructions = assignment.get('instructions', '')
    sections = assignment.get('sections', [])
    total_points = assignment.get('total_points', 100)
    time_estimate = assignment.get('time_estimate', '')

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.colors import black, gray, lightgrey, red, green
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Image,
            Table, TableStyle, PageBreak, KeepTogether
        )
        import io

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

        # Build the PDF
        safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
        suffix = "_ANSWER_KEY" if include_answers else "_Student"
        filename = f"{safe_title}{suffix}.pdf"
        output_folder = os.path.expanduser("~/Downloads/Graider/Assignments")
        os.makedirs(output_folder, exist_ok=True)
        filepath = os.path.join(output_folder, filename)

        doc = SimpleDocTemplate(
            filepath, pagesize=letter,
            topMargin=0.5*inch, bottomMargin=0.5*inch,
            leftMargin=0.75*inch, rightMargin=0.75*inch
        )

        story = []

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

        # Meta info
        if time_estimate or total_points:
            meta_text = []
            if time_estimate:
                meta_text.append(f"Time: {time_estimate}")
            if total_points:
                meta_text.append(f"Total Points: {total_points}")
            story.append(Paragraph("    ".join(meta_text), center_style))

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

            for q in questions:
                q_number = q.get('number', question_num)
                q_text = q.get('question', '')
                q_points = q.get('points', 0)
                q_options = q.get('options', [])
                q_answer = q.get('answer', '')
                q_type = q.get('question_type', section_type)
                q_visual = q.get('visual_type', None)  # number_line, coordinate_plane, etc.

                # Question text
                pts_text = f" ({q_points} pts)" if q_points else ""
                story.append(Paragraph(
                    f"<b>Question {q_number}:</b> {q_text}{pts_text}",
                    normal_style
                ))
                story.append(Spacer(1, 0.05*inch))

                # Multiple choice options
                if q_options:
                    for opt in q_options:
                        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;{opt}", normal_style))

                # Add visual elements based on question type
                if q_visual or q_type in ['number_line', 'coordinate_plane', 'graph', 'geometry']:
                    visual_image = _create_visual_for_question(q, include_answers)
                    if visual_image:
                        story.append(Spacer(1, 0.1*inch))
                        story.append(visual_image)
                        story.append(Spacer(1, 0.1*inch))

                # Answer section
                if include_answers:
                    # Show answer
                    if q_type == 'coordinates' and isinstance(q_answer, dict):
                        ans_text = f"ANSWER: Lat: {q_answer.get('lat', 0)}, Lng: {q_answer.get('lng', 0)}"
                    else:
                        ans_text = f"ANSWER: {q_answer}"
                    story.append(Paragraph(f"<b>{ans_text}</b>", answer_style))

                    if q_type == 'math_equation':
                        story.append(Paragraph("<i>(Equivalent forms accepted)</i>", normal_style))
                    elif q_type == 'coordinates':
                        tolerance_km = q.get('tolerance_km', 50)
                        story.append(Paragraph(f"<i>(Acceptable within {tolerance_km} km)</i>", normal_style))
                else:
                    # Answer space for students
                    if q_type == 'math_equation':
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
                        # Create empty table
                        headers = q.get('headers', ['Column 1', 'Column 2', 'Column 3'])
                        num_rows = q.get('num_rows', 5)
                        table_data = [headers] + [[''] * len(headers) for _ in range(num_rows)]
                        t = Table(table_data, colWidths=[1.5*inch] * len(headers))
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
                        story.append(Paragraph("<b>Answer:</b> _____", normal_style))
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
        subprocess.run(['open', filepath])

        return jsonify({"status": "success", "path": filepath})

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error exporting assignment: {e}")
        return jsonify({"error": str(e)})


def _create_visual_for_question(question: dict, show_answer: bool = False):
    """Create a visual element (graph, number line, etc.) for a question."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        from reportlab.lib.units import inch
        from reportlab.platypus import Image
        import io

        q_type = question.get('question_type', question.get('visual_type', ''))

        if q_type == 'number_line':
            # Create number line
            fig, ax = plt.subplots(figsize=(7, 1.5))
            min_val = question.get('min_val', -10)
            max_val = question.get('max_val', 10)

            ax.axhline(y=0, color='black', linewidth=2)
            ax.set_xlim(min_val - 0.5, max_val + 0.5)
            ax.set_ylim(-0.5, 0.5)

            # Tick marks
            for i in range(int(min_val), int(max_val) + 1):
                ax.plot([i, i], [-0.1, 0.1], 'k-', linewidth=1.5)
                ax.text(i, -0.25, str(i), ha='center', fontsize=10)

            # Arrows
            ax.annotate('', xy=(max_val + 0.3, 0), xytext=(max_val, 0),
                       arrowprops=dict(arrowstyle='->', color='black', lw=2))
            ax.annotate('', xy=(min_val - 0.3, 0), xytext=(min_val, 0),
                       arrowprops=dict(arrowstyle='->', color='black', lw=2))

            # Plot points if showing answer
            if show_answer and question.get('points_to_plot'):
                for pt in question['points_to_plot']:
                    ax.plot(pt, 0, 'ro', markersize=10)

            ax.axis('off')

        elif q_type == 'coordinate_plane':
            # Create coordinate plane
            fig, ax = plt.subplots(figsize=(5, 5))
            x_range = question.get('x_range', (-6, 6))
            y_range = question.get('y_range', (-6, 6))

            ax.axhline(y=0, color='black', linewidth=1.5)
            ax.axvline(x=0, color='black', linewidth=1.5)
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.set_xlim(x_range[0] - 0.5, x_range[1] + 0.5)
            ax.set_ylim(y_range[0] - 0.5, y_range[1] + 0.5)
            ax.set_xticks(range(x_range[0], x_range[1] + 1))
            ax.set_yticks(range(y_range[0], y_range[1] + 1))

            # Quadrant labels
            offset = (x_range[1] - x_range[0]) * 0.35
            ax.text(offset, offset, 'I', fontsize=14, color='gray', alpha=0.5)
            ax.text(-offset, offset, 'II', fontsize=14, color='gray', alpha=0.5)
            ax.text(-offset, -offset, 'III', fontsize=14, color='gray', alpha=0.5)
            ax.text(offset, -offset, 'IV', fontsize=14, color='gray', alpha=0.5)

            ax.set_xlabel('x')
            ax.set_ylabel('y')
            ax.set_aspect('equal')

            # Plot points if showing answer
            if show_answer and question.get('points_to_plot'):
                labels = question.get('point_labels', [])
                for i, pt in enumerate(question['points_to_plot']):
                    ax.plot(pt[0], pt[1], 'ro', markersize=10)
                    label = labels[i] if i < len(labels) else f"({pt[0]}, {pt[1]})"
                    ax.annotate(label, xy=pt, xytext=(5, 5), textcoords='offset points', fontsize=10)

        elif q_type == 'geometry' or q_type == 'triangle':
            # Create triangle
            fig, ax = plt.subplots(figsize=(4, 3.5))
            base = question.get('base', 6)
            height = question.get('height', 4)

            vertices = [(0, 0), (base, 0), (base/2, height)]
            triangle = plt.Polygon(vertices, fill=True, facecolor='lightblue',
                                  edgecolor='black', linewidth=2)
            ax.add_patch(triangle)
            ax.plot([base/2, base/2], [0, height], 'r--', linewidth=1.5)
            ax.text(base/2, -0.4, f'b = {base}', ha='center', fontsize=11)
            ax.text(base/2 + 0.3, height/2, f'h = {height}', ha='left', fontsize=11)
            ax.set_xlim(-1, base + 1)
            ax.set_ylim(-1, height + 1)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type == 'box_plot':
            # Create box plot
            fig, ax = plt.subplots(figsize=(7, 3))
            data = question.get('data', [[50, 60, 70, 75, 80, 85, 90]])
            labels = question.get('data_labels', [f'Set {i+1}' for i in range(len(data))])

            bp = ax.boxplot(data, patch_artist=True, labels=labels)
            colors = plt.cm.Pastel1(np.linspace(0, 1, len(data)))
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
            ax.set_ylabel('Value')
            ax.grid(True, axis='y', linestyle='--', alpha=0.5)

        elif q_type == 'bar_chart':
            # Create bar chart
            fig, ax = plt.subplots(figsize=(6, 4))
            categories = question.get('categories', ['A', 'B', 'C', 'D'])
            values = question.get('values', [0, 0, 0, 0]) if show_answer else [0] * len(question.get('categories', ['A', 'B', 'C', 'D']))

            ax.bar(categories, values, color='steelblue', edgecolor='black')
            ax.set_ylabel(question.get('y_label', 'Value'))
            ax.set_xlabel(question.get('x_label', 'Category'))
            ax.grid(True, axis='y', linestyle='--', alpha=0.5)

        else:
            return None

        # Convert to image
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        plt.close(fig)

        # Determine width based on type
        if q_type in ['coordinate_plane']:
            width = 3.5 * inch
        elif q_type in ['number_line', 'box_plot']:
            width = 5.5 * inch
        else:
            width = 4 * inch

        return Image(buf, width=width)

    except Exception as e:
        print(f"Error creating visual: {e}")
        return None


# =============================================================================
# ASSESSMENT GENERATION
# =============================================================================

@planner_bp.route('/api/generate-assessment', methods=['POST'])
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

    if not standards:
        return jsonify({"error": "No standards provided"})

    try:
        from openai import OpenAI
        from dotenv import load_dotenv

        app_dir = Path(__file__).parent.parent.parent
        load_dotenv(app_dir / '.env', override=True)
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        client = OpenAI(api_key=api_key)

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
            'matching': 0
        })
        points_per_type = assessment_config.get('pointsPerType', {
            'multiple_choice': 1,
            'short_answer': 2,
            'extended_response': 4,
            'true_false': 1,
            'matching': 1
        })
        dok_distribution = assessment_config.get('dokDistribution', {
            '1': 3, '2': 6, '3': 4, '4': 2
        })
        include_answer_key = assessment_config.get('includeAnswerKey', True)
        include_standards_ref = assessment_config.get('includeStandardsReference', True)
        target_period = assessment_config.get('targetPeriod', '')

        # Get global AI notes from config
        global_ai_notes = config.get('globalAINotes', '')

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
- Example: "What year did the Civil War begin?"

DOK 2 - Skills & Concepts:
- Compare, contrast, classify, organize
- Make observations, collect data
- Explain relationships, cause/effect
- Example: "Compare the economies of the North and South before the Civil War."

DOK 3 - Strategic Thinking:
- Analyze, evaluate, synthesize
- Draw conclusions, cite evidence
- Develop a logical argument
- Example: "Using evidence from the text, explain how economic differences contributed to sectional tensions."

DOK 4 - Extended Thinking:
- Design, create, connect across content
- Research, investigate over time
- Apply concepts to new situations
- Example: "Research and create a presentation analyzing how Civil War-era economic patterns continue to influence regional differences today."
"""

        # Question type instructions
        question_type_instructions = """
QUESTION TYPE FORMATS:

MULTIPLE CHOICE (type: "multiple_choice"):
{
    "number": 1,
    "question": "Question text here?",
    "dok": 2,
    "standard": "SS.8.A.1.1",
    "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
    "answer": "B",
    "explanation": "Brief explanation of why B is correct",
    "points": 1
}

SHORT ANSWER (type: "short_answer"):
{
    "number": 5,
    "question": "Question requiring 2-3 sentence response",
    "dok": 2,
    "standard": "SS.8.A.1.2",
    "answer": "Expected answer or key points to include",
    "rubric": "2 pts: Complete answer with evidence. 1 pt: Partial answer. 0 pts: Incorrect/no answer",
    "points": 2
}

EXTENDED RESPONSE (type: "extended_response"):
{
    "number": 10,
    "question": "Complex question requiring paragraph response with analysis",
    "dok": 3,
    "standard": "SS.8.A.2.1",
    "answer": "Model response or key elements that should be included",
    "rubric": "4 pts: Thorough analysis with multiple pieces of evidence...",
    "points": 4
}

TRUE/FALSE (type: "true_false"):
{
    "number": 3,
    "question": "Statement to evaluate",
    "dok": 1,
    "standard": "SS.8.A.1.1",
    "answer": "True",
    "explanation": "Why this is true/false",
    "points": 1
}

MATCHING (type: "matching"):
{
    "number": 8,
    "question": "Match the terms to their definitions",
    "dok": 1,
    "standard": "SS.8.A.1.1",
    "terms": ["Term 1", "Term 2", "Term 3"],
    "definitions": ["Definition A", "Definition B", "Definition C"],
    "answer": {"Term 1": "Definition B", "Term 2": "Definition C", "Term 3": "Definition A"},
    "points": 3
}
"""

        prompt = f"""You are an expert assessment developer creating a standards-aligned {assessment_type} for grade {config.get('grade', '8')} {config.get('subject', 'students')}.

{dok_descriptions}

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
{f'''
TARGET PERIOD: {target_period}
(Apply any period-specific differentiation rules from the teacher's instructions below)
''' if target_period else ''}
{f'''
TEACHER'S ADDITIONAL INSTRUCTIONS (MUST FOLLOW):
{global_ai_notes}
''' if global_ai_notes else ''}
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

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert assessment developer. Create rigorous, standards-aligned assessments. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        content = completion.choices[0].message.content
        assessment = json.loads(content)

        # Add metadata
        assessment['generated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        assessment['teacher'] = config.get('teacher_name', '')

        return jsonify({"assessment": assessment, "method": "AI"})

    except Exception as e:
        error_msg = str(e)
        print(f"Assessment Generation Error: {error_msg}")
        return jsonify({"error": f"Failed to generate assessment: {error_msg}"}), 500


@planner_bp.route('/api/export-assessment', methods=['POST'])
def export_assessment():
    """Export assessment to Word document."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch

    data = request.json
    assessment = data.get('assessment', {})
    include_answer_key = data.get('includeAnswerKey', False)

    if not assessment:
        return jsonify({"error": "No assessment data provided"})

    try:
        from docx import Document
        from docx.shared import Inches, Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        import tempfile
        import base64

        doc = Document()

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
                q_para = doc.add_paragraph()
                q_num = q.get('number', '')
                q_text = q.get('question', '')
                q_points = q.get('points', 1)
                q_dok = q.get('dok', '')

                # Question number and text
                q_para.add_run(f"{q_num}. ").bold = True
                q_para.add_run(f"{q_text} ")
                q_para.add_run(f"({q_points} pt{'s' if q_points > 1 else ''})").italic = True

                # Multiple choice options
                if q.get('options'):
                    for opt in q.get('options', []):
                        opt_para = doc.add_paragraph(f"    {opt}")
                        opt_para.paragraph_format.space_before = Pt(2)
                        opt_para.paragraph_format.space_after = Pt(2)

                # Matching terms and definitions
                if q.get('terms') and q.get('definitions'):
                    doc.add_paragraph("Terms:")
                    for i, term in enumerate(q.get('terms', []), 1):
                        doc.add_paragraph(f"    {i}. {term}")
                    doc.add_paragraph("Definitions:")
                    for letter_idx, defn in enumerate(q.get('definitions', [])):
                        letter = chr(65 + letter_idx)  # A, B, C...
                        doc.add_paragraph(f"    {letter}. {defn}")

                # Answer lines for short answer/extended response
                q_type = q.get('type', section.get('type', ''))
                if q_type in ['short_answer', 'extended_response']:
                    lines = 3 if q_type == 'short_answer' else 8
                    for _ in range(lines):
                        doc.add_paragraph("_" * 70)

                doc.add_paragraph()  # Space between questions

        # Answer Key (separate page)
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
        print(f"Export error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# ASSESSMENT PLATFORM TEMPLATES
# =============================================================================

TEMPLATES_DIR = os.path.expanduser("~/.graider_data/assessment_templates")


@planner_bp.route('/api/upload-assessment-template', methods=['POST'])
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

    # Create templates directory if it doesn't exist
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

    # Generate unique ID
    template_id = str(uuid.uuid4())[:8]

    # Save the file
    ext = os.path.splitext(file.filename)[1].lower()
    filename = f"{template_id}_{platform}{ext}"
    filepath = os.path.join(TEMPLATES_DIR, filename)
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


def parse_template_structure(filepath, ext):
    """Parse a template file to understand its structure for export."""
    structure = {
        "columns": [],
        "format": ext,
        "sample_rows": []
    }

    try:
        if ext in ['.csv', '.txt']:
            import csv
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                if rows:
                    structure["columns"] = rows[0]
                    structure["sample_rows"] = rows[1:4]  # First 3 data rows

        elif ext in ['.xlsx', '.xls']:
            from openpyxl import load_workbook
            wb = load_workbook(filepath)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                structure["columns"] = [str(c) if c else '' for c in rows[0]]
                structure["sample_rows"] = [[str(c) if c else '' for c in row] for row in rows[1:4]]

        elif ext == '.json':
            with open(filepath, 'r') as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    structure["columns"] = list(data[0].keys()) if isinstance(data[0], dict) else []
                    structure["sample_rows"] = data[:3]
                elif isinstance(data, dict):
                    structure["columns"] = list(data.keys())

    except Exception as e:
        structure["error"] = str(e)

    return structure


@planner_bp.route('/api/assessment-templates', methods=['GET'])
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
            except:
                pass

    # Sort by creation date (newest first)
    templates.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    return jsonify({"templates": templates})


@planner_bp.route('/api/assessment-template/<template_id>', methods=['DELETE'])
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
        return jsonify({"error": str(e)}), 500


@planner_bp.route('/api/export-assessment-platform', methods=['POST'])
def export_assessment_for_platform():
    """Export assessment in a specific platform's format."""
    data = request.json
    assessment = data.get('assessment', {})
    platform = data.get('platform', 'csv')
    template_id = data.get('templateId')

    if not assessment:
        return jsonify({"error": "No assessment data provided"}), 400

    try:
        import csv
        import io
        import base64

        # Get template structure if provided
        template_structure = None
        if template_id:
            meta_path = os.path.join(TEMPLATES_DIR, f"{template_id}.meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    template_meta = json.load(f)
                    template_structure = template_meta.get('structure', {})

        # Flatten questions from all sections
        all_questions = []
        for section in assessment.get('sections', []):
            for q in section.get('questions', []):
                all_questions.append({
                    **q,
                    'section': section.get('name', '')
                })

        # Export based on platform
        if platform == 'wayground' or platform == 'csv':
            # Generic CSV format - can be customized based on template
            output = io.StringIO()

            # Determine columns based on template or default
            if template_structure and template_structure.get('columns'):
                columns = template_structure['columns']
            else:
                columns = ['Question Number', 'Question', 'Type', 'Options', 'Answer',
                          'Points', 'DOK Level', 'Standard', 'Section']

            writer = csv.writer(output)
            writer.writerow(columns)

            for q in all_questions:
                options = '|'.join(q.get('options', [])) if q.get('options') else ''
                answer = q.get('answer', '')
                if isinstance(answer, dict):
                    answer = str(answer)

                row = [
                    q.get('number', ''),
                    q.get('question', ''),
                    q.get('type', 'multiple_choice'),
                    options,
                    answer,
                    q.get('points', 1),
                    q.get('dok', 2),
                    q.get('standard', ''),
                    q.get('section', '')
                ]
                writer.writerow(row)

            content = output.getvalue()
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
            filename = f"{safe_title.replace(' ', '_')}_{platform}.csv"

            return jsonify({
                "document": content_b64,
                "filename": filename,
                "format": "csv",
                "mime_type": "text/csv"
            })

        elif platform == 'canvas_qti':
            # QTI format for Canvas
            # This is a simplified QTI - full implementation would be more complex
            qti_xml = generate_qti_xml(assessment, all_questions)
            content_b64 = base64.b64encode(qti_xml.encode('utf-8')).decode('utf-8')

            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
            filename = f"{safe_title.replace(' ', '_')}_qti.xml"

            return jsonify({
                "document": content_b64,
                "filename": filename,
                "format": "xml",
                "mime_type": "application/xml"
            })

        elif platform == 'kahoot':
            # Kahoot spreadsheet format
            output = io.StringIO()
            writer = csv.writer(output)

            # Kahoot format: Question, Answer 1, Answer 2, Answer 3, Answer 4, Time limit, Correct answer(s)
            writer.writerow(['Question', 'Answer 1', 'Answer 2', 'Answer 3', 'Answer 4',
                           'Time limit', 'Correct answer(s)'])

            for q in all_questions:
                if q.get('options'):
                    options = q.get('options', [])
                    # Clean options (remove A), B), etc. prefixes)
                    clean_options = []
                    for opt in options[:4]:
                        clean = opt.strip()
                        if len(clean) > 2 and clean[1] == ')':
                            clean = clean[2:].strip()
                        clean_options.append(clean)

                    # Pad to 4 options
                    while len(clean_options) < 4:
                        clean_options.append('')

                    # Determine correct answer number
                    correct = q.get('answer', 'A')
                    if isinstance(correct, str) and len(correct) == 1:
                        correct_num = ord(correct.upper()) - ord('A') + 1
                    else:
                        correct_num = 1

                    writer.writerow([
                        q.get('question', ''),
                        clean_options[0],
                        clean_options[1],
                        clean_options[2],
                        clean_options[3],
                        30,  # Default 30 second time limit
                        correct_num
                    ])

            content = output.getvalue()
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
            filename = f"{safe_title.replace(' ', '_')}_kahoot.csv"

            return jsonify({
                "document": content_b64,
                "filename": filename,
                "format": "csv",
                "mime_type": "text/csv"
            })

        elif platform == 'quizlet':
            # Quizlet import format: term<tab>definition (or question<tab>answer)
            output = io.StringIO()

            for q in all_questions:
                question = q.get('question', '')
                answer = q.get('answer', '')
                if isinstance(answer, dict):
                    answer = answer.get('answer', str(answer))
                output.write(f"{question}\t{answer}\n")

            content = output.getvalue()
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
            filename = f"{safe_title.replace(' ', '_')}_quizlet.txt"

            return jsonify({
                "document": content_b64,
                "filename": filename,
                "format": "txt",
                "mime_type": "text/plain"
            })

        elif platform == 'google_forms':
            # Google Forms compatible CSV
            output = io.StringIO()
            writer = csv.writer(output)

            writer.writerow(['Question', 'Question Type', 'Required', 'Option 1',
                           'Option 2', 'Option 3', 'Option 4', 'Correct Answer', 'Points'])

            for q in all_questions:
                q_type = q.get('type', 'multiple_choice')
                if q_type == 'multiple_choice':
                    gf_type = 'MULTIPLE_CHOICE'
                elif q_type == 'short_answer':
                    gf_type = 'SHORT_ANSWER'
                elif q_type == 'true_false':
                    gf_type = 'MULTIPLE_CHOICE'
                else:
                    gf_type = 'PARAGRAPH'

                options = q.get('options', ['', '', '', ''])
                while len(options) < 4:
                    options.append('')

                writer.writerow([
                    q.get('question', ''),
                    gf_type,
                    'TRUE',
                    options[0] if options else '',
                    options[1] if len(options) > 1 else '',
                    options[2] if len(options) > 2 else '',
                    options[3] if len(options) > 3 else '',
                    q.get('answer', ''),
                    q.get('points', 1)
                ])

            content = output.getvalue()
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
            filename = f"{safe_title.replace(' ', '_')}_google_forms.csv"

            return jsonify({
                "document": content_b64,
                "filename": filename,
                "format": "csv",
                "mime_type": "text/csv"
            })

        else:
            return jsonify({"error": f"Unknown platform: {platform}"}), 400

    except Exception as e:
        print(f"Platform export error: {e}")
        return jsonify({"error": str(e)}), 500


def generate_qti_xml(assessment, questions):
    """Generate QTI 1.2 XML for Canvas/LMS import."""
    title = assessment.get('title', 'Assessment')

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<questestinterop xmlns="http://www.imsglobal.org/xsd/ims_qtiasiv1p2">
  <assessment ident="{title.replace(' ', '_')}" title="{title}">
    <section ident="root_section">
'''

    for q in questions:
        q_id = f"q_{q.get('number', 1)}"
        q_text = q.get('question', '')
        q_type = q.get('type', 'multiple_choice')
        points = q.get('points', 1)

        if q_type == 'multiple_choice' and q.get('options'):
            xml += f'''      <item ident="{q_id}" title="Question {q.get('number', '')}">
        <itemmetadata>
          <qtimetadata>
            <qtimetadatafield>
              <fieldlabel>question_type</fieldlabel>
              <fieldentry>multiple_choice_question</fieldentry>
            </qtimetadatafield>
            <qtimetadatafield>
              <fieldlabel>points_possible</fieldlabel>
              <fieldentry>{points}</fieldentry>
            </qtimetadatafield>
          </qtimetadata>
        </itemmetadata>
        <presentation>
          <material>
            <mattext texttype="text/html">{q_text}</mattext>
          </material>
          <response_lid ident="response1" rcardinality="Single">
            <render_choice>
'''
            correct_answer = q.get('answer', 'A')
            for i, opt in enumerate(q.get('options', [])):
                opt_id = chr(65 + i)  # A, B, C, D
                opt_text = opt
                if len(opt) > 2 and opt[1] == ')':
                    opt_text = opt[2:].strip()
                xml += f'''              <response_label ident="{opt_id}">
                <material>
                  <mattext texttype="text/html">{opt_text}</mattext>
                </material>
              </response_label>
'''
            xml += f'''            </render_choice>
          </response_lid>
        </presentation>
        <resprocessing>
          <outcomes>
            <decvar maxvalue="100" minvalue="0" varname="SCORE" vartype="Decimal"/>
          </outcomes>
          <respcondition continue="No">
            <conditionvar>
              <varequal respident="response1">{correct_answer}</varequal>
            </conditionvar>
            <setvar action="Set" varname="SCORE">100</setvar>
          </respcondition>
        </resprocessing>
      </item>
'''

    xml += '''    </section>
  </assessment>
</questestinterop>'''

    return xml


@planner_bp.route('/api/grade-assessment-answers', methods=['POST'])
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

        results = {
            "questions": [],
            "score": 0,
            "total_points": 0,
            "percentage": 0,
            "feedback_summary": ""
        }

        # Collect questions that need AI grading (short answer, extended response)
        ai_grading_needed = []

        # Process each section and question
        for sIdx, section in enumerate(assessment.get('sections', [])):
            for qIdx, question in enumerate(section.get('questions', [])):
                answer_key = f"{sIdx}-{qIdx}"
                student_answer = answers.get(answer_key)
                q_type = question.get('type', 'multiple_choice')
                points = question.get('points', 1)
                correct_answer = question.get('answer')

                results["total_points"] += points

                question_result = {
                    "number": question.get('number', qIdx + 1),
                    "question": question.get('question', ''),
                    "type": q_type,
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                    "points_possible": points,
                    "points_earned": 0,
                    "is_correct": False,
                    "feedback": ""
                }

                if student_answer is None or student_answer == "":
                    question_result["feedback"] = "No answer provided"
                    results["questions"].append(question_result)
                    continue

                # Grade based on question type
                if q_type == "multiple_choice":
                    # Check if answer matches (handle both index and letter formats)
                    options = question.get('options', [])
                    student_letter = None
                    if isinstance(student_answer, int) and student_answer < len(options):
                        student_letter = chr(65 + student_answer)  # Convert index to letter
                    elif isinstance(student_answer, str):
                        student_letter = student_answer.upper().strip()
                        if len(student_letter) > 1 and student_letter[1] == ')':
                            student_letter = student_letter[0]

                    correct_letter = correct_answer.upper().strip() if correct_answer else ""
                    if len(correct_letter) > 1 and correct_letter[1] == ')':
                        correct_letter = correct_letter[0]

                    is_correct = student_letter == correct_letter
                    question_result["is_correct"] = is_correct
                    question_result["points_earned"] = points if is_correct else 0
                    question_result["student_answer"] = f"{student_letter}) {options[ord(student_letter) - 65] if student_letter and ord(student_letter) - 65 < len(options) else student_answer}" if student_letter else student_answer
                    question_result["feedback"] = "Correct!" if is_correct else f"Incorrect. The correct answer is {correct_answer}."

                elif q_type == "true_false":
                    is_correct = str(student_answer).lower() == str(correct_answer).lower()
                    question_result["is_correct"] = is_correct
                    question_result["points_earned"] = points if is_correct else 0
                    explanation = question.get('explanation', '')
                    question_result["feedback"] = "Correct!" if is_correct else f"Incorrect. The answer is {correct_answer}. {explanation}"

                elif q_type == "matching":
                    # Check matching answers
                    correct_matches = question.get('answer', {})
                    terms = question.get('terms', [])
                    total_matches = len(terms)
                    correct_count = 0

                    match_details = []
                    for tIdx in range(total_matches):
                        match_key = f"{sIdx}-{qIdx}-match-{tIdx}"
                        student_match = answers.get(match_key, "")
                        term = terms[tIdx] if tIdx < len(terms) else f"Term {tIdx + 1}"

                        # Find correct letter for this term
                        correct_letter = None
                        definitions = question.get('definitions', [])
                        if term in correct_matches:
                            correct_def = correct_matches[term]
                            try:
                                def_idx = definitions.index(correct_def)
                                correct_letter = chr(65 + def_idx)
                            except ValueError:
                                correct_letter = None

                        is_match_correct = student_match.upper() == correct_letter if correct_letter else False
                        if is_match_correct:
                            correct_count += 1
                        match_details.append({
                            "term": term,
                            "student": student_match,
                            "correct": correct_letter,
                            "is_correct": is_match_correct
                        })

                    # Partial credit
                    earned = round(points * (correct_count / total_matches)) if total_matches > 0 else 0
                    question_result["points_earned"] = earned
                    question_result["is_correct"] = correct_count == total_matches
                    question_result["match_details"] = match_details
                    question_result["feedback"] = f"Got {correct_count}/{total_matches} matches correct."

                elif q_type in ["short_answer", "extended_response"]:
                    # Queue for AI grading
                    ai_grading_needed.append({
                        "index": len(results["questions"]),
                        "question": question,
                        "student_answer": student_answer,
                        "result": question_result
                    })

                results["questions"].append(question_result)

        # AI grading for open-ended questions
        if ai_grading_needed:
            try:
                from openai import OpenAI
                client = OpenAI()

                for item in ai_grading_needed:
                    q = item["question"]
                    student_ans = item["student_answer"]
                    q_result = item["result"]
                    points = q.get('points', 1)

                    grading_prompt = f"""Grade this student answer for the following question.

Question: {q.get('question', '')}
Question Type: {q.get('type', 'short_answer')}
Points Possible: {points}
Correct/Model Answer: {q.get('answer', 'N/A')}
Rubric: {q.get('rubric', 'N/A')}
DOK Level: {q.get('dok', 'N/A')}
Standard: {q.get('standard', 'N/A')}

Student's Answer: {student_ans}

Evaluate the student's response and provide:
1. Points earned (0 to {points})
2. Brief feedback (2-3 sentences)
3. Whether the answer demonstrates understanding

Respond in JSON format:
{{"points_earned": <number>, "feedback": "<string>", "is_correct": <boolean>}}"""

                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a fair and helpful teacher grading student work. Be encouraging but accurate. Provide constructive feedback."},
                            {"role": "user", "content": grading_prompt}
                        ],
                        response_format={"type": "json_object"},
                        max_tokens=300
                    )

                    ai_result = json.loads(response.choices[0].message.content)
                    q_result["points_earned"] = min(ai_result.get("points_earned", 0), points)
                    q_result["feedback"] = ai_result.get("feedback", "")
                    q_result["is_correct"] = ai_result.get("is_correct", False)

                    # Update in results
                    results["questions"][item["index"]] = q_result

            except Exception as e:
                print(f"AI grading error: {e}")
                # Fall back to basic comparison for failed AI grading
                for item in ai_grading_needed:
                    q_result = item["result"]
                    q_result["feedback"] = "Answer recorded. Manual review recommended."
                    q_result["points_earned"] = 0
                    results["questions"][item["index"]] = q_result

        # Calculate final score
        results["score"] = sum(q["points_earned"] for q in results["questions"])
        results["percentage"] = round((results["score"] / results["total_points"]) * 100) if results["total_points"] > 0 else 0

        # Generate summary feedback
        correct_count = sum(1 for q in results["questions"] if q["is_correct"])
        total_questions = len(results["questions"])
        results["feedback_summary"] = f"You answered {correct_count} out of {total_questions} questions correctly, earning {results['score']}/{results['total_points']} points ({results['percentage']}%)."

        return jsonify({"results": results})

    except Exception as e:
        print(f"Grade assessment error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
