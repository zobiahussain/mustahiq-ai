"""
find_matches(listing_id) -- the real, callable version of the matching
pipeline described in Marketplace_Spec.md section 5. Everything up to now
was one-off scripts proving the pieces work; this is the actual function
the app calls whenever a listing is created or edited.

THE FOUR STEPS, AND WHERE EACH ONE HAPPENS
---------------------------------------------
1. Complementary-role / seeking-flag filter -- decided in Python, by
   looking at what THIS listing declared (see _directions_for() below).
2. Distance eligibility -- a real SQL WHERE-clause filter, inside each
   query below. Candidates that fail this never even reach step 3.
3. Vector similarity -- pgvector's <=> operator, in the same SQL query as
   step 2 (never fetch-then-filter-in-Python -- see CLAUDE.md hard
   constraints).
4. Proximity re-weighting -- done in Python, via proximity.py, AFTER the
   SQL has already returned only eligible candidates.

WHY MULTIPLE DIRECTIONS PER LISTING
--------------------------------------
A listing can seek more than one thing at once (seeking_inputs=true AND
seeking_workers=true is valid). And matching runs symmetrically -- when a
SUPPLIER lists, we search for everyone who already declared
seeking_inputs=true, not just the reverse (Marketplace_Spec.md section
5.2, "the delayed match"). So one call to find_matches() can run several
underlying queries, one per applicable direction, and merge the results.

WHAT THIS FUNCTION DELIBERATELY DOES NOT DO YET
----------------------------------------------------
- Does not write anything to marketplace_matches (no persistence).
- Does not call the LLM to write a plain-language reason.
- Does not send SMS/email notifications.
Those are three separate, clearly separable next steps -- kept out of
this function so each piece stays independently testable, and because
notification has no working provider wired up yet.
"""

