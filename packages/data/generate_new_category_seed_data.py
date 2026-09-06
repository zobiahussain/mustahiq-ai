"""
Targeted top-up for the 5 categories added later in the session
(Handicrafts & Artisan Crafts, Construction & Home Trades, Beauty &
Personal Care, Repair & Maintenance, Education & Tutoring) -- confirmed
live: real listings existed in some of these (from reclassifying
"Services"), but adding the new categories to generate_seed_data.py's
TEMPLATES never actually ran a generation pass, so nobody NEW was ever
created there. Worse: the 3 listings that existed in Handicrafts (from
manual reclassification) all happened to be seeking_work -- zero
seeking_workers counterparts, so employment matching there was
structurally impossible, not just low-quality. Repair & Maintenance had
ZERO listings at all.

WHY THIS DOESN'T JUST RE-RUN generate_seed_data.py
--------------------------------------------------------------------------
That would regenerate 500+ MORE beneficiaries across all 15 categories --
duplicating what's already there. This is a small, targeted top-up:
new beneficiaries, but ONLY for these 5 categories, and DELIBERATELY
CYCLING through every template variant at least twice each (not
randomly sampling, which is exactly what produced the all-seeking_work
Handicrafts problem at small sample sizes) -- so every seeking flag a
template defines gets a real counterpart on the other side.

Run:
    cd packages/data
    ../rag/.venv/Scripts/python.exe generate_new_category_seed_data.py
"""

import os
import sys
import uuid
from datetime import date, timedelta

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))
from embeddings import embed_texts  # noqa: E402

from generate_seed_data import (  # noqa: E402
    TEMPLATES, SPECIALTY_SUFFIXES, DISTRICTS,
    FIRST_NAMES_MALE, FIRST_NAMES_FEMALE, LAST_NAMES,
    _generate_business_name,
)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

import random
random.seed(44)  # different from both prior seeds (42, 43) -- a fresh, non-repeating draw

NEW_CATEGORIES = [
    "Handicrafts & Artisan Crafts",
    "Construction & Home Trades",
    "Beauty & Personal Care",
    "Repair & Maintenance",
    "Education & Tutoring",
]

REPEATS_PER_TEMPLATE = 3  # each template variant gets created this many times,
                          # cycled deterministically -- guarantees every seeking
                          # flag a category defines has real counterparts, not
                          # a random draw that can (and did) miss one side entirely


