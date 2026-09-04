"""
Bulk version of create_test_customer.py -- fill in
test_customers_template.csv (open it in Excel, keep the header row, add
one row per test customer), then run this to create all of them in one
go. Same underlying logic as the single-customer script (imports
create_customer() from it directly, doesn't duplicate it) -- this file
is just the "read a spreadsheet, loop over rows" part.

CSV COLUMNS (must match the header row exactly)
--------------------------------------------------
phone           required. e.g. +923005550001
full_name       required.
district        required. e.g. Multan -- see packages/marketplace/
                proximity.py's PROVINCE_BY_DISTRICT for the full list.
trade_category  one of the 10 real names (packages/data/reference_lists.md),
                or leave BLANK to simulate a Liberation-Loan-style loan
                with no business.
status          approved / disbursed / defaulted / rejected. Blank
                defaults to "approved" (Marketplace_Spec.md section 2:
                eligible from approval, no need to wait for disbursement).

ONE BAD ROW DOES NOT STOP THE OTHERS
--------------------------------------------
Unlike create_test_customer.py's CLI (one customer, fails loudly), this
reports EVERY row's outcome at the end and keeps going past a bad one
(duplicate phone, typo'd category) -- a spreadsheet with 20 rows
shouldn't lose the other 19 because row 7 had a typo. Committed
per-row, not one giant transaction, for the same reason: rows before a
failure stay created.

USAGE
-----
    cd packages/data
    ../rag/.venv/Scripts/python.exe import_test_customers.py
    # or point at a different file:
    ../rag/.venv/Scripts/python.exe import_test_customers.py my_customers.csv
"""

import csv
import os
import sys

import psycopg2
from dotenv import load_dotenv

from create_test_customer import create_customer, VALID_STATUSES

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "test_customers_template.csv")


def run(csv_path: str):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"{csv_path} has no data rows (just a header, or empty).")
        return

    # ONE connection, reused for every row -- see create_customer()'s
    # docstring for why that matters on this project's database
    # specifically (a fresh connection here costs real seconds, not
    # milliseconds).
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    created, skipped = [], []
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        phone = (row.get("phone") or "").strip()
        full_name = (row.get("full_name") or "").strip()
        district = (row.get("district") or "").strip()
        category = (row.get("trade_category") or "").strip() or None
        status = (row.get("status") or "approved").strip() or "approved"
        cluster_id = f"{district[:3].upper()}-01" if district else ""

        if not phone or not full_name or not district:
            skipped.append((i, phone or "(blank)", "missing phone/full_name/district"))
            continue
        if status not in VALID_STATUSES:
            skipped.append((i, phone, f"invalid status '{status}' -- must be one of {VALID_STATUSES}"))
            continue

        try:
            beneficiary_id, loan_id = create_customer(cur, phone, full_name, district, cluster_id, category, status)
            conn.commit()
            created.append((phone, full_name, loan_id))
        except ValueError as e:
            conn.rollback()
            skipped.append((i, phone, str(e)))

    cur.close()
    conn.close()

    print(f"\n{len(created)} customer(s) created:")
    for phone, full_name, loan_id in created:
        print(f"  {phone}  {full_name}  loan_id={loan_id}")

    if skipped:
        print(f"\n{len(skipped)} row(s) skipped:")
        for row_num, phone, reason in skipped:
            print(f"  row {row_num} ({phone}): {reason}")

    print(f"\nSee create_test_customer.py's own printed output (or docs/Local_Setup_And_Testing.md) "
          f"for how to test the login gate and fire the loan-approved/loan-repaid webhooks against "
          f"any of the loan_ids above.")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    if not os.path.exists(csv_path):
        print(f"{csv_path} not found.")
        sys.exit(1)
    run(csv_path)
