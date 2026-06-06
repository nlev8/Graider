"""
Automation Routes — Playwright Workflow Builder backend.
CRUD for workflow JSON files + subprocess launch + element picker IPC.
"""
import os
import json
import re
import atexit
import signal
import subprocess
import threading
import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors
import sentry_sdk

_logger = logging.getLogger(__name__)

automation_bp = Blueprint('automation', __name__)

AUTOMATIONS_DIR = os.path.expanduser("~/.graider_data/automations")
GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNNER_SCRIPT = os.path.join(PROJECT_ROOT, "backend", "automation", "runner.js")
PICKER_SCRIPT = os.path.join(PROJECT_ROOT, "backend", "automation", "picker.js")
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "backend", "automation", "templates")

os.makedirs(AUTOMATIONS_DIR, exist_ok=True)


def _teacher_automations_dir(teacher_id):
    """Per-tenant automations dir (audit #8). Mirrors storage._tenant_home:
    'local-dev' (or falsy) keeps the historical flat layout; any real teacher_id
    gets an isolated subdir. Without this, automation CRUD/run was unscoped — and
    because a workflow's id is derived from its NAME (predictable + collision-prone),
    two teachers' same-named workflows would also overwrite each other in one global
    file. `teacher_id` is sanitized so it can't escape the automations root."""
    base = AUTOMATIONS_DIR
    if teacher_id and teacher_id != 'local-dev':
        safe_tid = re.sub(r'[^a-zA-Z0-9_-]', '_', str(teacher_id))
        base = os.path.join(AUTOMATIONS_DIR, safe_tid)
    os.makedirs(base, exist_ok=True)
    return base

# ── Run state ────────────────────────────────────────────────
_run_state = {
    "process": None,
    "status": "idle",
    "workflow_name": "",
    "current_step": 0,
    "total_steps": 0,
    "step_label": "",
    "message": "",
    "log": [],
}

_picker_state = {
    "process": None,
    "status": "idle",
    "events": [],
}


def _cleanup_subprocesses():
    """Kill any running automation/picker processes on shutdown."""
    for state in (_run_state, _picker_state):
        proc = state.get("process")
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    _logger.debug("automation subprocess kill failed", exc_info=True)

atexit.register(_cleanup_subprocesses)


def _read_runner_output(proc):
    """Background thread: read subprocess NDJSON stdout, update _run_state."""
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            etype = event.get("type", "")
            if etype == "start":
                _run_state["total_steps"] = event.get("total_steps", 0)
            elif etype == "step_start":
                _run_state["current_step"] = int(event.get("step", "0").split(".")[0])
                _run_state["step_label"] = event.get("label", "")
                _run_state["message"] = "Step " + event.get("step", "?") + ": " + event.get("label", "")
            elif etype == "step_done":
                _run_state["message"] = "Done: " + event.get("label", "")
            elif etype == "step_error":
                _run_state["message"] = "Error on '" + event.get("label", "") + "': " + event.get("message", "")
            elif etype == "status":
                _run_state["message"] = event.get("message", "")
            elif etype == "done":
                _run_state["status"] = "done"
                _run_state["message"] = event.get("message", "Complete")
            elif etype == "error":
                _run_state["status"] = "error"
                _run_state["message"] = event.get("message", "Unknown error")
            _run_state["log"].append(event)
            if len(_run_state["log"]) > 200:
                _run_state["log"] = _run_state["log"][-100:]
        except json.JSONDecodeError:
            pass

    if _run_state["status"] == "running":
        _run_state["status"] = "done"


def _read_picker_output(proc):
    """Read picker subprocess stdout, accumulate selector events."""
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "selector_picked":
                _picker_state["events"].append(event)
            elif event.get("type") == "done":
                _picker_state["status"] = "done"
        except json.JSONDecodeError:
            pass
    if _picker_state["status"] == "picking":
        _picker_state["status"] = "done"


# ── CRUD ──────────────────────────────────────────────────────

