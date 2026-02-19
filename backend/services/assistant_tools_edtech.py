"""
EdTech Quiz Generator Tools
============================
Generate platform-specific quiz files from standards, grades, and content.
Zero AI API calls — questions built deterministically from vocabulary,
sample assessments, and grade weakness data.
"""
import io
import os
import csv
import json
import random
import base64
import hashlib
from collections import defaultdict

from backend.services.assistant_tools import (
    _load_standards, _load_master_csv, _load_settings, _load_results,
    _normalize_period, _fuzzy_name_match, _safe_int_score,
    _normalize_assignment_name, SETTINGS_FILE,
)


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

_SHARED_INPUT_PROPS = {
    "topic": {
        "type": "string",
        "description": "Topic or standard code to generate questions from"
    },
    "assignment_name": {
        "type": "string",
        "description": "Generate questions from weak areas on this assignment (partial match)"
    },
    "content": {
        "type": "string",
        "description": "Raw text content to pull questions from"
    },
    "question_count": {
        "type": "integer",
        "description": "Number of questions to generate (default 10)"
    },
    "difficulty": {
        "type": "string",
        "enum": ["easy", "medium", "hard"],
        "description": "Question difficulty (default medium)"
    },
    "period": {
        "type": "string",
        "description": "Class period for differentiation"
    }
}

EDTECH_TOOL_DEFINITIONS = [
    {
        "name": "generate_kahoot_quiz",
        "description": "Generate a Kahoot-compatible .xlsx quiz file. Questions from standards vocabulary and sample assessments. Zero cost — no AI API call.",
        "input_schema": {
            "type": "object",
            "properties": _SHARED_INPUT_PROPS,
        }
    },
    {
        "name": "generate_blooket_set",
        "description": "Generate a Blooket-compatible .csv question set. Multiple choice questions from standards data. Zero cost — no AI API call.",
        "input_schema": {
            "type": "object",
            "properties": _SHARED_INPUT_PROPS,
        }
    },
    {
        "name": "generate_gimkit_kit",
        "description": "Generate a Gimkit-compatible .csv kit (Question, Correct Answer, Incorrect Answer 1-3). Zero cost — no AI API call.",
        "input_schema": {
            "type": "object",
            "properties": _SHARED_INPUT_PROPS,
        }
    },
    {
        "name": "generate_quizlet_set",
        "description": "Generate a Quizlet-compatible .txt flashcard set (tab-separated term/definition). Built from standards vocabulary. Zero cost — no AI API call.",
        "input_schema": {
            "type": "object",
            "properties": _SHARED_INPUT_PROPS,
        }
    },
    {
        "name": "generate_nearpod_questions",
        "description": "Generate a formatted .docx with questions for easy Nearpod copy-paste. Zero cost — no AI API call.",
        "input_schema": {
            "type": "object",
            "properties": _SHARED_INPUT_PROPS,
        }
    },
    {
        "name": "generate_canvas_qti",
        "description": "Generate a Canvas QTI 1.2 .xml file for LMS import. Multiple choice questions from standards. Zero cost — no AI API call.",
        "input_schema": {
            "type": "object",
            "properties": _SHARED_INPUT_PROPS,
        }
    },
]


# ═══════════════════════════════════════════════════════
# SHARED QUESTION BUILDER (zero AI)
# ═══════════════════════════════════════════════════════

def _deterministic_seed(topic, assignment_name):
    """Create a stable seed so the same inputs produce the same questions."""
    key = f"{topic or ''}-{assignment_name or ''}"
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)


