"""
NotebookLM API routes.
Provides endpoints for authenticating with NotebookLM, creating notebooks
from lesson plans, generating materials, and downloading results.
"""
import logging
import os
import json
import threading
from flask import Blueprint, request, jsonify, send_file, g

_logger = logging.getLogger(__name__)

notebooklm_bp = Blueprint("notebooklm", __name__)

# ── Lazy import guard (notebooklm-py is optional) ───────────────────────

_nlm_available = None


def _check_nlm_available():
    global _nlm_available
    if _nlm_available is None:
        try:
            import notebooklm  # noqa: F401
            _nlm_available = True
        except ImportError:
            _nlm_available = False
    return _nlm_available


def _get_teacher_id():
    return getattr(g, "user_id", "local-dev")


# ── Startup hooks ───────────────────────────────────────────────────────

@notebooklm_bp.record_once
def _on_register(state):
    """Run cleanup on blueprint registration."""
    if _check_nlm_available():
        from backend.services.notebooklm_service import (
            cleanup_stale_states, cleanup_expired_materials
        )
        cleanup_stale_states()
        cleanup_expired_materials()


# ── Routes ───────────────────────────────────────────────────────────────

@notebooklm_bp.route("/api/notebooklm/auth-status")
def nlm_auth_status():
    if not _check_nlm_available():
        return jsonify({
            "authenticated": False,
            "available": False,
            "error": "NotebookLM not installed. Run: pip install 'notebooklm-py[browser]'"
        })
    from backend.services.notebooklm_service import is_authenticated
    teacher_id = _get_teacher_id()
    return jsonify({"authenticated": is_authenticated(teacher_id), "available": True})


@notebooklm_bp.route("/api/notebooklm/login", methods=["POST"])
def nlm_login():
    if not _check_nlm_available():
        return jsonify({"error": "NotebookLM not installed"})
    from backend.services.notebooklm_service import (
        login_browser, complete_login, cancel_login, is_authenticated
    )

    teacher_id = _get_teacher_id()
    data = request.json or {}
    step = data.get("step", "start")

    try:
        if step == "complete":
            # User clicked "I'm logged in" — save cookies, close browser
            complete_login(teacher_id)
            return jsonify({"success": is_authenticated(teacher_id)})
        elif step == "cancel":
            cancel_login(teacher_id)
            return jsonify({"status": "cancelled"})
        else:
            # Already authenticated?
            if is_authenticated(teacher_id):
                return jsonify({"success": True, "already_authenticated": True})
            # Open Chromium for Google login
            login_browser(teacher_id)
            return jsonify({
                "browser_opened": True,
                "message": "Complete Google login in the browser window, then click 'I'm logged in'"
            })
    except Exception:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


ALLOWED_CONTEXT_EXTENSIONS = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt"}


@notebooklm_bp.route("/api/notebooklm/upload-context", methods=["POST"])
def nlm_upload_context():
    """Upload a reference document (PDF, image, docx) for NotebookLM context."""
    teacher_id = _get_teacher_id()
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_CONTEXT_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 400

    upload_dir = os.path.expanduser(f"~/.graider_notebooklm/context_uploads/{teacher_id}")
    os.makedirs(upload_dir, exist_ok=True)

    # Use original filename, avoid overwrites with a counter
    base, extension = os.path.splitext(file.filename)
    save_path = os.path.join(upload_dir, file.filename)
    counter = 1
    while os.path.exists(save_path):
        save_path = os.path.join(upload_dir, f"{base}_{counter}{extension}")
        counter += 1

    file.save(save_path)
    return jsonify({
        "path": save_path,
        "filename": os.path.basename(save_path),
        "size": os.path.getsize(save_path),
    })


