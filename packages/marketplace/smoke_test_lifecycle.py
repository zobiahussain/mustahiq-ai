"""
Tests all four lifecycle functions against real data, including the
negative cases (a loan with no trade category should NOT trigger an
invitation), not just the happy path.

Run: python smoke_test_lifecycle.py
"""

import os
import uuid

import psycopg2
from dotenv import load_dotenv

from lifecycle import (
    expire_stale_matches,
    expire_stale_listings,
    deactivate_listings_for_defaulted_loan,
    send_invitation_if_eligible,
)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    print("--- expire_stale_matches() ---")
    cur.execute("select id from marketplace_matches where status = 'active' limit 1")
    row = cur.fetchone()
    if row is None:
        # No active match anywhere -- create one fresh rather than skip
        # the test. Amina x Zainab always re-persists cleanly.
        cur.execute("select id from store_listings where business_name = %s", ("Amina's Tailoring",))
        amina_id = cur.fetchone()[0]
        conn.close()
        from matching_pipeline import match_and_notify
        match_and_notify(amina_id)
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute("select id from marketplace_matches where status = 'active' limit 1")
        row = cur.fetchone()

    match_id = row[0]
    cur.execute(
        "update marketplace_matches set expires_at = now() - interval '1 day' where id = %s",
        (match_id,),
    )
    conn.commit()
    count = expire_stale_matches()
    print(f"expired {count} match(es)")
    cur.execute("select status from marketplace_matches where id = %s", (match_id,))
    assert cur.fetchone()[0] == "expired"
    print("PASS -- confirmed status flipped to expired (open_request_count decrement already proven in persist.py's tests)")

    print("\n--- expire_stale_listings() ---")
    test_listing_id = str(uuid.uuid4())
    cur.execute(
        "select id from beneficiary_profiles where full_name = 'Bilal Ahmed'"
    )
    bilal_bid = cur.fetchone()[0]
    cur.execute(
        "select id from trade_categories where name = 'Manufacturing'"
    )
    cat_id = cur.fetchone()[0]
    cur.execute(
        """
        insert into store_listings
            (id, primary_beneficiary_id, business_name, trade_category_id,
             product_or_service_en, product_or_service_original, role,
             district, cluster_id, expires_at)
        values (%s, %s, 'Expiry Test Listing', %s, 'test', 'test', 'supplier',
                'Sukkur', 'SKR-01', current_date - interval '1 day')
        """,
        (test_listing_id, bilal_bid, cat_id),
    )
    conn.commit()
    count = expire_stale_listings()
    print(f"deactivated {count} listing(s)")
    cur.execute("select active from store_listings where id = %s", (test_listing_id,))
    assert cur.fetchone()[0] is False
    print("PASS -- confirmed the stale listing is now inactive")

    print("\n--- deactivate_listings_for_defaulted_loan() ---")
    cur.execute(
        "select ml.id from microfinance_loans ml "
        "join beneficiary_profiles bp on bp.id = ml.beneficiary_id "
        "where bp.full_name = 'Sara Iqbal' and ml.status = 'defaulted'"
    )
    sara_loan_id = cur.fetchone()[0]
    cur.execute("select id from beneficiary_profiles where full_name = 'Sara Iqbal'")
    sara_bid = cur.fetchone()[0]
    sara_listing_id = str(uuid.uuid4())
    cur.execute(
        """
        insert into store_listings
            (id, primary_beneficiary_id, business_name, trade_category_id,
             product_or_service_en, product_or_service_original, role,
             district, cluster_id, active)
        values (%s, %s, 'Saras Food Stall', %s, 'test', 'test', 'retailer',
                'Multan', 'MUL-01', true)
        """,
        (sara_listing_id, sara_bid, cat_id),
    )
    conn.commit()
    count = deactivate_listings_for_defaulted_loan(sara_loan_id)
    print(f"deactivated {count} listing(s) for Sara's defaulted loan")
    cur.execute("select active from store_listings where id = %s", (sara_listing_id,))
    assert cur.fetchone()[0] is False
    print("PASS -- Sara's listing correctly deactivated on her loan's default status")

    print("\n--- send_invitation_if_eligible() ---")
    cur.execute(
        "select ml.id from microfinance_loans ml "
        "join beneficiary_profiles bp on bp.id = ml.beneficiary_id "
        "where bp.full_name = 'Fahad Hussain'"
    )
    fahad_loan_id = cur.fetchone()[0]
    result = send_invitation_if_eligible(fahad_loan_id)
    assert result is True
    print("PASS -- eligible loan (has trade_category) correctly sent an invitation")

    cur.execute(
        "select ml.id from microfinance_loans ml "
        "join beneficiary_profiles bp on bp.id = ml.beneficiary_id "
        "where bp.full_name = 'Usman Tariq'"  # Liberation Loan, no trade category
    )
    usman_loan_id = cur.fetchone()[0]
    result = send_invitation_if_eligible(usman_loan_id)
    assert result is False, "Liberation Loan (no trade category) should NOT get an invitation"
    print("PASS -- Liberation Loan correctly did NOT trigger an invitation")

    conn.close()
    print("\nALL LIFECYCLE FUNCTIONS PASS.")


if __name__ == "__main__":
    main()
