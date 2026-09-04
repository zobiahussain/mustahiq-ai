"""
Generates a large, realistic-scale seed dataset -- 500 beneficiaries, 500
loans, and a realistic subset of listings -- ADDED ON TOP of whatever
seed_data.py already put in the database. Same additive precedent as
seed_expansion_only.py (never touches or deletes existing rows).

WHY A GENERATOR, NOT MORE HAND-WRITTEN ROWS LIKE seed_data.py
--------------------------------------------------------------------------
seed_data.py's 30 beneficiaries/25 listings are hand-written on purpose --
small enough that every row is deliberate (a specific matching scenario,
a specific gate case). 500 rows is a different kind of data: not "a few
scenarios to prove each code path works," but volume to test against --
realistic distribution across categories/roles/districts, and enough
listings that search/matching/proximity-weighting have real breadth to
show. Hand-writing 500 rows isn't authorship, it's just typing -- a
generator is the actually-correct engineering answer here (this is
"synthetic data generation via templates," the same concept
packages/eligibility's XGBoost training data uses, just simpler). Kept as
a SEPARATE file from seed_data.py rather than folding the two together,
since they're doing genuinely different jobs.

WHY NOT EVERY BENEFICIARY GETS A LISTING
--------------------------------------------
Marketplace_Spec.md section 2 is explicit: joining the marketplace is
voluntary, once approved -- not automatic. Giving all 500 a listing would
misrepresent real adoption. LISTING_CREATION_RATE below controls what
fraction of ELIGIBLE beneficiaries (approved/disbursed status, a real
trade category) actually created one -- everyone else is exactly what
they'd be in real life: eligible, invited (marketplace_invitations would
fire for them in the real flow), but hasn't gotten around to it yet.

PERFORMANCE -- TWO THINGS DONE DIFFERENTLY FROM seed_data.py, BOTH TIED
TO THE SAME NETWORK-LATENCY FINDING FROM TONIGHT'S OPTIMIZATION PASS
--------------------------------------------------------------------------
1. embed_texts() (BATCHED) instead of embed_text() in a loop -- the model
   itself processes many texts together faster than one at a time
   (embeddings.py's own docstring already said so; this is the first
   place in the codebase that actually needed enough volume for it to
   matter).
2. psycopg2.extras.execute_values() for bulk inserts instead of one
   INSERT per row in a Python loop -- collapses hundreds of individual
   network round-trips into a handful of batched ones. This matters a
   lot more here than it would on a fast local DB: earlier tonight we
   measured this project's DATABASE_URL (Supabase's direct/IPv6 host)
   at ~9.6s just to ESTABLISH a connection on this network, and every
   individual query on top of that pays real round-trip latency too --
   500 one-row-at-a-time INSERTs the old way would be painfully slow.
   One connection, a handful of batched statements, done.

Run:
    cd packages/data
    ../rag/.venv/Scripts/python.exe generate_seed_data.py
"""

import os
import random
import sys
import uuid
from datetime import date, timedelta

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))
from embeddings import embed_texts  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "marketplace"))
from proximity import PROVINCE_BY_DISTRICT  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

random.seed(42)  # reproducible -- rerunning this script (against an
                  # empty table) should generate the same dataset, not a
                  # new random one each time, so results are comparable
                  # across a demo dry-run and the real thing.

N_BENEFICIARIES = 500
LISTING_CREATION_RATE = 0.75  # see file docstring

# ---------------------------------------------------------------------------
# Name pools -- enough combinations (60 first x 50 last = 3000) that 500
# beneficiaries won't produce awkward exact-duplicate full names.
# ---------------------------------------------------------------------------