@notebooklm_bp.route("/api/notebooklm/create-notebook", methods=["POST"])
def nlm_create_notebook():
    if not _check_nlm_available():
        return jsonify({"error": "NotebookLM not installed"})
    from backend.services.notebooklm_service import create_notebook, is_authenticated, _fresh_state, _save_state

    teacher_id = _get_teacher_id()
    if not is_authenticated(teacher_id):
        return jsonify({"error": "session_expired", "needs_login": True})

    # Clear stale results from any previous generation run
    _save_state(teacher_id, _fresh_state())

    data = request.json or {}
    plan = data.get("plan", {})
    standards = data.get("standards", [])
    config = data.get("config", {})
    support_doc_paths = data.get("support_doc_paths", [])

    title = "Graider: " + plan.get("title", "Lesson Plan")

    try:
        notebook_id = create_notebook(
            title, plan, standards, config,
            teacher_id=teacher_id,
            support_doc_paths=support_doc_paths
        )
        return jsonify({"notebook_id": notebook_id, "status": "created"})
    except Exception as e:
        error_msg = str(e)
        if any(kw in error_msg.lower() for kw in ("auth", "login", "cookie", "session")):
            return jsonify({"error": "session_expired", "needs_login": True})
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@notebooklm_bp.route("/api/notebooklm/generate", methods=["POST"])
def nlm_generate():
    if not _check_nlm_available():
        return jsonify({"error": "NotebookLM not installed"})
    from backend.services.notebooklm_service import (
        get_generation_state, run_generation_thread, is_authenticated, _save_state
    )

    teacher_id = _get_teacher_id()
    if not is_authenticated(teacher_id):
        return jsonify({"error": "session_expired", "needs_login": True})

    data = request.json or {}
    notebook_id = data.get("notebook_id")
    material_types = data.get("materials", [])
    options = data.get("options", {})

    if not notebook_id:
        return jsonify({"error": "Missing notebook_id"})
    if not material_types:
        return jsonify({"error": "No material types selected"})

    state = get_generation_state(teacher_id)

    if state.get("is_running"):
        return jsonify({"error": "Generation already in progress"})

    # Reset state
    state.update({
        "is_running": True,
        "progress": [],
        "completed": [],
        "errors": [],
        "notebook_id": notebook_id,
        "materials": {},
    })
    _save_state(teacher_id, state)

    thread = threading.Thread(
        target=run_generation_thread,
        args=(teacher_id, notebook_id, material_types, options),
        daemon=True,
    )
    thread.start()

    return jsonify({"status": "started", "materials": material_types})


@notebooklm_bp.route("/api/notebooklm/status")
def nlm_status():
    if not _check_nlm_available():
        return jsonify({"is_running": False, "progress": [], "completed": [], "errors": [], "materials": {}})
    from backend.services.notebooklm_service import get_generation_state

    teacher_id = _get_teacher_id()
    state = get_generation_state(teacher_id)
    return jsonify({
        "is_running": state.get("is_running", False),
        "progress": state.get("progress", []),
        "completed": state.get("completed", []),
        "errors": state.get("errors", []),
        "materials": {k: os.path.basename(v) for k, v in state.get("materials", {}).items()},
    })


@notebooklm_bp.route("/api/notebooklm/download/<material_type>")
def nlm_download(material_type):
    if not _check_nlm_available():
        return jsonify({"error": "NotebookLM not installed"}), 400
    from backend.services.notebooklm_service import get_generation_state, MATERIAL_EXTENSIONS

    teacher_id = _get_teacher_id()
    state = get_generation_state(teacher_id)

    file_path = state.get("materials", {}).get(material_type)
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "Material not found: " + material_type}), 404

    # Convert study guide markdown to DOCX for download
    if material_type == "study_guide" and file_path.endswith(".md"):
        from backend.services.notebooklm_service import _md_to_docx
        docx_path = file_path.replace(".md", ".docx")
        if not os.path.exists(docx_path) or os.path.getmtime(file_path) > os.path.getmtime(docx_path):
            _md_to_docx(file_path, docx_path)
        return send_file(
            docx_path,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name="study_guide.docx"
        )

    ext = MATERIAL_EXTENSIONS.get(material_type, "bin")
    mime_types = {
        "mp3": "audio/mpeg",
        "mp4": "video/mp4",
        "json": "application/json",
        "md": "text/markdown",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "png": "image/png",
        "csv": "text/csv",
    }
    # ?inline=1 serves the file for in-browser preview (no download prompt)
    inline = request.args.get("inline") == "1"
    return send_file(
        file_path,
        mimetype=mime_types.get(ext, "application/octet-stream"),
        as_attachment=not inline,
        download_name=material_type + "." + ext
    )


