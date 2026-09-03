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
               case when mm.listing_a_id = %(listing_id)s then l_b.role else l_a.role end as role
        from marketplace_matches mm
        join store_listings l_a on l_a.id = mm.listing_a_id
        join store_listings l_b on l_b.id = mm.listing_b_id
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
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        """
        update marketplace_matches
        set status = 'dismissed', dismissed_by_listing_id = %(dismissing_listing_id)s
        where id = %(match_id)s
          and (listing_a_id = %(dismissing_listing_id)s or listing_b_id = %(dismissing_listing_id)s)
        """,
        {"match_id": match_id, "dismissing_listing_id": dismissing_listing_id},
    )
    if cur.rowcount == 0:
        conn.close()
        raise ValueError(
            f"no match {match_id} involving listing {dismissing_listing_id} -- "
            "either it doesn't exist, or this listing isn't one of its two participants"
        )
    conn.commit()
    cur.close()
    conn.close()
