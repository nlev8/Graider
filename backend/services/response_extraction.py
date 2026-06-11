"""Pure student-response text parsing and extraction. No Flask, no network, no file I/O."""

import logging
import re

_logger = logging.getLogger(__name__)


def is_question_or_prompt(text: str) -> bool:
    """
    Check if text looks like a question or instruction prompt rather than a student response.
    Returns True if the text should NOT be treated as a student response.

    Uses a SCORING approach with positive signals (instruction-like) and negative signals
    (student-content-like) so it generalizes to any assignment without needing specific keywords.
    """
    if not text or not text.strip():
        return True  # Empty is not a valid response

    text = text.strip()
    text_lower = text.lower()

    # === QUICK CHECKS ===

    # Ends with question mark → question
    if text.rstrip().endswith('?'):
        # But if there's an answer after a question mark on the same line, it's a response
        # e.g., "What year? 1803"
        if '?' in text:
            after_q = text.split('?', 1)[1].strip()
            if after_q and len(after_q) > 2:
                return False
        return True

    # Just a number with period/paren (bare question number)
    if re.match(r'^\d+[\.\)]\s*$', text_lower):
        return True

    # Numbered question format: "1. What was...", "2) Why did..."
    # These are almost certainly assignment prompts, even without a trailing ?
    # and even with history counter-signals (past tense verbs, proper nouns).
    if re.match(r'^\d+[\.\)]\s*(what|why|how|who|when|where|which)\b', text_lower):
        return True

    # === SCORING-BASED DETECTION ===
    # Positive score = instruction/prompt, Negative score = student response
    score = 0

    # Strip leading numbered prefix for pattern matching.
    # "1. Why was..." and "2) Explain..." should be detected the same as
    # "Why was..." and "Explain..." — the number prefix is just formatting.
    text_for_patterns = re.sub(r'^\d+[\.\)]\s*', '', text_lower).strip()

    # Strip common label prefixes that appear before imperative verbs.
    # "Student Task: Explain..." → "Explain..." so the imperative is detected.
    # "Activity: Write..." → "Write..."
    text_for_patterns = re.sub(
        r'^(student\s+task|task|activity|direction[s]?|instruction[s]?|prompt|'
        r'your\s+task|challenge|exercise|practice|assessment)\s*[:.\-–—]\s*',
        '', text_for_patterns
    ).strip()

    # --- POSITIVE SIGNALS (instruction-like) ---

    # Signal 1: Starts with imperative verb (the most reliable signal)
    # These are verbs used to give instructions, in base form without a subject
    imperative_starts = re.match(
        r'^(summarize|include|write|explain|describe|identify|compare|analyze|'
        r'discuss|list|define|name|state|create|draw|use|provide|give|think|'
        r'consider|refer|remember|note|evaluate|assess|determine|select|choose|'
        r'complete|answer|fill|circle|underline|highlight|review|read|examine|'
        r'outline|support|justify|predict|infer|contrast|classify|organize|'
        r'paraphrase|restate|cite|mention|address|respond|demonstrate|illustrate|'
        r'show|prove|argue|defend|critique|interpret|apply|connect|relate|'
        r'be sure|make sure|don\'t forget|do not forget)\b',
        text_for_patterns
    )
    if imperative_starts:
        score += 3

    # Signal 2: Starts with question word (what/how/why/etc.)
    question_start = re.match(
        r'^(what|how|why|when|where|who|which)\b', text_for_patterns
    )
    if question_start:
        # Question words WITHOUT ? and long text are often student statements
        # "How they resolved the issue was by..." is a student response
        if '?' not in text and len(text) > 40:
            score -= 1  # Likely a student statement
        else:
            score += 3  # Likely a question prompt

    # Signal 3: Contains quantifier/requirement language
    # "in 3-4 sentences", "at least 2 examples", "a 5-paragraph essay"
    if re.search(r'\d+[\-–]\d+\s*(sentences?|words?|paragraphs?|examples?|reasons?|points?)', text_lower):
        score += 3
    if re.search(r'at least\s+\d+', text_lower):
        score += 2

    # Signal 4: Contains assignment meta-language (addresses the student about the task)
    meta_phrases = (
        'your answer', 'your response', 'your own words', 'your summary',
        'the text', 'the reading', 'the passage', 'the chapter', 'the article',
        'the space below', 'the lines below', 'the box below',
        'from the reading', 'from the text', 'from the passage',
        'using evidence', 'using details', 'using examples', 'using information',
        'based on the', 'refer to the', 'according to the',
        'key reasons', 'key points', 'key events', 'key figures', 'key details',
        'main ideas', 'main causes', 'main points', 'main events',
        'supporting details', 'supporting evidence', 'textual evidence',
    )
    meta_count = sum(1 for phrase in meta_phrases if phrase in text_lower)
    score += min(meta_count * 2, 4)  # Cap at +4

    # Signal 5: Short text (< 100 chars) starting with imperative = very likely instruction
    if imperative_starts and len(text) < 100:
        score += 1

    # Signal 6: Contains "you" / "your" addressing the student
    if re.search(r'\byou(r)?\b', text_lower):
        score += 1

    # Signal 7: Instruction structure patterns
    if re.match(r'^(in\s+\d+|after\s+reading|before\s+reading|based\s+on|using\s+the)\b', text_for_patterns):
        score += 3

    # --- NEGATIVE SIGNALS (student-response-like) ---
    # NOTE: When text starts with an imperative verb, past-tense content and proper
    # nouns are the SUBJECT of the instruction (e.g., "Explain why Americans moved
    # westward"), not student narrative writing. Penalties are reduced accordingly.

    # Counter 1: Contains specific historical dates (1700s-2000s)
    year_matches = re.findall(r'\b(1[5-9]\d{2}|20\d{2})\b', text)
    if year_matches:
        score -= 1 if imperative_starts else 2

    # Counter 2: Past tense narrative verbs (student writing about events)
    past_verbs = re.findall(
        r'\b(was|were|had|did|led|fought|signed|began|ended|caused|resulted|'
        r'believed|wanted|decided|became|created|established|passed|declared|'
        r'invaded|conquered|defeated|surrendered|negotiated|agreed|refused|'
        r'moved|settled|built|discovered|explored|traveled|arrived|died|killed|'
        r'escaped|captured|freed|enslaved|governed|ruled|elected|appointed)\b',
        text_lower
    )
    if imperative_starts:
        # Imperative + past tense = instruction about historical content, mild penalty only
        if len(past_verbs) >= 3:
            score -= 1
    else:
        if len(past_verbs) >= 2:
            score -= 3
        elif len(past_verbs) == 1:
            score -= 1

    # Counter 3: Proper nouns mid-sentence (names of people, places, events)
    # Only a strong signal when combined with past tense verbs (narrative writing)
    # Instructions can also mention proper nouns ("Describe the impact on Native Americans")
    words = text.split()
    if len(words) > 3:
        proper_nouns = sum(1 for w in words[1:] if w[0:1].isupper() and not w.isupper()
                          and w not in ('I', 'I\'m', 'I\'ll', 'I\'ve', 'I\'d'))
        if imperative_starts:
            pass  # Don't penalize — instructions naturally reference proper nouns
        elif proper_nouns >= 2 and len(past_verbs) >= 1:
            score -= 2  # Proper nouns + past tense = strong student response signal
        elif proper_nouns >= 3:
            score -= 1  # Many proper nouns without imperative start

    # Counter 4: Contains because/since/therefore (reasoning = student work)
    if re.search(r'\b(because|since|therefore|however|although|furthermore|moreover|consequently)\b', text_lower):
        # "Explain why X because..." is unusual for prompts, but
        # "Explain because..." doesn't happen — the conjunction follows the subject
        score -= 1 if imperative_starts else 2

    # Counter 5: Long text (>150 chars) with no meta-language is likely student content
    if len(text) > 150 and meta_count == 0 and not imperative_starts:
        score -= 2

    # Counter 6: Definition patterns ("X means...", "X is defined as...", "X refers to...")
    if re.search(r'\b(means|is defined as|refers to|is when|is the|is a |are the|are a )\b', text_lower):
        # "Explain what X meant to them" has "meant" which is different from "means"
        score -= 1 if imperative_starts else 2

    # === DECISION ===
    # score >= 3 means instruction/prompt
    return score >= 3


