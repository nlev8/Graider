"""Regression guard: secrets / local DBs must never be committed.

Origin: security audit 2026-06 (#6) found `.env.telegram` (a live Telegram bot
token + DISABLE_SECURITY_PATTERNS=true) and SQLite sidecar files committed to the
repo, because `.gitignore`'s `.env.*.local` glob did not match `.env.telegram` and
`*.db` did not match the `.db-shm` / `.db-wal` sidecars. These tests pin the fix so
a future commit can't silently re-introduce the same class of leak.
"""
import subprocess


def _tracked_files() -> set[str]:
    out = subprocess.check_output(["git", "ls-files"], text=True)
    return set(out.splitlines())


def _is_gitignored(path: str) -> bool:
    # git check-ignore exits 0 when the path is ignored, 1 when it is not.
    return subprocess.run(
        ["git", "check-ignore", path], capture_output=True
    ).returncode == 0


def test_env_telegram_not_tracked():
    assert ".env.telegram" not in _tracked_files(), (
        ".env.telegram must not be tracked — it holds a live secret. "
        "Run `git rm --cached .env.telegram` and rotate the token."
    )


def test_no_dotenv_variants_tracked_except_example():
    """Only `.env.example` (a placeholder template) may be a tracked dotenv file."""
    tracked = _tracked_files()
    bad = {f for f in tracked if f.split("/")[-1].startswith(".env") and f != ".env.example"}
    assert not bad, f"tracked dotenv files that may contain secrets: {sorted(bad)}"


def test_no_sqlite_sidecars_tracked():
    tracked = _tracked_files()
    bad = {f for f in tracked if f.endswith((".db", ".db-shm", ".db-wal", ".db-journal"))}
    assert not bad, f"local SQLite DB/sidecar files must not be tracked: {sorted(bad)}"


def test_env_telegram_is_gitignored():
    assert _is_gitignored(".env.telegram"), ".env.telegram must be covered by .gitignore"


def test_sqlite_sidecars_are_gitignored():
    assert _is_gitignored("data/bot.db-shm"), "SQLite -shm sidecars must be gitignored"
    assert _is_gitignored("data/bot.db-wal"), "SQLite -wal sidecars must be gitignored"


def test_env_example_template_still_trackable():
    """The placeholder template must remain trackable (not ignored)."""
    assert not _is_gitignored(".env.example"), (
        ".env.example is a safe template and must stay trackable; "
        "the .env.* ignore rule needs a `!.env.example` negation."
    )
