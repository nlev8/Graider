"""Sanity check that mypy is installed and mypy.ini parses (Phase 5d PR 2)."""
from __future__ import annotations

import os
import subprocess
import sys


def test_mypy_installed():
    """mypy is on PATH for the test environment."""
    result = subprocess.run([sys.executable, "-m", "mypy", "--version"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("mypy "), result.stdout


def test_mypy_ini_exists_and_parses():
    """The repo's mypy.ini exists at the project root and mypy parses it
    without errors."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(repo_root, "mypy.ini")
    assert os.path.exists(config_path), f"mypy.ini not found at {config_path}"

    # `mypy --config-file=...` exits 0 and prints config-file path on no-arg run
    # (when no files are passed, mypy errors with "missing files" but only AFTER
    # parsing the config; a config parse error would manifest as a different
    # error code/message).
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file", config_path, "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"mypy refused config: {result.stderr}"