def filter_questions_from_response(response_text: str) -> str:
    """
    Filter out question/prompt text from a response, keeping only actual answers.

    For example:
    Input: "What year was the Louisiana Purchase? 1803"
    Output: "1803"

    Input: "How did slavery affect daily life?"
    Output: "" (blank - student didn't answer)
    """
    if not response_text:
        return ""

    lines = response_text.strip().split('\n')
    filtered_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip quoted text — primary source quotes from the template, not student writing.
        # Matches lines wrapped in any style of quotation marks (straight or smart).
        stripped_for_quote = line.strip()
        if ((stripped_for_quote.startswith('"') and stripped_for_quote.endswith('"'))
            or (stripped_for_quote.startswith('\u201c') and stripped_for_quote.endswith('\u201d'))
            or (stripped_for_quote.startswith('"') and stripped_for_quote.endswith('\u201d'))
            or (stripped_for_quote.startswith('\u201c') and stripped_for_quote.endswith('"'))):
            continue

        # Skip "Quote from [Person]:" attribution lines
        if re.match(r'^(?:quote|excerpt|passage)\s+(?:from|by)\s+', line, re.IGNORECASE):
            continue

        # If line contains ?, check if there's an answer after it
        if '?' in line:
            parts = line.split('?')
            # Get everything after the last question mark
            after_question = parts[-1].strip() if len(parts) > 1 else ''
            if after_question and len(after_question) > 2 and not is_question_or_prompt(after_question):
                filtered_lines.append(after_question)
        elif not is_question_or_prompt(line):
            # Line passed as non-prompt, but check if it starts with a prompt sentence
            # concatenated with the student answer (e.g., "Explain why X. The answer is Y.")
            period_pos = line.find('.')
            if period_pos != -1 and period_pos < len(line) - 10:
                before_period = line[:period_pos + 1].strip()
                if len(before_period) > 15 and is_question_or_prompt(before_period):
                    after_period = line[period_pos + 1:].strip()
                    if after_period and len(after_period) > 5:
                        filtered_lines.append(after_period)
                    # else: only the prompt, no student content — skip entirely
                else:
                    filtered_lines.append(line)
            else:
                filtered_lines.append(line)
        else:
            # Line IS a prompt/instruction — but check if student content follows
            # the instruction on the same line (after a period)
            line_lower = line.lower()
            period_pos = line.find('.')
            if period_pos != -1 and period_pos < len(line) - 5:
                after_period = line[period_pos + 1:].strip()
                if after_period and len(after_period) > 10 and not is_question_or_prompt(after_period):
                    filtered_lines.append(after_period)

    return '\n'.join(filtered_lines).strip()


def _strip_template_lines(response: str, marker_text: str, template_text: str, is_short_answer: bool = False) -> str:
    """Remove template/prompt lines from extracted response by comparing with template.

    After the marker heading (e.g., 'SUMMARY'), the template may contain instruction
    text like 'Summarize the key events in 4-5 sentences.' which appears in the student
    doc but is NOT student work. This function strips those template lines.
    """
    if not template_text or not response:
        return response

    # Find the marker section in the template
    marker_lower = marker_text.lower().strip()
    template_lower = template_text.lower()
    marker_pos = template_lower.find(marker_lower)
    if marker_pos == -1:
        return response

    # Extract template content after this marker
    template_after = template_text[marker_pos + len(marker_text):]
    # Stop at the next likely section marker (all-caps word on its own line)
    template_section_lines = []
    for line in template_after.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        # Stop if we hit another section marker (all-caps word, 3+ chars)
        if stripped.isupper() and len(stripped) >= 3 and stripped.isalpha():
            break
        template_section_lines.append(stripped)

    if not template_section_lines:
        return response

    # Build set of normalized template lines (lowered, stripped of underscores/whitespace)
    template_line_set = set()
    template_word_sets = []  # For fuzzy matching
    for tl in template_section_lines:
        cleaned = re.sub(r'[_\s]+', ' ', tl).strip().lower()
        if len(cleaned) >= 10:  # Only match substantial lines
            template_line_set.add(cleaned)
            # Also store word sets for fuzzy overlap matching
            words = set(re.findall(r'[a-z]{3,}', cleaned))
            if len(words) >= 3:
                template_word_sets.append(words)

    # Filter response lines: remove template text, preserving student answers
    # that may appear on the same line after a template prompt
    response_lines = response.split('\n')
    filtered = []
    for line in response_lines:
        line_cleaned = re.sub(r'[_\s]+', ' ', line).strip().lower()
        is_template = False
        partial_strip = None  # Student content remaining after template prefix

        # Exact / substring match
        for tl in template_line_set:
            if line_cleaned == tl or (len(line_cleaned) >= 15 and line_cleaned in tl):
                # Whole line is template or line is inside a longer template line
                is_template = True
                break
            if len(tl) >= 15 and tl in line_cleaned:
                # Template text is a prefix/substring of this line — the student
                # may have typed their answer on the same line after the prompt.
                # Strip the template portion and keep the rest.
                tl_pos = line_cleaned.find(tl)
                remainder = line_cleaned[tl_pos + len(tl):].strip()
                # Only keep if there's meaningful student content after the template
                min_remainder = 2 if is_short_answer else 10
                if len(remainder) >= min_remainder:
                    # Find the same position in the original (non-lowered) line
                    orig_cleaned = re.sub(r'[_\s]+', ' ', line).strip()
                    partial_strip = orig_cleaned[tl_pos + len(tl):].strip()
                else:
                    is_template = True
                break

        # Fuzzy match: high word overlap with any template line (catches rephrased prompts)
        if not is_template and partial_strip is None and len(line_cleaned) >= 15:
            line_words = set(re.findall(r'[a-z]{3,}', line_cleaned))
            if len(line_words) >= 3:
                for tw_set in template_word_sets:
                    overlap = len(line_words & tw_set)
                    # If 60%+ of the response line's words appear in a template line,
                    # it's likely template text (possibly reworded)
                    if overlap >= max(3, len(line_words) * 0.6):
                        is_template = True
                        break

        if partial_strip is not None:
            filtered.append(partial_strip)
        elif not is_template:
            filtered.append(line)

    result = '\n'.join(filtered).strip()
    if result != response.strip():
        stripped_count = len(response_lines) - len(filtered)
        print(f"      🧹 Stripped {stripped_count} template line(s) from {marker_text[:30]} response")  # noqa: T201
    return result


def strip_emojis(text: str) -> str:
    """Remove emojis and special unicode characters from text."""
    import re
    # Remove emojis (unicode ranges for emojis)
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F700-\U0001F77F"  # alchemical symbols
        u"\U0001F780-\U0001F7FF"  # Geometric Shapes
        u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        u"\U0001FA00-\U0001FA6F"  # Chess Symbols
        u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        u"\U00002702-\U000027B0"  # Dingbats
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub('', text).strip()


def fuzzy_find_marker(doc_text: str, marker: str, threshold: float = 0.7) -> int:
    """
    Find a marker in document using fuzzy matching.
    Handles cases where students slightly edit formatting.

    Returns position if found with confidence >= threshold, else -1.
    Processing time: ~1-2ms per marker.
    """
    doc_lower = doc_text.lower()
    marker_lower = marker.lower().strip()

    # First try exact match
    exact_pos = doc_lower.find(marker_lower)
    if exact_pos != -1:
        return exact_pos

    # Try matching with emojis stripped from both sides
    marker_no_emoji = strip_emojis(marker_lower)
    doc_no_emoji = strip_emojis(doc_lower)
    if marker_no_emoji:
        emoji_pos = doc_no_emoji.find(marker_no_emoji)
        if emoji_pos != -1:
            # Find the actual position in original doc by searching near this location
            # Account for removed emojis by doing a fuzzy position find
            search_start = max(0, emoji_pos - 20)
            search_chunk = doc_lower[search_start:search_start + len(marker_lower) + 50]
            actual_pos = search_chunk.find(marker_no_emoji)
            if actual_pos != -1:
                return search_start + actual_pos
            return emoji_pos  # Fallback to stripped position

    # Try matching without extra whitespace/punctuation
    marker_normalized = ' '.join(marker_lower.split())  # Collapse whitespace
    marker_words = marker_normalized.split()

    # For single-word markers (like "Summary", "Vocabulary"), try word boundary search
    if len(marker_words) == 1:
        # Look for the word with word boundaries
        pattern = r'\b' + re.escape(marker_words[0]) + r'\b'
        match = re.search(pattern, doc_lower)
        if match:
            return match.start()
        # Also try with emoji-stripped doc
        match = re.search(pattern, doc_no_emoji)
        if match:
            return match.start()
        return -1

    # Try finding first 3-4 significant words (skip common words)
    skip_words = {'the', 'a', 'an', 'of', 'to', 'in', 'for', 'on', 'with', 'is', 'are'}
    sig_words = [w for w in marker_words if w not in skip_words and len(w) > 2][:4]

    if len(sig_words) >= 2:
        # Build a pattern: first word.*second word.*third word (with flexibility)
        pattern_parts = [re.escape(w) for w in sig_words]
        pattern = r'.{0,20}'.join(pattern_parts)

        try:
            match = re.search(pattern, doc_lower)
            if match:
                return match.start()
        except re.error as e:
            _logger.debug("Marker significant-words pattern failed to compile: %s", e)

    # Try first significant phrase (first 5 words)
    first_phrase = ' '.join(marker_words[:5])
    # Allow for inserted spaces/chars
    flexible_pattern = r'\s*'.join([re.escape(c) for c in first_phrase if c.strip()])
    try:
        match = re.search(flexible_pattern[:100], doc_lower)  # Limit pattern length
        if match:
            return match.start()
    except re.error as e:
        _logger.debug("Marker flexible pattern failed to compile: %s", e)

    return -1


