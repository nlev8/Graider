"""PII redaction helpers for logs and audit strings."""


def redact_email(email: str | None) -> str:
    """Return 'a***@example.com' for 'alice@example.com'.

    Returns '' for None, empty string, or values without '@'.
    Returns '***@example.com' for single-character local parts.
    """
    if not email or "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    if len(local) <= 1:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def redact_name(name: str | None) -> str:
    """Return a non-identifying initials form of a person's name.

    Mirrors `redact_email`'s shape: keeps the leading initial of each
    whitespace-separated token for debuggability while stripping the
    identifying remainder. FERPA-driven (VB9 #20) — student/teacher names
    must not survive verbatim in audit details.

      'Alice Johnson'  -> 'A*** J***'
      'Charlie Brown'  -> 'C*** B***'
      'Bob'            -> 'B***'
      ''/None          -> ''
    """
    if not name:
        return ""
    parts = [tok for tok in str(name).split() if tok]
    if not parts:
        return ""
    return " ".join(f"{tok[0]}***" for tok in parts)
