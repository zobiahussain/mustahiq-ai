"""
The fixed cast of login accounts for a live demo of the marketplace app.

WHY A SEPARATE SCRIPT FROM generate_seed_data.py
--------------------------------------------------------------------------
generate_seed_data.py builds the *population* -- ~2,000 beneficiaries and
~1,750 listings for matching to have real breadth. This script builds the
*people you actually log in as on stage*: a small, memorised set of phone
numbers, one per trade category, in the two densest seed clusters, each
with a real microfinance_loans row (so they pass the eligibility gate with
SKIP_ELIGIBILITY_CHECK=false) and -- deliberately -- NO listing yet, so the
demo is "log in, create a listing, watch matching run," not "look at a
listing someone already made."

The full reference (which number, which category, what to describe) is in
docs/Demo_Accounts.md -- keep the two in sync if you edit the list here.

RE-RUNNABLE: clears its own rows (phone prefix +9231111) and recreates them.
Reuses create_test_customer.create_customer() -- one place that knows how to
insert a valid beneficiary+loan, same as import_test_customers.py.

Run:
    cd packages/data
    ../rag/.venv/Scripts/python.exe seed_demo_accounts.py
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from create_test_customer import create_customer  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "marketplace"))
from proximity import cluster_for  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

DEMO_PHONE_PREFIX = "+9231111"

# (phone, display name, district, trade category, loan status)
# "" category = a Liberation-Loan-style row: can log in, never offered
# listing creation (can_create_listing = false).
DEMO_ACCOUNTS = [
    # ---- Lahore / LHR-01 -- one per trade category (all 15) ----
    ("+923111100001", "Demo Traders",      "Lahore",  "Trading businesses",           "disbursed"),
    ("+923111100002", "Demo Karyana",      "Lahore",  "Grocery / Karyana",            "disbursed"),
    ("+923111100003", "Demo Tailor",       "Lahore",  "Tailoring & embroidery",       "approved"),
    ("+923111100004", "Demo Dairy",        "Lahore",  "Livestock",                    "disbursed"),
    ("+923111100005", "Demo Sportswear",   "Lahore",  "Manufacturing",                "disbursed"),
    ("+923111100006", "Demo Laundry",      "Lahore",  "Services",                     "disbursed"),
    ("+923111100007", "Demo Bakery",       "Lahore",  "Food",                         "disbursed"),
    ("+923111100008", "Demo Rickshaw",     "Lahore",  "Three-wheeler / rickshaw",     "disbursed"),
    ("+923111100009", "Demo Farm",         "Lahore",  "Agriculture",                  "approved"),
    ("+923111100010", "Demo WebStudio",    "Lahore",  "Freelancing / technology",     "disbursed"),
    ("+923111100011", "Demo Jewellery",    "Lahore",  "Handicrafts & Artisan Crafts", "disbursed"),
    ("+923111100012", "Demo Electrician",  "Lahore",  "Construction & Home Trades",   "disbursed"),
    ("+923111100013", "Demo Salon",        "Lahore",  "Beauty & Personal Care",       "disbursed"),
    ("+923111100014", "Demo PhoneRepair",  "Lahore",  "Repair & Maintenance",         "disbursed"),
    ("+923111100015", "Demo Tutor",        "Lahore",  "Education & Tutoring",          "disbursed"),
    # ---- Karachi / KHI-01 -- a second cluster, for cross-city / proximity demos ----
    ("+923111102001", "Demo KHI Tailor",     "Karachi", "Tailoring & embroidery",       "approved"),
    ("+923111102002", "Demo KHI Jewellery",  "Karachi", "Handicrafts & Artisan Crafts", "disbursed"),
    ("+923111102003", "Demo KHI Bakery",     "Karachi", "Food",                         "disbursed"),
    ("+923111102004", "Demo KHI Manufact",   "Karachi", "Manufacturing",                "disbursed"),
    ("+923111102005", "Demo KHI Livestock",  "Karachi", "Livestock",                    "disbursed"),
    ("+923111102006", "Demo KHI Salon",      "Karachi", "Beauty & Personal Care",       "disbursed"),
    # ---- edge case: logs in, but never offered listing creation ----
    ("+923111109001", "Demo Liberation",     "Lahore",  "",                             "disbursed"),
]


def _clear_previous(cur):
    cur.execute("select id from beneficiary_profiles where phone like %s", (DEMO_PHONE_PREFIX + "%",))
    ids = [r[0] for r in cur.fetchall()]
    if not ids:
        return
    cur.execute("select id from store_listings where primary_beneficiary_id = any(%s::uuid[])", (ids,))
    lids = [r[0] for r in cur.fetchall()]
    if lids:
        cur.execute("delete from marketplace_matches where listing_a_id = any(%s::uuid[]) or listing_b_id = any(%s::uuid[])", (lids, lids))
        cur.execute("update marketplace_matches set suggested_logistics_id = null where suggested_logistics_id = any(%s::uuid[])", (lids,))
        cur.execute("update marketplace_matches set dismissed_by_listing_id = null where dismissed_by_listing_id = any(%s::uuid[])", (lids,))
    cur.execute("delete from match_messages where sender_beneficiary_id = any(%s::uuid[])", (ids,))
    cur.execute("delete from beneficiary_profiles where id = any(%s::uuid[])", (ids,))
    print(f"  cleared {len(ids)} previous demo account(s)")


def run():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    _clear_previous(cur)
    for phone, name, district, category, status in DEMO_ACCOUNTS:
        create_customer(cur, phone, name, district, cluster_for(district),
                        category or None, status)
        print(f"  {phone}  {name:20s}  {district:8s}  {category or '(no category)':28s}  {status}")
    conn.commit()
    cur.close()
    conn.close()
    print(f"\n{len(DEMO_ACCOUNTS)} demo accounts ready. See docs/Demo_Accounts.md.")


if __name__ == "__main__":
    run()