def extract_fitb_by_template_comparison(student_text: str, template_text: str) -> list:
    """
    Extract fill-in-the-blank answers from student submission.

    For FITB assignments, the student's completed text IS the answer.
    This extracts content flexibly - works with:
    - Numbered lines (1., 2., 3.)
    - Lettered lines (a., b., c.)
    - Timestamped lines (1. (0:00) ...)
    - Plain paragraphs
    - Any format where blanks were filled inline

    Returns list of {"question": context, "answer": filled_text, "type": "fill_in_blank"}
    """
    if not student_text:
        return []

    extracted = []
    student_lines = student_text.strip().split('\n')

    # Skip patterns - these are template/header lines, not student answers
    skip_patterns = [
        r'^name\s*[:_]', r'^date\s*[:_]', r'^period\s*[:_]', r'^class\s*[:_]',
        r'^directions?\s*:', r'^instructions?\s*:', r'^fill in', r'^watch the video',
        r'^answer each', r'^complete the', r'^use evidence', r'^_{5,}$'
    ]

    item_number = 0
    for student_line in student_lines:
        student_line = student_line.strip()
        if not student_line or len(student_line) < 10:
            continue

        # Skip header/template lines
        line_lower = student_line.lower()
        if any(re.match(p, line_lower) for p in skip_patterns):
            continue

        # Try to match various formats:
        # 1. Numbered: "1.", "1)", "1:"
        # 2. Lettered: "a.", "a)", "A."
        # 3. With timestamp: "1. (0:00-0:25)"
        # 4. Plain content lines

        content = None
        label = None

        # Numbered with optional timestamp (handle bullet prefixes like •, *, -)
        num_match = re.match(r'^[•\*\-\u2022\u2023\u25E6\u2043\u2219\s]*(\d+)[\.\)\:]\s*(\([^)]+\))?\s*(.+)', student_line)
        if num_match:
            label = f"Item {num_match.group(1)}"
            if num_match.group(2):
                label += f" {num_match.group(2)}"
            content = num_match.group(3).strip()

        # Lettered (handle bullet prefixes)
        if not content:
            letter_match = re.match(r'^[•\*\-\u2022\u2023\u25E6\u2043\u2219\s]*([a-zA-Z])[\.\)\:]\s*(.+)', student_line)
            if letter_match:
                label = f"Item {letter_match.group(1).upper()}"
                content = letter_match.group(2).strip()

        # Plain line with substance (not just a title)
        if not content and len(student_line) > 20:
            # Check if it looks like content (has filled blanks or is a complete sentence)
            if '_' in student_line or student_line.endswith('.') or ',' in student_line:
                item_number += 1
                label = f"Response {item_number}"
                content = student_line

        if content and len(content) >= 10:
            # Don't add if it's just the assignment title
            if 'fill-in-the-blank' in content.lower() or 'activity' in content.lower()[:20]:
                continue

            extracted.append({
                "question": label or f"Response {len(extracted) + 1}",
                "answer": content,
                "type": "fill_in_blank_sentence"
            })

    # Also extract any text wrapped in underscores _answer_ or __answer__
    underscore_matches = re.findall(r'_+([^_\n]{1,80})_+', student_text)
    for match in underscore_matches:
        answer = match.strip()
        if answer and len(answer) > 0:
            # Skip common template words
            if answer.lower() not in ['name', 'date', 'period', 'class', 'blank', 'answer', 'your answer']:
                # Avoid duplicates
                already_exists = any(answer.lower() in e.get('answer', '').lower() for e in extracted)
                if not already_exists:
                    extracted.append({
                        "question": "Fill-in-blank",
                        "answer": answer,
                        "type": "fill_in_blank"
                    })

    return extracted


def parse_numbered_questions(text: str) -> list:
    """
    Parse numbered questions and their answers from a text block.

    Handles formats like:
    - "1. Question text? Answer text"
    - "1. Question text?\n   Answer text"
    - "1) Question text? Answer text"

    Returns list of {"question": "...", "answer": "..."} dicts.
    Returns empty list if no numbered questions found.
    """
    if not text or len(text) < 20:
        return []

    # Pattern to find numbered questions: "1." or "1)" at start of line or after newline
    # Captures: number, question text (up to ?), and everything after until next number
    number_pattern = r'(?:^|\n)\s*(\d+)[.\)]\s*'

    # Find all numbered items
    matches = list(re.finditer(number_pattern, text))

    if len(matches) < 2:
        # Not enough numbered items to indicate a numbered list
        return []

    # Check if numbers are sequential (1, 2, 3, ...)
    numbers = [int(m.group(1)) for m in matches]
    if numbers[0] != 1:
        return []  # Doesn't start with 1

    # Allow some gaps but should be roughly sequential
    is_sequential = all(numbers[i] <= numbers[i-1] + 2 for i in range(1, len(numbers)))
    if not is_sequential:
        return []

    results = []

    for i, match in enumerate(matches):
        q_num = match.group(1)
        q_start = match.end()  # Start of question text

        # Find end of this question's content (start of next number or end of text)
        if i + 1 < len(matches):
            q_end = matches[i + 1].start()
        else:
            q_end = len(text)

        content = text[q_start:q_end].strip()

        if not content:
            results.append({
                "question": f"Question {q_num}",
                "answer": "",
                "is_blank": True
            })
            continue

        # Split into question and answer
        # The question ends at '?' and answer is everything after
        question_mark_pos = content.find('?')

        if question_mark_pos != -1:
            question_text = content[:question_mark_pos + 1].strip()
            answer_text = content[question_mark_pos + 1:].strip()
        else:
            # No question mark - might be a statement or instruction
            # Look for newline as separator
            newline_pos = content.find('\n')
            if newline_pos != -1:
                question_text = content[:newline_pos].strip()
                answer_text = content[newline_pos:].strip()
            else:
                # Single line with no clear separator
                question_text = content
                answer_text = ""

        # Clean up answer - remove leading/trailing whitespace and blank lines
        answer_lines = [line.strip() for line in answer_text.split('\n') if line.strip()]

        answer_text = '\n'.join(answer_lines)

        # If there's any non-empty text after the question, it's an answer.
        # Don't try to second-guess whether it "looks like" a question —
        # content between two numbered items after the ? is the student's response.
        if answer_text and len(answer_text.strip()) > 2:
            results.append({
                "question": f"{q_num}. {question_text}",
                "answer": answer_text,
                "is_blank": False
            })
        else:
            results.append({
                "question": f"{q_num}. {question_text}",
                "answer": "",
                "is_blank": True
            })

    return results


def parse_vocab_terms(text: str) -> list:
    """
    Parse vocabulary Term: definition pairs from a text block.

    Handles formats like:
    - "Assimilate: to adopt the customs of another group"
    - "Indian Removal Act: 1830 law signed by Jackson"
    - "Term: _______________" (blank)
    - "Term:" followed by definition on next line

    Returns list of {"term": "...", "answer": "...", "is_blank": bool} dicts.
    Returns empty list if no vocab terms detected.
    """
    if not text or len(text) < 10:
        return []

    lines = text.strip().split('\n')
    results = []

    # Skip header keywords that aren't vocab terms
    skip_keywords = {'vocabulary', 'questions', 'summary', 'notes', 'section',
                     'directions', 'instructions', 'response', 'name', 'date',
                     'period', 'write your', 'use bullets', 'define the',
                     'in your own words', 'total', 'points'}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line or line.replace('_', '').replace(' ', '').replace('-', '') == '':
            continue

        # Check for "Term: definition" or "Term:" pattern
        if ':' not in line:
            continue

        parts = line.split(':', 1)
        term = parts[0].strip()
        defn = parts[1].strip() if len(parts) > 1 else ''

        # Validate it looks like a vocab term (not a header/instruction)
        if not term or len(term) < 2 or len(term) > 60:
            continue
        if len(term.split()) > 5:
            continue

        term_lower = term.lower()
        if any(kw in term_lower for kw in skip_keywords):
            continue

        # Skip if term starts with a number (likely a numbered question, not vocab)
        if re.match(r'^\d+[\.\)]\s', term):
            continue

        # Check if definition is blank (underscores, empty, dashes)
        defn_clean = re.sub(r'[_\-\s\.]+', '', defn)
        if len(defn_clean) < 3:
            # Check next line(s) for definition
            found_defn = False
            for look in range(i, min(i + 2, len(lines))):
                next_line = lines[look].strip()
                next_clean = re.sub(r'[_\-\s\.]+', '', next_line)
                if next_clean and len(next_clean) >= 3 and ':' not in next_line:
                    # Next line has content without a colon — it's the definition
                    defn = next_line
                    defn_clean = next_clean
                    found_defn = True
                    i = look + 1  # Skip past the definition line
                    break
                elif next_clean and ':' in next_line:
                    break  # Next line is another term — this one is blank

            if not found_defn or len(defn_clean) < 3:
                results.append({"term": term, "answer": "", "is_blank": True})
                continue

        results.append({"term": term, "answer": defn, "is_blank": False})

    # Only return results if we found at least 2 vocab terms (avoid false positives)
    if len(results) < 2:
        return []

    return results

