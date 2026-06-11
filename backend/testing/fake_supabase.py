"""In-memory fake Supabase client for hermetic E2E CI runs.

Hardening sprint PR5 (e2e de-skip wave 1). The PR-gated `Frontend E2E
Extended` CI job spawns the real Flask backend with GRAIDER_FAKE_SUPABASE=1
so the join-code publish → student-take → results flow runs end-to-end with
NO live Supabase project. backend/supabase_client.get_raw_supabase() returns
the singleton from get_fake_supabase() when the gate is enabled (the gate is
fail-closed: it raises unless FLASK_ENV is a dev/test value).

Scope — deliberately a SUBSET of the postgrest builder, just enough for the
promoted e2e specs' API surface (student_portal_routes.py join-code path,
submission_repository.py, assessment_results_routes.py, analytics_routes.py):

  table(name)
    .select(*cols, count=...)   # returns FULL rows; column projection is
                                # intentionally not implemented — handlers
                                # use .get() so extra keys are harmless
    .insert(row | [rows])
    .upsert(row | [rows], on_conflict="col[,col2]")  # merge semantics, like
                                                     # ON CONFLICT DO UPDATE
    .update(fields)
    .delete()
    .eq/.neq/.ilike/.in_/.gte/.lte/.gt/.lt/.is_(col, value)
    .order(col, desc=...)/.limit(n)/.range(a, b)
    .single()/.maybe_single()
    .execute() -> response with .data and .count

Not implemented (raises AttributeError naturally): rpc, embedded-resource
projections (``students(...)`` in a select string is ignored — the embed key
is simply absent from returned rows), or_, contains, text search. If a route
a future promoted spec exercises needs one of these, extend this file with a
pinned unit test in tests/test_fake_supabase.py.

Thread-safety: a single RLock guards every execute() — the Flask backend
serves Playwright traffic from multiple threads.
"""
from __future__ import annotations

