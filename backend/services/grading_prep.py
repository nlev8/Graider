"""Per-question grading prep for the grading pipeline: expected-answer parsing,
point distribution across extracted responses, and math-subject classification.
Pure logic (regex / list-dict math — no LLM / I/O / Flask) extracted from
assignment_grader.py. Wave 7 Slice 3 (grading-engine decomposition).
"""
import re


def _parse_expected_answers(custom_instructions: str) -> dict:
    """Parse expected answers from gradingNotes/custom instructions.

    Returns dict mapping question index (int) or question text (str) to expected answer.
    """
    answers = {}
    if not custom_instructions:
        return answers

    # Parse "Q1: answer" or "- Q1: answer" patterns
    for match in re.finditer(r'(?:^|\n)\s*-?\s*Q(\d+)\s*:\s*(.+)', custom_instructions):
        idx = int(match.group(1)) - 1  # 0-indexed
        answers[idx] = match.group(2).strip()

    # Parse "VOCABULARY EXPECTED DEFINITIONS:" section
    in_vocab = False
    for line in custom_instructions.split('\n'):
        line = line.strip()
        if 'EXPECTED' in line.upper() and ('DEFINITION' in line.upper() or 'ANSWER' in line.upper()):
            in_vocab = True
            continue
        if in_vocab and line.startswith('- '):
            parts = line[2:].split(':', 1)
            if len(parts) == 2:
                answers[parts[0].strip()] = parts[1].strip()
        elif in_vocab and not line:
            in_vocab = False

    return answers


def _distribute_points(responses: list, marker_config: list, total_points: int) -> list:
    """Distribute point values and section metadata across extracted responses.

    Uses marker_config if available, otherwise distributes evenly.
    Returns list of dicts with 'points', 'section_name', and 'section_type' per response.
    """
    if not responses:
        return []

    # Build lookup: marker_name_lower -> {points, name, type}
    marker_meta = {}
    if marker_config:
        for m in marker_config:
            if isinstance(m, dict):
                marker_meta[m.get('start', '').lower()] = {
                    'points': m.get('points', 10),
                    'name': m.get('start', 'Section'),
                    'type': m.get('type', 'written')
                }
            elif isinstance(m, str):
                marker_meta[m.lower()] = {
                    'points': 10,
                    'name': m,
                    'type': 'written'
                }

    result = []
    default_pts = total_points // max(len(responses), 1)

    for resp in responses:
        question = resp.get("question", "").lower()
        matched = None
        for marker_key, meta in marker_meta.items():
            if marker_key in question:
                matched = meta
                break

        if matched:
            result.append({
                'points': matched['points'],
                'section_name': matched['name'],
                'section_type': matched['type']
            })
        else:
            result.append({
                'points': default_pts,
                'section_name': '',
                'section_type': 'written'
            })

    return result


MATH_SUBJECTS = {
    'math', 'mathematics', 'algebra', 'pre-algebra', 'geometry',
    'calculus', 'pre-calculus', 'trigonometry', 'statistics',
    'ap calculus', 'ap statistics', 'integrated math',
    'math 6', 'math 7', 'math 8',
}


def _is_math_subject(subject: str) -> bool:
    """Check if the teacher-selected subject is a math subject.

    STRICT: Only returns True when subject was explicitly set to a math
    subject in Settings. Never guesses from question content or keywords.
    """
    return subject.strip().lower() in MATH_SUBJECTS


def build_section_rubric(marker_config: list, effort_points: int = 15) -> str:
    """Build a section-based rubric from marker configuration."""
    if not marker_config:
        return ""  # Use default rubric

    rubric_lines = ["""
You are grading a student assignment with SECTION-BASED POINT VALUES.
Be ENCOURAGING and GENEROUS - these are middle school students.

SECTION POINT VALUES:"""]

    total = 0
    for m in marker_config:
        if isinstance(m, dict):
            name = m.get('start', 'Section')
            points = m.get('points', 10)
            section_type = m.get('type', 'written')
            rubric_lines.append(f"- {name}: {points} points ({section_type})")
            total += points
        elif isinstance(m, str):
            rubric_lines.append(f"- {m}: 10 points")
            total += 10

    rubric_lines.append(f"- Effort & Engagement: {effort_points} points")
    total += effort_points
    rubric_lines.append(f"\nTOTAL: {total} points")

    # Build section names list for JSON example
    section_names = [m.get('start', 'Section') if isinstance(m, dict) else m for m in marker_config]
    section_json_example = ',\n        '.join([f'"{name}": {{"earned": <pts>, "possible": {m.get("points", 10) if isinstance(m, dict) else 10}}}' for name, m in zip(section_names, marker_config)])

    rubric_lines.append(f"""
GRADING RULES:
- Grade each section out of its assigned points
- BLANK SECTION = 0 POINTS for that section (no partial credit)
- For fill-blank sections: each correct answer is worth proportional points
- For written sections: grade on quality, completeness, and effort
- Effort & Engagement is based on overall presentation and engagement
- Accept reasonable synonyms and alternate phrasings
- Minor spelling errors should NOT be penalized if meaning is clear

IMPORTANT: Your JSON output MUST include a "section_scores" field showing points for each section:
"section_scores": {{
        {section_json_example},
        "Effort & Engagement": {{"earned": <pts>, "possible": {effort_points}}}
    }}

The "score" field should equal the sum of all section_scores earned values.
""")

    return "\n".join(rubric_lines)
