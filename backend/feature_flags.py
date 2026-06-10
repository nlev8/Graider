"""Env-backed feature flags (hardening sprint Wave 1, PR3).

Convention: ``flag_enabled("clever_roster_sync")`` reads the env var
``FLAG_CLEVER_ROSTER_SYNC`` (name upper-cased, ``FLAG_`` prefix).

- Truthy values: 1 / true / yes / on (case-insensitive)
- Falsy values:  0 / false / no / off (case-insensitive)
- Unset (or empty string, e.g. ``FLAG_X=`` in a .env file) → the ``default``
  parameter (itself defaulting to False per the plan DoD)
- Anything else → log a warning and fall back to ``default``

Flags are read from the environment at call time (no caching), so an
operator can flip a flag with a Railway env-var change + restart.

NOTE on adoption defaults: new/risky paths should be gated default-False;
paths that are already LIVE in prod get gated default-True (kill switch)
so shipping the gate does not change behavior. See FLAG_CLEVER_ROSTER_SYNC
in .env.example.
"""
import logging
import os

logger = logging.getLogger(__name__)

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})


def flag_enabled(name: str, default: bool = False) -> bool:
    """Return True if feature flag ``name`` is enabled via env var.

    Reads ``FLAG_<NAME>`` (upper-cased). Unset/empty → ``default``;
    unrecognized values warn and fall back to ``default``.
    """
    env_var = f"FLAG_{name.upper()}"
    raw = os.getenv(env_var)
    if raw is None:
        return default
    value = raw.strip().lower()
    if not value:
        # `FLAG_X=` (empty) in a .env file — treat as unset, no warning.
        return default
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    logger.warning(
        "Unrecognized value %r for feature flag env var %s; "
        "falling back to default=%s",
        raw, env_var, default,
    )
    return default
