"""Student-text preparation for the grading pipeline: FERPA PII sanitization
(before any external-AI call) + AI-detection preprocessing + prompt-injection
isolation of untrusted student answer text. Pure logic (re / hashlib — no LLM /
network / Flask) extracted from assignment_grader.py. Wave 7 Slice 2
(grading-engine decomposition).
"""
import hashlib
import logging
import re

_logger = logging.getLogger(__name__)

# Security (audit #10 — prompt injection): explicit, hard-to-forge fence around the
# untrusted student answer when it is interpolated into a grading prompt. The model is
# told everything between the two fence lines is untrusted student-authored content and
# must NOT be treated as instructions. The random-looking suffix makes the marker
# impractical for a student to reproduce verbatim; on top of that
# `neutralize_untrusted_student_text` strips any copy of the fence the student does manage
# to include, so the region cannot be closed early.
STUDENT_ANSWER_FENCE = "-----UNTRUSTED-STUDENT-ANSWER-7f3a9c2e-----"

# Line-leading tokens a student might forge to mimic the prompt's own structure / role
# markers. Matched case-insensitively at the start of a (left-stripped) line; any match is
# defanged by `neutralize_untrusted_student_text` so the line can no longer be parsed as a
# control header. Kept in sync with the section headers / role labels grade_per_question
# (and the feedback/single-pass prompts) emit, plus the standard chat role labels.
_INJECTION_MARKER_RE = re.compile(
    r"""^(?:
        system | assistant | user | developer            # chat role labels
        | teacher'?s\s+grading\s+instructions             # grade_per_question teacher block
        | teacher'?s\s+instructions                       # feedback prompt teacher block
        | question | student\s+answer | expected\s+answer # grade_per_question fields
        | points\s+possible | rules | context             # grade_per_question fields
        | grading\s+approach | section\s+type | section   # grade_per_question fields
        | default\s+score\s+anchors                       # grade_per_question anchors
        | universal\s+rules | feedback\s+structure        # feedback prompt headers
        | score | rubric\s+breakdown                      # feedback prompt fields
    )\b\s*[:\-–—]+\s*""",
    # `\b` + a REQUIRED separator (colon / hyphen / en- or em-dash) IMMEDIATELY
    # after the token: a forged control header is `TOKEN:` or `TOKEN — …` (the
    # prompt's own headers + role labels), NOT a prose word. Requiring the
    # separator right after the token (modulo whitespace) means legitimate answers
    # that merely START a line with a marker word pass through unchanged —
    # "Systematic…", "Users of…" (no word boundary), "Question 3:" (a number sits
    # before the colon), "Context matters…", "Section A …" (no separator). This
    # fixes the over-defanging the bare-word/optional-colon pattern caused
    # (Codex VB6 verify, important) while still catching dash-separated forgeries.
    re.IGNORECASE | re.VERBOSE,
)


def neutralize_untrusted_student_text(text: str) -> str:
    """Security (audit #10): structurally neutralize prompt-injection attempts in untrusted
    student answer text BEFORE it is interpolated (fenced) into a grading prompt.

    This is the programmatic safety net (Dev Principle #3 — not prompt-wording-only). It does
    NOT change a legitimate answer's content; it only defangs sequences that mimic the prompt's
    own control structure so a student cannot escalate their text into instructions:

    - Strips any copy of `STUDENT_ANSWER_FENCE` (so the student cannot close their own region).
    - Prefixes a `> ` quote-marker to any line that begins with a forged role label
      ("SYSTEM:", "ASSISTANT:", …) or a forged section header ("TEACHER'S GRADING
      INSTRUCTIONS", "POINTS POSSIBLE:", "RULES:", …). The marker text is preserved (so a
      legitimate answer that merely mentions one of these words is not corrupted) but the line
      no longer LEADS with the token, so it cannot be parsed as a control header.

    Idempotent and safe on empty / None input.
    """
    if not text:
        return ""

    # Remove any forged copy of the fence first (case-sensitive: the real marker is fixed).
    neutralized = text.replace(STUDENT_ANSWER_FENCE, "")

    out_lines = []
    for line in neutralized.split("\n"):
        stripped = line.lstrip()
        if _INJECTION_MARKER_RE.match(stripped):
            # Preserve indentation + content; break the leading control token with a quote
            # prefix so it reads as quoted untrusted content, not a header/role marker.
            indent = line[: len(line) - len(stripped)]
            out_lines.append(f"{indent}> {stripped}")
        else:
            out_lines.append(line)

    return "\n".join(out_lines)