import copy
import re
import threading
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ilike_to_regex(pattern: str) -> "re.Pattern[str]":
    """Translate a SQL ILIKE pattern (with backslash escapes) to a regex.

    ``%`` → ``.*``, ``_`` → ``.``; ``\\%``/``\\_``/``\\\\`` are literals
    (matches _escape_ilike in backend/services/submission_repository.py).
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\" and i + 1 < len(pattern):
            out.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        if ch == "%":
            out.append(".*")
        elif ch == "_":
            out.append(".")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("".join(out), re.IGNORECASE | re.DOTALL)


def _matches(row: dict[str, Any], filters: list[tuple[str, str, Any]]) -> bool:
    """AND-combine all recorded filters against one row."""
    for kind, col, value in filters:
        actual = row.get(col)
        if kind == "eq":
            if actual != value:
                return False
        elif kind == "neq":
            if actual == value:
                return False
        elif kind == "ilike":
            if actual is None or not _ilike_to_regex(str(value)).fullmatch(str(actual)):
                return False
        elif kind == "in":
            if actual not in value:
                return False
        elif kind == "is":
            # postgrest .is_(col, 'null') / .is_(col, 'true'|'false')
            want = {"null": None, "true": True, "false": False}.get(str(value).lower(), value)
            if actual is not want and actual != want:
                return False
        elif kind in ("gte", "lte", "gt", "lt"):
            if actual is None:
                return False
            try:
                if kind == "gte" and not actual >= value:
                    return False
                if kind == "lte" and not actual <= value:
                    return False
                if kind == "gt" and not actual > value:
                    return False
                if kind == "lt" and not actual < value:
                    return False
            except TypeError:
                return False
        else:  # pragma: no cover — unknown filter kinds fail loudly
            raise NotImplementedError(f"fake_supabase: unsupported filter {kind!r}")
    return True


class FakeQuery:
    """One chained postgrest query against one in-memory table."""

    def __init__(self, rows: list[dict[str, Any]], lock: threading.RLock) -> None:
        self._rows = rows  # live reference into the client's store
        self._lock = lock
        self._op = "select"
        self._payload: list[dict[str, Any]] = []
        self._update_fields: dict[str, Any] = {}
        self._conflict_cols: list[str] = ["id"]
        self._filters: list[tuple[str, str, Any]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._range: tuple[int, int] | None = None
        self._single = False
        self._maybe_single = False
        self._count: str | None = None

    # ── verbs ────────────────────────────────────────────────────
    def select(self, *cols: str, count: str | None = None, **_kwargs: Any) -> "FakeQuery":
        self._op = "select"
        self._count = count
        return self

    def insert(self, rows: Any, **_kwargs: Any) -> "FakeQuery":
        self._op = "insert"
        self._payload = [rows] if isinstance(rows, dict) else list(rows)
        return self

    def upsert(self, rows: Any, on_conflict: str | None = None, **_kwargs: Any) -> "FakeQuery":
        self._op = "upsert"
        self._payload = [rows] if isinstance(rows, dict) else list(rows)
        if on_conflict:
            self._conflict_cols = [c.strip() for c in on_conflict.split(",") if c.strip()]
        return self

    def update(self, fields: dict[str, Any], **_kwargs: Any) -> "FakeQuery":
        self._op = "update"
        self._update_fields = dict(fields)
        return self

    def delete(self, **_kwargs: Any) -> "FakeQuery":
        self._op = "delete"
        return self

    # ── filters ──────────────────────────────────────────────────
    def eq(self, col: str, value: Any) -> "FakeQuery":
        self._filters.append(("eq", col, value))
        return self

    def neq(self, col: str, value: Any) -> "FakeQuery":
        self._filters.append(("neq", col, value))
        return self

    def ilike(self, col: str, value: Any) -> "FakeQuery":
        self._filters.append(("ilike", col, value))
        return self

    def in_(self, col: str, values: Any) -> "FakeQuery":
        self._filters.append(("in", col, list(values)))
        return self

    def is_(self, col: str, value: Any) -> "FakeQuery":
        self._filters.append(("is", col, value))
        return self

    def gte(self, col: str, value: Any) -> "FakeQuery":
        self._filters.append(("gte", col, value))
        return self

    def lte(self, col: str, value: Any) -> "FakeQuery":
        self._filters.append(("lte", col, value))
        return self

    def gt(self, col: str, value: Any) -> "FakeQuery":
        self._filters.append(("gt", col, value))
        return self

    def lt(self, col: str, value: Any) -> "FakeQuery":
        self._filters.append(("lt", col, value))
        return self

    # ── modifiers ────────────────────────────────────────────────
    def order(self, col: str, desc: bool = False, **_kwargs: Any) -> "FakeQuery":
        self._order = (col, desc)
        return self

    def limit(self, n: int, **_kwargs: Any) -> "FakeQuery":
        self._limit = n
        return self

    def range(self, start: int, end: int, **_kwargs: Any) -> "FakeQuery":
        self._range = (start, end)
        return self

    def single(self) -> "FakeQuery":
        self._single = True
        return self

    def maybe_single(self) -> "FakeQuery":
        self._maybe_single = True
        return self

    # ── execution ────────────────────────────────────────────────
    def execute(self) -> Any:
        with self._lock:
            if self._op == "select":
                data = self._run_select()
            elif self._op == "insert":
                data = self._run_insert()
            elif self._op == "upsert":
                data = self._run_upsert()
            elif self._op == "update":
                data = self._run_update()
            elif self._op == "delete":
                data = self._run_delete()
            else:  # pragma: no cover
                raise NotImplementedError(f"fake_supabase: unsupported op {self._op!r}")

            # Deepcopy INSIDE the lock: `data` holds live references into the
            # shared store, and a concurrent writer thread could mutate a row
            # mid-copy if this ran after lock release.
            result: Any = copy.deepcopy(data)

        count = len(data) if self._count else None

        if self._single:
            if len(result) != 1:
                # Mirrors postgrest APIError("JSON object requested, multiple
                # (or no) rows returned"). Routes catch broad Exception.
                raise ValueError(
                    f"fake_supabase: .single() matched {len(result)} rows, expected 1"
                )
            result = result[0]
        elif self._maybe_single:
            result = result[0] if result else None

        return SimpleNamespace(data=result, count=count)

    # ── op implementations (called under lock) ───────────────────
    def _matched(self) -> list[dict[str, Any]]:
        return [r for r in self._rows if _matches(r, self._filters)]

    def _run_select(self) -> list[dict[str, Any]]:
        data = self._matched()
        if self._order:
            col, desc = self._order

            def key(row: dict[str, Any]) -> tuple[int, str]:
                v = row.get(col)
                # None sorts before everything; mixed types compared as str.
                return (0, "") if v is None else (1, str(v))

            data = sorted(data, key=key, reverse=desc)
        if self._range is not None:
            start, end = self._range
            data = data[start : end + 1]
        if self._limit is not None:
            data = data[: self._limit]
        return data

    def _fill_defaults(self, row: dict[str, Any]) -> dict[str, Any]:
        """Mimic common column DEFAULTs (gen_random_uuid(), now())."""
        new = copy.deepcopy(row)
        new.setdefault("id", str(uuid.uuid4()))
        new.setdefault("created_at", _now_iso())
        new.setdefault("submitted_at", _now_iso())
        return new

    def _run_insert(self) -> list[dict[str, Any]]:
        inserted = []
        for row in self._payload:
            new = self._fill_defaults(row)
            self._rows.append(new)
            inserted.append(new)
        return inserted

    def _run_upsert(self) -> list[dict[str, Any]]:
        results = []
        for row in self._payload:
            existing = None
            for candidate in self._rows:
                if all(candidate.get(c) == row.get(c) for c in self._conflict_cols):
                    existing = candidate
                    break
            if existing is not None:
                # ON CONFLICT DO UPDATE: provided columns overwrite,
                # unprovided columns retain their previous values.
                existing.update(copy.deepcopy(row))
                results.append(existing)
            else:
                new = self._fill_defaults(row)
                self._rows.append(new)
                results.append(new)
        return results

    def _run_update(self) -> list[dict[str, Any]]:
        updated = []
        for row in self._matched():
            row.update(copy.deepcopy(self._update_fields))
            updated.append(row)
        return updated

    def _run_delete(self) -> list[dict[str, Any]]:
        doomed = self._matched()
        for row in doomed:
            self._rows.remove(row)
        return doomed


class FakeSupabaseClient:
    """Duck-typed stand-in for supabase.Client (postgrest subset only)."""

    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.RLock()

    def table(self, name: str) -> FakeQuery:
        with self._lock:
            rows = self._tables.setdefault(name, [])
        return FakeQuery(rows, self._lock)

    # supabase-py exposes .from_ as an alias of .table
    def from_(self, name: str) -> FakeQuery:
        return self.table(name)


_singleton: FakeSupabaseClient | None = None
_singleton_lock = threading.Lock()


def get_fake_supabase() -> FakeSupabaseClient:
    """Process-wide singleton, so all request threads share one store."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = FakeSupabaseClient()
    return _singleton


def reset_fake_supabase() -> None:
    """Drop all in-memory state (test isolation helper)."""
    global _singleton
    with _singleton_lock:
        _singleton = None