FIRST_NAMES_MALE = [
    "Ahmed", "Ali", "Asif", "Bilal", "Danish", "Faisal", "Farhan", "Hamza",
    "Hassan", "Imran", "Irfan", "Javed", "Kamran", "Khalid", "Mohsin",
    "Naveed", "Nasir", "Owais", "Qasim", "Rashid", "Rizwan", "Saad",
    "Sajid", "Salman", "Shahzad", "Tariq", "Usman", "Waqas", "Yasir",
    "Zeeshan", "Adeel", "Arslan", "Fahad", "Junaid", "Kashif", "Maqsood",
]
FIRST_NAMES_FEMALE = [
    "Amina", "Ayesha", "Bushra", "Farah", "Farhana", "Hina", "Kiran",
    "Mehwish", "Nadia", "Naseem", "Nasreen", "Rabia", "Robina", "Rubina",
    "Saba", "Sadia", "Samina", "Sana", "Sania", "Sara", "Shabana",
    "Shazia", "Sumaira", "Tahira", "Uzma", "Zainab", "Zara", "Zubaida",
    "Asma", "Fatima",
]
LAST_NAMES = [
    "Ahmed", "Akhtar", "Ali", "Baig", "Butt", "Chaudhry", "Farooq",
    "Hussain", "Iqbal", "Jamil", "Javed", "Kausar", "Khan", "Malik",
    "Mehmood", "Naz", "Parveen", "Qureshi", "Raza", "Rehman", "Riaz",
    "Sarwar", "Shah", "Sheikh", "Siddiqui", "Tariq", "Yousaf", "Yousuf",
    "Zaman", "Zafar",
]

# ---------------------------------------------------------------------------
# Districts -- spread across all four provinces + ICT, so proximity
# weighting (same cluster / adjacent / same province / elsewhere) has
# real variety at 500-beneficiary scale, not just the original 7. One
# cluster per district ("XXX-01"), same convention seed_data.py already
# established -- Al-Khidmat's real 53-cluster map isn't this module's to
# invent (Data Engineering's territory), so this stays a simplification,
# same as seed_data.py's.
# ---------------------------------------------------------------------------

DISTRICTS = [
    # (district, cluster_id) -- Punjab
    ("Lahore", "LHR-01"), ("Faisalabad", "FSD-01"), ("Multan", "MUL-01"),
    ("Rawalpindi", "RWP-01"), ("Gujranwala", "GRW-01"), ("Sialkot", "SLK-01"),
    ("Bahawalpur", "BWP-01"), ("Sargodha", "SGD-01"), ("Sheikhupura", "SKP-01"),
    ("Rahim Yar Khan", "RYK-01"), ("Jhang", "JHG-01"), ("Sahiwal", "SWL-01"),
    ("Okara", "OKR-01"), ("Kasur", "KSR-01"), ("Gujrat", "GJT-01"),
    # Sindh
    ("Karachi", "KHI-01"), ("Hyderabad", "HYD-01"), ("Sukkur", "SKR-01"),
    ("Larkana", "LRK-01"), ("Mirpur Khas", "MPK-01"), ("Shaheed Benazirabad", "SBA-01"),
    ("Jacobabad", "JCB-01"), ("Khairpur", "KRP-01"), ("Dadu", "DAD-01"),
    # Khyber Pakhtunkhwa
    ("Peshawar", "PSH-01"), ("Mardan", "MDN-01"), ("Abbottabad", "ABT-01"),
    ("Swat", "SWT-01"), ("Kohat", "KHT-01"), ("Bannu", "BAN-01"),
    ("Dera Ismail Khan", "DIK-01"), ("Mansehra", "MAN-01"),
    # Balochistan
    ("Quetta", "QTA-01"), ("Gwadar", "GWD-01"), ("Sibi", "SIB-01"),
    ("Khuzdar", "KHZ-01"), ("Kech", "KEC-01"),
    # Islamabad Capital Territory
    ("Islamabad", "ISB-01"),
    # Azad Jammu & Kashmir
    ("Muzaffarabad", "MZF-01"), ("Mirpur", "MIR-01"),
    # Gilgit-Baltistan
    ("Gilgit", "GIL-01"), ("Skardu", "SKD-01"),
]

# every district above must resolve to a real province -- fail loudly at
# import time (not silently mid-generation) if seed_data.py's district
# convention and proximity.py's reference list ever drift apart
for _district, _cluster in DISTRICTS:
    assert _district in PROVINCE_BY_DISTRICT, f"{_district} missing from proximity.PROVINCE_BY_DISTRICT"

LOAN_PRODUCTS = [
    "Small Business Loan", "Loan for Orphan's Mother",
    "Liberation Loan", "Income Generating Project",
]

# (status, weight, gets_trade_category) -- roughly: most loans are live
# and disbursed, a meaningful chunk approved-not-yet-disbursed (still
# eligible per section 2), a small realistic minority defaulted/rejected,
# and a small Liberation-Loan-style slice with no trade category at all.
STATUS_WEIGHTS = [
    ("disbursed", 60), ("approved", 20), ("defaulted", 6),
    ("rejected", 6), ("liberation", 8),  # "liberation" = disbursed, no category
]

