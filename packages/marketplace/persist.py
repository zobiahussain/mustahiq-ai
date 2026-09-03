"""
persist_matches() -- saves the output of find_matches() + add_reasons()
into the real marketplace_matches table, so results survive after the
script that computed them ends.

WHY THIS HAS TO BE IDEMPOTENT (a concept worth naming, not just a detail)
--------------------------------------------------------------------------
"Idempotent" means: running the same operation twice has the same effect
as running it once. That matters here because matching re-runs every time
a listing is edited (Marketplace_Spec.md section 5: "fires whenever a
listing is created or edited") -- so the SAME pair of listings will get
matched again and again over time as either side edits their listing.
Without idempotency, every re-run would either crash (the schema's
`unique (match_model, listing_a_id, listing_b_id)` constraint would
reject the duplicate) or silently pile up duplicate rows. Instead we
UPSERT: insert if the pair has never matched before, update the score if
it has.

FIXED 4 SEP 2026 -- A REAL BUG THE ORIGINAL VERSION HAD
------------------------------------------------------------
The schema's unique constraint is on (match_model, listing_a_id,
listing_b_id) EXACTLY as ordered -- it does NOT know that (A, B) and
(B, A) are the same conceptual pair. The original version always put
`source_id` in listing_a_id, which was harmless as long as matching only
ever ran from one side. It stops being harmless the moment matching runs
automatically for BOTH sides over time (Amina's listing matches Zainab's
-> (A=Amina, B=Zainab); later Zainab's own listing gets matched too ->
would insert (A=Zainab, B=Amina), a SECOND row for the same real-world
pair. Fixed by canonicalizing: whichever listing id sorts first,
alphabetically, always goes in listing_a_id, regardless of which side
triggered the match. Now the same pair always resolves to the same row
no matter which side's creation/edit triggered the search.

WHAT UPSERT DELIBERATELY DOES NOT TOUCH
--------------------------------------------
Only the scoring fields (similarity, proximity, final_score, reason) get
refreshed on a repeat match. status, dismissed_by_listing_id, and
expires_at are NEVER overwritten by this function -- those belong to
separate actions (someone dismissing a match, a match expiring, the daily
sweep). If we blindly overwrote status on every re-run, a match someone
already dismissed could silently reappear the next time either listing
gets edited -- directly against Marketplace_Spec.md's "a dismissed pair
never resurfaces."

WHY THIS RETURNS is_new PER MATCH NOW
------------------------------------------
The delayed-match notification trigger (matching_pipeline.py) needs to
know which matches are genuinely NEW -- notifying both parties every
time a listing is merely re-scored (someone edits an unrelated field)
would be spam, not a delayed-match notification. `(xmax = 0)` is
Postgres's standard idiom for "this row was just INSERTed, not UPDATEd"
inside a RETURNING clause on an ON CONFLICT statement -- xmax is an
internal column Postgres uses for its own MVCC bookkeeping; it's 0 on a
freshly inserted row and non-zero once any update has touched it.

open_request_count IS INCREMENTED HERE, ON EVERY NEW MATCH -- FOUND MISSING 4 SEP 2026
--------------------------------------------------------------------------------------------
Marketplace_Spec.md section 8's rate-limit backstop (a listing stops
surfacing once it has more than 5 open, unanswered requests) was
implemented as a filter in every matching.py query (`open_request_count
< max_open_requests`) -- but nothing anywhere ever INCREMENTED that
counter, so it sat at its schema default (0) forever and the filter was
a silent no-op. A new match IS an open, unanswered request for both
sides -- so it increments here, for both listing_a_id and listing_b_id,
exactly once, only when is_new (never on a re-score of an existing
match). It's decremented in dismiss_match() and expire_stale_matches()
(lifecycle.py) -- whichever ends a match's 'active' status frees the slot
back up.
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def persist_matches(source_id: str, matches: list[dict]) -> list[dict]:
    """
    matches: the list find_matches() (optionally passed through
             add_reasons()) returned. 'reason' is optional -- persisted as
             null if reasoning hasn't run yet.

    Returns one dict per match: {"id", "listing_a_id", "listing_b_id",
    "is_new"} -- is_new is True only the first time this exact pair was
    ever stored.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    results = []
    for m in matches:
        # canonical order -- see file docstring "FIXED 4 SEP 2026"
        listing_a_id, listing_b_id = sorted([source_id, m["id"]])

        cur.execute(
            """
            insert into marketplace_matches
                (match_model, listing_a_id, listing_b_id,
                 similarity_score, proximity_multiplier, final_score,
                 proximity_label, reason)
            values (%(match_model)s, %(listing_a_id)s, %(listing_b_id)s,
                    %(similarity)s, %(proximity_multiplier)s, %(final_score)s,
                    %(proximity_label)s, %(reason)s)
            on conflict (match_model, listing_a_id, listing_b_id)
            do update set
                similarity_score = excluded.similarity_score,
                proximity_multiplier = excluded.proximity_multiplier,
                final_score = excluded.final_score,
                proximity_label = excluded.proximity_label,
                reason = coalesce(excluded.reason, marketplace_matches.reason)
            returning id, (xmax = 0) as is_new
            """,
            {
                "match_model": m["match_model"],
                "listing_a_id": listing_a_id,
                "listing_b_id": listing_b_id,
                "similarity": m["similarity"],
                "proximity_multiplier": m["proximity_multiplier"],
                "final_score": m["final_score"],
                "proximity_label": m["proximity_label"],
                "reason": m.get("reason"),
            },
        )
        row_id, is_new = cur.fetchone()
        results.append({
            "id": row_id,
            "listing_a_id": listing_a_id,
            "listing_b_id": listing_b_id,
            "is_new": is_new,
        })

        if is_new:
            cur.execute(
                "update store_listings set open_request_count = open_request_count + 1 "
                "where id in (%s, %s)",
                (listing_a_id, listing_b_id),
            )

    conn.commit()
    cur.close()
    conn.close()
    return results