STUDENT_WORK_MARKERS = [
    # Direct task indicators
    "student task",
    "your turn",
    "now you try",
    "student responses below",
    
    # Question indicators
    "answer the question",
    "questions to check understanding",
    "questions / summary",
    
    # Activity types
    "answer the",
    "match",
    "fill-in-the-blank",
    "fill in the blank",
    "write",
    "explain",
    "complete",
    "describe",
    "summarize",
    
    # Analysis & thinking verbs
    "analyze",
    "compare",
    "contrast",
    "evaluate",
    "identify",
    "list",
    "define",
    
    # Application verbs
    "apply",
    "demonstrate",
    "illustrate",
    "predict",
    "solve",
    
    # Creation verbs
    "create",
    "design",
    "develop",
    "construct",
    
    # Reflection indicators
    "final reflection",
    "final reflection question",
    "reflect",
    "think about",
    
    # Learning check indicators
    "let's see what you've learned",
    "lets see what you've learned",
    "let's see what you've learned",  # curly apostrophe version
    "check your understanding",
    "show what you know",
    "practice",
]


def _build_marker_positions(custom_markers, document_text, doc_lower,
                            doc_lower_normalized, normalize_for_search):
    """Locate each custom marker in the document (exact / first-line /
    fuzzy strategies) and return (marker_positions, exact_matches,
    fuzzy_matches). Extracted verbatim from extract_student_responses (CQ7).
    """
    marker_positions = []
    exact_matches = 0
    fuzzy_matches = 0

    for marker in custom_markers:
        # Handle both string and object markers
        if isinstance(marker, dict):
            marker_clean = marker.get('start', '').strip()
            end_marker = marker.get('end', '').strip()
        else:
            marker_clean = str(marker).strip()
            end_marker = None

        if not marker_clean:
            continue

        # Split marker into lines for multi-line matching strategies
        marker_lines = [l.strip() for l in marker_clean.split('\n') if l.strip()]
        first_line = marker_lines[0] if marker_lines else marker_clean
        marker_lower = marker_clean.lower()

        pos = -1
        match_type = None
        content_end_pos = -1  # Where content actually starts (after all marker/prompt lines)

        # Strategy 1: Full exact match (ideal — whole multi-line marker found as-is)
        # Prefer line-start matches to avoid substring hits (e.g., "NOTES" in "CORNELL NOTES")
        # A "line-start" match means the marker is at position 0, or preceded by a newline
        # (possibly with emoji/whitespace between the newline and the marker text).
        pos = -1
        search_start = 0
        while True:
            candidate = doc_lower.find(marker_lower, search_start)
            if candidate == -1:
                break
            # Check if this is a standalone section header (at line start)
            is_line_start = (candidate == 0)
            if not is_line_start and candidate > 0:
                # Look back from candidate to the previous newline — if only
                # whitespace/emoji/special chars between newline and marker, it's line-start
                lookback = doc_lower[max(0, candidate - 10):candidate]
                newline_pos = lookback.rfind('\n')
                if newline_pos != -1:
                    between = lookback[newline_pos + 1:]
                    # Only whitespace, emoji, or common prefix chars (star, bullet, dash)
                    is_line_start = all(
                        c in ' \t\u2b50\U0001f31f\U0001f4d3\U0001f4dd\U0001f331\U0001f4d6\U0001f4da\U0001f50d\u2022\u2013\u2014-*'
                        or ord(c) > 0x2600  # emoji/symbol unicode ranges
                        for c in between
                    )
            if is_line_start:
                pos = candidate
                break
            # Otherwise keep searching for a line-start match
            if pos == -1:
                pos = candidate  # fallback to first occurrence if no line-start match
            search_start = candidate + 1
        if pos != -1:
            match_type = 'exact'
            content_end_pos = pos + len(marker_clean)

        # Strategy 2: First-line exact match + forward scan for subsequent lines
        if pos == -1:
            first_line_lower = first_line.lower()
            matched_len = len(first_line)  # Track actual matched text length

            # Try with original text
            pos = doc_lower.find(first_line_lower)

            # Try with normalized dashes/quotes
            if pos == -1:
                first_normalized = normalize_for_search(first_line_lower)
                pos = doc_lower_normalized.find(first_normalized)

            # Try without emojis (matched_len changes since emoji chars aren't in doc)
            if pos == -1:
                first_no_emoji = strip_emojis(first_line_lower).strip()
                if first_no_emoji and len(first_no_emoji) >= 3:
                    pos = doc_lower.find(first_no_emoji)
                    if pos == -1:
                        # Try normalized + emoji-stripped
                        pos = doc_lower_normalized.find(normalize_for_search(first_no_emoji))
                    if pos != -1:
                        matched_len = len(first_no_emoji)  # Use stripped length

            if pos != -1:
                match_type = 'first_line'
                # Find the actual end of the heading line in the document
                heading_newline = doc_lower.find('\n', pos)
                if heading_newline != -1 and heading_newline < pos + matched_len + 50:
                    content_end_pos = heading_newline + 1  # Start of next line
                else:
                    content_end_pos = pos + matched_len

                # Scan forward for instruction/prompt lines that come RIGHT AFTER
                # the heading — skip past them so content starts at student answers.
                # STOP scanning at numbered questions (1., 2.) since those contain
                # individual Q&A pairs that parse_numbered_questions will handle.
                if len(marker_lines) > 1:
                    last_advance = content_end_pos
                    search_to = min(last_advance + len(marker_clean) + 500, len(doc_lower))

                    for mline in marker_lines[1:]:
                        mline_lower = mline.lower().strip()

                        # Stop at numbered questions — don't skip past them
                        if re.match(r'^\d+[\.\)]\s', mline_lower):
                            break

                        mline_normalized = normalize_for_search(mline_lower)

                        # Try finding this line near the current position
                        line_pos = doc_lower.find(mline_lower, last_advance, search_to)
                        if line_pos == -1:
                            line_pos = doc_lower_normalized.find(mline_normalized, last_advance, search_to)
                        if line_pos == -1:
                            mline_no_emoji = strip_emojis(mline_lower).strip()
                            if mline_no_emoji and len(mline_no_emoji) >= 5:
                                line_pos = doc_lower.find(mline_no_emoji, last_advance, search_to)
                        if line_pos == -1:
                            # Try first few words (handles table | format)
                            mline_words = mline_lower.split()[:3]
                            if len(mline_words) >= 2:
                                short_search = ' '.join(mline_words)
                                if len(short_search) >= 5:
                                    line_pos = doc_lower.find(short_search, last_advance, search_to)

                        if line_pos != -1:
                            # Only advance if this line is CLOSE (no big gap with student content)
                            if line_pos - last_advance > 200:
                                break  # Gap too large — student content in between
                            newline_after = doc_lower.find('\n', line_pos)
                            if newline_after != -1 and newline_after < search_to:
                                content_end_pos = max(content_end_pos, newline_after + 1)
                                last_advance = newline_after + 1
                            else:
                                content_end_pos = max(content_end_pos, line_pos + len(mline_lower))
                                last_advance = content_end_pos
                        else:
                            break  # Line not found — stop scanning

        # Strategy 3: Fuzzy match (fallback)
        if pos == -1:
            pos = fuzzy_find_marker(document_text, marker_clean)
            if pos != -1:
                match_type = 'fuzzy'
                content_end_pos = pos + min(len(marker_clean), 100)

        if pos != -1:
            if match_type == 'exact':
                exact_matches += 1
            elif match_type == 'first_line':
                exact_matches += 1  # First-line is reliable enough to count as exact
            else:
                fuzzy_matches += 1

            marker_positions.append({
                'marker': marker_clean,
                'start': pos,
                'end': content_end_pos,
                'end_marker': end_marker,
                'match_type': match_type,
                'section_type': marker.get('type', 'written') if isinstance(marker, dict) else 'written',
            })

    return marker_positions, exact_matches, fuzzy_matches


