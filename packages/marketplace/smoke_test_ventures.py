"""
Proves venture formation end to end, including the security check and
that both parent listings' availability actually changes.

Run: python smoke_test_ventures.py
"""

import os

import psycopg2
from dotenv import load_dotenv

from create_listing import enrich_listing_text, save_listing
from ventures import form_venture

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def get_id(table, column, value):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(f"select id from {table} where {column} = %s", (value,))
    row = cur.fetchone()
    conn.close()
    return row[0]


def main():
    amina_bid = get_id("beneficiary_profiles", "full_name", "Amina Bibi")
    amina_listing = get_id("store_listings", "business_name", "Amina's Tailoring")
    zainab_listing = get_id("store_listings", "business_name", "Zainab Leather Supplies")

    print("--- Amina creates the venture's own listing (normal flow, reused as-is) ---")
    draft = enrich_listing_text(amina_bid, "سلائی اور چمڑے کی مشترکہ دکان")  # combined tailoring+leather shop
    venture_id = save_listing(
        beneficiary_id=amina_bid,
        role="producer",
        product_or_service_en=draft["product_or_service_en"],
        product_or_service_original=draft["product_or_service_original"],
        skills_en=draft.get("skills_en"),
        is_remote_capable=False,
        output_is_physical=True,
        business_name="Amina & Zainab Combined Leather Goods",
    )
    print(f"venture listing created: {venture_id}")

    print("\n--- security check: a beneficiary who owns NEITHER parent should be rejected ---")
    bilal_bid = get_id("beneficiary_profiles", "full_name", "Bilal Ahmed")
    try:
        form_venture(bilal_bid, venture_id, [amina_listing, zainab_listing])
        print("BUG: should have raised")
    except ValueError as e:
        print("correctly rejected:", e)

    print("\n--- form_venture() for real, called by Amina (who owns one parent) ---")
    form_venture(amina_bid, venture_id, [amina_listing, zainab_listing])

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        "select parent_listing_id from venture_lineage where venture_listing_id = %s", (venture_id,)
    )
    lineage = {row[0] for row in cur.fetchall()}
    assert lineage == {amina_listing, zainab_listing}, f"expected both parents in lineage, got {lineage}"
    print("PASS -- venture_lineage records both parents")

    cur.execute(
        "select beneficiary_id from listing_participants where listing_id = %s and role = 'owner'",
        (venture_id,),
    )
    owners = {row[0] for row in cur.fetchall()}
    zainab_bid = get_id("beneficiary_profiles", "full_name", "Zainab Sheikh")
    assert owners == {amina_bid, zainab_bid}, f"expected both original owners, got {owners}"
    print("PASS -- both Amina and Zainab are now owners of the venture listing")

    cur.execute("select availability from store_listings where id in (%s, %s)", (amina_listing, zainab_listing))
    availabilities = [row[0] for row in cur.fetchall()]
    assert all(a == "committed" for a in availabilities), f"expected both committed, got {availabilities}"
    print("PASS -- both parent listings' own availability is now 'committed'")

    conn.close()
    print("\nALL VENTURE CHECKS PASS.")


if __name__ == "__main__":
    main()
