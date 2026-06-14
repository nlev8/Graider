"""Fetch the OFL woff2 files the slide templates embed, into
backend/assets/slide_fonts/, and write MANIFEST.json. Re-runnable.

Sources are the @fontsource CDN (jsDelivr), which serves OFL Google Fonts as
woff2 at stable paths. Pin exact versions here so builds are reproducible."""
import json
import os
import urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "backend", "assets", "slide_fonts")
BASE = "https://cdn.jsdelivr.net/npm"

# (family, css_family, weight, style, npm pkg@ver, woff2 path within pkg, license_id)
FONTS = [
    ("Inter",          "Inter",          400, "normal", "@fontsource/inter@5.0.18",          "/files/inter-latin-400-normal.woff2",          "OFL-1.1"),
    ("Inter",          "Inter",          800, "normal", "@fontsource/inter@5.0.18",          "/files/inter-latin-800-normal.woff2",          "OFL-1.1"),
    ("PlayfairDisplay","Playfair Display",700, "normal","@fontsource/playfair-display@5.0.19","/files/playfair-display-latin-700-normal.woff2","OFL-1.1"),
    ("PlayfairDisplay","Playfair Display",900, "normal","@fontsource/playfair-display@5.0.19","/files/playfair-display-latin-900-normal.woff2","OFL-1.1"),
    ("SpaceGrotesk",   "Space Grotesk",  700, "normal", "@fontsource/space-grotesk@5.0.18",  "/files/space-grotesk-latin-700-normal.woff2",  "OFL-1.1"),
    ("Fredoka",        "Fredoka",        600, "normal", "@fontsource/fredoka@5.2.10",        "/files/fredoka-latin-600-normal.woff2",        "OFL-1.1"),
    ("SpaceMono",      "Space Mono",     700, "normal", "@fontsource/space-mono@5.0.18",     "/files/space-mono-latin-700-normal.woff2",     "OFL-1.1"),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    for fam, css_family, weight, style, pkg, path, lic in FONTS:
        fname = f"{fam}-{weight}-{style}.woff2"
        url = f"{BASE}/{pkg}{path}"
        dest = os.path.join(OUT, fname)
        print("fetch", url)
        urllib.request.urlretrieve(url, dest)
        manifest.append({"file": fname, "family": css_family, "weight": weight,
                         "style": style, "license": lic, "source": url})
    with open(os.path.join(OUT, "MANIFEST.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("wrote", len(manifest), "fonts +", "MANIFEST.json")


if __name__ == "__main__":
    main()