def _determine_marker_content_end(i, marker_positions, content_start, end_marker,
                                  document_text, doc_lower, doc_lower_normalized,
                                  exclude_markers_normalized):
    """Compute where a marker section's content ends (explicit end marker /
    next marker / section delimiters / exclude boundaries). Extracted
    verbatim from the per-marker loop of extract_student_responses (CQ7).
    """
    # Determine where content ends (in priority order):
    # 1. Explicit end marker (if defined)
    # 2. Next start marker
    # 3. Section delimiters
    # 4. Document end (capped at 1500 chars)

    if end_marker:
        # Use explicit end marker with fallback for suspiciously short content
        MIN_CONTENT_LENGTH = 50  # If content is shorter, end marker may have been found too early

        end_pos = doc_lower.find(end_marker.lower(), content_start)
        if end_pos != -1:
            # Check if content is suspiciously short
            potential_content = document_text[content_start:end_pos].strip()

            # If too short, look for NEXT occurrence of end marker
            search_pos = end_pos + 1
            while len(potential_content) < MIN_CONTENT_LENGTH and search_pos < len(document_text):
                next_end_pos = doc_lower.find(end_marker.lower(), search_pos)
                if next_end_pos == -1:
                    break  # No more occurrences
                potential_content = document_text[content_start:next_end_pos].strip()
                if len(potential_content) >= MIN_CONTENT_LENGTH:
                    end_pos = next_end_pos
                    break
                search_pos = next_end_pos + 1

            content_end = end_pos
        else:
            # End marker not found, fall back to next marker or cap
            if i + 1 < len(marker_positions):
                content_end = marker_positions[i + 1]['start']
            else:
                content_end = min(content_start + 1500, len(document_text))
    elif i + 1 < len(marker_positions):
        # End at next marker
        content_end = marker_positions[i + 1]['start']
    else:
        # Last marker - cap at 1500 chars
        content_end = min(content_start + 1500, len(document_text))

    # Also stop at known section delimiters (reading material, etc.)
    # BUT skip this if we already have an explicit end marker (to avoid re-truncating)
    # NOTE: Removed '___' from delimiters - it conflicts with fill-in-the-blank notation
    if not end_marker:
        section_delimiters = ['📖', '📚', '🔍', '--- ', '***', '===']
        for delim in section_delimiters:
            delim_pos = document_text.find(delim, content_start, content_end)
            if delim_pos != -1 and delim_pos > content_start:
                content_end = delim_pos

    # Also stop at exclude marker boundaries — don't capture excluded
    # section content as part of an adjacent graded section's response
    if exclude_markers_normalized:
        for em in exclude_markers_normalized:
            # Try multiple search strategies (emoji/dash/encoding differences)
            em_lines = [l.strip() for l in em.split('\n') if l.strip()]
            search_terms = set()
            for el in em_lines[:3]:  # First 3 lines
                search_terms.add(el)
                # Without leading emoji/special chars
                stripped = re.sub(r'^[^a-zA-Z]*', '', el).strip()
                if stripped and len(stripped) >= 5:
                    search_terms.add(stripped)
                # Normalized dashes/quotes
                normalized = el.replace('\u2013', '-').replace('\u2014', '-').replace('\u2018', "'").replace('\u2019', "'")
                if normalized != el:
                    search_terms.add(normalized)

            found_boundary = False
            for em_search in search_terms:
                if len(em_search) >= 5 and not found_boundary:
                    em_pos = doc_lower.find(em_search, content_start, content_end)
                    if em_pos == -1:
                        # Also try in normalized doc text
                        em_pos = doc_lower_normalized.find(em_search, content_start, content_end)
                    if em_pos != -1 and em_pos > content_start:
                        content_end = min(content_end, em_pos)
                        found_boundary = True

    return content_end


def _extract_responses_per_marker(marker_positions, custom_markers, template_text,
                                  document_text, doc_lower, doc_lower_normalized,
                                  exclude_markers_normalized, extracted,
                                  blank_questions, excluded_sections):
    """Walk the located markers and append student responses to ``extracted``
    (and blanks to ``blank_questions``, skips to ``excluded_sections``),
    mutating those lists in place. Extracted verbatim from
    extract_student_responses (CQ7); the content-end computation is delegated
    to _determine_marker_content_end.
    """
    # Extract response after each marker
    for i, mp in enumerate(marker_positions):
        marker_text = mp['marker']
        content_start = mp['end']
        end_marker = mp.get('end_marker')
        section_type = mp.get('section_type', 'written')
        # Detect short-answer from explicit type OR from marker name containing FITB keywords
        marker_name_hint = mp['marker'].lower()
        is_short_answer = (
            section_type in ('fill-blank', 'fill_in_blank', 'vocabulary', 'matching')
            or 'fill-in' in marker_name_hint
            or 'fill in' in marker_name_hint
            or 'fitb' in marker_name_hint
            or 'blanks' in marker_name_hint
        )

        # Check if this marker should be excluded from grading
        marker_lower = marker_text.lower().strip()
        marker_first_line = marker_lower.split('\n')[0].strip()
        marker_first_no_emoji = strip_emojis(marker_first_line).strip()
        is_excluded = False
        for em in exclude_markers_normalized:
            em_first_line = em.split('\n')[0].strip()
            em_first_no_emoji = strip_emojis(em_first_line).strip()
            # Compare full text, first lines, and emoji-stripped first lines
            if (em in marker_lower or marker_lower in em
                or em_first_line in marker_first_line or marker_first_line in em_first_line
                or (em_first_no_emoji and marker_first_no_emoji
                    and (em_first_no_emoji in marker_first_no_emoji or marker_first_no_emoji in em_first_no_emoji))):
                is_excluded = True
                excluded_sections.append(marker_text[:80])
                break

        if is_excluded:
            continue  # Skip this section - don't grade it

        content_end = _determine_marker_content_end(
            i, marker_positions, content_start, end_marker, document_text,
            doc_lower, doc_lower_normalized, exclude_markers_normalized)

        # Extract the response
        response = document_text[content_start:content_end].strip()

        # Clean up: remove leading colons, newlines
        response = re.sub(r'^[:\s\n]+', '', response).strip()

        # Check if response contains numbered questions (1., 2., 3., etc.)
        # If so, parse them individually instead of as one blob
        numbered_items = parse_numbered_questions(response)
        if numbered_items:
            print(f"      📝 Found {len(numbered_items)} numbered questions in section")  # noqa: T201
            for item in numbered_items:
                answer = item.get("answer", "")

                # Clean template artifacts from numbered question answers:
                # "(25 pts)", "Response: ___", "_____" lines are template text, not student content
                if answer:
                    cleaned_lines = []
                    for aline in answer.split('\n'):
                        stripped = aline.strip()
                        # Skip point value markers like "(20 pts)" or "(25 pts)"
                        if re.match(r'^\(\s*\d+\s*(?:pts?|points?)\s*\)\s*$', stripped, re.IGNORECASE):
                            continue
                        # Skip "Response:" with only underscores after it
                        if re.match(r'^Response\s*:\s*[_\s]*$', stripped, re.IGNORECASE):
                            continue
                        # Skip lines that are only underscores/dashes/spaces
                        if re.match(r'^[_\-\s]+$', stripped) or not stripped:
                            continue
                        # Skip "Response:" prefix but keep any actual text after it
                        resp_match = re.match(r'^Response\s*:\s*(.+)', stripped, re.IGNORECASE)
                        if resp_match:
                            actual = resp_match.group(1).strip()
                            if actual and not re.match(r'^[_\-\s]+$', actual):
                                cleaned_lines.append(actual)
                            continue
                        cleaned_lines.append(stripped)
                    answer = '\n'.join(cleaned_lines).strip()

                if not answer or len(answer) < 3:
                    blank_questions.append(item.get("question", "Unknown"))
                else:
                    extracted.append({
                        "question": item["question"],
                        "answer": answer[:10000],
                        "type": "numbered_question"
                    })
            continue  # Skip normal processing for this marker

        # Check if this is a VOCABULARY section with Term: definition pairs
        # Parse each vocab term individually for better grading granularity
        marker_name_lower = marker_text.lower().split('\n')[0].strip()
        is_vocab_section = 'vocab' in marker_name_lower
        if is_vocab_section:
            vocab_items = parse_vocab_terms(response)
            if vocab_items:
                print(f"      📖 Found {len(vocab_items)} vocab terms in section")  # noqa: T201
                for vitem in vocab_items:
                    if vitem.get("is_blank"):
                        blank_questions.append(vitem["term"] + " (no definition)")
                    else:
                        extracted.append({
                            "question": vitem["term"],
                            "answer": vitem["answer"][:10000],
                            "type": "vocab_term"
                        })
                continue  # Skip normal blob processing

        # Get a short label for the question (first 50 chars of marker)
        question_label = marker_text[:80] + '...' if len(marker_text) > 80 else marker_text
        # Clean up newlines in label
        question_label = ' '.join(question_label.split())

        # Check if response is actually blank (just whitespace, or only template/boilerplate)
        is_blank = False
        if not response or len(response) <= 5:
            is_blank = True
        else:
            # Filter out common template patterns that aren't student answers
            response_clean = response.strip()

            # Remove lines that start with instructions/prompts
            lines = [l.strip() for l in response_clean.split('\n') if l.strip()]
            # Filter out blank placeholder lines, track blank vocab terms
            student_lines = []
            for line in lines:
                # Skip lines that are just underscores/spaces (blank placeholders)
                if line.replace('_', '').replace(' ', '') == '':
                    continue
                # Skip quoted text — primary source quotes from the template
                stripped_q = line.strip()
                if ((stripped_q.startswith('"') and stripped_q.endswith('"'))
                    or (stripped_q.startswith('\u201c') and stripped_q.endswith('\u201d'))
                    or (stripped_q.startswith('"') and stripped_q.endswith('\u201d'))
                    or (stripped_q.startswith('\u201c') and stripped_q.endswith('"'))):
                    continue
                # Skip "Quote from [Person]:" attribution lines
                if re.match(r'^(?:quote|excerpt|passage)\s+(?:from|by)\s+', line, re.IGNORECASE):
                    continue
                # Skip "Student Task:" / "Task:" instruction lines
                if re.match(r'^(?:student\s+task|task|activity|directions?|instructions?)\s*:', line, re.IGNORECASE):
                    continue
                # Check if line has 3+ consecutive underscores (fill-in-the-blank format)
                if re.search(r'_{3,}', line):
                    # Strip all underscores — if meaningful text remains, keep it
                    text_only = re.sub(r'_+', ' ', line).strip()
                    # Remove the term/label before colon too for checking
                    if ':' in text_only:
                        after_colon = text_only.split(':', 1)[1].strip()
                    else:
                        after_colon = text_only
                    min_answer_len = 1 if is_short_answer else 3
                    if len(after_colon) < min_answer_len:
                        # Truly blank — if it looks like a vocab term (Term: ___), track it
                        if ':' in text_only:
                            term = text_only.split(':', 1)[0].strip()
                            if term and len(term.split()) <= 4:
                                blank_questions.append(f"{term} (no definition)")
                        continue
                    # Otherwise student wrote something between/around the underscores — keep it
                student_lines.append(line)

            # If no student content remains, it's blank
            min_content_len = 3 if is_short_answer else 10
            if not student_lines or sum(len(l) for l in student_lines) < min_content_len:
                is_blank = True
            else:
                # Use filtered response
                response = '\n'.join(student_lines)

        # CRITICAL: Strip template lines from response using original template.
        # This removes instruction/prompt text that appears between the marker
        # heading and the student's actual response (e.g., "Summarize the key events...")
        # SKIP when:
        #   - FITB sections: template lines ARE the questions
        #   - Teacher explicitly set custom markers: the aggressive 60% word-overlap
        #     heuristic in _strip_template_lines incorrectly strips valid student
        #     answers for formats like Cornell Notes where answers share vocabulary
        #     with the template (history content, proper nouns, etc.)
        using_teacher_markers = bool(custom_markers and len(custom_markers) > 0)
        if not is_blank and template_text and not is_short_answer and not using_teacher_markers:
            response = _strip_template_lines(response, marker_text, template_text, is_short_answer=is_short_answer)

        # CRITICAL: Filter out questions/prompts from response.
        # This correctly removes lines ending with '?' and imperative instructions.
        # KEEP active even with custom markers — questions embedded in extracted
        # content (e.g., "Why was the Louisiana Purchase important?") must be
        # removed so they aren't graded as student responses.
        # SKIP only for FITB: the prompts are the fill-in sentences themselves.
        if not is_blank and not is_short_answer:
            pre_filter = response
            response = filter_questions_from_response(response)
            if not response or len(response.strip()) < 3:
                is_blank = True
                print(f"      🔍 filter_questions_from_response made '{question_label[:50]}' blank")  # noqa: T201
                print(f"         Before: {pre_filter[:120].replace(chr(10), ' ')}")  # noqa: T201
                print(f"         After:  [{response}]")  # noqa: T201

        # Additional blank check: if remaining response is very short and looks like
        # template fragments (sub-prompts, topic lists, page refs), mark as blank.
        # Real student answers for questions are typically 20+ characters.
        if not is_blank and response:
            resp_clean = response.strip()
            # Remove common template artifacts: page refs, point values, "Response:" labels
            resp_stripped = re.sub(r'\((?:pp?\.?\s*\d+[\-–]\d+|\d+\s*(?:pts?|points?))\)', '', resp_clean)
            resp_stripped = re.sub(r'(?i)^response\s*:\s*', '', resp_stripped).strip()
            resp_stripped = re.sub(r'[_\-\s]+$', '', resp_stripped).strip()
            min_response_len = 3 if is_short_answer else 15
            if len(resp_stripped) < min_response_len:
                is_blank = True

        if not is_blank:
            # Check for blank vocab terms within this section (Term: with no definition)
            resp_lines = response.split('\n')
            for line_idx, line in enumerate(resp_lines):
                line = line.strip()
                if ':' in line and not line.startswith('http'):
                    parts = line.split(':', 1)
                    term = parts[0].strip()
                    defn = parts[1].strip() if len(parts) > 1 else ''
                    # If term is short (vocab-like) and definition is empty on this line,
                    # check the NEXT line(s) — student may have put the definition there
                    if len(term.split()) <= 3 and not defn:
                        # Look ahead up to 2 lines for a definition
                        has_next_line_content = False
                        for look_ahead in range(1, 3):
                            if line_idx + look_ahead < len(resp_lines):
                                next_line = resp_lines[line_idx + look_ahead].strip()
                                # Skip empty lines and underscore-only lines
                                if next_line and not re.match(r'^[_\s\-\.]+$', next_line) and len(next_line) > 3:
                                    has_next_line_content = True
                                    break
                        if has_next_line_content:
                            continue  # Definition is on the next line — not blank
                        # Don't flag terms that match excluded section keywords
                        term_lower = term.lower()
                        is_from_excluded = any(
                            term_lower in em or em.split('\n')[0].strip().endswith(term_lower)
                            for em in exclude_markers_normalized
                        ) if exclude_markers_normalized else False
                        if not is_from_excluded:
                            blank_questions.append(f"{term} (no definition)")

            extracted.append({
                "question": question_label,
                "answer": response[:10000],
                "type": "marker_response"
            })
        else:
            blank_questions.append(question_label)


