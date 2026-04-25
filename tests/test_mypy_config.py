"""Sanity check that mypy is installed and mypy.ini parses (Phase 5d PR 2)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile


def test_mypy_installed():
    """mypy is on PATH for the test environment."""
    result = subprocess.run([sys.executable, "-m", "mypy", "--version"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("mypy "), result.stdout


def test_mypy_ini_exists_and_parses():
    """The repo's mypy.ini exists at the project root and mypy reads it
    without surfacing config diagnostics on stderr.

    Note: `mypy --help` short-circuits config validation, so we run mypy
    against a temporary empty file. With a valid config, stderr is empty
    (or contains only unrelated warnings); a bogus key, invalid value, or
    malformed INI section produces stderr lines like
    "mypy.ini: [...]: Unrecognized option: ..." that this test catches.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(repo_root, "mypy.ini")
    assert os.path.exists(config_path), f"mypy.ini not found at {config_path}"

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        empty_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--config-file", config_path, empty_path],
            capture_output=True, text=True,
        )
    finally:
        os.unlink(empty_path)

    # Real config errors land on stderr with the config-file name as prefix.
    # Other stderr content (deprecation noise) is tolerated.
    bad_lines = [
        line for line in result.stderr.splitlines()
        if "mypy.ini" in line and ("Unrecognized option" in line or "invalid value" in line.lower())
    ]
    assert not bad_lines, f"mypy reported config diagnostics: {bad_lines!r}\nfull stderr:\n{result.stderr}"
