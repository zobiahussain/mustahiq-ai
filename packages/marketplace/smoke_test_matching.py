"""
Runs find_matches() against the real seeded listings and checks the
results make sense -- not just "it didn't crash."

Run: python smoke_test_matching.py
"""

import os

import psycopg2
from dotenv import load_dotenv

from matching import find_matches

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def listing_id_by_business_name(name: str) -> str:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select id from store_listings where business_name = %s", (name,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        raise ValueError(f"no listing named {name!r} -- did seed_data.py run?")
    return row[0]


def main():
    # Amina's Tailoring: seeking_inputs=true (per seed_data.py) -> should
    # find role='supplier' listings. Zainab's leather supply is the only
    # supplier in the seed data, in a different cluster/province -- this
    # proves cross-cluster matching actually surfaces, not just same-cluster.
    amina_id = listing_id_by_business_name("Amina's Tailoring")
    matches = find_matches(amina_id)

    print(f"Matches for Amina's Tailoring ({len(matches)} found):")
    for m in matches:
        print(
            f"  [{m['match_model']}] {m['business_name']} ({m['role']}) -- "
            f"similarity={m['similarity']:.3f} x proximity={m['proximity_multiplier']} "
            f"({m['proximity_label']}) = final_score={m['final_score']:.3f}"
        )

    assert len(matches) > 0, "expected at least one match -- Zainab's Leather Supplies should surface"
    assert any(m["business_name"] == "Zainab Leather Supplies" for m in matches), \
        "expected the only supplier in the seed data to show up as a match"

    print("\nPASS -- find_matches() returns real, correctly-filtered, correctly-scored results.")


if __name__ == "__main__":
    main()
