"""
Assignment Grader for 6th Grade Social Studies
===============================================
Tailored for Southwestern Middle School

FILE NAMING EXPECTED: FirstName_LastName_AssignmentName.docx
ROSTER FORMAT: "LastName; FirstName" with Student ID and Email columns

FERPA COMPLIANCE:
- Student names are NOT sent to OpenAI's API
- Only assignment content is analyzed for grading
- All student identification stays local on your computer
- OpenAI API data is not used to train models (per their policy)
- Consult your district's policies for AI tool usage

SETUP:
1. pip install openai python-docx openpyxl python-dotenv
2. Create .env file with: OPENAI_API_KEY=your-key-here
3. Update the folder paths below
4. Update the ASSIGNMENT_INSTRUCTIONS for each assignment
"""

import os
import csv
import json
import re
import random
import concurrent.futures
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Import student history for personalized feedback
try:
    from backend.student_history import build_history_context
except ImportError:
    # Fallback if running standalone or module not available
    def build_history_context(student_id):
        return ""

# Import accommodations for IEP/504 support (FERPA compliant)
try:
    from backend.accommodations import build_accommodation_prompt
except ImportError:
    # Fallback if running standalone or module not available
    def build_accommodation_prompt(student_id):
        return ""

# Load environment variables from .env file (override system env vars)
import os
app_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(app_dir, '.env'), override=True)

# =============================================================================
# PRE-EXTRACTION - Extract student responses BEFORE AI grading (prevents hallucination)
# =============================================================================

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

    # Try matching without extra whitespace/punctuation
    marker_normalized = ' '.join(marker_lower.split())  # Collapse whitespace
    marker_words = marker_normalized.split()

    if len(marker_words) < 2:
        return -1  # Too short for fuzzy matching

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


def extract_student_responses(document_text: str, custom_markers: list = None, exclude_markers: list = None) -> dict:
    """
    Extract student responses from document using customMarkers from Builder.

    APPROACH (with fallbacks):
    1. EXACT MATCH: Find markers exactly in document
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

    # PRIORITY 1: Use customMarkers from Builder (most reliable)
    # Markers can be:
    #   - String: "Summary (Bottom Section)" - extracts until next marker
    #   - Object: {"start": "Summary", "end": "📖"} - extracts until end marker
    if custom_markers and len(custom_markers) > 0:
        # Find positions of all markers in the document (exact + fuzzy)
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

            # Try exact match first
            pos = doc_lower.find(marker_clean.lower())
            if pos != -1:
                exact_matches += 1
                marker_positions.append({
                    'marker': marker_clean,
                    'start': pos,
                    'end': pos + len(marker_clean),
                    'end_marker': end_marker,
                    'match_type': 'exact'
                })
            else:
                # Try fuzzy match
                pos = fuzzy_find_marker(document_text, marker_clean)
                if pos != -1:
                    fuzzy_matches += 1
                    # Estimate end position based on marker length
                    marker_positions.append({
                        'marker': marker_clean,
                        'start': pos,
                        'end': pos + min(len(marker_clean), 100),
                        'end_marker': end_marker,
                        'match_type': 'fuzzy'
                    })

        # Sort by position in document
        marker_positions.sort(key=lambda x: x['start'])

        # Track excluded sections
        excluded_sections = []

        # Normalize exclude markers for comparison
        exclude_markers_normalized = []
        if exclude_markers:
            for em in exclude_markers:
                exclude_markers_normalized.append(em.lower().strip())

        # Extract response after each marker
        for i, mp in enumerate(marker_positions):
            marker_text = mp['marker']
            content_start = mp['end']
            end_marker = mp.get('end_marker')

            # Check if this marker should be excluded from grading
            marker_lower = marker_text.lower().strip()
            is_excluded = False
            for em in exclude_markers_normalized:
                # Check if exclude marker is contained in this marker or vice versa
                if em in marker_lower or marker_lower in em:
                    is_excluded = True
                    excluded_sections.append(marker_text[:80])
                    break

            if is_excluded:
                continue  # Skip this section - don't grade it

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

            # Extract the response
            response = document_text[content_start:content_end].strip()

            # Clean up: remove leading colons, newlines
            response = re.sub(r'^[:\s\n]+', '', response).strip()

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
                # Filter out blank placeholder lines only
                student_lines = []
                for line in lines:
                    # Skip lines that are just underscores (blank placeholders)
                    if line.replace('_', '').replace(' ', '') == '':
                        continue
                    student_lines.append(line)

                # If no student content remains, it's blank
                if not student_lines or sum(len(l) for l in student_lines) < 10:
                    is_blank = True
                else:
                    # Use filtered response
                    response = '\n'.join(student_lines)

            if not is_blank:
                extracted.append({
                    "question": question_label,
                    "answer": response[:1000],
                    "type": "marker_response"
                })
            else:
                blank_questions.append(question_label)

        # If we found markers, return results (skip pattern matching)
        if marker_positions:
            total_q = len(extracted) + len(blank_questions)
            match_summary = f"{exact_matches} exact"
            if fuzzy_matches > 0:
                match_summary += f", {fuzzy_matches} fuzzy"
            summary = f"Extracted {len(extracted)} responses using {len(marker_positions)} markers ({match_summary})."
            if excluded_sections:
                summary += f" Excluded {len(excluded_sections)} section(s) from grading."
            return {
                "extracted_responses": extracted,
                "blank_questions": blank_questions,
                "total_questions": total_q,
                "answered_questions": len(extracted),
                "extraction_summary": summary,
                "excluded_sections": excluded_sections
            }

    # FALLBACK: If no markers provided, use simple pattern matching
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
                if answer and len(answer) > 3:
                    extracted.append({
                        "question": current_question,
                        "answer": answer[:500],
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
        if answer and len(answer) > 3:
            extracted.append({
                "question": current_question,
                "answer": answer[:500],
                "type": "numbered_qa"
            })

    # Fill-in-the-blank pattern 1: ___answer___ (wrapped in underscores)
    blank_matches = re.findall(r'_{2,}([^_\n]{1,100})_{2,}', document_text)
    for match in blank_matches:
        answer = match.strip()
        if answer and len(answer) > 0:
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
    # Look for lines that start with a word (potential answer) followed by context
    for line in lines:
        line_stripped = line.strip()
        # Skip if empty, a question, or already processed
        if not line_stripped or line_stripped.endswith('?'):
            continue
        # Check if line has a short leading phrase that could be an answer
        # Pattern: starts with 1-3 words, followed by more context
        leading_match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Za-z]+){0,2})\s+(.{10,})$', line_stripped)
        if leading_match:
            potential_answer = leading_match.group(1)
            context = leading_match.group(2)
            # If context mentions blanks or has fill-in structure, this might be an answer
            if '___' in context or 'was' in context.lower()[:20] or 'the' in context.lower()[:10]:
                # Skip if it's template text
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


def extract_student_responses_legacy(document_text: str, custom_markers: list = None) -> dict:
    """LEGACY: Old complex extraction - kept for reference but not used."""
    import re

    lines = document_text.split('\n')
    extracted = []
    blank_questions = []

    if response_sections:
        for section in response_sections:
            start_marker = section.get('start', '').strip()
            end_marker = section.get('end', '').strip() if section.get('end') else None

            if not start_marker:
                continue

            start_lower = start_marker.lower()
            doc_lower = document_text.lower()
            start_pos = doc_lower.find(start_lower)

            if start_pos == -1:
                blank_questions.append(start_marker)
                continue

            content_start = start_pos + len(start_marker)

            if end_marker:
                end_pos = doc_lower.find(end_marker.lower(), content_start)
                if end_pos == -1:
                    end_pos = min(content_start + 1000, len(document_text))  # Cap at 1000 chars
            else:
                # No end marker - find next likely section or cap at 800 chars
                # Look for common section boundaries
                next_section = len(document_text)
                for boundary in ['\n\n\n', '📝', '✏️', '🌱', '\nVocabulary', '\nQuestions', '\nReflection', '\nMain Idea']:
                    pos = doc_lower.find(boundary.lower(), content_start + 20)  # Skip a bit to avoid finding ourselves
                    if pos != -1 and pos < next_section:
                        next_section = pos
                end_pos = min(next_section, content_start + 800)

            # Extract the content
            content = document_text[content_start:end_pos].strip()

            # Clean up: remove leading colons, newlines, and prompt fragments
            content = re.sub(r'^[:\s\n]+', '', content)
            content = re.sub(r'^\s*of\s+(?:today.?s?\s+)?(?:the\s+)?(?:reading|lesson|section|article)[:\s]*\n*', '', content, flags=re.IGNORECASE).strip()
            content = re.sub(r'^\s*(?:today.?s?\s+)?(?:the\s+)?(?:reading|lesson|article)[:\s]*\n*', '', content, flags=re.IGNORECASE).strip()

            # Check if there's actual student content (not just template text)
            if content and len(content) > 10:
                # Filter out template text
                is_template = any(kw in content.lower() for kw in [
                    'write your', 'answer each', 'explain how', 'describe how',
                    'complete the', 'using the reading', 'type your answer',
                    '[your answer here]', '[type here]'
                ])

                if not is_template:
                    extracted.append({
                        "question": start_marker,
                        "answer": content[:800],
                        "type": "highlighted_section"
                    })
                else:
                    blank_questions.append(start_marker)
            else:
                blank_questions.append(start_marker)

    # Patterns for questions/prompts
    question_patterns = [
        r'^\d+[\.\)]\s*(.+)',  # "1. Question" or "1) Question"
        r'^[a-zA-Z][\.\)]\s*(.+)',  # "a. Question" or "a) Question"
    ]

    # Track current question for multi-line answers
    current_question = None
    current_question_idx = -1

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Pattern 1: Fill-in-the-blank with answer (text between underscores)
        # e.g., "The year was ___1803___"
        blank_matches = re.findall(r'_{2,}([^_\n]{1,50})_{2,}', line)
        for match in blank_matches:
            answer = match.strip()
            if answer and len(answer) > 0:
                # Try to find the question context
                question_context = line_stripped[:50] + "..." if len(line_stripped) > 50 else line_stripped
                extracted.append({
                    "question": question_context,
                    "answer": answer,
                    "type": "fill_in_blank"
                })

        # Pattern 2: Vocabulary definitions (Term: answer)
        # e.g., "Rebellion: going again"
        if ':' in line_stripped:
            parts = line_stripped.split(':', 1)
            term = parts[0].strip()
            answer = parts[1].strip() if len(parts) > 1 else ""

            # Check if this looks like a vocabulary term (not a section header)
            is_vocab = (
                len(term) > 2 and
                len(term) < 50 and
                not any(kw in term.lower() for kw in ['question', 'task', 'summary', 'reflection', 'main idea', 'vocabulary', 'answer', 'notes', 'reading', 'section'])
            )

            if is_vocab:
                # Check if answer is blank or just underscores
                if answer and not re.match(r'^[_\s\-\.]+$', answer) and len(answer) > 1:
                    extracted.append({
                        "question": f"Define: {term}",
                        "answer": answer,
                        "type": "vocabulary"
                    })
                else:
                    blank_questions.append(f"Define: {term}")

        # Pattern 3: Numbered questions with answers on same line
        # e.g., "1. Why was this important? It helped the country grow"
        num_match = re.match(r'^(\d+)[\.\)]\s*(.+?)[\?:]\s*(.+)$', line_stripped)
        if num_match:
            q_num = num_match.group(1)
            question = num_match.group(2).strip() + "?"
            answer = num_match.group(3).strip()

            if answer and not re.match(r'^[_\s\-\.]+$', answer) and len(answer) > 1:
                extracted.append({
                    "question": f"{q_num}. {question}",
                    "answer": answer,
                    "type": "short_answer"
                })
            else:
                blank_questions.append(f"{q_num}. {question}")
            continue

        # Pattern 4: Questions ending with ? (track for next line answer)
        if line_stripped.endswith('?'):
            current_question = line_stripped
            current_question_idx = i
            continue

        # Pattern 5: Numbered question without answer on same line
        num_only = re.match(r'^(\d+)[\.\)]\s*(.+)$', line_stripped)
        if num_only and '?' in line_stripped:
            current_question = line_stripped
            current_question_idx = i
            continue

        # Pattern 6: Check if this line is an answer to the previous question
        if current_question and i == current_question_idx + 1:
            # This might be an answer
            potential_answer = line_stripped

            # Filter out template text, headers, and blanks
            is_template = any(kw in potential_answer.lower() for kw in [
                'write your', 'explain', 'describe', 'answer', 'complete',
                'section', 'chapter', 'reading', 'vocabulary', 'summary',
                'reflection', 'task', 'question'
            ])
            is_blank = re.match(r'^[_\s\-\.]*$', potential_answer) or len(potential_answer) < 3

            if not is_template and not is_blank:
                extracted.append({
                    "question": current_question,
                    "answer": potential_answer,
                    "type": "short_answer"
                })
            else:
                blank_questions.append(current_question)

            current_question = None

    # Pattern 7: Check for section headers that expect written responses
    # These are headers like "Summary:", "📝 SUMMARY", "Reflection:", etc. followed by student paragraphs
    # Using (?:📝|✏️|✍️|🖊️|🌟)? to optionally match common emojis
    section_headers = [
        # Summary patterns - be specific to avoid matching "Questions / Summary" headers
        (r'write\s+(?:a\s+)?(?:\d+[–-]\d+\s+)?(?:sentence\s+)?summary[:\s]+', 'Summary'),  # "Write a 2-3 sentence summary:"
        (r'(?:📝|✏️|✍️|🖊️)\s*summary\s*(?:\([^)]*\))?\s*[:\.\n]', 'Summary'),  # 📝 SUMMARY (3-4 sentences):
        (r'\bsummary\s*of\s+(?:today\'?s?\s+)?(?:reading|lesson|section)[:\s]+', 'Summary'),  # "Summary of today's reading:"
        (r'(?:^|\n)\s*summary[:\s]*(?=\n)', 'Summary'),  # "Summary:" on its own line
        # Reflection patterns
        (r'(?:📝|✏️|✍️)?\s*reflection\s*[^\.]*[:\.]', 'Reflection'),
        (r'(?:^|\n)\s*reflection[:\s]+', 'Reflection'),
        (r'final reflection[:\s]*', 'Final Reflection'),
        # Task patterns
        (r'(?:📝|✏️|✍️)?\s*student task\s*[^\.]*[:\.]', 'Student Task'),
        (r'student task[:\s]+', 'Student Task'),
        # Other patterns
        (r'main idea[:\s]+', 'Main Idea'),
        (r'explain in your own words[:\s]*', 'Explanation'),
        (r'write your answer[:\s]*', 'Written Response'),
        (r'your response[:\s]*', 'Response'),
    ]

    full_text_lower = document_text.lower()
    full_text = document_text  # Keep original case for answer extraction

    for pattern, section_name in section_headers:
        match = re.search(pattern, full_text_lower)
        if match:
            # Find the position of the header
            header_end = match.end()

            # Look for paragraph content after the header
            # Skip blank lines and find the next substantial text
            remaining_text = full_text[header_end:]

            # Split into lines/paragraphs to find student response
            # Skip instruction lines that start with prompt words
            instruction_starters = [
                'explain how', 'describe how', 'write a', 'write your', 'answer each',
                'complete the', 'using the reading', 'in a few sentences', 'in your own words',
                'what is', 'what are', 'what was', 'what were', 'how did', 'how do', 'why did', 'why do',
                'summarize', 'identify', 'list the', 'define the'
            ]

            # Find paragraphs (split by double newline or single newline)
            paragraphs = re.split(r'\n\s*\n|\n', remaining_text)
            student_response = None

            for para in paragraphs:
                para = para.strip()
                if not para or len(para) < 15:
                    continue

                # Check if this looks like an instruction line
                para_lower = para.lower()
                is_instruction = any(para_lower.startswith(starter) for starter in instruction_starters)

                # Also check for question marks at the end (likely a prompt, not answer)
                if para.rstrip().endswith('?'):
                    is_instruction = True

                if not is_instruction:
                    # This looks like a student response
                    # Clean up any remaining prompt fragments
                    content = para
                    content = re.sub(r'^\s*of\s+(?:today.?s?\s+)?(?:the\s+)?(?:reading|lesson|section|article)[:\s]*', '', content, flags=re.IGNORECASE).strip()
                    content = re.sub(r'^\s*(?:today.?s?\s+)?(?:the\s+)?(?:reading|lesson|article)[:\s]*', '', content, flags=re.IGNORECASE).strip()

                    # Check it has substance
                    if len(content) > 20 and any(c.isalpha() for c in content):
                        student_response = content
                        break

            if student_response:
                # Check if we already captured this (avoid duplicates)
                already_captured = any(student_response[:50] in r.get('answer', '')[:50] for r in extracted)
                if not already_captured:
                    extracted.append({
                        "question": section_name,
                        "answer": student_response[:800],  # Allow longer responses
                        "type": "written_response"
                    })
            else:
                # Section appears to be blank or only has instructions
                blank_questions.append(section_name)

    # Build summary
    total_q = len(extracted) + len(blank_questions)
    answered_q = len(extracted)

    summary = f"Found {answered_q} responses out of {total_q} detected questions/prompts."
    if blank_questions:
        summary += f" {len(blank_questions)} questions left blank."

    return {
        "extracted_responses": extracted,
        "blank_questions": blank_questions,
        "total_questions": total_q,
        "answered_questions": answered_q,
        "extraction_summary": summary
    }


def format_extracted_for_grading(extraction_result: dict, marker_config: list = None) -> str:
    """
    Format pre-extracted responses for the grading prompt.
    Includes section point values if provided.

    Args:
        extraction_result: Dict with extracted_responses, blank_questions, etc.
        marker_config: List of marker configs with points, e.g. [{"start": "Summary", "points": 20}, ...]
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
    output.append("VERIFIED STUDENT RESPONSES (extracted from document)")
    output.append("=" * 50)
    output.append("")

    for i, item in enumerate(extraction_result["extracted_responses"], 1):
        q_type = item.get("type", "unknown")
        question = item.get("question", "Unknown question")
        answer = item.get("answer", "")

        # Clean answer: strip out question text, keep only student responses
        cleaned_lines = []
        for line in answer.split('\n'):
            line = line.strip()
            if not line:
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
                # Only treat as vocab if term is short (1-4 words)
                if len(term.split()) <= 4 and defn:
                    cleaned_lines.append(defn)
                else:
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)

        cleaned_answer = '\n'.join(cleaned_lines) if cleaned_lines else answer

        # Look up points for this section
        points_str = ""
        for marker_key, pts in marker_points.items():
            if marker_key in question.lower():
                points_str = f" [{pts} points]"
                break

        output.append(f"[{i}] {question}{points_str}")
        output.append(f"    STUDENT ANSWER: \"{cleaned_answer[:500]}{'...' if len(cleaned_answer) > 500 else ''}\"")
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

    output.append("")
    output.append(f"SUMMARY: {extraction_result.get('extraction_summary', '')}")

    return "\n".join(output)


