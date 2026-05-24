"""Deterministic provider-SDK fakes for the grader golden net (Wave 7 Phase B).

The grading core (`grade_per_question`, `generate_feedback`, `grade_multipass`,
`grade_assignment`, `detect_ai_plagiarism`, `_translate_feedback`, `grade_with_ensemble`,
`grade_with_parallel_detection`) calls the RAW openai / anthropic / google-generativeai SDKs
inline (function-local imports), each wrapped in `with_retry(lambda: <call>, label=...)`.

This harness builds a FAITHFUL, DETERMINISTIC net by patching the 3 SDK entrypoints
(`openai.OpenAI`, `anthropic.Anthropic`, `google.generativeai.GenerativeModel` +
`google.generativeai.configure`) with provider-shaped fakes and setting env API keys
(`get_api_key` falls through to env; ThreadPoolExecutor workers see env, not contextvars).

Design (3-model reconciled consensus, see
docs/superpowers/specs/2026-05-24-wave7-phaseb-grader-golden-net.md):
- `with_retry` stays REAL (exercises the true call + parse + `_try_parse_json_fallback` path).
- Do NOT patch `_get_api_key` (its bound name moves on extraction) — set env keys instead.
- Per-question responses are CONTENT-MATCHED (derived from the question + points in the prompt)
  → distinct per question, deterministic, robust to fixture changes. Aggregation math is
  therefore genuinely exercised.
- The fake records every call under a Lock (parallel detection + multipass threads are safe).

These fakes return canned payloads; the GOLDEN VALUES are whatever the REAL grader computes
from them — captured once and pinned in the golden tests. The fakes' job is determinism, not
realism of scores.
"""
import json
import re
import threading
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest import mock

# Import the SDK modules so `mock.patch("<module>.<attr>")` can resolve the targets.
# openai + anthropic are required deps; google.generativeai is the OLD Gemini SDK and may be
# absent (this repo's venv ships google-genai instead) — patch it only when importable so the
# harness is robust across environments. The grader's gemini branch ImportErrors gracefully
# when the module is missing, so gemini goldens are simply skipped where it is absent.
import anthropic  # noqa: F401
import openai  # noqa: F401

try:
    import google.generativeai  # noqa: F401
    GEMINI_SDK_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment
    GEMINI_SDK_AVAILABLE = False

# ── Deterministic, content-matched payload builders ───────────────────────────

# Distinct-but-deterministic per-question scoring factor keyed by question text.
_FACTORS = [0.9, 0.7, 1.0]


def _stable_factor(text: str) -> float:
    return _FACTORS[sum(ord(c) for c in text) % len(_FACTORS)]


def _per_question_payload(prompt: str) -> dict:
    """Build a PerQuestionResponse-shaped dict from a grade_per_question prompt.

    Reads POINTS POSSIBLE + QUESTION + STUDENT ANSWER out of the prompt so the score is
    proportional to the question's point value and distinct per question (content-matched).
    """
    pts_m = re.search(r'POINTS POSSIBLE: (\d+)', prompt)
    points = int(pts_m.group(1)) if pts_m else 10
    q_m = re.search(r'QUESTION: (.+)', prompt)
    qtext = q_m.group(1).strip() if q_m else ''
    a_m = re.search(r'STUDENT ANSWER: "(.*?)"', prompt, re.DOTALL)
    answer = (a_m.group(1).strip() if a_m else '')

    if not answer:
        score, quality, is_correct = 0, 'insufficient', False
    else:
        factor = _stable_factor(qtext)
        score = int(round(points * factor))
        quality = 'excellent' if factor >= 0.9 else ('good' if factor >= 0.7 else 'adequate')
        is_correct = factor >= 0.6

    return {
        "grade": {
            "score": score, "possible": points,
            "reasoning": f"Fake per-question grade ({quality}).",
            "is_correct": is_correct, "quality": quality,
        },
        "excellent": score >= int(points * 0.9),
        "improvement_note": "" if score >= int(points * 0.9) else "Add supporting detail.",
    }


def _feedback_payload() -> dict:
    return {
        "feedback": "FAKE_FEEDBACK: Solid understanding shown. Push your analysis further next time.",
        "excellent_answers": ["Your strongest answer was clear and correct."],
        "needs_improvement": ["One answer needed more evidence."],
        "skills_demonstrated": {"strengths": ["factual recall"], "developing": ["analysis"]},
    }


def _detection_payload() -> dict:
    return {
        "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
        "plagiarism_detection": {"flag": "none", "reason": ""},
    }


def _grading_payload() -> dict:
    """Full single-pass GradingResponse-shaped dict (grade_assignment)."""
    return {
        "score": 85, "letter_grade": "B",
        "breakdown": {"content_accuracy": 34, "completeness": 22, "writing_quality": 17, "effort_engagement": 12},
        "student_responses": ["Fake extracted response 1", "Fake extracted response 2"],
        "unanswered_questions": [],
        "excellent_answers": ["A clear, correct answer."],
        "needs_improvement": ["An answer that needed more detail."],
        "skills_demonstrated": {"strengths": ["factual recall"], "developing": ["analysis"]},
        "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
        "plagiarism_detection": {"flag": "none", "reason": ""},
        "feedback": "FAKE_FEEDBACK: single-pass feedback text.",
    }


_TRANSLATION = "FAKE_TRANSLATION: traducción simulada."


