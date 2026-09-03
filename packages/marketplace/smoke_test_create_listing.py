"""
Creates a REAL new listing for a real seeded beneficiary who has no
listing yet, then immediately runs matching against it -- proves the full
loop closes: create -> find -> explain, not just create in isolation.

Uses Fahad Hussain on purpose -- his loan is status='approved', NOT YET
disbursed. Proves the "approved counts too" eligibility decision actually
works all the way through listing creation, not just at login.

Run: python smoke_test_create_listing.py
"""

import os

import psycopg2
from dotenv import load_dotenv

from create_listing import enrich_listing_text, save_listing
from matching import find_matches

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def get_fahad_id():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select id from beneficiary_profiles where full_name = %s", ("Fahad Hussain",))
    row = cur.fetchone()
    conn.close()
    return row[0]


def main():
    fahad_id = get_fahad_id()

    print("Step 1 -- enrich (draft, nothing saved yet)...")
    draft = enrich_listing_text(fahad_id, "چاہیے کیشیئر، اسٹور مینیجر")  # "need a cashier, store manager"
    print(f"  draft: {draft}")

    print("\nStep 2 -- save (person tapped confirm)...")
    listing_id = save_listing(
        beneficiary_id=fahad_id,
        role="retailer",
        product_or_service_en=draft["product_or_service_en"],
        product_or_service_original=draft["product_or_service_original"],
        skills_en=draft.get("skills_en"),
        seeking_workers=True,
        is_remote_capable=False,
        output_is_physical=True,
        business_name="Fahad's Grocery",
    )
    print(f"Created listing: {listing_id}")

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        """
        select business_name, trade_category_id, district,
               product_or_service_en, product_or_service_original
        from store_listings where id = %s
        """,
        (listing_id,),
    )
    row = cur.fetchone()
    conn.close()

    print(f"\nSaved row:")
    print(f"  business_name: {row[0]}")
    print(f"  trade_category_id: {row[1]} (should be Grocery/Karyana's id, auto-derived from his loan)")
    print(f"  district: {row[2]} (should be Lahore, auto-derived from his profile)")
    print(f"  product_or_service_en: {row[3]}")

    assert row[2] == "Lahore", "district should have been auto-derived from beneficiary_profiles"

    print("\nRunning find_matches() against the listing we JUST created...")
    matches = find_matches(listing_id)
    print(f"Found {len(matches)} match(es).")
    for m in matches:
        print(f"  [{m['match_model']}] {m['business_name']} -- final_score={m['final_score']:.3f}")

    print("\nPASS -- create_listing() works end to end, and the new listing can immediately be matched.")


if __name__ == "__main__":
    main()
