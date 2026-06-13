import subprocess, sys, pathlib

def test_backend_scan_flags_over_200(tmp_path):
    f = tmp_path / "big.py"
    body = "\n".join(f"    x{i} = {i}" for i in range(210))
    f.write_text(f"def huge():\n{body}\n")
    out = subprocess.run(
        [sys.executable, str(pathlib.Path("scripts/cq_scan_backend.py")), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert "huge" in out.stdout
    assert out.returncode == 1  # nonzero when offenders exist

def test_backend_scan_clean_is_zero_exit(tmp_path):
    (tmp_path / "ok.py").write_text("def small():\n    return 1\n")
    out = subprocess.run(
        [sys.executable, str(pathlib.Path("scripts/cq_scan_backend.py")), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0
    assert out.stdout.strip() == "" or "0 functions" in out.stdout