def _route_text(blob: str) -> str:
    """Route a raw text/JSON request (anthropic/gemini, and openai text-create) to a canned
    string by schema markers in the prompt. Order matters: grade_assignment's schema also
    contains excellent_answers, so its unique `"letter_grade"` marker is checked first.
    """
    if "Translate the following teacher feedback" in blob:
        return _TRANSLATION
    if '"letter_grade"' in blob:                       # grade_assignment GradingResponse schema
        return json.dumps(_grading_payload())
    if '"possible"' in blob:                            # grade_per_question schema
        return json.dumps(_per_question_payload(blob))
    if '"excellent_answers"' in blob:                   # generate_feedback schema
        return json.dumps(_feedback_payload())
    return json.dumps(_detection_payload())             # fallback (detect_ai_plagiarism text)


# ── Call book (thread-safe call log) ──────────────────────────────────────────

class CallBook:
    def __init__(self):
        self._lock = threading.Lock()
        self.calls = []  # list of dicts: {provider, method, model, schema}

    def record(self, provider, method, model, schema):
        with self._lock:
            self.calls.append({"provider": provider, "method": method, "model": model, "schema": schema})

    def count(self, *, provider=None, method=None, schema=None) -> int:
        with self._lock:
            return sum(
                1 for c in self.calls
                if (provider is None or c["provider"] == provider)
                and (method is None or c["method"] == method)
                and (schema is None or c["schema"] == schema)
            )

    @property
    def total(self) -> int:
        with self._lock:
            return len(self.calls)


# ── Provider-shaped response objects ──────────────────────────────────────────

def _oa_response(parsed=None, content=None, p=120, c=60):
    msg = SimpleNamespace(parsed=parsed, content=content)
    usage = SimpleNamespace(prompt_tokens=p, completion_tokens=c, total_tokens=p + c)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


def _anthropic_response(text, p=120, c=60):
    usage = SimpleNamespace(input_tokens=p, output_tokens=c)
    return SimpleNamespace(content=[SimpleNamespace(text=text)], usage=usage)


def _gemini_response(text, p=120, c=60):
    usage = SimpleNamespace(prompt_token_count=p, candidates_token_count=c)
    return SimpleNamespace(text=text, usage_metadata=usage)


def _user_content(messages) -> str:
    """Concatenate system+user message text from an OpenAI/Anthropic messages list."""
    parts = []
    for m in messages or []:
        content = m.get("content", "") if isinstance(m, dict) else ""
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):  # multimodal: pull text parts
            parts.extend(str(p.get("text", "")) for p in content if isinstance(p, dict))
    return "\n".join(parts)


# ── Fake SDK clients ──────────────────────────────────────────────────────────

class _FakeOpenAI:
    def __init__(self, book, *, force_text=False, **_kw):
        self._book = book
        self._force_text = force_text
        self.beta = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=self._parse))
        )
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _parse(self, *, model, messages, response_format, **_kw):
        name = response_format.__name__
        user = _user_content(messages)
        self._book.record("openai", "parse", model, name)
        if self._force_text:
            # Simulate a structured-parse miss: parsed=None, content carries JSON.
            return _oa_response(parsed=None, content=_route_text(user + ' "parsed_miss"'))
        if name == "PerQuestionResponse":
            payload = _per_question_payload(user)
        elif name == "FeedbackResponse":
            payload = _feedback_payload()
        elif name == "DetectionResponse":
            payload = _detection_payload()
        elif name == "GradingResponse":
            payload = _grading_payload()
        else:
            payload = {}
        parsed = response_format(**payload)  # real Pydantic instance (validates the shape)
        return _oa_response(parsed=parsed, content=json.dumps(payload))

    def _create(self, *, model, messages, **_kw):
        user = _user_content(messages)
        self._book.record("openai", "create", model, None)
        return _oa_response(parsed=None, content=_route_text(user))


class _FakeAnthropic:
    def __init__(self, book, **_kw):
        self._book = book
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, *, model, messages, system="", **_kw):
        blob = (system or "") + "\n" + _user_content(messages)
        self._book.record("anthropic", "create", model, None)
        return _anthropic_response(_route_text(blob))


class _FakeGeminiModel:
    def __init__(self, model, book, **_kw):
        self._model = model
        self._book = book

    def generate_content(self, content, **_kw):
        if isinstance(content, str):
            blob = content
        else:  # list: [prompt_str, image_part]
            blob = "\n".join(c for c in content if isinstance(c, str))
        self._book.record("gemini", "generate", self._model, None)
        return _gemini_response(_route_text(blob))


# ── Context manager ───────────────────────────────────────────────────────────

@contextmanager
def patched_llm(*, force_text=False):
    """Patch the 3 SDK entrypoints + set env keys. Yields a CallBook recording every call.

    force_text=True makes OpenAI's structured `.parse` return parsed=None (content-only),
    exercising the `.parsed`-None fallback paths.
    """
    book = CallBook()
    env = {"OPENAI_API_KEY": "test-openai", "ANTHROPIC_API_KEY": "test-anthropic",
           "GEMINI_API_KEY": "test-gemini"}
    with ExitStack() as stack:
        stack.enter_context(mock.patch.dict("os.environ", env, clear=False))
        stack.enter_context(mock.patch("openai.OpenAI", lambda **kw: _FakeOpenAI(book, force_text=force_text, **kw)))
        stack.enter_context(mock.patch("anthropic.Anthropic", lambda **kw: _FakeAnthropic(book, **kw)))
        if GEMINI_SDK_AVAILABLE:
            stack.enter_context(mock.patch("google.generativeai.GenerativeModel", lambda m, **kw: _FakeGeminiModel(m, book, **kw)))
            stack.enter_context(mock.patch("google.generativeai.configure", lambda **kw: None))
        yield book
