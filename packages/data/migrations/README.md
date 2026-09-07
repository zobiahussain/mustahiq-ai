# Migrations

## What a migration actually is, in plain terms

Every change to the database's *structure* (a new column, a new table, a new
index -- anything that isn't just adding/editing rows) is written down as a
small, numbered `.sql` file here, in the order it happened. A tiny Python
script (`run_migrations.py`) keeps a table in the database itself
(`schema_migrations`) that records which of these files have already been
run. Every time you run the script, it looks at that table, finds the files
that AREN'T in it yet, and runs only those, in order.

That solves a specific, real problem this project hit: before this folder
existed, every schema change this session was applied by hand, directly
against the live Supabase database, through a one-off `psycopg2` script or
the Supabase SQL editor -- and then the `.sql` files under
`packages/data/schema/` were edited afterwards, by hand, to match. That works
as long as one person remembers to do both steps every time. It stops
working the moment:
- a second person on the team touches the same database and doesn't know
  what's already been applied,
- someone sets up a fresh database (a new Supabase project, a teammate's
  local Postgres) and needs to bring it up to the CURRENT structure, not
  just the structure from whenever the `.sql` files were last hand-edited,
- or the `.sql` files and the live database quietly drift apart, and nobody
  notices until a query fails.

A migration file is the fix: instead of "the database was changed, and
separately, someone wrote down what changed," it's "the file IS the change" --
running it against any database (a fresh one or an existing one) always
produces the same result, because `schema_migrations` remembers what already
ran and skips it.

## What's already live vs. what's a migration

The two files under `packages/data/schema/` --
`al_khidmat_core_schema.sql` and `al_khidmat_marketplace_schema.sql` -- are
the **baseline**: everything needed to create the database from nothing, and
they're kept up to date with what's actually live as of the last time this
README was edited. Migrations in this folder are for changes made **after**
that point, going forward. So:

- **Setting up a brand-new database** (a fresh Supabase project, a
  teammate's own instance): run the two schema files first, in order (core,
  then marketplace -- marketplace references core's tables), THEN run
  `run_migrations.py` to catch it up to anything added since.
- **This project's existing live database**: just run `run_migrations.py` --
  the baseline is already there; only the migrations are new.

## Running it

```
cd packages/data
../rag/.venv/Scripts/python.exe run_migrations.py
```

Safe to run repeatedly -- already-applied migrations are skipped, and each
migration runs inside its own transaction (a migration that fails partway
rolls back cleanly, it doesn't leave the schema half-changed).

## Adding a new migration

Create a new file here named `NNNN_short_description.sql`, one number higher
than the last one, containing plain SQL. Use `if not exists` /
`if exists` guards where the statement supports it (see `0001_...sql` for the
pattern) -- makes the file safe to read and reason about even if it's ever
run against a database that's in a slightly unexpected state. Then run
`run_migrations.py` to apply it, and update the relevant `schema/*.sql` file
by hand to match, same as before -- migrations record *history*, the
`schema/*.sql` files stay the readable *current snapshot*.
