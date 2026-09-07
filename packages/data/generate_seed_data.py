"""
Generates a large, realistic-scale seed dataset and ADDS it on top of
whatever seed_data.py already put in the database. Two layers:

  1. A RANDOM TAIL (N_RANDOM_BENEFICIARIES) -- beneficiaries scattered
     across every district/category/status, for realistic volume and a
     long thin tail that proximity weighting and search have to cope with.
  2. BALANCED HUB COVERAGE -- for every (hub city x trade category), one
     listing of EVERY template variant in that category (a supplier AND a
     producer-needing-inputs, a business-hiring AND a worker-seeking-work,
     two partners). This is the layer that guarantees matching actually
     has something to find: without it, a random 500 rows spread over
     43 districts x 15 categories x 5 roles leaves most (cluster,
     category) cells with 0-1 listings, so a new listing usually has no
     complementary counterpart in its own cluster and every match funnel
     empties out. With it, every hub has a real supply-chain pair, a real
     employment pair, and a real joint-venture pair in every category.

RE-RUNNABLE (this is new -- the old version refused to touch existing
rows and so could only run once, then collided on the unique phone
numbers). Every row this script creates carries a marker phone prefix
(+9234 random tail, +9235 balanced coverage); on each run it first
deletes its own previous output (and only its own -- seed_data.py's
+92300 curated rows and the +92300777/+92300999 SKIP_ELIGIBILITY_CHECK
test rows are never touched), then regenerates. Safe to run repeatedly.

WHY A GENERATOR, NOT MORE HAND-WRITTEN ROWS LIKE seed_data.py
--------------------------------------------------------------------------
seed_data.py's ~30 beneficiaries/~25 listings are hand-written on purpose
-- small enough that every row is deliberate (a specific matching
scenario, a specific gate case). Thousands of rows are a different kind
of data: volume and coverage to test against, not scenarios. This is
"synthetic data generation via templates," same concept
packages/eligibility's XGBoost training data uses, just simpler. Kept a
SEPARATE file from seed_data.py since they do genuinely different jobs.

WHY NOT EVERY BENEFICIARY GETS A LISTING (random tail only)
--------------------------------------------
Marketplace_Spec.md section 2: joining the marketplace is voluntary, not
automatic. LISTING_CREATION_RATE controls what fraction of ELIGIBLE
random-tail beneficiaries actually created one -- the rest are eligible,
invited, but haven't gotten around to it. The balanced-coverage layer
ignores this rate on purpose: its whole point is guaranteed coverage.

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
from proximity import PROVINCE_BY_DISTRICT, CLUSTER_BY_DISTRICT  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

random.seed(42)  # reproducible -- rerunning this script (against an
                  # empty table) should generate the same dataset, not a
                  # new random one each time, so results are comparable
                  # across a demo dry-run and the real thing.

N_RANDOM_BENEFICIARIES = 800   # the random tail -- see file docstring
LISTING_CREATION_RATE = 0.85   # of eligible random-tail beneficiaries
HUB_TAIL_BIAS = 0.6            # fraction of the random tail placed in a hub district

# Hub cities that get FULL (hub x category x every template) coverage --
# the biggest real population centres across all provinces + ICT, so
# proximity weighting still has near/adjacent/far variety while every
# common (cluster, category) actually has complementary listings in it.
# cluster_id comes from proximity.CLUSTER_BY_DISTRICT (single source).
_HUB_CITIES = [
    "Lahore", "Karachi", "Faisalabad", "Rawalpindi", "Multan", "Gujranwala",
    "Peshawar", "Islamabad", "Hyderabad", "Quetta", "Sialkot", "Sukkur",
    "Bahawalpur", "Sargodha",
]
HUB_DISTRICTS = [(city, CLUSTER_BY_DISTRICT[city]) for city in _HUB_CITIES]

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
# Districts -- spread across all four provinces + ICT + AJK + GB, so
# proximity weighting (same cluster / adjacent / same province /
# elsewhere) has real variety. The (district -> cluster_id) map is the
# ONE in proximity.CLUSTER_BY_DISTRICT -- shared with seed_data.py,
# create_test_customer.py and auth.py so every path agrees on a
# district's cluster (see that dict's comment for the bug this fixes).
# ---------------------------------------------------------------------------

DISTRICTS = sorted(CLUSTER_BY_DISTRICT.items())  # [(district, cluster_id), ...]

# fail loudly at import time if the two proximity reference maps ever
# drift apart, rather than silently mid-generation
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

# SPECIALTY SUFFIXES -- added 5 Sep 2026, direct feedback ("multiple
# businesses have the same [description]"). Measured directly: 352
# generated listings, only 46 distinct description texts -- with that
# few templates spread across ~350 listings, most of a category shares
# byte-identical text, which means byte-identical embeddings, which
# makes semantic search trivially "perfect" within a category and
# genuinely untestable (nothing to actually differentiate on). Rather
# than hand-writing dozens of full alternate templates (a much bigger
# authoring job) or an LLM call per listing (real Groq rate-limit risk
# at this volume, per CLAUDE.md's own risk list), each generated
# description gets a random per-category "specialty" phrase appended --
# multiplies (base templates) x (specialty suffixes) worth of distinct
# text combinations from a much smaller amount of new content, and a
# real trailing phrase changes the embedding, unlike padding with
# meaningless filler would.
SPECIALTY_SUFFIXES = {
    "Tailoring & embroidery": [
        ("specializing in bridal wear and formal suits", "شادی اور رسمی لباس میں مہارت"),
        ("known for quick turnaround on school uniforms", "یونیفارم جلدی تیار کرنے میں مشہور"),
        ("with a focus on hand embroidery work", "ہاتھ کی کڑھائی پر خاص توجہ"),
        ("serving both men's and women's clothing", "مردوں اور خواتین دونوں کے کپڑے"),
        ("also does alterations and repairs", "کپڑوں کی مرمت بھی کرتے ہیں"),
    ],
    "Grocery / Karyana": [
        ("known for competitive wholesale rates", "مسابقتی تھوک نرخوں کے لیے مشہور"),
        ("carries imported as well as local brands", "درآمدی اور مقامی برانڈز دونوں دستیاب"),
        ("open long hours, serves the whole neighbourhood", "لمبے اوقات کار، پورا محلہ خدمت میں"),
        ("also stocks household cleaning supplies", "صفائی کا سامان بھی رکھتے ہیں"),
    ],
    "Livestock": [
        ("specializes in goats for Eid season", "عید کے لیے بکروں میں مہارت"),
        ("known for healthy, well-fed cattle", "صحت مند مویشیوں کے لیے مشہور"),
        ("also sells fresh milk daily", "روزانہ تازہ دودھ بھی فروخت"),
        ("focuses on breeding and rearing", "افزائش اور پرورش پر توجہ"),
    ],
    "Manufacturing": [
        ("specializes in export-quality finishing", "برآمدی معیار کی فنشنگ میں مہارت"),
        ("known for durable, heavy-duty goods", "پائیدار اور مضبوط سامان کے لیے مشہور"),
        ("handles both small and bulk orders", "چھوٹے اور بڑے دونوں آرڈر لیتے ہیں"),
        ("focuses on custom-made pieces", "حسب ضرورت سامان بناتے ہیں"),
    ],
    "Services": [
        ("known for same-day service", "اسی دن کام مکمل کرنے میں مشہور"),
        ("serves both homes and businesses", "گھروں اور کاروبار دونوں کی خدمت"),
    ],
    "Beauty & Personal Care": [
        ("specializes in bridal packages", "دلہن کے پیکجز میں مہارت"),
        ("known for using quality, gentle products", "معیاری اور نرم مصنوعات کے لیے مشہور"),
        ("also offers home-visit appointments", "گھر پر بھی خدمات فراہم کرتے ہیں"),
        ("serves both homes and businesses", "گھروں اور کاروبار دونوں کی خدمت"),
    ],
    "Construction & Home Trades": [
        ("known for same-day service", "اسی دن کام مکمل کرنے میں مشہور"),
        ("specializes in emergency call-outs", "ہنگامی کالز میں مہارت"),
        ("offers a warranty on all work", "تمام کام پر ضمانت دیتے ہیں"),
        ("serves both homes and businesses", "گھروں اور کاروبار دونوں کی خدمت"),
    ],
    "Repair & Maintenance": [
        ("known for same-day service", "اسی دن کام مکمل کرنے میں مشہور"),
        ("offers a warranty on all work", "تمام کام پر ضمانت دیتے ہیں"),
        ("also does on-site repairs", "موقع پر بھی مرمت کرتے ہیں"),
    ],
    "Education & Tutoring": [
        ("specializes in exam preparation", "امتحان کی تیاری میں مہارت"),
        ("known for individualized lesson plans", "انفرادی نصاب کے لیے مشہور"),
        ("also offers group class discounts", "گروپ کلاسز پر رعایت بھی دیتے ہیں"),
    ],
    "Food": [
        ("known for fresh-baked goods every morning", "روزانہ صبح تازہ بیکری کے لیے مشہور"),
        ("specializes in wedding and event orders", "شادی اور تقریبات کے آرڈر میں مہارت"),
        ("also does bulk catering for offices", "دفاتر کے لیے تھوک کیٹرنگ بھی"),
        ("focuses on traditional home-style recipes", "روایتی گھریلو ذائقے پر توجہ"),
    ],
    "Three-wheeler / rickshaw": [
        ("covers long-distance intercity routes", "طویل فاصلے کے بین شہری روٹس"),
        ("specializes in same-day small goods delivery", "اسی دن سامان کی ترسیل میں مہارت"),
        ("known for reliable, on-time service", "قابل اعتماد اور وقت کی پابندی کے لیے مشہور"),
        ("also available for passenger trips", "مسافروں کے لیے بھی دستیاب"),
    ],
    "Agriculture": [
        ("specializes in seasonal wheat and rice", "موسمی گندم اور چاول میں مہارت"),
        ("known for organic farming methods", "نامیاتی کاشتکاری کے طریقوں کے لیے مشہور"),
        ("also supplies to local mandis directly", "مقامی منڈیوں کو براہ راست سپلائی بھی"),
        ("focuses on high-yield seasonal crops", "زیادہ پیداوار والی موسمی فصلوں پر توجہ"),
    ],
    "Freelancing / technology": [
        ("specializes in e-commerce websites", "ای کامرس ویب سائٹس میں مہارت"),
        ("known for fast turnaround on small projects", "چھوٹے منصوبوں پر تیز کام کے لیے مشہور"),
        ("also offers ongoing maintenance support", "مسلسل معاونت بھی فراہم کرتے ہیں"),
        ("focuses on mobile-friendly design", "موبائل دوست ڈیزائن پر توجہ"),
    ],
    # Added 5 Sep 2026 alongside the new trade_categories row -- direct
    # request, and the actual case that surfaced the gap: a clay-jewelry
    # maker had no honest category before this.
    "Handicrafts & Artisan Crafts": [
        ("specializes in custom wedding-order pieces", "شادی کے حسبِ ضرورت آرڈرز میں مہارت"),
        ("known for traditional hand-painted designs", "روایتی ہاتھ سے بنے ڈیزائن کے لیے مشہور"),
        ("also sells through local exhibitions and stalls", "مقامی نمائشوں اور اسٹالز میں بھی فروخت"),
        ("focuses on eco-friendly, locally-sourced materials", "ماحول دوست، مقامی مواد پر توجہ"),
    ],
    "Trading businesses": [
        ("specializes in bulk import orders", "تھوک درآمدی آرڈرز میں مہارت"),
        ("known for a wide range of mixed merchandise", "متنوع سامان کی وسیع رینج کے لیے مشہور"),
        ("also handles export documentation", "برآمدی دستاویزات بھی سنبھالتے ہیں"),
        ("focuses on household and daily-use goods", "گھریلو اور روزمرہ استعمال کے سامان پر توجہ"),
    ],
}


# ---------------------------------------------------------------------------
# Per-trade-category templates. Each entry: role, which seeking flag(s)
# it sets, a few EN phrasings (picked at random per listing for lexical
# variety -- 500 identical-text listings in one category would make
# search/matching trivially easy, not a realistic test), a matching Urdu
# original, and the two travel/distance gates. Multiple template variants
# per category so a category isn't just "one business, repeated." See
# SPECIALTY_SUFFIXES above for the second layer of diversity on top of
# these.
# ---------------------------------------------------------------------------

TEMPLATES = {
    "Tailoring & embroidery": [
        dict(role="producer", seeking={"seeking_inputs": True},
             en=["Tailoring and stitching -- shalwar kameez, school uniforms, custom garment production",
                 "Embroidery and tailoring workshop -- bridal wear, uniforms, everyday clothing"],
             ur=["سلائی کا کام، یونیفارم اور کپڑے", "کڑھائی اور سلائی، شادی اور روزمرہ لباس"],
             remote=False, physical=True),
        dict(role="supplier", seeking={},
             en=["Fabric and tailoring-supplies wholesaler -- cloth, thread, buttons, trims for tailors and boutiques"],
             ur=["کپڑا اور سلائی کا سامان تھوک میں فراہم کرتا ہوں"],
             remote=False, physical=True, travel="will_deliver_outside_area"),
        dict(role="producer", seeking={"seeking_partner": True},
             en=["Tailoring business seeking a partner to expand into bridal wear"],
             ur=["سلائی کا کاروبار، شراکت دار چاہیے"],
             remote=False, physical=True, travel="will_partner_outside_district"),
        dict(role="service", seeking={"seeking_work": True},
             en=["Skilled tailor seeking steady work -- shirts, trousers, alterations"],
             ur=["ماہر درزی، کام کی تلاش میں"],
             remote=False, physical=False),
        dict(role="producer", seeking={"seeking_workers": True},
             en=["Growing tailoring workshop hiring additional stitching staff"],
             ur=["سلائی کا بڑھتا ہوا کاروبار، درزی چاہیے"],
             remote=False, physical=True),
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
        dict(role="retailer", seeking={"seeking_workers": True},
             en=["Busy karyana store hiring a cashier and stock help"],
             ur=["کریانہ کی دکان، کیشیئر چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_work": True},
             en=["Experienced store clerk seeking work -- cashier, stock, customer service"],
             ur=["تجربہ کار دکاندار، کام کی تلاش میں"],
             remote=False, physical=False),
        dict(role="retailer", seeking={"seeking_partner": True},
             en=["Grocery store seeking a partner to open a second branch"],
             ur=["کریانہ کی دکان، دوسری شاخ کے لیے شراکت دار چاہیے"],
             remote=False, physical=True, travel="will_partner_outside_district"),
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
        dict(role="producer", seeking={"seeking_inputs": True},
             en=["Livestock farm needing feed, fodder, and veterinary supplies"],
             ur=["مویشیوں کے لیے چارہ اور ادویات چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_work": True},
             en=["Experienced livestock handler seeking work -- feeding, milking, herd care"],
             ur=["مویشیوں کا تجربہ کار کارکن، کام کی تلاش میں"],
             remote=False, physical=False),
        dict(role="producer", seeking={"seeking_partner": True},
             en=["Dairy farm seeking a partner to expand into a larger herd"],
             ur=["ڈیری فارم، شراکت دار چاہیے"],
             remote=False, physical=True, travel="will_partner_outside_district"),
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
        dict(role="producer", seeking={"seeking_workers": True},
             en=["Growing manufacturing workshop hiring skilled production staff"],
             ur=["تیار کرنے کا کاروبار بڑھ رہا ہے، ہنر مند کارکن چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_work": True},
             en=["Skilled machine operator / production worker seeking steady factory work"],
             ur=["ہنر مند مشین آپریٹر، کام کی تلاش میں"],
             remote=False, physical=False),
        dict(role="producer", seeking={"seeking_partner": True},
             en=["Small manufacturing unit seeking a partner to scale up production"],
             ur=["مینوفیکچرنگ یونٹ، شراکت دار چاہیے"],
             remote=False, physical=True, travel="will_partner_outside_district"),
    ],
    # "Services" split 5 Sep 2026 -- moved out of here into 4 dedicated
    # categories below (Beauty & Personal Care, Construction & Home
    # Trades, Repair & Maintenance, Education & Tutoring). See the
    # schema comment on the same date for why: every real listing that
    # used to be filed under "Services" was actually one of these four,
    # and leaving them lumped together was defeating the employment
    # same-category match rule (an electrician and a beautician
    # counting as "the same trade").
    "Services": [
        dict(role="service", seeking={"seeking_work": True},
             en=["Laundry and dry-cleaning service -- washing, ironing, seeking steady customers or work"],
             ur=["لانڈری اور ڈرائی کلیننگ سروس، کام چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={},
             en=["Courier and documentation service -- local delivery, paperwork and errand assistance"],
             ur=["کورئیر اور دستاویزات کی خدمات"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_inputs": True},
             en=["General service business needing supplies -- cleaning materials, packaging, office items"],
             ur=["سروس کاروبار کے لیے سامان چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_workers": True},
             en=["Growing service business hiring general staff"],
             ur=["بڑھتا ہوا سروس کاروبار، عملہ چاہیے"],
             remote=False, physical=False),
        dict(role="service", seeking={"seeking_partner": True},
             en=["Established service business seeking a partner to expand"],
             ur=["قائم شدہ سروس کاروبار، شراکت دار چاہیے"],
             remote=False, physical=False, travel="will_partner_outside_district"),
    ],
    "Beauty & Personal Care": [
        dict(role="service", seeking={"seeking_partner": True},
             en=["Beauty parlor and salon services -- haircare, bridal makeup, seeking a partner"],
             ur=["بیوٹی پارلر، شراکت دار چاہیے"],
             remote=False, physical=False, travel="will_partner_outside_district"),
        dict(role="service", seeking={"seeking_work": True},
             en=["Skilled beautician seeking steady work -- haircare, bridal makeup, skincare"],
             ur=["ماہر بیوٹیشن، کام کی تلاش میں"],
             remote=False, physical=False, travel="will_relocate_for_work"),
        dict(role="service", seeking={"seeking_workers": True},
             en=["Established beauty salon hiring additional staff"],
             ur=["بیوٹی سیلون، ملازم چاہیے"],
             remote=False, physical=False),
        dict(role="service", seeking={"seeking_inputs": True},
             en=["Beauty parlor needing cosmetics, haircare products, and salon supplies"],
             ur=["بیوٹی پارلر کے لیے میک اپ اور سیلون کا سامان چاہیے"],
             remote=False, physical=True),
    ],
    "Construction & Home Trades": [
        dict(role="service", seeking={"seeking_work": True},
             en=["Electrician services -- household and commercial wiring, appliance repair",
                 "Plumbing services -- household repairs and installation, seeking work"],
             ur=["بجلی کا کام، مجھے کام چاہیے", "پلمبنگ کا کام، کام چاہیے"],
             remote=False, physical=False, travel="will_relocate_for_work"),
        dict(role="service", seeking={"seeking_workers": True},
             en=["Construction contractor hiring skilled tradesmen -- masonry, carpentry, wiring"],
             ur=["تعمیراتی ٹھیکیدار، ہنر مند مزدور چاہیے"],
             remote=False, physical=False),
        dict(role="service", seeking={},
             en=["Carpentry and woodwork -- custom furniture, home fittings and repairs"],
             ur=["بڑھئی کا کام، فرنیچر اور مرمت"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_inputs": True},
             en=["Construction business needing cement, wiring, pipes, and hardware supplies"],
             ur=["تعمیراتی کاروبار کے لیے سیمنٹ اور سامان چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_partner": True},
             en=["Home-trades business seeking a partner to take on larger contracts"],
             ur=["گھریلو خدمات کا کاروبار، بڑے ٹھیکوں کے لیے شراکت دار چاہیے"],
             remote=False, physical=False, travel="will_partner_outside_district"),
    ],
    "Repair & Maintenance": [
        dict(role="service", seeking={"seeking_work": True},
             en=["Mobile phone and appliance repair -- screen replacement, hardware fixes, seeking work"],
             ur=["موبائل اور آلات کی مرمت، کام چاہیے"],
             remote=False, physical=False, travel="will_relocate_for_work"),
        dict(role="service", seeking={},
             en=["Vehicle and motorcycle repair workshop -- servicing, parts replacement"],
             ur=["گاڑی اور موٹرسائیکل مرمت کی ورکشاپ"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_workers": True},
             en=["Busy repair workshop hiring an additional technician -- mobile, appliance, or vehicle repair skills"],
             ur=["مصروف مرمت کی ورکشاپ، اضافی ٹیکنیشن چاہیے"],
             remote=False, physical=False),
        dict(role="service", seeking={"seeking_inputs": True},
             en=["Repair workshop needing spare parts and replacement components"],
             ur=["مرمت کی ورکشاپ کے لیے پرزہ جات چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_partner": True},
             en=["Repair workshop seeking a partner to open a second location"],
             ur=["مرمت کی ورکشاپ، دوسری برانچ کے لیے شراکت دار چاہیے"],
             remote=False, physical=False, travel="will_partner_outside_district"),
    ],
    "Education & Tutoring": [
        dict(role="service", seeking={"seeking_work": True},
             en=["Online tutoring services -- remote teaching, seeking employment, no travel needed"],
             ur=["آن لائن ٹیوشن، دور سے کام کر سکتی ہوں"],
             remote=True, physical=False),
        dict(role="service", seeking={"seeking_workers": True},
             en=["Tutoring academy hiring additional subject teachers"],
             ur=["ٹیوشن اکیڈمی، اساتذہ چاہیے"],
             remote=False, physical=False),
        dict(role="service", seeking={"seeking_inputs": True},
             en=["Tutoring center needing books, stationery, and teaching materials"],
             ur=["ٹیوشن سینٹر کے لیے کتابیں اور تدریسی سامان چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_partner": True},
             en=["Individual tutor seeking a partner to open a proper academy"],
             ur=["ٹیوٹر، اکیڈمی کھولنے کے لیے شراکت دار چاہیے"],
             remote=False, physical=False, travel="will_partner_outside_district"),
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
        dict(role="retailer", seeking={"seeking_workers": True},
             en=["Growing bakery hiring kitchen and counter staff"],
             ur=["بیکری کا کاروبار بڑھ رہا ہے، عملہ چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_work": True},
             en=["Experienced cook / baker seeking steady kitchen work"],
             ur=["تجربہ کار باورچی، کام کی تلاش میں"],
             remote=False, physical=False),
        dict(role="retailer", seeking={"seeking_partner": True},
             en=["Food business seeking a partner to open a second outlet"],
             ur=["فوڈ کاروبار، دوسری شاخ کے لیے شراکت دار چاہیے"],
             remote=False, physical=True, travel="will_partner_outside_district"),
    ],
    "Three-wheeler / rickshaw": [
        dict(role="logistics", seeking={},
             en=["Three-wheeler rickshaw transport -- passenger and small goods delivery between districts"],
             ur=["رکشہ، سامان کی ترسیل"],
             remote=False, physical=True),
        dict(role="logistics", seeking={"seeking_inputs": True},
             en=["Rickshaw operator needing fuel, tyres, and spare parts supply"],
             ur=["رکشہ کے لیے پرزہ جات اور ایندھن چاہیے"],
             remote=False, physical=True),
        dict(role="logistics", seeking={"seeking_workers": True},
             en=["Small transport business hiring an additional rickshaw driver"],
             ur=["ٹرانسپورٹ کا کاروبار، اضافی ڈرائیور چاہیے"],
             remote=False, physical=False),
        dict(role="service", seeking={"seeking_work": True},
             en=["Experienced rickshaw driver seeking steady work"],
             ur=["تجربہ کار رکشہ ڈرائیور، کام کی تلاش میں"],
             remote=False, physical=False),
        dict(role="logistics", seeking={"seeking_partner": True},
             en=["Rickshaw operator seeking a partner to expand into a small transport fleet"],
             ur=["رکشہ آپریٹر، فلیٹ بڑھانے کے لیے شراکت دار چاہیے"],
             remote=False, physical=False, travel="will_partner_outside_district"),
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
        dict(role="producer", seeking={"seeking_inputs": True},
             en=["Farm needing seeds, fertilizer, and irrigation supplies for the coming season"],
             ur=["فارم کے لیے بیج اور کھاد چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_work": True},
             en=["Experienced farm laborer seeking seasonal or steady field work"],
             ur=["تجربہ کار کسان مزدور، کام کی تلاش میں"],
             remote=False, physical=False),
        dict(role="producer", seeking={"seeking_partner": True},
             en=["Farm seeking a partner to lease and cultivate additional land"],
             ur=["فارم، اضافی زمین کاشت کرنے کے لیے شراکت دار چاہیے"],
             remote=False, physical=True, travel="will_partner_outside_district"),
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
        # Deliberately no supply_chain template here -- freelance/tech
        # work has no physical input to seek or supply, unlike every
        # other category. seeking_inputs would be a fabricated scenario,
        # not a real one -- see PRODUCT_OR_SERVICE reasoning elsewhere in
        # this file about not inventing detail that isn't real.
        dict(role="service", seeking={"seeking_partner": True},
             en=["Freelance developer or designer seeking a partner to form a small digital agency"],
             ur=["فری لانسر، ڈیجیٹل ایجنسی بنانے کے لیے شراکت دار چاہیے"],
             remote=True, physical=False),
    ],
    "Trading businesses": [
        dict(role="retailer", seeking={"seeking_inputs": True},
             en=["Wholesale general trading -- household goods, mixed merchandise retail"],
             ur=["ہول سیل دکان، سامان چاہیے"],
             remote=False, physical=True),
        dict(role="supplier", seeking={},
             en=["General merchandise wholesaler -- mixed household and daily-use goods, bulk supply"],
             ur=["عمومی سامان تھوک میں فراہم کرتا ہوں"],
             remote=False, physical=True, travel="will_deliver_outside_area"),
        dict(role="supplier", seeking={"seeking_partner": True},
             en=["Import-export trading business -- general merchandise sourcing, seeking a partner"],
             ur=["درآمد برآمد کاروبار، شراکت دار چاہیے"],
             remote=False, physical=True, travel="will_partner_outside_district"),
        dict(role="retailer", seeking={"seeking_workers": True},
             en=["Growing trading business hiring warehouse and sales staff"],
             ur=["تجارتی کاروبار بڑھ رہا ہے، عملہ چاہیے"],
             remote=False, physical=True),
        dict(role="service", seeking={"seeking_work": True},
             en=["Experienced trading/sales worker seeking steady employment"],
             ur=["تجربہ کار سیلز کارکن، کام کی تلاش میں"],
             remote=False, physical=False),
    ],
    "Handicrafts & Artisan Crafts": [
        dict(role="producer", seeking={"seeking_inputs": True},
             en=["Handmade pottery and clay craft production -- decorative and functional pieces, needs raw clay and glazing materials",
                 "Handmade jewelry making -- beads, clay, and metal accessories, needs craft materials"],
             ur=["مٹی کے برتن اور دستکاری، خام مال چاہیے", "ہاتھ سے بنی جیولری، سامان چاہیے"],
             remote=False, physical=True),
        dict(role="supplier", seeking={},
             en=["Craft-supplies wholesaler -- beads, clay, dyes, and materials for artisans"],
             ur=["دستکاری کا سامان تھوک میں فراہم کرتا ہوں"],
             remote=False, physical=True, travel="will_deliver_outside_area"),
        dict(role="producer", seeking={"seeking_partner": True},
             en=["Artisan crochet and home decor workshop seeking a partner to expand into new markets"],
             ur=["دستکاری اور کروشیے کا کام، شراکت دار چاہیے"],
             remote=False, physical=True, travel="will_partner_outside_district"),
        dict(role="service", seeking={"seeking_work": True},
             en=["Skilled artisan (pottery, jewelry, or crochet) seeking steady work or commissions"],
             ur=["ہنر مند کاریگر، کام کی تلاش میں"],
             remote=False, physical=False),
        dict(role="producer", seeking={"seeking_workers": True},
             en=["Growing handicrafts workshop hiring additional artisans -- pottery, jewelry-making, or crochet skills"],
             ur=["دستکاری کا بڑھتا ہوا کاروبار، ہنر مند کاریگر چاہیے"],
             remote=False, physical=True),
    ],
}


# One or two plausible nouns per category, for real business names --
# added 5 Sep 2026, direct feedback: every generated listing's
# business_name was hardcoded None, so browse/match screens showed
# "(unnamed business)" for nearly everyone -- reads as "every business
# has the same name," not as N distinct businesses.
BUSINESS_NAME_NOUNS = {
    "Tailoring & embroidery": ["Tailoring", "Boutique", "Stitching House"],
    "Grocery / Karyana": ["General Store", "Grocery", "Karyana Store"],
    "Livestock": ["Farm", "Livestock Farm", "Dairy Farm"],
    "Manufacturing": ["Works", "Manufacturing", "Industries"],
    "Services": ["Services", "Service Center"],
    "Beauty & Personal Care": ["Beauty Parlor", "Salon", "Beauty Studio"],
    "Construction & Home Trades": ["Electric Works", "Home Services", "Trades"],
    "Repair & Maintenance": ["Repair Center", "Fix-It Shop", "Workshop"],
    "Education & Tutoring": ["Tutoring", "Academy", "Learning Center"],
    "Food": ["Foods", "Bakery", "Kitchen"],
    "Three-wheeler / rickshaw": ["Transport", "Rickshaw Service", "Logistics"],
    "Agriculture": ["Farms", "Agri Farms"],
    "Freelancing / technology": ["Studio", "Tech Services", "Digital Works"],
    "Trading businesses": ["Traders", "Trading Co.", "Trading Business"],
    "Handicrafts & Artisan Crafts": ["Crafts", "Pottery Studio", "Artisan Works"],
}


def _generate_business_name(full_name: str, category_name: str) -> str:
    first = full_name.split()[0]
    last = full_name.split()[-1]
    noun = random.choice(BUSINESS_NAME_NOUNS[category_name])
    pattern = random.choice([
        f"{first}'s {noun}",
        f"{first} {noun}",
        f"{last} {noun}",
    ])
    return pattern


def weighted_status():
    statuses = [s for s, _weight in STATUS_WEIGHTS]
    weights = [w for _s, w in STATUS_WEIGHTS]
    return random.choices(statuses, weights=weights, k=1)[0]


GEN_PHONE_PREFIXES = ("+9234", "+9235")  # +9234 random tail, +9235 balanced coverage.
                                         # Both distinct from seed_data.py's +923001234xxx
                                         # curated rows and SKIP_ELIGIBILITY_CHECK's
                                         # +92300777xxxxx / +92300999xxxxx test numbers, so
                                         # this script's output is unambiguous to spot -- and
                                         # to delete on the next run (see _clean_previous).


def _clean_previous(cur):
    """
    Delete only the rows a previous run of THIS script created -- nothing
    else. Identified purely by the marker phone prefixes above.

    beneficiary_profiles -> loans/listings/participants/photos/notifications
    all cascade on delete. The two FKs that DON'T cascade and would block
    the delete are handled first: marketplace_matches.suggested_logistics_id
    / .dismissed_by_listing_id (nulled), and match_messages.sender_beneficiary_id
    (row deleted). Freshly generated seed data has none of these, but a run
    after someone clicked around the app might.
    """
    cur.execute(
        "select id from beneficiary_profiles where "
        + " or ".join("phone like %s" for _ in GEN_PHONE_PREFIXES),
        tuple(p + "%" for p in GEN_PHONE_PREFIXES),
    )
    ids = [r[0] for r in cur.fetchall()]
    if not ids:
        print("  nothing from a previous run to clear.")
        return

    cur.execute("select id from store_listings where primary_beneficiary_id = any(%s::uuid[])", (ids,))
    listing_ids = [r[0] for r in cur.fetchall()]
    if listing_ids:
        cur.execute(
            "delete from marketplace_matches "
            "where listing_a_id = any(%s::uuid[]) or listing_b_id = any(%s::uuid[])",
            (listing_ids, listing_ids),
        )
        cur.execute("update marketplace_matches set suggested_logistics_id = null "
                    "where suggested_logistics_id = any(%s::uuid[])", (listing_ids,))
        cur.execute("update marketplace_matches set dismissed_by_listing_id = null "
                    "where dismissed_by_listing_id = any(%s::uuid[])", (listing_ids,))
        cur.execute("update donations set listing_id = null where listing_id = any(%s::uuid[])", (listing_ids,))
        cur.execute("update graduation_events set listing_id = null where listing_id = any(%s::uuid[])", (listing_ids,))
    cur.execute("delete from match_messages where sender_beneficiary_id = any(%s::uuid[])", (ids,))
    cur.execute("delete from beneficiary_profiles where id = any(%s::uuid[])", (ids,))
    print(f"  cleared {len(ids)} beneficiaries and {len(listing_ids)} listings from a previous run.")


def _random_district():
    """Random-tail placement -- biased toward the hubs (HUB_TAIL_BIAS) so
    proximity weighting sees realistic density, with a genuine long tail
    of one-offs in the smaller districts."""
    if random.random() < HUB_TAIL_BIAS:
        return random.choice(HUB_DISTRICTS)
    return random.choice(DISTRICTS)


def _random_name():
    is_male = random.random() < 0.55
    first = random.choice(FIRST_NAMES_MALE if is_male else FIRST_NAMES_FEMALE)
    return f"{first} {random.choice(LAST_NAMES)}", is_male


def run():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    print("clearing rows from any previous run of this script...")
    _clean_previous(cur)

    cur.execute("select id, name from trade_categories")
    category_id_by_name = {name: cid for cid, name in cur.fetchall()}
    category_names = list(category_id_by_name.keys())

    today = date.today()
    beneficiaries = []   # (id, name, phone, district, cluster, is_male)
    loan_rows = []       # full microfinance_loans insert tuple
    listing_plans = []   # (bid, name, district, cluster, category_name, template, is_women_led)

    def add_person(phone, district, cluster, *, category_name, status, make_listing, template=None):
        bid = str(uuid.uuid4())
        name, is_male = _random_name()
        beneficiaries.append((bid, name, phone, district, cluster, is_male))
        category_id = category_id_by_name.get(category_name) if category_name else None
        product = ("Liberation Loan" if category_name is None
                   else random.choice([p for p in LOAN_PRODUCTS if p != "Liberation Loan"]))
        disbursed_on = (today - timedelta(days=random.randint(15, 400))
                        if status in ("disbursed", "defaulted") else None)
        amount = 150000 if product in ("Small Business Loan", "Income Generating Project") else 100000
        loan_rows.append((
            str(uuid.uuid4()), f"AK-GEN-{10000 + len(loan_rows)}", bid, product, category_id,
            f"Loan for {category_name or 'personal needs'}", status,
            amount if disbursed_on else None, disbursed_on,
        ))
        if make_listing and category_id is not None:
            listing_plans.append((
                bid, name, district, cluster, category_name,
                template or random.choice(TEMPLATES[category_name]), not is_male,
            ))

    # -----------------------------------------------------------------
    # 1. Random tail -- volume + a realistic thin spread
    # -----------------------------------------------------------------
    print(f"generating {N_RANDOM_BENEFICIARIES} random-tail beneficiaries...")
    for i in range(N_RANDOM_BENEFICIARIES):
        district, cluster = _random_district()
        status_choice = weighted_status()
        if status_choice == "liberation":     # disbursed, but no trade category
            category_name, status = None, "disbursed"
        else:
            category_name, status = random.choice(category_names), status_choice
        make_listing = (status in ("approved", "disbursed") and category_name is not None
                        and random.random() <= LISTING_CREATION_RATE)
        add_person(f"+9234{1_000_000 + i:07d}", district, cluster,
                   category_name=category_name, status=status, make_listing=make_listing)

    # -----------------------------------------------------------------
    # 2. Balanced coverage -- every hub x every category x every template
    #    variant, so supply-chain / employment / joint-venture each have a
    #    real counterpart in every hub. seeking_partner templates get two
    #    copies so a joint venture has an actual pair, not a singleton.
    # -----------------------------------------------------------------
    print(f"generating balanced coverage: {len(HUB_DISTRICTS)} hubs "
          f"x {len(category_names)} categories x every template...")
    seq = 0
    for district, cluster in HUB_DISTRICTS:
        for category_name in category_names:
            for template in TEMPLATES[category_name]:
                copies = 2 if template["seeking"].get("seeking_partner") else 1
                for _ in range(copies):
                    add_person(f"+9235{1_000_000 + seq:07d}", district, cluster,
                               category_name=category_name, status="disbursed",
                               make_listing=True, template=template)
                    seq += 1

    # -----------------------------------------------------------------
    # Insert beneficiaries + loans
    # -----------------------------------------------------------------
    print(f"inserting {len(beneficiaries)} beneficiary_profiles...")
    psycopg2.extras.execute_values(
        cur,
        "insert into beneficiary_profiles (id, full_name, phone, district, cluster_id, consent_given) values %s",
        [(bid, name, phone, district, cluster, True)
         for bid, name, phone, district, cluster, _is_male in beneficiaries],
    )
    print(f"inserting {len(loan_rows)} microfinance_loans...")
    psycopg2.extras.execute_values(
        cur,
        "insert into microfinance_loans "
        "(id, loan_reference, beneficiary_id, loan_product, trade_category_id, "
        " stated_purpose_text, status, amount_disbursed, disbursed_on) values %s",
        loan_rows,
    )

    # -----------------------------------------------------------------
    # Listing text -> embeddings -> insert
    # -----------------------------------------------------------------
    print(f"{len(listing_plans)} listings -- building text and embedding in batches...")
    en_texts, ur_texts = [], []
    for _bid, _name, _district, _cluster, category_name, template, _is_women_led in listing_plans:
        # ONE shared index into en/ur so the two stay a real translation
        # pair (each template was written with en[i]/ur[i] as matching
        # phrasings -- picking independently could mismatch them).
        i = random.randrange(len(template["en"]))
        en_text, ur_text = template["en"][i], template["ur"][i]
        # SPECIALTY_SUFFIXES second diversity layer -- see that dict's
        # comment. 85%, not 100%, keeps a few identical-text pairs around
        # for exact-duplicate-handling checks.
        if category_name in SPECIALTY_SUFFIXES and random.random() < 0.85:
            en_suffix, ur_suffix = random.choice(SPECIALTY_SUFFIXES[category_name])
            en_text = f"{en_text} -- {en_suffix}"
            ur_text = f"{ur_text}، {ur_suffix}"
        en_texts.append(en_text)
        ur_texts.append(ur_text)

    BATCH = 100
    vectors = []
    for start in range(0, len(en_texts), BATCH):
        vectors.extend(embed_texts(en_texts[start:start + BATCH]))
        print(f"    embedded {min(start + BATCH, len(en_texts))}/{len(en_texts)}")

    listing_rows, participant_rows = [], []
    for (bid, name, district, cluster, category_name, template, is_women_led), en_text, ur_text, vector in zip(
        listing_plans, en_texts, ur_texts, vectors
    ):
        listing_id = str(uuid.uuid4())
        seeking = template["seeking"]
        travel_flag = template.get("travel")
        listing_rows.append((
            listing_id, bid, _generate_business_name(name, category_name),
            category_id_by_name[category_name],
            en_text, ur_text, None,  # skills_en -- not generated here, matches seed_data.py's style
            template["role"],
            seeking.get("seeking_inputs", False), seeking.get("seeking_workers", False),
            seeking.get("seeking_partner", False), seeking.get("seeking_work", False),
            template["remote"], template["physical"],
            travel_flag == "will_deliver_outside_area",
            travel_flag == "will_relocate_for_work",
            travel_flag == "will_partner_outside_district",
            is_women_led,  # from the owning beneficiary's generated gender -- an imperfect
                            # proxy, but a real signal instead of a hardcoded False that
                            # zeroed out the impact report's women_led_businesses metric.
            district, cluster, vector,
        ))
        participant_rows.append((listing_id, bid, "owner", "confirmed"))

    print(f"inserting {len(listing_rows)} store_listings + listing_participants...")
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

    n_hub = sum(1 for b in beneficiaries if b[2].startswith("+9235"))
    print(f"\nDone. {len(beneficiaries)} beneficiaries "
          f"({n_hub} balanced-coverage, {len(beneficiaries) - n_hub} random tail), "
          f"{len(loan_rows)} loans, {len(listing_rows)} listings.")


if __name__ == "__main__":
    run()