@automation_bp.route('/api/automations', methods=['GET'])
@require_teacher
@handle_route_errors
def list_automations():
    """List all saved workflow files."""
    tdir = _teacher_automations_dir(g.teacher_id)
    workflows = []
    for filename in sorted(os.listdir(tdir)):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(tdir, filename), 'r') as f:
                wf = json.load(f)
            workflows.append({
                "id": wf.get("id", filename.replace('.json', '')),
                "name": wf.get("name", filename),
                "description": wf.get("description", ""),
                "step_count": len(wf.get("steps", [])),
                "updated_at": wf.get("updated_at", ""),
            })
        except Exception as e:
            sentry_sdk.capture_exception(e)
    return jsonify({"workflows": workflows})


@automation_bp.route('/api/automations/<workflow_id>', methods=['GET'])
@require_teacher
@handle_route_errors
def get_automation(workflow_id):
    """Load a specific workflow JSON."""
    safe_id = re.sub(r'[^a-z0-9_-]', '', workflow_id)
    filepath = os.path.join(_teacher_automations_dir(g.teacher_id), safe_id + ".json")
    if not os.path.exists(filepath):
        return jsonify({"error": "Workflow not found"}), 404
    with open(filepath, 'r') as f:
        return jsonify(json.load(f))


@automation_bp.route('/api/automations', methods=['POST'])
@require_teacher
@handle_route_errors
def save_automation():
    """Save or create a workflow."""
    data = request.json
    if not data or not data.get("name"):
        return jsonify({"error": "Workflow name required"}), 400

    raw_id = data.get("id") or re.sub(r'[^a-z0-9]+', '-', data["name"].lower()).strip('-')
    # Sanitize the (possibly client-supplied) id the SAME way the URL handlers
    # sanitize workflow_id. Without this a crafted body id like
    # "../<other-teacher>/<wf>" escapes the per-teacher subdir and overwrites
    # another tenant's workflow (audit #8 — caught by Codex verification).
    wf_id = re.sub(r'[^a-z0-9_-]', '', str(raw_id))
    if not wf_id:
        return jsonify({"error": "Invalid workflow id"}), 400
    data["id"] = wf_id
    data.setdefault("version", 1)
    data.setdefault("created_at", datetime.now().isoformat())
    data["updated_at"] = datetime.now().isoformat()

    for i, step in enumerate(data.get("steps", [])):
        step.setdefault("id", "step-" + str(i + 1))

    filepath = os.path.join(_teacher_automations_dir(g.teacher_id), wf_id + ".json")
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    return jsonify({"status": "saved", "id": wf_id})


@automation_bp.route('/api/automations/<workflow_id>', methods=['DELETE'])
@require_teacher
@handle_route_errors
def delete_automation(workflow_id):
    """Delete a workflow file."""
    safe_id = re.sub(r'[^a-z0-9_-]', '', workflow_id)
    filepath = os.path.join(_teacher_automations_dir(g.teacher_id), safe_id + ".json")
    if os.path.exists(filepath):
        os.remove(filepath)
    return jsonify({"status": "deleted"})


@automation_bp.route('/api/automations/templates', methods=['GET'])
@require_teacher
@handle_route_errors
def list_templates():
    """Return built-in template workflows."""
    templates = []
    if os.path.isdir(TEMPLATES_DIR):
        for filename in sorted(os.listdir(TEMPLATES_DIR)):
            if not filename.endswith('.json'):
                continue
            try:
                with open(os.path.join(TEMPLATES_DIR, filename), 'r') as f:
                    wf = json.load(f)
                templates.append({
                    "id": wf.get("id", filename.replace('.json', '')),
                    "name": wf.get("name", filename),
                    "description": wf.get("description", ""),
                    "step_count": len(wf.get("steps", [])),
                    "is_template": True,
                })
            except Exception as e:
                sentry_sdk.capture_exception(e)
    return jsonify({"templates": templates})


@automation_bp.route('/api/automations/templates/<template_id>', methods=['GET'])
@require_teacher
@handle_route_errors
def get_template(template_id):
    """Load a specific template by ID."""
    if not os.path.isdir(TEMPLATES_DIR):
        return jsonify({"error": "Template not found"}), 404
    for filename in os.listdir(TEMPLATES_DIR):
        if not filename.endswith('.json'):
            continue
        filepath = os.path.join(TEMPLATES_DIR, filename)
        try:
            with open(filepath, 'r') as f:
                wf = json.load(f)
            if wf.get("id") == template_id:
                return jsonify(wf)
        except Exception as e:
            sentry_sdk.capture_exception(e)
    return jsonify({"error": "Template not found"}), 404