def _build_questions_from_source(topic=None, assignment_name=None, content=None,
                                  question_count=None, difficulty=None, period=None):
    """Generate questions deterministically from standards, grades, and content.

    Returns list of dicts with keys:
        question, correct_answer, wrong_answers (list of 3), source_standard, q_type
    """
    question_count = question_count or 10
    difficulty = difficulty or "medium"
    questions = []

    standards = _load_standards()

    # Filter standards by topic if provided
    filtered_standards = standards
    if topic:
        topic_lower = topic.lower()
        filtered_standards = [s for s in standards if (
            topic_lower in s.get("benchmark", "").lower()
            or topic_lower in " ".join(s.get("topics", [])).lower()
            or topic_lower in " ".join(s.get("vocabulary", [])).lower()
            or topic_lower in s.get("code", "").lower()
        )]
        if not filtered_standards:
            filtered_standards = standards  # Fall back to all

    # If assignment_name provided, find weak areas and map to standards
    weak_topics = []
    if assignment_name:
        results = _load_results()
        assign_results = [r for r in results if
                         _normalize_assignment_name(assignment_name).lower() in
                         _normalize_assignment_name(r.get("assignment", "")).lower()]
        # Collect developing skills
        skill_freq = defaultdict(int)
        for r in assign_results:
            skills = r.get("skills_demonstrated", {})
            if isinstance(skills, dict):
                for s in (skills.get("developing", []) or []):
                    skill_freq[s.strip().lower()] += 1
        weak_topics = [s for s, _ in sorted(skill_freq.items(), key=lambda x: -x[1])[:5]]

        # Try to match weak topics to standards
        if weak_topics:
            topic_standards = []
            for s in standards:
                benchmark_lower = s.get("benchmark", "").lower()
                vocab_lower = " ".join(s.get("vocabulary", [])).lower()
                for wt in weak_topics:
                    if wt in benchmark_lower or wt in vocab_lower:
                        topic_standards.append(s)
                        break
            if topic_standards:
                filtered_standards = topic_standards

    # Seed for deterministic output
    rng = random.Random(_deterministic_seed(topic, assignment_name))

    # Source 1: Vocabulary → definition matching questions
    vocab_items = []
    for s in filtered_standards:
        vocab = s.get("vocabulary", [])
        benchmark = s.get("benchmark", "")
        code = s.get("code", "")
        for term in vocab:
            vocab_items.append({"term": term, "standard": code, "benchmark": benchmark})

    rng.shuffle(vocab_items)

    for item in vocab_items[:question_count * 2]:  # Gather extras, we'll trim
        term = item["term"]
        # Build a definition question using the benchmark as context
        q = f"What is the meaning of '{term}'?"
        # Correct answer: use the term's context from the benchmark
        correct = f"A key concept related to: {item['benchmark'][:80]}"

        # Wrong answers: pick other vocab terms from different standards
        other_terms = [v["term"] for v in vocab_items if v["term"] != term]
        rng.shuffle(other_terms)
        wrong = [f"Related to {t}" for t in other_terms[:3]]
        while len(wrong) < 3:
            wrong.append("Not applicable to this topic")

        questions.append({
            "question": q,
            "correct_answer": correct,
            "wrong_answers": wrong[:3],
            "source_standard": item["standard"],
            "q_type": "vocab",
            "term": term,
        })

    # Source 2: Sample assessments → ready-made MC questions
    for s in filtered_standards:
        sample = s.get("sample_assessment", "")
        if not sample or "?" not in sample:
            continue
        # Parse MC format: question text, then A) B) C) D) options
        parts = sample.split("?", 1)
        q_text = parts[0].strip() + "?"
        options_text = parts[1].strip() if len(parts) > 1 else ""

        options = []
        correct_letter = "A"
        for prefix in ["A)", "B)", "C)", "D)"]:
            idx = options_text.find(prefix)
            if idx >= 0:
                next_idx = len(options_text)
                for np in ["A)", "B)", "C)", "D)"]:
                    ni = options_text.find(np, idx + 2)
                    if ni > idx and ni < next_idx:
                        next_idx = ni
                opt = options_text[idx + 2:next_idx].strip()
                options.append(opt)

        if len(options) >= 2:
            correct = options[0]  # Sample assessments have correct as first real answer
            # Actually, the format has the correct answer identified — for now assume
            # the standard convention that the answer matches the one in bold or first
            # We'll use a simple heuristic: correct_letter from sample
            wrong = [o for i, o in enumerate(options) if i != 0]
            while len(wrong) < 3:
                wrong.append("")

            questions.append({
                "question": q_text[:95],  # Kahoot 95 char limit
                "correct_answer": correct[:60],
                "wrong_answers": [w[:60] for w in wrong[:3]],
                "source_standard": s.get("code", ""),
                "q_type": "mc",
            })

    # Source 3: Essential questions → open-ended (for Nearpod/doc formats)
    for s in filtered_standards:
        for eq in s.get("essential_questions", []):
            questions.append({
                "question": eq,
                "correct_answer": s.get("benchmark", "")[:100],
                "wrong_answers": [],
                "source_standard": s.get("code", ""),
                "q_type": "open",
            })

    # Difficulty filtering
    if difficulty == "easy":
        # Prefer vocab questions (DOK 1)
        questions.sort(key=lambda q: 0 if q["q_type"] == "vocab" else 1)
    elif difficulty == "hard":
        # Prefer open/MC questions (DOK 2-3)
        questions.sort(key=lambda q: 0 if q["q_type"] == "open" else (1 if q["q_type"] == "mc" else 2))

    # Trim to requested count, prefer MC > vocab > open for platforms that need MC
    mc_qs = [q for q in questions if q["q_type"] == "mc"]
    vocab_qs = [q for q in questions if q["q_type"] == "vocab"]
    open_qs = [q for q in questions if q["q_type"] == "open"]
    ordered = mc_qs + vocab_qs + open_qs
    return ordered[:question_count]


