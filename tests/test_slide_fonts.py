import json
import os

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "assets", "slide_fonts")


def test_manifest_files_all_exist_and_are_licensed():
    with open(os.path.join(FONT_DIR, "MANIFEST.json")) as f:
        manifest = json.load(f)
    assert manifest, "manifest is empty"
    for entry in manifest:
        assert os.path.exists(os.path.join(FONT_DIR, entry["file"])), entry["file"]
        assert entry["license"] in ("OFL-1.1", "Apache-2.0")
        assert entry["family"] and entry["weight"] and entry["source"]
    # license text shipped
    assert os.path.exists(os.path.join(FONT_DIR, "LICENSES", "OFL-1.1.txt"))