# Given names that are ALSO ordinary English words. When such a name part appears in lowercase
# inside a student answer it is almost certainly the word ("founded in may", "grace under
# pressure"), not the student's identity — redacting it case-insensitively would corrupt grading
# (Dev Principle #3: never fix FERPA by breaking grading). For these we redact only the
# Capitalized / ALL-CAPS standalone form, which is the actual identity reference.
_COMMON_WORD_NAMES = frozenset({
    'grace', 'may', 'mark', 'hope', 'will', 'art', 'rose', 'joy', 'dawn', 'faith', 'sky', 'ray',
    'jean', 'gene', 'summer', 'autumn', 'crystal', 'pearl', 'ruby', 'olive', 'ivy', 'iris',
    'angel', 'chase', 'drew', 'frank', 'rich', 'bill', 'sunny', 'star', 'jay', 'lane', 'reed',
    'wade', 'hart', 'noble', 'price', 'paige', 'page', 'sage', 'colt', 'cliff', 'dale', 'glen',
    'heath', 'king', 'earl', 'duke', 'rey', 'sonny', 'major', 'justice', 'honor', 'merry',
})

# Words that appear inside the redaction tokens this function emits ([STUDENT], [ID-REMOVED], …).
# A name part equal to one of these would otherwise rewrite INSIDE an already-inserted token.
_RESERVED_TOKEN_WORDS = frozenset({
    'student', 'removed', 'ssn', 'email', 'phone', 'address', 'dob', 'zip',
})


def sanitize_pii_for_ai(student_name: str, content: str) -> tuple:
    """
    FERPA Compliance: Remove all Personally Identifiable Information (PII)
    before sending student work to external AI services.

    Returns:
        tuple: (anonymous_id, sanitized_content)
    """
    if not content:
        return "Student_0000", ""

    # Create consistent anonymous identifier from student name. md5 is used purely
    # for stable anonymization bucketing (not security) — usedforsecurity=False is
    # accurate and silences Bandit B324 while producing the identical digest.
    if student_name:
        hash_val = int(hashlib.md5(student_name.encode(), usedforsecurity=False).hexdigest(), 16) % 10000
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


