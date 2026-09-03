"""
create_listing() -- the real version of what seed_data.py fakes: takes
the 5-card form's answers (Marketplace_Spec.md section 3), runs the ONE
enrichment call, computes the embedding, and saves an actual
store_listings row plus the owner's listing_participants row.

WHAT THIS DELIBERATELY DOES NOT DO
--------------------------------------
- Does not trust a caller-supplied listing owner. beneficiary_id here
  stands in for "whatever the real API extracts from a verified login
  token" -- Marketplace_Spec.md's own flow diagram is explicit that
  listing ownership comes from the JWT, never from the request body, so
  nobody can create a listing pretending to be someone else.
- Does not run find_matches() automatically. Creating a listing and
  matching it stay two separate, separately-testable steps -- chain them
  yourself (see smoke_test_create_listing.py for exactly what that looks
  like end to end).

A REAL GAP THIS FILE SURFACES, NOT SOLVES
----------------------------------------------
store_listings.cluster_id has no defined source anywhere in the current
schema. trade_category_id and district both come cleanly from the
beneficiary's existing records (their most recent qualifying loan, and
their profile) -- but nothing anywhere records which of Al-Khidmat's 53
clusters a beneficiary belongs to. Required here as an explicit
parameter rather than silently guessed or defaulted, because guessing it
wrong would silently corrupt every proximity calculation for that
listing forever. Needs a real answer -- most likely a new field on
beneficiary_profiles, populated by staff, the same shape of gap
trade_category_id was before it got added to the loan application.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))
from embeddings import embed_text  # noqa: E402
from groq_client import chat_json  # noqa: E402

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# Marketplace_Spec.md section 3.1, verbatim -- the ONE LLM call in the
# whole listing-creation flow.
ENRICHMENT_PROMPT = """
Trade category: {trade_category}
They wrote: "{raw_text}"

Return JSON:
{{
  "product_or_service_en": "expanded English description for
     semantic matching -- include the craft, typical outputs, and
     related terms a supplier or employer would search for",
  "product_or_service_original": "their exact words unchanged",
  "skills_en": "comma-separated skills in English"
}}
"""


def _fetch_beneficiary_context(cur, beneficiary_id: str) -> dict:
    """The 'already known, never asked again' fields -- section 3, GET /me/context."""
    cur.execute(
        "select district from beneficiary_profiles where id = %s", (beneficiary_id,)
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"no beneficiary_profiles row with id={beneficiary_id}")
    district = row[0]

    cur.execute(
        """
        select trade_category_id from microfinance_loans
        where beneficiary_id = %s and status in ('approved', 'disbursed')
        order by created_at desc limit 1
        """,
        (beneficiary_id,),
    )
    row = cur.fetchone()
    trade_category_id = row[0] if row else None

    return {"district": district, "trade_category_id": trade_category_id}


def create_listing(
    *,
    beneficiary_id: str,
    cluster_id: str,  # see file docstring "A REAL GAP" -- no defined source yet
    role: str,
    raw_text: str,  # card 3's free text, Urdu or English
    seeking_inputs: bool = False,
    seeking_workers: bool = False,
    seeking_partner: bool = False,
    seeking_work: bool = False,
    is_remote_capable: bool = False,  # card 4, plain tap, never LLM-touched
    output_is_physical: bool = True,  # card 4, plain tap, never LLM-touched
    will_deliver_outside_area: bool = False,
    will_relocate_for_work: bool = False,
    will_partner_outside_district: bool = False,
    monthly_capacity: str | None = None,
    price_range: str | None = None,
    business_name: str | None = None,
    is_women_led: bool = False,
) -> str:
    """Returns the new listing's id."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    context = _fetch_beneficiary_context(cur, beneficiary_id)
    if context["trade_category_id"] is None:
        # Should never actually reach here -- the app itself must not offer
        # listing creation to a beneficiary the eligibility gate already
        # excluded. This check exists so a bug elsewhere fails loudly here
        # instead of silently writing a listing nobody should have gotten to.
        raise ValueError(
            f"beneficiary {beneficiary_id} has no qualifying trade category -- "
            "see al_khidmat_marketplace_schema.sql reference query G"
        )

    cur.execute(
        "select name from trade_categories where id = %s",
        (context["trade_category_id"],),
    )
    trade_category_name = cur.fetchone()[0]

    enrichment = chat_json(
        ENRICHMENT_PROMPT.format(trade_category=trade_category_name, raw_text=raw_text)
    )

    # Embed product_or_service_en alone, UNLESS this is an employment
    # listing (seeking_work) -- then fold skills in too, since that's what
    # an employer's search actually matches against. See
    # store_listings.embedding's column comment in the schema for this
    # same rule stated there.
    text_to_embed = enrichment["product_or_service_en"]
    if seeking_work and enrichment.get("skills_en"):
        text_to_embed += ". Skills: " + enrichment["skills_en"]
    vector = embed_text(text_to_embed)

    cur.execute(
        """
        insert into store_listings
            (primary_beneficiary_id, business_name, trade_category_id,
             product_or_service_en, product_or_service_original, skills_en,
             role, seeking_inputs, seeking_workers, seeking_partner, seeking_work,
             is_remote_capable, output_is_physical,
             will_deliver_outside_area, will_relocate_for_work,
             will_partner_outside_district, is_women_led,
             monthly_capacity, price_range, district, cluster_id, embedding)
        values
            (%(beneficiary_id)s, %(business_name)s, %(trade_category_id)s,
             %(product_or_service_en)s, %(product_or_service_original)s, %(skills_en)s,
             %(role)s, %(seeking_inputs)s, %(seeking_workers)s, %(seeking_partner)s, %(seeking_work)s,
             %(is_remote_capable)s, %(output_is_physical)s,
             %(will_deliver_outside_area)s, %(will_relocate_for_work)s,
             %(will_partner_outside_district)s, %(is_women_led)s,
             %(monthly_capacity)s, %(price_range)s, %(district)s, %(cluster_id)s, %(embedding)s)
        returning id
        """,
        {
            "beneficiary_id": beneficiary_id,
            "business_name": business_name,
            "trade_category_id": context["trade_category_id"],
            "product_or_service_en": enrichment["product_or_service_en"],
            "product_or_service_original": enrichment["product_or_service_original"],
            "skills_en": enrichment.get("skills_en"),
            "role": role,
            "seeking_inputs": seeking_inputs,
            "seeking_workers": seeking_workers,
            "seeking_partner": seeking_partner,
            "seeking_work": seeking_work,
            "is_remote_capable": is_remote_capable,
            "output_is_physical": output_is_physical,
            "will_deliver_outside_area": will_deliver_outside_area,
            "will_relocate_for_work": will_relocate_for_work,
            "will_partner_outside_district": will_partner_outside_district,
            "is_women_led": is_women_led,
            "monthly_capacity": monthly_capacity,
            "price_range": price_range,
            "district": context["district"],
            "cluster_id": cluster_id,
            "embedding": vector,
        },
    )
    listing_id = cur.fetchone()[0]

    # listing_participants row for the owner -- schema section 6/7:
    # "one row per person per listing"
    cur.execute(
        """
        insert into listing_participants (listing_id, beneficiary_id, role, status)
        values (%s, %s, 'owner', 'confirmed')
        """,
        (listing_id, beneficiary_id),
    )

    conn.commit()
    cur.close()
    conn.close()
    return listing_id