@automation_bp.route('/api/automations/templates/<template_id>', methods=['DELETE'])
@require_teacher
@handle_route_errors
def delete_template(template_id):
    """Delete a template file by matching its JSON id field."""
    if not os.path.isdir(TEMPLATES_DIR):
        return jsonify({"status": "deleted"})
    for filename in os.listdir(TEMPLATES_DIR):
        if not filename.endswith('.json'):
            continue
        filepath = os.path.join(TEMPLATES_DIR, filename)
        try:
            with open(filepath, 'r') as f:
                wf = json.load(f)
            if wf.get("id") == template_id:
                os.remove(filepath)
                return jsonify({"status": "deleted"})
        except Exception as e:
            sentry_sdk.capture_exception(e)
    return jsonify({"status": "deleted"})


# ── Run ──────────────────────────────────────────────────────

@automation_bp.route('/api/automations/<workflow_id>/run', methods=['POST'])
@require_teacher
@handle_route_errors
def run_automation(workflow_id):
    """Launch workflow as subprocess."""
    if _run_state.get("status") == "running":
        return jsonify({"error": "An automation is already running"}), 409

    safe_id = re.sub(r'[^a-z0-9_-]', '', workflow_id)
    workflow_path = os.path.join(_teacher_automations_dir(g.teacher_id), safe_id + ".json")
    if not os.path.exists(workflow_path):
        return jsonify({"error": "Workflow not found"}), 404

    if not os.path.exists(RUNNER_SCRIPT):
        return jsonify({"error": "runner.js not found"}), 500

    data = request.json or {}
    var_args = []
    for k, v in data.get("vars", {}).items():
        var_args.extend(["--var", str(k) + "=" + str(v)])

    # Closes GH #245 (Codex rounds 2 + 3 + 4): runner.js login step
    # reads creds; populate the per-teacher creds file BEFORE launching
    # so concurrent workflows for different teachers each read their
    # own credentials. write_temp_creds_file returns False on Supabase
    # miss + no local file — fail fast rather than spawning a
    # subprocess that hits a missing creds file mid-run. Preflight
    # runs BEFORE the _run_state mutation so a 400 here does not leave
    # the run endpoint stuck in "running" (next call would hit 409).
    teacher_id = getattr(g, 'user_id', 'local-dev')
    from backend.routes.assistant_routes import (
        _portal_credentials_file_for,
        write_temp_creds_file,
    )
    if not write_temp_creds_file(teacher_id):
        return jsonify({"error": "VPortal credentials not configured. Go to Settings > Tools to set them up."}), 400
    creds_path = _portal_credentials_file_for(teacher_id)
    sub_env = {**os.environ, 'GRAIDER_PORTAL_CREDS_FILE': creds_path}

    _run_state.update({
        "process": None, "status": "running",
        "workflow_name": workflow_id,
        # Tenant isolation (audit #8 / Codex): the runner is a single global
        # subprocess, so record who owns the current run. status/stop gate on this
        # so one teacher can't read or kill another teacher's run.
        "teacher_id": g.teacher_id,
        "current_step": 0, "total_steps": 0,
        "step_label": "", "message": "Starting automation...",
        "log": [],
    })

    proc = subprocess.Popen(
        ["node", RUNNER_SCRIPT, workflow_path] + var_args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
        env=sub_env,
    )
    _run_state["process"] = proc
    threading.Thread(target=_read_runner_output, args=(proc,), daemon=True).start()
    return jsonify({"status": "started"})


@automation_bp.route('/api/automations/run/status', methods=['GET'])
@require_teacher
@handle_route_errors
def run_status():
    """Poll current automation run state."""
    # Tenant isolation (audit #8 / Codex): the runner is a single global
    # subprocess. Only surface it to the teacher who started it; everyone else
    # sees idle (no leak of another tenant's workflow_name / progress / log).
    if _run_state.get("teacher_id") != g.teacher_id:
        return jsonify({
            "status": "idle", "workflow_name": "", "current_step": 0,
            "total_steps": 0, "step_label": "", "message": "", "log": [],
        })
    return jsonify({
        "status": _run_state.get("status", "idle"),
        "workflow_name": _run_state.get("workflow_name", ""),
        "current_step": _run_state.get("current_step", 0),
        "total_steps": _run_state.get("total_steps", 0),
        "step_label": _run_state.get("step_label", ""),
        "message": _run_state.get("message", ""),
        "log": _run_state.get("log", [])[-20:],
    })