def sanitize_grading_prompt_for_ai(student_name: str, text: str) -> str:
    """FERPA: redact student PII from text about to be sent to an external LLM, WITHOUT
    corrupting legitimate gradeable content.

    Unlike sanitize_pii_for_ai (used for whole-submission anonymization + audit), this is applied
    to the FINAL PROMPT STRING at each LLM send boundary, where the text IS the content the model
    grades. So it must NOT redact naked numeric/date answers (828,000 / 8280000 / 1803 / 2/15/1861)
    — those are student answers, not PII.

    Redacts: student-name parts (len>2, word-boundary, case-insensitive); emails; phones (with
    separators); SSNs; street addresses; and IDs/DOB/zip ONLY when context-labeled
    (e.g. "Student ID: 1234567", "DOB: 02/15/2009", "Zip: 33101").
    Preserves: all naked numbers/dates (legitimate answers).
    """
    if not text:
        return text

    sanitized = text

    # Structured PII FIRST (so a name embedded in an email, e.g. jane.doe@…, is caught whole
    # before name-redaction could break the email's local part).

    # SSN (distinctive XXX-XX-XXXX format) — safe to always redact
    sanitized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN-REMOVED]', sanitized)

    # Email addresses
    sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '[EMAIL-REMOVED]', sanitized)

    # Phone numbers — REQUIRE separators so a bare 10-digit answer is NOT treated as a phone
    sanitized = re.sub(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b', '[PHONE-REMOVED]', sanitized)
    sanitized = re.sub(r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}', '[PHONE-REMOVED]', sanitized)

    # Street addresses: street-number + 1-4 Capitalized name words + a street-type suffix.
    # Case-SENSITIVE + capitalized-name requirement avoids false positives on lowercase graded
    # content (e.g. "in 1803 for the new way") that a loose/ignorecase pattern would mangle.
    sanitized = re.sub(
        r'\b\d{1,6}\s+(?:[A-Z][A-Za-z.]*\s+){1,4}'
        r'(?:Street|Avenue|Road|Drive|Lane|Boulevard|Court|Circle|Place|Way|Highway|Terrace|Trail|'
        r'St|Ave|Rd|Dr|Ln|Blvd|Ct|Cir|Pl|Hwy)\b\.?',
        '[ADDRESS-REMOVED]',
        sanitized,
    )

    # Context-LABELED IDs / DOB / zip / SSN — only redacted when a label precedes the number, so
    # naked numeric/date ANSWERS survive. The label is preserved; only the value is redacted.
    # The separator class allows :, #, or a dash so form-style "DOB - 02/15/2009" is caught.
    # IDs have no length ceiling (label-gated ⇒ no false-positive risk on long SIS IDs).
    sanitized = re.sub(
        r'(?i)\b(student\s*id|id\s*number|local\s*id|student\s*number)\b(\s*[:#\-–]?\s*)\d{4,}\b',
        r'\1\2[ID-REMOVED]', sanitized,
    )
    sanitized = re.sub(
        r'(?i)\b(dob|date\s*of\s*birth|birth\s*date|birthday)\b(\s*[:#\-–]?\s*)\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\1\2[DOB-REMOVED]', sanitized,
    )
    sanitized = re.sub(
        r'(?i)\b(zip|zip\s*code|postal\s*code)\b(\s*[:#\-–]?\s*)\d{5}(?:-\d{4})?\b',
        r'\1\2[ZIP-REMOVED]', sanitized,
    )
    # Labeled SSN catches the bare-9-digit form ("SSN: 123456789") the literal XXX-XX-XXXX rule
    # above misses; the naked 9-digit form stays preserved (it could be a gradeable answer).
    sanitized = re.sub(
        r'(?i)\b(ssn|social\s*security(?:\s*number)?)\b(\s*[:#\-–]?\s*)\d{3}-?\d{2}-?\d{4}\b',
        r'\1\2[SSN-REMOVED]', sanitized,
    )

    # Student name variations LAST (word-boundary; len>2 avoids "I"/"Al"). Normal name parts are
    # redacted case-insensitively (strong PII removal). Common-word names (Grace/May/Mark/…) are
    # redacted only in Capitalized / ALL-CAPS form so their lowercase use as ordinary words in an
    # answer survives. Parts equal to a reserved token word are skipped to avoid mangling tokens.
    if student_name:
        for part in student_name.split():
            if len(part) <= 2 or part.lower() in _RESERVED_TOKEN_WORDS:
                continue
            if part.lower() in _COMMON_WORD_NAMES:
                sanitized = re.sub(
                    rf'\b(?:{re.escape(part.capitalize())}|{re.escape(part.upper())})\b',
                    '[STUDENT]', sanitized,
                )
            else:
                sanitized = re.sub(
                    rf'\b{re.escape(part)}\b', '[STUDENT]', sanitized, flags=re.IGNORECASE
                )

    return sanitized


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


def log_pii_sanitization(student_name: str, original_len: int, sanitized_len: int, removals: dict):
    """
    Log PII sanitization actions for audit purposes.
    Does not log actual PII - only counts and types of removals.
    """
    # This could be extended to write to an audit log file
    if any(removals.values()):
        _logger.info(f"  🔒 PII sanitized for student submission (removed: {', '.join(k for k, v in removals.items() if v > 0)})")