# =============================================================================
# WRITING STYLE ANALYSIS - For AI Detection
# =============================================================================

def analyze_writing_style(text: str) -> dict:
    """
    Analyze writing style metrics from student text.
    Used to build a profile and detect AI-generated content.
    """
    if not text or len(text.strip()) < 20:
        return None

    # Clean text
    clean_text = text.strip()

    # Split into sentences (basic sentence detection)
    sentences = re.split(r'[.!?]+', clean_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]

    # Split into words
    words = re.findall(r'\b[a-zA-Z]+\b', clean_text)
    if len(words) < 5:
        return None

    # Calculate metrics
    avg_word_length = sum(len(w) for w in words) / len(words)
    avg_sentence_length = len(words) / max(len(sentences), 1)

    # Vocabulary complexity (based on word length distribution)
    long_words = [w for w in words if len(w) > 7]
    complex_word_ratio = len(long_words) / len(words)

    # Detect common misspellings (lowercase words that might be proper nouns)
    potential_misspellings = []
    common_misspelled = re.findall(r'\b[a-z]+[A-Z][a-z]*\b|\b[a-z]{2,}\b', clean_text)

    # Check for specific patterns
    uses_contractions = bool(re.search(r"\b(don't|can't|won't|isn't|aren't|doesn't|didn't|wouldn't|couldn't|shouldn't|I'm|you're|they're|we're|it's|that's|what's|there's|here's)\b", clean_text, re.IGNORECASE))

    # Capitalization habits
    proper_caps = len(re.findall(r'\b[A-Z][a-z]+\b', clean_text))
    all_caps = len(re.findall(r'\b[A-Z]{2,}\b', clean_text))

    # Simple vs complex vocabulary indicators
    simple_words = ['the', 'a', 'an', 'is', 'was', 'are', 'were', 'it', 'they', 'he', 'she', 'we', 'you', 'i', 'and', 'but', 'or', 'so', 'because', 'like', 'just', 'really', 'very', 'good', 'bad', 'big', 'small']
    simple_count = sum(1 for w in words if w.lower() in simple_words)
    simple_ratio = simple_count / len(words)

    # Academic/AI indicator words
    academic_words = ['furthermore', 'therefore', 'consequently', 'however', 'nevertheless', 'moreover', 'subsequently', 'fundamental', 'significant', 'essentially', 'particularly', 'specifically', 'transforming', 'establishing', 'securing', 'trajectory', 'precedent', 'constitutional', 'acquisition', 'vital', 'expansion']
    academic_count = sum(1 for w in words if w.lower() in academic_words)

    # Calculate complexity score (1-10 scale)
    complexity_score = min(10, max(1,
        (avg_word_length - 3) * 1.5 +  # Word length contribution
        (avg_sentence_length / 5) +     # Sentence length contribution
        (complex_word_ratio * 10) +     # Complex words contribution
        (academic_count * 2) -          # Academic words add complexity
        (simple_ratio * 3)              # Simple words reduce complexity
    ))

    return {
        "avg_word_length": round(avg_word_length, 2),
        "avg_sentence_length": round(avg_sentence_length, 2),
        "word_count": len(words),
        "sentence_count": len(sentences),
        "complex_word_ratio": round(complex_word_ratio, 3),
        "simple_word_ratio": round(simple_ratio, 3),
        "academic_word_count": academic_count,
        "uses_contractions": uses_contractions,
        "complexity_score": round(complexity_score, 2)
    }


def compare_writing_styles(current_style: dict, historical_profile: dict) -> dict:
    """
    Compare current submission's writing style against student's historical profile.
    Returns deviation analysis and AI likelihood.
    """
    if not current_style or not historical_profile:
        return {"deviation": "unknown", "ai_likelihood": "unknown", "reason": "Insufficient data"}

    deviations = []

    # Check complexity score deviation
    hist_complexity = historical_profile.get("avg_complexity_score", 3.0)
    curr_complexity = current_style.get("complexity_score", 3.0)
    complexity_diff = curr_complexity - hist_complexity

    if complexity_diff > 3:
        deviations.append(f"Complexity jumped from {hist_complexity:.1f} to {curr_complexity:.1f}")

    # Check sentence length deviation
    hist_sent_len = historical_profile.get("avg_sentence_length", 8.0)
    curr_sent_len = current_style.get("avg_sentence_length", 8.0)
    sent_len_diff = curr_sent_len - hist_sent_len

    if sent_len_diff > 10:
        deviations.append(f"Sentence length jumped from {hist_sent_len:.1f} to {curr_sent_len:.1f} words")

    # Check for sudden academic vocabulary
    hist_academic = historical_profile.get("avg_academic_words", 0)
    curr_academic = current_style.get("academic_word_count", 0)

    if curr_academic > hist_academic + 2:
        deviations.append(f"Academic vocabulary increased significantly ({curr_academic} vs typical {hist_academic})")

    # Check word length deviation
    hist_word_len = historical_profile.get("avg_word_length", 4.0)
    curr_word_len = current_style.get("avg_word_length", 4.0)

    if curr_word_len - hist_word_len > 1.5:
        deviations.append(f"Word length increased from {hist_word_len:.1f} to {curr_word_len:.1f}")

    # Determine AI likelihood based on deviations
    if len(deviations) >= 3:
        ai_likelihood = "likely"
    elif len(deviations) >= 2:
        ai_likelihood = "possible"
    elif len(deviations) == 1 and complexity_diff > 4:
        ai_likelihood = "possible"
    else:
        ai_likelihood = "none"

    return {
        "deviation": "significant" if len(deviations) >= 2 else "minor" if len(deviations) == 1 else "none",
        "ai_likelihood": ai_likelihood,
        "deviations": deviations,
        "reason": "; ".join(deviations) if deviations else "Writing style consistent with history"
    }


def update_writing_profile(student_id: str, current_style: dict, student_name: str = None):
    """
    Update student's writing profile with new submission data.
    Maintains running averages across assignments.
    """
    if not current_style or not student_id:
        return

    history_dir = os.path.expanduser("~/.graider_data/student_history")
    history_file = os.path.join(history_dir, f"{student_id}.json")

    try:
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
        else:
            history = {"student_id": student_id, "assignments": []}

        # Always update the student name if provided
        if student_name:
            history["name"] = student_name

        # Get or initialize writing profile
        profile = history.get("writing_profile", {
            "avg_word_length": 0,
            "avg_sentence_length": 0,
            "avg_complexity_score": 0,
            "avg_academic_words": 0,
            "uses_contractions": False,
            "sample_count": 0
        })

        # Update running averages
        n = profile.get("sample_count", 0)
        if n > 0:
            profile["avg_word_length"] = (profile["avg_word_length"] * n + current_style["avg_word_length"]) / (n + 1)
            profile["avg_sentence_length"] = (profile["avg_sentence_length"] * n + current_style["avg_sentence_length"]) / (n + 1)
            profile["avg_complexity_score"] = (profile["avg_complexity_score"] * n + current_style["complexity_score"]) / (n + 1)
            profile["avg_academic_words"] = (profile["avg_academic_words"] * n + current_style["academic_word_count"]) / (n + 1)
        else:
            profile["avg_word_length"] = current_style["avg_word_length"]
            profile["avg_sentence_length"] = current_style["avg_sentence_length"]
            profile["avg_complexity_score"] = current_style["complexity_score"]
            profile["avg_academic_words"] = current_style["academic_word_count"]

        profile["uses_contractions"] = profile.get("uses_contractions", False) or current_style["uses_contractions"]
        profile["sample_count"] = n + 1

        # Round values
        for key in ["avg_word_length", "avg_sentence_length", "avg_complexity_score", "avg_academic_words"]:
            if key in profile:
                profile[key] = round(profile[key], 2)

        history["writing_profile"] = profile
        history["last_updated"] = datetime.now().isoformat()

        # Save updated history
        os.makedirs(history_dir, exist_ok=True)
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)

    except Exception as e:
        print(f"  ⚠️ Could not update writing profile: {e}")


def get_writing_profile(student_id: str) -> dict:
    """
    Retrieve student's historical writing profile.
    """
    if not student_id:
        return None

    history_dir = os.path.expanduser("~/.graider_data/student_history")
    history_file = os.path.join(history_dir, f"{student_id}.json")

    try:
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
                return history.get("writing_profile")
    except Exception:
        pass

    return None

# =============================================================================
# CONFIGURATION - UPDATE THESE FOR EACH GRADING SESSION
# =============================================================================

# Folder containing student assignment files (.docx)
ASSIGNMENT_FOLDER = "/Users/alexc/Downloads/Assignments"

# Output folder for CSV and email files
OUTPUT_FOLDER = "/Users/alexc/Downloads/Assignment Grader/Results"

# Path to your student roster Excel file
ROSTER_FILE = "/Users/alexc/Downloads/Assignment Grader/all_students_updated.xlsx"

# Your OpenAI API key (set in .env file or paste here)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")

# Anthropic API key for Claude models
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Google Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Assignment name (used in output files and emails)
ASSIGNMENT_NAME = "Cornell Notes - Political Parties"  # UPDATE FOR EACH ASSIGNMENT

