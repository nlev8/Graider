"""Regression: Clever API v3.0 role resolution in `get_clever_user`.

Clever API v3.0 changed the `/me` endpoint: `data.type` now returns the
generic string ``"user"`` for EVERY record instead of the role
(``"teacher"`` / ``"student"`` / ``"district_admin"``). See Clever's
upgrade guide (https://dev.clever.com/docs/api-v3-upgrade-guide):

    "The type field on /me will now return 'user' for any user records
     instead of a specific role type."

The actual role moved into the ``/users/{id}`` → ``data.roles`` object
(e.g. ``{"student": {...}}``). `get_clever_user` previously returned
``me_data["type"]`` verbatim, so under v3.0 every SSO user came back as
``type="user"``, the `clever_callback` ``== "student"`` branch
(`clever_routes.py:459`) became dead code, and *students were routed into
the teacher onboarding flow*.

The pre-existing callback tests mock `get_clever_user`'s OUTPUT
(``_clever_user(role)`` hands back ``{"type": role}``), so they never
exercised the real `/me` parsing — that's why CI stayed green while live
SSO mis-routed. These tests pin role resolution against the REAL v3.0 wire
shape, plus a v2.x-compat case so we don't regress districts still pinned
to the older API version.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

MODULE = "backend.clever"


def _async_client_for(me_json, user_json):
    """Build a mock httpx.AsyncClient that returns `me_json` for `/me` and
    `user_json` for the `/users/{id}` fetch (both HTTP 200)."""
    me_resp = MagicMock()
    me_resp.status_code = 200
    me_resp.json.return_value = me_json

    user_resp = MagicMock()
    user_resp.status_code = 200
    user_resp.json.return_value = user_json

    async def fake_get(url, **_):
        return me_resp if url.endswith("/me") else user_resp

    client = MagicMock()
    client.get = fake_get
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


def _resolve(me_json, user_json):
    from backend.clever import get_clever_user

    client = _async_client_for(me_json, user_json)
    with patch(f"{MODULE}.httpx.AsyncClient", return_value=client):
        return asyncio.run(get_clever_user("token"))


class TestV3RoleResolution:
    def test_student_role_resolved_from_roles_object(self):
        """v3.0 `/me` type='user' + roles={'student':...} ⇒ type 'student'.

        This is the load-bearing case: if it returns anything else,
        `clever_callback` routes the student into the teacher dashboard.
        """
        result = _resolve(
            {"data": {"id": "stu-1", "type": "user"}},
            {"data": {
                "id": "stu-1",
                "name": {"first": "Jane", "last": "Doe"},
                "email": "jane@school.edu",
                "roles": {"student": {"grade": "9"}},
            }},
        )
        assert result is not None
        assert result["type"] == "student", (
            "v3.0 student mis-resolved — clever_callback would route them to "
            "the teacher onboarding flow instead of /student"
        )

    def test_teacher_role_resolved_from_roles_object(self):
        result = _resolve(
            {"data": {"id": "t-1", "type": "user"}},
            {"data": {
                "id": "t-1",
                "name": {"first": "Sam"},
                "email": "sam@school.edu",
                "roles": {"teacher": {"title": "Mr"}},
            }},
        )
        assert result["type"] == "teacher"

    def test_district_admin_preferred_over_teacher_for_multi_role(self):
        """Per Clever docs a user may hold teacher + staff + district_admin
        simultaneously. district_admin must win so the admin-gated route
        (`clever_routes.py:873`, `type != 'district_admin'`) stays reachable."""
        result = _resolve(
            {"data": {"id": "a-1", "type": "user"}},
            {"data": {
                "id": "a-1",
                "name": {},
                "email": "admin@school.edu",
                "roles": {"teacher": {}, "staff": {}, "district_admin": {}},
            }},
        )
        assert result["type"] == "district_admin"

    def test_v2_compat_me_type_preserved_when_no_roles(self):
        """API v2.x: `/me` type IS the role and the user record may carry no
        `roles` object. Preserve the `/me` type so v2-pinned districts work."""
        result = _resolve(
            {"data": {"id": "t-2", "type": "teacher"}},
            {"data": {"id": "t-2", "name": {}, "email": "t2@school.edu"}},
        )
        assert result["type"] == "teacher"

    def test_unknown_role_falls_back_to_present_role_key(self):
        """A role key we don't explicitly rank (e.g. 'contact') should still
        surface as that role rather than the generic '/me' 'user'."""
        result = _resolve(
            {"data": {"id": "c-1", "type": "user"}},
            {"data": {
                "id": "c-1",
                "name": {},
                "email": "guardian@home.edu",
                "roles": {"contact": {}},
            }},
        )
        assert result["type"] == "contact"
