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
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def persist_matches(source_id: str, matches: list[dict]) -> list[str]:
    """
    matches: the list find_matches() (optionally passed through
             add_reasons()) returned. 'reason' is optional -- persisted as
             null if reasoning hasn't run yet.

    Returns the list of marketplace_matches.id for the rows touched.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    ids = []
    for m in matches:
        cur.execute(
            """
            insert into marketplace_matches
                (match_model, listing_a_id, listing_b_id,
                 similarity_score, proximity_multiplier, final_score,
                 proximity_label, reason)
            values (%(match_model)s, %(source_id)s, %(candidate_id)s,
                    %(similarity)s, %(proximity_multiplier)s, %(final_score)s,
                    %(proximity_label)s, %(reason)s)
            on conflict (match_model, listing_a_id, listing_b_id)
            do update set
                similarity_score = excluded.similarity_score,
                proximity_multiplier = excluded.proximity_multiplier,
                final_score = excluded.final_score,
                proximity_label = excluded.proximity_label,
                reason = coalesce(excluded.reason, marketplace_matches.reason)
            returning id
            """,
            {
                "match_model": m["match_model"],
                "source_id": source_id,
                "candidate_id": m["id"],
                "similarity": m["similarity"],
                "proximity_multiplier": m["proximity_multiplier"],
                "final_score": m["final_score"],
                "proximity_label": m["proximity_label"],
                "reason": m.get("reason"),
            },
        )
        ids.append(cur.fetchone()[0])

    conn.commit()
    cur.close()
    conn.close()
    return ids