@notebooklm_bp.route("/api/notebooklm/preview/<material_type>")
def nlm_preview(material_type):
    """Return preview data for JSON/markdown materials."""
    if not _check_nlm_available():
        return jsonify({"error": "NotebookLM not installed"}), 400
    from backend.services.notebooklm_service import get_generation_state

    teacher_id = _get_teacher_id()
    state = get_generation_state(teacher_id)

    file_path = state.get("materials", {}).get(material_type)
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "Material not found"}), 404

    if material_type in ("quiz", "flashcards", "mind_map"):
        with open(file_path, "r") as f:
            data = json.load(f)
        return jsonify({"type": material_type, "data": data})
    elif material_type == "study_guide":
        with open(file_path, "r") as f:
            content = f.read()
        return jsonify({"type": material_type, "content": content})
    else:
        return jsonify({"error": "Preview not available for " + material_type}), 400


@notebooklm_bp.route("/api/notebooklm/cancel", methods=["POST"])
def nlm_cancel():
    if not _check_nlm_available():
        return jsonify({"status": "not_running"})
    from backend.services.notebooklm_service import get_generation_state, _save_state

    teacher_id = _get_teacher_id()
    state = get_generation_state(teacher_id)
    if state.get("is_running"):
        state["is_running"] = False
        state["errors"].append("Cancelled by user")
        _save_state(teacher_id, state)
        return jsonify({"status": "cancelled"})
    return jsonify({"status": "not_running"})


@notebooklm_bp.route("/api/notebooklm/retry", methods=["POST"])
def nlm_retry():
    if not _check_nlm_available():
        return jsonify({"error": "NotebookLM not installed"})
    from backend.services.notebooklm_service import (
        get_generation_state, run_generation_thread, is_authenticated, _save_state
    )

    teacher_id = _get_teacher_id()
    if not is_authenticated(teacher_id):
        return jsonify({"error": "session_expired", "needs_login": True})

    state = get_generation_state(teacher_id)

    if state.get("is_running"):
        return jsonify({"error": "Generation already in progress"})

    # Extract failed types from error messages (format: "type: error msg")
    failed_types = [e.split(":")[0].strip() for e in state.get("errors", [])
                    if ":" in e and e.split(":")[0].strip() != "Cancelled by user"]
    if not failed_types:
        return jsonify({"error": "No failed materials to retry"})

    notebook_id = state.get("notebook_id")
    if not notebook_id:
        return jsonify({"error": "No notebook to retry against"})

    # Keep existing completed + materials, clear errors
    state["is_running"] = True
    state["errors"] = []
    _save_state(teacher_id, state)

    data = request.json or {}
    options = data.get("options", {})

    thread = threading.Thread(
        target=run_generation_thread,
        args=(teacher_id, notebook_id, failed_types, options),
        daemon=True,
    )
    thread.start()
    return jsonify({"status": "retrying", "materials": failed_types})