# ---------------------------------------------------------------------------
# Per-trade-category templates. Each entry: role, which seeking flag(s)
# it sets, a few EN phrasings (picked at random per listing for lexical
# variety -- 500 identical-text listings in one category would make
# search/matching trivially easy, not a realistic test), a matching Urdu
# original, and the two travel/distance gates. Multiple template variants
# per category so a category isn't just "one business, repeated."
# ---------------------------------------------------------------------------

TEMPLATES = {
    "Tailoring & embroidery": [
        dict(role="producer", seeking={"seeking_inputs": True},
             en=["Tailoring and stitching -- shalwar kameez, school uniforms, custom garment production",
                 "Embroidery and tailoring workshop -- bridal wear, uniforms, everyday clothing"],
             ur=["سلائی کا کام، یونیفارم اور کپڑے", "کڑھائی اور سلائی، شادی اور روزمرہ لباس"],
             remote=False, physical=True),
        dict(role="producer", seeking={"seeking_partner": True},
             en=["Tailoring business seeking a partner to expand into bridal wear"],
             ur=["سلائی کا کاروبار، شراکت دار چاہیے"],
             remote=False, physical=True, travel="will_partner_outside_district"),
        dict(role="service", seeking={"seeking_work": True},
             en=["Skilled tailor seeking steady work -- shirts, trousers, alterations"],
             ur=["ماہر درزی، کام کی تلاش میں"],
             remote=False, physical=False),
    ],
    "Grocery / Karyana": [
        dict(role="retailer", seeking={"seeking_inputs": True},
             en=["Grocery and general store -- staple foods, household goods, daily essentials retail",
                 "Karyana shop -- rice, flour, cooking oil, household items"],
             ur=["کریانہ کی دکان، سامان چاہیے", "جنرل سٹور، روزمرہ اشیاء"],
             remote=False, physical=True),
        dict(role="supplier", seeking={},
             en=["Wholesale grocery supplier -- staple foods and household goods, bulk supply to retail shops"],
             ur=["کریانہ کا سامان تھوک میں فراہم کرتا ہوں"],
             remote=False, physical=True, travel="will_deliver_outside_area"),
    ],
    "Livestock": [
        dict(role="producer", seeking={"seeking_workers": True},
             en=["Livestock farming -- goats and cattle rearing, dairy and meat production"],
             ur=["مویشی پالنا، مزدور چاہیے"],
             remote=False, physical=True),
        dict(role="supplier", seeking={},
             en=["Dairy and wool products supplier -- milk, wool, livestock byproducts"],
             ur=["دودھ اور اون کی فراہمی"],
             remote=False, physical=True, travel="will_deliver_outside_area"),
    ],
    "Manufacturing": [
        dict(role="supplier", seeking={},
             en=["Leather supplier -- hides and finished leather for shoemakers and garment producers"],
             ur=["چمڑے کی سپلائی"],
             remote=False, physical=True, travel="will_deliver_outside_area"),
        dict(role="producer", seeking={"seeking_inputs": True},
             en=["Shoe manufacturing -- leather footwear production, needs material supply",
                 "Textile manufacturing -- fabric weaving, needs raw cotton and yarn"],
             ur=["جوتے بنانے کا کام، چمڑا چاہیے", "کپڑا بنانے کا کام، خام مال چاہیے"],
             remote=False, physical=True),
    ],
    "Services": [
        dict(role="service", seeking={"seeking_partner": True},
             en=["Beauty parlor and salon services -- haircare, bridal makeup, seeking a partner"],
             ur=["بیوٹی پارلر، شراکت دار چاہیے"],
             remote=False, physical=False, travel="will_partner_outside_district"),
        dict(role="service", seeking={"seeking_work": True},
             en=["Electrician services -- household and commercial wiring, appliance repair",
                 "Plumbing services -- household repairs and installation, seeking work"],
             ur=["بجلی کا کام، مجھے کام چاہیے", "پلمبنگ کا کام، کام چاہیے"],
             remote=False, physical=False, travel="will_relocate_for_work"),
    ],
    "Food": [
        dict(role="retailer", seeking={"seeking_inputs": True},
             en=["Bakery -- bread and pastries, needs flour and sugar supply"],
             ur=["بیکری، آٹا اور چینی چاہیے"],
             remote=False, physical=True),
        dict(role="supplier", seeking={},
             en=["Catering and prepared food supplier -- bulk meals, event catering"],
             ur=["کیٹرنگ سروس، کھانا فراہم کرتا ہوں"],
             remote=False, physical=True, travel="will_deliver_outside_area"),
    ],
    "Three-wheeler / rickshaw": [
        dict(role="logistics", seeking={},
             en=["Three-wheeler rickshaw transport -- passenger and small goods delivery between districts"],
             ur=["رکشہ، سامان کی ترسیل"],
             remote=False, physical=True),
    ],
    "Agriculture": [
        dict(role="producer", seeking={"seeking_workers": True},
             en=["Agricultural farming -- crop cultivation, seasonal harvest, needs field workers"],
             ur=["کھیتی باڑی، مزدور چاہیے"],
             remote=False, physical=True),
        dict(role="supplier", seeking={},
             en=["Agricultural inputs supplier -- seeds, fertilizer, farming materials"],
             ur=["بیج اور کھاد کی فراہمی"],
             remote=False, physical=True, travel="will_deliver_outside_area"),
    ],
    "Freelancing / technology": [
        dict(role="service", seeking={"seeking_work": True},
             en=["Freelance web development and software services, remote-capable",
                 "Freelance IT support and technical work, seeking employment"],
             ur=["ویب ڈویلپمنٹ، دور سے کام", "فری لانس آئی ٹی کام"],
             remote=True, physical=False),
        dict(role="service", seeking={"seeking_workers": True},
             en=["Graphic design studio -- branding and digital design, hiring additional designers"],
             ur=["گرافک ڈیزائن اسٹوڈیو، ملازم چاہیے"],
             remote=True, physical=False),
    ],
    "Trading businesses": [
        dict(role="retailer", seeking={"seeking_inputs": True},
             en=["Wholesale general trading -- household goods, mixed merchandise retail"],
             ur=["ہول سیل دکان، سامان چاہیے"],
             remote=False, physical=True),
        dict(role="supplier", seeking={"seeking_partner": True},
             en=["Import-export trading business -- general merchandise sourcing, seeking a partner"],
             ur=["درآمد برآمد کاروبار، شراکت دار چاہیے"],
             remote=False, physical=True, travel="will_partner_outside_district"),
    ],
}


