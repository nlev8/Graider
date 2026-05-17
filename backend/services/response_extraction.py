"""Pure student-response text parsing and extraction. No Flask, no network, no file I/O."""

import re


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
        except re.error:
            pass

    # Try first significant phrase (first 5 words)
    first_phrase = ' '.join(marker_words[:5])
    # Allow for inserted spaces/chars
    flexible_pattern = r'\s*'.join([re.escape(c) for c in first_phrase if c.strip()])
    try:
        match = re.search(flexible_pattern[:100], doc_lower)  # Limit pattern length
        if match:
            return match.start()
    except re.error:
        pass

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
