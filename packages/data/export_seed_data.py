"""
Exports the live database's beneficiaries/loans/listings to CSV, for
eyeballing in Excel -- not for re-import, just for review. Joins in
readable names (trade category, not trade_category_id) rather than
raw UUIDs wherever a human would otherwise have to cross-reference
another table by hand.

Run:
    cd packages/data
    ../rag/.venv/Scripts/python.exe export_seed_data.py
Writes to packages/data/exports/ (gitignored -- this is a point-in-time
snapshot for review, not something that belongs in version control).
"""

import csv
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

OUT_DIR = os.path.join(os.path.dirname(__file__), "exports")


def _write_csv(path: str, rows: list[dict]) -> None:
    if not rows:
        print(f"  (nothing to write for {path})")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: Excel needs the BOM to render Urdu correctly
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {len(rows)} rows -> {path}")


def run():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    print("exporting beneficiaries...")
    cur.execute(
        """
        select bp.id, bp.full_name, bp.phone, bp.district, bp.cluster_id,
               ml.loan_reference, ml.loan_product, tc.name as trade_category,
               ml.status as loan_status, ml.amount_disbursed, ml.disbursed_on
        from beneficiary_profiles bp
        left join microfinance_loans ml on ml.beneficiary_id = bp.id
        left join trade_categories tc on tc.id = ml.trade_category_id
        order by bp.full_name
        """
    )
    _write_csv(os.path.join(OUT_DIR, "beneficiaries_and_loans.csv"), cur.fetchall())

    print("exporting listings...")
    cur.execute(
        """
        select sl.id, sl.business_name, bp.full_name as owner_name, bp.phone as owner_phone,
               tc.name as trade_category, sl.role,
               sl.seeking_inputs, sl.seeking_workers, sl.seeking_partner, sl.seeking_work,
               sl.is_remote_capable, sl.output_is_physical,
               sl.will_deliver_outside_area, sl.will_relocate_for_work, sl.will_partner_outside_district,
               sl.is_women_led, sl.availability, sl.district, sl.cluster_id,
               sl.product_or_service_en, sl.product_or_service_original,
               sl.open_request_count, sl.active, sl.created_at
        from store_listings sl
        left join beneficiary_profiles bp on bp.id = sl.primary_beneficiary_id
        left join trade_categories tc on tc.id = sl.trade_category_id
        order by sl.created_at desc
        """
    )
    _write_csv(os.path.join(OUT_DIR, "listings.csv"), cur.fetchall())

    print("exporting matches...")
    cur.execute(
        """
        select mm.id, mm.match_model, mm.status,
               la.business_name as listing_a, lb.business_name as listing_b,
               mm.similarity_score, mm.proximity_multiplier, mm.final_score,
               mm.proximity_label, mm.reason, mm.created_at, mm.expires_at
        from marketplace_matches mm
        join store_listings la on la.id = mm.listing_a_id
        join store_listings lb on lb.id = mm.listing_b_id
        order by mm.created_at desc
        """
    )
    _write_csv(os.path.join(OUT_DIR, "matches.csv"), cur.fetchall())

    cur.close()
    conn.close()
    print(f"\nDone. Open the .csv files in {OUT_DIR} with Excel.")


if __name__ == "__main__":
    run()