import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from proximity import proximity_multiplier

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def _get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _fetch_listing(cur, listing_id: str) -> dict:
    cur.execute(
        """
        select id, primary_beneficiary_id, business_name, product_or_service_en, role,
               seeking_inputs, seeking_workers, seeking_partner,
               seeking_work, is_remote_capable, output_is_physical,
               will_deliver_outside_area, will_relocate_for_work,
               will_partner_outside_district,
               cluster_id, district, embedding, active
        from store_listings
        where id = %s
        """,
        (listing_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"no store_listings row with id={listing_id}")
    return dict(row)


# Each function here is ONE direction: "given this source listing, find
# candidates on the OTHER side of one matching model." Every query filters
# and ranks in the same SQL statement -- see module docstring, step 2+3.

def _search_supply_chain_suppliers(cur, source: dict, limit: int) -> list[dict]:
    """Source seeks_inputs=true -> find role='supplier' candidates."""
    cur.execute(
        """
        select id, primary_beneficiary_id, business_name, product_or_service_en, role, district, cluster_id,
               1 - (embedding <=> %(vec)s) as similarity
        from store_listings
        where active = true
          and availability in ('seeking', 'open_to_offers')
          and role = 'supplier'
          and open_request_count < max_open_requests
          and id <> %(source_id)s
          and (output_is_physical = false
               or cluster_id = %(cluster)s
               or will_deliver_outside_area = true)
        order by embedding <=> %(vec)s
        limit %(limit)s
        """,
        {"vec": source["embedding"], "source_id": source["id"],
         "cluster": source["cluster_id"], "limit": limit},
    )
    return [dict(r) | {"match_model": "supply_chain"} for r in cur.fetchall()]


def _search_supply_chain_producers(cur, source: dict, limit: int) -> list[dict]:
    """Source role='supplier' -> find seeking_inputs=true candidates."""
    cur.execute(
        """
        select id, primary_beneficiary_id, business_name, product_or_service_en, role, district, cluster_id,
               1 - (embedding <=> %(vec)s) as similarity
        from store_listings
        where active = true
          and availability in ('seeking', 'open_to_offers')
          and seeking_inputs = true
          and open_request_count < max_open_requests
          and id <> %(source_id)s
          and (%(source_output_physical)s = false
               or cluster_id = %(cluster)s
               or %(source_will_deliver)s = true)
        order by embedding <=> %(vec)s
        limit %(limit)s
        """,
        {"vec": source["embedding"], "source_id": source["id"],
         "cluster": source["cluster_id"], "limit": limit,
         "source_output_physical": source["output_is_physical"],
         "source_will_deliver": source.get("will_deliver_outside_area", False)},
    )
    return [dict(r) | {"match_model": "supply_chain"} for r in cur.fetchall()]


def _search_employment_workers(cur, source: dict, limit: int) -> list[dict]:
    """Source seeking_workers=true -> find seeking_work=true candidates."""
    cur.execute(
        """
        select id, primary_beneficiary_id, business_name, product_or_service_en, role, district, cluster_id,
               1 - (embedding <=> %(vec)s) as similarity
        from store_listings
        where active = true
          and seeking_work = true
          and availability = 'seeking'
          and open_request_count < max_open_requests
          and id <> %(source_id)s
          and (is_remote_capable = true
               or cluster_id = %(cluster)s
               or will_relocate_for_work = true)
        order by embedding <=> %(vec)s
        limit %(limit)s
        """,
        {"vec": source["embedding"], "source_id": source["id"],
         "cluster": source["cluster_id"], "limit": limit},
    )
    return [dict(r) | {"match_model": "employment"} for r in cur.fetchall()]


def _search_employment_businesses(cur, source: dict, limit: int) -> list[dict]:
    """Source seeking_work=true -> find seeking_workers=true candidates."""
    cur.execute(
        """
        select id, primary_beneficiary_id, business_name, product_or_service_en, role, district, cluster_id,
               1 - (embedding <=> %(vec)s) as similarity
        from store_listings
        where active = true
          and seeking_workers = true
          and availability in ('seeking', 'open_to_offers')
          and open_request_count < max_open_requests
          and id <> %(source_id)s
          and (%(source_remote)s = true
               or cluster_id = %(cluster)s
               or %(source_relocate)s = true)
        order by embedding <=> %(vec)s
        limit %(limit)s
        """,
        {"vec": source["embedding"], "source_id": source["id"],
         "cluster": source["cluster_id"], "limit": limit,
         "source_remote": source["is_remote_capable"],
         "source_relocate": source.get("will_relocate_for_work", False)},
    )
    return [dict(r) | {"match_model": "employment"} for r in cur.fetchall()]


def _search_joint_venture(cur, source: dict, limit: int) -> list[dict]:
    """Source seeking_partner=true -> find other seeking_partner=true candidates."""
    cur.execute(
        """
        select id, primary_beneficiary_id, business_name, product_or_service_en, role, district, cluster_id,
               1 - (embedding <=> %(vec)s) as similarity
        from store_listings
        where active = true
          and seeking_partner = true
          and availability in ('seeking', 'open_to_offers')
          and open_request_count < max_open_requests
          and id <> %(source_id)s
          and (is_remote_capable = true
               or cluster_id = %(cluster)s
               or will_partner_outside_district = true)
        order by embedding <=> %(vec)s
        limit %(limit)s
        """,
        {"vec": source["embedding"], "source_id": source["id"],
         "cluster": source["cluster_id"], "limit": limit},
    )
    return [dict(r) | {"match_model": "joint_venture"} for r in cur.fetchall()]


def find_matches(listing_id: str, limit: int = 10) -> list[dict]:
    """
    Returns candidates ranked by final_score (similarity x proximity),
    across every matching model this listing's flags make it eligible
    for. Each result: id, business_name, role, match_model, similarity,
    proximity_multiplier, proximity_label, final_score.
    """
    conn = _get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    source = _fetch_listing(cur, listing_id)

    candidates = []
    if source["seeking_inputs"]:
        candidates += _search_supply_chain_suppliers(cur, source, limit)
    if source["role"] == "supplier":
        candidates += _search_supply_chain_producers(cur, source, limit)
    if source["seeking_workers"]:
        candidates += _search_employment_workers(cur, source, limit)
    if source["seeking_work"]:
        candidates += _search_employment_businesses(cur, source, limit)
    if source["seeking_partner"]:
        candidates += _search_joint_venture(cur, source, limit)

    cur.close()
    conn.close()

    for c in candidates:
        multiplier, label = proximity_multiplier(
            source["cluster_id"], source["district"], c["cluster_id"], c["district"]
        )
        c["proximity_multiplier"] = multiplier
        c["proximity_label"] = label
        c["final_score"] = c["similarity"] * multiplier

    candidates.sort(key=lambda c: c["final_score"], reverse=True)
    return candidates[:limit]
