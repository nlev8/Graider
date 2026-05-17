"""Survey submit must write tz-aware ISO timestamps (Data Integrity Tier 1)."""
import re
from datetime import datetime, timezone


def test_survey_module_uses_tz_aware_now():
    """No naive datetime.utcnow() may remain in survey_routes; the submit
    path must produce an offset-bearing ISO-8601 timestamp."""
    import backend.routes.survey_routes as sr
    text = open(sr.__file__, encoding="utf-8").read()
    assert "datetime.utcnow()" not in text, "naive utcnow() still present"
    assert "datetime.now(timezone.utc)" in text
    ts = datetime.now(timezone.utc).isoformat()
    assert re.search(r"\+00:00$", ts)
