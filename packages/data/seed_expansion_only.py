"""
One-off: inserts ONLY the 20 new beneficiaries/loans/listings added to
seed_data.py on 4 Sep 2026 (indices 10-29), against a database that
already has the original 10 from an earlier run. seed_data.py itself has
no idempotency check, so re-running it wholesale would duplicate the
original 10 -- this script exists so today's expansion doesn't have to
risk that. A fresh run of seed_data.py against an EMPTY database still
seeds all 30 correctly in one go; this is purely a top-up for a database
that's already partially seeded.

Run: python seed_expansion_only.py
"""

import os
import sys
import uuid
from datetime import date, timedelta

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))
from embeddings import embed_text  # noqa: E402

from seed_data import BENEFICIARIES, LOANS, LISTINGS  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def run():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    new_beneficiaries = BENEFICIARIES[10:]
    new_loans = [row for row in LOANS if row[0] >= 10]
    new_listings = [d for d in LISTINGS if d["beneficiary_index"] >= 10]

    print(f"seeding {len(new_beneficiaries)} new beneficiary_profiles...")
    beneficiary_ids = {}  # index (10..29) -> id
    for offset, (name, phone, district, cluster_id) in enumerate(new_beneficiaries):
        idx = 10 + offset
        bid = str(uuid.uuid4())
        cur.execute(
            "insert into beneficiary_profiles (id, full_name, phone, district, cluster_id, consent_given) "
            "values (%s, %s, %s, %s, %s, true)",
            (bid, name, phone, district, cluster_id),
        )
        beneficiary_ids[idx] = bid

    print(f"seeding {len(new_loans)} new microfinance_loans...")
    cur.execute("select id, name from trade_categories")
    category_id_by_name = {name: cid for cid, name in cur.fetchall()}

    for i, (b_idx, product, category_name, status) in enumerate(new_loans):
        lid = str(uuid.uuid4())
        category_id = category_id_by_name.get(category_name) if category_name else None
        disbursed_on = date.today() - timedelta(days=30) if status in ("disbursed", "defaulted") else None
        amount = 150000 if "Small Business" in product or "Income" in product else 100000
        cur.execute(
            "insert into microfinance_loans "
            "(id, loan_reference, beneficiary_id, loan_product, trade_category_id, "
            " stated_purpose_text, status, amount_disbursed, disbursed_on) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                lid, f"AK-LOAN-{2000 + i}", beneficiary_ids[b_idx], product, category_id,
                f"Loan for {category_name or 'personal needs'}", status,
                amount if disbursed_on else None, disbursed_on,
            ),
        )

    print(f"seeding {len(new_listings)} new store_listings (embedding each one)...")
    for listing in new_listings:
        listing = dict(listing)  # don't mutate the shared LISTINGS list
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
                 will_deliver_outside_area, will_relocate_for_work, will_partner_outside_district,
                 district, cluster_id, embedding)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                listing.get("will_partner_outside_district", False),
                listing["district"], listing["cluster_id"], vector,
            ),
        )
        cur.execute(
            "insert into listing_participants (listing_id, beneficiary_id, role, status) "
            "values (%s, %s, 'owner', 'confirmed')",
            (listing_id, beneficiary_ids[b_idx]),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("\nDone. Expansion seed data is live.")


if __name__ == "__main__":
    run()