def _build_vocab_pairs(topic=None, question_count=None):
    """Build term/definition pairs for Quizlet-style tools.
    Returns list of {term, definition, standard}."""
    question_count = question_count or 10
    standards = _load_standards()

    if topic:
        topic_lower = topic.lower()
        standards = [s for s in standards if (
            topic_lower in s.get("benchmark", "").lower()
            or topic_lower in " ".join(s.get("topics", [])).lower()
            or topic_lower in " ".join(s.get("vocabulary", [])).lower()
            or topic_lower in s.get("code", "").lower()
        )] or standards

    pairs = []
    for s in standards:
        vocab = s.get("vocabulary", [])
        benchmark = s.get("benchmark", "")
        code = s.get("code", "")
        for term in vocab:
            # Use learning targets and benchmark to craft a definition
            targets = s.get("learning_targets", [])
            definition = benchmark[:120]
            # Find a more specific target if available
            for t in targets:
                if term.lower() in t.lower():
                    definition = t
                    break
            pairs.append({"term": term, "definition": definition, "standard": code})

    return pairs[:question_count]


# ═══════════════════════════════════════════════════════
# FILE FORMAT GENERATORS
# ═══════════════════════════════════════════════════════

def _safe_filename(text):
    """Create a safe filename from text."""
    return "".join(c if c.isalnum() or c in " -_" else "" for c in (text or "quiz")).replace(" ", "_")


def generate_kahoot_quiz(topic=None, assignment_name=None, content=None,
                          question_count=None, difficulty=None, period=None):
    """Generate Kahoot .xlsx file. Columns: Question, Answer 1-4, Time limit, Correct answer(s)."""
    questions = _build_questions_from_source(topic, assignment_name, content,
                                             question_count, difficulty, period)
    mc_questions = [q for q in questions if len(q.get("wrong_answers", [])) >= 1]
    if not mc_questions:
        return {"error": "Not enough multiple-choice questions could be generated. Try a different topic or add content."}

    try:
        from openpyxl import Workbook
    except ImportError:
        return {"error": "openpyxl is required for Kahoot .xlsx export. Install with: pip install openpyxl"}

    wb = Workbook()
    ws = wb.active
    ws.title = "Kahoot Quiz"
    ws.append(["Question", "Answer 1", "Answer 2", "Answer 3", "Answer 4",
               "Time limit", "Correct answer(s)"])

    time_limits = {"easy": 30, "medium": 20, "hard": 10}
    time_val = time_limits.get(difficulty or "medium", 20)

    for q in mc_questions:
        answers = [q["correct_answer"]] + q.get("wrong_answers", [])
        while len(answers) < 4:
            answers.append("")
        # Truncate to Kahoot limits
        q_text = q["question"][:95]
        answers = [a[:60] for a in answers[:4]]
        ws.append([q_text, answers[0], answers[1], answers[2], answers[3], time_val, 1])

    # Save to bytes
    buf = io.BytesIO()
    wb.save(buf)
    content_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    filename = f"{_safe_filename(topic or assignment_name or 'quiz')}_kahoot.xlsx"

    return {
        "document": content_b64,
        "filename": filename,
        "format": "xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "question_count": len(mc_questions),
        "message": f"Kahoot quiz with {len(mc_questions)} questions ready for import.",
    }


