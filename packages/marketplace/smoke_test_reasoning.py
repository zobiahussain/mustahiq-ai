"""
Runs find_matches() then generate_match_reason() on the real result --
proves the full "find it, then explain it" loop works together, since
that's the actual feature (matches WITH reasoning), not two separate
unconnected pieces.

Run: python smoke_test_reasoning.py
"""

import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from matching import find_matches, _fetch_listing
from reasoning import add_reasons

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select id from store_listings where business_name = %s", ("Amina's Tailoring",))
    amina_id = cur.fetchone()[0]

    # find_matches() doesn't return the source listing itself -- fetch it
    # the same way find_matches() does internally, so the reasoning step
    # has product_or_service_en to work with.
    cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    source = _fetch_listing(cur2, amina_id)
    conn.close()

    matches = find_matches(amina_id)
    assert matches, "expected at least one match"

    matches_with_reasons = add_reasons(source, matches)

    print(f"Matches for {source['business_name']}, with reasoning:\n")
    for m in matches_with_reasons:
        print(f"  {m['business_name']} ({m['match_model']}, score={m['final_score']:.3f})")
        print(f"  Reason: {m['reason']}\n")

    print("PASS -- full find + explain loop works.")


if __name__ == "__main__":
    main()
