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


def load_standards(state, subject):
    """Load standards from JSON file."""
    # Clean subject name for filename (replace spaces with underscores, slashes with hyphens)
    subject_clean = subject.lower().replace(' ', '_').replace('/', '-')
    filename = f"standards_{state.lower()}_{subject_clean}.json"
    filepath = DATA_DIR / filename

    if filepath.exists():
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data.get('standards', [])
    return []


@planner_bp.route('/api/get-standards', methods=['POST'])
def get_standards():
    """Get standards for a specific state, grade, and subject."""
    data = request.json
    state = data.get('state', 'FL')
    grade = data.get('grade', '7')
    subject = data.get('subject', 'Civics')

    # Try to load from JSON files first
    standards = load_standards(state, subject)

    if standards:
        return jsonify({"standards": standards})

    # Fallback to empty if no data file exists
    return jsonify({"standards": []})


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

        prompt = f"""You are an expert curriculum developer brainstorming lesson plan ideas for a {config.get('grade', '7')}th grade {config.get('subject', 'Social Studies')} class.
{support_docs}

Standards to Cover:
{', '.join(selected_standards)}

Generate 5 creative and diverse lesson plan ideas that would effectively teach these standards. Each idea should represent a DIFFERENT teaching approach.

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

        prompt = f"""
You are an expert curriculum developer creating a COMPLETE, READY-TO-USE {content_type} for a {config.get('grade', '7')}th grade {config.get('subject', 'Civics')} class.
{support_docs}
{idea_guidance}
Title: "{config.get('title', 'Untitled')}"
Duration: {config.get('duration', 1)} day(s)
Class Period Length: {period_length} minutes

Standards to Cover:
{', '.join(selected_standards)}

Additional Requirements:
{config.get('requirements', 'None specified')}

Create a COMPREHENSIVE, DETAILED plan that a teacher can use immediately without any additional preparation.

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
