import os


def graider_export_dir(*subpath: str) -> str:
    """Resolved export base, joined with optional subpath. Call-time only.

    ``GRAIDER_EXPORT_DIR`` overrides the base; default is the historical
    ``~/Downloads/Graider`` so behavior is byte-identical to the prior code
    when the variable is unset. An empty value is treated as unset (falls
    back to the default). Does not create directories.
    """
    base = os.environ.get("GRAIDER_EXPORT_DIR") or os.path.expanduser("~/Downloads/Graider")
    return os.path.join(base, *subpath)
