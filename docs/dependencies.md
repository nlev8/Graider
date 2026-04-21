# Dependency Management

Graider uses **pip-tools** for reproducible, hash-verified installs.

## Files

- `requirements.in` — **edited by humans.** Loose version declarations for runtime deps.
- `requirements.txt` — **generated.** Output of `pip-compile` with full pinning + hashes. Never hand-edit.
- `requirements-dev.in` — **edited by humans.** Dev-only deps (pytest, selenium, etc. — NOT playwright; that's runtime).
- `requirements-dev.txt` — **generated.** Constrained against `requirements.txt`. Never hand-edit.

## Install

```
pip install --require-hashes -r requirements.txt -r requirements-dev.txt
```

## Add a new runtime package

1. Add to `requirements.in` (loose, e.g. `somelib>=1.2`).
2. Run `pip-compile --generate-hashes --allow-unsafe --output-file=requirements.txt requirements.in`.
3. Run `pip-compile --generate-hashes --allow-unsafe --output-file=requirements-dev.txt requirements-dev.in -c requirements.txt` (to keep dev aligned).
4. Commit both `.in` and `.txt` files.
5. Open PR. The `lockfile-drift-check` CI job verifies your `.txt` files match what `.in` would regenerate.

## Add a new dev-only package

1. Add to `requirements-dev.in`.
2. Run `pip-compile --generate-hashes --allow-unsafe --output-file=requirements-dev.txt requirements-dev.in -c requirements.txt`.
3. Commit both `.in` and `.txt` files.

## Upgrade a package

Same as adding — edit the version pin in the relevant `.in` file, then recompile both lockfiles as above.

## Resolve a conflict

`pip-compile` will print which pins conflict. Common causes:
- Overly tight pin on a transitive dep — relax the constraint in `.in`.
- Incompatible versions across two direct deps — pick one to pin looser.

## Hash mismatch at install

Means someone hand-edited `.txt` without recompiling. Regenerate both lockfiles with `pip-compile`, commit, retry.

## Why --allow-unsafe?

`py2app` (in `requirements-dev.in`) pulls in `setuptools` as a transitive dep. pip-compile classifies `setuptools`, `pip`, and `wheel` as "unsafe" by default and won't pin them without this flag. The flag is safe to use here — it just means those packages get pinned and hashed like everything else.
