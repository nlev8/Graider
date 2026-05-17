"""Prompt construction for the planner. Pure string building (no Flask)."""


def _build_assignment_prompt(lesson_plan, config, assignment_type='assignment'):
    """Build the AI prompt for generating an assignment from a lesson plan.

    Returns the full prompt string. Extracted for testability.
    Assignment type determines the structure:
    - 'assignment': returns None (caller uses existing multi-section worksheet logic)
    - 'essay': single essay prompt with thesis question + rubric
    - 'project': project brief with milestones, deliverables + rubric
    """
    lesson_title = lesson_plan.get('title', 'Untitled Lesson')
    lesson_overview = lesson_plan.get('overview', '')
    essential_questions = lesson_plan.get('essential_questions', [])
    days = lesson_plan.get('days', [])

    all_vocabulary = []
    all_objectives = []
    all_key_points = []

    for day in days:
        vocab = day.get('vocabulary', [])
        for v in vocab:
            if isinstance(v, dict):
                all_vocabulary.append(v.get('term', '') + ": " + v.get('definition', ''))
            else:
                all_vocabulary.append(str(v))
        if day.get('objective'):
            all_objectives.append(day['objective'])
        di = day.get('direct_instruction', {})
        if isinstance(di, dict) and di.get('key_points'):
            all_key_points.extend(di['key_points'])

    _subject = config.get('subject', '')
    _grade = config.get('grade', '7')
    global_ai_notes = config.get('globalAINotes', '')

    # Lesson context block (shared by all types)
    lesson_block = "LESSON PLAN DETAILS:" + chr(10)
    lesson_block += "Title: " + lesson_title + chr(10)
    lesson_block += "Overview: " + lesson_overview + chr(10)
    lesson_block += chr(10) + "Essential Questions:" + chr(10)
    lesson_block += (chr(10).join("- " + q for q in essential_questions) if essential_questions else "None specified") + chr(10)
    lesson_block += chr(10) + "Learning Objectives:" + chr(10)
    lesson_block += (chr(10).join("- " + obj for obj in all_objectives) if all_objectives else "None specified") + chr(10)
    lesson_block += chr(10) + "Key Content Points:" + chr(10)
    lesson_block += (chr(10).join("- " + kp for kp in all_key_points[:10]) if all_key_points else "None specified") + chr(10)
    lesson_block += chr(10) + "Vocabulary:" + chr(10)
    lesson_block += (chr(10).join("- " + v for v in all_vocabulary[:15]) if all_vocabulary else "None specified") + chr(10)

    global_notes_block = ""
    if global_ai_notes:
        global_notes_block = chr(10) + "=== TEACHER INSTRUCTIONS (MUST FOLLOW) ===" + chr(10) + global_ai_notes + chr(10) + "=== END TEACHER INSTRUCTIONS ===" + chr(10)

    # ── ESSAY TYPE ──────────────────────────────────────────────
    if assignment_type == 'essay':
        return (
            "You are an expert " + _subject + " teacher creating an essay assignment for grade " + _grade + " students." + chr(10)
            + global_notes_block + chr(10)
            + lesson_block + chr(10)
            + "Create a SINGLE essay assignment based on this lesson plan. Do NOT create multiple sections, " + chr(10)
            + "vocabulary matching, multiple choice, or short answer questions. This is an ESSAY ONLY." + chr(10)
            + chr(10)
            + "The essay should:" + chr(10)
            + "- Have a clear, thought-provoking thesis prompt that connects to the lesson objectives" + chr(10)
            + "- Specify required length (number of paragraphs or word count)" + chr(10)
            + "- Include pre-writing guidance (what to consider, key terms to use)" + chr(10)
            + "- Include a detailed rubric with 4-5 categories and point values" + chr(10)
            + chr(10)
            + "Return JSON with this structure:" + chr(10)
            + '{' + chr(10)
            + '  "title": "Essay title",' + chr(10)
            + '  "type": "essay",' + chr(10)
            + '  "instructions": "Brief instructions for the student",' + chr(10)
            + '  "time_estimate": "Estimated completion time",' + chr(10)
            + '  "total_points": 100,' + chr(10)
            + '  "essay_prompt": "The full essay question/thesis prompt",' + chr(10)
            + '  "required_length": "e.g., 3-5 paragraphs or 500-750 words",' + chr(10)
            + '  "prewriting_guidance": ["Key point to address 1", "Key point 2", ...],' + chr(10)
            + '  "vocabulary_to_use": ["term1", "term2", ...],' + chr(10)
            + '  "rubric": [' + chr(10)
            + '    {"category": "Thesis & Argument", "points": 25, "description": "Clear thesis supported by evidence"},' + chr(10)
            + '    {"category": "Content & Evidence", "points": 25, "description": "Uses specific examples from lesson content"},' + chr(10)
            + '    {"category": "Organization", "points": 20, "description": "Logical structure with intro, body, conclusion"},' + chr(10)
            + '    {"category": "Writing Quality", "points": 20, "description": "Grammar, spelling, academic language"},' + chr(10)
            + '    {"category": "Vocabulary Use", "points": 10, "description": "Uses key terms correctly"}' + chr(10)
            + '  ]' + chr(10)
            + '}' + chr(10)
            + chr(10)
            + "Return ONLY valid JSON. No markdown, no code fences."
        )

    # ── PROJECT TYPE ────────────────────────────────────────────
    if assignment_type == 'project':
        return (
            "You are an expert " + _subject + " teacher creating a multi-day project for grade " + _grade + " students." + chr(10)
            + global_notes_block + chr(10)
            + lesson_block + chr(10)
            + "Create a PROJECT assignment based on this lesson plan. Do NOT create multiple choice questions, " + chr(10)
            + "vocabulary matching, or short answer sections. This is a PROJECT with deliverables and milestones." + chr(10)
            + chr(10)
            + "The project should:" + chr(10)
            + "- Have a clear, engaging project description" + chr(10)
            + "- Include 3-5 milestones with due dates (Day 1, Day 2, etc.)" + chr(10)
            + "- Specify concrete deliverables (what the student turns in)" + chr(10)
            + "- Include a detailed rubric with categories and point values" + chr(10)
            + "- Be achievable within the lesson timeframe" + chr(10)
            + chr(10)
            + "Return JSON with this structure:" + chr(10)
            + '{' + chr(10)
            + '  "title": "Project title",' + chr(10)
            + '  "type": "project",' + chr(10)
            + '  "instructions": "Project overview and goals for the student",' + chr(10)
            + '  "time_estimate": "Total project duration",' + chr(10)
            + '  "total_points": 100,' + chr(10)
            + '  "project_description": "Detailed description of what students will create",' + chr(10)
            + '  "deliverables": ["Final essay/presentation/model", "Research notes", ...],' + chr(10)
            + '  "milestones": [' + chr(10)
            + '    {"day": 1, "task": "Research and gather sources", "deliverable": "Annotated bibliography"},' + chr(10)
            + '    {"day": 2, "task": "Create outline", "deliverable": "Project outline"},' + chr(10)
            + '    {"day": 3, "task": "Build/write draft", "deliverable": "Draft submission"},' + chr(10)
            + '    {"day": 4, "task": "Revise and finalize", "deliverable": "Final product"}' + chr(10)
            + '  ],' + chr(10)
            + '  "rubric": [' + chr(10)
            + '    {"category": "Content & Accuracy", "points": 30, "description": "Demonstrates understanding of lesson content"},' + chr(10)
            + '    {"category": "Creativity & Effort", "points": 25, "description": "Original thinking and thorough work"},' + chr(10)
            + '    {"category": "Organization", "points": 20, "description": "Clear structure and logical flow"},' + chr(10)
            + '    {"category": "Presentation", "points": 15, "description": "Professional quality of final deliverable"},' + chr(10)
            + '    {"category": "Timeliness", "points": 10, "description": "Met milestone deadlines"}' + chr(10)
            + '  ]' + chr(10)
            + '}' + chr(10)
            + chr(10)
            + "Return ONLY valid JSON. No markdown, no code fences."
        )

    # ── ASSIGNMENT TYPE (default — multi-section worksheet) ─────
    # Returns None to signal the caller to use the existing prompt logic
    return None


