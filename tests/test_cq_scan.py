import subprocess, sys, pathlib

SCAN = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "cq_scan_backend.py"

def test_backend_scan_flags_over_200(tmp_path):
    f = tmp_path / "big.py"
    body = "\n".join(f"    x{i} = {i}" for i in range(210))
    f.write_text(f"def huge():\n{body}\n")
    out = subprocess.run(
        [sys.executable, str(SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert "huge" in out.stdout
    assert out.returncode == 1  # nonzero when offenders exist

def test_backend_scan_clean_is_zero_exit(tmp_path):
    (tmp_path / "ok.py").write_text("def small():\n    return 1\n")
    out = subprocess.run(
        [sys.executable, str(SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0
    assert out.stdout.strip() == "" or "0 functions" in out.stdout

def test_backend_scan_fails_closed_on_parse_error(tmp_path):
    # A measurement gate must NOT certify clean when a file could not be scanned.
    (tmp_path / "broken.py").write_text("def oops(:\n    pass\n")  # syntax error
    out = subprocess.run(
        [sys.executable, str(SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert out.returncode == 2, f"expected fail-closed exit 2, got {out.returncode}"
    assert "INCOMPLETE" in out.stderr

def test_backend_scan_fails_closed_on_missing_root(tmp_path):
    missing = tmp_path / "does-not-exist"
    out = subprocess.run(
        [sys.executable, str(SCAN), str(missing)],
        capture_output=True, text=True,
    )
    assert out.returncode == 2, f"expected fail-closed exit 2, got {out.returncode}"
    assert "INCOMPLETE" in out.stderr