def run():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute("select id, name from trade_categories")
    category_id_by_name = {name: cid for cid, name in cur.fetchall()}

    plans = []  # (name, is_male, district, cluster_id, category_name, template, business_name)
    for category_name in NEW_CATEGORIES:
        templates = TEMPLATES[category_name]
        for template in templates:
            for _ in range(REPEATS_PER_TEMPLATE):
                is_male = random.random() < 0.55
                first = random.choice(FIRST_NAMES_MALE if is_male else FIRST_NAMES_FEMALE)
                last = random.choice(LAST_NAMES)
                name = f"{first} {last}"
                district, cluster_id = random.choice(DISTRICTS)
                business_name = _generate_business_name(name, category_name)
                plans.append((name, is_male, district, cluster_id, category_name, template, business_name))

    print(f"generating {len(plans)} new beneficiaries/loans/listings across {len(NEW_CATEGORIES)} categories...")

    # +9235 prefix -- distinct from every other block used so far this
    # session (+923001234xxx hand-curated, +9234... bulk generator,
    # +923007/9... SKIP_ELIGIBILITY_CHECK test rows) -- unambiguous to
    # spot later.
    beneficiary_rows = []
    loan_rows = []
    for i, (name, is_male, district, cluster_id, category_name, template, business_name) in enumerate(plans):
        bid = str(uuid.uuid4())
        phone = f"+9235{2000000 + i:07d}"
        beneficiary_rows.append((bid, name, phone, district, cluster_id, True))

        lid = str(uuid.uuid4())
        loan_rows.append((
            lid, f"AK-CAT-{20000 + i}", bid, "Small Business Loan",
            category_id_by_name[category_name],
            f"Loan for {category_name}", "disbursed", 150000,
            date.today() - timedelta(days=random.randint(15, 300)),
        ))

    psycopg2.extras.execute_values(
        cur,
        "insert into beneficiary_profiles (id, full_name, phone, district, cluster_id, consent_given) values %s",
        beneficiary_rows,
    )
    psycopg2.extras.execute_values(
        cur,
        "insert into microfinance_loans "
        "(id, loan_reference, beneficiary_id, loan_product, trade_category_id, "
        " stated_purpose_text, status, amount_disbursed, disbursed_on) values %s",
        loan_rows,
    )
    print(f"  {len(beneficiary_rows)} beneficiaries + loans inserted (all disbursed, real category, real listing follows for each).")

    # Every one of these beneficiaries gets a listing -- unlike the main
    # generator's LISTING_CREATION_RATE, 100% here on purpose: the whole
    # point of this top-up is guaranteeing real counterparts exist, not
    # modelling realistic adoption (generate_seed_data.py already does that).
    en_texts, ur_texts = [], []
    for name, is_male, district, cluster_id, category_name, template, business_name in plans:
        i = random.randrange(len(template["en"]))
        en_text, ur_text = template["en"][i], template["ur"][i]
        if category_name in SPECIALTY_SUFFIXES and random.random() < 0.85:
            en_suffix, ur_suffix = random.choice(SPECIALTY_SUFFIXES[category_name])
            en_text = f"{en_text} -- {en_suffix}"
            ur_text = f"{ur_text}، {ur_suffix}"
        en_texts.append(en_text)
        ur_texts.append(ur_text)

    print("embedding descriptions in batches...")
    BATCH = 100
    vectors = []
    for start in range(0, len(en_texts), BATCH):
        vectors.extend(embed_texts(en_texts[start:start + BATCH]))
        print(f"    embedded {min(start + BATCH, len(en_texts))}/{len(en_texts)}")

    listing_rows, participant_rows = [], []
    for (bid, *_rest_b), (lid, *_rest_l), (name, is_male, district, cluster_id, category_name, template, business_name), en_text, ur_text, vector in zip(
        beneficiary_rows, loan_rows, plans, en_texts, ur_texts, vectors
    ):
        listing_id = str(uuid.uuid4())
        seeking = template["seeking"]
        travel_flag = template.get("travel")
        listing_rows.append((
            listing_id, bid, business_name, category_id_by_name[category_name],
            en_text, ur_text, None,
            template["role"],
            seeking.get("seeking_inputs", False), seeking.get("seeking_workers", False),
            seeking.get("seeking_partner", False), seeking.get("seeking_work", False),
            template["remote"], template["physical"],
            travel_flag == "will_deliver_outside_area",
            travel_flag == "will_relocate_for_work",
            travel_flag == "will_partner_outside_district",
            not is_male,
            district, cluster_id, vector,
        ))
        participant_rows.append((listing_id, bid, "owner", "confirmed"))

    print("inserting listings...")
    psycopg2.extras.execute_values(
        cur,
        """
        insert into store_listings
            (id, primary_beneficiary_id, business_name, trade_category_id,
             product_or_service_en, product_or_service_original, skills_en,
             role, seeking_inputs, seeking_workers, seeking_partner, seeking_work,
             is_remote_capable, output_is_physical,
             will_deliver_outside_area, will_relocate_for_work, will_partner_outside_district,
             is_women_led, district, cluster_id, embedding)
        values %s
        """,
        listing_rows,
    )
    psycopg2.extras.execute_values(
        cur,
        "insert into listing_participants (listing_id, beneficiary_id, role, status) values %s",
        participant_rows,
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. {len(listing_rows)} new listings added across the 5 newer categories, "
          f"with every seeking flag each category defines now having a real counterpart.")


if __name__ == "__main__":
    run()
