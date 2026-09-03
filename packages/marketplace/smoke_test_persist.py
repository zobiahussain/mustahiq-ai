"""
Runs the full loop -- find, explain, save -- then runs it a SECOND time
to prove idempotency actually works (no crash, no duplicate row, same
match_id both times).

Run: python smoke_test_persist.py
"""

import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from matching import find_matches, _fetch_listing
from reasoning import add_reasons
from persist import persist_matches

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def get_amina_id():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select id from store_listings where business_name = %s", ("Amina's Tailoring",))
    row = cur.fetchone()
    conn.close()
    return row[0]


def run_once(amina_id):
    matches = find_matches(amina_id)

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    source = _fetch_listing(cur, amina_id)
    conn.close()

    matches = add_reasons(source, matches)
    return persist_matches(amina_id, matches)


def main():
    amina_id = get_amina_id()

    # Clean slate -- this test has been run before in this same session,
    # so without this, "first run should be new" would be testing
    # leftover state from a previous run, not what it claims to test.
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        "delete from marketplace_matches where listing_a_id = %s or listing_b_id = %s",
        (amina_id, amina_id),
    )
    conn.commit()
    conn.close()

    print("--- first run ---")
    results_1 = run_once(amina_id)
    print(f"saved: {results_1}")
    assert all(r["is_new"] for r in results_1), "first run should report every match as NEW"

    print("\n--- second run (should UPDATE, not duplicate) ---")
    results_2 = run_once(amina_id)
    print(f"saved: {results_2}")
    assert not any(r["is_new"] for r in results_2), "second run should report NOTHING as new -- same pairs already existed"

    ids_1 = [r["id"] for r in results_1]
    ids_2 = [r["id"] for r in results_2]
    assert ids_1 == ids_2, "same pair should produce the SAME row id both times, not a new one"

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        "select count(*) from marketplace_matches where listing_a_id = %s or listing_b_id = %s",
        (amina_id, amina_id),
    )
    count = cur.fetchone()[0]
    conn.close()

    print(f"\ntotal marketplace_matches rows for this listing: {count}")
    assert count == len(ids_1), "row count should match how many DISTINCT matches were found, no duplicates"

    print("\nPASS -- persisted, idempotent, no duplicates, is_new correctly True then False.")


if __name__ == "__main__":
    main()
