"""Sanity check that mutmut is installed and setup.cfg's [mutmut] section
parses (Phase 5d PR 4)."""
from __future__ import annotations

import configparser
import os
import subprocess
import sys


def test_mutmut_installed():
    result = subprocess.run([sys.executable, "-m", "mutmut", "--version"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "mutmut" in result.stdout.lower()


def test_setup_cfg_has_mutmut_section():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cfg_path = os.path.join(repo_root, "setup.cfg")
    assert os.path.exists(cfg_path), f"setup.cfg not found at {cfg_path}"

    parser = configparser.ConfigParser()
    parser.read(cfg_path)
    assert "mutmut" in parser.sections(), "setup.cfg missing [mutmut] section"

    section = parser["mutmut"]
    assert "paths_to_mutate" in section, "[mutmut] missing paths_to_mutate"
    assert section.get("mutate_only_covered_lines", "False").lower() == "true"
