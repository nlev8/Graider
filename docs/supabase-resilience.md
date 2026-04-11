# Supabase Resilience Pattern

Graider's Supabase client is wrapped in a resilience proxy (`ResilientClient`) that automatically retries transient failures with exponential backoff.

## What's retried automatically

Every `.execute()` call on a query built through `db.table(...)`, `db.from_()`, `db.rpc(...)`, or `db.schema(...)` is routed through retry logic. The policy depends on the HTTP verb:

| Verb    | Operation     | Retry policy    |
|---------|---------------|-----------------|
| `GET`   | select        | full            |
| `PATCH` | update        | full            |
| `DELETE`| delete        | full            |
| `POST`  | upsert        | full            |
| `POST`  | insert        | preflight only  |

**full** = retry on any transient error (OSError, ConnectionError, TimeoutError, `httpcore.NetworkError`, `httpcore.TimeoutException`, `httpcore.ProtocolError`, HTTP 408/429/5xx, etc.)

**preflight only** = retry only on errors that occurred *before* any bytes reached the server (`ConnectError`, `ConnectTimeout`, DNS failures). Response-phase errors during a raw insert are surfaced to the caller because the server may already have committed the write — retrying would double-insert.

## When to use caller-generated UUIDs

If your insert MUST retry safely even on response-phase errors — i.e., you cannot tolerate a failed submission surfacing a 500 to a student — pass a caller-generated UUID as the `id` field and call `upsert(..., on_conflict='id')` instead of `insert(...)`:

```python
import uuid
row = {
    'id': str(uuid.uuid4()),
    # ... other fields ...
}
db.table('my_table').upsert(row, on_conflict='id').execute()
```

The upsert gets classified as "full retry". If the first attempt committed the row and the response dropped, the retry's `UPSERT` on the same id merges-duplicates to a no-op and returns the existing row. Unique indexes on other columns (like `student_id + content_id`) still fire for genuine duplicate submissions because a fresh session generates a fresh UUID.

Currently used in:
- `backend/routes/student_account_routes.py::submit_student_work`
- `backend/routes/student_account_routes.py::save_submission_draft`
- `backend/routes/student_portal_routes.py::publish_assessment`
- `backend/routes/student_portal_routes.py::submit_assessment` (join-code path)

## How to opt out of retry

For long-running streaming queries, custom retry logic, or healthchecks that must fail fast:

```python
from backend.supabase_client import get_raw_supabase
raw = get_raw_supabase()
raw.table('my_table').select('*').execute()  # no retry wrapping
```

The `/healthz` endpoint in `backend/app.py` bypasses the wrapper entirely and does a raw `httpx.get()` with a 3-second timeout against the PostgREST REST API — a slow Supabase should mark the pod degraded, not succeed after retries.

## Never bypass the wrapper with create_client()

Do NOT call `supabase.create_client()` directly in route handlers or services. Use `backend.supabase_client.get_supabase()` or `get_supabase_or_raise()` instead. The regression test `tests/test_no_direct_create_client.py` will fail the build if any module outside `backend/supabase_client.py` introduces a direct `create_client()` call.

## Retry budget

- 5 retries per operation (configurable in `backend/retry.py`)
- Exponential backoff: 0.5s, 1s, 2s, 4s, 8s, capped at 32s
- ±25% jitter
- Honours `Retry-After` header

## Observability

Every retry is logged with `logger.warning` at:
- `[supabase-get]` for selects
- `[supabase-patch]` for updates
- `[supabase-delete]` for deletes
- `[supabase-post]` for upserts
- `[supabase-insert-preflight]` for insert preflight retries

Grep for these labels to see retry activity in production logs.
