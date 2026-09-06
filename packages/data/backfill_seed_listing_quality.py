"""
One-off: fixes the listings generate_seed_data.py ALREADY inserted --
gives every one of them a real business_name (was hardcoded None,
showing as "(unnamed business)" everywhere), a real is_women_led value
(was hardcoded False), and re-rolls the description text through the
SAME template + SPECIALTY_SUFFIXES logic the generator now uses, so the
"46 distinct descriptions across 352 listings" problem gets fixed for
data that's already live, not just for a future run nobody's going to
make today. Re-embeds every changed description, since the embedding
has to match the text it was computed from.

SCOPED PRECISELY, NOT "EVERY LISTING WITH A NULL NAME"
--------------------------------------------------------------------------
Only touches listings owned by a beneficiary with the generator's own
phone marker (+9234...) -- seed_data.py's hand-curated listings also
have some null business_name/false is_women_led entries, but those were
DELIBERATE modelling choices (e.g. a freelancer with no storefront name
makes sense), not an oversight. Only the generator's output was wrong;
only the generator's output gets touched.

Run:
    cd packages/data
    ../rag/.venv/Scripts/python.exe backfill_seed_listing_quality.py
"""

import os
import random
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))
from embeddings import embed_texts  # noqa: E402

from generate_seed_data import TEMPLATES, SPECIALTY_SUFFIXES, _generate_business_name  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

random.seed(43)  # different seed from generate_seed_data.py's 42 -- deliberately NOT
                  # reproducing the exact same picks, or "more diversity" would just
                  # regenerate the same 46 combinations again


def run():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        """
        select sl.id, bp.full_name, tc.name as trade_category, sl.role
        from store_listings sl
        join beneficiary_profiles bp on bp.id = sl.primary_beneficiary_id
        join trade_categories tc on tc.id = sl.trade_category_id
        where bp.phone like '+9234%'
        """
    )
    rows = cur.fetchall()
    print(f"found {len(rows)} generator-created listings to backfill.")

    updates = []  # (id, business_name, is_women_led, en_text, ur_text)
    en_texts_to_embed = []
    for listing_id, full_name, category_name, role in rows:
        business_name = _generate_business_name(full_name, category_name)
        is_women_led = random.random() < 0.30  # not tied to a stored gender here (this
                                                 # script only has the listing's role/category,
                                                 # not the generator's in-memory is_male) --
                                                 # a plain independent draw is still a real
                                                 # signal, better than a hardcoded False

        candidates = [t for t in TEMPLATES.get(category_name, []) if t["role"] == role]
        if not candidates:
            candidates = TEMPLATES.get(category_name, [])
        if not candidates:
            updates.append((listing_id, business_name, is_women_led, None, None))
            continue
        template = random.choice(candidates)
        i = random.randrange(len(template["en"]))
        en_text = template["en"][i]
        ur_text = template["ur"][i]

        if category_name in SPECIALTY_SUFFIXES and random.random() < 0.85:
            en_suffix, ur_suffix = random.choice(SPECIALTY_SUFFIXES[category_name])
            en_text = f"{en_text} -- {en_suffix}"
            ur_text = f"{ur_text}، {ur_suffix}"

        updates.append((listing_id, business_name, is_women_led, en_text, ur_text))
        en_texts_to_embed.append((listing_id, en_text))

    print(f"embedding {len(en_texts_to_embed)} new descriptions in batches...")
    BATCH = 100
    vectors_by_id = {}
    texts_only = [t for _id, t in en_texts_to_embed]
    ids_only = [i for i, _t in en_texts_to_embed]
    for start in range(0, len(texts_only), BATCH):
        chunk = texts_only[start:start + BATCH]
        chunk_ids = ids_only[start:start + BATCH]
        vectors = embed_texts(chunk)
        for lid, vec in zip(chunk_ids, vectors):
            vectors_by_id[lid] = vec
        print(f"    embedded {min(start + BATCH, len(texts_only))}/{len(texts_only)}")

    print("applying updates...")
    updated = 0
    for listing_id, business_name, is_women_led, en_text, ur_text in updates:
        if en_text is None:
            cur.execute(
                "update store_listings set business_name = %s, is_women_led = %s where id = %s",
                (business_name, is_women_led, listing_id),
            )
        else:
            cur.execute(
                """
                update store_listings
                set business_name = %s, is_women_led = %s,
                    product_or_service_en = %s, product_or_service_original = %s,
                    embedding = %s
                where id = %s
                """,
                (business_name, is_women_led, en_text, ur_text, vectors_by_id[listing_id], listing_id),
            )
        updated += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. {updated} listings backfilled with real names and more varied descriptions.")


if __name__ == "__main__":
    run()
