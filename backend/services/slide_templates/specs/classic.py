"""Classic group descriptors — the four migrated templates, now full skins.

Each decor_css below uses implicit adjacent-string concatenation: every line is a
complete, self-terminated CSS rule, so keep each fragment a whole rule (a dropped
trailing ';' would be a silent style bug, not a syntax error)."""
from backend.services.slide_templates.types import Font, ImageStyle, TemplateSpec
from backend.services.slide_templates.specs._fonts import INTER

EDITORIAL_BOLD = TemplateSpec(
    key="editorial-bold", name="Editorial Bold", group="Classic",
    fonts=(Font("Playfair Display", "PlayfairDisplay-700-normal.woff2", 700),
           Font("Playfair Display", "PlayfairDisplay-900-normal.woff2", 900), INTER),
    tokens={
        "--bg": "#f7f3ea", "--ink": "#1f1b16", "--muted": "#6b6453", "--accent": "#c0392b",
        "--font-head": "'Playfair Display', Georgia, serif", "--font-body": "'Inter', system-ui, sans-serif",
        "--pad": "84px", "--img-radius": "4px",
        "--title-size": "72px", "--title-weight": "900", "--head-size": "44px",
    },
    decor_css=".kicker{border-bottom:1px solid #d8d2c2;padding-bottom:10px;}"
              ".bullets li{border-bottom:1px solid #ece7da;padding-bottom:14px;}"
              ".bullets li::before{content:'\\2014';}",
    image_style=ImageStyle(
        medium="refined editorial illustration", composition="elegant, generous whitespace, sophisticated",
        avoid="text, logos, watermarks, clutter",
        education_constraints="clear, age-appropriate, subject-accurate, legible behind text"),
    accent_role="ai",
)

VIBRANT_GRADIENT = TemplateSpec(
    key="vibrant-gradient", name="Vibrant Gradient", group="Classic",
    fonts=(Font("Space Grotesk", "SpaceGrotesk-700-normal.woff2", 700), INTER),
    tokens={
        "--bg": "linear-gradient(135deg,#6d28d9,#db2777 55%,#f59e0b)", "--ink": "#ffffff",
        "--muted": "#f0e6ff", "--accent": "#ffe14d",
        "--font-head": "'Space Grotesk', system-ui, sans-serif", "--font-body": "'Inter', system-ui, sans-serif",
        "--pad": "72px", "--img-radius": "16px",
        "--title-size": "66px", "--head-size": "44px", "--title-color": "#ffffff", "--head-color": "#ffffff",
    },
    decor_css=".bullets li{background:rgba(255,255,255,.14);padding:12px 18px;border-radius:10px;}"
              ".s-head{letter-spacing:-1px;}",
    image_style=ImageStyle(
        medium="bright bold flat-vector illustration", composition="energetic, high-saturation, dynamic",
        avoid="text, logos, watermarks",
        education_constraints="clear, age-appropriate, subject-accurate, legible behind text"),
    accent_role="ai",
)

CINEMATIC = TemplateSpec(
    key="cinematic", name="Cinematic Dark", group="Classic",
    fonts=(Font("Space Grotesk", "SpaceGrotesk-700-normal.woff2", 700), INTER),
    tokens={
        "--bg": "radial-gradient(120% 120% at 80% 0%,#13233a,#070b12 70%)", "--ink": "#ffffff",
        "--muted": "#8aa0bf", "--accent": "#7CFC00",
        "--font-head": "'Space Grotesk', system-ui, sans-serif", "--font-body": "'Inter', system-ui, sans-serif",
        "--pad": "72px", "--img-radius": "14px",
        "--title-size": "72px", "--head-size": "46px",
    },
    decor_css=".s-title,.key-concept .big{letter-spacing:-1px;}"
              ".bullets li{background:rgba(255,255,255,.06);padding:12px 18px;border-radius:10px;}",
    image_style=ImageStyle(
        medium="dramatic dark cinematic illustration", composition="high-contrast, moody, atmospheric",
        avoid="text, logos, watermarks",
        education_constraints="clear, age-appropriate, subject-accurate, legible behind text"),
    accent_role="fixed",
)

PLAYFUL_ORGANIC = TemplateSpec(
    key="playful-organic", name="Playful Organic", group="Classic",
    fonts=(Font("Fredoka", "Fredoka-600-normal.woff2", 600),),
    tokens={
        "--bg": "#fff6ec", "--ink": "#4a3b28", "--muted": "#8a7a63", "--accent": "#ef476f",
        "--font-head": "'Fredoka', 'Trebuchet MS', sans-serif", "--font-body": "'Fredoka', 'Trebuchet MS', sans-serif",
        "--pad": "72px", "--img-radius": "24px",
        "--title-size": "64px", "--head-size": "44px", "--head-color": "#ef476f", "--title-color": "#3d348b",
    },
    decor_css=".bullets li{background:#fff3e0;padding:14px 20px;border-radius:18px;}"
              ".bullets li::before{content:'\\2728';}",
    image_style=ImageStyle(
        medium="friendly rounded flat illustration", composition="cheerful, warm, simple shapes",
        avoid="text, logos, watermarks, scary imagery",
        education_constraints="clear, age-appropriate for younger grades, subject-accurate"),
    accent_role="ai",
)

SPECS = [EDITORIAL_BOLD, VIBRANT_GRADIENT, CINEMATIC, PLAYFUL_ORGANIC]
