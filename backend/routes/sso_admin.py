"""Provider-agnostic SSO admin designation match.

Run after an SSO callback has resolved a Supabase UUID. Routes the user by the
district-managed `sso_admin_designation:{email}` list — independent of any IdP
role claim. Currently wired into the ClassLink callback only (Clever is a
one-line add later).
"""

import logging

from backend.storage import load as storage_load
from backend.routes.admin_routes import _grant_sso_school_admin, _sync_sso_admin_revocation

logger = logging.getLogger(__name__)


def _normalize_email(email):
    return str(email or "").strip().lower()


def apply_sso_admin_designation(email, teacher_id, session):
    """Apply the district-managed admin designation for a resolved SSO login.

    Returns the applied tier: 'district' | 'school' | 'none'. Side effects:
      - district → revoke any stale SSO-designated school grant, then set
        session['district_admin'] = True
      - school   → upsert a source='sso_designated' admin_role (school from the designation)
      - none     → revoke any stale source='sso_designated' grant (self-heal)
    Never grants without a designation match.
    """
    norm = _normalize_email(email)
    rec = storage_load(f"sso_admin_designation:{norm}", "system") if norm else None

    if isinstance(rec, dict) and rec.get("tier") == "district":
        # Promotion school→district must not strand the old school grant.
        _sync_sso_admin_revocation(teacher_id)
        session["district_admin"] = True
        return "district"

    if isinstance(rec, dict) and rec.get("tier") == "school":
        _grant_sso_school_admin(teacher_id, rec.get("school", ""))
        return "school"

    _sync_sso_admin_revocation(teacher_id)
    return "none"
