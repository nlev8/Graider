"""Regression tests for issue #731 — local pytest runs must NEVER write to
the live Supabase ``audit_log`` table.

Root cause: the developer ``.env`` carries production ``SUPABASE_URL`` /
``SUPABASE_SERVICE_KEY``, and ``backend.utils.audit.audit_log()`` dual-writes
to Supabase whenever ``get_supabase()`` yields a client. Two batches of
fixture rows (teacher_id ``t-1``, ``clever:clever-teacher-001``, actions
``CLEVER_USER_READ`` / ``CLASSLINK_LOGIN`` / ``clever_roster_sync``) were
observed in the production audit trail on 2026-06-10, timestamped exactly at
local full-suite runs.

The fix is the autouse ``_isolate_live_supabase`` fixture in
``tests/conftest.py``, which patches the ``_get_audit_supabase`` seam in
``backend/utils/audit.py`` so that:

  - the REAL ``backend.supabase_client.get_supabase`` is never invoked from
    the audit sink during tests (a real client built from production env vars
    can therefore never receive audit inserts), while
  - a test-installed fake (``monkeypatch`` / ``mock.patch`` on
    ``backend.supabase_client.get_supabase``) IS honored, preserving the
    ``tests/test_audit_redaction.py`` contract that asserts on the redacted
    payloads the sink inserts.
"""
from unittest.mock import MagicMock

from backend.utils.audit import audit_log


class TestLiveClientBlocked:
    def test_get_supabase_returns_none_for_unmocked_tests(self):
        """CI parity invariant: an unmocked test must never see a real
        Supabase client, even when the developer .env carries production
        credentials. The conftest guard nulls the singletons and stubs
        create_client, so get_supabase()/get_raw_supabase() return None —
        exactly what CI (no SUPABASE_URL) produces."""
        import backend.supabase_client as sc

        assert sc.get_supabase() is None
        assert sc.get_raw_supabase() is None


class TestAuditSinkIsolation:
    def test_real_supabase_singleton_not_reachable_from_audit_log(
        self, monkeypatch, tmp_path
    ):
        """The leak condition: a real client exists as the process-wide
        singleton (what a production .env produces locally) and the test does
        NOT patch get_supabase. audit_log() must not reach that client.

        RED on main: audit_log() resolves the real get_supabase(), which
        returns the cached singleton, and the insert fires against it.
        GREEN with the conftest guard: the unpatched (real) get_supabase is
        blocked, so the recorder never sees a call.
        """
        import backend.supabase_client as sc

        recorder = MagicMock(name="live_client_stand_in")
        # Simulate the production-credentials condition without any network:
        # the resilient singleton is already populated. We deliberately do
        # NOT patch sc.get_supabase — that unpatched state is exactly the
        # condition under which the 2026-06-10 leak happened.
        monkeypatch.setattr(sc, "_supabase_resilient", recorder)
        monkeypatch.setattr(
            "backend.utils.audit.AUDIT_LOG_FILE", str(tmp_path / "audit.log")
        )

        audit_log(
            "ISOLATION_PROBE",
            "fixture-only details",
            user="teacher",
            teacher_id="t-isolation",
        )

        assert not recorder.mock_calls, (
            "audit_log() reached the process-wide Supabase singleton during a "
            "test run — with a production .env this inserts fixture rows into "
            "the LIVE audit_log table (issue #731). First calls: "
            f"{recorder.mock_calls[:3]}"
        )

    def test_local_file_write_still_happens(self, monkeypatch, tmp_path):
        """The guard must only block the Supabase sink — the local audit file
        write is asserted on by other tests and must keep working."""
        log_path = tmp_path / "audit.log"
        monkeypatch.setattr("backend.utils.audit.AUDIT_LOG_FILE", str(log_path))

        audit_log(
            "ISOLATION_FILE_PROBE",
            "local file still written",
            user="teacher",
            teacher_id="t-isolation",
        )

        contents = log_path.read_text()
        assert "ISOLATION_FILE_PROBE" in contents
        assert "local file still written" in contents
        assert "teacher=t-isolation" in contents

    def test_explicit_test_fake_is_still_honored(self, monkeypatch, tmp_path):
        """tests/test_audit_redaction.py installs fakes on
        backend.supabase_client.get_supabase and asserts on the inserted
        payload. The guard must pass an explicitly-installed fake through to
        the sink (it only blocks the REAL, unpatched function)."""
        captured = {}

        def fake_insert(payload):
            captured["payload"] = payload
            chain = MagicMock()
            chain.execute.return_value = MagicMock()
            return chain

        mock_table = MagicMock()
        mock_table.insert.side_effect = fake_insert
        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table

        monkeypatch.setattr(
            "backend.supabase_client.get_supabase", lambda: mock_sb
        )
        monkeypatch.setattr(
            "backend.utils.audit.AUDIT_LOG_FILE", str(tmp_path / "audit.log")
        )

        audit_log(
            "ISOLATION_FAKE_PROBE",
            "explicit fake must receive the insert",
            user="teacher",
            teacher_id="t-isolation",
        )

        payload = captured.get("payload")
        assert payload is not None, (
            "An explicitly test-installed get_supabase fake was NOT honored — "
            "the conftest guard is over-blocking (it must only block the real, "
            "unpatched client)."
        )
        assert payload["action"] == "ISOLATION_FAKE_PROBE"
        assert payload["teacher_id"] == "t-isolation"