def _extract_by_pattern_matching(document_text, extracted, blank_questions):
    """No-marker fallback: numbered-Q&A + fill-in-the-blank pattern matching.
    Appends to ``extracted`` and returns the final result dict. Extracted
    verbatim from extract_student_responses (CQ7).
    """
    lines = document_text.split('\n')

    # Look for numbered questions with answers
    current_question = None
    current_answer_lines = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check for numbered question (1. or 1))
        num_match = re.match(r'^(\d+)[\.\)]\s*(.+)', line_stripped)
        if num_match:
            # Save previous Q&A if exists
            if current_question and current_answer_lines:
                answer = ' '.join(current_answer_lines).strip()
                # Filter out questions/prompts from answer
                answer = filter_questions_from_response(answer)
                if answer and len(answer) > 3:
                    extracted.append({
                        "question": current_question,
                        "answer": answer[:10000],
                        "type": "numbered_qa"
                    })

            # Start new question
            question_text = num_match.group(2).strip()
            # Check if answer is on same line (after ? or :)
            if '?' in question_text:
                parts = question_text.split('?', 1)
                current_question = parts[0].strip() + '?'
                if len(parts) > 1 and parts[1].strip():
                    current_answer_lines = [parts[1].strip()]
                else:
                    current_answer_lines = []
            else:
                current_question = question_text
                current_answer_lines = []
        elif current_question:
            # This might be part of the answer
            current_answer_lines.append(line_stripped)

    # Don't forget last Q&A
    if current_question and current_answer_lines:
        answer = ' '.join(current_answer_lines).strip()
        # Filter out questions/prompts from answer
        answer = filter_questions_from_response(answer)
        if answer and len(answer) > 3:
            extracted.append({
                "question": current_question,
                "answer": answer[:10000],
                "type": "numbered_qa"
            })

    # Fill-in-the-blank pattern 1a: ___answer___ (wrapped in 2+ underscores)
    blank_matches = re.findall(r'_{2,}([^_\n]{1,100})_{2,}', document_text)
    for match in blank_matches:
        answer = match.strip()
        if answer and len(answer) > 0:
            extracted.append({
                "question": "Fill-in-blank",
                "answer": answer,
                "type": "fill_in_blank"
            })

    # Fill-in-the-blank pattern 1b: _answer_ (wrapped in single underscores)
    # Common format: "_Meriwether_ Lewis" or "named _Pomp_"
    single_blank_matches = re.findall(r'(?<![_\w])_([^_\n]{1,80})_(?![_\w])', document_text)
    for match in single_blank_matches:
        answer = match.strip()
        # Filter out likely template placeholders vs actual answers
        if answer and len(answer) > 0 and len(answer) < 60:
            # Skip common template words
            if answer.lower() not in ['name', 'date', 'period', 'class', 'blank', 'answer']:
                extracted.append({
                    "question": "Fill-in-blank",
                    "answer": answer,
                    "type": "fill_in_blank"
                })

    # Fill-in-the-blank pattern 2: Numbered blanks where student replaced underscores
    # e.g., "1. Clark" or "5. Louisiana Purchase" (student replaced _____ with answer)
    for line in lines:
        line_stripped = line.strip()
        # Match numbered items that have short answers (likely FITB)
        num_short = re.match(r'^(\d+)[\.\)]\s*([A-Za-z][^?]{1,60})$', line_stripped)
        if num_short:
            q_num = num_short.group(1)
            answer = num_short.group(2).strip()
            # Skip if it's a question (ends with ?) or instruction
            if answer and not answer.endswith('?') and not any(kw in answer.lower() for kw in ['write', 'explain', 'describe', 'answer', 'complete', 'fill in']):
                # Check if this looks like a student answer (not a question prompt)
                if len(answer) < 50 and not re.match(r'^[_\s\-\.]+$', answer):
                    extracted.append({
                        "question": f"Question {q_num}",
                        "answer": answer,
                        "type": "fill_in_blank"
                    })

    # Fill-in-the-blank pattern 3: Lines with blanks followed by text
    # e.g., "_____ led the expedition" where student wrote "Clark led the expedition"
    # ONLY triggers when underscores are present — prevents false positives on reading passages
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or line_stripped.endswith('?'):
            continue
        # Only match if the line actually contains fill-in-the-blank underscores
        if '___' not in line_stripped:
            continue
        leading_match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Za-z]+){0,2})\s+(.{10,})$', line_stripped)
        if leading_match:
            potential_answer = leading_match.group(1)
            context = leading_match.group(2)
            if '___' in context:
                if not any(kw in potential_answer.lower() for kw in ['name', 'date', 'period', 'class', 'write', 'answer']):
                    extracted.append({
                        "question": f"Fill-in: {context[:40]}...",
                        "answer": potential_answer,
                        "type": "fill_in_blank"
                    })

    total_q = len(extracted) + len(blank_questions)
    return {
        "extracted_responses": extracted,
        "blank_questions": blank_questions,
        "total_questions": max(total_q, 1),
        "answered_questions": len(extracted),
        "extraction_summary": f"Found {len(extracted)} responses via pattern matching."
    }


