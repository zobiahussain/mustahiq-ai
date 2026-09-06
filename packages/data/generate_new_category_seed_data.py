"""
Targeted top-up, round 2 -- now covering ALL 15 trade categories, not
just the 5 added later in the session.

WHY THIS RUN EXISTS: after round 1 (the 45-listing top-up for Handicrafts
/ Construction / Beauty / Repair / Education), the user asked a broader
question -- "for each category, what are the three working modes?" --
which surfaced that the ORIGINAL 10 categories had the exact same
problem, just less visibly: Manufacturing, Grocery, Food, and Trading
businesses had zero employment or joint_venture template coverage at
all, and Three-wheeler/rickshaw had no seeking-flag templates whatsoever
(a single bare logistics listing, nothing else). Those gaps were in
generate_seed_data.py's TEMPLATES from day one; a full re-run of that
generator was never triggered after they'd have been fixed, and even if
it had been, random sampling at typical per-category volume is exactly
what silently produced round 1's problem (Handicrafts drawing
seeking_work three times in a row, never seeking_workers).

So: TEMPLATES now has real coverage for every applicable mode in every
category (see the "for each category, what are the three working modes"
conversation -- Freelancing/technology and the base "supplier" role for
Beauty & Personal Care / Education & Tutoring are the only deliberate
omissions, since cross-category supply_chain matching already covers a
tutoring center's book supplier without needing an in-category one).
This script is that fix's live counterpart: run once across ALL 15
categories so every newly-added template variant gets a guaranteed real
counterpart in the database, not just a definition in the file.

WHY THIS DOESN'T JUST RE-RUN generate_seed_data.py
--------------------------------------------------------------------------
That would regenerate 500+ MORE beneficiaries across all 15 categories --
duplicating what's already there. This is still a targeted top-up: new
beneficiaries only, and DELIBERATELY CYCLING through every template
variant a fixed number of times each (not randomly sampling, which is
exactly what produced the all-seeking_work Handicrafts problem at small
sample sizes in round 1) -- so every seeking flag a template defines
gets a real counterpart on the other side, in every category this time,
not just the 5 that got attention first.

Phone prefix bumped to +9236 (round 1 used +9235) and the random seed to
45 (round 1 used 44) specifically so this run's rows land in a fresh,
non-colliding phone-number range and produce a different random draw --
same reasoning as round 1's own seed bump from 42/43.

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
random.seed(45)  # different from all three prior seeds (42, 43, 44) -- a fresh, non-repeating draw

NEW_CATEGORIES = [
    "Tailoring & embroidery",
    "Grocery / Karyana",
    "Livestock",
    "Manufacturing",
    "Services",
    "Beauty & Personal Care",
    "Construction & Home Trades",
    "Repair & Maintenance",
    "Education & Tutoring",
    "Food",
    "Three-wheeler / rickshaw",
    "Agriculture",
    "Freelancing / technology",
    "Trading businesses",
    "Handicrafts & Artisan Crafts",
]  # all 15 -- name kept as NEW_CATEGORIES so the loop below didn't need touching

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

    # +9236 prefix -- distinct from every other block used so far this
    # session (+923001234xxx hand-curated, +9234... bulk generator,
    # +9235... round-1 top-up, +923007/9... SKIP_ELIGIBILITY_CHECK test
    # rows) -- unambiguous to spot later, and avoids a phone-uniqueness
    # collision with round 1's rows.
    beneficiary_rows = []
    loan_rows = []
    for i, (name, is_male, district, cluster_id, category_name, template, business_name) in enumerate(plans):
        bid = str(uuid.uuid4())
        phone = f"+9236{2000000 + i:07d}"
        beneficiary_rows.append((bid, name, phone, district, cluster_id, True))

        lid = str(uuid.uuid4())
        loan_rows.append((
            # AK-CAT2- not AK-CAT- -- round 1 already claimed AK-CAT-20000
            # upward (loan_reference is unique); this run's numbering would
            # otherwise collide 1:1 since both scripts start counting at 0.
            lid, f"AK-CAT2-{20000 + i}", bid, "Small Business Loan",
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
    print(f"\nDone. {len(listing_rows)} new listings added across all {len(NEW_CATEGORIES)} categories, "
          f"with every seeking flag each category defines now having a real counterpart.")


if __name__ == "__main__":
    run()
