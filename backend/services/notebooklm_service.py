"""
NotebookLM service wrapper.
Wraps the async notebooklm-py API for synchronous Flask usage.
Follows the same threading + state pattern as the grading engine.
"""
import os
import re
import json
import asyncio
import threading
import time
from pathlib import Path

# ── Configurable paths (env vars for container deployments) ──────────────

NOTEBOOKLM_DATA_DIR = os.environ.get(
    "GRAIDER_NLM_DATA_DIR",
    os.path.expanduser("~/.graider_data/notebooklm")
)

STORAGE_STATE_DIR = os.path.join(NOTEBOOKLM_DATA_DIR, "sessions")

RETENTION_DAYS = int(os.environ.get("GRAIDER_NLM_RETENTION_DAYS", "30"))

# ── Material type mappings ───────────────────────────────────────────────

MATERIAL_EXTENSIONS = {
    "audio_overview": "mp3",
    "video_overview": "mp4",
    "quiz": "json",
    "flashcards": "json",
    "study_guide": "md",
    "slide_deck": "pptx",
    "mind_map": "json",
    "infographic": "png",
    "data_table": "csv",
}

MATERIAL_FILENAMES = {
    "audio_overview": "podcast.mp3",
    "video_overview": "video.mp4",
    "quiz": "quiz.json",
    "flashcards": "flashcards.json",
    "study_guide": "study_guide.md",
    "slide_deck": "slides.pptx",
    "mind_map": "mindmap.json",
    "infographic": "infographic.png",
    "data_table": "data_table.csv",
}

# ── Per-user credential isolation ────────────────────────────────────────


def _get_storage_path(teacher_id="local-dev"):
    """Each teacher gets their own NotebookLM session file."""
    os.makedirs(STORAGE_STATE_DIR, exist_ok=True)
    return os.path.join(STORAGE_STATE_DIR, teacher_id + "_storage_state.json")


def _get_default_storage_path():
    """Get the default notebooklm CLI storage path."""
    try:
        from notebooklm.auth import get_storage_path
        return str(get_storage_path())
    except ImportError:
        return os.path.expanduser("~/.notebooklm/storage_state.json")


def is_authenticated(teacher_id="local-dev"):
    """Check session: env var (containers), per-user file, or default CLI path."""
    if os.environ.get("NOTEBOOKLM_AUTH_JSON"):
        return True
    # Check per-user session file
    if os.path.exists(_get_storage_path(teacher_id)):
        return True
    # Fall back to default CLI auth (from `notebooklm login`)
    return os.path.exists(_get_default_storage_path())


# ── Playwright login management ──────────────────────────────────────────

# Active login sessions: { teacher_id: { "context": BrowserContext, "playwright": Playwright } }
_login_sessions = {}
_login_lock = threading.Lock()


def login_browser(teacher_id="local-dev"):
    """Open a Playwright Chromium browser for Google login.
    Non-blocking — opens the browser and returns immediately.
    Call complete_login() after the user finishes logging in."""
    import sys
    if sys.platform == "linux" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        raise RuntimeError(
            "No display server available. For containerized deployments, "
            "run 'notebooklm login' locally and set NOTEBOOKLM_AUTH_JSON env var "
            "with the JSON contents of ~/.notebooklm/storage_state.json"
        )

    with _login_lock:
        if teacher_id in _login_sessions:
            raise RuntimeError("Login already in progress")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: pip install 'notebooklm-py[browser]' && playwright install chromium"
        )

    storage_path = _get_storage_path(teacher_id)
    # Each teacher gets their own browser profile so sessions don't cross-contaminate
    browser_profile = Path(STORAGE_STATE_DIR) / ("profile_" + teacher_id)
    Path(storage_path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    browser_profile.mkdir(parents=True, exist_ok=True, mode=0o700)

    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        user_data_dir=str(browser_profile),
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--password-store=basic",
        ],
        ignore_default_args=["--enable-automation"],
    )

    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://notebooklm.google.com/")

    with _login_lock:
        _login_sessions[teacher_id] = {
            "context": context,
            "playwright": pw,
            "storage_path": storage_path,
        }


def complete_login(teacher_id="local-dev"):
    """Save storage state and close the login browser.
    Call after the user has completed Google login in the browser."""
    with _login_lock:
        session = _login_sessions.pop(teacher_id, None)

    if not session:
        raise RuntimeError("No login session in progress")

    context = session["context"]
    pw = session["playwright"]
    storage_path = session["storage_path"]

    try:
        context.storage_state(path=storage_path)
        Path(storage_path).chmod(0o600)
    finally:
        context.close()
        pw.stop()