def extract_student_responses(document_text: str, custom_markers: list = None, exclude_markers: list = None, template_text: str = None) -> dict:
    """
    Extract student responses from document using customMarkers from Builder.

    Args:
        document_text: The student's submitted document text
        custom_markers: List of markers to look for
        exclude_markers: List of markers to exclude from grading
        template_text: Original assignment template (for fill-in-the-blank comparison)

    APPROACH (with fallbacks):
    1. TEMPLATE COMPARISON: If template provided, compare to find filled blanks
    2. EXACT MATCH: Find markers exactly in document
    2. FUZZY MATCH: If exact fails, try fuzzy matching (~1-2ms)
    3. PATTERN MATCH: If all else fails, use regex patterns

    Args:
        document_text: The full document text
        custom_markers: List of marker strings from Builder (the template/prompt text)
        exclude_markers: List of section names to NOT grade (e.g., "Notes Section")

    Returns:
        {
            "extracted_responses": [{"question": "...", "answer": "...", "type": "..."}, ...],
            "blank_questions": ["question text", ...],
            "total_questions": int,
            "answered_questions": int,
            "extraction_summary": "string describing what was found",
            "excluded_sections": ["section name", ...] - sections that were skipped
        }
    """
    import re

    extracted = []
    blank_questions = []
    doc_lower = document_text.lower()

    # Pre-compute normalized doc text (en-dash → hyphen, smart quotes → regular)
    def normalize_for_search(text):
        return text.replace('\u2013', '-').replace('\u2014', '-').replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
    doc_lower_normalized = normalize_for_search(doc_lower)

    # PRIORITY 0: Fill-in-the-blank detection
    # Only trigger FITB if the document/title explicitly mentions fill-in-the-blank
    # Don't trigger just because there are underscores (Cornell Notes has blank lines too)
    has_fitb_keyword = 'fill-in' in doc_lower or 'fill in the blank' in doc_lower or 'fillintheblank' in doc_lower.replace(' ', '').replace('-', '')
    has_timestamps = bool(re.search(r'\d+\.\s*\(\d+:\d+', document_text))  # Has timestamps like "1. (0:00)"

    # Only use underscores as indicator if FITB keyword is also present
    is_fitb = has_fitb_keyword or has_timestamps

    if is_fitb:
        print(f"  📝 Detected fill-in-the-blank format - using FITB extraction")  # noqa: T201
        fitb_results = extract_fitb_by_template_comparison(document_text, template_text)
        if fitb_results:
            # Filter out excluded sections and blank/template content
            exclude_lower = [em.lower().strip() for em in exclude_markers] if exclude_markers else []
            filtered_fitb = []
            for resp in fitb_results:
                question = resp.get('question', '').lower()
                answer = resp.get('answer', '')
                answer_lower = answer.lower()

                # Skip blank underscore lines (e.g., "• _______________")
                answer_stripped = re.sub(r'[_•\-\s]', '', answer)
                if len(answer_stripped) < 5:
                    continue

                # Skip template instruction text
                if any(kw in answer_lower for kw in ['use bullets', 'write important', 'add more notes', 'drawing']):
                    continue

                # Check if this response is from an excluded section
                # Check both directions: exclude text in answer, AND answer in exclude text
                is_excluded = False
                for em in exclude_lower:
                    # Original: exclude marker contained in answer (short marker, long answer)
                    if em in answer_lower:
                        is_excluded = True
                        break
                    # Reverse: answer contained in exclude marker (long marker, short answer)
                    # Only for answers with enough length to avoid false positives
                    if len(answer_lower) >= 15 and answer_lower in em:
                        is_excluded = True
                        break
                if not is_excluded:
                    filtered_fitb.append(resp)
            fitb_results = filtered_fitb
            extracted.extend(fitb_results)
            print(f"      Found {len(fitb_results)} responses via FITB extraction")  # noqa: T201

    # PRIORITY 1: Use customMarkers from Builder (most reliable)
    # Markers can be:
    #   - String: "Summary (Bottom Section)" - extracts until next marker
    #   - Object: {"start": "Summary", "end": "📖"} - extracts until end marker
    if custom_markers and len(custom_markers) > 0:
        # Find positions of all markers in the document (exact + fuzzy)
        marker_positions, exact_matches, fuzzy_matches = _build_marker_positions(
            custom_markers, document_text, doc_lower, doc_lower_normalized,
            normalize_for_search)

        # Sort by position in document
        marker_positions.sort(key=lambda x: x['start'])

        # Track excluded sections
        excluded_sections = []

        # Normalize exclude markers for comparison
        exclude_markers_normalized = []
        if exclude_markers:
            for em in exclude_markers:
                exclude_markers_normalized.append(em.lower().strip())

        # Track markers that were NOT found in the document at all
        # Build a set of found marker names using multiple representations
        # (full text, first line, emoji-stripped) so multi-line or emoji markers
        # are correctly matched against the config
        found_marker_names = set()
        for mp in marker_positions:
            m = mp['marker'].lower()
            found_marker_names.add(m)
            # Also add first line (for multi-line markers found by first-line strategy)
            first_line_found = m.split('\n')[0].strip()
            if first_line_found:
                found_marker_names.add(first_line_found)
            # Also add emoji-stripped versions
            m_no_emoji = strip_emojis(m).strip()
            if m_no_emoji:
                found_marker_names.add(m_no_emoji)
            first_no_emoji = strip_emojis(first_line_found).strip()
            if first_no_emoji:
                found_marker_names.add(first_no_emoji)

        missing_sections = []
        for marker in custom_markers:
            if isinstance(marker, dict):
                marker_name = marker.get('start', '').strip()
            else:
                marker_name = str(marker).strip()
            if not marker_name:
                continue
            # Check multiple representations of the marker name
            marker_lower = marker_name.lower()
            marker_first_line = marker_lower.split('\n')[0].strip()
            marker_no_emoji = strip_emojis(marker_lower).strip()
            marker_first_no_emoji = strip_emojis(marker_first_line).strip()
            is_found = (marker_lower in found_marker_names
                       or marker_first_line in found_marker_names
                       or marker_no_emoji in found_marker_names
                       or marker_first_no_emoji in found_marker_names)
            if not is_found:
                # Don't flag excluded sections as missing
                is_excluded = any(em in marker_name.lower() or marker_name.lower() in em
                                for em in exclude_markers_normalized)
                if not is_excluded:
                    missing_sections.append(marker_name)

        _extract_responses_per_marker(
            marker_positions, custom_markers, template_text, document_text,
            doc_lower, doc_lower_normalized, exclude_markers_normalized,
            extracted, blank_questions, excluded_sections,
        )

        # Post-processing: strip any excluded marker text that leaked into responses
        if exclude_markers_normalized and extracted:
            for resp in extracted:
                answer = resp.get("answer", "")
                if not answer:
                    continue
                answer_lower = answer.lower()
                for em in exclude_markers_normalized:
                    em_lines = [l.strip() for l in em.split('\n') if l.strip()]
                    for em_line in em_lines[:3]:
                        stripped_em = re.sub(r'^[^a-zA-Z]*', '', em_line).strip()
                        # If the exclude marker line appears at the start of the answer, strip it and everything after
                        for search_term in [em_line, stripped_em]:
                            if search_term and len(search_term) >= 5:
                                pos = answer_lower.find(search_term)
                                if pos != -1:
                                    answer = answer[:pos].strip()
                                    answer_lower = answer.lower()
                # Strip trailing emoji/whitespace/special chars left over
                answer = answer.rstrip()
                answer = re.sub(r'[\s\U00010000-\U0010ffff]+$', '', answer).strip()
                if answer != resp["answer"]:
                    resp["answer"] = answer
                    if not answer or len(answer.strip()) < 5:
                        # Answer was entirely excluded content — mark as blank
                        extracted.remove(resp)
                        blank_questions.append(resp.get("question", "Unknown"))

        # Post-processing: strip custom marker text that leaked into responses.
        # This handles cases where multi-line marker forward scan fails to skip
        # all marker lines, or where marker positions overlap with adjacent content.
        if custom_markers and extracted:
            marker_line_texts = []
            for m in custom_markers:
                mt = m.get('start', '').strip() if isinstance(m, dict) else str(m).strip()
                if mt:
                    for ml in mt.split('\n'):
                        ml = ml.strip()
                        if ml and len(ml) >= 10:
                            marker_line_texts.append(ml.lower())

            for resp in list(extracted):
                answer = resp.get("answer", "")
                if not answer:
                    continue
                lines = answer.split('\n')
                filtered = []
                for line in lines:
                    line_stripped = line.strip()
                    line_lower = line_stripped.lower()
                    # Check if this line matches any custom marker line.
                    # - mt in line_lower: marker text appears within the line (clear match)
                    # - line_lower in mt: line is a substring of marker text — only match
                    #   if the line is substantial (>=30 chars) to avoid removing short
                    #   student answers like "Jefferson" that happen to be in a long marker
                    is_marker_line = False
                    for mt in marker_line_texts:
                        if mt in line_lower or (len(line_lower) >= 30 and line_lower in mt):
                            is_marker_line = True
                            break
                    if not is_marker_line:
                        filtered.append(line)
                new_answer = '\n'.join(filtered).strip()
                if new_answer != answer:
                    resp["answer"] = new_answer
                    if not new_answer or len(new_answer.strip()) < 5:
                        extracted.remove(resp)
                        blank_questions.append(resp.get("question", "Unknown"))

        # If we found markers, return results (skip pattern matching)
        if marker_positions:
            total_q = len(extracted) + len(blank_questions)
            match_summary = f"{exact_matches} exact"
            if fuzzy_matches > 0:
                match_summary += f", {fuzzy_matches} fuzzy"
            summary = f"Extracted {len(extracted)} responses using {len(marker_positions)} markers ({match_summary})."
            if excluded_sections:
                summary += f" Excluded {len(excluded_sections)} section(s) from grading."
            if missing_sections:
                summary += f" {len(missing_sections)} required section(s) MISSING from submission."
            return {
                "extracted_responses": extracted,
                "blank_questions": blank_questions,
                "missing_sections": missing_sections,
                "total_questions": total_q,
                "answered_questions": len(extracted),
                "extraction_summary": summary,
                "excluded_sections": excluded_sections
            }

    # FALLBACK: If no markers provided, use simple pattern matching
    return _extract_by_pattern_matching(document_text, extracted, blank_questions)