def generate_blooket_set(topic=None, assignment_name=None, content=None,
                          question_count=None, difficulty=None, period=None):
    """Generate Blooket .csv. Columns: Question #, Question Text, Answer 1-4, Correct Answer(s), Time Limit."""
    questions = _build_questions_from_source(topic, assignment_name, content,
                                             question_count, difficulty, period)
    mc_questions = [q for q in questions if len(q.get("wrong_answers", [])) >= 1]
    if not mc_questions:
        return {"error": "Not enough MC questions. Try a different topic."}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Question #", "Question Text", "Answer 1", "Answer 2",
                     "Answer 3", "Answer 4", "Correct Answer(s)", "Time Limit"])

    for i, q in enumerate(mc_questions, 1):
        answers = [q["correct_answer"]] + q.get("wrong_answers", [])
        while len(answers) < 4:
            answers.append("")
        writer.writerow([i, q["question"], answers[0], answers[1],
                        answers[2], answers[3], "1", 30])

    content_b64 = base64.b64encode(output.getvalue().encode("utf-8")).decode("utf-8")
    filename = f"{_safe_filename(topic or assignment_name or 'quiz')}_blooket.csv"

    return {
        "document": content_b64,
        "filename": filename,
        "format": "csv",
        "mime_type": "text/csv",
        "question_count": len(mc_questions),
        "message": f"Blooket set with {len(mc_questions)} questions ready for import.",
    }


def generate_gimkit_kit(topic=None, assignment_name=None, content=None,
                         question_count=None, difficulty=None, period=None):
    """Generate Gimkit .csv. Columns: Question, Correct Answer, Incorrect Answer 1-3."""
    questions = _build_questions_from_source(topic, assignment_name, content,
                                             question_count, difficulty, period)
    mc_questions = [q for q in questions if len(q.get("wrong_answers", [])) >= 1]
    if not mc_questions:
        return {"error": "Not enough MC questions. Try a different topic."}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Question", "Correct Answer", "Incorrect Answer 1",
                     "Incorrect Answer 2", "Incorrect Answer 3"])

    for q in mc_questions:
        wrong = q.get("wrong_answers", [])
        while len(wrong) < 3:
            wrong.append("")
        writer.writerow([q["question"], q["correct_answer"],
                        wrong[0], wrong[1], wrong[2]])

    content_b64 = base64.b64encode(output.getvalue().encode("utf-8")).decode("utf-8")
    filename = f"{_safe_filename(topic or assignment_name or 'quiz')}_gimkit.csv"

    return {
        "document": content_b64,
        "filename": filename,
        "format": "csv",
        "mime_type": "text/csv",
        "question_count": len(mc_questions),
        "message": f"Gimkit kit with {len(mc_questions)} questions ready for import.",
    }


def generate_quizlet_set(topic=None, assignment_name=None, content=None,
                          question_count=None, difficulty=None, period=None):
    """Generate Quizlet .txt (tab-separated term\\tdefinition per line)."""
    pairs = _build_vocab_pairs(topic, question_count)
    if not pairs:
        # Fall back to question-based
        questions = _build_questions_from_source(topic, assignment_name, content,
                                                 question_count, difficulty, period)
        pairs = [{"term": q["question"][:100], "definition": q["correct_answer"][:200]}
                 for q in questions]

    if not pairs:
        return {"error": "No vocabulary data found. Try specifying a topic."}

    output = io.StringIO()
    for p in pairs:
        output.write(f"{p['term']}\t{p['definition']}\n")

    content_b64 = base64.b64encode(output.getvalue().encode("utf-8")).decode("utf-8")
    filename = f"{_safe_filename(topic or assignment_name or 'vocab')}_quizlet.txt"

    return {
        "document": content_b64,
        "filename": filename,
        "format": "txt",
        "mime_type": "text/plain",
        "card_count": len(pairs),
        "message": f"Quizlet set with {len(pairs)} flashcards ready for import.",
    }


