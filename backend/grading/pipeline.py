"""Grading business-logic pipeline.

Extracted from backend/app.py in Phase 3a PR3. Byte-identical move --
no internal decomposition. The nested format_rubric_for_prompt at
line ~490 stays nested here in PR3; it moves out to
backend/services/rubric_formatting.py in PR4.
"""
# ---------------------------------------------------------------------------
# All imports needed by _run_grading_thread_inner.
# Copied from backend/app.py top-level imports.
# Inline lazy imports inside the function body are preserved verbatim.
# ---------------------------------------------------------------------------
import os
import re
import sys
import json
import csv
import math
import threading
import concurrent.futures
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Optional
import logging
import sentry_sdk

# student_history helpers (with fallback stubs matching app.py)
try:
    from backend.student_history import add_assignment_to_history, detect_baseline_deviation, build_history_context
except ImportError:
    try:
        from student_history import add_assignment_to_history, detect_baseline_deviation, build_history_context  # type: ignore[import-not-found,no-redef]
    except ImportError:
        def add_assignment_to_history(student_id: str, result: dict[str, Any]) -> None:  # type: ignore[misc]
            return None
        def detect_baseline_deviation(student_id: str, result: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
            return {"flag": "normal", "reasons": [], "details": {}}
        def build_history_context(student_id: str) -> str:
            return ""

# accommodation helpers (with fallback stubs matching app.py)
try:
    from backend.accommodations import build_accommodation_prompt
except ImportError:
    try:
        from accommodations import build_accommodation_prompt  # type: ignore[import-not-found,no-redef]
    except ImportError:
        def build_accommodation_prompt(student_id: str, teacher_id: str = '') -> str:
            return ""

# State helpers from canonical grading.state module
from backend.grading.state import _get_state, _get_lock, save_results
from backend.services.rubric_formatting import format_rubric_for_prompt

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants copied byte-identical from backend/app.py (can't import because
# app.py imports pipeline via shim → circular).
# ---------------------------------------------------------------------------
DOCUMENTS_DIR = os.path.expanduser("~/.graider_data/documents")


# ---------------------------------------------------------------------------
# _check_batch_calibration — MOVED from backend/app.py:398-441 (byte-identical
# body). Only caller was _run_grading_thread_inner below, so the definition
# moves with its consumer. Removed from app.py to avoid stale duplicate.
# ---------------------------------------------------------------------------
def _check_batch_calibration(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Check if grading results have anomalous distribution.

    Runs after a full class is graded to catch systematic issues.
    Returns dict with calibrated flag and any concerns.
    """
    raw_scores = [r.get("score", 0) for r in results
                  if r.get("letter_grade") not in ("ERROR", "MANUAL REVIEW", "INCOMPLETE")]
    # Safely coerce scores to float (AI may return strings like "85")
    scores = []
    for s in raw_scores:
        try:
            scores.append(float(s))
        except (ValueError, TypeError):
            pass
    if len(scores) < 5:
        return {"calibrated": True, "concerns": []}

    import statistics
    mean = statistics.mean(scores)
    stdev = statistics.stdev(scores) if len(scores) > 1 else 0
    ai_flagged = sum(1 for r in results
                     if r.get("ai_detection", {}).get("flag") in ("possible", "likely")
                     or r.get("plagiarism_detection", {}).get("flag") in ("possible", "likely"))

    concerns = []
    if mean > 95:
        concerns.append(f"Mean score is {mean:.0f} — unusually high, grading may be too lenient")
    elif mean < 55:
        concerns.append(f"Mean score is {mean:.0f} — unusually low, check rubric or extraction")

    if stdev < 5 and len(scores) > 10:
        concerns.append(f"Standard deviation is only {stdev:.1f} — scores are suspiciously uniform")

    if ai_flagged > len(results) * 0.3:
        concerns.append(f"{ai_flagged}/{len(results)} flagged for AI/plagiarism — detection may be oversensitive")

    return {
        "calibrated": len(concerns) == 0,
        "mean": round(mean, 1),
        "stdev": round(stdev, 1),
        "concerns": concerns,
        "ai_flagged_count": ai_flagged
    }


# ---------------------------------------------------------------------------
# load_support_documents_for_grading — byte-identical copy from app.py:258.
# Reproduced here so pipeline.py is self-contained (app.py imports pipeline,
# so pipeline cannot import app without a circular dependency).
# Extracted to a shared module in PR4.
# ---------------------------------------------------------------------------
def load_support_documents_for_grading(subject: Optional[str] = None) -> str:
    """
    Load relevant support documents to include in AI grading context.

    Args:
        subject: Optional subject to filter documents

    Returns:
        String with document content to include in AI prompt
    """
    if not os.path.exists(DOCUMENTS_DIR):
        return ""

    docs_content = []
    total_chars = 0
    max_chars = 8000  # Limit to avoid overwhelming the AI

    # Load metadata for all documents
    for f in os.listdir(DOCUMENTS_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(DOCUMENTS_DIR, f), 'r') as mf:
                    metadata = json.load(mf)

                doc_type = metadata.get('doc_type', 'general')
                filepath = metadata.get('filepath', '')
                description = metadata.get('description', '')

                # Prioritize rubrics and curriculum docs
                if doc_type not in ['rubric', 'curriculum', 'standards']:
                    continue

                if not os.path.exists(filepath):
                    continue

                # Read document content
                content = ""
                if filepath.endswith('.txt') or filepath.endswith('.md'):
                    with open(filepath, 'r', encoding='utf-8') as df:
                        content = df.read()
                elif filepath.endswith('.docx'):
                    try:
                        from docx import Document
                        doc = Document(filepath)
                        content = '\n'.join([p.text for p in doc.paragraphs])
                    except Exception:
                        _logger.debug("support document docx extraction failed", exc_info=True)
                        continue
                elif filepath.endswith('.pdf'):
                    try:
                        import fitz  # type: ignore[import-untyped]  # PyMuPDF lacks py.typed
                        pdf = fitz.open(filepath)
                        content = '\n'.join([page.get_text() for page in pdf])
                        pdf.close()
                    except Exception:
                        _logger.debug("support document pdf extraction failed", exc_info=True)
                        continue

                if content and total_chars + len(content) < max_chars:
                    doc_label = doc_type.upper()
                    if description:
                        doc_label += f" - {description}"
                    docs_content.append(f"[{doc_label}]\n{content[:2000]}")
                    total_chars += len(content[:2000])

            except Exception as e:
                _logger.error("Error loading document: %s", e)
                continue

    if not docs_content:
        return ""

    return "\n".join([
        "",
        "═══════════════════════════════════════════════════════════",
        "REFERENCE DOCUMENTS (Use these to inform your grading):",
        "═══════════════════════════════════════════════════════════",
        "",
        *docs_content,
        "",
        "═══════════════════════════════════════════════════════════",
        ""
    ])



def extract_content_fingerprints(config_data: dict[str, Any]) -> set[str]:
    """Extract unique phrases from assignment's imported document for content matching."""
    fingerprints = set()
    imported_doc = config_data.get('importedDoc') or {}
    doc_text = imported_doc.get('text', '')

    if doc_text:
        # Extract significant phrases (questions, numbered items, unique sentences)
        import re
        # Get numbered questions/items (e.g., "1.", "1)", "Question 1")
        numbered = re.findall(r'(?:^|\n)\s*(?:\d+[\.\)]\s*|Question\s*\d+[:\.]?\s*)(.{20,100})', doc_text, re.IGNORECASE)
        for item in numbered[:10]:  # Limit to first 10
            clean = re.sub(r'\s+', ' ', item.strip().lower())
            if len(clean) > 20:
                fingerprints.add(clean[:50])  # First 50 chars of each

        # Get marker texts as fingerprints
        for marker in config_data.get('customMarkers', []):
            if len(marker) > 10:
                fingerprints.add(marker.lower()[:50])

        # Get unique sentences (not too short, not too long)
        sentences = re.split(r'[.!?]\s+', doc_text)
        for sent in sentences[:20]:
            clean = re.sub(r'\s+', ' ', sent.strip().lower())
            if 30 < len(clean) < 150:
                fingerprints.add(clean[:50])

    return fingerprints


def fuzzy_match_score(text1: str, text2: str) -> float:
    """Calculate fuzzy match score between two strings."""
    if not text1 or not text2:
        return 0

    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    # Exact match
    if t1 == t2:
        return 100

    # One contains the other
    if t1 in t2 or t2 in t1:
        return 80

    # Word overlap matching
    import re
    words1 = set(re.findall(r'\b\w{3,}\b', t1))  # Words 3+ chars
    words2 = set(re.findall(r'\b\w{3,}\b', t2))

    if not words1 or not words2:
        return 0

    overlap = len(words1 & words2)
    total = max(len(words1), len(words2))
    word_score = (overlap / total) * 60 if total > 0 else 0

    # Abbreviation detection (e.g., "Ch5" matches "Chapter 5")
    abbrev_patterns = [
        (r'ch(?:ap(?:ter)?)?[\s\-_]*(\d+)', r'chapter \1'),  # Ch5, Chap5, Chapter5
        (r'q(?:uiz)?[\s\-_]*(\d+)', r'quiz \1'),  # Q1, Quiz1
        (r'hw[\s\-_]*(\d+)', r'homework \1'),  # HW1
        (r'test[\s\-_]*(\d+)', r'test \1'),
        (r'unit[\s\-_]*(\d+)', r'unit \1'),
    ]

    for pattern, expansion in abbrev_patterns:
        t1_expanded = re.sub(pattern, expansion, t1, flags=re.IGNORECASE)
        t2_expanded = re.sub(pattern, expansion, t2, flags=re.IGNORECASE)
        if t1_expanded in t2_expanded or t2_expanded in t1_expanded:
            return 70

    return word_score


def calculate_late_penalty(filepath: Any, matched_config: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Calculate late penalty based on file modification time and assignment config.

    Returns dict with penalty info or None if no penalty applies.
    """
    if not matched_config:
        return None

    due_date_str = matched_config.get('dueDate', '')
    late_penalty_cfg = matched_config.get('latePenalty', {})

    if not due_date_str or not late_penalty_cfg.get('enabled'):
        return None

    try:
        due_date = datetime.fromisoformat(due_date_str)
    except (ValueError, TypeError):
        return None

    # Get file modification time
    try:
        file_mtime = datetime.fromtimestamp(Path(filepath).stat().st_mtime)
    except (OSError, TypeError):
        return None

    # Apply grace period
    grace_hours = late_penalty_cfg.get('gracePeriodHours', 0) or 0
    from datetime import timedelta
    effective_due = due_date + timedelta(hours=grace_hours)

    if file_mtime <= effective_due:
        return {"is_late": False, "days_late": 0, "penalty_percent": 0, "penalty_points": 0}

    # Calculate days late (partial days round up)
    delta = file_mtime - effective_due
    days_late = math.ceil(delta.total_seconds() / 86400)

    penalty_type = late_penalty_cfg.get('type', 'points_per_day')
    amount = late_penalty_cfg.get('amount', 10) or 10
    max_penalty = late_penalty_cfg.get('maxPenalty', 50) or 50
    tiers = late_penalty_cfg.get('tiers', [])

    penalty_percent: float = 0
    penalty_points: float = 0

    if penalty_type == 'points_per_day':
        penalty_points = min(days_late * amount, max_penalty)
    elif penalty_type == 'percent_per_day':
        penalty_percent = min(days_late * amount, max_penalty)
    elif penalty_type == 'tiered':
        # Sort tiers by daysLate descending and find the matching bracket
        sorted_tiers = sorted(tiers, key=lambda t: t.get('daysLate', 0), reverse=True)
        for tier in sorted_tiers:
            if days_late >= tier.get('daysLate', 0):
                penalty_percent = min(tier.get('penalty', 0), max_penalty)
                break

    return {
        "is_late": True,
        "days_late": days_late,
        "penalty_type": penalty_type,
        "penalty_percent": penalty_percent,
        "penalty_points": penalty_points,
    }


def find_matching_config(filename: str, all_configs: dict[str, Any], grading_state: dict[str, Any], file_content: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Find matching config for a filename, with alias and fuzzy matching."""
    filename_lower = filename.lower()

    # Extract assignment part from filename.
    # Filenames follow pattern: FirstName_LastName_Assignment Title.ext
    # or FirstName_LastName_Assignment Title - Details (N).ext
    # Strip the student name prefix first, then use the full remaining
    # assignment title (which may itself contain ' - ').
    assignment_candidates = []

    # Strategy 1: Strip student name prefix (underscore-separated)
    if '_' in filename_lower:
        parts = filename_lower.split('_')
        if len(parts) > 2:
            full_assignment = '_'.join(parts[2:])
            full_assignment = os.path.splitext(full_assignment)[0]
            assignment_candidates.append(full_assignment)
            # Also strip trailing " (N)" version numbers
            import re
            stripped = re.sub(r'\s*\(\d+\)\s*$', '', full_assignment).strip()
            if stripped != full_assignment:
                assignment_candidates.append(stripped)

    # Strategy 2: Split on ' - ' (legacy: assumes student_name - assignment)
    if ' - ' in filename_lower:
        after_dash = filename_lower.split(' - ', 1)[1]
        after_dash = os.path.splitext(after_dash)[0]
        if after_dash not in assignment_candidates:
            assignment_candidates.append(after_dash)

    # Strategy 3: Full filename as fallback
    fallback = os.path.splitext(filename_lower)[0]
    if fallback not in assignment_candidates:
        assignment_candidates.append(fallback)

    # Use the first candidate as primary (best quality extraction)
    assignment_part = assignment_candidates[0] if assignment_candidates else fallback

    best_match = None
    best_score: float = 0
    match_reason = ""

    for config_name, config_data in all_configs.items():
        config_title = config_data.get('title', '').lower()
        aliases = [a.lower() for a in config_data.get('aliases', [])]

        # Try all assignment candidates (full title, stripped version, dash-split, etc.)
        for candidate in assignment_candidates:
            # 1. Exact name/title match (highest priority)
            if config_name == candidate or config_title == candidate:
                return config_data  # type: ignore[no-any-return]  # config_data is Any from json.load

            # 2. Substring match on name/title
            if config_name in candidate or candidate in config_name:
                score = len(config_name) + 50
                if score > best_score:
                    best_score = score
                    best_match = config_data
                    match_reason = f"name match: {config_name}"

            if config_title and (config_title in candidate or candidate in config_title):
                score = len(config_title) + 50
                if score > best_score:
                    best_score = score
                    best_match = config_data
                    match_reason = f"title match: {config_title}"

            # 3. Alias matching (check all aliases)
            for alias in aliases:
                if alias in candidate or candidate in alias:
                    score = len(alias) + 40
                    if score > best_score:
                        best_score = score
                        best_match = config_data
                        match_reason = f"alias match: {alias}"

                # Fuzzy match on alias
                fuzzy = fuzzy_match_score(alias, candidate)
                if fuzzy > 50 and fuzzy + 20 > best_score:
                    best_score = fuzzy + 20
                    best_match = config_data
                    match_reason = f"fuzzy alias: {alias}"

            # 4. Fuzzy matching on name/title
            fuzzy_name = fuzzy_match_score(config_name, candidate)
            if fuzzy_name > 50 and fuzzy_name > best_score:
                best_score = fuzzy_name
                best_match = config_data
                match_reason = f"fuzzy name: {config_name}"

            fuzzy_title = fuzzy_match_score(config_title, candidate)
            if fuzzy_title > 50 and fuzzy_title > best_score:
                best_score = fuzzy_title
                best_match = config_data
                match_reason = f"fuzzy title: {config_title}"

    # 5. Content fingerprinting (if no good match found and file content provided)
    if best_score < 50 and file_content:
        file_content_lower = file_content.lower()
        for config_name, config_data in all_configs.items():
            fingerprints = extract_content_fingerprints(config_data)
            if fingerprints:
                matches = sum(1 for fp in fingerprints if fp in file_content_lower)
                if matches >= 2:  # At least 2 fingerprint matches
                    content_score = min(matches * 15, 80)  # Cap at 80
                    if content_score > best_score:
                        best_score = content_score
                        best_match = config_data
                        match_reason = f"content fingerprint: {matches} matches"

    if best_match and match_reason:
        grading_state["log"].append(f"Auto-matched via {match_reason}")

    return best_match


def _build_file_ai_notes(
    *,
    custom_rubric: Any | None,
    file_notes: Any,
    filepath: Any,
    global_ai_notes: str,
    grading_state: dict[str, Any],
    matched_config: dict[str, Any] | None,
    matched_title: Any,
    output_folder: str,
    period_class_level_map: dict[str, str],
    resubmissions: Any,
    rubric_type: Any | str,
    student_info: Any,
    student_period: str,
    teacher_id: str,
) -> tuple[str, str]:
    file_ai_notes = global_ai_notes
    if global_ai_notes:
        _logger.info("  Applying Global AI Instructions (%d chars)", len(global_ai_notes))
    if file_notes:
        file_ai_notes += f"\n\nASSIGNMENT-SPECIFIC INSTRUCTIONS:\n{file_notes}"
        _logger.info("  Applying Assignment-Specific Notes (%d chars)", len(file_notes))

    # Inject correction patterns (learn from teacher edits)
    try:
        from backend.services.correction_patterns import build_correction_context
        _question_types = []
        if matched_config:
            _section_cats = matched_config.get('sectionCategories', {})
            _question_types = [k for k, v in _section_cats.items() if v]
        if not _question_types:
            _question_types = ['short_answer', 'multiple_choice', 'extended_writing']
        _correction_ctx = build_correction_context(  # type: ignore[no-untyped-call]
            teacher_id, matched_config.get('subject', '') if matched_config else '', _question_types
        )
        if _correction_ctx:
            file_ai_notes += "\n\n" + _correction_ctx
            _logger.info("  Applying Correction Patterns (%d chars)", len(_correction_ctx))
    except Exception as e:
        _logger.warning("  Correction patterns skipped: %s", e)

    # Inject model answers from config (if generated)
    model_answers = matched_config.get('modelAnswers', {}) if matched_config else {}
    if model_answers:
        ma_lines = ["\n\nMODEL ANSWERS (compare student responses against these):"]
        for section_name, answer_text in model_answers.items():
            ma_lines.append(f"- {section_name}: {answer_text}")
        file_ai_notes += "\n".join(ma_lines)
        _logger.info("  Applying Model Answers (%d sections)", len(model_answers))

        # Detect fill-in-the-blank assignments and add special rubric override
        # Use specific phrases to avoid false positives (e.g., "fill in the Cornell Notes")
        _fn_lower = file_notes.lower()
        if ('fill-in-the-blank' in _fn_lower or 'fill in the blank' in _fn_lower
                or 'fill in blank' in _fn_lower or 'fillintheblank' in _fn_lower.replace(' ', '').replace('-', '')):
            file_ai_notes += """

FILL-IN-THE-BLANK RUBRIC OVERRIDE:
This is a fill-in-the-blank assignment. IGNORE the standard rubric categories and use this instead:
- Content Accuracy (70%): Is each answer correct or essentially correct?
- Completeness (30%): Did the student attempt all blanks?

CRITICAL GRADING RULES FOR FILL-IN-THE-BLANK:
- DO NOT penalize for spelling errors if the word is recognizable
- DO NOT penalize for capitalization
- DO NOT assess "Writing Quality" or "Critical Thinking" - these don't apply
- Accept synonyms and reasonable variations
- If the answer is close enough to understand the intent, mark it CORRECT
- A student who fills in all blanks with mostly correct answers should get 90+
- Minor typos like "rebelion" for "rebellion" = FULL CREDIT
"""
            _logger.info("  Fill-in-the-blank detected - applying lenient grading override")

    # Apply assignment-specific rubric type (overrides global rubric)
    if rubric_type and rubric_type != 'standard':
        if rubric_type == 'fill-in-blank':
            file_ai_notes += """

ASSIGNMENT RUBRIC TYPE: FILL-IN-THE-BLANK
IGNORE the standard rubric. Use these categories ONLY:
- Content Accuracy (70%): Is each answer correct or essentially correct?
- Completeness (30%): Did the student attempt all blanks?

CRITICAL RULES:
- DO NOT penalize spelling errors if the word is recognizable
- DO NOT penalize capitalization
- Accept synonyms and reasonable variations
- A student who fills in all blanks with mostly correct answers = 90+
"""
            _logger.info("  Rubric Type: Fill-in-the-Blank")
        elif rubric_type == 'essay':
            file_ai_notes += """

ASSIGNMENT RUBRIC TYPE: ESSAY/WRITTEN RESPONSE
Use these categories:
- Content & Ideas (35%): Are the main points valid and well-supported?
- Writing Quality (30%): Grammar, spelling, sentence structure, clarity
- Critical Thinking & Analysis (20%): Depth of analysis, connections made
- Effort & Engagement (15%): Evidence of genuine effort and thought

Grade writing quality more strictly than fill-in-blank, but still be encouraging.
"""
            _logger.info("  Rubric Type: Essay/Written Response")
        elif rubric_type == 'cornell-notes':
            file_ai_notes += """

ASSIGNMENT RUBRIC TYPE: CORNELL NOTES
Use these categories:
- Content Accuracy (40%): Are the notes factually correct and relevant?
- Note Structure (25%): Proper Cornell format - questions in cue column, notes in main area
- Summary Quality (20%): Does the summary synthesize main ideas?
- Effort & Completeness (15%): Are all sections filled in?

Look for: main ideas captured, good questions, clear summary at bottom.
"""
            _logger.info("  Rubric Type: Cornell Notes")
        elif rubric_type == 'custom' and custom_rubric:
            rubric_text = "ASSIGNMENT RUBRIC TYPE: CUSTOM\nUse these categories ONLY:\n"
            for cat in custom_rubric:
                name = cat.get('name', 'Unknown')
                weight = cat.get('weight', 0)
                rubric_text += f"- {name} ({weight}%)\n"
            file_ai_notes += f"\n{rubric_text}"
            _logger.info("  Rubric Type: Custom (%d categories)", len(custom_rubric))

    # Add accommodation prompt if student has IEP/504
    if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
        accommodation_prompt = build_accommodation_prompt(student_info['student_id'], teacher_id)
        if accommodation_prompt:
            file_ai_notes += f"\n{accommodation_prompt}"

    # Build student history context (passed separately to feedback, NOT mixed into grading instructions)
    history_context = ""
    if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
        history_context = build_history_context(student_info['student_id'])

    # Add class period context for differentiated grading
    if student_period:
        class_level = period_class_level_map.get(student_period, 'standard')
        file_ai_notes += f"\n\nCLASS PERIOD: {student_period}"
        file_ai_notes += f"\nCLASS LEVEL: {class_level.upper()}"

        if class_level == 'advanced':
            file_ai_notes += """
ADVANCED CLASS - RUBRIC ADJUSTMENT:
When applying the rubric above, make these automatic adjustments:
- INCREASE weight of Critical Thinking/Analysis categories by +15%
- INCREASE weight of Writing Quality/Communication by +10%
- DECREASE weight of Completion/Effort categories by -15%
- DECREASE weight of basic Content Accuracy by -10%
(Percentages are relative shifts - redistribute points accordingly)

ADVANCED CLASS GRADING EXPECTATIONS:
- Hold students to HIGHER standards than the base rubric suggests
- Expect detailed, thoughtful responses with deeper analysis
- Grade more strictly on grammar, vocabulary, and sophistication
- Look for evidence of critical thinking and connections between concepts
- Surface-level or simplistic answers should score in the B/C range, not A
- An "A" (90+) should represent truly exceptional, insightful work
- Be constructive but maintain high expectations
"""
        elif class_level == 'support':
            file_ai_notes += """
SUPPORT CLASS - RUBRIC ADJUSTMENT:
When applying the rubric above, make these automatic adjustments:
- INCREASE weight of Effort/Engagement categories by +20%
- INCREASE weight of Completion categories by +15%
- DECREASE weight of Writing Quality/Grammar by -20%
- DECREASE weight of Critical Thinking/Analysis by -15%
(Percentages are relative shifts - redistribute points accordingly)

SUPPORT CLASS GRADING EXPECTATIONS:
- Be MORE LENIENT and ENCOURAGING than the base rubric suggests
- Prioritize effort, completion, and basic understanding
- Be very generous with partial credit for attempts that show learning
- Do NOT penalize spelling, grammar, or incomplete sentences
- If student attempted the work and shows basic understanding, lean toward passing
- Recognize and praise progress and effort in feedback
- Focus feedback on encouragement and growth, not deficits
- A student who tries hard and completes work should score B or higher
"""
        else:  # standard
            file_ai_notes += """
STANDARD CLASS GRADING EXPECTATIONS:
- Apply the rubric as written without adjustment
- Balance rigor with encouragement
- Award credit for demonstrated understanding even if answers aren't perfect
- Grade fairly according to grade-level expectations
"""

    # Inject resubmission context so feedback references improvements
    if filepath.name in resubmissions:
        sid = student_info.get('student_id', '')
        prev_r = None

        # Source 1: Current session results (has full breakdown + feedback)
        for r in grading_state["results"]:
            if r.get("student_id") == sid and r.get("assignment") == matched_title:
                prev_r = r
                break

        # Source 2: Master CSV fallback (prior session)
        if prev_r is None:
            try:
                master_csv = Path(output_folder) / "master_grades.csv"
                if master_csv.exists():
                    import csv as csv_mod
                    with open(master_csv, 'r', encoding='utf-8') as csvf:
                        reader = csv_mod.DictReader(csvf)
                        for row in reader:
                            if (row.get('Student ID', '') == sid and
                                row.get('Assignment', '').strip().lower() == matched_title.strip().lower()):
                                prev_r = {
                                    "score": row.get('Overall Score', '?'),
                                    "letter_grade": row.get('Letter Grade', '?'),
                                    "feedback": row.get('Feedback', ''),
                                    "breakdown": {}
                                }
                                break
            except Exception as e:
                # Best-effort: prior-session lookup is for resubmission
                # context. If the master CSV is unreadable, the
                # primary-session error already alerted via the
                # already_graded loader above; skip the resubmission
                # comparison and proceed.
                _logger.debug("Resubmission CSV fallback failed for sid=%s: %s", sid, e)

        if prev_r:
            prev_score = prev_r.get("score", "?")
            prev_grade = prev_r.get("letter_grade", "?")
            prev_breakdown = prev_r.get("breakdown", {})
            prev_feedback = str(prev_r.get("feedback", ""))
            if len(prev_feedback) > 500:
                prev_feedback = prev_feedback[:500] + "..."

            breakdown_lines = ""
            if prev_breakdown:
                breakdown_lines = (
                    f"- Content Accuracy: {prev_breakdown.get('content_accuracy', '?')}/40\n"
                    f"- Completeness: {prev_breakdown.get('completeness', '?')}/25\n"
                    f"- Writing Quality: {prev_breakdown.get('writing_quality', '?')}/20\n"
                    f"- Effort & Engagement: {prev_breakdown.get('effort_engagement', '?')}/15"
                )

            resub_context = (
                "\n\nRESUBMISSION CONTEXT:\n"
                "This student is resubmitting a previously graded assignment. "
                "Compare their new work to the previous submission and highlight specific improvements.\n\n"
                f"Previous submission:\n"
                f"- Score: {prev_score} ({prev_grade})\n"
                f"{breakdown_lines}\n"
                f"- Previous feedback: {prev_feedback}\n\n"
                "FEEDBACK INSTRUCTIONS FOR RESUBMISSION:\n"
                "1. Start feedback by acknowledging this is a resubmission and that the student took the initiative to improve their work\n"
                "2. Specifically call out what improved compared to the previous submission "
                "(e.g., 'Your definition of X is now much more complete - last time you missed the key detail about Y')\n"
                "3. If breakdown categories improved, mention which areas showed growth\n"
                "4. If some areas still need work, note them as 'still developing' rather than as failures\n"
                "5. End with encouragement about their growth mindset and willingness to revise\n"
            )
            file_ai_notes += resub_context
            _logger.info("  Injected resubmission context (prev score: %s)", prev_score)
    return file_ai_notes, history_context


def _resolve_student(
    *,
    filepath: Any,
    grading_state: dict[str, Any],
    roster: dict[Any, Any],
) -> tuple[Any, Any]:
    from assignment_grader import (  # function-local: preserves test patchability
        parse_filename,
    )
    parsed = parse_filename(filepath.name)
    student_name = f"{parsed['first_name']} {parsed['last_name']}"
    lookup_key = parsed['lookup_key']

    # Lookup student in roster
    if lookup_key in roster:
        student_info = roster[lookup_key].copy()
    else:
        # Try fuzzy matching for partial/hyphenated last names
        student_info = None
        first_name_lower = parsed['first_name'].lower()
        last_name_lower = parsed['last_name'].lower()
        # Strip apostrophes/special chars for comparison (Da'Jaun → dajaun)
        first_name_norm = first_name_lower.replace("'", "").replace("\u2019", "")
        last_name_norm = last_name_lower.replace("'", "").replace("\u2019", "")
        # Normalize spaces/hyphens (Salvador Guzman → salvadorguzman)
        last_name_collapsed = last_name_norm.replace(" ", "").replace("-", "")

        for roster_key, roster_data in roster.items():
            if isinstance(roster_data, dict):
                roster_first = roster_data.get('first_name', '').lower()
                roster_last = roster_data.get('last_name', '').lower()
                roster_first_norm = roster_first.replace("'", "").replace("\u2019", "")
                roster_last_norm = roster_last.replace("'", "").replace("\u2019", "")
                roster_last_collapsed = roster_last_norm.replace(" ", "").replace("-", "")

                # Match first name (strip apostrophes for comparison)
                if (roster_first_norm != first_name_norm
                        and not roster_first_norm.startswith(first_name_norm)):
                    continue

                # Check various last name matching patterns
                roster_last_parts_hyphen = roster_last_norm.split('-')
                roster_last_parts_space = roster_last_norm.split(' ')
                if (
                    roster_last_norm.startswith(last_name_norm) or  # "k" matches "kolas"
                    roster_last_parts_hyphen[0] == last_name_norm or  # "kolas" matches "kolas-nowicki"
                    last_name_norm in roster_last_parts_hyphen or  # "nowicki" matches "kolas-nowicki"
                    roster_last_parts_space[0] == last_name_norm or  # "maloney" matches "maloney fox"
                    last_name_norm in roster_last_parts_space or  # "fox" matches "maloney fox"
                    roster_last_collapsed == last_name_collapsed  # "salvador guzman" matches "salvador-guzman"
                ):
                    student_info = roster_data.copy()
                    student_name = f"{roster_data.get('first_name', parsed['first_name'])} {roster_data.get('last_name', parsed['last_name'])}"
                    grading_state["log"].append(f"  📎 Matched '{parsed['first_name']} {parsed['last_name']}' to '{student_name}'")
                    break

        if not student_info:
            student_info = {"student_id": "UNKNOWN", "student_name": student_name,
                           "first_name": parsed['first_name'], "last_name": parsed['last_name'], "email": ""}
    return student_info, parsed


def _dispatch_grade(
    *,
    ai_model: str,
    assignment_template_local: Any,
    custom_rubric: Any | None,
    effort_points: Any | int,
    ensemble_models: list[str] | None,
    extraction_mode: str,
    file_ai_notes: str,
    file_exclude_markers: Any,
    file_markers: Any,
    grade_data: dict[str, Any],
    grade_level: str,
    grading_style: str,
    history_context: str,
    marker_config: Any | None,
    rubric_prompt: Any,
    rubric_type: Any | str,
    rubric_weights: list[Any] | None,
    student_info: Any,
    subject: str,
    trusted_students: list[str] | None,
) -> Any:
    from assignment_grader import (  # function-local: preserves test patchability
        grade_assignment,
        grade_multipass,
        grade_with_ensemble,
        grade_with_parallel_detection,
    )
    student_id = student_info.get('student_id', '')
    # Debug: Show what we're checking
    _logger.debug("  Checking trust: student_id='%s', trusted_list=%s", student_id, trusted_students)
    is_trusted = trusted_students and student_id in trusted_students
    if is_trusted:
        _logger.info("  Trusted student - skipping AI/copy detection")

    # FITB: Skip AI/plagiarism detection - answers are factual, not creative writing
    is_fitb = rubric_type == 'fill-in-blank'
    if is_fitb:
        _logger.info("  FITB assignment - skipping AI/copy detection")

    # Skip detection for trusted students or FITB assignments
    skip_detection = is_trusted or is_fitb

    # Per-assignment custom rubric overrides global rubric weights
    file_rubric_weights = rubric_weights
    if rubric_type == 'custom' and custom_rubric and len(custom_rubric) == 4:
        file_rubric_weights = [cat.get('weight', 0) for cat in custom_rubric]
        if file_rubric_weights != [40, 25, 20, 15]:
            _logger.info("  Using per-assignment custom rubric weights: %s", file_rubric_weights)
        else:
            file_rubric_weights = None  # Default weights, no override needed

    # file_rubric_weights / marker_config are Optional[list] but grading functions
    # declare list[Any] — None means "use defaults", handled gracefully at runtime.
    if ensemble_models and len(ensemble_models) >= 2:
        grade_result = grade_with_ensemble(
            student_info['student_name'], grade_data, file_ai_notes,
            grade_level, subject, ensemble_models, student_info.get('student_id'),
            assignment_template_local, rubric_prompt, file_markers, file_exclude_markers,
            marker_config, effort_points, extraction_mode, grading_style,  # type: ignore[arg-type]
            rubric_weights=file_rubric_weights,  # type: ignore[arg-type]
        )
    elif is_trusted:
        # Trusted student: Use full multi-pass pipeline, skip detection only
        grade_result = grade_multipass(
            student_info['student_name'], grade_data, file_ai_notes,
            grade_level, subject, ai_model, student_info.get('student_id'),
            assignment_template_local, rubric_prompt, file_markers, file_exclude_markers,
            marker_config, effort_points, extraction_mode, grading_style,  # type: ignore[arg-type]
            student_history=history_context, rubric_weights=file_rubric_weights,  # type: ignore[arg-type]
        )
        grade_result['ai_detection'] = {"flag": "none", "confidence": 0, "reason": "Trusted writer - detection skipped"}
        grade_result['plagiarism_detection'] = {"flag": "none", "reason": "Trusted writer - detection skipped"}
    elif skip_detection:
        # FITB only: Use single-pass (genuinely needs it)
        grade_result = grade_assignment(
            student_info['student_name'], grade_data, file_ai_notes,
            grade_level, subject, ai_model, student_info.get('student_id'), assignment_template_local,
            rubric_prompt, file_markers, file_exclude_markers,
            marker_config, effort_points, extraction_mode, grading_style=grading_style,  # type: ignore[arg-type]
            rubric_weights=file_rubric_weights,  # type: ignore[arg-type]
        )
        grade_result['ai_detection'] = {"flag": "none", "confidence": 0, "reason": "N/A - Fill-in-the-blank"}
        grade_result['plagiarism_detection'] = {"flag": "none", "reason": "N/A - Fill-in-the-blank"}
    else:
        grade_result = grade_with_parallel_detection(
            student_info['student_name'], grade_data, file_ai_notes,
            grade_level, subject, ai_model, student_info.get('student_id'), assignment_template_local,
            rubric_prompt, file_markers, file_exclude_markers,
            marker_config, effort_points, extraction_mode, grading_style,  # type: ignore[arg-type]
            student_history=history_context, rubric_weights=file_rubric_weights,  # type: ignore[arg-type]
        )
    return grade_result


def _assemble_post_grade(
    *,
    config_mismatch: bool,
    config_mismatch_reason: str,
    file_data: dict[Any, Any],
    file_markers: Any,
    file_notes: Any,
    file_sections: Any,
    filepath: Any,
    grade_result: Any,
    matched_config: dict[str, Any] | None,
    matched_title: Any,
    period_class_level_map: dict[str, str],
    student_info: Any,
    student_period: str,
) -> dict[str, Any]:
    has_config = matched_config is not None
    has_custom_markers = len(file_markers) > 0
    has_grading_notes = bool(file_notes.strip()) if file_notes else False
    has_response_sections = len(file_sections) > 0
    is_verified = has_config or has_custom_markers or has_grading_notes or has_response_sections
    marker_status = "verified" if is_verified else "unverified"

    # Check baseline deviation
    baseline_deviation = {"flag": "normal", "reasons": [], "details": {}}
    if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
        try:
            baseline_deviation = detect_baseline_deviation(student_info['student_id'], grade_result)
        except Exception as e:
            # Behavior-critical: baseline deviation detection flags
            # anomalous grades (potential cheating signal). Silent
            # failure means anomalies go unflagged. The grading
            # itself proceeds with the "normal" default, but the
            # detector failure must be visible in Sentry so it
            # gets fixed instead of degrading silently.
            # Per Codex review: hash the student_id for log
            # correlation; raw IDs are PII for log streams (the
            # repo's Sentry scrubber treats them as sensitive).
            import hashlib
            sid_hash = hashlib.sha256(str(student_info['student_id']).encode()).hexdigest()[:12]
            _logger.error("detect_baseline_deviation failed for sid_hash=%s: %s", sid_hash, e)
            sentry_sdk.capture_exception(e)

    # Save to student history
    if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
        try:
            grade_record_hist = {**student_info, **grade_result, "filename": filepath.name,
                           "assignment": matched_title, "period": student_period}
            add_assignment_to_history(student_info['student_id'], grade_record_hist)
        except Exception as e:
            sentry_sdk.capture_exception(e)

    # Get class level for logging
    class_level = period_class_level_map.get(student_period, 'standard') if student_period else 'standard'
    level_indicator = "🎯" if class_level == "advanced" else "💚" if class_level == "support" else ""

    log_messages = [f"  Score: {grade_result['score']} ({grade_result['letter_grade']}) {level_indicator}{class_level.upper() if class_level != 'standard' else ''}".strip()]
    if config_mismatch:
        log_messages.append(f"  ⚠️  CONFIG MISMATCH - may have wrong rubric!")
    if marker_status == "unverified":
        log_messages.append(f"  ⚠️  UNVERIFIED: No assignment config")
    if baseline_deviation.get('flag') != 'normal':
        log_messages.append(f"  ⚠️  Baseline deviation: {baseline_deviation.get('flag')}")
    if grade_result.get('ai_detection', {}).get('flag') in ['possible', 'likely']:
        log_messages.append(f"  🤖 AI detected: {grade_result['ai_detection']['flag']}")
    if grade_result.get('plagiarism_detection', {}).get('flag') in ['possible', 'likely']:
        log_messages.append(f"  📋 Plagiarism detected: {grade_result['plagiarism_detection']['flag']}")

    return {
        "success": True,
        "student_info": student_info,
        "filepath": filepath,
        "matched_title": matched_title,
        "matched_config": matched_config,
        "student_period": student_period,
        "is_completion_only": False,
        "grade_result": grade_result,
        "file_data": file_data,
        "marker_status": marker_status,
        "baseline_deviation": baseline_deviation,
        "config_mismatch": config_mismatch,
        "config_mismatch_reason": config_mismatch_reason,
        "log_messages": log_messages
    }


def _resolve_student_period(
    *,
    class_period: str,
    student_info: Any,
    student_period_map: dict[str, str],
) -> str:
    student_name_lower = student_info['student_name'].lower()
    student_period = student_period_map.get(student_name_lower, None)

    # If no exact match, try fuzzy matching on period map
    if not student_period:
        first_name_lower = student_info.get('first_name', '').lower() or student_name_lower.split()[0] if student_name_lower else ''
        last_name_lower = student_info.get('last_name', '').lower() or (student_name_lower.split()[-1] if len(student_name_lower.split()) > 1 else '')

        for period_key, period_val in student_period_map.items():
            period_parts = period_key.split()
            if len(period_parts) >= 2:
                # period_key format: "firstname middlename lastname" or "firstname lastname"
                period_first = period_parts[0]
                period_last = period_parts[-1]

                # Match first name
                if period_first == first_name_lower or period_first.startswith(first_name_lower) or first_name_lower.startswith(period_first):
                    # Match last name (handle initials and compound names)
                    if (period_last == last_name_lower or
                        period_last.startswith(last_name_lower) or
                        last_name_lower.startswith(period_last) or
                        (len(last_name_lower) == 1 and period_last.startswith(last_name_lower))):
                        student_period = period_val
                        break

    if not student_period:
        student_period = class_period
    return student_period


def grade_single_file(
    filepath: Any, file_index: int, total_files: int, *,
    ai_model: str,
    all_configs: dict[str, Any],
    assignment_config: dict[str, Any] | None,
    class_period: str,
    ensemble_models: list[str] | None,
    extraction_mode: str,
    fallback_completion_only: bool,
    fallback_custom_rubric: Any | None,
    fallback_effort_points: int,
    fallback_exclude_markers: list[Any],
    fallback_imported_doc: dict[str, Any],
    fallback_markers: list[Any],
    fallback_notes: str,
    fallback_rubric_type: str,
    fallback_sections: list[Any],
    fallback_use_section_points: bool,
    global_ai_notes: str,
    grade_level: str,
    grading_state: dict[str, Any],
    grading_style: str,
    output_folder: str,
    period_class_level_map: dict[str, str],
    resubmissions: Any,
    roster: dict[Any, Any],
    rubric_prompt: Any,
    rubric_weights: list[Any] | None,
    student_period_map: dict[str, str],
    subject: str,
    teacher_id: str,
    trusted_students: list[str] | None,
) -> dict[str, Any]:
    """Grade a single file - designed for parallel execution."""
    # The grade fns + ASSIGNMENT_NAME stay a FUNCTION-LOCAL import: a module-level
    # hoist binds references at import time and silently no-ops the test suite's
    # patch('assignment_grader.grade_*') (tests/test_grading_thread_golden.py).
    from assignment_grader import (
        ASSIGNMENT_NAME,
        grade_assignment,
        grade_multipass,
        grade_with_ensemble,
        grade_with_parallel_detection,
        parse_filename,
        read_assignment_file,
    )
    try:
        student_info, parsed = _resolve_student(
            filepath=filepath,
            grading_state=grading_state,
            roster=roster,
        )

        # Match assignment config
        _logger.debug("  Matching config for: %s", filepath.name)
        _logger.debug("  Available configs: %s", list(all_configs.keys()))
        matched_config = find_matching_config(filepath.name, all_configs, grading_state)
        _logger.debug("  Match result: %s", ('FOUND - ' + matched_config.get('title', '?')) if matched_config else 'NONE')
        if not matched_config:
            try:
                temp_file_data = read_assignment_file(filepath)
                if temp_file_data and temp_file_data.get("type") == "text":
                    file_text = temp_file_data.get("content", "")
                    if file_text:
                        matched_config = find_matching_config(filepath.name, all_configs, grading_state, file_text)
            except Exception as e:
                # Best-effort: content-based matching failed. The
                # surrounding flow will then use whatever fallback
                # config / no-config handling exists for this file
                # (which can include skipping grading if no config
                # or markers can be derived). Debug-level only.
                _logger.debug("Content-based config matching failed for %s: %s", filepath.name, e)

        # Track if config matches the submitted file
        config_mismatch = False
        config_mismatch_reason = ""

        if matched_config:
            file_markers = matched_config.get('customMarkers', [])
            file_exclude_markers = matched_config.get('excludeMarkers', [])
            file_notes = matched_config.get('gradingNotes', '')
            file_sections = matched_config.get('responseSections', [])
            _logger.info("  Config matched: %s", matched_config.get('title', '?'))
            _logger.info("  Grading notes: %d chars, LENIENT=%s", len(file_notes), 'YES' if 'LENIENT' in file_notes.upper() else 'NO')
            matched_title = matched_config.get('title', 'Unknown')
            is_completion_only = matched_config.get('completionOnly', False)
            imported_doc = matched_config.get('importedDoc') or {}
            assignment_template_local = imported_doc.get('text', '')
            rubric_type = matched_config.get('rubricType') or 'standard'
            custom_rubric = matched_config.get('customRubric', None)
            # Section-based point configuration - only use when toggle is enabled
            use_section_points = matched_config.get('useSectionPoints', False)
            marker_config = file_markers if use_section_points else None
            effort_points = matched_config.get('effortPoints', 15) if use_section_points else 15
        else:
            # NO MATCHING CONFIG FOUND
            # Use parse_filename to properly strip student name prefix
            import re
            parsed = parse_filename(filepath.name)
            submitted_assignment = parsed.get('assignment_part', '') or os.path.splitext(filepath.name)[0]
            # Clean up: remove trailing (N) version numbers and extensions
            submitted_assignment = re.sub(r'\s*\(\d+\)\s*$', '', submitted_assignment).strip()
            submitted_assignment = re.sub(r'\.docx?\s*$', '', submitted_assignment, flags=re.IGNORECASE).strip()
            submitted_assignment = re.sub(r'\.pdf\s*$', '', submitted_assignment, flags=re.IGNORECASE).strip()
            # Replace underscores with spaces for display
            submitted_assignment = submitted_assignment.replace('_', ' ').strip()

            # Check if we're using a fallback config that doesn't match
            fallback_title = assignment_config.get('title', '') if assignment_config else ''
            if fallback_title and fallback_title.lower() != submitted_assignment.lower():
                config_mismatch = True
                config_mismatch_reason = f"Submitted '{submitted_assignment}' but no matching config found. Using fallback '{fallback_title}'"
                grading_state["log"].append(f"  ⚠️  CONFIG MISMATCH: {config_mismatch_reason}")
            elif not fallback_title:
                config_mismatch = True
                config_mismatch_reason = f"No saved config for '{submitted_assignment}'"
                grading_state["log"].append(f"  ⚠️  NO CONFIG: {submitted_assignment}")

            file_markers = fallback_markers
            file_exclude_markers = fallback_exclude_markers
            file_notes = fallback_notes
            file_sections = fallback_sections
            # Use the loaded assignment config name so all results group together.
            # Only fall back to filename if there's truly no config at all.
            matched_title = ASSIGNMENT_NAME if ASSIGNMENT_NAME else submitted_assignment
            is_completion_only = fallback_completion_only
            imported_doc = fallback_imported_doc
            assignment_template_local = fallback_imported_doc.get('text', '')
            rubric_type = fallback_rubric_type
            custom_rubric = fallback_custom_rubric
            use_section_points = fallback_use_section_points
            marker_config = file_markers if use_section_points else None
            effort_points = fallback_effort_points if use_section_points else 15

        # Handle completion-only rubric type
        if rubric_type == 'completion-only':
            is_completion_only = True

        # Auto-detect rubric type from filename if not already set
        filename_lower = filepath.name.lower().replace('_', ' ').replace('-', ' ')
        if rubric_type == 'standard':
            if 'fill in the blank' in filename_lower or 'fill in blank' in filename_lower or 'fillintheblank' in filename_lower.replace(' ', ''):
                rubric_type = 'fill-in-blank'
                _logger.info("  Auto-detected Fill-in-the-Blank from filename")
            elif 'cornell notes' in filename_lower or 'cornellnotes' in filename_lower.replace(' ', ''):
                rubric_type = 'cornell-notes'
                _logger.info("  Auto-detected Cornell Notes from filename")

        # Get student's period - try exact match first, then fuzzy match
        student_period = _resolve_student_period(
            class_period=class_period,
            student_info=student_info,
            student_period_map=student_period_map,
        )

        # Handle completion-only assignments
        if is_completion_only:
            return {
                "success": True,
                "student_info": student_info,
                "filepath": filepath,
                "matched_title": matched_title,
                "student_period": student_period,
                "is_completion_only": True,
                "grade_result": {
                    "score": 100,
                    "letter_grade": "SUBMITTED",
                    "feedback": "Completion-only assignment - submitted successfully.",
                    "breakdown": {},
                    "student_responses": [],
                    "unanswered_questions": [],
                    "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
                    "plagiarism_detection": {"flag": "none", "reason": ""}
                },
                "file_data": {"type": "text", "content": ""},
                "marker_status": "completion_only",
                "baseline_deviation": {"flag": "normal", "reasons": [], "details": {}},
                "log_messages": [f"  Completion only - recorded submission"]
            }

        # Build AI notes
        file_ai_notes, history_context = _build_file_ai_notes(
            custom_rubric=custom_rubric,
            file_notes=file_notes,
            filepath=filepath,
            global_ai_notes=global_ai_notes,
            grading_state=grading_state,
            matched_config=matched_config,
            matched_title=matched_title,
            output_folder=output_folder,
            period_class_level_map=period_class_level_map,
            resubmissions=resubmissions,
            rubric_type=rubric_type,
            student_info=student_info,
            student_period=student_period,
            teacher_id=teacher_id,
        )

        # Read file
        file_data = read_assignment_file(filepath)
        if not file_data:
            return {"success": False, "error": "Could not read file", "filepath": filepath}

        # Prepare grade data
        if file_data["type"] == "text":
            grade_data = {"type": "text", "content": file_data["content"]}
            # Pass through Graider table data for structured extraction
            if file_data.get("graider_tables"):
                grade_data["graider_tables"] = file_data["graider_tables"]
        else:
            grade_data = file_data

        # Grade with parallel detection or ensemble
        # Pass file_markers (customMarkers) for extraction, not file_sections
        # Pass file_exclude_markers (excludeMarkers) to skip sections that shouldn't be graded
        # Pass marker_config and effort_points for section-based point rubric

        # GUARD: Skip grading if no assignment config exists
        # Prevents reading passages, handouts, and other non-assignment docs from being graded
        if not matched_config and not file_markers and not file_sections:
            doc_label = matched_title or filepath.name
            grading_state["log"].append(f"  ⏭️  SKIPPED: No assignment config — cannot grade without a configured assignment")
            return {
                "success": False,
                "error": f"No assignment config found for '{doc_label}'. Set up an assignment in the Builder tab before grading.",
                "filepath": filepath,
                "is_config_missing": True
            }

        # Check if student is trusted (skip AI/plagiarism detection)
        grade_result = _dispatch_grade(
            ai_model=ai_model,
            assignment_template_local=assignment_template_local,
            custom_rubric=custom_rubric,
            effort_points=effort_points,
            ensemble_models=ensemble_models,
            extraction_mode=extraction_mode,
            file_ai_notes=file_ai_notes,
            file_exclude_markers=file_exclude_markers,
            file_markers=file_markers,
            grade_data=grade_data,
            grade_level=grade_level,
            grading_style=grading_style,
            history_context=history_context,
            marker_config=marker_config,
            rubric_prompt=rubric_prompt,
            rubric_type=rubric_type,
            rubric_weights=rubric_weights,
            student_info=student_info,
            subject=subject,
            trusted_students=trusted_students,
        )

        # Check for errors
        if grade_result.get('letter_grade') == 'ERROR':
            return {"success": False, "error": grade_result.get('feedback', 'API error'),
                    "filepath": filepath, "is_api_error": True}

        # Determine marker status
        return _assemble_post_grade(
            config_mismatch=config_mismatch,
            config_mismatch_reason=config_mismatch_reason,
            file_data=file_data,
            file_markers=file_markers,
            file_notes=file_notes,
            file_sections=file_sections,
            filepath=filepath,
            grade_result=grade_result,
            matched_config=matched_config,
            matched_title=matched_title,
            period_class_level_map=period_class_level_map,
            student_info=student_info,
            student_period=student_period,
        )

    except Exception as e:
        _logger.error("Grading failed for %s: %s", filepath, str(e))
        return {"success": False, "error": "Grading failed for this file", "filepath": filepath}


def _export_results(
    *,
    all_grades: list[Any],
    grading_state: dict[str, Any],
    output_folder: str,
    school_name: str,
    subject: str,
    teacher_name: str,
) -> None:
    from assignment_grader import (  # function-local: preserves test patchability
        ASSIGNMENT_NAME,
        export_detailed_report,
        export_focus_csv,
        save_emails_to_folder,
        save_to_master_csv,
    )
    if len(all_grades) > 0:
        grading_state["log"].append("")
        grading_state["log"].append("Exporting results...")

        # Focus CSVs (by assignment)
        export_focus_csv(all_grades, output_folder, ASSIGNMENT_NAME)
        grading_state["log"].append("  Focus CSVs created")

        # Detailed report
        export_detailed_report(all_grades, output_folder, ASSIGNMENT_NAME)
        grading_state["log"].append("  Detailed report created")

        # Email files
        save_emails_to_folder(all_grades, output_folder, teacher_name, subject, school_name)
        grading_state["log"].append("  Email files created")

        # Master tracking CSV
        save_to_master_csv(all_grades, output_folder)
        grading_state["log"].append("  Master grades updated")

        # Audit trail JSON
        audit_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audit_path = os.path.join(output_folder, f"Audit_{ASSIGNMENT_NAME}_{audit_timestamp}.json")
        audit_data = []
        for r in grading_state["results"]:
            audit_data.append({
                "student_name": r["student_name"],
                "student_id": r["student_id"],
                "score": r["score"],
                "letter_grade": r["letter_grade"],
                "ai_input": r.get("ai_input", ""),
                "ai_response": r.get("ai_response", "")
            })
        try:
            with open(audit_path, 'w') as fh:
                json.dump(audit_data, fh, indent=2)
            grading_state["log"].append("  Audit trail saved")
        except Exception as e:
            grading_state["log"].append(f"  Audit trail error: {str(e)}")
            sentry_sdk.capture_exception(e)


def _grade_all_files(
    *,
    PARALLEL_WORKERS: int,
    _update_state: Callable[..., None],
    ai_model: str,
    all_grades: list[Any],
    grading_lock: threading.Lock,
    grading_period: str,
    grading_state: dict[str, Any],
    gsf_kwargs: dict[str, Any],
    new_files: list[Any],
    resubmissions: set[Any],
    selected_files: list[str] | None,
) -> bool:
    completed = 0
    api_error_occurred = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        # Submit files in batches for responsive stop and ordered results
        file_index = 0
        stop_break = False
        while file_index < len(new_files) and not stop_break:
            if grading_state.get("stop_requested", False):
                grading_state["log"].append("")
                grading_state["log"].append(f"Stopped - {completed}/{len(new_files)} files completed")
                break

            # Submit next batch
            batch_end = min(file_index + PARALLEL_WORKERS, len(new_files))
            future_to_file = {}
            for i in range(file_index, batch_end):
                filepath = new_files[i]
                future = executor.submit(grade_single_file, filepath, i + 1, len(new_files), **gsf_kwargs)
                future_to_file[future] = (filepath, i + 1)

            # Wait for batch to complete, check stop between results
            for future in concurrent.futures.as_completed(future_to_file):
                if grading_state.get("stop_requested", False):
                    for fut in future_to_file:
                        fut.cancel()
                    grading_state["log"].append("")
                    grading_state["log"].append(f"Stopped - {completed}/{len(new_files)} files completed")
                    stop_break = True
                    break

                filepath, file_num = future_to_file[future]

                try:
                    result = future.result()
                except Exception as e:
                    grading_state["log"].append(f"[{file_num}/{len(new_files)}] {filepath.name}")
                    grading_state["log"].append(f"  ❌ Error: {str(e)}")
                    continue

                # Update progress
                completed += 1
                _update_state(progress=completed, current_file=filepath.name)

                # Handle failed grading
                if not result.get("success"):
                    grading_state["log"].append(f"[{file_num}/{len(new_files)}] {filepath.name}")
                    if result.get("is_config_missing"):
                        grading_state["log"].append(f"  ⏭️  {result.get('error', 'No config')}")
                    else:
                        grading_state["log"].append(f"  ❌ {result.get('error', 'Unknown error')}")

                    # Stop on API errors
                    if result.get("is_api_error"):
                        api_error_occurred = True
                        err_msg = result.get('error', '')
                        err_lower = err_msg.lower() if err_msg else ''
                        is_network = any(kw in err_lower for kw in ['connection', 'timeout', 'unreachable', 'refused'])
                        grading_state["log"].append("")
                        grading_state["log"].append("=" * 50)
                        if is_network:
                            grading_state["log"].append("⚠️  GRADING STOPPED - NETWORK ERROR")
                            grading_state["log"].append("Unable to connect to the AI provider. This may be due to")
                            grading_state["log"].append("network restrictions. Contact your IT department to allow")
                            grading_state["log"].append("access to OpenAI/Anthropic services.")
                        else:
                            grading_state["log"].append("⚠️  GRADING STOPPED - API ERROR")
                        grading_state["log"].append("=" * 50)
                        _update_state(error=f"{'Network' if is_network else 'API'} Error: {err_msg}")
                        for fut in future_to_file:
                            fut.cancel()
                        stop_break = True
                        break
                    continue

                # Log success
                student_info = result["student_info"]
                grade_result = result["grade_result"]

                grading_state["log"].append(f"[{file_num}/{len(new_files)}] {student_info['student_name']}")
                for msg in result.get("log_messages", []):
                    grading_state["log"].append(msg)

                # Build grade record for export
                file_data = result.get("file_data", {})
                if file_data.get("type") == "text":
                    student_content = file_data.get("content", "")[:5000]
                    full_content = file_data.get("content", "")[:10000]
                else:
                    student_content = "[Image file]"
                    full_content = "[Image file]"

                grade_record = {
                    **student_info,
                    **grade_result,
                    "filename": filepath.name,
                    "assignment": result["matched_title"],
                    "period": result["student_period"],
                    "grading_period": grading_period,
                    "has_markers": False,
                    "config_mismatch": result.get("config_mismatch", False),
                    "config_mismatch_reason": result.get("config_mismatch_reason", ""),
                    "ai_model": ai_model,
                    "email_approval": "pending"
                }

                # Resubmission handling: only replace if new score >= old score
                new_score = int(float(grade_result.get('score', 0) or 0))

                # Late penalty calculation
                matched_config = result.get("matched_config")
                late_info = calculate_late_penalty(filepath, matched_config) if matched_config else None
                original_score = new_score
                if late_info and late_info.get('is_late'):
                    penalty_type = late_info.get('penalty_type', 'points_per_day')
                    if penalty_type == 'points_per_day':
                        new_score = max(0, new_score - late_info['penalty_points'])
                    else:
                        new_score = max(0, new_score - round(original_score * late_info['penalty_percent'] / 100))
                    penalty_applied = original_score - new_score
                    grading_state["log"].append(
                        f"  Late penalty: -{penalty_applied} pts ({late_info['days_late']} day{'s' if late_info['days_late'] != 1 else ''} late)"
                    )

                # Only treat as resubmission if no explicit file selection
                # (explicit selection = teacher re-grade, not student resubmission)
                is_resub = filepath.name in resubmissions and selected_files is None
                previous_result = None
                previous_score = None

                if is_resub:
                    sid = student_info.get('student_id', '')
                    assign = result["matched_title"]
                    for r in grading_state["results"]:
                        if r.get("student_id") == sid and r.get("assignment") == assign:
                            previous_result = r
                            previous_score = int(float(r.get("score", 0) or 0))
                            break

                    if previous_score is not None and new_score < previous_score:
                        grading_state["log"].append(f"  ↳ Kept original grade ({previous_score}) — resubmission scored lower ({new_score})")
                        if previous_result:
                            previous_result["is_resubmission"] = True
                            previous_result["resubmission_score"] = new_score
                            previous_result["kept_higher"] = True
                        continue

                all_grades.append(grade_record)

                # Add to results for UI (remove any existing result for same file first - for regrading)
                new_result = {
                    "student_name": student_info['student_name'],
                    "student_id": student_info.get('student_id', ''),
                    "student_email": student_info.get('email', ''),
                    "filename": filepath.name,
                    "filepath": str(filepath),
                    "assignment": result["matched_title"],
                    "period": result["student_period"],
                    "score": new_score,
                    "letter_grade": grade_result.get('letter_grade', 'N/A'),
                    "feedback": grade_result.get('feedback', ''),
                    "student_content": student_content,
                    "full_content": full_content,
                    "breakdown": grade_result.get('breakdown', {}),
                    "student_responses": grade_result.get('student_responses', []),
                    "unanswered_questions": grade_result.get('unanswered_questions', []),
                    "ai_detection": grade_result.get('ai_detection', {}),
                    "plagiarism_detection": grade_result.get('plagiarism_detection', {}),
                    "baseline_deviation": result.get("baseline_deviation", {}),
                    "skills_demonstrated": grade_result.get('skills_demonstrated', {}),
                    "marker_status": result.get("marker_status", "unverified"),
                    "is_resubmission": is_resub,
                    "previous_score": previous_score,
                    "kept_higher": False,
                    "graded_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "ai_input": grade_result.get('_audit', {}).get('ai_input', ''),
                    "ai_response": grade_result.get('_audit', {}).get('ai_response', ''),
                    "token_usage": grade_result.get('token_usage', {}),
                    "email_approval": "pending",
                    "original_score": original_score if (late_info and late_info.get('is_late')) else None,
                    "late_penalty": {"days_late": late_info['days_late'], "penalty_applied": original_score - new_score, "penalty_type": late_info.get('penalty_type', '')} if (late_info and late_info.get('is_late')) else None,
                }
                with grading_lock:
                    from backend.staging import canonicalize_filename as _canon_dedup
                    canon_name = filepath.name
                    grading_state["results"] = [r for r in grading_state["results"]
                                                if r.get("filename") != canon_name
                                                and _canon_dedup(r.get("filename", "")) != canon_name]  # type: ignore[no-untyped-call]
                    if is_resub and previous_result:
                        sid = student_info.get('student_id', '')
                        assign = result["matched_title"]
                        grading_state["results"] = [r for r in grading_state["results"] if not (r.get("student_id") == sid and r.get("assignment") == assign)]
                    grading_state["results"].append(new_result)

                # Accumulate session cost (lock for compound read-modify-write)
                usage = grade_result.get('token_usage', {})
                if usage:
                    with grading_lock:
                        grading_state["session_cost"]["total_cost"] += usage.get("total_cost", 0)
                        grading_state["session_cost"]["total_input_tokens"] += usage.get("total_input_tokens", 0)
                        grading_state["session_cost"]["total_output_tokens"] += usage.get("total_output_tokens", 0)
                        grading_state["session_cost"]["total_api_calls"] += usage.get("api_calls", 0)

                # Warn when approaching cost limit
                cost_limit = grading_state.get("cost_limit", 0)
                if cost_limit > 0 and not grading_state.get("cost_warning_sent"):
                    warning_pct = grading_state.get("cost_warning_pct", 80) / 100
                    if grading_state["session_cost"]["total_cost"] >= cost_limit * warning_pct:
                        _update_state(cost_warning_sent=True)
                        grading_state["log"].append(f"  ⚠️ Approaching cost limit: ${grading_state['session_cost']['total_cost']:.4f} of ${cost_limit:.2f}")

                # Auto-stop if cost limit exceeded
                if cost_limit > 0 and grading_state["session_cost"]["total_cost"] >= cost_limit:
                    _update_state(stop_requested=True, cost_limit_hit=True)
                    grading_state["log"].append("")
                    grading_state["log"].append(f"Cost limit reached (${grading_state['session_cost']['total_cost']:.4f} >= ${cost_limit:.2f}). Auto-stopping...")

            # Advance to next batch
            file_index = batch_end
    return api_error_occurred


def _load_already_graded(
    *,
    grading_state: dict[str, Any],
    output_folder: str,
) -> tuple[set[Any], set[Any]]:
    # Load already graded files from master CSV AND in-memory results
    already_graded = set()

    # Check master CSV
    master_file = os.path.join(output_folder, "master_grades.csv")
    if os.path.exists(master_file):
        try:
            from backend.staging import canonicalize_filename as _canon_csv
            with open(master_file, 'r', encoding='utf-8') as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    filename = row.get('Filename', '')
                    if filename:
                        already_graded.add(filename)
                        already_graded.add(_canon_csv(filename))  # type: ignore[no-untyped-call]
        except Exception as e:
            # Behavior-critical: if we can't read the master CSV, the
            # already_graded set stays empty and previously-graded files
            # may be regraded (cost + duplicate results). Sentry must see
            # this so the corrupted CSV gets fixed.
            _logger.error("Failed to load master_grades.csv for already_graded set: %s", e)
            sentry_sdk.capture_exception(e)

    # Also check in-memory results (loaded from saved JSON)
    # Track which files are verified (have markers/config) for skip_verified option
    # Canonicalize all filenames so they match staged canonical names
    from backend.staging import canonicalize_filename as _canon
    verified_files = set()
    for r in grading_state.get("results", []):
        if r.get("filename"):
            already_graded.add(r["filename"])
            already_graded.add(_canon(r["filename"]))  # type: ignore[no-untyped-call]
            # Track verified status for skip_verified filtering
            if r.get("marker_status") == "verified":
                verified_files.add(r["filename"])
                verified_files.add(_canon(r["filename"]))  # type: ignore[no-untyped-call]

    if already_graded:
        grading_state["log"].append(f"Found {len(already_graded)} previously graded files")
        if verified_files:
            grading_state["log"].append(f"  ({len(verified_files)} verified, {len(already_graded) - len(verified_files)} unverified)")
    return already_graded, verified_files


def _load_period_maps(
    *,
    grading_state: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    student_period_map = {}  # Maps student name -> period name
    period_class_level_map = {}  # Maps period name -> class level (standard/advanced/support)
    periods_dir = os.path.expanduser("~/.graider_data/periods")
    if os.path.exists(periods_dir):
        import csv
        for period_file in os.listdir(periods_dir):
            if period_file.endswith('.csv'):
                period_name = period_file.replace('.csv', '')
                class_level = 'standard'  # Default

                # Load class_level from metadata file if it exists
                meta_path = os.path.join(periods_dir, f"{period_file}.meta.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r') as mf:
                            meta = json.load(mf)
                            period_name = meta.get('period_name', period_name)
                            class_level = meta.get('class_level', 'standard')
                    except Exception as e:
                        # Best-effort: malformed metadata falls back to
                        # defaults (period name from filename, standard
                        # class level). Less personalization, not broken.
                        _logger.debug("Failed to load period metadata %s: %s", meta_path, e)

                period_class_level_map[period_name] = class_level

                try:
                    with open(os.path.join(periods_dir, period_file), 'r', encoding='utf-8') as pf:
                        reader = csv.DictReader(pf)
                        for row in reader:
                            # Try common column names for student name
                            first = row.get('FirstName', row.get('First Name', row.get('first_name', ''))).strip()
                            last = row.get('LastName', row.get('Last Name', row.get('last_name', ''))).strip()
                            full_name = row.get('Name', row.get('Student Name', row.get('Student', row.get('name', '')))).strip()

                            if first and last:
                                student_key = f"{first} {last}".lower()
                                student_period_map[student_key] = period_name
                            elif full_name:
                                # Handle "Last; First" or "Last, First" formats
                                if '; ' in full_name:
                                    parts = full_name.split('; ', 1)
                                    if len(parts) == 2:
                                        student_key = f"{parts[1]} {parts[0]}".lower()
                                        student_period_map[student_key] = period_name
                                elif ', ' in full_name:
                                    parts = full_name.split(', ', 1)
                                    if len(parts) == 2:
                                        last_name = parts[0].strip()
                                        first_name = parts[1].strip()
                                        # Full key: "First Middle Last1 Last2"
                                        student_key = f"{first_name} {last_name}".lower()
                                        student_period_map[student_key] = period_name
                                        # Also add short key: "FirstWord LastWord" for filename matching
                                        first_simple = first_name.split()[0].lower() if first_name else ''
                                        last_simple = last_name.split()[0].lower() if last_name else ''
                                        if first_simple and last_simple:
                                            short_key = f"{first_simple} {last_simple}"
                                            if short_key != student_key:
                                                student_period_map[short_key] = period_name
                                else:
                                    student_period_map[full_name.lower()] = period_name
                except Exception as e:
                    grading_state["log"].append(f"Warning: Could not load period file {period_file}: {e}")

        if student_period_map:
            grading_state["log"].append(f"Loaded period data for {len(student_period_map)} students")
            # Log class levels
            advanced_count = sum(1 for v in period_class_level_map.values() if v == 'advanced')
            support_count = sum(1 for v in period_class_level_map.values() if v == 'support')
            if advanced_count or support_count:
                grading_state["log"].append(f"  Class levels: {advanced_count} advanced, {support_count} support, {len(period_class_level_map) - advanced_count - support_count} standard")
    return student_period_map, period_class_level_map


def _run_grading_thread_inner(
    assignments_folder: str,
    output_folder: str,
    roster_file: str,
    assignment_config: Optional[dict[str, Any]] = None,
    global_ai_notes: str = '',
    grading_period: str = 'Q3',
    grade_level: str = '7',
    subject: str = 'Social Studies',
    teacher_name: str = '',
    school_name: str = '',
    selected_files: Optional[list[str]] = None,
    ai_model: str = 'gpt-4o-mini',
    skip_verified: bool = False,
    class_period: str = '',
    rubric: Optional[dict[str, Any]] = None,
    ensemble_models: Optional[list[str]] = None,
    extraction_mode: str = 'structured',
    trusted_students: Optional[list[str]] = None,
    grading_style: str = 'standard',
    teacher_id: str = 'local-dev',
) -> None:
    """Inner grading logic (extracted so run_grading_thread can wrap with BYOK context)."""
    # Shadow globals with per-teacher locals — all 100+ references below just work unchanged
    grading_state = _get_state(teacher_id)
    grading_lock = _get_lock(teacher_id)
    def _update_state(**kwargs: Any) -> None:
        with grading_lock:
            grading_state.update(kwargs)

    # Log global AI notes status
    if global_ai_notes:
        preview = global_ai_notes[:100].replace('\n', ' ')
        _logger.info("[GRADING] Global AI Instructions received: %d chars - \"%s...\"", len(global_ai_notes), preview)
    else:
        _logger.info("[GRADING] No Global AI Instructions provided")

    # Format rubric and log status
    rubric_prompt = format_rubric_for_prompt(rubric)  # type: ignore[no-untyped-call]
    if rubric_prompt:
        cat_count = len(rubric.get('categories', [])) if rubric else 0
        _logger.info("[GRADING] Custom rubric loaded: %d categories", cat_count)
        grading_state["log"].append(f"📋 Using custom rubric ({cat_count} categories)")
    else:
        _logger.info("[GRADING] No custom rubric - using default")

    # Build rubric_weights list for score aggregation
    # The breakdown always has 4 categories in order: content_accuracy, completeness, writing_quality, effort_engagement
    # Rubric categories map positionally to these (1st=content, 2nd=completeness, 3rd=writing, 4th=effort)
    rubric_weights = None
    if rubric and rubric.get('categories'):
        cats = rubric['categories']
        weights = [cat.get('weight', 0) for cat in cats]
        # Only use custom weights if they differ from the default 40/25/20/15
        default_weights = [40, 25, 20, 15]
        if len(weights) == 4 and weights != default_weights:
            rubric_weights = weights
            cat_names = [cat.get('name', '') for cat in cats]
            _logger.info("[GRADING] Custom rubric weights: %s", list(zip(cat_names, weights)))

    # Load ALL saved assignment configs for auto-matching
    all_configs = {}
    assignments_dir = os.path.expanduser("~/.graider_assignments")
    if os.path.exists(assignments_dir):
        for f in os.listdir(assignments_dir):
            if f.endswith('.json'):
                config_name = f.replace('.json', '')
                try:
                    with open(os.path.join(assignments_dir, f), 'r') as cf:
                        all_configs[config_name.lower()] = json.load(cf)
                except Exception as e:
                    # Best-effort: malformed/missing config file just means this
                    # one entry isn't available for matching. Other configs work.
                    _logger.debug("Failed to load assignment config %s: %s", f, e)

    # Extract custom markers, notes, and response sections from selected config (fallback)
    fallback_markers = []
    fallback_notes = ''
    fallback_sections = []
    fallback_exclude_markers = []
    fallback_imported_doc: dict[str, Any] = {}
    fallback_rubric_type = 'standard'
    fallback_custom_rubric = None
    fallback_completion_only = False
    fallback_use_section_points = False
    fallback_effort_points = 15
    if assignment_config:
        fallback_markers = assignment_config.get('customMarkers', [])
        fallback_notes = assignment_config.get('gradingNotes', '')
        fallback_sections = assignment_config.get('responseSections', [])
        fallback_exclude_markers = assignment_config.get('excludeMarkers', [])
        fallback_imported_doc = assignment_config.get('importedDoc') or {}
        fallback_rubric_type = assignment_config.get('rubricType') or 'standard'
        fallback_custom_rubric = assignment_config.get('customRubric', None)
        fallback_completion_only = assignment_config.get('completionOnly', False)
        fallback_use_section_points = assignment_config.get('useSectionPoints', False)
        fallback_effort_points = assignment_config.get('effortPoints', 15)

    try:
        from assignment_grader import (
            load_roster, parse_filename, read_assignment_file,
            extract_student_work, grade_assignment, grade_multipass, grade_with_parallel_detection,
            grade_with_ensemble, STUDENT_WORK_MARKERS
        )

        if all_configs:
            grading_state["log"].append(f"Loaded {len(all_configs)} assignment configs for auto-matching")

        if global_ai_notes:
            grading_state["log"].append(f"Global AI notes loaded")

        # Load support documents (rubrics, curriculum guides, standards)
        support_docs_content = load_support_documents_for_grading(subject)
        if support_docs_content:
            grading_state["log"].append(f"Loaded reference documents for AI context")

        # Load student-to-period mapping from period CSVs for per-student grading levels
        student_period_map, period_class_level_map = _load_period_maps(
            grading_state=grading_state,
        )

        os.makedirs(output_folder, exist_ok=True)

        already_graded, verified_files = _load_already_graded(
            grading_state=grading_state,
            output_folder=output_folder,
        )

        grading_state["log"].append("Loading student roster...")
        roster = load_roster(roster_file)
        grading_state["log"].append(f"Loaded {len(roster)//2} students")

        # Stage files: canonicalize names and deduplicate (keeps newest per student+assignment)
        from backend.staging import stage_files
        stage_result = stage_files(assignments_folder, log_fn=grading_state["log"].append)  # type: ignore[no-untyped-call]
        staging_folder = stage_result["staging_folder"]
        resubmissions = stage_result.get("resubmissions", set())

        staging_path = Path(staging_folder)
        all_files: list[Any] = []
        for ext in ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png', '*.pdf']:
            all_files.extend(staging_path.glob(ext))

        # Filter by selected files if provided (match canonical names)
        if selected_files is not None and len(selected_files) > 0:
            from backend.staging import canonicalize_filename as _canon
            selected_canonical = set(_canon(f) for f in selected_files)  # type: ignore[no-untyped-call]
            all_files = [f for f in all_files if f.name in selected_canonical]
            grading_state["log"].append(f"Matched {len(all_files)} of {len(selected_files)} selected files")
        else:
            grading_state["log"].append(f"Found {len(all_files)} total files (no filter applied)")

        # Filter out already graded files (only if not using selection)
        # Resubmissions bypass the already_graded filter — they have newer content
        if selected_files is None:
            new_files = [f for f in all_files
                         if f.name not in already_graded or f.name in resubmissions]
            resubmit_count = sum(1 for f in new_files if f.name in resubmissions and f.name in already_graded)
            if resubmit_count > 0:
                grading_state["log"].append(f"Re-grading {resubmit_count} resubmission(s) with newer versions")
            skipped = len(all_files) - len(new_files)
            if skipped > 0:
                grading_state["log"].append(f"Skipping {skipped} already-graded files")
        else:
            # When files are selected, grade them even if previously graded (re-grade)
            # BUT if skip_verified is True, skip files that were previously verified
            if skip_verified and verified_files:
                new_files = [f for f in all_files if f.name not in verified_files]
                skipped_verified = len(all_files) - len(new_files)
                if skipped_verified > 0:
                    grading_state["log"].append(f"Skipping {skipped_verified} verified grades (regrading only unverified)")
            else:
                new_files = all_files

        _update_state(total=len(new_files))
        grading_state["log"].append(f"Queued {len(new_files)} files for grading")

        if len(new_files) == 0:
            grading_state["log"].append("")
            grading_state["log"].append("All files have already been graded!")
            _update_state(complete=True, is_running=False)
            return

        all_grades: list[Any] = []

        # ═══════════════════════════════════════════════════════════
        # PARALLEL GRADING — build per-file kwargs here, then run the
        # executor loop (extracted to _grade_all_files in CQ7 PR-4)
        # ═══════════════════════════════════════════════════════════
        PARALLEL_WORKERS = 3  # Conservative: 3 students at once (6 API calls with detection)

        grading_state["log"].append(f"⚡ Parallel grading enabled ({PARALLEL_WORKERS} workers)")
        grading_state["log"].append("")

        gsf_kwargs: dict[str, Any] = dict(
            ai_model=ai_model,
            all_configs=all_configs,
            assignment_config=assignment_config,
            class_period=class_period,
            ensemble_models=ensemble_models,
            extraction_mode=extraction_mode,
            fallback_completion_only=fallback_completion_only,
            fallback_custom_rubric=fallback_custom_rubric,
            fallback_effort_points=fallback_effort_points,
            fallback_exclude_markers=fallback_exclude_markers,
            fallback_imported_doc=fallback_imported_doc,
            fallback_markers=fallback_markers,
            fallback_notes=fallback_notes,
            fallback_rubric_type=fallback_rubric_type,
            fallback_sections=fallback_sections,
            fallback_use_section_points=fallback_use_section_points,
            global_ai_notes=global_ai_notes,
            grade_level=grade_level,
            grading_state=grading_state,
            grading_style=grading_style,
            output_folder=output_folder,
            period_class_level_map=period_class_level_map,
            resubmissions=resubmissions,
            roster=roster,
            rubric_prompt=rubric_prompt,
            rubric_weights=rubric_weights,
            student_period_map=student_period_map,
            subject=subject,
            teacher_id=teacher_id,
            trusted_students=trusted_students,
        )
        api_error_occurred = _grade_all_files(
            PARALLEL_WORKERS=PARALLEL_WORKERS,
            _update_state=_update_state,
            ai_model=ai_model,
            all_grades=all_grades,
            grading_lock=grading_lock,
            grading_period=grading_period,
            grading_state=grading_state,
            gsf_kwargs=gsf_kwargs,
            new_files=new_files,
            resubmissions=resubmissions,
            selected_files=selected_files,
        )

        # Handle API error - stop and save
        if api_error_occurred:
            _update_state(complete=True, is_running=False)
            with grading_lock:
                results_copy = list(grading_state["results"])
            if results_copy:
                save_results(results_copy, teacher_id)
            return

        # Export CSVs and emails
        _export_results(
            all_grades=all_grades,
            grading_state=grading_state,
            output_folder=output_folder,
            school_name=school_name,
            subject=subject,
            teacher_name=teacher_name,
        )

        grading_state["log"].append("")
        grading_state["log"].append("=" * 50)

        if grading_state.get("stop_requested", False):
            grading_state["log"].append(f"GRADING STOPPED - {len(all_grades)} files saved")
            grading_state["log"].append("Restart to continue with remaining files")
        else:
            grading_state["log"].append("GRADING COMPLETE!")

        grading_state["log"].append(f"Results saved to: {output_folder}")
        _update_state(complete=True)

        # Post-batch calibration check
        with grading_lock:
            results_snapshot = list(grading_state["results"])
        calibration = _check_batch_calibration(results_snapshot)
        if not calibration["calibrated"]:
            for concern in calibration["concerns"]:
                grading_state["log"].append(f"⚠️ CALIBRATION: {concern}")
            _update_state(calibration=calibration)

        # Save results to storage for persistence across restarts
        save_results(results_snapshot, teacher_id)

    except Exception as e:
        _update_state(error=str(e))
        sentry_sdk.capture_exception(e)
        grading_state["log"].append(f"Error: {str(e)}")
    finally:
        _update_state(is_running=False, stop_requested=False)
        # Also save on stop/error to preserve partial results
        with grading_lock:
            results_copy = list(grading_state["results"])
        if results_copy:
            save_results(results_copy, teacher_id)


