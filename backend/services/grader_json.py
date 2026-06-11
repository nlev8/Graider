"""LLM-JSON repair for the grading pipeline: parse a model response into a dict,
stripping markdown fences and applying common-error repairs (missing commas,
parenthetical comments, unescaped newlines). Pure logic (json + re — no LLM /
I/O / Flask) extracted from assignment_grader.py. Wave 7 Slice 5.
"""
import json
import logging
import re

_logger = logging.getLogger(__name__)


def _try_parse_json_fallback(text: str) -> dict:
    """Attempt to parse JSON from LLM response text with repair logic.

    Used as fallback for Claude/Gemini responses and OpenAI text fallback.
    Returns parsed dict or None if unrecoverable.
    """
    if not text:
        return None

    # First try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        _logger.debug("Direct JSON parse of LLM response failed; trying fence strip")

    # Strip markdown code blocks
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split('\n')
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                end = i
                break
        cleaned = '\n'.join(lines[start:end]).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        _logger.debug("Fence-stripped JSON parse failed; applying repair heuristics")

    # Repair common LLM JSON issues
    fixed = cleaned

    # Fix malformed "reason" fields
    fixed = re.sub(r'"reason":\s*"[^"]*\\n[^"]*"', '"reason": ""', fixed)
    fixed = re.sub(r'"reason":\s*"[\s\n]*\}', '"reason": ""}', fixed)
    fixed = re.sub(r'"reason":\s*"[\s\n]*,', '"reason": "",', fixed)
    fixed = re.sub(r'"reason":\s*"[^"]*\{[^"]*"', '"reason": ""', fixed)

    # Remove parenthetical comments after closing quotes
    fixed = re.sub(r'"\s*\([^)]+\)', '"', fixed)

    # Add missing commas
    fixed = re.sub(r'"\s*\n(\s*)"', r'",\n\1"', fixed)
    fixed = re.sub(r'(\d)\s*\n(\s*)"', r'\1,\n\2"', fixed)
    fixed = re.sub(r'(true|false|null)\s*\n(\s*)"', r'\1,\n\2"', fixed)
    fixed = re.sub(r'(\]|\})\s*\n(\s*)"', r'\1,\n\2"', fixed)

    # Escape unescaped newlines inside strings
    result_chars = []
    in_string = False
    i = 0
    while i < len(fixed):
        char = fixed[i]
        if char == '\\' and i + 1 < len(fixed):
            result_chars.append(char)
            result_chars.append(fixed[i + 1])
            i += 2
            continue
        if char == '"':
            in_string = not in_string
            result_chars.append(char)
            i += 1
            continue
        if in_string:
            if char == '\n':
                result_chars.append('\\n')
            elif char == '\r':
                pass
            elif char == '\t':
                result_chars.append('\\t')
            else:
                result_chars.append(char)
        else:
            result_chars.append(char)
        i += 1

    fixed = ''.join(result_chars)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None
