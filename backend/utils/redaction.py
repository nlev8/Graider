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