def weighted_status():
    statuses = [s for s, _weight in STATUS_WEIGHTS]
    weights = [w for _s, w in STATUS_WEIGHTS]
    return random.choices(statuses, weights=weights, k=1)[0]


def run():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute("select id, name from trade_categories")
    category_id_by_name = {name: cid for cid, name in cur.fetchall()}
    category_names = list(category_id_by_name.keys())

    # -----------------------------------------------------------------
    # Beneficiaries
    # -----------------------------------------------------------------
    print(f"generating {N_BENEFICIARIES} beneficiaries...")
    beneficiaries = []  # (id, name, phone, district, cluster_id)
    used_names = set()
    for i in range(N_BENEFICIARIES):
        is_male = random.random() < 0.55
        first = random.choice(FIRST_NAMES_MALE if is_male else FIRST_NAMES_FEMALE)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        # allow repeats past a point -- 3000 combos for 500 people makes
        # collisions rare, but not worth an infinite retry loop over
        used_names.add(name)
        district, cluster_id = random.choice(DISTRICTS)
        # +9234 prefix -- distinct from seed_data.py's +923001234xxx range
        # and from SKIP_ELIGIBILITY_CHECK's auto-provisioned test numbers
        # (+92300777xxxxx / +92300999xxxxx), so this block is unambiguous
        # to spot in the database later.
        phone = f"+9234{1000000 + i:07d}"
        beneficiaries.append((str(uuid.uuid4()), name, phone, district, cluster_id))

    psycopg2.extras.execute_values(
        cur,
        "insert into beneficiary_profiles (id, full_name, phone, district, cluster_id, consent_given) values %s",
        [(bid, name, phone, district, cluster_id, True) for bid, name, phone, district, cluster_id in beneficiaries],
    )
    print(f"  {len(beneficiaries)} beneficiary_profiles inserted.")

    # -----------------------------------------------------------------
    # Loans -- one per beneficiary
    # -----------------------------------------------------------------
    print("generating loans...")
    loans = []  # (id, beneficiary_id, product, category_name_or_None, status)
    for i, (bid, *_rest) in enumerate(beneficiaries):
        status_choice = weighted_status()
        if status_choice == "liberation":
            product, category_name, status = "Liberation Loan", None, "disbursed"
        else:
            product = random.choice([p for p in LOAN_PRODUCTS if p != "Liberation Loan"])
            category_name = random.choice(category_names)
            status = status_choice
        loans.append((str(uuid.uuid4()), bid, product, category_name, status))

    today = date.today()
    loan_rows = []
    for i, (lid, bid, product, category_name, status) in enumerate(loans):
        category_id = category_id_by_name.get(category_name) if category_name else None
        disbursed_on = today - timedelta(days=random.randint(15, 400)) if status in ("disbursed", "defaulted") else None
        amount = 150000 if product in ("Small Business Loan", "Income Generating Project") else 100000
        loan_rows.append((
            lid, f"AK-GEN-{10000 + i}", bid, product, category_id,
            f"Loan for {category_name or 'personal needs'}", status,
            amount if disbursed_on else None, disbursed_on,
        ))

    psycopg2.extras.execute_values(
        cur,
        "insert into microfinance_loans "
        "(id, loan_reference, beneficiary_id, loan_product, trade_category_id, "
        " stated_purpose_text, status, amount_disbursed, disbursed_on) values %s",
        loan_rows,
    )
    print(f"  {len(loan_rows)} microfinance_loans inserted.")

    # -----------------------------------------------------------------
    # Listings -- only for eligible beneficiaries (approved/disbursed +
    # a real category), and only LISTING_CREATION_RATE of those (see
    # file docstring).
    # -----------------------------------------------------------------
    print("selecting which eligible beneficiaries actually created a listing...")
    listing_plans = []  # (beneficiary_id, district, cluster_id, category_name, template)
    for (lid, ref, bid, product, category_id, purpose, status, amount, disbursed_on), \
        (b_id, name, phone, district, cluster_id) in zip(loan_rows, beneficiaries):
        if status not in ("approved", "disbursed") or category_id is None:
            continue
        if random.random() > LISTING_CREATION_RATE:
            continue
        category_name = next(n for n, cid in category_id_by_name.items() if cid == category_id)
        template = random.choice(TEMPLATES[category_name])
        listing_plans.append((bid, district, cluster_id, category_name, template))

    print(f"  {len(listing_plans)} listings to create -- embedding in batches...")
    en_texts = []
    ur_texts = []
    for bid, district, cluster_id, category_name, template in listing_plans:
        # Pick ONE shared index into en/ur so the two stay a real
        # translation pair -- every template above was written with
        # en[i] and ur[i] as matching phrasings, so picking them
        # independently would risk pairing an English sentence with an
        # unrelated Urdu one for the same listing.
        i = random.randrange(len(template["en"]))
        en_texts.append(template["en"][i])
        ur_texts.append(template["ur"][i])

    # embed_texts() batches the model call -- see file docstring's
    # "performance" note. Chunked at 100 to keep memory/latency
    # per-batch reasonable rather than one giant 375-item call.
    BATCH = 100
    vectors = []
    for start in range(0, len(en_texts), BATCH):
        chunk = en_texts[start:start + BATCH]
        vectors.extend(embed_texts(chunk))
        print(f"    embedded {min(start + BATCH, len(en_texts))}/{len(en_texts)}")

    listing_rows = []
    participant_rows = []
    for (bid, district, cluster_id, category_name, template), en_text, ur_text, vector in zip(
        listing_plans, en_texts, ur_texts, vectors
    ):
        listing_id = str(uuid.uuid4())
        seeking = template["seeking"]
        travel_flag = template.get("travel")
        listing_rows.append((
            listing_id, bid, None, category_id_by_name[category_name],
            en_text, ur_text, None,  # skills_en -- not generated here, matches seed_data.py's style
            template["role"],
            seeking.get("seeking_inputs", False), seeking.get("seeking_workers", False),
            seeking.get("seeking_partner", False), seeking.get("seeking_work", False),
            template["remote"], template["physical"],
            travel_flag == "will_deliver_outside_area",
            travel_flag == "will_relocate_for_work",
            travel_flag == "will_partner_outside_district",
            False,  # is_women_led -- not modeled here; seed_data.py's small hand-set already covers that case
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
    print(f"  {len(listing_rows)} store_listings + listing_participants inserted.")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. +{len(beneficiaries)} beneficiaries, +{len(loan_rows)} loans, "
          f"+{len(listing_rows)} listings added on top of whatever was already there.")


if __name__ == "__main__":
    run()
