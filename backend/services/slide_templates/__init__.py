"""Slide-template registry + resolution. Public API:
`template_css`, `get_spec`, `TEMPLATES`, `GROUPS`, `DEFAULT_TEMPLATE`, `LEGACY_ALIASES`,
and the descriptor types. See spec §3/§6/§8."""
from collections import OrderedDict

from .types import Font, ImageStyle, TemplateSpec  # noqa: F401
from .specs import ALL_SPECS

TEMPLATES = OrderedDict((s.key, s) for s in ALL_SPECS)
DEFAULT_TEMPLATE = "minimal"

# Old keys (pre-vivid-library) → new keys. Old `bold` was already a dark gradient,
# so bold→cinematic is faithful (spec §6 / §8).
LEGACY_ALIASES = {
    "academic": "minimal",
    "editorial": "editorial-bold",
    "bold": "cinematic",
    "playful": "playful-organic",
}

# group -> ordered list of keys (drives the picker; single source of truth)
_GROUP_ORDER = ["Classic", "Illustrated", "Themed", "Refined"]
GROUPS = OrderedDict(
    (g, [s.key for s in ALL_SPECS if s.group == g]) for g in _GROUP_ORDER
)
GROUPS = OrderedDict((g, ks) for g, ks in GROUPS.items() if ks)  # drop empty groups


def resolve_key(key):
    """Resolve a request key/alias to a registered key, falling back to default.

    Total for any input: a non-string key (None, an int, or an unhashable list/
    dict from a malformed request body) resolves to the default instead of
    raising — `key in TEMPLATES` would otherwise TypeError on unhashable input."""
    if not isinstance(key, str):
        return DEFAULT_TEMPLATE
    if key in TEMPLATES:
        return key
    if key in LEGACY_ALIASES:
        return LEGACY_ALIASES[key]
    return DEFAULT_TEMPLATE


def get_spec(key) -> TemplateSpec:
    """Return the TemplateSpec for a key/alias, default if unknown/None."""
    return TEMPLATES[resolve_key(key)]


# engine.template_css is imported last to avoid a circular import at module load
from .engine import template_css  # noqa: E402,F401
