"""Shared Font instances reused across descriptors (DRY — see spec §3 elegance
bar). Body Inter is reused by most templates; the heavy weight pairs with it for
Swiss/Minimal-style headings."""
from backend.services.slide_templates.types import Font

INTER = Font("Inter", "Inter-400-normal.woff2", 400)
INTER_BLACK = Font("Inter", "Inter-800-normal.woff2", 800)