def _build_period_differentiation_block(target_period):
    """Period-differentiation prompt block for generate_assessment.

    Emitted only when target_period is non-empty. Period differentiation
    modifies vocabulary, reading level, context complexity, and scaffolding
    tone — it does NOT modify the DOK distribution. Without this clarifier,
    the AI receives contradictory instructions when both a DOK distribution
    AND a target_period with period-specific differentiation are present.
    Mirrors the orthogonal-coexistence clarifier added to remediation in
    Phase 4.2 #12 (PR #149) — see _build_remediation_prompt in
    student_portal_routes.py.
    """
    target_period = str(target_period).strip() if target_period is not None else ""
    if not target_period:
        return ""
    return (
        f"TARGET PERIOD FOR THIS ASSESSMENT: {target_period}\n"
        "CRITICAL: You MUST apply any period-specific differentiation rules "
        "from the teacher instructions above to this period.\n"
        "- If the instructions indicate this period is advanced, use more "
        "challenging vocabulary, richer contexts, and less scaffolding — "
        "but DO NOT modify the DOK distribution above.\n"
        "- If the instructions indicate this period is standard or lower "
        "level, use simpler vocabulary, more scaffolding, and clearer "
        "examples — but DO NOT modify the DOK distribution above.\n"
        "- Cognitive rigor (DOK) is set by the distribution; period "
        "differentiation modifies vocabulary, reading level, context "
        "complexity, and scaffolding only.\n"
        "- They can coexist — e.g., \"Period 3 advanced\" + \"DOK 1 Recall\" "
        "means a recall question with more challenging vocabulary.\n"
    )
