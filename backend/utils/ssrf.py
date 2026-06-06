"""SSRF guard for server-side requests to externally-supplied URLs.

Origin: security audit 2026-06 (#9/#11/#14) — the OneRoster client issued
server-side HTTP requests to a district-admin-supplied base_url / token_url with
no validation, so a (post-auth) district admin could point Graider at internal
services or the cloud metadata endpoint (169.254.169.254) and use the response
as an oracle.

`validate_outbound_url` rejects:
  - non-allowed schemes (default: https only)
  - hosts that are a LITERAL private / loopback / link-local / reserved /
    multicast / unspecified IP (e.g. 127.0.0.1, 10.x, 169.254.169.254)
  - well-known internal hostnames (localhost, the cloud metadata names)
  - and, when resolve=True, hostnames that RESOLVE to such an address.

By default resolve=False (no DNS) so it is cheap, network-free, and safe to call
from object constructors / hot paths. That blocks the realistic vectors (literal
metadata/loopback/private IPs, localhost, http://). Pass resolve=True at a
config-entry chokepoint if you also want to catch a hostname that resolves to a
private IP (a more advanced, DNS-controlled vector).
"""
import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = {
    "localhost", "ip6-localhost", "ip6-loopback",
    "metadata", "metadata.google.internal",
}


class SSRFValidationError(ValueError):
    """Raised when an outbound URL targets a non-public / disallowed destination."""


def _ip_is_blocked(ip: "ipaddress.IPv4Address | ipaddress.IPv6Address") -> bool:
    return bool(
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def validate_outbound_url(
    url: str, *, allowed_schemes: tuple[str, ...] = ("https",), resolve: bool = False
) -> str:
    """Return `url` if it is a safe outbound target, else raise SSRFValidationError."""
    if not isinstance(url, str) or not url:
        raise SSRFValidationError(f"Invalid URL: {url!r}")
    parsed = urlparse(url)
    if parsed.scheme not in allowed_schemes:
        raise SSRFValidationError(
            f"URL scheme must be one of {allowed_schemes} (got {parsed.scheme!r}): {url!r}"
        )
    host = parsed.hostname
    if not host:
        raise SSRFValidationError(f"URL has no host: {url!r}")
    if host.lower() in _BLOCKED_HOSTNAMES:
        raise SSRFValidationError(f"Blocked internal host: {host}")

    # Host is a literal IP → check it directly (no DNS needed).
    try:
        literal_ip = ipaddress.ip_address(host.strip("[]"))  # strip IPv6 brackets
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        if _ip_is_blocked(literal_ip):
            raise SSRFValidationError(f"URL targets a non-public IP ({literal_ip}): {url!r}")
        return url

    # Catch ALTERNATE IPv4 encodings that ipaddress.ip_address() does NOT parse
    # but the OS resolver treats as a literal IPv4 — decimal-integer, hex (0x..),
    # octal, and short dotted forms. e.g. https://2130706433/ -> 127.0.0.1 and
    # https://0xA9FEA9FE/ -> 169.254.169.254 (Codex SSRF probe, audit #9/#11/#14).
    # socket.inet_aton parses exactly these numeric forms and raises OSError for a
    # genuine DNS hostname, so this stays network-free.
    try:
        packed = socket.inet_aton(host)
    except OSError:
        packed = None
    if packed is not None:
        numeric_ip = ipaddress.IPv4Address(packed)
        if _ip_is_blocked(numeric_ip):
            raise SSRFValidationError(
                f"URL targets a non-public IP ({numeric_ip}, via numeric encoding): {url!r}"
            )
        return url

    # Hostname: optionally resolve and check every returned address.
    if resolve:
        try:
            infos = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
        except socket.gaierror as e:
            raise SSRFValidationError(f"Could not resolve host {host!r}: {e}")
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if _ip_is_blocked(ip):
                raise SSRFValidationError(
                    f"Host {host!r} resolves to a non-public IP ({ip}): {url!r}"
                )
    return url
