"""Regression guards for the minor cleanup items from the Phase-4 review.

Each test pins a specific fix so the pattern can't regress:
  1. SIGTERM handler snapshots _grading_states under the meta lock.
  2. init_app is idempotent (second call is a no-op).
  3. outlook_sender no longer pages Sentry on a benign button-label miss.
  4. run_grading_thread's set_thread_keys is inside the try/finally so
     clear_thread_keys always runs on exit, even if set raises.
"""
from __future__ import annotations

import ast
import pathlib
import sys


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _source(relpath: str) -> str:
    return (_REPO_ROOT / relpath).read_text(encoding="utf-8")


def _find_function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Function {name!r} not found")


# ───────────────────────────── SIGTERM ─────────────────────────────────


def test_handle_sigterm_snapshots_under_meta_lock():
    """`_handle_sigterm` must snapshot `_grading_states.items()` inside a
    `with _states_meta_lock:` block before iterating, to avoid
    RuntimeError if a concurrent _get_state() adds an entry mid-iteration.
    """
    source = _source("backend/app.py")
    tree = ast.parse(source)
    fn = _find_function(tree, "_handle_sigterm")

    # The function body should contain a `with _states_meta_lock:` block,
    # AND the raw `_grading_states.items()` call inside the `with` body.
    found_snapshot = False
    for node in ast.walk(fn):
        if isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Name) and ctx.id == "_states_meta_lock":
                    # Inside the with-body, confirm .items() is called on _grading_states
                    for sub in ast.walk(node):
                        if (
                            isinstance(sub, ast.Call)
                            and isinstance(sub.func, ast.Attribute)
                            and sub.func.attr == "items"
                            and isinstance(sub.func.value, ast.Name)
                            and sub.func.value.id == "_grading_states"
                        ):
                            found_snapshot = True
    assert found_snapshot, (
        "_handle_sigterm must snapshot _grading_states.items() inside a "
        "`with _states_meta_lock:` block. Direct iteration can race with "
        "_get_state() adding a new teacher entry and raise RuntimeError."
    )


# ───────────────────────────── init_app idempotency ────────────────────


def test_init_app_is_idempotent():
    """A second call to init_app(app) on the same Flask app must be a no-op.

    Without the guard, Flask raises ``AssertionError: View function
    mapping is overwriting an existing endpoint function`` when
    register_routes runs twice on the same app.
    """
    source = _source("backend/app.py")
    tree = ast.parse(source)
    fn = _find_function(tree, "init_app")

    # Must have an early-return guarded by an attribute on `app`.
    has_guard = False
    for node in fn.body:
        if isinstance(node, ast.If):
            # Look for `if getattr(app, '_graider_initialized', ...):`
            test = node.test
            if (
                isinstance(test, ast.Call)
                and isinstance(test.func, ast.Name)
                and test.func.id == "getattr"
                and len(test.args) >= 2
                and isinstance(test.args[0], ast.Name)
                and test.args[0].id == "app"
            ):
                # Body must be a return
                if any(isinstance(stmt, ast.Return) for stmt in node.body):
                    has_guard = True
                    break
    assert has_guard, (
        "init_app must guard against double-initialization with an early "
        "return checking `getattr(app, '_graider_initialized', False)`."
    )

    # Must set the attribute somewhere after register_routes.
    sets_attr = False
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Attribute)
            and node.targets[0].attr == "_graider_initialized"
            and isinstance(node.targets[0].value, ast.Name)
            and node.targets[0].value.id == "app"
        ):
            sets_attr = True
            break
    assert sets_attr, (
        "init_app must set `app._graider_initialized = True` after "
        "register_routes so subsequent calls short-circuit."
    )


# ───────────────────────────── outlook_sender ──────────────────────────


def test_outlook_new_mail_timeout_does_not_page_sentry():
    """The `page.get_by_role("button", name="New mail").wait_for(...)`
    fallback in navigate_to_outlook is an EXPECTED label-mismatch path.
    A Sentry capture here pages ops on every login — remove it.
    """
    source = _source("backend/services/outlook_sender.py")
    tree = ast.parse(source)
    fn = _find_function(tree, "navigate_to_outlook")

    # Walk every Try in the function; assert the New-mail wait's except
    # clause does not call sentry_sdk.capture_exception.
    for node in ast.walk(fn):
        if not isinstance(node, ast.Try):
            continue
        # Look for the wait_for("New mail") call in the try body
        waits_for_new_mail = False
        for stmt in ast.walk(node):
            if (
                isinstance(stmt, ast.Call)
                and isinstance(stmt.func, ast.Attribute)
                and stmt.func.attr == "wait_for"
            ):
                src = ast.unparse(stmt) if hasattr(ast, "unparse") else ""
                if "New mail" in src:
                    waits_for_new_mail = True
                    break
        if not waits_for_new_mail:
            continue

        for handler in node.handlers:
            for stmt in ast.walk(handler):
                if (
                    isinstance(stmt, ast.Call)
                    and isinstance(stmt.func, ast.Attribute)
                    and stmt.func.attr == "capture_exception"
                ):
                    raise AssertionError(
                        "navigate_to_outlook's 'New mail' wait_for fallback "
                        "is an expected label-mismatch path — Sentry capture "
                        "here pages ops on every login. Remove the capture."
                    )


# ───────────────────────────── BYOK try ordering ───────────────────────


def test_run_grading_thread_set_keys_inside_try():
    """`set_thread_keys(user_api_keys)` must be called inside the same
    try/finally whose finally clears the keys. Otherwise a partial or
    raising `set` skips the cleanup path.
    """
    source = _source("backend/grading/thread.py")
    tree = ast.parse(source)
    fn = _find_function(tree, "run_grading_thread")

    # Find the try block whose finally calls clear_thread_keys(). The body
    # of that try must include a set_thread_keys(...) call (directly or
    # inside a guarded `if user_api_keys:`).
    try_with_cleanup = None
    for node in ast.walk(fn):
        if isinstance(node, ast.Try):
            for fstmt in node.finalbody:
                for sub in ast.walk(fstmt):
                    if (
                        isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Name)
                        and sub.func.id == "clear_thread_keys"
                    ):
                        try_with_cleanup = node
                        break
                if try_with_cleanup:
                    break
        if try_with_cleanup:
            break

    assert try_with_cleanup is not None, (
        "run_grading_thread must have a try/finally whose finally calls "
        "clear_thread_keys()."
    )

    set_inside = False
    for sub in ast.walk(try_with_cleanup):
        if sub is try_with_cleanup:
            continue
        # Ignore nodes inside finalbody (we want try body only)
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id == "set_thread_keys"
        ):
            # Confirm it's in try.body (not finalbody)
            in_body = False
            for bstmt in try_with_cleanup.body:
                if sub in ast.walk(bstmt):
                    in_body = True
                    break
            if in_body:
                set_inside = True
                break

    assert set_inside, (
        "set_thread_keys(...) must be inside the try/finally body, not "
        "before it. Otherwise a raising set leaks contextvars past exit."
    )