# Marker phrase(s) that indicate where student work begins
# Only content within the section (until next header) will be graded
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

# Section headers that indicate a NEW section (stops extraction from previous marker)
SECTION_HEADERS = [
    "vocabulary",
    "vocabulary mini-lesson",
    "key vocabulary",
    "notes",
    "guided notes",
    "reading",
    "directions",
    "instructions",
    "primary source",
    "background",
    "overview",
    "introduction",
]


# =============================================================================
# GRADING RUBRIC - Customize point values and criteria as needed
# =============================================================================

GRADING_RUBRIC = """
You are grading 6th grade Social Studies assignments. Be ENCOURAGING and GENEROUS.
These are 11-12 year old students - grade with appropriate expectations for their age.

IMPORTANT GRADING GUIDELINES:
- For FILL-IN-THE-BLANK exercises: Accept any answer that is factually correct or very close. Spelling mistakes should NOT reduce the grade if the intent is clear.
- Accept reasonable synonyms, alternate phrasings, and partial answers that demonstrate understanding.
- If a student gets the main idea right but uses slightly different wording, give FULL CREDIT.
- Minor spelling errors (like "piler" instead of "pillar") should NOT be penalized.
- Be GENEROUS - when in doubt, give the student the benefit of the doubt.

GRADING SCALE (out of 100 points):

1. CONTENT ACCURACY (40 points)
   - Are the answers factually correct or demonstrate understanding?
   - For fill-in-the-blank: Is the completed statement essentially true?
   - 40 pts: Most answers correct (90%+)
   - 35 pts: Good understanding (80-89% correct)
   - 30 pts: Solid effort (70-79% correct)
   - 25 pts: Some understanding (60-69% correct)
   - 20 pts: Partial understanding (50-59% correct)
   - Below 20: Less than half correct

2. COMPLETENESS (25 points)
   - Did the student attempt ALL questions/blanks?
   - 25 pts: All questions attempted
   - 20 pts: Nearly all attempted (90%+)
   - 15 pts: Most attempted (75%+)
   - 10 pts: About half attempted
   - 5 pts: Less than half attempted

3. WRITING QUALITY (20 points)
   - Is the writing legible and understandable?
   - For fill-in-blank, this is less important - be generous
   - 20 pts: Clear and readable
   - 15 pts: Minor issues but understandable
   - 10 pts: Some difficulty but can figure out meaning
   - 5 pts: Hard to understand

4. EFFORT & ENGAGEMENT (15 points)
   - Did the student put in genuine effort?
   - Are answers thoughtful (not random guesses)?
   - 15 pts: Clear effort shown
   - 10 pts: Good effort
   - 5 pts: Minimal effort
   - 0 pts: No real effort

GRADE RANGES:
- A: 90-100 (Great job!)
- B: 80-89 (Good work!)
- C: 70-79 (Solid effort)
- D: 60-69 (Needs improvement)
- F: Below 60 (Significant concerns)

REMEMBER: These are 6th graders. Be kind, encouraging, and generous with grading.
A student who attempts all questions and gets most right should get an A or B.
"""

# DEFAULT ASSIGNMENT INSTRUCTIONS - Only used if no assignment-specific config provided
# This should be empty or generic - assignment-specific instructions come from Builder configs
ASSIGNMENT_INSTRUCTIONS = """
Grade the student's work based on what they were asked to do.
Focus on the content they provided, not on sections that may not apply to this assignment type.
"""


# =============================================================================
# ROSTER LOADING - Reads your Excel student list
# =============================================================================