def cancel_login(teacher_id="local-dev"):
    """Close the login browser without saving credentials."""
    with _login_lock:
        session = _login_sessions.pop(teacher_id, None)

    if session:
        try:
            session["context"].close()
        except Exception:
            pass
        try:
            session["playwright"].stop()
        except Exception:
            pass


# ── File-backed generation state ─────────────────────────────────────────


def _state_path(teacher_id):
    os.makedirs(NOTEBOOKLM_DATA_DIR, exist_ok=True)
    return os.path.join(NOTEBOOKLM_DATA_DIR, teacher_id + "_state.json")


def get_generation_state(teacher_id="local-dev"):
    """Load state from disk, falling back to fresh state."""
    path = _state_path(teacher_id)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return _fresh_state()


def _fresh_state():
    return {
        "is_running": False,
        "progress": [],
        "completed": [],
        "errors": [],
        "notebook_id": None,
        "materials": {},
    }


def _save_state(teacher_id, state):
    """Persist state to disk after each update."""
    os.makedirs(NOTEBOOKLM_DATA_DIR, exist_ok=True)
    path = _state_path(teacher_id)
    with open(path, "w") as f:
        json.dump(state, f)


# ── Startup cleanup hooks ───────────────────────────────────────────────


def cleanup_stale_states():
    """Reset any is_running states from crashed processes."""
    if not os.path.exists(NOTEBOOKLM_DATA_DIR):
        return
    for fname in os.listdir(NOTEBOOKLM_DATA_DIR):
        if fname.endswith("_state.json"):
            path = os.path.join(NOTEBOOKLM_DATA_DIR, fname)
            try:
                with open(path, "r") as f:
                    state = json.load(f)
                if state.get("is_running"):
                    state["is_running"] = False
                    state["errors"].append("Generation interrupted by server restart")
                    with open(path, "w") as f:
                        json.dump(state, f)
            except (json.JSONDecodeError, IOError):
                pass


def cleanup_expired_materials():
    """Delete NotebookLM artifacts older than RETENTION_DAYS."""
    if not os.path.exists(NOTEBOOKLM_DATA_DIR):
        return
    cutoff = time.time() - (RETENTION_DAYS * 86400)
    for dirname in os.listdir(NOTEBOOKLM_DATA_DIR):
        dirpath = os.path.join(NOTEBOOKLM_DATA_DIR, dirname)
        if not os.path.isdir(dirpath) or dirname == "sessions":
            continue
        meta_path = os.path.join(dirpath, "metadata.json")
        if os.path.exists(meta_path):
            if os.path.getmtime(meta_path) < cutoff:
                import shutil
                shutil.rmtree(dirpath, ignore_errors=True)


# ── PII sanitization ────────────────────────────────────────────────────


def _sanitize_for_external(text):
    """Remove student names, IEP references, and PII before sending to NotebookLM.
    NotebookLM is an external Google service -- never send student-identifiable data."""
    # Strip IEP/504 accommodation blocks
    text = re.sub(r'(?i)(iep|504|accommodation|individualized education).*?\n', '', text)
    # Strip student name patterns (Last, First)
    text = re.sub(r'[A-Z][a-z]+,\s+[A-Z][a-z]+', '[Student]', text)
    return text


# ── Source formatting ────────────────────────────────────────────────────


