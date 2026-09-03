"""
Dummy data for the demo: beneficiaries, loans (mixed statuses/categories so
the eligibility gate has something real to test against), and existing
store listings (so a brand-new signup has something to match against
immediately, instead of an empty marketplace).

WHY PYTHON, NOT RAW SQL INSERT STATEMENTS
-------------------------------------------
Two of these tables need a 768-number embedding per row (store_listings),
computed from local text -- that's Python's job (packages/rag/embeddings.py),
not something a plain .sql file can do. Writing it all in one script keeps
the beneficiary/loan/listing relationships consistent (a listing's owner has
to actually be one of the seeded beneficiaries with a qualifying loan) in a
way that's easy to check by reading top to bottom.

HOW TO RUN
----------
Needs DATABASE_URL in .env (the Supabase connection string) and the
packages/rag venv active for the embeddings import.

    cd packages/data
    ../rag/.venv/Scripts/python.exe seed_data.py
"""

import os
import sys
import uuid
from datetime import date, timedelta

import psycopg2
from dotenv import load_dotenv

# reuse the embedding wrapper we already built and tested -- never
# reimplement this here, one source of truth for how text becomes a vector
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))
from embeddings import embed_text  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit(
        "DATABASE_URL not set in .env -- this is the Supabase connection "
        "string (Session pooler, URI format). See packages/rag conversation "
        "for exactly where to find it in the Supabase dashboard."
    )


# ---------------------------------------------------------------------------
# Beneficiaries -- kept minimal on purpose. Only the fields the marketplace
# gate and matching actually touch (name, phone, district). Real profiles
# have many more columns (household_size, monthly_income, ...) but those
# belong to the eligibility side, not this module.
# ---------------------------------------------------------------------------

BENEFICIARIES = [
    # (full_name, phone, district, cluster_id)
    ("Amina Bibi",      "+923001234567", "Lahore",     "LHR-01"),
    ("Fahad Hussain",   "+923001234568", "Lahore",     "LHR-01"),
    ("Zainab Sheikh",   "+923001234569", "Hyderabad",  "HYD-01"),
    ("Bilal Ahmed",     "+923001234570", "Sukkur",     "SKR-01"),
    ("Hina Yousaf",     "+923001234571", "Karachi",    "KHI-01"),
    ("Usman Tariq",     "+923001234572", "Faisalabad", "FSD-01"),
    ("Sara Iqbal",      "+923001234573", "Multan",     "MUL-01"),
    ("Kashif Raza",     "+923001234574", "Lahore",     "LHR-01"),
    ("Nadia Parveen",   "+923001234575", "Hyderabad",  "HYD-01"),
    ("Rashid Mehmood",  "+923001234576", "Karachi",    "KHI-01"),
]

# ---------------------------------------------------------------------------
# Loans -- deliberately covers every status and includes one Liberation
# Loan (trade_category = None), so the eligibility gate (packages/data/
# schema/al_khidmat_marketplace_schema.sql, reference query G) has a real
# mix to filter, not just the happy path.
# ---------------------------------------------------------------------------

# index into BENEFICIARIES, loan_product, trade_category name (None = not a business), status
LOANS = [
    (0, "Small Business Loan",        "Tailoring & embroidery",   "disbursed"),
    (1, "Income Generating Project",  "Grocery / Karyana",        "approved"),   # approved, not yet disbursed -- still eligible
    (2, "Small Business Loan",        "Livestock",                "disbursed"),
    (3, "Loan for Orphan's Mother",   "Manufacturing",             "disbursed"),
    (4, "Small Business Loan",        "Freelancing / technology", "approved"),
    (5, "Liberation Loan",            None,                        "disbursed"),  # no business -- can log in, no listing
    (6, "Income Generating Project",  "Food",                      "defaulted"),  # gate closed, any listing deactivated
    (7, "Small Business Loan",        "Three-wheeler / rickshaw",  "disbursed"),
    (8, "Loan for Orphan's Mother",   "Services",                  "rejected"),   # never eligible at all
    (9, "Small Business Loan",        "Agriculture",                "disbursed"),
]

# ---------------------------------------------------------------------------
# Store listings -- these are what a brand-new signup will actually see
# and match against. Deliberately spans multiple districts/clusters and
# all three matching models, and includes one remote-capable /
# non-physical-output pair (the freelancer) to prove that path works too.
# beneficiary_index refers to BENEFICIARIES above.
# ---------------------------------------------------------------------------