def get_stored_matches(listing_id: str) -> list[dict]:
    """
    A plain READ of what's already in marketplace_matches for this
    listing -- no recomputation, no fresh embeddings, no fresh Groq
    calls. This is what a "my matches" screen should call, NOT
    match_and_notify() again -- match_and_notify() already ran once, at
    creation (or whenever this listing was last edited), and persisted
    everything. Re-running it every time someone just wants to LOOK at
    their matches would burn Groq calls for nothing new.

    It also naturally shows delayed matches (Marketplace_Spec.md 5.2):
    if someone else's later listing matched this one, THEIR
    match_and_notify() call already wrote the row here (canonical
    ordering means it doesn't matter which side's listing_id this query
    filters on) -- opening this screen sees it immediately, no need to
    re-trigger anything from this listing's own side.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        """
        select mm.id, mm.match_model, mm.final_score, mm.proximity_label,
               mm.reason, mm.status,
               case when mm.listing_a_id = %(listing_id)s then l_b.id else l_a.id end as other_id,
               case when mm.listing_a_id = %(listing_id)s then l_b.business_name else l_a.business_name end as business_name,
               case when mm.listing_a_id = %(listing_id)s then l_b.role else l_a.role end as role,
               logi.business_name as suggested_logistics_business_name
        from marketplace_matches mm
        join store_listings l_a on l_a.id = mm.listing_a_id
        join store_listings l_b on l_b.id = mm.listing_b_id
        left join store_listings logi on logi.id = mm.suggested_logistics_id
        where (mm.listing_a_id = %(listing_id)s or mm.listing_b_id = %(listing_id)s)
          and mm.status = 'active'
        order by mm.final_score desc
        """,
        {"listing_id": listing_id},
    )
    columns = [d[0] for d in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return results


def dismiss_match(match_id: str, dismissing_listing_id: str) -> None:
    """
    Marketplace_Spec.md section 7: "Either side may dismiss a match, and
    that pair never resurfaces." Setting status='dismissed' is exactly
    why persist_matches()'s upsert deliberately never touches status --
    if it did, the next time either listing gets edited, the re-run
    would silently flip a dismissed match back to active.

    Only lets one of the actual two participants dismiss it -- checked
    here, not left to whoever calls this, same "never trust the caller"
    reasoning as beneficiary_id coming from a verified token everywhere
    else in this codebase.

    Also decrements open_request_count for both listings -- see
    persist_matches()'s note on why that counter has to move in both
    directions, not just up.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        """
        update marketplace_matches
        set status = 'dismissed', dismissed_by_listing_id = %(dismissing_listing_id)s
        where id = %(match_id)s
          and (listing_a_id = %(dismissing_listing_id)s or listing_b_id = %(dismissing_listing_id)s)
        returning listing_a_id, listing_b_id
        """,
        {"match_id": match_id, "dismissing_listing_id": dismissing_listing_id},
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise ValueError(
            f"no match {match_id} involving listing {dismissing_listing_id} -- "
            "either it doesn't exist, or this listing isn't one of its two participants"
        )
    listing_a_id, listing_b_id = row
    cur.execute(
        "update store_listings set open_request_count = greatest(open_request_count - 1, 0) "
        "where id in (%s, %s)",
        (listing_a_id, listing_b_id),
    )
    conn.commit()
    cur.close()
    conn.close()