def format_lesson_plan_as_source(plan, standards, config):
    """Convert lesson plan JSON + standards into structured text for NotebookLM source.

    FERPA NOTE: This function intentionally excludes student-identifiable data.
    Only curriculum content (objectives, vocabulary, activities, standards) is included.
    The _sanitize_for_external() pass is a safety net against accidental PII leakage.
    """
    parts = []

    # Title and metadata
    title = plan.get("title", "Lesson Plan")
    parts.append("# " + title)
    subject = config.get("subject", "")
    grade = config.get("grade", config.get("grade_level", ""))
    if subject or grade:
        parts.append("Subject: " + str(subject) + " | Grade: " + str(grade))

    # Overview
    overview = plan.get("overview", "")
    if overview:
        parts.append("\n## Overview\n" + overview)

    # Essential questions
    eq = plan.get("essential_questions", [])
    if eq:
        parts.append("\n## Essential Questions")
        for q in eq:
            parts.append("- " + str(q))

    # Standards
    if standards:
        parts.append("\n## Standards Addressed")
        for std in standards:
            if isinstance(std, dict):
                code = std.get("code", "")
                benchmark = std.get("benchmark", "")
                vocab = std.get("vocabulary", [])
                targets = std.get("learning_targets", [])
                parts.append("- **" + code + "**: " + benchmark)
                if vocab:
                    parts.append("  Vocabulary: " + ", ".join(str(v) for v in vocab[:15]))
                if targets:
                    for t in targets[:3]:
                        parts.append("  - " + str(t))
            else:
                parts.append("- " + str(std))

    # Days (lesson/unit plans)
    days = plan.get("days", [])
    for day in days:
        day_num = day.get("day", "?")
        topic = day.get("topic", "")
        parts.append("\n## Day " + str(day_num) + ": " + topic)

        obj = day.get("objective", "")
        if obj:
            parts.append("**Objective**: " + obj)

        # Vocabulary
        vocab = day.get("vocabulary", [])
        if vocab:
            parts.append("\n### Vocabulary")
            for v in vocab:
                if isinstance(v, dict):
                    parts.append("- **" + v.get("term", "") + "**: " + v.get("definition", ""))
                else:
                    parts.append("- " + str(v))

        # Bell ringer
        br = day.get("bell_ringer", {})
        if br and br.get("prompt"):
            parts.append("\n### Bell Ringer\n" + br["prompt"])

        # Direct instruction
        di = day.get("direct_instruction", {})
        if di and di.get("key_points"):
            parts.append("\n### Key Points")
            for kp in di["key_points"]:
                parts.append("- " + str(kp))

        # Activity
        act = day.get("activity", {})
        if act and act.get("name"):
            parts.append("\n### Activity: " + act["name"])
            if act.get("description"):
                parts.append(act["description"])

        # Assessment
        assess = day.get("assessment", {})
        if assess and assess.get("description"):
            parts.append("\n### Assessment\n" + assess["description"])
            if assess.get("exit_ticket"):
                parts.append("Exit Ticket: " + assess["exit_ticket"])

    # Sections (assignment-type plans)
    sections = plan.get("sections", [])
    if sections and not days:
        parts.append("\n## Assignment Sections")
        for section in sections:
            sname = section.get("name", "Section")
            pts = section.get("points", 0)
            parts.append("\n### " + sname + " (" + str(pts) + " pts)")
            for q in section.get("questions", []):
                qnum = q.get("number", "")
                qtext = q.get("question", q.get("text", ""))
                parts.append("Q" + str(qnum) + ": " + str(qtext))
                ans = q.get("answer", q.get("correct_answer", ""))
                if ans:
                    parts.append("  Answer: " + str(ans))

    # Phases (project-type plans)
    phases = plan.get("phases", [])
    if phases:
        parts.append("\n## Project Phases")
        for phase in phases:
            pname = phase.get("name", "Phase")
            parts.append("\n### " + pname)
            if phase.get("description"):
                parts.append(phase["description"])
            for d in phase.get("deliverables", []):
                parts.append("- Deliverable: " + str(d))

    raw_text = "\n".join(parts)
    return _sanitize_for_external(raw_text)


# ── Notebook creation ────────────────────────────────────────────────────


async def _create_notebook_with_sources(title, sources_list, storage_path=None):
    """Create a NotebookLM notebook and add sources. Returns notebook ID."""
    from notebooklm import NotebookLMClient

    if storage_path:
        client_ctx = await NotebookLMClient.from_storage(path=storage_path)
    else:
        client_ctx = await NotebookLMClient.from_storage()

    async with client_ctx as client:
        nb = await client.notebooks.create(title)
        for src in sources_list:
            if src["type"] == "text":
                await client.sources.add_text(nb.id, src["content"], wait=True)
            elif src["type"] == "url":
                await client.sources.add_url(nb.id, src["url"], wait=True)
            elif src["type"] == "file":
                await client.sources.add_file(nb.id, src["path"], wait=True)
        return nb.id


def _resolve_storage_path(teacher_id):
    """Find the best available storage path for a teacher."""
    per_user = _get_storage_path(teacher_id)
    if os.path.exists(per_user):
        return per_user
    default = _get_default_storage_path()
    if os.path.exists(default):
        return default
    return None


