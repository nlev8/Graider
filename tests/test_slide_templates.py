from backend.services.slide_templates import TEMPLATES, template_css, DEFAULT_TEMPLATE


def test_four_templates_exist():
    assert set(TEMPLATES) == {"editorial", "bold", "academic", "playful"}
    assert DEFAULT_TEMPLATE == "academic"


def test_template_css_includes_base_and_accent():
    css = template_css("academic", accent="#1a7f43")
    assert ".slide" in css           # base layout rules present
    assert "1a7f43" in css           # accent injected
    assert "--accent" in css         # uses CSS variable system


def test_unknown_template_falls_back_to_default():
    css = template_css("nope", accent="#1a7f43")
    assert css == template_css("academic", accent="#1a7f43")


def test_malicious_accent_is_rejected_not_injected():
    """accent is attacker-controllable (round-trips via the /api/slides POST
    body), so a CSS-injection payload must fall back to the safe default rather
    than break out of the --accent declaration."""
    payload = "#fff; } body { background:url(http://169.254.169.254/) } :root{--x:"
    css = template_css("academic", accent=payload)
    assert "url(http://169.254.169.254/)" not in css
    assert "169.254.169.254" not in css
    # falls back to the hardcoded safe accent
    assert css == template_css("academic", accent="#1a7f43")


def test_valid_hex_accents_pass_through():
    for good in ("#abc", "#1a7f43", "#1A7F43FF"):
        assert good.lstrip("#") in template_css("academic", accent=good)


def test_accent_with_trailing_or_embedded_newline_is_rejected():
    """Guards the fullmatch (not match) invariant: Python's `$` matches before a
    trailing newline, so .match() would accept '#fff\\n'. .fullmatch() must not."""
    for bad in ("#fff\n", "#1a7f43\n", "#fff\n; }", "#fff\r\n"):
        css = template_css("academic", accent=bad)
        assert css == template_css("academic", accent="#1a7f43")  # safe fallback
