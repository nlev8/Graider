"""Alembic online-mode environment.

Reads ALEMBIC_DATABASE_URL from the environment and connects via
psycopg 3 (sync). Configures transaction_per_migration=True so that
each revision runs in its own transaction — this is required by the
autocommit-only DDL policy in
docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md.

We do NOT import from sqlalchemy.orm or any Graider application
modules here. This file must work against a completely empty Python
environment that has only alembic + psycopg installed, because the
Railway pre-deploy command runs it before the Flask app starts.
"""
from __future__ import annotations

import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool


_config = context.config


def _database_url() -> str:
    url = os.getenv("ALEMBIC_DATABASE_URL")
    if not url:
        print(
            "ERROR: ALEMBIC_DATABASE_URL environment variable is not set. "
            "Set it to a Postgres connection string (session pooler or "
            "direct — NOT transaction pooler). Example:\n"
            "  export ALEMBIC_DATABASE_URL='postgresql+psycopg://user:pw@host:port/db'",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return url


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a live database connection."""
    configuration = _config.get_section(_config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            # transaction_per_migration=True so each revision runs in its
            # own transaction. This is required by the spec's
            # autocommit-only DDL policy — without it, a failed autocommit
            # revision could strand work from earlier revisions in the
            # same `alembic upgrade` run.
            transaction_per_migration=True,
            # target_metadata stays None — we do not use autogenerate.
            # All migrations are raw op.execute() SQL.
            target_metadata=None,
            # Compare server default and type info is pointless without
            # metadata; explicitly off.
            compare_server_default=False,
            compare_type=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    # Offline mode is not supported in Graider's workflow. All migrations
    # run online against Railway's Postgres via the preDeployCommand.
    # Fail loudly rather than silently emitting SQL to stdout.
    print(
        "ERROR: Alembic offline mode is not supported. "
        "Run without --sql; migrations must execute online against the "
        "target database.",
        file=sys.stderr,
    )
    raise SystemExit(2)

run_migrations_online()