def format_extracted_for_grading(extraction_result: dict, marker_config: list = None, extraction_mode: str = 'structured') -> str:
    """
    Format pre-extracted responses for the grading prompt.
    Includes section point values if provided.

    Args:
        extraction_result: Dict with extracted_responses, blank_questions, etc.
        marker_config: List of marker configs with points, e.g. [{"start": "Summary", "points": 20}, ...]
        extraction_mode: "structured" (parse with rules) or "ai" (send raw, let AI figure it out)
    """
    if not extraction_result or not extraction_result.get("extracted_responses"):
        return "NO STUDENT RESPONSES FOUND - Document appears to be blank or unfinished."

    # Build marker points lookup
    marker_points = {}
    if marker_config:
        for m in marker_config:
            if isinstance(m, dict):
                marker_points[m.get('start', '').lower()] = m.get('points', 10)
            elif isinstance(m, str):
                marker_points[m.lower()] = 10

    output = []
    output.append("=" * 50)
    if extraction_mode == 'ai':
        output.append("RAW SECTION CONTENT (AI will identify prompts vs student responses)")
    else:
        output.append("VERIFIED STUDENT RESPONSES (extracted from document)")
    output.append("=" * 50)
    output.append("")

    for i, item in enumerate(extraction_result["extracted_responses"], 1):
        q_type = item.get("type", "unknown")
        question = item.get("question", "Unknown question")
        answer = item.get("answer", "")

        if extraction_mode == 'ai':
            # AI mode: send raw content, let AI identify what's prompt vs response
            cleaned_answer = answer
        else:
            # Structured mode: clean answer by stripping out question text
            cleaned_lines = []
            for line in answer.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Skip common prompt-only lines (no student content)
                if line.lower() in ('write your answer:', 'your answer:', 'answer:'):
                    continue
                # If line has a question mark, only keep text AFTER the ?
                if '?' in line:
                    parts = line.split('?')
                    after_q = parts[-1].strip() if len(parts) > 1 else ''
                    if after_q and len(after_q) > 1:
                        cleaned_lines.append(after_q)
                    # Skip lines that are ONLY questions (nothing after ?)
                # If line has colon (vocab format), only keep text AFTER the :
                elif ':' in line and not line.startswith('http'):
                    parts = line.split(':', 1)
                    term = parts[0].strip()
                    defn = parts[1].strip() if len(parts) > 1 else ''
                    # Only treat as vocab if term is short (1-4 words) AND has a definition
                    if len(term.split()) <= 4 and defn and len(defn) > 1:
                        cleaned_lines.append(defn)
                    elif defn and len(defn) > 1:
                        # Longer term but has definition - keep whole line
                        cleaned_lines.append(line)
                    # Skip lines that are just "Term:" with no definition (blank vocab)
                else:
                    # Final check: skip lines that are instructions/prompts
                    if not is_question_or_prompt(line):
                        cleaned_lines.append(line)

            cleaned_answer = '\n'.join(cleaned_lines) if cleaned_lines else ''
            if not cleaned_answer and answer:
                print(f"    ⚠️ format_extracted: All content for '{question[:50]}' was template text — sending empty")  # noqa: T201

        # Look up points for this section
        points_str = ""
        for marker_key, pts in marker_points.items():
            if marker_key in question.lower():
                points_str = f" [{pts} points]"
                break

        output.append(f"[{i}] {question}{points_str}")
        output.append(f"    STUDENT ANSWER: \"{cleaned_answer}\"")
        output.append(f"    (Type: {q_type})")
        output.append("")

    # Add blank questions with their point values
    if extraction_result.get("blank_questions"):
        output.append("-" * 50)
        output.append("UNANSWERED QUESTIONS (left blank by student):")
        for q in extraction_result["blank_questions"]:
            points_str = ""
            for marker_key, pts in marker_points.items():
                if marker_key in q.lower():
                    points_str = f" [LOSES {pts} points]"
                    break
            output.append(f"  • {q}{points_str}")

    # Add missing sections (required by assignment but entirely absent from submission)
    if extraction_result.get("missing_sections"):
        output.append("-" * 50)
        output.append("MISSING SECTIONS (required by assignment but not found in student submission):")
        for section in extraction_result["missing_sections"]:
            points_str = ""
            for marker_key, pts in marker_points.items():
                if marker_key in section.lower():
                    points_str = f" [LOSES {pts} points]"
                    break
            output.append(f"  ✗ {section}{points_str} — ENTIRELY OMITTED")

    output.append("")
    output.append(f"SUMMARY: {extraction_result.get('extraction_summary', '')}")

    return "\n".join(output)


def extract_student_work(content: str) -> tuple:
    """
    Extract only the student work portions of the document.

    Finds the first student work marker and returns everything after it.
    This ensures we capture student responses without duplicating content.

    Returns: (student_work, markers_found)
    - student_work: The extracted student content (or full content if no marker)
    - markers_found: List of markers that were found
    """
    content_lower = content.lower()

    # Find the earliest marker position
    found_markers = []
    earliest_pos = len(content)
    earliest_marker = None

    for marker in STUDENT_WORK_MARKERS:
        marker_lower = marker.lower()
        pos = content_lower.find(marker_lower)
        if pos != -1:
            if marker not in found_markers:
                found_markers.append(marker)
            if pos < earliest_pos:
                earliest_pos = pos
                earliest_marker = marker

    if not earliest_marker:
        # No markers found - return full content
        return content, []

    # Return everything from the first marker onward
    # Find the line containing the marker and start from there
    line_start = content.rfind('\n', 0, earliest_pos)
    if line_start == -1:
        line_start = 0
    else:
        line_start += 1  # Skip the newline character

    student_work = content[line_start:].strip()
    return student_work, found_markers