def create_notebook(title, plan, standards, config, teacher_id="local-dev", support_doc_paths=None):
    """Create NotebookLM notebook with lesson plan as source. Synchronous wrapper."""
    source_text = format_lesson_plan_as_source(plan, standards, config)
    sources = [{"type": "text", "content": source_text}]

    # Add support documents as file sources
    if support_doc_paths:
        for doc_path in support_doc_paths:
            if os.path.exists(doc_path):
                sources.append({"type": "file", "path": doc_path})

    storage_path = _resolve_storage_path(teacher_id)
    notebook_id = asyncio.run(
        _create_notebook_with_sources(title, sources, storage_path)
    )

    # Save metadata
    nb_dir = os.path.join(NOTEBOOKLM_DATA_DIR, notebook_id)
    os.makedirs(nb_dir, exist_ok=True)
    metadata = {
        "notebook_id": notebook_id,
        "plan_title": plan.get("title", "Untitled"),
        "subject": config.get("subject", ""),
        "grade": config.get("grade", config.get("grade_level", "")),
        "teacher_id": teacher_id,
        "created_at": time.time(),
    }
    with open(os.path.join(nb_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return notebook_id


# ── Material generation ──────────────────────────────────────────────────


async def _generate_single_material(notebook_id, material_type, options, output_dir, storage_path=None):
    """Generate one material type. Returns output file path."""
    from notebooklm import NotebookLMClient

    os.makedirs(output_dir, exist_ok=True)
    filename = MATERIAL_FILENAMES.get(material_type, material_type + ".bin")
    out_path = os.path.join(output_dir, filename)

    if storage_path:
        client_ctx = await NotebookLMClient.from_storage(path=storage_path)
    else:
        client_ctx = await NotebookLMClient.from_storage()

    async with client_ctx as client:
        if material_type == "audio_overview":
            status = await client.artifacts.generate_audio(
                notebook_id,
                format=options.get("format", "deep-dive"),
                length=options.get("length", "medium"),
                language=options.get("language", "en"),
                instructions=options.get("instructions", ""),
            )
            await client.artifacts.wait_for_completion(notebook_id, status.task_id)
            await client.artifacts.download_audio(notebook_id, out_path)

        elif material_type == "video_overview":
            status = await client.artifacts.generate_video(
                notebook_id,
                style=options.get("style", "classic"),
            )
            await client.artifacts.wait_for_completion(notebook_id, status.task_id)
            await client.artifacts.download_video(notebook_id, out_path)

        elif material_type == "quiz":
            status = await client.artifacts.generate_quiz(
                notebook_id,
                quantity=options.get("quantity", "default"),
                difficulty=options.get("difficulty", "medium"),
            )
            await client.artifacts.wait_for_completion(notebook_id, status.task_id)
            await client.artifacts.download_quiz(notebook_id, out_path, output_format="json")

        elif material_type == "flashcards":
            status = await client.artifacts.generate_flashcards(
                notebook_id,
                quantity=options.get("quantity", "default"),
                difficulty=options.get("difficulty", "medium"),
            )
            await client.artifacts.wait_for_completion(notebook_id, status.task_id)
            await client.artifacts.download_flashcards(notebook_id, out_path, output_format="json")

        elif material_type == "study_guide":
            status = await client.artifacts.generate_report(
                notebook_id,
                template=options.get("format", "study_guide"),
            )
            await client.artifacts.wait_for_completion(notebook_id, status.task_id)
            await client.artifacts.download_report(notebook_id, out_path)

        elif material_type == "slide_deck":
            status = await client.artifacts.generate_slides(
                notebook_id,
                format=options.get("format", "detailed"),
            )
            await client.artifacts.wait_for_completion(notebook_id, status.task_id)
            await client.artifacts.download_slides(notebook_id, out_path, output_format="pptx")

        elif material_type == "mind_map":
            status = await client.artifacts.generate_mindmap(notebook_id)
            await client.artifacts.wait_for_completion(notebook_id, status.task_id)
            await client.artifacts.download_mindmap(notebook_id, out_path)

        elif material_type == "infographic":
            status = await client.artifacts.generate_infographic(
                notebook_id,
                orientation=options.get("orientation", "portrait"),
            )
            await client.artifacts.wait_for_completion(notebook_id, status.task_id)
            await client.artifacts.download_infographic(notebook_id, out_path)

        elif material_type == "data_table":
            status = await client.artifacts.generate_table(notebook_id)
            await client.artifacts.wait_for_completion(notebook_id, status.task_id)
            await client.artifacts.download_table(notebook_id, out_path)

    return out_path


def run_generation_thread(teacher_id, notebook_id, material_types, options):
    """Background thread: generate each material type sequentially, updating state."""
    state = get_generation_state(teacher_id)
    output_dir = os.path.join(NOTEBOOKLM_DATA_DIR, notebook_id)
    storage_path = _resolve_storage_path(teacher_id)

    try:
        for mat_type in material_types:
            if not state.get("is_running"):
                break  # cancelled

            state["progress"].append({
                "type": mat_type,
                "message": "Generating " + mat_type.replace("_", " ") + "...",
            })
            _save_state(teacher_id, state)

            try:
                mat_options = options.get(mat_type, {})
                out_path = asyncio.run(
                    _generate_single_material(
                        notebook_id, mat_type, mat_options, output_dir, storage_path
                    )
                )
                state["materials"][mat_type] = out_path
                state["completed"].append(mat_type)
            except Exception as e:
                state["errors"].append(mat_type + ": " + str(e))

            _save_state(teacher_id, state)
    finally:
        state["is_running"] = False
        _save_state(teacher_id, state)
