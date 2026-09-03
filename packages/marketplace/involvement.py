"""
get_other_involvements() -- Marketplace_Spec.md section 9.4:

    "Every listing publicly shows where else that person is confirmed to
    be involved... In a network where nobody has ratings yet, existing
    involvement is real signal, and it lets someone judge availability
    before asking."
    "Only confirmed involvement is shown. Pending or in-discussion
    involvement is never displayed, since nothing has actually happened
    yet."

Nothing built this before now -- not a recomputation of an existing
signal, a genuinely new query.

WHY THIS QUERIES listing_participants, NOT primary_beneficiary_id
--------------------------------------------------------------------------
store_listings.primary_beneficiary_id only ever names ONE person, but a
venture listing can have several owners (ventures.py adds each parent's
owner(s) via listing_participants, on top of whoever created the venture
listing itself). Using primary_beneficiary_id alone would silently miss
every co-owner added that way. listing_participants (role='owner',
status='confirmed') is the complete, correct owner set for ANY listing --
a plain single-owner listing has exactly one such row too, written by
save_listing() at creation, so this one query covers both cases without
a special case for ventures.

WHY "confirmed" IS THE ONLY STATUS THIS READS
--------------------------------------------------
listing_participants.status can be other things (e.g. a pending employee
add). The spec is explicit that unconfirmed involvement must never show --
showing it would imply an outcome that hasn't actually happened.
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def get_other_involvements(listing_id: str) -> list[dict]:
    """
    For every CONFIRMED owner of listing_id, find every OTHER active
    listing they're confirmedly involved in (as owner or employee), and
    return the union -- deduplicated, excluding listing_id itself.

    Returns [] for a listing with no confirmed owners at all (shouldn't
    happen for anything save_listing() created, but a plain read like
    this should never raise over a data shape it merely doesn't expect).
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        """
        select beneficiary_id from listing_participants
        where listing_id = %s and role = 'owner' and status = 'confirmed'
        """,
        (listing_id,),
    )
    owner_ids = [row[0] for row in cur.fetchall()]
    if not owner_ids:
        cur.close()
        conn.close()
        return []

    # ::uuid[] cast required for the same reason search.py's ::vector cast
    # is: owner_ids is a plain Python list psycopg2 has no column to infer
    # a type from (unlike an INSERT's target column), so `= any(%s)` sends
    # an untyped array literal and Postgres refuses to compare it against
    # a uuid column ("operator does not exist: uuid = text"). Any bare
    # list bound into a WHERE/ANY clause in this codebase needs this same
    # explicit cast -- it's not particular to vectors or to uuids.
    cur.execute(
        """
        select distinct sl.id, sl.business_name, sl.role, lp.role as participant_role
        from listing_participants lp
        join store_listings sl on sl.id = lp.listing_id
        where lp.beneficiary_id = any(%s::uuid[])
          and lp.status = 'confirmed'
          and sl.active = true
          and sl.id <> %s
        order by sl.business_name
        """,
        (owner_ids, listing_id),
    )
    columns = [d[0] for d in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return results
