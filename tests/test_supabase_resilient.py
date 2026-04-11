"""Tests for the resilient Supabase client wrapper."""

import pytest
from unittest.mock import MagicMock, patch


class TestOperationClassification:
    """Tests for _classify_operation — picks retry policy from the query builder."""

    def test_select_returns_full(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "GET"
        q.request.headers = {}
        assert _classify_operation(q) == "full"

    def test_update_returns_full(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "PATCH"
        q.request.headers = {"Prefer": "return=representation"}
        assert _classify_operation(q) == "full"

    def test_delete_returns_full(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "DELETE"
        q.request.headers = {"Prefer": "return=representation"}
        assert _classify_operation(q) == "full"

    def test_upsert_returns_full(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation,resolution=merge-duplicates"}
        assert _classify_operation(q) == "full"

    def test_insert_returns_preflight_only(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation"}
        assert _classify_operation(q) == "preflight_only"

    def test_unknown_method_defaults_to_preflight(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "PUT"
        q.request.headers = {}
        assert _classify_operation(q) == "preflight_only"


class TestPreflightRetryFilter:
    """Tests for _is_preflight_error — distinguishes connect-phase from response-phase errors."""

    def test_connect_error_is_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        import httpcore
        assert _is_preflight_error(httpcore.ConnectError("refused")) is True

    def test_connect_timeout_is_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        import httpcore
        assert _is_preflight_error(httpcore.ConnectTimeout("dns")) is True

    def test_read_error_is_not_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        import httpcore
        # ReadError means bytes were in flight — server may have committed
        assert _is_preflight_error(httpcore.ReadError("reset")) is False

    def test_read_timeout_is_not_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        import httpcore
        assert _is_preflight_error(httpcore.ReadTimeout("slow")) is False

    def test_dns_oserror_is_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        # OSError with gaierror-style message
        err = OSError("[Errno -2] Name or service not known")
        assert _is_preflight_error(err) is True

    def test_protocol_error_is_not_preflight(self):
        """RemoteProtocolError means the stream was mid-flight — not safe for insert retry."""
        from backend.supabase_resilient import _is_preflight_error
        import httpcore
        assert _is_preflight_error(httpcore.RemoteProtocolError("mid-stream reset")) is False


class TestResilientExecute:
    """Tests for the execute() wrapper's retry behavior."""

    def test_select_retries_on_oserror(self):
        from backend.supabase_resilient import _resilient_execute

        call_count = {"n": 0}
        q = MagicMock()
        q.request.http_method = "GET"
        q.request.headers = {}

        def fake_execute():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise OSError("temporarily unavailable")
            return MagicMock(data=[{"id": "xxx"}])

        q.execute = fake_execute
        # Patch time.sleep to speed up the test
        with patch("time.sleep"):
            result = _resilient_execute(q)
        assert call_count["n"] == 3
        assert result.data == [{"id": "xxx"}]

    def test_insert_retries_connect_error(self):
        from backend.supabase_resilient import _resilient_execute
        import httpcore

        call_count = {"n": 0}
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation"}

        def fake_execute():
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise httpcore.ConnectError("refused")
            return MagicMock(data=[{"id": "xxx"}])

        q.execute = fake_execute
        with patch("time.sleep"):
            result = _resilient_execute(q)
        assert call_count["n"] == 2

    def test_insert_does_not_retry_read_error(self):
        from backend.supabase_resilient import _resilient_execute
        import httpcore

        call_count = {"n": 0}
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation"}

        def fake_execute():
            call_count["n"] += 1
            raise httpcore.ReadError("server disconnected mid-response")

        q.execute = fake_execute
        with patch("time.sleep"), pytest.raises(httpcore.ReadError):
            _resilient_execute(q)
        assert call_count["n"] == 1  # no retry

    def test_upsert_retries_read_error(self):
        from backend.supabase_resilient import _resilient_execute
        import httpcore

        call_count = {"n": 0}
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation,resolution=merge-duplicates"}

        def fake_execute():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise httpcore.ReadError("reset")
            return MagicMock(data=[{"id": "xxx"}])

        q.execute = fake_execute
        with patch("time.sleep"):
            result = _resilient_execute(q)
        assert call_count["n"] == 3

    def test_non_retryable_error_propagates(self):
        from backend.supabase_resilient import _resilient_execute

        q = MagicMock()
        q.request.http_method = "GET"
        q.request.headers = {}
        q.execute = MagicMock(side_effect=ValueError("invalid arg"))

        with pytest.raises(ValueError):
            _resilient_execute(q)
        assert q.execute.call_count == 1

    def test_upsert_retries_protocol_error(self):
        """httpcore.RemoteProtocolError (HTTP/2 stream reset) should be retried on upsert."""
        from backend.supabase_resilient import _resilient_execute
        import httpcore

        call_count = {"n": 0}
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation,resolution=merge-duplicates"}

        def fake_execute():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise httpcore.RemoteProtocolError("stream reset")
            return MagicMock(data=[{"id": "xxx"}])

        q.execute = fake_execute
        with patch("time.sleep"):
            result = _resilient_execute(q)
        assert call_count["n"] == 3


class TestProxyBehavior:
    """Tests that the ResilientClient proxy preserves the chained API surface."""

    def test_table_returns_chainable_wrapper(self):
        from backend.supabase_resilient import ResilientClient

        mock_raw = MagicMock()
        wrapper = ResilientClient(mock_raw)
        result = wrapper.table("classes").select("id").eq("id", "xxx")
        # The chain should have been forwarded through to the raw client
        mock_raw.table.assert_called_once_with("classes")

    def test_non_postgrest_attrs_passthrough(self):
        """auth, storage, realtime, functions pass through untouched."""
        from backend.supabase_resilient import ResilientClient

        mock_raw = MagicMock()
        mock_raw.auth = "auth_obj"
        mock_raw.storage = "storage_obj"
        mock_raw.realtime = "realtime_obj"
        mock_raw.functions = "functions_obj"
        wrapper = ResilientClient(mock_raw)
        assert wrapper.auth == "auth_obj"
        assert wrapper.storage == "storage_obj"
        assert wrapper.realtime == "realtime_obj"
        assert wrapper.functions == "functions_obj"

    def test_rpc_returns_wrapped_builder(self):
        """rpc() results have .execute() — they must be wrapped."""
        from backend.supabase_resilient import ResilientClient, _ExecuteProxy

        # Raw rpc builder exposes .execute
        raw_builder = MagicMock()
        raw_builder.execute = MagicMock(return_value=MagicMock(data=[]))

        mock_raw = MagicMock()
        mock_raw.rpc = MagicMock(return_value=raw_builder)

        wrapper = ResilientClient(mock_raw)
        result = wrapper.rpc("some_function", {"arg": 1})
        assert isinstance(result, _ExecuteProxy)
        mock_raw.rpc.assert_called_once_with("some_function", {"arg": 1})

    def test_rpc_without_params(self):
        """rpc() can be called with just the function name."""
        from backend.supabase_resilient import ResilientClient, _ExecuteProxy

        raw_builder = MagicMock()
        raw_builder.execute = MagicMock(return_value=MagicMock(data=[]))

        mock_raw = MagicMock()
        mock_raw.rpc = MagicMock(return_value=raw_builder)

        wrapper = ResilientClient(mock_raw)
        result = wrapper.rpc("no_args_fn")
        assert isinstance(result, _ExecuteProxy)
        mock_raw.rpc.assert_called_once_with("no_args_fn")

    def test_schema_returns_wrapped_sub_client(self):
        """schema() returns a sub-client whose .from_()/.table()/.rpc() must also be wrapped."""
        from backend.supabase_resilient import ResilientClient, _ExecuteProxy

        # Raw schema sub-client has table/from_/rpc
        raw_builder = MagicMock()
        raw_builder.execute = MagicMock(return_value=MagicMock(data=[]))

        sub_client = MagicMock(spec=["table", "from_", "rpc"])
        sub_client.table = MagicMock(return_value=raw_builder)
        sub_client.from_ = MagicMock(return_value=raw_builder)
        sub_client.rpc = MagicMock(return_value=raw_builder)

        mock_raw = MagicMock()
        mock_raw.schema = MagicMock(return_value=sub_client)

        wrapper = ResilientClient(mock_raw)
        sub_wrapper = wrapper.schema("analytics")
        # Sub-client should itself be a ResilientClient
        assert isinstance(sub_wrapper, ResilientClient)
        # Calls through the sub-wrapper should produce wrapped builders
        assert isinstance(sub_wrapper.table("events"), _ExecuteProxy)
