"""
Proves the actual "delayed match" scenario from Marketplace_Spec.md
section 5.2: an OLDER, pre-existing listing gets notified when a NEWLY
created listing turns out to match it -- not just the new listing's own
owner finding out.

Bilal Ahmed (Sukkur) has no listing yet. Creating a leather-supply
listing for him should match Amina's Tailoring (already existed before
this script ran) -- and BOTH Amina and Bilal should get notified, even
though Amina did nothing just now. That's the actual fix, demonstrated,
not just asserted.

Run: python smoke_test_delayed_match.py
"""

import os

import psycopg2
from dotenv import load_dotenv

from create_listing import enrich_listing_text, save_listing
from matching_pipeline import match_and_notify

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def get_beneficiary_id(name):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select id from beneficiary_profiles where full_name = %s", (name,))
    row = cur.fetchone()
    conn.close()
    return row[0]


def cleanup_old_test_listing(beneficiary_id):
    """Remove any listing this script created on a previous run, so this stays repeatable."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        "delete from marketplace_matches where listing_a_id in "
        "(select id from store_listings where primary_beneficiary_id = %s) "
        "or listing_b_id in (select id from store_listings where primary_beneficiary_id = %s)",
        (beneficiary_id, beneficiary_id),
    )
    cur.execute("delete from listing_participants where beneficiary_id = %s", (beneficiary_id,))
    cur.execute("delete from store_listings where primary_beneficiary_id = %s", (beneficiary_id,))
    conn.commit()
    conn.close()


def main():
    bilal_id = get_beneficiary_id("Bilal Ahmed")
    cleanup_old_test_listing(bilal_id)

    print("Creating a NEW leather-supply listing for Bilal (Sukkur)...")
    print("(Amina's Tailoring already existed before this line ran -- the delayed match.)\n")

    draft = enrich_listing_text(bilal_id, "چمڑا فراہم کرتا ہوں")  # "I supply leather"
    listing_id = save_listing(
        beneficiary_id=bilal_id,
        role="supplier",
        product_or_service_en=draft["product_or_service_en"],
        product_or_service_original=draft["product_or_service_original"],
        skills_en=draft.get("skills_en"),
        is_remote_capable=False,
        output_is_physical=True,
        will_deliver_outside_area=True,
        business_name="Bilal Leather Trading",
    )
    print(f"Created listing: {listing_id}\n")

    print("Running match_and_notify() -- watch for TWO [SMS] lines below,")
    print("one to Bilal (the new listing), one to Amina (the OLD listing")
    print("that just got a new match it had no way to know about until now):\n")

    matches = match_and_notify(listing_id)

    print(f"\n{len(matches)} match(es) found and processed.")
    for m in matches:
        print(f"  {m['business_name']} -- is_new notification cycle already ran above")


if __name__ == "__main__":
    main()
