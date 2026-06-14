"""Design-system CSS for web-rendered slide decks.

One base stylesheet (16:9 slide geometry + the six layout classes) plus four
token sets (CSS-variable overrides) = four professional templates without
re-implementing layouts per template. The per-deck AI accent color is injected
as --accent. See docs/superpowers/specs/2026-06-14-web-slide-decks-design.md.
"""
import re

DEFAULT_TEMPLATE = "academic"

# The accent color round-trips through the browser and back via the
# /api/slides/{html,pdf} POST body, so it is attacker-controllable. Validate it
# against a strict hex-color grammar before interpolating into a <style> block —
# a mere "#"-prefix check would let `#fff; } body { background:url(...) } :root{`
# through, injecting CSS (and, via server-side Chromium url(), an SSRF vector).
_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

# 1280x720 = 16:9. Each .slide is one print page.
_BASE_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
@page { size: 1280px 720px; margin: 0; }
html, body { background: #555; }
.deck { display:flex; flex-direction:column; align-items:center; gap:16px; }
.slide {
  width:1280px; height:720px; overflow:hidden; position:relative;
  background: var(--bg); color: var(--ink);
  font-family: var(--font-body);
  padding: var(--pad);
  display:flex; flex-direction:column;
  break-after: page;
}
.slide h1, .slide h2, .slide .kicker { font-family: var(--font-head); }
.kicker { text-transform:uppercase; letter-spacing:3px; font-size:18px; color:var(--accent); margin-bottom:18px; }
.s-title { font-size:64px; font-weight:800; line-height:1.05; color:var(--ink); }
.s-head { font-size:44px; font-weight:800; color:var(--accent); margin-bottom:28px; }
.s-sub { font-size:30px; color:var(--muted); margin-top:18px; }
.bullets { list-style:none; display:flex; flex-direction:column; gap:18px; font-size:28px; line-height:1.4; }
.bullets li { display:flex; gap:16px; align-items:flex-start; }
.bullets li::before { content:"\\25CF"; color:var(--accent); font-size:18px; line-height:1.9; }
.body-2col { display:flex; gap:48px; flex:1; }
.col { flex:1; }
.col h3 { font-size:30px; color:var(--accent); margin-bottom:16px; font-family:var(--font-head); }
.content-row { display:flex; gap:48px; flex:1; align-items:center; }
.content-row .text { flex:1.1; }
.content-row .art { flex:.9; display:flex; align-items:center; justify-content:center; }
.content-row .art img { max-width:100%; max-height:520px; border-radius:var(--img-radius); }
.image-focus { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:24px; }
.image-focus img { max-width:90%; max-height:540px; border-radius:var(--img-radius); }
.caption { font-size:24px; color:var(--muted); }
.key-concept { flex:1; display:flex; align-items:center; justify-content:center; text-align:center; }
.key-concept .big { font-size:52px; font-weight:800; color:var(--ink); max-width:1000px; line-height:1.2; }
.divider { flex:1; display:flex; align-items:center; }
.divider .s-title { font-size:72px; }
.accent-bar { position:absolute; top:0; left:0; right:0; height:10px; background:var(--accent); }
"""

# Per-template CSS-variable token sets + optional template-specific rules.
TEMPLATES = {
    "academic": {
        "vars": {
            "--bg": "#ffffff", "--ink": "#1c2530", "--muted": "#5b6577",
            "--font-head": "'Segoe UI', system-ui, sans-serif",
            "--font-body": "'Segoe UI', system-ui, sans-serif",
            "--pad": "72px", "--img-radius": "10px",
        },
        "extra": ".bullets li::before { content:\"\\2713\"; font-weight:700; }",
    },
    "editorial": {
        "vars": {
            "--bg": "#faf8f3", "--ink": "#23211c", "--muted": "#6b6453",
            "--font-head": "Georgia, 'Times New Roman', serif",
            "--font-body": "system-ui, sans-serif",
            "--pad": "84px", "--img-radius": "4px",
        },
        "extra": ".kicker { border-bottom:1px solid #d8d2c2; padding-bottom:10px; } .bullets li { border-bottom:1px solid #ece7da; padding-bottom:14px; } .bullets li::before { content:\"\\2014\"; }",
    },
    "bold": {
        "vars": {
            "--bg": "linear-gradient(150deg,#0b1220,#101826)", "--ink": "#ffffff",
            "--muted": "#aab6c8",
            "--font-head": "'Segoe UI', system-ui, sans-serif",
            "--font-body": "'Segoe UI', system-ui, sans-serif",
            "--pad": "72px", "--img-radius": "16px",
        },
        "extra": ".s-title, .key-concept .big { letter-spacing:-1px; } .bullets li { background:rgba(255,255,255,.06); padding:12px 18px; border-radius:10px; } .bullets li::before { color:var(--accent); }",
    },
    "playful": {
        "vars": {
            "--bg": "#fffdf8", "--ink": "#4a3b28", "--muted": "#8a7a63",
            "--font-head": "'Trebuchet MS', 'Segoe UI', sans-serif",
            "--font-body": "'Trebuchet MS', 'Segoe UI', sans-serif",
            "--pad": "72px", "--img-radius": "24px",
        },
        "extra": ".s-head, .s-title { color:var(--accent); } .bullets li { background:#fff3e0; padding:14px 20px; border-radius:18px; } .bullets li::before { content:\"\\2728\"; }",
    },
}


def template_css(template: str, accent: str) -> str:
    """Return the full <style> body for a template with the AI accent injected."""
    tmpl = TEMPLATES.get(template) or TEMPLATES[DEFAULT_TEMPLATE]
    safe_accent = accent if (isinstance(accent, str) and _HEX_COLOR.match(accent)) else "#1a7f43"
    root_vars = "".join(f"{k}:{v};" for k, v in tmpl["vars"].items())
    root = f":root{{--accent:{safe_accent};{root_vars}}}"
    return _BASE_CSS + "\n" + root + "\n" + tmpl.get("extra", "")
