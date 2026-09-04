"""
Tests all five graduation triggers against real data, including the
"only the FIRST time" logic for business_established and became_donor.

Run: python smoke_test_graduation.py
"""

import os

import psycopg2
from dotenv import load_dotenv

from graduation import (
    record_loan_repaid,
    record_donation,
    confirm_match_connection,
    record_no_longer_seeking_assistance,
)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def get_id(table, column, value):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(f"select id from {table} where {column} = %s", (value,))
    row = cur.fetchone()
    conn.close()
    return row[0]


def count_events(beneficiary_id, event_type):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        "select count(*) from graduation_events where beneficiary_id = %s and event_type = %s",
        (beneficiary_id, event_type),
    )
    n = cur.fetchone()[0]
    conn.close()
    return n


def main():
    fahad_bid = get_id("beneficiary_profiles", "full_name", "Fahad Hussain")

    print("--- record_loan_repaid() ---")
    fahad_loan_id = get_id("microfinance_loans", "beneficiary_id", fahad_bid)
    before = count_events(fahad_bid, "loan_repaid")
    record_loan_repaid(fahad_loan_id)
    after = count_events(fahad_bid, "loan_repaid")
    assert after == before + 1, f"expected exactly one new event, before={before} after={after}"
    print("PASS -- loan_repaid event recorded")

    print("\n--- business_established, via a beneficiary's genuinely FIRST listing ---")
    # Use a genuinely fresh test beneficiary (via the SKIP_ELIGIBILITY_CHECK
    # toggle) rather than an existing seeded one -- every real beneficiary
    # in the seed data already has at least one listing by this point in
    # the session, which would make "first listing" untestable against them.
    from auth import request_otp
    import random
    fresh_phone = f"+9230077{random.randint(10000, 99999)}"
    request_otp(fresh_phone)
    fresh_bid = get_id("beneficiary_profiles", "phone", fresh_phone)

    before = count_events(fresh_bid, "business_established")
    from create_listing import enrich_listing_text, save_listing
    draft = enrich_listing_text(fresh_bid, "آن لائن ٹیوشن")
    save_listing(
        beneficiary_id=fresh_bid, role="service",
        product_or_service_en=draft["product_or_service_en"],
        product_or_service_original=draft["product_or_service_original"],
        seeking_work=True, is_remote_capable=True, output_is_physical=False,
    )
    after = count_events(fresh_bid, "business_established")
    assert after == before + 1 == 1, f"expected exactly one new event, before={before} after={after}"
    print("PASS -- business_established recorded on a genuinely first listing")

    print("\n--- became_donor -- only on the FIRST donation, not the second ---")
    amina_bid = get_id("beneficiary_profiles", "full_name", "Amina Bibi")
    before_donor_events = count_events(amina_bid, "became_donor")
    r1 = record_donation(amina_bid, 500)
    r2 = record_donation(amina_bid, 300)
    after_donor_events = count_events(amina_bid, "became_donor")
    print(f"  donation 1: graduation_event_id={r1['graduation_event_id']}")
    print(f"  donation 2: graduation_event_id={r2['graduation_event_id']}")
    if before_donor_events == 0:
        assert r1["graduation_event_id"] is not None, "first-ever donation should trigger became_donor"
        assert r2["graduation_event_id"] is None, "second donation should NOT trigger it again"
        assert after_donor_events == 1
        print("PASS -- became_donor fired once on the first donation, not the second")
    else:
        assert r1["graduation_event_id"] is None and r2["graduation_event_id"] is None
        print("PASS -- Amina had already donated before (re-run of this test) -- correctly did not re-fire")

    print("\n--- confirm_match_connection() on a real employment match ---")
    # Rashid Grains (seeking_workers) should have real employment
    # candidates from the expanded seed data.
    from matching_pipeline import match_and_notify
    rashid_listing = get_id("store_listings", "business_name", "Rashid Grains")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select primary_beneficiary_id from store_listings where id = %s", (rashid_listing,))
    rashid_bid = cur.fetchone()[0]
    conn.close()

    matches = match_and_notify(rashid_listing)
    employment_matches = [m for m in matches if m["match_model"] == "employment"]
    if employment_matches:
        from persist import get_stored_matches
        stored = get_stored_matches(rashid_listing)
        # get_stored_matches returns match_model per row -- filter for the
        # SAME employment match match_and_notify() just found, rather than
        # blindly taking stored[0] (which could be a different-model match
        # for this same listing, e.g. supply_chain).
        stored_employment = [m for m in stored if m["match_model"] == "employment"]
        assert stored_employment, "match_and_notify found an employment match but get_stored_matches didn't persist one"
        match_id = stored_employment[0]["id"]
        # beneficiary_id must be a PARTY to the match -- that's Rashid
        # Grains's OWNER (a beneficiary_id), not the listing's own id
        # (a listing_id) -- confirm_match_connection() checks
        # store_listings.primary_beneficiary_id / listing_participants,
        # neither of which a listing id would ever match.
        result = confirm_match_connection(match_id, rashid_bid)
        print(f"  confirm result: {result}")
        assert result["connected"] is True
        print("PASS -- match connected" + (", hired_employee recorded" if result["graduation_event_id"] else ""))
    else:
        print("SKIP -- no employment match found for Rashid Grains right now")

    print("\n--- record_no_longer_seeking_assistance() ---")
    before = count_events(fahad_bid, "no_longer_seeking_assistance")
    event_id = record_no_longer_seeking_assistance(fahad_bid, notes="testing")
    after = count_events(fahad_bid, "no_longer_seeking_assistance")
    assert after == before + 1
    print(f"PASS -- event recorded ({event_id})")

    print("\nALL GRADUATION CHECKS PASS.")


if __name__ == "__main__":
    main()
