"""
Applies every not-yet-applied .sql file in migrations/, in filename order,
tracked in a schema_migrations table so re-running this is always safe --
see migrations/README.md for the concept and why this exists.

Run:
    cd packages/data
    ../rag/.venv/Scripts/python.exe run_migrations.py
"""

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run():
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print("no .sql files in migrations/ -- nothing to do")
        return

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    # The tracking table itself -- created once, on first run, the same way
    # every other table here is: plain SQL, no ORM. id is the filename
    # (e.g. "0001_matches_computed_at.sql"), so "has this run" is just a
    # primary-key lookup.
    cur.execute(
        """
        create table if not exists schema_migrations (
            id          text primary key,
            applied_at  timestamptz not null default now()
        )
        """
    )
    conn.commit()

    cur.execute("select id from schema_migrations")
    already_applied = {row[0] for row in cur.fetchall()}

    pending = [f for f in files if f.name not in already_applied]
    if not pending:
        print(f"up to date -- all {len(files)} migration(s) already applied.")
        cur.close()
        conn.close()
        return

    print(f"{len(pending)} pending migration(s) to apply:")
    for f in pending:
        sql = f.read_text(encoding="utf-8")
        print(f"  applying {f.name}...")
        try:
            # One transaction per migration -- a failure partway through
            # rolls back cleanly (the schema is never left half-changed),
            # and every migration after it in this run is skipped rather
            # than applied on top of a state its author didn't expect.
            cur.execute(sql)
            cur.execute(
                "insert into schema_migrations (id) values (%s)", (f.name,)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"  FAILED on {f.name}: {e}")
            print("  stopping here -- fix the migration and re-run "
                  "(everything before this one is already recorded as applied).")
            cur.close()
            conn.close()
            raise

    print(f"\nDone. {len(pending)} migration(s) applied.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    run()
