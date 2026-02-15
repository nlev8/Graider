"""
District configuration loader for Graider.
Each district has a JSON config defining its SSO portal URL, type, and selectors.
Auto-detects district from teacher's email domain.
"""
import os
import json
import glob

DISTRICTS_DIR = os.path.dirname(__file__)


def list_districts():
    """Return all district configs."""
    configs = []
    for f in glob.glob(os.path.join(DISTRICTS_DIR, "*.json")):
        with open(f) as fh:
            configs.append(json.load(fh))
    return configs


def get_district(district_id):
    """Get a specific district config by ID."""
    path = os.path.join(DISTRICTS_DIR, district_id + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def find_district_by_email(email):
    """Auto-detect district from email domain."""
    domain = email.split("@")[-1] if "@" in email else ""
    for d in list_districts():
        if d.get("email_domain") == domain:
            return d
    return None
