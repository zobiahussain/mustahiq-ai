"""
search_listings() -- the real version of Marketplace_Spec.md section 5.3
and the schema's reference query H: a beneficiary browsing/searching the
marketplace directly, on their own terms.

WHY THIS IS A COMPLETELY SEPARATE FUNCTION FROM find_matches()
--------------------------------------------------------------------
Not a variant, not a shared code path -- deliberately separate, because
the RULES are opposite in a way that matters:

  find_matches() (matching.py) -- automatic, push-driven. Applies the
  distance-eligibility filter: a candidate who hasn't opted into
  cross-cluster reach is EXCLUDED entirely, never shown.

  search_listings() (this file) -- manual, pull-driven. NO proximity
  filter, NO willingness check, ever. Someone searching already knows
  what they want and can judge distance themselves -- a Sukkur cobbler
  searching for leather suppliers should see every supplier that exists,
  including a strong one in Hyderabad, and decide for himself whether
  the distance is worth it. Silently reusing find_matches()'s filtered
  query here would be a real bug: it would hide results a beneficiary
  explicitly asked to see.

FILTERS ARE ALL OPTIONAL AND COMBINABLE
--------------------------------------------
Every parameter below defaults to None/not-applied. Pass only the ones
someone actually picked. trade_category is matched by NAME, not id --
the frontend should never need to know or look up category ids, just
show the ten names (packages/data/reference_lists.md) and pass whichever
was picked straight through.

query_text IS OPTIONAL TOO
------------------------------
Pure filter-browsing with no search phrase at all is a valid, real use
case ("show me every supplier in Karachi") -- ranked by newest first
instead of by similarity, since there's no query vector to rank against.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))
from embeddings import embed_text  # noqa: E402

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def search_listings(
    query_text: str | None = None,
    *,
    trade_category: str | None = None,
    role: str | None = None,
    district: str | None = None,
    is_women_led: bool | None = None,
    seeking_inputs: bool | None = None,
    seeking_workers: bool | None = None,
    seeking_partner: bool | None = None,
    seeking_work: bool | None = None,
    exclude_beneficiary_id: str | None = None,
    limit: int = 20,
) -> list[dict]:
    conditions = ["l.active = true", "l.availability in ('seeking', 'open_to_offers')"]
    params: dict = {"limit": limit}

    if trade_category:
        conditions.append("tc.name = %(trade_category)s")
        params["trade_category"] = trade_category
    if role:
        conditions.append("l.role = %(role)s")
        params["role"] = role
    if district:
        conditions.append("l.district = %(district)s")
        params["district"] = district
    if is_women_led is not None:
        conditions.append("l.is_women_led = %(is_women_led)s")
        params["is_women_led"] = is_women_led
    if seeking_inputs is not None:
        conditions.append("l.seeking_inputs = %(seeking_inputs)s")
        params["seeking_inputs"] = seeking_inputs
    if seeking_workers is not None:
        conditions.append("l.seeking_workers = %(seeking_workers)s")
        params["seeking_workers"] = seeking_workers
    if seeking_partner is not None:
        conditions.append("l.seeking_partner = %(seeking_partner)s")
        params["seeking_partner"] = seeking_partner
    if seeking_work is not None:
        conditions.append("l.seeking_work = %(seeking_work)s")
        params["seeking_work"] = seeking_work
    if exclude_beneficiary_id:
        conditions.append("l.primary_beneficiary_id <> %(exclude_beneficiary_id)s")
        params["exclude_beneficiary_id"] = exclude_beneficiary_id

    where_clause = " and ".join(conditions)

    # NOTE: deliberately no cluster_id/district proximity condition
    # anywhere in this query -- see file docstring.
    #
    # ::vector cast is required here specifically -- embed_text() returns
    # a plain Python list, and psycopg2 has no way to know it should be
    # the pgvector `vector` type rather than a generic numeric array
    # unless told explicitly. INSERTs (create_listing.py, seed_data.py)
    # never needed this cast because the target COLUMN's type gives
    # Postgres that context automatically; a bare comparison like <=> in
    # a WHERE/ORDER BY has no such context to infer from.
    if query_text and query_text.strip():
        params["vec"] = embed_text(query_text)
        order_clause = "l.embedding <=> %(vec)s::vector"
        select_extra = "1 - (l.embedding <=> %(vec)s::vector) as similarity"
    else:
        order_clause = "l.created_at desc"
        select_extra = "null as similarity"

    sql = f"""
        select l.id, l.business_name, l.product_or_service_en,
               l.product_or_service_original, l.role, l.district,
               l.cluster_id, l.is_remote_capable, l.output_is_physical,
               l.is_women_led, tc.name as trade_category,
               {select_extra}
        from store_listings l
        left join trade_categories tc on tc.id = l.trade_category_id
        where {where_clause}
        order by {order_clause}
        limit %(limit)s
    """

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    results = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return results
