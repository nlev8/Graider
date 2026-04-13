"""One-shot probe: determine published_assessments.teacher_id live column type.

Strategy: issue a PostgREST filter with a non-UUID string. If the column
is UUID, Postgres returns "invalid input syntax for type uuid". If it's
TEXT, the query returns 0 rows with no error. If the column doesn't
exist, we get a schema error naming the missing column.

Never writes to the database. Reads 0 rows.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from backend.supabase_client import get_raw_supabase

sb = get_raw_supabase()
if sb is None:
    print("ERROR: Supabase not configured", file=sys.stderr)
    sys.exit(2)

probe_value = "not-a-uuid-at-all"
try:
    sb.table("published_assessments").select("id").eq("teacher_id", probe_value).limit(0).execute()
    print("RESULT: column teacher_id exists AND accepts text (type=TEXT or similar)")
except Exception as e:
    msg = str(e)
    if "invalid input syntax for type uuid" in msg.lower() or "uuid" in msg.lower():
        print("RESULT: column teacher_id exists AND type is UUID")
        print(f"  error shape: {msg[:200]}")
    elif "column" in msg.lower() and "teacher_id" in msg.lower():
        print("RESULT: column teacher_id does NOT exist")
        print(f"  error shape: {msg[:200]}")
    else:
        print("RESULT: unknown error — inspect manually")
        print(f"  error: {msg[:400]}")