@notebooklm_bp.route("/api/notebooklm/share-material", methods=["POST"])
def share_material():
    """Publish any NotebookLM material for students via join code."""
    from backend.supabase_client import get_supabase_or_raise as get_supabase
    from backend.routes.student_portal_routes import generate_join_code
    from backend.services.notebooklm_service import (
        get_generation_state, MATERIAL_EXTENSIONS
    )
    import shutil

    data = request.json or {}
    material_type = data.get("material_type")
    title = data.get("title", material_type or "Material")

    if not material_type:
        return jsonify({"error": "No material_type provided"}), 400

    teacher_id = _get_teacher_id()
    state = get_generation_state(teacher_id)

    # JSON-storable types: store data inline
    json_types = ("quiz", "flashcards", "mind_map")
    text_types = ("study_guide",)
    # Media types: copy file and store path
    media_types = ("audio_overview", "video_overview", "infographic",
                   "data_table", "slide_deck")

    assessment_data = {"content_type": material_type, "title": title}

    if material_type in json_types:
        file_path = state.get("materials", {}).get(material_type)
        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "Material not generated yet"}), 404
        with open(file_path, "r") as f:
            assessment_data["data"] = json.load(f)

    elif material_type in text_types:
        file_path = state.get("materials", {}).get(material_type)
        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "Material not generated yet"}), 404
        with open(file_path, "r") as f:
            assessment_data["content"] = f.read()

    elif material_type in media_types:
        file_path = state.get("materials", {}).get(material_type)
        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "Material not generated yet"}), 404
        # Copy file to shared directory keyed by a unique name
        from backend.services.notebooklm_service import NOTEBOOKLM_DATA_DIR
        shared_dir = os.path.join(NOTEBOOKLM_DATA_DIR, "shared")
        os.makedirs(shared_dir, exist_ok=True)
        ext = MATERIAL_EXTENSIONS.get(material_type, "bin")
        # Use timestamp to avoid collisions
        import time
        shared_filename = f"{material_type}_{int(time.time())}.{ext}"
        shared_path = os.path.join(shared_dir, shared_filename)
        shutil.copy2(file_path, shared_path)
        assessment_data["shared_file"] = shared_filename
    else:
        return jsonify({"error": f"Unknown material type: {material_type}"}), 400

    try:
        db = get_supabase()
        code = generate_join_code()

        db.table("published_assessments").insert({
            "join_code": code,
            "title": title,
            "assessment": assessment_data,
            "settings": {"content_type": material_type},
            "teacher_name": data.get("teacher_name", "Teacher"),
            "is_active": True,
        }).execute()

        host = request.host_url.rstrip("/")
        return jsonify({
            "success": True,
            "join_code": code,
            "join_link": host + "/join/" + code,
        })
    except Exception:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@notebooklm_bp.route("/api/student/shared-media/<code>")
def serve_shared_media(code):
    """Serve media files for shared materials (student-accessible)."""
    from backend.supabase_client import get_supabase_or_raise as get_supabase
    from backend.services.notebooklm_service import (
        NOTEBOOKLM_DATA_DIR, MATERIAL_EXTENSIONS
    )

    try:
        db = get_supabase()
        result = db.table("published_assessments").select(
            "assessment, settings, is_active"
        ).eq("join_code", code.upper()).execute()

        if not result.data:
            return jsonify({"error": "Not found"}), 404

        record = result.data[0]
        if not record.get("is_active", True):
            return jsonify({"error": "No longer available"}), 403

        assessment = record.get("assessment", {})
        shared_filename = assessment.get("shared_file")
        if not shared_filename:
            return jsonify({"error": "No media file"}), 404

        shared_dir = os.path.join(NOTEBOOKLM_DATA_DIR, "shared")
        file_path = os.path.join(shared_dir, shared_filename)

        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404

        material_type = assessment.get("content_type", "")
        ext = MATERIAL_EXTENSIONS.get(material_type, "bin")
        mime_types = {
            "mp3": "audio/mpeg", "mp4": "video/mp4",
            "json": "application/json", "md": "text/markdown",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "png": "image/png", "csv": "text/csv",
        }
        return send_file(
            file_path,
            mimetype=mime_types.get(ext, "application/octet-stream"),
            as_attachment=False,
            download_name=material_type + "." + ext,
        )
    except Exception:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500
