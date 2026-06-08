"""SSRF guard tests (audit #9/#11/#14).

The OneRoster client issued server-side requests to a district-admin-supplied
base_url/token_url; without validation an admin could target internal services
or the cloud metadata endpoint. validate_outbound_url + the OneRosterClient
constructor guard close that.
"""
import pytest

from backend.utils.ssrf import SSRFValidationError, validate_outbound_url


@pytest.mark.parametrize("url", [
    "https://169.254.169.254/latest/meta-data/",  # cloud metadata IP
    "https://127.0.0.1/x",                          # loopback
    "https://10.0.0.5/api",                         # private
    "https://192.168.1.1/api",                      # private
    "https://172.16.0.1/api",                       # private
    "https://[::1]/api",                            # ipv6 loopback
    "https://localhost/api",                        # localhost hostname
    "https://metadata.google.internal/x",           # metadata hostname
    "http://sis.example.com/api",                   # non-https scheme
    "ftp://sis.example.com/api",                    # non-https scheme
    "",                                             # empty
    "https:///nohost",                              # no host
    # Alternate IPv4 encodings the OS resolver maps to internal IPs (Codex probe):
    "https://2130706433/x",                         # decimal-integer 127.0.0.1
    "https://0x7f000001/x",                         # hex 127.0.0.1
    "https://2852039166/x",                         # decimal 169.254.169.254 (metadata)
    "https://0xA9FEA9FE/x",                         # hex 169.254.169.254 (metadata)
    "https://0251.0376.0251.0376/x",                # octal-dotted 169.254.169.254
    "https://127.1/x",                              # short-form loopback
])
def test_rejects_internal_and_bad_urls(url):
    with pytest.raises(SSRFValidationError):
        validate_outbound_url(url)


@pytest.mark.parametrize("url", [
    "https://sis.example.com/ims/oneroster/v1p1",
    "https://8.8.8.8/api",  # public literal IP is fine
])
def test_allows_public_https(url):
    assert validate_outbound_url(url) == url


def test_resolve_true_blocks_hostname_resolving_to_private(monkeypatch):
    import backend.utils.ssrf as ssrf

    def fake_getaddrinfo(host, port, **kwargs):
        return [(2, 1, 6, "", ("10.1.2.3", port))]

    monkeypatch.setattr(ssrf.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(SSRFValidationError):
        validate_outbound_url("https://rebind.example.com/x", resolve=True)


# ── OneRosterClient constructor guard ──────────────────────────────

def test_oneroster_client_rejects_metadata_base_url():
    from backend.oneroster import OneRosterClient
    with pytest.raises(SSRFValidationError):
        OneRosterClient("https://169.254.169.254/oneroster", "cid", "secret")


def test_oneroster_client_rejects_loopback_base_url():
    from backend.oneroster import OneRosterClient
    with pytest.raises(SSRFValidationError):
        OneRosterClient("https://127.0.0.1/oneroster", "cid", "secret")


def test_oneroster_client_rejects_http_base_url():
    from backend.oneroster import OneRosterClient
    with pytest.raises(SSRFValidationError):
        OneRosterClient("http://sis.example.com/oneroster", "cid", "secret")


def test_oneroster_client_rejects_private_token_url():
    from backend.oneroster import OneRosterClient
    with pytest.raises(SSRFValidationError):
        OneRosterClient("https://sis.example.com/oneroster", "cid", "secret",
                        token_url="https://10.0.0.1/token")


def test_oneroster_client_allows_public_https():
    from backend.oneroster import OneRosterClient
    c = OneRosterClient("https://sis.example.com/oneroster", "cid", "secret")
    assert c.base_url == "https://sis.example.com/oneroster"