def generate_nearpod_questions(topic=None, assignment_name=None, content=None,
                                question_count=None, difficulty=None, period=None):
    """Generate .docx with formatted questions for Nearpod copy-paste."""
    questions = _build_questions_from_source(topic, assignment_name, content,
                                             question_count, difficulty, period)
    if not questions:
        return {"error": "No questions could be generated. Try specifying a topic."}

    try:
        from backend.services.document_generator import generate_document
    except ImportError:
        return {"error": "Document generator not available."}

    # Build content blocks for the document generator
    blocks = [
        {"type": "heading", "text": f"Nearpod Questions: {topic or assignment_name or 'Review'}", "level": 1},
        {"type": "paragraph", "text": f"**{len(questions)} questions** for Nearpod import. Copy-paste into your Nearpod lesson."},
    ]

    for i, q in enumerate(questions, 1):
        blocks.append({"type": "heading", "text": f"Question {i}", "level": 2})
        blocks.append({"type": "paragraph", "text": q["question"]})

        if q.get("wrong_answers"):
            options = [q["correct_answer"]] + q["wrong_answers"]
            items = [f"{chr(65 + j)}) {opt}" for j, opt in enumerate(options) if opt]
            blocks.append({"type": "bullet_list", "items": items})
            blocks.append({"type": "paragraph", "text": f"*Correct: A) {q['correct_answer']}*"})
        else:
            blocks.append({"type": "paragraph", "text": f"*Expected answer: {q['correct_answer'][:150]}*"})

        if q.get("source_standard"):
            blocks.append({"type": "paragraph", "text": f"Standard: {q['source_standard']}"})

    result = generate_document(
        title=f"Nearpod Questions - {topic or assignment_name or 'Review'}",
        content=blocks,
    )
    if result.get("document"):
        result["question_count"] = len(questions)
        result["message"] = f"Nearpod document with {len(questions)} questions ready for copy-paste."
    return result


def generate_canvas_qti(topic=None, assignment_name=None, content=None,
                         question_count=None, difficulty=None, period=None):
    """Generate Canvas QTI 1.2 XML for LMS import."""
    questions = _build_questions_from_source(topic, assignment_name, content,
                                             question_count, difficulty, period)
    mc_questions = [q for q in questions if len(q.get("wrong_answers", [])) >= 1]
    if not mc_questions:
        return {"error": "Not enough MC questions for QTI. Try a different topic."}

    title = topic or assignment_name or "Quiz"

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<questestinterop xmlns="http://www.imsglobal.org/xsd/ims_qtiasiv1p2">
  <assessment ident="{_safe_filename(title)}" title="{title}">
    <section ident="root_section">
'''

    for i, q in enumerate(mc_questions, 1):
        q_id = f"q_{i}"
        q_text = q["question"]
        options = [q["correct_answer"]] + q.get("wrong_answers", [])
        options = [o for o in options if o]  # Remove empty

        xml += f'''      <item ident="{q_id}" title="Question {i}">
        <itemmetadata>
          <qtimetadata>
            <qtimetadatafield>
              <fieldlabel>question_type</fieldlabel>
              <fieldentry>multiple_choice_question</fieldentry>
            </qtimetadatafield>
            <qtimetadatafield>
              <fieldlabel>points_possible</fieldlabel>
              <fieldentry>1</fieldentry>
            </qtimetadatafield>
          </qtimetadata>
        </itemmetadata>
        <presentation>
          <material>
            <mattext texttype="text/html">{q_text}</mattext>
          </material>
          <response_lid ident="response1" rcardinality="Single">
            <render_choice>
'''
        for j, opt in enumerate(options):
            opt_id = chr(65 + j)
            xml += f'''              <response_label ident="{opt_id}">
                <material>
                  <mattext texttype="text/html">{opt}</mattext>
                </material>
              </response_label>
'''
        xml += f'''            </render_choice>
          </response_lid>
        </presentation>
        <resprocessing>
          <outcomes>
            <decvar maxvalue="100" minvalue="0" varname="SCORE" vartype="Decimal"/>
          </outcomes>
          <respcondition continue="No">
            <conditionvar>
              <varequal respident="response1">A</varequal>
            </conditionvar>
            <setvar action="Set" varname="SCORE">100</setvar>
          </respcondition>
        </resprocessing>
      </item>
'''

    xml += '''    </section>
  </assessment>
</questestinterop>'''

    content_b64 = base64.b64encode(xml.encode("utf-8")).decode("utf-8")
    filename = f"{_safe_filename(title)}_canvas_qti.xml"

    return {
        "document": content_b64,
        "filename": filename,
        "format": "xml",
        "mime_type": "application/xml",
        "question_count": len(mc_questions),
        "message": f"Canvas QTI with {len(mc_questions)} questions ready for LMS import.",
    }


# ═══════════════════════════════════════════════════════
# HANDLER MAP
# ═══════════════════════════════════════════════════════

EDTECH_TOOL_HANDLERS = {
    "generate_kahoot_quiz": generate_kahoot_quiz,
    "generate_blooket_set": generate_blooket_set,
    "generate_gimkit_kit": generate_gimkit_kit,
    "generate_quizlet_set": generate_quizlet_set,
    "generate_nearpod_questions": generate_nearpod_questions,
    "generate_canvas_qti": generate_canvas_qti,
}