LISTINGS = [
    dict(
        beneficiary_index=0, business_name="Amina's Tailoring",
        trade_category="Tailoring & embroidery",
        role="producer", product_or_service_en="Tailoring and stitching -- shalwar "
        "kameez, school uniforms, garment production, custom clothing",
        product_or_service_original="سلائی، شلوار قمیض، یونیفارم",
        seeking_inputs=True, is_remote_capable=False, output_is_physical=True,
        will_deliver_outside_area=False, district="Lahore", cluster_id="LHR-01",
    ),
    dict(
        beneficiary_index=2, business_name="Zainab Leather Supplies",
        trade_category="Manufacturing",
        role="supplier", product_or_service_en="Leather supplier -- hides, "
        "finished leather, materials for shoemakers and garment producers",
        product_or_service_original="چمڑے کی سپلائی",
        seeking_partner=False, is_remote_capable=False, output_is_physical=True,
        will_deliver_outside_area=True, district="Hyderabad", cluster_id="HYD-01",
    ),
    dict(
        beneficiary_index=4, business_name=None,
        trade_category="Freelancing / technology",
        role="service", product_or_service_en="Freelance web development and "
        "software services -- websites, business software, technical consulting",
        product_or_service_original="ویب ڈویلپمنٹ",
        seeking_work=True, is_remote_capable=True, output_is_physical=False,
        district="Faisalabad", cluster_id="FSD-01",
    ),
    dict(
        beneficiary_index=7, business_name="Tariq Transport",
        trade_category="Three-wheeler / rickshaw",
        role="logistics", product_or_service_en="Three-wheeler rickshaw transport "
        "and small goods delivery between districts",
        product_or_service_original="رکشہ، سامان کی ترسیل",
        is_remote_capable=False, output_is_physical=True,
        will_deliver_outside_area=True, district="Faisalabad", cluster_id="FSD-01",
    ),
    dict(
        beneficiary_index=9, business_name="Rashid Grains",
        trade_category="Agriculture",
        role="producer", product_or_service_en="Agricultural produce -- wheat, "
        "rice, seasonal grains, farm-to-market trading",
        product_or_service_original="اناج، گندم، چاول",
        seeking_workers=True, is_remote_capable=False, output_is_physical=True,
        district="Karachi", cluster_id="KHI-01",
    ),
]


def run():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("seeding beneficiary_profiles...")
    beneficiary_ids = []
    for name, phone, district, cluster_id in BENEFICIARIES:
        bid = str(uuid.uuid4())
        cur.execute(
            """
            insert into beneficiary_profiles (id, full_name, phone, district, cluster_id, consent_given)
            values (%s, %s, %s, %s, %s, true)
            """,
            (bid, name, phone, district, cluster_id),
        )
        beneficiary_ids.append(bid)
    print(f"  {len(beneficiary_ids)} beneficiaries inserted.")

    print("seeding microfinance_loans...")
    cur.execute("select id, name from trade_categories")
    category_id_by_name = {name: cid for cid, name in cur.fetchall()}

    loan_ids = []
    for i, (b_idx, product, category_name, status) in enumerate(LOANS):
        lid = str(uuid.uuid4())
        category_id = category_id_by_name.get(category_name) if category_name else None
        disbursed_on = date.today() - timedelta(days=30) if status in ("disbursed", "defaulted") else None
        amount = 150000 if "Small Business" in product or "Income" in product else 100000
        cur.execute(
            """
            insert into microfinance_loans
                (id, loan_reference, beneficiary_id, loan_product, trade_category_id,
                 stated_purpose_text, status, amount_disbursed, disbursed_on)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                lid, f"AK-LOAN-{1000 + i}", beneficiary_ids[b_idx], product, category_id,
                f"Loan for {category_name or 'personal needs'}", status,
                amount if disbursed_on else None, disbursed_on,
            ),
        )
        loan_ids.append(lid)
    print(f"  {len(loan_ids)} loans inserted (statuses: "
          f"{', '.join(sorted(set(l[3] for l in LOANS)))}).")

    print("seeding store_listings (embedding each one -- this is the slow part)...")
    for listing in LISTINGS:
        b_idx = listing.pop("beneficiary_index")
        category_id = category_id_by_name[listing.pop("trade_category")]
        listing_id = str(uuid.uuid4())

        vector = embed_text(listing["product_or_service_en"])
        cur.execute(
            """
            insert into store_listings
                (id, primary_beneficiary_id, business_name, trade_category_id,
                 product_or_service_en, product_or_service_original, role,
                 seeking_inputs, seeking_workers, seeking_partner, seeking_work,
                 is_remote_capable, output_is_physical,
                 will_deliver_outside_area, will_relocate_for_work,
                 district, cluster_id, embedding)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                listing_id, beneficiary_ids[b_idx], listing.get("business_name"),
                category_id,
                listing["product_or_service_en"], listing["product_or_service_original"],
                listing["role"],
                listing.get("seeking_inputs", False), listing.get("seeking_workers", False),
                listing.get("seeking_partner", False), listing.get("seeking_work", False),
                listing["is_remote_capable"], listing["output_is_physical"],
                listing.get("will_deliver_outside_area", False),
                listing.get("will_relocate_for_work", False),
                listing["district"], listing["cluster_id"], vector,
            ),
        )

        # Matches what the real save_listing() does for every listing
        # created through the app -- an owner row in listing_participants.
        # Missing here originally; ventures.py's ownership check is what
        # surfaced it (a seeded listing had no recorded owner at all).
        cur.execute(
            "insert into listing_participants (listing_id, beneficiary_id, role, status) "
            "values (%s, %s, 'owner', 'confirmed')",
            (listing_id, beneficiary_ids[b_idx]),
        )
    print(f"  {len(LISTINGS)} listings inserted.")

    conn.commit()
    cur.close()
    conn.close()
    print("\nDone. Seed data is live in Supabase.")


if __name__ == "__main__":
    run()
