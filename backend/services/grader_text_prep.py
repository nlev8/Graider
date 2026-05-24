"""Student-text preparation for the grading pipeline: FERPA PII sanitization
(before any external-AI call) + AI-detection preprocessing. Pure logic
(re / hashlib — no LLM / network / Flask) extracted from
assignment_grader.py. Wave 7 Slice 2 (grading-engine decomposition).
"""
import hashlib
import re


def sanitize_pii_for_ai(student_name: str, content: str) -> tuple:
    """
    FERPA Compliance: Remove all Personally Identifiable Information (PII)
    before sending student work to external AI services.

    Returns:
        tuple: (anonymous_id, sanitized_content)
    """
    if not content:
        return "Student_0000", ""

    # Create consistent anonymous identifier from student name
    if student_name:
        hash_val = int(hashlib.md5(student_name.encode()).hexdigest(), 16) % 10000
        anon_id = f"Student_{hash_val:04d}"
    else:
        anon_id = "Student_0000"

    sanitized = content

    # Remove student name variations (first name, last name, full name)
    if student_name:
        name_parts = student_name.split()
        for part in name_parts:
            if len(part) > 2:  # Avoid removing short words like "I" or "A"
                sanitized = re.sub(
                    rf'\b{re.escape(part)}\b',
                    '[STUDENT]',
                    sanitized,
                    flags=re.IGNORECASE
                )

    # Remove Social Security Numbers (XXX-XX-XXXX)
    sanitized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN-REMOVED]', sanitized)

    # Remove Student ID numbers (7-10 digit numbers that look like IDs)
    sanitized = re.sub(r'\b\d{7,10}\b', '[ID-REMOVED]', sanitized)

    # Remove email addresses
    sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL-REMOVED]', sanitized)

    # Remove phone numbers (various formats)
    sanitized = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE-REMOVED]', sanitized)
    sanitized = re.sub(r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}', '[PHONE-REMOVED]', sanitized)

    # Remove dates that might be birthdates (MM/DD/YYYY, MM-DD-YYYY, etc.)
    # But preserve historical dates (years before 2000 are likely historical)
    sanitized = re.sub(r'\b\d{1,2}[/-]\d{1,2}[/-](20\d{2}|19[89]\d)\b', '[DATE-REMOVED]', sanitized)

    # Remove street addresses (basic pattern)
    sanitized = re.sub(
        r'\b\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|court|ct|boulevard|blvd|circle|cir|place|pl)\.?\b',
        '[ADDRESS-REMOVED]',
        sanitized,
        flags=re.IGNORECASE
    )

    # Remove zip codes (5 digit or 5+4 format)
    sanitized = re.sub(r'\b\d{5}(-\d{4})?\b', '[ZIP-REMOVED]', sanitized)

    return anon_id, sanitized


def preprocess_for_ai_detection(text: str) -> str:
    """
    Preprocess extracted text to focus on student-written content for AI detection.

    - Extracts fill-in-the-blank answers (text between underscores)
    - Removes template/instructional text
    - Focuses on longer written responses, not factual answers

    Returns cleaned text suitable for AI detection analysis.
    Short fill-in-blank answers (dates, names, single words) are excluded since
    they're factual answers, not writing that can be AI-detected.
    """
    import re

    lines = text.split('\n')
    student_written = []
    fill_in_answers = []

    # Patterns that indicate template/instructional text (not student writing)
    template_patterns = [
        r'^Q:\s*',  # Question prefix
        r'^A:\s*$',  # Empty answer prefix
        r'^The .+ happened in the year',
        r'^The U\.S\. bought',
        r'^The purchase doubled',
        r'^The price paid',
        r'^This purchase helped',
        r'^Explain in your own words',
        r'^Write a \d+',
        r'^How do you think .+\?$',  # Questions ending with ?
        r'^Why was the .+\?$',
        r'^Who was the .+\?$',
        r'^What role did .+\?$',
        r'^How did .+\?$',
        r'^\d+\.\s*(Why|What|Who|How|Where|When)\s+.+\?$',  # Numbered questions
        r'^Primary Source Quote',
        r'^Quote from',
        r'^"The acquisition of',  # Known quote text
        r'^Student Task:',
        r'^Final Reflection Question',
        r'^Questions to Check Understanding',
        r'^Guided Notes',
        r'^Cornell Notes',
        r'^Essential Question',
        r'^Vocabulary',
    ]

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Extract fill-in-the-blank answers (text between underscores)
        blank_matches = re.findall(r'_{2,}([^_\n]{1,100})_{2,}', line)
        if blank_matches:
            for match in blank_matches:
                answer = match.strip()
                if answer:
                    fill_in_answers.append(answer)
            continue  # Rest of line is template

        # Strip "A: " prefix before checking template patterns so patterns match
        check_text = line_stripped
        if check_text.startswith('A: '):
            check_text = check_text[3:].strip()

        # Check if this line matches a template pattern
        is_template = False
        for pattern in template_patterns:
            if re.match(pattern, check_text, re.IGNORECASE):
                is_template = True
                break

        if is_template:
            continue

        # Skip lines that are just "A: " followed by a question (unanswered)
        if line_stripped.startswith('A: ') and line_stripped.endswith('?'):
            continue

        # Skip Q: labels
        if line_stripped.startswith('Q: '):
            continue

        # Skip vocabulary definitions from template (Term | Definition format)
        if ' | ' in check_text:
            continue

        # Skip quoted text (primary source quotes from the template)
        if check_text.startswith('"') and check_text.endswith('"'):
            continue

        # Skip lines that are template fill-in-blank prompts (not the student's answer)
        # These have the structure "The ___ did something ___" with underscores
        underscore_count = check_text.count('_')
        non_underscore = re.sub(r'_+', '', check_text).strip()
        if underscore_count >= 3 and len(non_underscore) > 20:
            # Line is mostly template text with blank slots — skip it
            continue

        # Keep substantive student-written content (paragraphs, explanations)
        # Must be more than 30 chars to be considered "writing" vs labels
        # Exclude lines that are questions (end with ?) or instruction text
        if len(check_text) > 30 and not check_text.endswith('?'):
            # Skip lines that look like unanswered template text
            instruction_keywords = ['write a few sentences', 'explain in your own words',
                                   'how do you think', 'why do you think', 'what do you think',
                                   'describe how', 'explain how', 'explain why',
                                   'student task:', 'final reflection']
            is_instruction = any(kw in check_text.lower() for kw in instruction_keywords)
            if not is_instruction:
                student_written.append(check_text)

    # Build result
    result_parts = []

    # Only flag fill-in answers if they're suspiciously long (might be copied text)
    # Short answers like "1803", "France", "15 million" are factual, not AI-detectable
    suspicious_fill_ins = [a for a in fill_in_answers if len(a) > 40]
    if suspicious_fill_ins:
        result_parts.append("Suspiciously long fill-in answers:\n" + "\n".join(suspicious_fill_ins))

    # Student written content (main focus for AI detection)
    if student_written:
        result_parts.append("Student written content:\n" + "\n".join(student_written))

    # If no substantial content to analyze, return empty (skip AI detection)
    if not result_parts:
        return ""

    return "\n\n".join(result_parts)