@automation_bp.route('/api/automations/run/stop', methods=['POST'])
@require_teacher
@handle_route_errors
def stop_run():
    """Kill running automation subprocess."""
    # Tenant isolation (audit #8 / Codex): don't let one teacher stop another
    # teacher's run (DoS). Only the owner of an active run may stop it; an idle
    # state is a harmless no-op for anyone.
    if _run_state.get("status") != "idle" and _run_state.get("teacher_id") not in (None, g.teacher_id):
        return jsonify({"error": "No running automation"}), 404
    proc = _run_state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
    _run_state["status"] = "idle"
    _run_state["message"] = "Stopped by user"
    return jsonify({"status": "stopped"})


# ── Element Picker ───────────────────────────────────────────

@automation_bp.route('/api/automations/picker/start', methods=['POST'])
@require_teacher
@handle_route_errors
def start_picker():
    """Launch element picker browser."""
    if _picker_state.get("status") == "picking":
        return jsonify({"error": "Picker already running"}), 409

    if not os.path.exists(PICKER_SCRIPT):
        return jsonify({"error": "picker.js not found"}), 500

    data = request.json or {}
    start_url = data.get("url", "https://vportal.volusia.k12.fl.us/")
    auto_login = data.get("login", False)

    # Tenant isolation (audit #8 / Codex): single global picker subprocess —
    # record the owner so events/stop can be gated to the teacher who started it.
    _picker_state.update({"status": "picking", "events": [], "process": None,
                          "teacher_id": g.teacher_id})

    cmd = ["node", PICKER_SCRIPT, "--url", start_url]
    if auto_login:
        cmd.append("--login")

    # Closes GH #245 (Codex rounds 2 + 3): picker.js loads creds when
    # --login is set; populate the per-teacher creds file BEFORE
    # launching so concurrent picker sessions don't read each other's
    # credentials. Only required when auto_login=True since picker.js
    # skips loadCredentials() otherwise.
    teacher_id = getattr(g, 'user_id', 'local-dev')
    from backend.routes.assistant_routes import (
        _portal_credentials_file_for,
        write_temp_creds_file,
    )
    if auto_login and not write_temp_creds_file(teacher_id):
        _picker_state["status"] = "idle"
        return jsonify({"error": "VPortal credentials not configured. Go to Settings > Tools to set them up."}), 400
    creds_path = _portal_credentials_file_for(teacher_id)
    sub_env = {**os.environ, 'GRAIDER_PORTAL_CREDS_FILE': creds_path}

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
        env=sub_env,
    )
    _picker_state["process"] = proc
    threading.Thread(target=_read_picker_output, args=(proc,), daemon=True).start()
    return jsonify({"status": "picker_started"})


@automation_bp.route('/api/automations/picker/events', methods=['GET'])
@require_teacher
@handle_route_errors
def picker_events():
    """Drain and return accumulated picker events."""
    # Tenant isolation (audit #8 / Codex): only the teacher who started the picker
    # may drain its events — otherwise another tenant could read A's selector
    # events and starve A of them (the buffer is drained on read).
    if _picker_state.get("teacher_id") != g.teacher_id:
        return jsonify({"status": "idle", "events": []})
    events = list(_picker_state.get("events", []))
    _picker_state["events"] = []
    return jsonify({"status": _picker_state.get("status", "idle"), "events": events})


@automation_bp.route('/api/automations/picker/stop', methods=['POST'])
@require_teacher
@handle_route_errors
def stop_picker():
    """Close picker browser."""
    # Tenant isolation (audit #8 / Codex): only the owner may stop an active
    # picker (don't let one tenant kill another's picker browser).
    if _picker_state.get("status") != "idle" and _picker_state.get("teacher_id") not in (None, g.teacher_id):
        return jsonify({"error": "No active picker"}), 404
    proc = _picker_state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
    _picker_state["status"] = "idle"
    return jsonify({"status": "stopped"})
