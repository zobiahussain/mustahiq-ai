"""
Proves logistics both ways: direct search, and automatic attachment to
a real cross-cluster supply_chain match.

Run: python smoke_test_logistics.py
"""

import os

import psycopg2
from dotenv import load_dotenv

from logistics import add_logistics_route, search_transport
from matching_pipeline import match_and_notify
from persist import get_stored_matches

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select id from store_listings where business_name = 'Kashif Rickshaw Transport'")
    kashif_logistics_id = cur.fetchone()[0]
    conn.close()

    print("--- add_logistics_route() ---")
    route_id = add_logistics_route(
        kashif_logistics_id, "Lahore", "Hyderabad", "rickshaw", "up to 200kg"
    )
    print(f"route added: {route_id}")

    print("\n--- add_logistics_route() rejects a non-logistics listing ---")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select id from store_listings where business_name = %s", ("Amina's Tailoring",))
    amina_id = cur.fetchone()[0]
    conn.close()
    try:
        add_logistics_route(amina_id, "Lahore", "Hyderabad")
        print("BUG: should have raised")
    except ValueError as e:
        print("correctly rejected:", e)

    print("\n--- search_transport() direct search ---")
    results = search_transport("Lahore", "Hyderabad")
    for r in results:
        print(" ", r)
    assert any(r["business_name"] == "Kashif Rickshaw Transport" for r in results)
    print("PASS -- found via direct search")

    print("\n--- automatic attachment to a real cross-cluster supply_chain match ---")
    # Amina (Lahore, seeking_inputs) x Zainab (Hyderabad, supplier) is
    # already a real cross-cluster match from earlier testing. Re-run
    # matching for Amina to exercise the attach path (it runs on every
    # NEW match; force a clean slate for this one pair so it's new again).
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select id from store_listings where business_name = 'Zainab Leather Supplies'")
    zainab_id = cur.fetchone()[0]
    cur.execute(
        "delete from marketplace_matches where (listing_a_id in (%s,%s) and listing_b_id in (%s,%s))",
        (amina_id, zainab_id, amina_id, zainab_id),
    )
    conn.commit()
    conn.close()

    match_and_notify(amina_id)

    matches = get_stored_matches(amina_id)
    zainab_match = [m for m in matches if m["business_name"] == "Zainab Leather Supplies"][0]
    print("suggested_logistics_business_name:", zainab_match["suggested_logistics_business_name"])
    assert zainab_match["suggested_logistics_business_name"] == "Kashif Rickshaw Transport"
    print("PASS -- cross-cluster supply_chain match automatically got a logistics suggestion.")


if __name__ == "__main__":
    main()