def load_roster(roster_path: str) -> dict:
    """
    Load student roster from Excel or CSV file.

    Excel format: Student, Student ID, Local ID, Email, Grade, Team
    CSV format: FirstName, LastName, StudentID, Email, Period

    Returns dict mapping "firstname lastname" (lowercase) -> student info
    """
    roster = {}

    if not Path(roster_path).exists():
        print(f"⚠️  Roster file not found: {roster_path}")
        return {}

    roster_path_lower = roster_path.lower()

    # Handle CSV files
    if roster_path_lower.endswith('.csv'):
        import csv
        with open(roster_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try various column name formats
                first_name = row.get('FirstName') or row.get('First Name') or row.get('first_name') or row.get('First') or ''
                last_name = row.get('LastName') or row.get('Last Name') or row.get('last_name') or row.get('Last') or ''
                student_id = row.get('StudentID') or row.get('Student ID') or row.get('student_id') or row.get('ID') or ''
                email = row.get('Email') or row.get('email') or ''
                period = row.get('Period') or row.get('period') or row.get('Class') or ''

                # If Student column exists with "Last; First" format
                if not first_name and not last_name:
                    student_col = row.get('Student') or row.get('Name') or ''
                    if ';' in student_col:
                        parts = student_col.split(';')
                        last_name = parts[0].strip()
                        first_name = parts[1].strip() if len(parts) > 1 else ''
                    elif ',' in student_col:
                        parts = student_col.split(',')
                        last_name = parts[0].strip()
                        first_name = parts[1].strip() if len(parts) > 1 else ''

                if not first_name and not last_name:
                    continue

                first_name_simple = first_name.split()[0] if first_name else ''
                lookup_key = f"{first_name_simple} {last_name}".lower().strip()

                roster[lookup_key] = {
                    "student_id": str(student_id),
                    "student_name": f"{first_name} {last_name}".strip(),
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email or "",
                    "period": str(period) if period else ""
                }

                reverse_key = f"{last_name} {first_name_simple}".lower().strip()
                roster[reverse_key] = roster[lookup_key]

        print(f"📋 Loaded {len(roster)//2} students from CSV roster")
        return roster

    # Handle Excel files
    try:
        import openpyxl
    except ImportError:
        print("❌ openpyxl not installed. Run: pip install openpyxl")
        return {}

    wb = openpyxl.load_workbook(roster_path)
    sheet = wb.active

    # Get header row to find column indices
    headers = [str(cell.value).lower() if cell.value else '' for cell in sheet[1]]

    # Try to find period column
    period_col = None
    for i, h in enumerate(headers):
        if 'period' in h or 'class' in h or 'team' in h:
            period_col = i
            break

    # Skip header row
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue

        student_name = row[0]
        student_id = row[1]
        email = row[3] if len(row) > 3 else ''
        period = row[period_col] if period_col is not None and len(row) > period_col else ''

        if ';' in str(student_name):
            parts = str(student_name).split(';')
            last_name = parts[0].strip()
            first_name = parts[1].strip() if len(parts) > 1 else ""
            first_name_simple = first_name.split()[0] if first_name else ""
        else:
            last_name = str(student_name)
            first_name = ""
            first_name_simple = ""

        lookup_key = f"{first_name_simple} {last_name}".lower().strip()

        roster[lookup_key] = {
            "student_id": str(student_id),
            "student_name": f"{first_name} {last_name}".strip(),
            "first_name": first_name,
            "last_name": last_name,
            "email": email or "",
            "period": str(period) if period else ""
        }

        reverse_key = f"{last_name} {first_name_simple}".lower().strip()
        roster[reverse_key] = roster[lookup_key]

    print(f"📋 Loaded {len(roster)//2} students from Excel roster")
    return roster


# =============================================================================
# FILE PARSING - Extract student name from filename
# =============================================================================

def parse_filename(filename: str) -> dict:
    """
    Parse student info from filename.
    
    Expected format: FirstName_LastName_AssignmentName.docx
    Examples:
        A'kareah_West_Cornell Notes_ Political Parties.docx
        Eli_Long_Hamilton_Jefferson_Graphic_Organizer.docx
        Gabriella_Bueno_Cornell Notes – The Louisiana Purchase.docx
    
    Returns: {"first_name": ..., "last_name": ..., "assignment_part": ...}
    """
    # Remove extension
    name = Path(filename).stem
    
    # Split by underscore
    parts = name.split('_')
    
    if len(parts) >= 2:
        first_name = parts[0].strip()
        last_name = parts[1].strip()
        assignment_part = '_'.join(parts[2:]) if len(parts) > 2 else ""
        
        return {
            "first_name": first_name,
            "last_name": last_name,
            "assignment_part": assignment_part,
            "lookup_key": f"{first_name} {last_name}".lower()
        }
    else:
        # Can't parse - return filename as-is
        return {
            "first_name": name,
            "last_name": "",
            "assignment_part": "",
            "lookup_key": name.lower()
        }


def read_docx_file(filepath: str) -> str:
    """
    Read text content from a Word document (.docx) in document order.
    This properly interleaves paragraphs and tables as they appear.
    """
    try:
        from docx import Document
        from docx.document import Document as DocType
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError:
        print("❌ python-docx not installed. Run: pip install python-docx")
        return None

    try:
        doc = Document(filepath)
        full_text = []

        # Iterate through document body elements in order
        # This ensures tables and paragraphs appear in their actual document order
        for element in doc.element.body:
            # Check if it's a paragraph
            if element.tag.endswith('p'):
                para = Paragraph(element, doc)
                if para.text.strip():
                    full_text.append(para.text)
            # Check if it's a table
            elif element.tag.endswith('tbl'):
                table = Table(element, doc)
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        full_text.append(' | '.join(row_text))

        return '\n'.join(full_text)
    except Exception as e:
        print(f"  ⚠️  Error reading file: {e}")
        return None


def read_image_file(filepath: str) -> dict:
    """
    Read an image file and return it as base64 for GPT-4o vision.
    
    Returns dict with:
    - type: "image"
    - data: base64 encoded image
    - media_type: image MIME type
    """
    import base64
    
    filepath = Path(filepath)
    extension = filepath.suffix.lower()
    
    # Map extensions to MIME types
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    
    if extension not in mime_types:
        print(f"  ⚠️  Unsupported image type: {extension}")
        return None
    
    try:
        with open(filepath, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        return {
            "type": "image",
            "data": image_data,
            "media_type": mime_types[extension]
        }
    except Exception as e:
        print(f"  ⚠️  Error reading image: {e}")
        return None


def read_assignment_file(filepath: str) -> dict:
    """
    Read assignment file based on its extension.
    Supports: .docx, .txt, .jpg, .jpeg, .png, .gif, .webp
    
    Returns dict with:
    - type: "text" or "image"
    - content: text content or base64 image data
    """
    filepath = Path(filepath)
    extension = filepath.suffix.lower()
    
    # Text-based files
    if extension == '.docx':
        content = read_docx_file(filepath)
        if content:
            return {"type": "text", "content": content}
        return None
    
    elif extension == '.txt':
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return {"type": "text", "content": f.read()}
        except Exception as e:
            print(f"  ⚠️  Error reading text file: {e}")
            return None
    
    # Image files
    elif extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        image_data = read_image_file(filepath)
        if image_data:
            return {
                "type": "image",
                "content": image_data["data"],
                "media_type": image_data["media_type"]
            }
        return None
    
    else:
        print(f"  ⚠️  Unsupported file type: {extension}")
        return None


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


# =============================================================================
# FERPA COMPLIANCE - PII SANITIZATION
# =============================================================================

import hashlib

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


def log_pii_sanitization(student_name: str, original_len: int, sanitized_len: int, removals: dict):
    """
    Log PII sanitization actions for audit purposes.
    Does not log actual PII - only counts and types of removals.
    """
    # This could be extended to write to an audit log file
    if any(removals.values()):
        print(f"  🔒 PII sanitized for student submission (removed: {', '.join(k for k, v in removals.items() if v > 0)})")


# =============================================================================
# AI/PLAGIARISM DETECTION (Parallel Agent using GPT-4o-mini)
# =============================================================================

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

        # Check if this line matches a template pattern
        is_template = False
        for pattern in template_patterns:
            if re.match(pattern, line_stripped, re.IGNORECASE):
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

        # Keep substantive student-written content (paragraphs, explanations)
        # Must be more than 30 chars to be considered "writing" vs labels
        # Exclude lines that are questions (end with ?) or instruction text
        if len(line_stripped) > 30 and not line_stripped.endswith('?'):
            # Skip lines that look like unanswered template text
            instruction_keywords = ['write a few sentences', 'explain in your own words',
                                   'how do you think', 'why do you think', 'what do you think',
                                   'describe how', 'explain how', 'explain why']
            is_instruction = any(kw in line_stripped.lower() for kw in instruction_keywords)
            if not is_instruction:
                student_written.append(line_stripped)

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


def detect_ai_plagiarism(student_responses: str, grade_level: str = '6') -> dict:
    """
    Dedicated AI/Plagiarism detection using GPT-4o-mini.
    Runs in parallel with grading for speed.

    Returns:
        {
            "ai_detection": {"flag": "none/unlikely/possible/likely", "confidence": 0-100, "reason": "..."},
            "plagiarism_detection": {"flag": "none/possible/likely", "reason": "..."}
        }
    """
    # Skip detection if no substantial content to analyze
    # (e.g., fill-in-the-blank only assignments with short factual answers)
    if not student_responses or len(student_responses.strip()) < 50:
        return {
            "ai_detection": {"flag": "none", "confidence": 0, "reason": "Fill-in-the-blank or short-answer only - exempt from AI detection"},
            "plagiarism_detection": {"flag": "none", "reason": "Fill-in-the-blank or short-answer only - exempt from plagiarism detection"}
        }

    try:
        from openai import OpenAI
    except ImportError:
        return {"ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
                "plagiarism_detection": {"flag": "none", "reason": ""}}

    client = OpenAI(api_key=OPENAI_API_KEY)

    age_range = "11-12" if grade_level == "6" else "12-13" if grade_level == "7" else "13-14"

    detection_prompt = f"""You are an expert at detecting AI-generated content and plagiarism in student work.
Analyze this grade {grade_level} student's responses ({age_range} years old) for signs of AI use or copy-paste.

DETECTION CRITERIA:

1. AI-GENERATED CONTENT - Flag as "likely" if you see:
- Sophisticated vocabulary a {age_range} year old wouldn't use: "ideology", "emphasizing", "implementing", "interconnected", "fostering", "trajectory"
- Perfect grammar and sentence structure throughout
- Academic/formal tone: "This demonstrates...", "It is important to note...", "Furthermore..."
- Phrases like: "transforming a limited mission", "securing vital trade routes", "fundamentally altered"

2. PLAGIARISM/COPY-PASTE - Flag as "likely" if you see:
- Dictionary-perfect definitions (e.g., "exclusive possession or control of the supply of or trade in a commodity or service" for monopoly)
- Wikipedia-style language that doesn't match a child's writing
- Textbook phrases copied verbatim
- Sudden shifts between simple spelling errors and sophisticated paragraphs

3. CONTRAST CHECK (MOST IMPORTANT):
- If student writes simple answers like "it made the US bigger", "idk", misspells words
- BUT also writes "an ideology emphasizing intense loyalty to one's nation"
- That is 100% copy-paste - flag PLAGIARISM as "likely"

REAL {age_range} YEAR OLD WRITES:
- "when one company controls everything" (for monopoly)
- "it helped them trade stuff"
- "so boats could go there"

AI/COPIED TEXT LOOKS LIKE:
- "exclusive possession or control of the supply of or trade in a commodity or service"
- "government-provided financial incentives"
- "implementing three interconnected policies"

STUDENT RESPONSES TO ANALYZE:
{student_responses}

Respond ONLY with this JSON (no other text):
{{
    "ai_detection": {{
        "flag": "<none, unlikely, possible, or likely>",
        "confidence": <0-100>,
        "reason": "<specific phrases that triggered the flag, or empty string if none>"
    }},
    "plagiarism_detection": {{
        "flag": "<none, possible, or likely>",
        "reason": "<specific copied phrases found, or empty string if none>"
    }}
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap for detection
            messages=[{"role": "user", "content": detection_prompt}],
            max_tokens=500,
            temperature=0.1  # Low temperature for consistent detection
        )

        response_text = response.choices[0].message.content.strip()

        # Clean markdown if present
        if response_text.startswith("```"):
            lines = response_text.split('\n')
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines)
            for i in range(len(lines)-1, -1, -1):
                if lines[i].strip() == "```":
                    end = i
                    break
            response_text = '\n'.join(lines[start:end])

        result = json.loads(response_text)
        return result

    except Exception as e:
        print(f"  ⚠️  Detection error: {e}")
        return {
            "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
            "plagiarism_detection": {"flag": "none", "reason": ""}
        }


def grade_with_ensemble(student_name: str, assignment_data: dict, custom_ai_instructions: str = '',
                        grade_level: str = '6', subject: str = 'Social Studies',
                        ensemble_models: list = None, student_id: str = None,
                        assignment_template: str = None, rubric_prompt: str = None,
                        custom_markers: list = None, exclude_markers: list = None,
                        marker_config: list = None, effort_points: int = 15) -> dict:
    """
    Grade assignment using multiple AI models and combine results.

    Args:
        ensemble_models: List of model names to use (e.g., ['gpt-4o-mini', 'claude-haiku', 'gemini-flash'])
        marker_config: List of marker configs with points for section-based grading
        effort_points: Points for effort/engagement category (default 15)

    Returns:
        Combined result with:
        - score: Average of all model scores
        - ensemble_scores: Individual scores from each model
        - ensemble_feedback: Feedback from each model
        - letter_grade: Based on averaged score
    """
    if not ensemble_models or len(ensemble_models) < 2:
        # Fall back to single model grading
        model = ensemble_models[0] if ensemble_models else 'gpt-4o-mini'
        return grade_with_parallel_detection(student_name, assignment_data, custom_ai_instructions,
                                             grade_level, subject, model, student_id,
                                             assignment_template, rubric_prompt, custom_markers, exclude_markers,
                                             marker_config, effort_points)

    print(f"  🎯 Ensemble grading with {len(ensemble_models)} models: {', '.join(ensemble_models)}")

    # Run all models in parallel
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ensemble_models)) as executor:
        futures = {}
        for model in ensemble_models:
            future = executor.submit(
                grade_assignment, student_name, assignment_data, custom_ai_instructions,
                grade_level, subject, model, student_id, assignment_template, rubric_prompt,
                custom_markers, exclude_markers, marker_config, effort_points
            )
            futures[future] = model

        # Collect results
        for future in concurrent.futures.as_completed(futures):
            model = futures[future]
            try:
                result = future.result()
                results[model] = result
                print(f"    ✓ {model}: {result.get('score', 0)} ({result.get('letter_grade', 'N/A')})")
            except Exception as e:
                print(f"    ✗ {model}: Error - {str(e)[:50]}")
                results[model] = {"score": 0, "letter_grade": "ERROR", "feedback": f"Error: {e}"}

    # Calculate ensemble score
    valid_scores = [r.get('score', 0) for r in results.values() if r.get('letter_grade') != 'ERROR']
    if not valid_scores:
        return {"score": 0, "letter_grade": "ERROR", "feedback": "All models failed", "breakdown": {}}

    # Use median for robustness against outliers
    valid_scores.sort()
    if len(valid_scores) % 2 == 0:
        median_score = (valid_scores[len(valid_scores)//2 - 1] + valid_scores[len(valid_scores)//2]) / 2
    else:
        median_score = valid_scores[len(valid_scores)//2]

    avg_score = sum(valid_scores) / len(valid_scores)
    final_score = round(median_score)  # Use median as final

    # Determine letter grade
    if final_score >= 90:
        letter_grade = "A"
    elif final_score >= 80:
        letter_grade = "B"
    elif final_score >= 70:
        letter_grade = "C"
    elif final_score >= 60:
        letter_grade = "D"
    else:
        letter_grade = "F"

    # Pick the best feedback (from the model closest to median score)
    best_model = min(results.keys(), key=lambda m: abs(results[m].get('score', 0) - median_score) if results[m].get('letter_grade') != 'ERROR' else 999)
    best_result = results[best_model]

    # Build ensemble result
    ensemble_result = {
        "score": final_score,
        "letter_grade": letter_grade,
        "feedback": best_result.get("feedback", ""),
        "breakdown": best_result.get("breakdown", {}),
        "ai_detection": best_result.get("ai_detection", {}),
        "plagiarism_detection": best_result.get("plagiarism_detection", {}),
        "student_responses": best_result.get("student_responses", []),
        "unanswered_questions": best_result.get("unanswered_questions", []),
        # Ensemble-specific fields
        "ensemble_grading": True,
        "ensemble_models": ensemble_models,
        "ensemble_scores": {model: results[model].get("score", 0) for model in results},
        "ensemble_grades": {model: results[model].get("letter_grade", "N/A") for model in results},
        "ensemble_avg": round(avg_score, 1),
        "ensemble_median": round(median_score, 1),
        "ensemble_feedback_source": best_model,
    }

    print(f"  📊 Ensemble result: {final_score} ({letter_grade}) - avg: {avg_score:.1f}, median: {median_score:.1f}")

    return ensemble_result


def grade_with_parallel_detection(student_name: str, assignment_data: dict, custom_ai_instructions: str = '',
                                   grade_level: str = '6', subject: str = 'Social Studies',
                                   ai_model: str = 'gpt-4o-mini', student_id: str = None,
                                   assignment_template: str = None, rubric_prompt: str = None,
                                   custom_markers: list = None, exclude_markers: list = None,
                                   marker_config: list = None, effort_points: int = 15) -> dict:
    """
    Grade assignment with parallel AI/plagiarism detection.
    Runs detection (GPT-4o-mini) and grading simultaneously for speed.

    Args:
        rubric_prompt: Custom rubric prompt string from Settings (overrides default)
        marker_config: List of marker configs with points for section-based grading
        effort_points: Points for effort/engagement category (default 15)
    """
    # Extract responses first (needed for both detection and grading context)
    content = assignment_data.get("content", "")
    extracted_text = ""

    if assignment_data.get("type") == "text" and content:
        extraction_result = extract_student_responses(content, custom_markers, exclude_markers)
        if extraction_result.get("extracted_responses"):
            extracted_text = "\n".join([
                f"Q: {r.get('question', 'Unknown')}\nA: {r.get('answer', '')}"
                for r in extraction_result["extracted_responses"]
            ])

    # If no extracted text, can't do parallel detection
    if not extracted_text:
        return grade_assignment(student_name, assignment_data, custom_ai_instructions,
                               grade_level, subject, ai_model, student_id, assignment_template, rubric_prompt,
                               custom_markers, exclude_markers, marker_config, effort_points)

    print(f"  🔄 Running parallel detection + grading...")

    # Preprocess text for AI detection (removes template text, focuses on student writing)
    detection_text = preprocess_for_ai_detection(extracted_text)

    # Run detection and grading in parallel using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both tasks
        detection_future = executor.submit(detect_ai_plagiarism, detection_text, grade_level)
        grading_future = executor.submit(grade_assignment, student_name, assignment_data,
                                         custom_ai_instructions, grade_level, subject,
                                         ai_model, student_id, assignment_template, rubric_prompt,
                                         custom_markers, exclude_markers, marker_config, effort_points)

        # Wait for both to complete
        detection_result = detection_future.result()
        grading_result = grading_future.result()

    # Merge detection results into grading results
    # Detection agent's flags override grading agent's (more specialized)
    detection_ai = detection_result.get("ai_detection", {})
    detection_plag = detection_result.get("plagiarism_detection", {})

    grading_ai = grading_result.get("ai_detection", {})
    grading_plag = grading_result.get("plagiarism_detection", {})

    # Use the more severe flag from either source
    flag_severity = {"none": 0, "unlikely": 1, "possible": 2, "likely": 3}

    # AI detection - take the higher severity
    if flag_severity.get(detection_ai.get("flag", "none"), 0) >= flag_severity.get(grading_ai.get("flag", "none"), 0):
        grading_result["ai_detection"] = detection_ai
        if detection_ai.get("flag") in ["possible", "likely"]:
            print(f"  🤖 Detection agent flagged AI: {detection_ai.get('flag')} - {detection_ai.get('reason', '')[:100]}")

    # Plagiarism detection - take the higher severity
    if flag_severity.get(detection_plag.get("flag", "none"), 0) >= flag_severity.get(grading_plag.get("flag", "none"), 0):
        grading_result["plagiarism_detection"] = detection_plag
        if detection_plag.get("flag") in ["possible", "likely"]:
            print(f"  📋 Detection agent flagged plagiarism: {detection_plag.get('flag')} - {detection_plag.get('reason', '')[:100]}")

    # Apply score caps based on detection flags
    ai_flag = grading_result.get("ai_detection", {}).get("flag", "none")
    plag_flag = grading_result.get("plagiarism_detection", {}).get("flag", "none")
    original_score = grading_result.get("score", 0)

    # Determine cap based on flags
    cap = 100
    cap_reason = ""

    if ai_flag == "likely" and plag_flag == "likely":
        cap = 40
        cap_reason = "AI + Plagiarism detected"
    elif ai_flag == "likely":
        cap = 50
        cap_reason = "Likely AI-generated"
    elif plag_flag == "likely":
        cap = 50
        cap_reason = "Likely plagiarized"
    elif ai_flag == "possible":
        cap = 65
        cap_reason = "Possible AI use"
    elif plag_flag == "possible":
        cap = 65
        cap_reason = "Possible plagiarism"

    # Apply cap if needed
    if original_score > cap:
        grading_result["score"] = cap
        grading_result["score_capped"] = True
        grading_result["original_score"] = original_score
        grading_result["cap_reason"] = cap_reason
        # Update letter grade
        if cap <= 59:
            grading_result["letter_grade"] = "F"
        elif cap <= 69:
            grading_result["letter_grade"] = "D"
        elif cap <= 79:
            grading_result["letter_grade"] = "C"
        print(f"  ⚠️  Score capped: {original_score} → {cap} ({cap_reason})")

    # Replace feedback with academic integrity message for high AI/plagiarism likelihood
    # But NOT for blank submissions (they get their own feedback)
    ai_confidence = grading_result.get("ai_detection", {}).get("confidence", 0)
    student_responses = grading_result.get("student_responses", [])
    # Empty list = blank submission, UNLESS we recovered from JSON error (then we don't know)
    is_blank = not student_responses and not grading_result.get("json_recovery")

    if is_blank:
        # Blank submission - use clear feedback, skip academic integrity check
        grading_result["feedback"] = "You submitted a blank assignment. Please resubmit a completed version."
        grading_result["score"] = 0
        grading_result["letter_grade"] = "F"
        print(f"  📝 Blank submission detected")
    elif ai_confidence >= 50 or plag_flag in ["possible", "likely"]:
        grading_result["original_feedback"] = grading_result.get("feedback", "")
        grading_result["feedback"] = "Please resubmit using your own words. Copying and pasting from Google (plagiarism) or use of AI is considered a violation of academic integrity."
        grading_result["academic_integrity_flag"] = True
        print(f"  🚨 Academic integrity concern - feedback replaced")

    return grading_result


# =============================================================================
# SECTION-BASED RUBRIC BUILDER
# =============================================================================

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

    rubric_lines.append("""
GRADING RULES:
- Grade each section out of its assigned points
- BLANK SECTION = 0 POINTS for that section (no partial credit)
- For fill-blank sections: each correct answer is worth proportional points
- For written sections: grade on quality, completeness, and effort
- Effort & Engagement is based on overall presentation and engagement
- Accept reasonable synonyms and alternate phrasings
- Minor spelling errors should NOT be penalized if meaning is clear

In your JSON output, include a "section_scores" field with each section's earned points.
""")

    return "\n".join(rubric_lines)


# =============================================================================
# AI GRADING WITH CLAUDE
# =============================================================================

def grade_assignment(student_name: str, assignment_data: dict, custom_ai_instructions: str = '', grade_level: str = '6', subject: str = 'Social Studies', ai_model: str = 'gpt-4o-mini', student_id: str = None, assignment_template: str = None, rubric_prompt: str = None, custom_markers: list = None, exclude_markers: list = None, marker_config: list = None, effort_points: int = 15) -> dict:
    """
    Use OpenAI GPT to grade a student assignment.

    FERPA COMPLIANCE: Student name is NOT sent to OpenAI.
    We use "Student" as a placeholder to protect privacy.

    Supports both text and image inputs.

    Parameters:
    - student_name: Name of the student (kept local, not sent to API)
    - assignment_data: dict with "type" ("text" or "image") and "content"
    - custom_ai_instructions: Additional grading instructions from the teacher
    - grade_level: The student's grade level (e.g., '6', '7', '8')
    - subject: The subject being graded (e.g., 'Social Studies', 'English/ELA')
    - ai_model: OpenAI model to use ('gpt-4o' or 'gpt-4o-mini')
    - assignment_template: The original assignment template with all questions (for context)

    Returns dict with:
    - score: numeric grade (0-100)
    - letter_grade: A, B, C, D, or F
    - feedback: detailed feedback for the student
    - breakdown: points for each rubric category
    - authenticity_flag: 'clean', 'review', or 'flagged'
    - authenticity_reason: Explanation for flagged or review status
    """
    # Determine which API to use based on model name
    if ai_model.startswith("claude"):
        provider = "anthropic"
    elif ai_model.startswith("gemini"):
        provider = "gemini"
    else:
        provider = "openai"

    # Initialize the appropriate client
    if provider == "anthropic":
        try:
            import anthropic
        except ImportError:
            print("❌ anthropic not installed. Run: pip install anthropic")
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Anthropic API not available - pip install anthropic"}

        if not ANTHROPIC_API_KEY:
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Anthropic API key not configured"}

        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        claude_model_map = {
            "claude-haiku": "claude-3-5-haiku-latest",
            "claude-sonnet": "claude-sonnet-4-20250514",
            "claude-opus": "claude-opus-4-20250514",
        }
        actual_model = claude_model_map.get(ai_model, "claude-3-5-haiku-latest")
        print(f"  🤖 Using Claude model: {actual_model}")

    elif provider == "gemini":
        try:
            import google.generativeai as genai
        except ImportError:
            print("❌ google-generativeai not installed. Run: pip install google-generativeai")
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Google AI not available - pip install google-generativeai"}

        if not GEMINI_API_KEY:
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Gemini API key not configured"}

        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model_map = {
            "gemini-flash": "gemini-2.0-flash",
            "gemini-pro": "gemini-2.0-pro-exp",
        }
        actual_model = gemini_model_map.get(ai_model, "gemini-2.0-flash")
        gemini_client = genai.GenerativeModel(actual_model)
        print(f"  🤖 Using Gemini model: {actual_model}")

    else:  # OpenAI
        try:
            from openai import OpenAI
        except ImportError:
            print("❌ openai not installed. Run: pip install openai")
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "OpenAI API not available"}

        openai_client = OpenAI(api_key=OPENAI_API_KEY)

    # Check for empty/blank student submissions before sending to API
    content = assignment_data.get("content", "")
    if assignment_data.get("type") == "text" and content:
        import re

        # Method 1: Check for filled-in blanks (text between underscores like ___answer___)
        filled_blanks = re.findall(r'_{2,}([^_\n]+)_{2,}', content)
        filled_blanks = [b.strip() for b in filled_blanks if b.strip() and len(b.strip()) > 1]

        # Method 2: Check for content after colons that isn't just blanks
        # e.g., "Nationalism: the belief that..." vs "Nationalism: ___"
        after_colons = re.findall(r':\s*([^_\n:]{10,})', content)
        after_colons = [a.strip() for a in after_colons if a.strip() and not a.strip().startswith('_')]

        # Method 3: Look for paragraph-length responses (likely written answers)
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 50]
        # Filter out paragraphs that are mostly underscores
        real_paragraphs = [p for p in paragraphs if p.count('_') < len(p) * 0.3]

        # Method 4: Count lines that are JUST underscores (blank response lines)
        blank_lines = len(re.findall(r'^[\s_]+$', content, re.MULTILINE))
        total_lines = len([l for l in content.split('\n') if l.strip()])
        blank_ratio = blank_lines / max(total_lines, 1)

        # Method 5: Check for questions followed by no response
        # Look for question patterns and check if there's content after them
        lines = content.split('\n')
        unanswered_questions = []
        question_indices = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            # Check if line is a question (ends with ? or starts with number/bullet or is a vocab term with colon)
            is_question = (
                line_stripped.endswith('?') or
                re.match(r'^\d+[\.\)]\s*\w', line_stripped) or  # "1. Question" or "1) Question"
                re.match(r'^[a-zA-Z][\.\)]\s*\w', line_stripped) or  # "a. Question" or "a) Question"
                (line_stripped.endswith(':') and len(line_stripped) > 5 and '_' not in line_stripped)  # "Nationalism:"
            )
            if is_question and len(line_stripped) > 5:
                question_indices.append(i)

        # Check content between consecutive questions
        for idx, q_idx in enumerate(question_indices):
            line_stripped = lines[q_idx].strip()
            # Determine where the next question starts (or end of document)
            next_q_idx = question_indices[idx + 1] if idx + 1 < len(question_indices) else len(lines)

            # Get content between this question and the next
            content_between = []
            for j in range(q_idx + 1, min(next_q_idx, q_idx + 6)):  # Check up to 5 lines after
                if j < len(lines):
                    between_line = lines[j].strip()
                    # Skip empty lines and lines that are just underscores
                    if between_line and not re.match(r'^[_\s\-\.]+$', between_line):
                        # Check if this line has actual content (not just template markers)
                        if len(between_line) > 3 and between_line.count('_') < len(between_line) * 0.5:
                            content_between.append(between_line)

            # If no substantive content found after this question, mark as unanswered
            if not content_between:
                unanswered_questions.append(line_stripped[:60] + "..." if len(line_stripped) > 60 else line_stripped)

        # Determine if submission is blank
        has_filled_blanks = len(filled_blanks) >= 2
        has_written_responses = len(after_colons) >= 2 or len(real_paragraphs) >= 1
        mostly_blank_lines = blank_ratio > 0.4
        many_unanswered = len(unanswered_questions) >= 3

        is_blank = (not has_filled_blanks and not has_written_responses and mostly_blank_lines) or \
                   (many_unanswered and not has_filled_blanks and not has_written_responses)

        if is_blank:
            print(f"  ⚠️  BLANK/EMPTY SUBMISSION DETECTED")
            print(f"      Filled blanks: {len(filled_blanks)}, Written responses: {len(after_colons)}")
            print(f"      Blank line ratio: {blank_ratio:.1%}, Unanswered questions: {len(unanswered_questions)}")
            return {
                "score": 0,
                "letter_grade": "INCOMPLETE",
                "breakdown": {
                    "content_accuracy": 0,
                    "completeness": 0,
                    "critical_thinking": 0,
                    "communication": 0
                },
                "feedback": f"This assignment appears to be incomplete or blank. {len(unanswered_questions)} question(s) were found without responses. Please complete the assignment and resubmit, or see your teacher if you need help.",
                "student_responses": [],
                "unanswered_questions": unanswered_questions[:10],  # Limit to first 10
                "authenticity_flag": "clean",
                "authenticity_reason": "",
                "skills_demonstrated": {}
            }

    # FERPA: Use anonymous placeholder instead of real student name
    anonymous_name = "Student"
    
    # Build custom instructions section if provided
    custom_section = ''
    if custom_ai_instructions:
        custom_section = f"""
---
TEACHER'S GRADING INSTRUCTIONS (FOLLOW THESE CAREFULLY):
{custom_ai_instructions}
---
"""

    # Build student history context for personalized feedback
    history_context = ''
    if student_id and student_id != "UNKNOWN":
        try:
            history_context = build_history_context(student_id)
        except Exception as e:
            print(f"  Note: Could not load student history: {e}")

    # Build accommodation context for IEP/504 students (FERPA compliant)
    # NOTE: Only accommodation TYPE is sent to AI - no student identifying info
    accommodation_context = ''
    if student_id and student_id != "UNKNOWN":
        try:
            accommodation_context = build_accommodation_prompt(student_id)
            if accommodation_context:
                print(f"  Applying accommodations for student")
        except Exception as e:
            print(f"  Note: Could not load accommodations: {e}")

    # PRE-EXTRACT student responses to prevent AI hallucination
    extraction_result = None
    extracted_responses_text = ''
    if assignment_data.get("type") == "text" and content:
        # Debug: Log markers being used
        marker_count = len(custom_markers) if custom_markers else 0
        print(f"  🔍 Extraction using {marker_count} markers")
        if custom_markers and marker_count > 0:
            for i, m in enumerate(custom_markers[:3]):  # Show first 3
                marker_text = m.get('start', m) if isinstance(m, dict) else m
                print(f"      Marker {i+1}: {marker_text[:50]}...")

        extraction_result = extract_student_responses(content, custom_markers, exclude_markers)
        if extraction_result:
            extracted_responses_text = format_extracted_for_grading(extraction_result, marker_config)
            answered = extraction_result.get("answered_questions", 0)
            total = extraction_result.get("total_questions", 0)
            print(f"  📋 Pre-extracted {answered}/{total} responses")

            # If no responses found, return early with 0 score
            if answered == 0:
                print(f"  ⚠️  NO RESPONSES EXTRACTED - Document is blank or markers don't match")
                return {
                    "score": 0,
                    "letter_grade": "INCOMPLETE",
                    "breakdown": {
                        "content_accuracy": 0,
                        "completeness": 0,
                        "critical_thinking": 0,
                        "communication": 0
                    },
                    "feedback": "This assignment appears to be blank or incomplete. No student responses were found. Please complete the assignment and resubmit.",
                    "student_responses": [],
                    "unanswered_questions": extraction_result.get("blank_questions", []),
                    "authenticity_flag": "clean",
                    "authenticity_reason": "",
                    "skills_demonstrated": {},
                    "extraction_result": extraction_result
                }

    # Analyze current submission's writing style for AI detection
    writing_style_context = ''
    current_writing_style = None
    style_comparison = None
    if assignment_data.get("type") == "text" and content:
        current_writing_style = analyze_writing_style(content)
        if current_writing_style:
            # Get student's historical writing profile
            historical_profile = get_writing_profile(student_id) if student_id and student_id != "UNKNOWN" else None

            if historical_profile and historical_profile.get("sample_count", 0) >= 2:
                # Compare current vs historical style
                style_comparison = compare_writing_styles(current_writing_style, historical_profile)

                if style_comparison.get("ai_likelihood") in ["likely", "possible"]:
                    print(f"  ⚠️  Writing style deviation detected: {style_comparison.get('deviation')}")
                    writing_style_context = f"""
---
WRITING STYLE ANALYSIS (COMPARE TO STUDENT'S HISTORY):
This student's historical writing profile (based on {historical_profile.get('sample_count', 0)} previous assignments):
- Average complexity score: {historical_profile.get('avg_complexity_score', 'N/A')}/10
- Average sentence length: {historical_profile.get('avg_sentence_length', 'N/A')} words
- Average word length: {historical_profile.get('avg_word_length', 'N/A')} characters
- Typical academic vocabulary: {historical_profile.get('avg_academic_words', 0):.1f} words per submission

Current submission analysis:
- Complexity score: {current_writing_style.get('complexity_score', 'N/A')}/10
- Sentence length: {current_writing_style.get('avg_sentence_length', 'N/A')} words
- Word length: {current_writing_style.get('avg_word_length', 'N/A')} characters
- Academic vocabulary count: {current_writing_style.get('academic_word_count', 0)}

DEVIATION ALERT: {'; '.join(style_comparison.get('deviations', []))}
This suggests possible AI use - be extra vigilant in your authenticity check!
---
"""

    # Map grade level to age range for context
    grade_age_map = {
        'K': '5-6', '1': '6-7', '2': '7-8', '3': '8-9', '4': '9-10', '5': '10-11',
        '6': '11-12', '7': '12-13', '8': '13-14', '9': '14-15', '10': '15-16',
        '11': '16-17', '12': '17-18'
    }
    age_range = grade_age_map.get(str(grade_level), '11-12')

    # Build extracted responses section for the prompt
    extracted_responses_section = ""
    if extracted_responses_text:
        extracted_responses_section = f"""
---
{extracted_responses_text}
---
"""

    # Build assignment template section (provides question context)
    assignment_template_section = ""
    if assignment_template:
        # Truncate if very long to save tokens
        template_text = assignment_template[:8000] if len(assignment_template) > 8000 else assignment_template
        assignment_template_section = f"""
---
ASSIGNMENT TEMPLATE (The questions/prompts the student was asked to answer):
{template_text}
---
"""

    # Use custom rubric if provided, otherwise use default
    # If marker_config is provided, build a section-based rubric
    section_rubric = ""
    if marker_config:
        section_rubric = build_section_rubric(marker_config, effort_points)

    effective_rubric = rubric_prompt if rubric_prompt else GRADING_RUBRIC

    prompt_text = f"""
{effective_rubric}

{section_rubric}

{ASSIGNMENT_INSTRUCTIONS}
{custom_section}
{accommodation_context}
{history_context}
{writing_style_context}
{assignment_template_section}
---

STUDENT CONTEXT:
- Grade Level: {grade_level}
- Subject: {subject}
- Expected Age Range: {age_range} years old

{extracted_responses_section}

CRITICAL - PRE-EXTRACTED RESPONSES:
The student responses have been PRE-EXTRACTED from the document and listed above.
DO NOT invent or hallucinate any responses that are not in the VERIFIED STUDENT RESPONSES section.
ONLY grade the responses that were explicitly extracted and shown to you.
If a question is listed as "UNANSWERED", it means the student left it blank - do not imagine an answer.

IMPORTANT: Only assess sections that appear in the extracted responses above.
If a section (like "Notes Section") was NOT extracted, it means the teacher did NOT require it for grading.
Do NOT penalize students for sections that were not marked for grading by the teacher.
Only the extracted/marked sections count toward the grade.

Your "student_responses" field MUST contain ONLY the raw answer text from each "STUDENT ANSWER:" line above.
Do NOT include question numbers, section names, or labels like "[1] Summary:" - just the student's actual written text.
Example: If the verified response shows 'STUDENT ANSWER: "The treaty was signed in 1803"', your student_responses should contain "The treaty was signed in 1803" - not "Summary: The treaty was signed in 1803".
If no responses were extracted, the student gets a 0.

For MATCHING exercises specifically:
- Look for numbers placed next to vocabulary terms in the extracted responses
- The number indicates which definition the student chose
- Grade whether they matched correctly

GRADING GUIDELINES:
- Assess EVERY answer the student provided.
- For fill-in-the-blank: check if the answer is factually correct or close enough.
- Accept multiple valid answers and synonyms.
- DO NOT penalize spelling mistakes if the meaning is clear.
- Be age-appropriate - these are grade {grade_level} students ({age_range} years old).
- IMPORTANT: If the teacher provided custom grading instructions above, follow them carefully.

CRITICAL - COMPLETENESS REQUIREMENTS:
- ONLY check completeness for sections that appear in the EXTRACTED RESPONSES above.
- If a section was NOT extracted (not listed above), the teacher did NOT require it - do NOT penalize for it.
- For the sections that WERE extracted, check if the student answered them, especially:
  * "Explain in your own words" sections - these require written responses, not blank
  * "Reflection" or "Final Reflection" questions - these MUST be answered
  * "Student Task" sections - these are major components requiring written responses
  * Any prompt asking students to "Write a few sentences" or "Describe" or "Explain"
  * Summary sections (only if they were extracted/marked)
  * Primary source analysis tasks (only if they were extracted/marked)
- Skipping EXTRACTED/MARKED written sections shows AVOIDANCE OF EFFORT and must be penalized!
- EACH SKIPPED SECTION LOWERS THE GRADE BY ONE FULL LETTER:
  * 0 sections skipped = eligible for A (90-100)
  * 1 section skipped = maximum B (80-89) - dropped one letter
  * 2 sections skipped = maximum C (70-79) - dropped two letters
  * 3 sections skipped = maximum D (60-69) - dropped three letters
  * 4+ sections skipped = F (below 60) - shows no effort on written work
- Students who ONLY do fill-in-the-blanks and skip ALL written responses = maximum C (75)
- An "A" grade (90+) is ONLY possible if ALL sections are completed with quality responses
- This applies to ALL assignments - skipping reflections, explanations, or analysis tasks is unacceptable
- List ALL skipped/unanswered questions in the "unanswered_questions" field

CRITICAL - AUTHENTICITY CHECKS (YOU MUST CHECK THIS CAREFULLY!):

1. AI DETECTION - Compare the student's simple answers to their written paragraphs:
STEP 1: Look at their short answers (fill-in-blanks, one-word responses). Note the vocabulary level.
STEP 2: Look at their paragraph responses. Compare the vocabulary and complexity.
STEP 3: If there's a MISMATCH (simple short answers but sophisticated paragraphs), flag as "likely" AI.

AUTOMATIC "likely" AI FLAGS - if you see ANY of these phrases, it's 100% AI:
- "transformed the nation into a continental power"
- "transforming a limited mission"
- "historic deal that doubled"
- "fueling westward expansion"
- "triggered intense political debates"
- "spurred exploration"
- "fundamentally altered the trajectory"
- "establishing the precedent for"
- "constitutional questions regarding federal authority"
- "resonate through subsequent decades"
- "vital for trade and growth"
- "securing vital trade routes"
- "manifest destiny"
- "territorial expansion"
- "abundant natural resources"
- Any phrase starting with "Transforming...", "Establishing...", "Securing..."
- Any phrase a {age_range} year old would NEVER write

CRITICAL CONTRAST CHECK - THIS IS THE MOST IMPORTANT CHECK:
Look at the student's spelling and grammar in simple answers. If they write:
- Misspellings like "Tomas Jefferson", "the u's", "france" (lowercase)
- Simple phrases like "It doubled in size", "idk"
- Basic vocabulary and short sentences

BUT THEN write sophisticated phrases like:
- "Transforming a limited mission to buy New Orleans into a historic deal"
- Any sentence with words like "vital", "securing", "expanding", "historic deal"

That is 100% AI or copied - flag as "likely" IMMEDIATELY. A student who misspells "Thomas" does NOT write "transforming a limited mission into a historic deal."

Real grade {grade_level} students write: "it made the US bigger", "they needed the river for boats", "so ships could go there"
AI writes: "it transformed the nation into a continental power", "securing vital trade routes"

OBVIOUS COPY-PASTE DEFINITIONS (flag as PLAGIARISM "likely" IMMEDIATELY):
- "exclusive possession or control of the supply of or trade in a commodity or service" = Google definition of monopoly
- "an ideology emphasizing intense loyalty to one's nation" = textbook definition
- "government-provided financial incentives" = too sophisticated
- "implementing three interconnected policies" = not student language
- "authority not explicitly stated in the U.S. Constitution but deemed necessary" = textbook definition of implied powers
- ANY definition that sounds like it was copied from a dictionary or Wikipedia = PLAGIARISM

A real {age_range} year old defines monopoly as: "when one company controls everything" or "only one person sells something"
NOT: "exclusive possession or control of the supply of or trade in a commodity or service"

2. PLAGIARISM DETECTION - Look for:
- SUDDEN SHIFTS in writing quality (simple answers + sophisticated paragraphs = copied/AI)
- Textbook-perfect definitions that don't match the student's other answers
- Phrases that sound memorized or copied verbatim
- Statistics or specific numbers not in the reading (like "828,000 square miles")
- DICTIONARY DEFINITIONS - If a vocabulary definition sounds like it was copied from Google/dictionary (e.g., "exclusive possession or control of the supply of or trade in a commodity or service" for monopoly), flag as PLAGIARISM "likely"
- SOPHISTICATED VOCABULARY MISMATCH - Words like "ideology", "emphasizing", "fostering", "interconnected", "implementing" are NOT how grade {grade_level} students write definitions
- FRAGMENT ANSWERS that are clearly pasted (no complete sentence, just a definition dump)
- If student writes simple answers for some questions but sophisticated definitions for vocabulary = COPY/PASTE from Google

HARD CAPS FOR AI USE / PLAGIARISM (apply FIRST, before other caps):
- AI flag "likely" = MAX score is 50 (F) - this is cheating
- AI flag "possible" = MAX score is 65 (D) - suspicious, needs verification
- Plagiarism flag "likely" = MAX score is 50 (F) - this is cheating
- Plagiarism flag "possible" = MAX score is 65 (D) - suspicious
- If BOTH AI and plagiarism are flagged = MAX score is 40 (F)

In feedback for AI/plagiarism flags:
- Clearly state the work appears to be AI-generated or copied
- Explain that academic integrity is important
- Recommend the student redo the assignment in their own words
- Note this will be reviewed by the teacher

THEN apply HARD CAPS FOR INCOMPLETE WORK (MANDATORY - each skipped section = one letter grade drop):
Count the number of skipped/unanswered written sections (Student Task, Reflection, Explain, etc.):
- 0 skipped = eligible for A (up to 100)
- 1 skipped = MAXIMUM 89 (B) - NO EXCEPTIONS
- 2 skipped = MAXIMUM 79 (C) - NO EXCEPTIONS
- 3 skipped = MAXIMUM 69 (D) - NO EXCEPTIONS
- 4+ skipped = MAXIMUM 59 (F)
- 5+ skipped = MAXIMUM 49 (F)
- 6+ skipped = MAXIMUM 39 (F)

NEARLY BLANK SUBMISSIONS - Score based on effort shown:
- If student answered only 1-2 questions out of 5+ = score 10-25 (F)
- If student answered only 3-4 questions out of 10+ = score 25-40 (F)
- A single poor answer like "idk" or "going again" does NOT earn 50 points
- The score should reflect ACTUAL WORK DONE, not a default minimum
- Empty or nearly empty = score in the 0-30 range

YOU MUST APPLY THESE CAPS. If a student skipped 2 written sections, their score CANNOT be above 79 even if their fill-in-the-blanks were perfect.

The LOWEST cap wins. Example: AI "likely" (cap 50) + 6 sections skipped (cap 39) = final cap is 39.

Provide your response in the following JSON format ONLY (no other text):
{{
    "score": <FIRST calculate raw score, THEN apply the caps above. If 2 sections skipped, max is 79>,
    "letter_grade": "<A, B, C, D, or F - must match the capped score>",
    "breakdown": {{
        "content_accuracy": <points out of 40 - correctness of answers>,
        "completeness": <points out of 25 - ALL sections must be attempted. Written responses (reflections, explanations, Student Tasks) count heavily! 0-5 if 2+ major sections skipped, 6-12 if 1 major section skipped, 13-20 if minor gaps only, 21-25 only if ALL parts fully completed>,
        "writing_quality": <points out of 20>,
        "effort_engagement": <points out of 15>
    }},
    "student_responses": ["<EXTRACT ONLY the actual answer text that appears after 'STUDENT ANSWER:' in the verified responses above. Do NOT include the question/section name, number, or label. WRONG: 'Summary: The treaty was...' or '[1] Summary: The treaty...' - RIGHT: 'The treaty was signed in 1803 and...' - just the raw answer text the student wrote>"],
    "unanswered_questions": ["<list ALL questions/sections the student left blank or didn't answer - especially written response sections like reflections, explanations, summaries>"],
    "excellent_answers": ["<Quote 2-4 specific answers that were particularly strong, accurate, or showed great understanding. Include the exact text the student wrote.>"],
    "needs_improvement": ["<Quote 1-3 specific answers that were incorrect or incomplete, along with what the correct/better answer would be. Format: 'You wrote [X] but [correct info]' or 'For the question about [topic], [guidance]'>"],
    "skills_demonstrated": {{
        "strengths": ["<List 2-4 specific skills the student showed strength in. Go BEYOND the rubric categories - identify skills like: reading comprehension, critical thinking, source analysis, making connections, vocabulary usage, following directions, organization, creativity, historical thinking, cause-and-effect reasoning, comparing/contrasting, using evidence, drawing conclusions, summarizing, note-taking, attention to detail, etc. Only include skills clearly demonstrated in THIS assignment.>"],
        "developing": ["<List 1-2 skills the student is still developing or struggled with. Same skill types as above. Be specific about what skill needs work based on their answers.>"]
    }},
    "ai_detection": {{
        "flag": "<none, unlikely, possible, or likely>",
        "confidence": <number 0-100 representing confidence in the assessment>,
        "reason": "<Brief explanation if not 'none', otherwise empty string>"
    }},
    "plagiarism_detection": {{
        "flag": "<none, possible, or likely>",
        "reason": "<Brief explanation if not 'none', otherwise empty string>"
    }},
    "feedback": "<Write 3-4 paragraphs of thorough, personalized feedback that sounds like a real teacher wrote it - warm, encouraging, and specific. IMPORTANT GUIDELINES: 1) VARY your sentence structure and openings - don't start every sentence the same way. Mix short punchy sentences with longer ones. 2) QUOTE specific answers from the student's work when praising them (e.g., 'I loved how you explained that [quote their answer]' or 'Your answer about [topic] - '[their exact words]' - shows real understanding'). 3) When mentioning areas to improve, be gentle and constructive - reference specific questions they struggled with and give them a hint or the right direction. 4) Sound HUMAN - use contractions (you're, that's, I'm), occasional casual phrases ('Nice!', 'Great thinking here'), and vary your enthusiasm. 5) End with genuine encouragement that connects to something specific they did well. 6) Do NOT use the student's name - say 'you' or 'your'. 7) Avoid repetitive phrases like 'Great job!' at the start of every paragraph - mix it up! 8) IF STUDENT HISTORY IS PROVIDED ABOVE: Reference their progress! Mention streaks, acknowledge CONSISTENT SKILLS (e.g., 'Your reading comprehension continues to be a real strength!'), celebrate IMPROVING SKILLS (e.g., 'I notice your critical thinking is getting sharper - great progress!'), and gently encourage SKILLS TO DEVELOP (e.g., 'Keep working on making connections between ideas'). Connect current work to past achievements when relevant. 9) BILINGUAL FEEDBACK: ONLY provide bilingual feedback if the student ACTUALLY WROTE their answers in a non-English language. Do NOT assume language based on the student's name - a Hispanic surname does NOT mean the student needs Spanish feedback. Analyze the ACTUAL TEXT of their responses. If (and ONLY if) the student wrote answers in Spanish, Creole, Portuguese, etc., then provide feedback in BOTH English and their language. Format: [English feedback]\\n\\n---\\n\\n[Traducción / Translation]\\n[Same feedback in student's language].>",
    "student_language": "<Detected language based on the ACTUAL TEXT of student's written responses (not their name): 'english', 'spanish', 'portuguese', 'creole', or other. Default to 'english' unless student clearly wrote in another language>"
}}
"""

    print(f"  🤖 Grading with AI...")

    try:
        # FERPA COMPLIANCE: Sanitize PII from text content before sending to AI
        if assignment_data["type"] == "text":
            original_content = assignment_data['content']
            anon_id, sanitized_content = sanitize_pii_for_ai(student_name, original_content)

            # Log if any PII was removed (for audit trail)
            if sanitized_content != original_content:
                print(f"  🔒 PII sanitized from submission before AI processing")

            # HARD BLOCK: Only send extracted responses to prevent hallucination
            # If extraction succeeded, use ONLY extracted responses (not raw content)
            if extracted_responses_text:
                # Send only the pre-extracted verified responses
                print(f"  ✅ Using ONLY pre-extracted responses (hallucination prevention)")
                full_prompt = prompt_text + f"\n\nSTUDENT'S VERIFIED RESPONSES (extracted from document):\n{extracted_responses_text}"
            else:
                # Extraction failed or found nothing - REQUIRES MANUAL REVIEW
                print(f"  ⚠️  HARD BLOCK: No responses extracted - flagging for manual review")
                return {
                    "score": 0,
                    "letter_grade": "MANUAL REVIEW",
                    "breakdown": {
                        "content_accuracy": 0,
                        "completeness": 0,
                        "critical_thinking": 0,
                        "communication": 0
                    },
                    "feedback": "⚠️ MANUAL REVIEW REQUIRED: The automated extraction could not find student responses in this document. This could mean:\n\n1. The document is blank or nearly blank\n2. The formatting is unusual\n3. The student wrote in unexpected locations\n\nPlease open the original document and grade manually to prevent AI hallucination.",
                    "student_responses": [],
                    "unanswered_questions": [],
                    "authenticity_flag": "manual_review",
                    "authenticity_reason": "Extraction failed - cannot verify responses",
                    "skills_demonstrated": {},
                    "requires_manual_review": True
                }
            messages = [{"role": "user", "content": full_prompt}]

        elif assignment_data["type"] == "image":
            # Image-based assignment - use vision
            # WARNING: Cannot extract/verify responses from images - higher hallucination risk
            print(f"  ⚠️  IMAGE SUBMISSION: Cannot pre-extract responses - recommend spot-checking")
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text + "\n\nSTUDENT'S WORK (see attached image):\nIMPORTANT: Only grade what you can CLEARLY see in the image. If text is unclear or cut off, mark as incomplete rather than guessing."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{assignment_data['media_type']};base64,{assignment_data['content']}"
                        }
                    }
                ]
            }]
            # Flag that this is an unverified image submission
            extraction_result = {"type": "image", "verified": False}
        else:
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Unknown content type"}

        # Make API call based on provider
        if provider == "anthropic":
            # Claude API call
            if assignment_data.get("type") == "image":
                claude_content = [
                    {"type": "text", "text": prompt_text + "\n\nSTUDENT'S WORK (see attached image):\nIMPORTANT: Only grade what you can CLEARLY see in the image. If text is unclear or cut off, mark as incomplete rather than guessing."},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": assignment_data['media_type'],
                            "data": assignment_data['content']
                        }
                    }
                ]
            else:
                claude_content = messages[0]["content"] if isinstance(messages[0]["content"], str) else messages[0]["content"][0]["text"]

            response = claude_client.messages.create(
                model=actual_model,
                max_tokens=1500,
                messages=[{"role": "user", "content": claude_content}]
            )
            response_text = response.content[0].text.strip()

        elif provider == "gemini":
            # Gemini API call with retry for rate limits
            import time
            max_retries = 3
            retry_delay = 2  # seconds

            for attempt in range(max_retries):
                try:
                    if assignment_data.get("type") == "image":
                        import base64
                        image_data = base64.b64decode(assignment_data['content'])
                        image_part = {
                            "mime_type": assignment_data['media_type'],
                            "data": image_data
                        }
                        full_prompt = prompt_text + "\n\nSTUDENT'S WORK (see attached image):\nIMPORTANT: Only grade what you can CLEARLY see in the image. If text is unclear or cut off, mark as incomplete rather than guessing."
                        response = gemini_client.generate_content([full_prompt, image_part])
                    else:
                        text_content = messages[0]["content"] if isinstance(messages[0]["content"], str) else messages[0]["content"][0]["text"]
                        response = gemini_client.generate_content(text_content)
                    response_text = response.text.strip()
                    break  # Success, exit retry loop
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        print(f"  ⏳ Rate limited, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise  # Re-raise if not rate limit or out of retries

        else:
            # OpenAI API call
            response = openai_client.chat.completions.create(
                model=ai_model,
                messages=messages,
                max_tokens=1500,
                temperature=0.3
            )
            response_text = response.choices[0].message.content.strip()

        # Clean up response (remove markdown code blocks if present)
        if response_text.startswith("```"):
            lines = response_text.split('\n')
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines)
            for i in range(len(lines)-1, -1, -1):
                if lines[i].strip() == "```":
                    end = i
                    break
            response_text = '\n'.join(lines[start:end])
        response_text = response_text.strip()

        # Fix Claude's malformed JSON:
        # 1. Remove parenthetical comments after string values
        # 2. Add missing commas between properties
        # 3. Escape unescaped newlines inside strings
        import re

        def fix_claude_json(text):
            # First check if already valid
            try:
                json.loads(text)
                return text
            except json.JSONDecodeError:
                pass

            # Fix 0: Handle malformed "reason" fields where AI didn't close the string
            # The AI sometimes outputs: "reason": "\n    },\n    "next_field"
            # This replaces any "reason" field that contains },  or starts with whitespace/newline
            # with an empty string
            fixed = re.sub(r'"reason":\s*"[^"]*\\n[^"]*"', '"reason": ""', text)
            fixed = re.sub(r'"reason":\s*"[\s\n]*\}', '"reason": ""}', fixed)
            fixed = re.sub(r'"reason":\s*"[\s\n]*,', '"reason": "",', fixed)
            # Also fix cases where reason value contains JSON-like content
            fixed = re.sub(r'"reason":\s*"[^"]*\{[^"]*"', '"reason": ""', fixed)

            # Fix 1: Remove parenthetical comments after closing quotes
            fixed = re.sub(r'"\s*\([^)]+\)', '"', fixed)

            # Fix 2: Remove double quotes (Claude sometimes outputs "" instead of ")
            fixed = re.sub(r'""', '"', fixed)

            # Fix 3: Add missing commas - pattern: "value"\n    "key" → "value",\n    "key"
            fixed = re.sub(r'"\s*\n(\s*)"', r'",\n\1"', fixed)

            # Fix 4: Add missing commas after numbers/booleans before string keys
            fixed = re.sub(r'(\d)\s*\n(\s*)"', r'\1,\n\2"', fixed)
            fixed = re.sub(r'(true|false|null)\s*\n(\s*)"', r'\1,\n\2"', fixed)

            # Fix 5: Add missing commas after ] or } before "key"
            fixed = re.sub(r'(\]|\})\s*\n(\s*)"', r'\1,\n\2"', fixed)

            # Fix 6: Escape newlines inside strings (character-by-character)
            result = []
            in_string = False
            i = 0
            while i < len(fixed):
                char = fixed[i]
                if char == '\\' and i + 1 < len(fixed):
                    result.append(char)
                    result.append(fixed[i + 1])
                    i += 2
                    continue
                if char == '"':
                    in_string = not in_string
                    result.append(char)
                    i += 1
                    continue
                if in_string:
                    if char == '\n':
                        result.append('\\n')
                    elif char == '\r':
                        pass
                    elif char == '\t':
                        result.append('\\t')
                    else:
                        result.append(char)
                else:
                    result.append(char)
                i += 1

            return ''.join(result)

        original_text = response_text
        response_text = fix_claude_json(response_text)

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            # Debug: show what we're trying to parse
            print(f"  ⚠️  JSON parse error: {e}")
            print(f"  ⚠️  Error at position {e.pos}, showing context:")
            start = max(0, e.pos - 100)
            end = min(len(response_text), e.pos + 100)
            print(f"  ⚠️  ...{repr(response_text[start:end])}...")

            # Save both original and fixed for comparison
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='_original.json', delete=False) as f:
                f.write(original_text)
                print(f"  ⚠️  Original saved to: {f.name}")
            with tempfile.NamedTemporaryFile(mode='w', suffix='_fixed.json', delete=False) as f:
                f.write(response_text)
                print(f"  ⚠️  Fixed saved to: {f.name}")
            raise

        # Update student's writing profile (only if not flagged as AI)
        # This builds their baseline for future AI detection
        if student_id and student_id != "UNKNOWN" and current_writing_style:
            ai_flag = result.get("ai_detection", {}).get("flag", "none")
            if ai_flag not in ["likely", "possible"]:
                try:
                    update_writing_profile(student_id, current_writing_style, student_name)
                    print(f"  📊 Updated writing profile for {student_name}")
                except Exception as e:
                    print(f"  Note: Could not update writing profile: {e}")

        # Add style comparison info to result for transparency
        if style_comparison and style_comparison.get("ai_likelihood") in ["likely", "possible"]:
            result["writing_style_deviation"] = style_comparison

        return result

    except json.JSONDecodeError as e:
        print(f"  ⚠️  Error parsing AI response: {e}")
        # Try to show response content for debugging
        try:
            raw_preview = response_text[:800] if len(response_text) > 800 else response_text
            print(f"  ⚠️  Raw response preview:\n{raw_preview}")
            # Write full response to temp file for debugging
            import tempfile
            debug_file = tempfile.NamedTemporaryFile(mode='w', suffix='_graider_debug.json', delete=False)
            debug_file.write(response_text)
            debug_file.close()
            print(f"  ⚠️  Full response saved to: {debug_file.name}")
        except:
            print(f"  ⚠️  Could not display response")

        # Try to extract key fields with regex as fallback
        try:
            score_match = re.search(r'"score":\s*(\d+)', response_text)
            grade_match = re.search(r'"letter_grade":\s*"([A-F])"', response_text)
            feedback_match = re.search(r'"feedback":\s*"([^"]{20,500})', response_text)

            if score_match and grade_match:
                print(f"  ✅ Recovered score/grade from malformed JSON")
                return {
                    "score": int(score_match.group(1)),
                    "letter_grade": grade_match.group(1),
                    "breakdown": {"content_accuracy": 0, "completeness": 0, "writing_quality": 0, "effort_engagement": 0},
                    "feedback": feedback_match.group(1) + "..." if feedback_match else "Grading completed but response was malformed.",
                    "student_responses": [],
                    "unanswered_questions": [],
                    "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
                    "plagiarism_detection": {"flag": "none", "reason": ""},
                    "skills_demonstrated": {"strengths": [], "developing": []},
                    "json_recovery": True
                }
        except:
            pass

        return {
            "score": 0,
            "letter_grade": "ERROR",
            "breakdown": {},
            "feedback": f"Error grading - AI returned invalid JSON. Please review manually."
        }
    except Exception as e:
        print(f"  ⚠️  API error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "score": 0,
            "letter_grade": "ERROR",
            "breakdown": {},
            "feedback": f"API error: {e}"
        }


# =============================================================================
# EMAIL GENERATION
# =============================================================================

def generate_email_content(student_info: dict, grade_result: dict, assignment_name: str) -> tuple:
    """
    Generate email subject and body for a student.
    
    Returns: (subject, body)
    """
    first_name = student_info.get('first_name', 'Student').split()[0]  # Just first name
    
    subject = f"Grade for {assignment_name}: {grade_result['letter_grade']}"
    
    body = f"""Hi {first_name},

Here is your grade and feedback for {assignment_name}:

GRADE: {grade_result['score']}/100 ({grade_result['letter_grade']})

FEEDBACK:
{grade_result['feedback']}

If you have any questions about your grade, please see me during class.

- Mr. Crionas US History
"""
    return subject, body


def save_emails_to_folder(grades: list, output_folder: str, teacher_name: str = '', subject: str = '', school_name: str = ''):
    """
    Save emails as individual text files - ONE EMAIL PER STUDENT
    with feedback for ALL their assignments combined.
    """
    email_folder = Path(output_folder) / "emails"
    email_folder.mkdir(parents=True, exist_ok=True)
    
    # Group grades by student
    students = {}
    for grade in grades:
        student_name = grade.get('student_name', 'Unknown')
        if student_name not in students:
            # Get only first name (no middle initial)
            full_first = grade.get('first_name', student_name.split()[0])
            first_only = full_first.split()[0] if full_first else student_name.split()[0]
            students[student_name] = {
                'email': grade.get('email', ''),
                'first_name': first_only,
                'assignments': []
            }
        students[student_name]['assignments'].append(grade)
    
    email_count = 0
    for student_name, data in students.items():
        if not data['email']:
            continue
        
        # Build combined email
        assignments = data['assignments']
        first_name = data['first_name']
        
        # Email subject line
        if len(assignments) == 1:
            email_subject = f"Grade for {assignments[0].get('assignment', 'Assignment')}: {assignments[0]['letter_grade']}"
        else:
            email_subject = f"Grades for {len(assignments)} Assignments"
        
        # Body
        body = f"Hi {first_name},\n\n"
        
        if len(assignments) == 1:
            a = assignments[0]
            body += f"Here is your grade and feedback for {a.get('assignment', 'your assignment')}:\n\n"
            body += f"GRADE: {a['score']}/100 ({a['letter_grade']})\n\n"
            body += f"FEEDBACK:\n{a.get('feedback', 'No feedback available.')}\n"
        else:
            body += "Here are your grades and feedback:\n\n"
            for a in assignments:
                assignment_name = a.get('assignment', 'Assignment')
                body += f"{'='*50}\n"
                body += f"📝 {assignment_name}\n"
                body += f"{'='*50}\n"
                body += f"GRADE: {a['score']}/100 ({a['letter_grade']})\n\n"
                body += f"FEEDBACK:\n{a.get('feedback', 'No feedback available.')}\n\n"
        
        body += "\nIf you have any questions about your grades, please see me during class.\n\n"
        signature = teacher_name if teacher_name else "Your Teacher"
        if subject:
            signature += f" {subject}"
        body += f"- {signature}\n"
        
        # Save file
        safe_name = re.sub(r'[^\w\s-]', '', student_name).replace(' ', '_')
        filepath = email_folder / f"{safe_name}_email.txt"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"TO: {data['email']}\n")
            f.write(f"SUBJECT: {email_subject}\n")
            f.write(f"{'='*50}\n\n")
            f.write(body)
        
        email_count += 1
    
    print(f"📧 Saved {email_count} email files to: {email_folder}")


def create_outlook_drafts(grades: list):
    """
    Create draft emails in Outlook desktop app (Windows only).
    This lets you review each email before sending.
    """
    try:
        import win32com.client
    except ImportError:
        print("⚠️  pywin32 not installed. Run: pip install pywin32")
        print("   Falling back to saving emails as files.")
        return False
    
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        count = 0
        
        for grade in grades:
            if not grade.get('email'):
                continue
                
            subject, body = generate_email_content(grade, grade, ASSIGNMENT_NAME)
            
            mail = outlook.CreateItem(0)  # 0 = mail item
            mail.To = grade['email']
            mail.Subject = subject
            mail.Body = body
            mail.Save()  # Save as draft
            count += 1
        
        print(f"📧 Created {count} draft emails in Outlook")
        return True
        
    except Exception as e:
        print(f"⚠️  Outlook error: {e}")
        return False


# =============================================================================
# CSV EXPORT FOR FOCUS
# =============================================================================

def export_focus_csv(grades: list, output_folder: str, assignment_name: str) -> list:
    """
    Create CSV files formatted for Focus import, SEPARATED BY ASSIGNMENT.
    
    Groups students by the assignment extracted from their filename,
    creates one CSV per assignment type.
    
    Format:
    Student ID,Score,Comment
    1950304,85,"Great job, Jackson! You correctly identified..."
    1956701,92,"Excellent work, Maria!..."
    
    Returns list of created file paths.
    """
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    # Group grades by assignment
    assignments = {}
    for grade in grades:
        # Extract assignment name from filename (everything after FirstName_LastName_)
        filename = grade.get('filename', '')
        parts = Path(filename).stem.split('_')
        if len(parts) >= 3:
            # Assignment is everything after first two parts (first_last)
            assignment = '_'.join(parts[2:])
        else:
            assignment = "Unknown_Assignment"
        
        # Clean up assignment name for display (replace underscores with spaces)
        assignment = assignment.strip().replace('_', ' ')
        
        if assignment not in assignments:
            assignments[assignment] = []
        assignments[assignment].append(grade)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    created_files = []
    
    print(f"\n  Creating {len(assignments)} separate Focus CSVs by assignment:")
    
    for assignment, assignment_grades in assignments.items():
        # Clean assignment name for filename
        safe_name = re.sub(r'[^\w\s-]', '', assignment).replace(' ', '_')[:50]
        filepath = Path(output_folder) / f"{safe_name}_{timestamp}.csv"
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Column headers: Student ID, Score, Comment
            writer.writerow(['Student ID', 'Score', 'Comment'])
            
            for grade in assignment_grades:
                if grade['student_id'] != "UNKNOWN":
                    # Get student's first name only (no middle initial)
                    full_first = grade.get('first_name', '')
                    first_name = full_first.split()[0] if full_first else ''
                    
                    # Clean up feedback
                    feedback = grade.get('feedback', '')
                    feedback_clean = ' '.join(feedback.split())
                    
                    # Varied natural phrases based on grade
                    score = grade.get('score', 0)
                    
                    if first_name:
                        if score >= 90:
                            openers = [
                                f"Great job, {first_name}!",
                                f"Excellent work, {first_name}!",
                                f"{first_name}, this was fantastic!",
                                f"Well done, {first_name}!",
                                f"{first_name}, you nailed this!"
                            ]
                        elif score >= 80:
                            openers = [
                                f"Nice work, {first_name}!",
                                f"Good job, {first_name}!",
                                f"{first_name}, solid effort here!",
                                f"Well done, {first_name}!",
                                f"{first_name}, this was good work!"
                            ]
                        elif score >= 70:
                            openers = [
                                f"{first_name}, decent effort!",
                                f"Good start, {first_name}!",
                                f"{first_name}, you're on the right track!",
                                f"Keep it up, {first_name}!",
                                f"{first_name}, nice try!"
                            ]
                        else:
                            openers = [
                                f"{first_name}, let's work on this together.",
                                f"{first_name}, I know you can do better!",
                                f"Keep trying, {first_name}!",
                                f"{first_name}, don't give up!",
                                f"{first_name}, let's review this."
                            ]
                        
                        opener = random.choice(openers)
                        comment = f"{opener} {feedback_clean}"
                    else:
                        comment = feedback_clean
                    
                    writer.writerow([
                        grade['student_id'], 
                        grade['score'],
                        comment
                    ])
        
        print(f"    📊 {assignment}: {len(assignment_grades)} students → {filepath.name}")
        created_files.append(str(filepath))
    
    return created_files


def save_to_master_csv(grades: list, output_folder: str):
    """
    Append grades to a master CSV file that tracks ALL grades over time.
    This enables progress tracking across the entire school year.
    
    Columns:
    - Date, Student ID, Student Name, Period, Assignment, Unit, Quarter
    - Overall Score, Letter Grade
    - Content Accuracy, Completeness, Writing Quality, Effort & Engagement
    """
    master_file = Path(output_folder) / "master_grades.csv"
    
    # Check if file exists to determine if we need headers
    file_exists = master_file.exists()
    
    # Determine current quarter based on date
    today = datetime.now()
    month = today.month
    if month >= 8 and month <= 10:
        quarter = "Q1"
    elif month >= 11 or month <= 1:
        quarter = "Q2"
    elif month >= 2 and month <= 4:
        quarter = "Q3"
    else:
        quarter = "Q4"
    
    with open(master_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header if new file
        if not file_exists:
            writer.writerow([
                'Date', 'Student ID', 'Student Name', 'First Name', 'Last Name',
                'Period', 'Assignment', 'Unit', 'Quarter',
                'Overall Score', 'Letter Grade',
                'Content Accuracy', 'Completeness', 'Writing Quality', 'Effort Engagement',
                'Feedback'
            ])
        
        # Write each grade
        for grade in grades:
            if grade.get('student_id') == "UNKNOWN":
                continue
            
            breakdown = grade.get('breakdown', {})
            
            writer.writerow([
                today.strftime('%Y-%m-%d'),
                grade.get('student_id', ''),
                grade.get('student_name', ''),
                grade.get('first_name', ''),
                grade.get('last_name', ''),
                grade.get('period', ''),
                grade.get('assignment', ''),
                grade.get('unit', ''),
                grade.get('grading_period', quarter),  # Use grading_period from settings, fallback to calculated
                grade.get('score', 0),
                grade.get('letter_grade', ''),
                breakdown.get('content_accuracy', 0),
                breakdown.get('completeness', 0),
                breakdown.get('writing_quality', 0),
                breakdown.get('effort_engagement', 0),
                grade.get('feedback', '')[:500]  # Truncate feedback for CSV
            ])
    
    print(f"📊 Updated master grades file: {master_file}")


def export_detailed_report(grades: list, output_folder: str, assignment_name: str) -> str:
    """
    Create detailed CSV with all grading information for your records.
    """
    safe_name = re.sub(r'[^\w\s-]', '', assignment_name).replace(' ', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = Path(output_folder) / f"Detailed_Report_{safe_name}_{timestamp}.csv"
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Student ID', 'Student Name', 'Email', 'Assignment', 'Score', 'Letter Grade',
            'Content (40)', 'Completeness (25)', 'Writing (20)', 'Effort (15)',
            'Feedback', 'Filename'
        ])
        
        for grade in grades:
            breakdown = grade.get('breakdown', {})
            writer.writerow([
                grade.get('student_id', ''),
                grade.get('student_name', ''),
                grade.get('email', ''),
                grade.get('assignment', ''),
                grade.get('score', ''),
                grade.get('letter_grade', ''),
                breakdown.get('content_accuracy', ''),
                breakdown.get('completeness', ''),
                breakdown.get('writing_quality', ''),
                breakdown.get('effort_engagement', breakdown.get('critical_thinking', '')),
                grade.get('feedback', ''),
                grade.get('filename', '')
            ])
    
    print(f"📋 Detailed report saved: {filepath}")
    return str(filepath)


# =============================================================================
# MAIN GRADING WORKFLOW
# =============================================================================

def run_grading(
    assignment_folder: str = ASSIGNMENT_FOLDER,
    output_folder: str = OUTPUT_FOLDER,
    roster_file: str = ROSTER_FILE,
    assignment_name: str = ASSIGNMENT_NAME,
    create_outlook_emails: bool = False  # Set True if you have Outlook on Windows
):
    """
    Main function - runs the complete grading workflow.
    
    1. Loads student roster
    2. Reads each .docx file from assignment folder
    3. Grades each assignment with AI
    4. Generates emails (saves to files or creates Outlook drafts)
    5. Creates Focus CSV for grade import
    6. Creates detailed report for your records
    """
    print("=" * 60)
    print("📚 ASSIGNMENT GRADER - 6th Grade Social Studies")
    print("=" * 60)
    print(f"📁 Assignment folder: {assignment_folder}")
    print(f"💾 Output folder: {output_folder}")
    print(f"📝 Assignment: {assignment_name}")
    print()
    
    # Load roster
    roster = load_roster(roster_file)
    
    # Get all .docx files
    assignment_path = Path(assignment_folder)
    if not assignment_path.exists():
        print(f"❌ Assignment folder not found: {assignment_folder}")
        return []
    
    # Find all supported files (docx, txt, and images)
    supported_extensions = ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']
    all_files = []
    for ext in supported_extensions:
        all_files.extend(assignment_path.glob(ext))
    
    print(f"📄 Found {len(all_files)} files ({', '.join(supported_extensions)})")
    print()
    
    # Process each file
    all_grades = []
    
    for i, filepath in enumerate(all_files, 1):
        print(f"[{i}/{len(all_files)}] {filepath.name}")
        
        # Parse filename to get student name
        parsed = parse_filename(filepath.name)
        student_name = f"{parsed['first_name']} {parsed['last_name']}"
        lookup_key = parsed['lookup_key']
        
        # Look up student in roster
        if lookup_key in roster:
            student_info = roster[lookup_key].copy()
            print(f"  👤 {student_info['student_name']} (ID: {student_info['student_id']})")
        else:
            # Not found in roster - use parsed name
            student_info = {
                "student_id": "UNKNOWN",
                "student_name": student_name,
                "first_name": parsed['first_name'],
                "last_name": parsed['last_name'],
                "email": ""
            }
            print(f"  👤 {student_name} (⚠️ NOT IN ROSTER)")
        
        # Read file content
        file_data = read_assignment_file(filepath)
        if not file_data:
            print(f"  ❌ Could not read file")
            continue
        
        # Handle based on file type
        markers_found = []
        
        if file_data["type"] == "text":
            # Text-based file - check for markers
            content = file_data["content"]
            
            if len(content.strip()) < 20:
                print(f"  ⚠️  File appears empty ({len(content)} chars)")
                continue
            
            # Extract only the student work portion
            student_work, markers_found = extract_student_work(content)
            
            if markers_found:
                print(f"  📝 Found marker(s): {', '.join(markers_found[:2])}{'...' if len(markers_found) > 2 else ''}")
            else:
                print(f"  ⚠️  NO MARKERS FOUND - Check if student uploaded wrong document!")
                print(f"      → Review manually: {filepath.name}")
            
            if len(student_work.strip()) < 10:
                print(f"  ⚠️  No student work found after marker")
                continue
            
            # Prepare data for grading
            grade_data = {"type": "text", "content": student_work}
        
        elif file_data["type"] == "image":
            # Image file - send entire image to AI for grading
            print(f"  🖼️  Image file - sending to AI for visual grading")
            grade_data = file_data
            markers_found = ["image"]  # Mark as having content
        
        else:
            print(f"  ❌ Unknown file type")
            continue
        
        # Grade with AI
        grade_result = grade_assignment(student_info['student_name'], grade_data)
        
        # Combine all info
        # Extract assignment name from filename
        parts = Path(filepath.name).stem.split('_')
        if len(parts) >= 3:
            assignment_from_file = ' '.join(parts[2:])
        else:
            assignment_from_file = ASSIGNMENT_NAME
        
        grade_record = {
            **student_info,
            **grade_result,
            "filename": filepath.name,
            "assignment": assignment_from_file,
            "has_markers": len(markers_found) > 0
        }
        all_grades.append(grade_record)
        
        print(f"  ✅ Score: {grade_result['score']} ({grade_result['letter_grade']})")
        print()
    
    # Export results
    print("=" * 60)
    print("📊 EXPORTING RESULTS")
    print("=" * 60)
    
    # Focus CSVs (separated by assignment)
    focus_files = export_focus_csv(all_grades, output_folder, assignment_name)
    
    # Detailed report (one file with all grades)
    export_detailed_report(all_grades, output_folder, assignment_name)
    
    # Emails
    if create_outlook_emails:
        if not create_outlook_drafts(all_grades):
            save_emails_to_folder(all_grades, output_folder)
    else:
        save_emails_to_folder(all_grades, output_folder)
    
    # Summary
    print()
    print("=" * 60)
    print("📈 GRADING SUMMARY")
    print("=" * 60)
    
    if all_grades:
        scores = [g['score'] for g in all_grades if g['score'] > 0]
        if scores:
            print(f"Total graded: {len(all_grades)}")
            print(f"Average score: {sum(scores)/len(scores):.1f}")
            print(f"Highest: {max(scores)}")
            print(f"Lowest: {min(scores)}")
            
            # Grade distribution
            grade_dist = {}
            for g in all_grades:
                letter = g['letter_grade']
                grade_dist[letter] = grade_dist.get(letter, 0) + 1
            print(f"Distribution: {dict(sorted(grade_dist.items()))}")
            
            # Per-assignment breakdown
            print(f"\n📚 By Assignment:")
            assignments = {}
            for g in all_grades:
                a = g.get('assignment', 'Unknown')
                if a not in assignments:
                    assignments[a] = []
                assignments[a].append(g['score'])
            
            for assignment, scores_list in sorted(assignments.items()):
                valid_scores = [s for s in scores_list if s > 0]
                if valid_scores:
                    avg = sum(valid_scores) / len(valid_scores)
                    print(f"   • {assignment[:40]}: {len(scores_list)} students, avg {avg:.1f}")
        
        # List students not in roster
        unknown = [g for g in all_grades if g['student_id'] == 'UNKNOWN']
        if unknown:
            print(f"\n⚠️  {len(unknown)} students NOT FOUND in roster:")
            for g in unknown:
                print(f"   - {g['student_name']} ({g['filename']})")
        
        # List documents with no markers (possible wrong uploads)
        no_markers = [g for g in all_grades if not g.get('has_markers', True)]
        if no_markers:
            print(f"\n🚨 {len(no_markers)} documents had NO MARKERS - review for possible wrong uploads:")
            for g in no_markers:
                print(f"   - {g['student_name']}: {g['filename']}")
    
    print()
    print("✅ GRADING COMPLETE!")
    return all_grades


# =============================================================================
# RUN THE SCRIPT
# =============================================================================

if __name__ == "__main__":
    # Update the paths at the top of this file, then run!
    results = run_grading(
        create_outlook_emails=False  # Set True if you have Outlook desktop on Windows
    )
