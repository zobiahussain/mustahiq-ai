"""
Creates ONE real beneficiary + microfinance_loans row, standing in for
what a loan officer enters at a facilitation centre -- since
services/api has no POST /profile yet (that's the eligibility side's
endpoint, someone else's to build, not implemented anywhere in this
repo today). This is the ONLY way to get a "real" customer into the
system for testing right now, as opposed to SKIP_ELIGIBILITY_CHECK's
auto-provisioned test rows.

WHY THIS MATTERS FOR TESTING THE REAL (NOT BYPASSED) GATE
--------------------------------------------------------------------------
With SKIP_ELIGIBILITY_CHECK=true in .env, ANY phone number logs in --
useful for fast iteration, but it means you're never actually exercising
Marketplace_Spec.md section 2's real eligibility check (does a
microfinance_loans row exist, with status approved/disbursed, with a
trade_category_id set). To test THAT for real -- and to test the
loan-approved/loan-repaid WEBHOOKS as something that fires off a genuine
new loan record, the way Al-Khidmat's own loan system would trigger
them -- you need a real row to test against. This script makes one.

WHAT THIS DOES NOT DO
--------------------------
Does not touch SKIP_ELIGIBILITY_CHECK -- that's still whatever .env says.
Set it to false first if you want to prove the REAL gate rejects numbers
NOT created this way (see "Testing the real gate" below).

USAGE
-----
    cd packages/data
    ../rag/.venv/Scripts/python.exe create_test_customer.py \\
        --phone "+923005559999" \\
        --name "Rukhsana Bibi" \\
        --district "Multan" \\
        --category "Tailoring & embroidery" \\
        --status approved

    # or just answer the prompts:
    ../rag/.venv/Scripts/python.exe create_test_customer.py

--status defaults to "approved" (Marketplace_Spec.md section 2: eligible
from approval, doesn't need to wait for disbursement). Pass
--status disbursed / defaulted / rejected to test other gate outcomes,
or --category "" (empty) to simulate a Liberation-Loan-style loan with no
business (can log in, never offered listing creation).

Prints the new loan_id at the end -- copy it straight into the webhook
test commands this script also prints, to watch
POST /webhooks/loan-approved actually fire the marketplace_invitations
SMS for a loan you JUST created, live.
"""

import argparse
import os
import sys
import uuid
from datetime import date

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

VALID_STATUSES = ("approved", "disbursed", "defaulted", "rejected")


def run(phone: str, full_name: str, district: str, cluster_id: str, category: str | None, status: str):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute("select id from beneficiary_profiles where phone = %s", (phone,))
    if cur.fetchone():
        print(f"A beneficiary with phone {phone} already exists -- pick a different number, "
              "or look it up directly if you meant to reuse it.")
        cur.close()
        conn.close()
        sys.exit(1)

    category_id = None
    if category:
        cur.execute("select id from trade_categories where name = %s", (category,))
        row = cur.fetchone()
        if row is None:
            print(f"'{category}' isn't one of the 10 real trade categories -- "
                  "see packages/data/reference_lists.md for the exact names.")
            cur.close()
            conn.close()
            sys.exit(1)
        category_id = row[0]

    beneficiary_id = str(uuid.uuid4())
    cur.execute(
        "insert into beneficiary_profiles (id, full_name, phone, district, cluster_id, consent_given) "
        "values (%s, %s, %s, %s, %s, true)",
        (beneficiary_id, full_name, phone, district, cluster_id),
    )

    loan_id = str(uuid.uuid4())
    disbursed_on = date.today() if status in ("disbursed", "defaulted") else None
    amount = 150000 if disbursed_on else None
    cur.execute(
        "insert into microfinance_loans "
        "(id, loan_reference, beneficiary_id, loan_product, trade_category_id, "
        " stated_purpose_text, status, amount_disbursed, disbursed_on) "
        "values (%s, %s, %s, 'Small Business Loan', %s, %s, %s, %s, %s)",
        (
            loan_id, f"AK-MANUAL-{loan_id[:8]}", beneficiary_id, category_id,
            f"Loan for {category or 'personal needs'}", status, amount, disbursed_on,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()

    print(f"\nCreated beneficiary {beneficiary_id}")
    print(f"Created loan {loan_id} (status={status}, category={category or 'none -- no business'})")
    print(f"\n--- Test the real (non-bypassed) login gate ---")
    print(f"Set SKIP_ELIGIBILITY_CHECK=false in .env, restart the API server, then log in with:")
    print(f"  phone: {phone}")
    if status not in ("approved", "disbursed") or category_id is None:
        print(f"  (this one is EXPECTED to fail the gate -- status={status}, "
              f"category={'set' if category_id else 'none'})")

    key = os.environ.get("INTERNAL_API_KEY", "<INTERNAL_API_KEY from .env>")
    print(f"\n--- Test the loan-approved webhook (marketplace_invitations SMS) LIVE ---")
    print(f"With the API server running (port 8000 or wherever yours is):")
    print(f'  curl -X POST http://localhost:8000/webhooks/loan-approved \\')
    print(f'    -H "X-Internal-Key: {key}" -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"loan_id": "{loan_id}"}}\'')
    print(f"Watch the server's terminal -- a real marketplace_invitations row gets written, "
          f"and the (stand-in) SMS print shows the invitation code for {phone}.")

    if status == "disbursed":
        print(f"\n--- Test the loan-repaid webhook (zakat graduation trigger) LIVE ---")
        print(f'  curl -X POST http://localhost:8000/webhooks/loan-repaid \\')
        print(f'    -H "X-Internal-Key: {key}" -H "Content-Type: application/json" \\')
        print(f'    -d \'{{"loan_id": "{loan_id}"}}\'')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phone", help="e.g. +923005559999")
    parser.add_argument("--name", help="full name")
    parser.add_argument("--district", help="e.g. Multan -- see packages/marketplace/proximity.py for the full list")
    parser.add_argument("--cluster", help="defaults to first-3-letters-of-district + '-01' if omitted")
    parser.add_argument("--category", help="one of the 10 real trade categories, or empty string for 'not a business'")
    parser.add_argument("--status", choices=VALID_STATUSES, default="approved")
    args = parser.parse_args()

    phone = args.phone or input("Phone (e.g. +923005559999): ").strip()
    full_name = args.name or input("Full name: ").strip()
    district = args.district or input("District (e.g. Multan): ").strip()
    cluster_id = args.cluster or f"{district[:3].upper()}-01"
    category = args.category if args.category is not None else input(
        "Trade category (one of the 10 real names, or blank for 'not a business'): "
    ).strip()
    status = args.status

    run(phone, full_name, district, cluster_id, category or None, status)


if __name__ == "__main__":
    main()
