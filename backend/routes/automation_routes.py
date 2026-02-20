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
from datetime import datetime

from flask import Blueprint, request, jsonify

automation_bp = Blueprint('automation', __name__)

AUTOMATIONS_DIR = os.path.expanduser("~/.graider_data/automations")
GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNNER_SCRIPT = os.path.join(PROJECT_ROOT, "backend", "automation", "runner.js")
PICKER_SCRIPT = os.path.join(PROJECT_ROOT, "backend", "automation", "picker.js")
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "backend", "automation", "templates")

os.makedirs(AUTOMATIONS_DIR, exist_ok=True)

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
                    pass

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
def list_automations():
    """List all saved workflow files."""
    workflows = []
    for filename in sorted(os.listdir(AUTOMATIONS_DIR)):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(AUTOMATIONS_DIR, filename), 'r') as f:
                wf = json.load(f)
            workflows.append({
                "id": wf.get("id", filename.replace('.json', '')),
                "name": wf.get("name", filename),
                "description": wf.get("description", ""),
                "step_count": len(wf.get("steps", [])),
                "updated_at": wf.get("updated_at", ""),
            })
        except Exception:
            pass
    return jsonify({"workflows": workflows})


@automation_bp.route('/api/automations/<workflow_id>', methods=['GET'])
def get_automation(workflow_id):
    """Load a specific workflow JSON."""
    safe_id = re.sub(r'[^a-z0-9_-]', '', workflow_id)
    filepath = os.path.join(AUTOMATIONS_DIR, safe_id + ".json")
    if not os.path.exists(filepath):
        return jsonify({"error": "Workflow not found"}), 404
    with open(filepath, 'r') as f:
        return jsonify(json.load(f))


@automation_bp.route('/api/automations', methods=['POST'])
def save_automation():
    """Save or create a workflow."""
    data = request.json
    if not data or not data.get("name"):
        return jsonify({"error": "Workflow name required"}), 400

    wf_id = data.get("id") or re.sub(r'[^a-z0-9]+', '-', data["name"].lower()).strip('-')
    data["id"] = wf_id
    data.setdefault("version", 1)
    data.setdefault("created_at", datetime.now().isoformat())
    data["updated_at"] = datetime.now().isoformat()

    for i, step in enumerate(data.get("steps", [])):
        step.setdefault("id", "step-" + str(i + 1))

    filepath = os.path.join(AUTOMATIONS_DIR, wf_id + ".json")
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    return jsonify({"status": "saved", "id": wf_id})


@automation_bp.route('/api/automations/<workflow_id>', methods=['DELETE'])
def delete_automation(workflow_id):
    """Delete a workflow file."""
    safe_id = re.sub(r'[^a-z0-9_-]', '', workflow_id)
    filepath = os.path.join(AUTOMATIONS_DIR, safe_id + ".json")
    if os.path.exists(filepath):
        os.remove(filepath)
    return jsonify({"status": "deleted"})


@automation_bp.route('/api/automations/templates', methods=['GET'])
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
            except Exception:
                pass
    return jsonify({"templates": templates})


# ── Run ──────────────────────────────────────────────────────

@automation_bp.route('/api/automations/<workflow_id>/run', methods=['POST'])
def run_automation(workflow_id):
    """Launch workflow as subprocess."""
    if _run_state.get("status") == "running":
        return jsonify({"error": "An automation is already running"}), 409

    safe_id = re.sub(r'[^a-z0-9_-]', '', workflow_id)
    workflow_path = os.path.join(AUTOMATIONS_DIR, safe_id + ".json")
    if not os.path.exists(workflow_path):
        return jsonify({"error": "Workflow not found"}), 404

    if not os.path.exists(RUNNER_SCRIPT):
        return jsonify({"error": "runner.js not found"}), 500

    data = request.json or {}
    var_args = []
    for k, v in data.get("vars", {}).items():
        var_args.extend(["--var", str(k) + "=" + str(v)])

    _run_state.update({
        "process": None, "status": "running",
        "workflow_name": workflow_id,
        "current_step": 0, "total_steps": 0,
        "step_label": "", "message": "Starting automation...",
        "log": [],
    })

    proc = subprocess.Popen(
        ["node", RUNNER_SCRIPT, workflow_path] + var_args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    _run_state["process"] = proc
    threading.Thread(target=_read_runner_output, args=(proc,), daemon=True).start()
    return jsonify({"status": "started"})


@automation_bp.route('/api/automations/run/status', methods=['GET'])
def run_status():
    """Poll current automation run state."""
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
def stop_run():
    """Kill running automation subprocess."""
    proc = _run_state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
    _run_state["status"] = "idle"
    _run_state["message"] = "Stopped by user"
    return jsonify({"status": "stopped"})


# ── Element Picker ───────────────────────────────────────────

@automation_bp.route('/api/automations/picker/start', methods=['POST'])
def start_picker():
    """Launch element picker browser."""
    if _picker_state.get("status") == "picking":
        return jsonify({"error": "Picker already running"}), 409

    if not os.path.exists(PICKER_SCRIPT):
        return jsonify({"error": "picker.js not found"}), 500

    data = request.json or {}
    start_url = data.get("url", "https://vportal.volusia.k12.fl.us/")

    _picker_state.update({"status": "picking", "events": [], "process": None})

    proc = subprocess.Popen(
        ["node", PICKER_SCRIPT, "--url", start_url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    _picker_state["process"] = proc
    threading.Thread(target=_read_picker_output, args=(proc,), daemon=True).start()
    return jsonify({"status": "picker_started"})


@automation_bp.route('/api/automations/picker/events', methods=['GET'])
def picker_events():
    """Drain and return accumulated picker events."""
    events = list(_picker_state.get("events", []))
    _picker_state["events"] = []
    return jsonify({"status": _picker_state.get("status", "idle"), "events": events})


@automation_bp.route('/api/automations/picker/stop', methods=['POST'])
def stop_picker():
    """Close picker browser."""
    proc = _picker_state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
    _picker_state["status"] = "idle"
    return jsonify({"status": "stopped"})
