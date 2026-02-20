"""
Automation Tool Definitions for the AI Assistant.
Allows the assistant to create, list, and run Playwright automations.
"""
import os
import json
import re
from datetime import datetime

AUTOMATIONS_DIR = os.path.expanduser("~/.graider_data/automations")

AUTOMATION_TOOL_DEFINITIONS = [
    {
        "name": "list_automations",
        "description": "List saved Playwright automation workflows. Use when teacher asks 'what automations do I have?' or 'show my browser automations'.",
        "input_schema": {
            "type": "object",
            "properties": {},
        }
    },
    {
        "name": "create_automation",
        "description": "Create a new Playwright automation workflow. The teacher describes what they want and you generate the steps. Use text=VisibleText selectors when the exact CSS selector is unknown. Always start with a login step for authenticated school portals. Step types: login, navigate, click, fill, select, wait, screenshot, extract_text, download, keyboard, loop, conditional.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short display name for the automation"},
                "description": {"type": "string", "description": "What this automation does"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["login", "navigate", "click", "fill", "select", "wait", "screenshot", "extract_text", "download", "keyboard", "loop", "conditional"]},
                            "label": {"type": "string", "description": "Human-readable step description"},
                            "params": {"type": "object", "description": "Step parameters (url, selector, value, count, steps, etc.)"}
                        },
                        "required": ["type", "label"]
                    },
                    "description": "Array of workflow steps"
                },
                "browser_persistent": {"type": "boolean", "description": "Reuse browser session between runs. Default false."},
                "headless": {"type": "boolean", "description": "Run without visible browser. Default false (visible for 2FA)."}
            },
            "required": ["name", "steps"]
        }
    },
    {
        "name": "run_automation",
        "description": "Run a saved automation workflow by name. Returns instructions for monitoring progress in the Automations tab.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name or partial name of the automation to run"}
            },
            "required": ["name"]
        }
    },
]


def list_automations_tool():
    os.makedirs(AUTOMATIONS_DIR, exist_ok=True)
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
            })
        except Exception:
            pass
    if not workflows:
        return {"message": "No automations saved yet. I can create one for you - just describe what you want to automate."}
    return {"automations": workflows, "count": len(workflows)}


def create_automation_tool(name, steps, description="", browser_persistent=False, headless=False):
    os.makedirs(AUTOMATIONS_DIR, exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

    for i, step in enumerate(steps):
        step.setdefault("id", "step-" + str(i + 1))
        step.setdefault("params", {})

    workflow = {
        "id": slug,
        "name": name,
        "description": description,
        "version": 1,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "browser": {
            "headless": headless,
            "persistent_context": browser_persistent,
            "context_dir": (slug + "_browser") if browser_persistent else None,
        },
        "credentials": "portal",
        "steps": steps,
    }

    filepath = os.path.join(AUTOMATIONS_DIR, slug + ".json")
    with open(filepath, 'w') as f:
        json.dump(workflow, f, indent=2)

    return {
        "success": True,
        "id": slug,
        "name": name,
        "step_count": len(steps),
        "message": "Automation '" + name + "' created with " + str(len(steps)) + " steps. Go to the Automations tab to run it, edit steps, or use the element picker to refine selectors.",
    }


def run_automation_tool(name):
    os.makedirs(AUTOMATIONS_DIR, exist_ok=True)
    for filename in sorted(os.listdir(AUTOMATIONS_DIR)):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(AUTOMATIONS_DIR, filename), 'r') as f:
                wf = json.load(f)
            if name.lower() in wf.get("name", "").lower():
                return {
                    "found": True,
                    "workflow_id": wf.get("id"),
                    "workflow_name": wf.get("name"),
                    "step_count": len(wf.get("steps", [])),
                    "message": "Found automation '" + wf["name"] + "'. Switch to the Automations tab and click the Run button to start it.",
                }
        except Exception:
            pass
    return {"found": False, "error": "No automation matching '" + name + "' found. Use create_automation to make one."}


AUTOMATION_TOOL_HANDLERS = {
    "list_automations": list_automations_tool,
    "create_automation": create_automation_tool,
    "run_automation": run_automation_tool,
}
