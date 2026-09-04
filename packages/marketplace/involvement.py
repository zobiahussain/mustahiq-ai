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

WHY THIS TAKES AN OPTIONAL conn (NOT A CURSOR) -- ADDED 5 SEP 2026, A REAL PERF BUG
--------------------------------------------------------------------------------------
Callers that show a LIST of listings (get_stored_matches() in persist.py,
search_listings() in search.py) call this once PER ROW -- 20 search
results means 20 calls. The original version always opened its own fresh
psycopg2.connect() per call, which is normally a minor inefficiency
(connection setup is cheap on a local/pooled DB) -- but turned out to be
a REAL, SEVERE bug here specifically: this project's DATABASE_URL points
at Supabase's DIRECT connection host, which resolves to an IPv6-only
address, and on this network a fresh TCP connect to it takes roughly
9.6 SECONDS (confirmed by direct measurement -- not a guess). A 20-row
search page was opening 20 of those, serially, on top of the 1 the main
search query already needed -- around 96 seconds for one search.

Passing an already-open CONNECTION in from the caller (see
persist.py/search.py) means all N involvement lookups for one request
reuse ONE connection instead of opening N. This takes a connection, not
a cursor, DELIBERATELY: search.py's own cursor is a RealDictCursor
(rows come back as dicts), but this file's queries are written
tuple-style (`row[0]`, `dict(zip(columns, row))`) -- silently handed a
RealDictCursor, `row[0]` would raise KeyError (a RealDictRow has no
integer keys) and `zip(columns, row)` would zip against the row's KEYS,
not its values, since iterating a dict yields keys. Opening a fresh
PLAIN cursor from the shared connection (conn.cursor(), no
cursor_factory) sidesteps this entirely -- cheap, since it's just a new
client-side cursor object, not a new TCP connection -- and this function
never has to know or care what cursor style its caller prefers.

This is a real fix, but not the whole story -- reusing one connection
turned "N ~9.6s connects" into "N+1 sequential queries on one
connection," and on THIS network even a single query round-trip to
Supabase carries real latency (tens to a couple hundred ms), so 41
sequential queries for a 20-row search still added up to several
seconds. get_other_involvements_batch() below is the actual fix for
THAT: 2 queries total, for any number of listings, instead of 2 per
listing. Use it for anything showing a LIST (persist.py, search.py);
keep get_other_involvements() (singular) for a genuine one-listing
lookup, if something ever needs just that.
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def get_other_involvements(listing_id: str, conn=None) -> list[dict]:
    """
    For every CONFIRMED owner of listing_id, find every OTHER active
    listing they're confirmedly involved in (as owner or employee), and
    return the union -- deduplicated, excluding listing_id itself.

    conn: an already-open psycopg2 CONNECTION to run this on (a fresh
    plain cursor is opened from it, regardless of what cursor_factory
    the caller's own cursor uses -- see file docstring). If omitted,
    this function opens and closes its own connection -- fine for a
    single standalone call, but NEVER call it this way inside a loop
    over many listings (see the file docstring's "real perf bug" note --
    that's exactly the mistake that caused it).

    Returns [] for a listing with no confirmed owners at all (shouldn't
    happen for anything save_listing() created, but a plain read like
    this should never raise over a data shape it merely doesn't expect).
    """
    owns_connection = conn is None
    if owns_connection:
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
        if owns_connection:
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
    if owns_connection:
        conn.close()
    return results


def get_other_involvements_batch(listing_ids: list[str], conn=None) -> dict[str, list[dict]]:
    """
    Same result as calling get_other_involvements() once per id in
    listing_ids, but as exactly 2 queries total instead of up to 2*N --
    see the file docstring's "not the whole story" note for why that
    matters here specifically (real per-query network latency, not just
    connection setup). Returns {listing_id: [...]}; an id with no
    confirmed owners (or that just wasn't in listing_ids) maps to [].

    HOW THE COLLAPSE WORKS
    --------------------------
    Query 1 gets EVERY (listing_id, owner beneficiary_id) pair for ALL
    requested listings at once, instead of one listing at a time. Query 2
    gets EVERY confirmed involvement for the UNION of all those owner
    ids, also at once. Everything after that -- matching each listing
    back to its owners' involvements, deduplicating, excluding the
    listing itself -- happens in Python over data already in memory, not
    in further round trips.
    """
    if not listing_ids:
        return {}

    owns_connection = conn is None
    if owns_connection:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        """
        select listing_id, beneficiary_id from listing_participants
        where listing_id = any(%s::uuid[]) and role = 'owner' and status = 'confirmed'
        """,
        (listing_ids,),
    )
    owners_by_listing: dict[str, list[str]] = {}
    all_owner_ids: set[str] = set()
    for listing_id, beneficiary_id in cur.fetchall():
        owners_by_listing.setdefault(listing_id, []).append(beneficiary_id)
        all_owner_ids.add(beneficiary_id)

    if not all_owner_ids:
        cur.close()
        if owns_connection:
            conn.close()
        return {lid: [] for lid in listing_ids}

    cur.execute(
        """
        select distinct lp.beneficiary_id, sl.id, sl.business_name, sl.role, lp.role as participant_role
        from listing_participants lp
        join store_listings sl on sl.id = lp.listing_id
        where lp.beneficiary_id = any(%s::uuid[])
          and lp.status = 'confirmed'
          and sl.active = true
        order by sl.business_name
        """,
        (list(all_owner_ids),),
    )
    involvements_by_owner: dict[str, list[dict]] = {}
    for beneficiary_id, sl_id, business_name, role, participant_role in cur.fetchall():
        involvements_by_owner.setdefault(beneficiary_id, []).append(
            {"id": sl_id, "business_name": business_name, "role": role, "participant_role": participant_role}
        )
    cur.close()
    if owns_connection:
        conn.close()

    result: dict[str, list[dict]] = {}
    for listing_id in listing_ids:
        seen_ids: set[str] = set()
        deduped: list[dict] = []
        for owner_id in owners_by_listing.get(listing_id, []):
            for involvement in involvements_by_owner.get(owner_id, []):
                if involvement["id"] == listing_id or involvement["id"] in seen_ids:
                    continue
                seen_ids.add(involvement["id"])
                deduped.append(involvement)
        result[listing_id] = deduped
    return result
