"""
Re-validates every ACTIVE marketplace_matches row against the CURRENT
quality-floor thresholds in matching.py, and dismisses (never deletes)
any that no longer clear them.

WHY THIS SCRIPT NEEDS TO EXIST AT ALL
--------------------------------------------------------------------------
persist_matches() is a pure upsert -- see its own docstring. It inserts a
match the first time find_matches() surfaces a pair, and updates the
score if that same pair is found again. It never goes the other
direction: if a threshold gets stricter (like EMPLOYMENT_STRONG_
SIMILARITY going 0.55 -> 0.70 on 6 Sep 2026), every row that was
persisted under the OLD, looser gate just... stays active. Nothing
re-checks it, because nothing re-runs find_matches() for an existing
pair unless one side happens to edit their listing.

Confirmed directly, not assumed: querying marketplace_matches after
tonight's threshold raise turned up 56 cross-category employment matches
still marked active, every single one scored BELOW the current 0.70 gate
(0.41-0.56) -- exactly the "Fatima Farms for a clay-jewelry maker" shape
of bad match the gate exists to prevent, still live because they were
saved on 3-5 Sep, before the fix.

WHY DISMISSED, NOT DELETED
--------------------------------------------------------------------------
'dismissed' already exists in marketplace_matches.status precisely for
"this pair should stop surfacing" -- reusing it means every other place
that reads matches (get_stored_matches's `status = 'active'` filter)
already does the right thing with zero code changes. Deleting would lose
the fact that this pairing was ever computed, and blocks confirming a
cleanup actually happened. `dismissed_by_listing_id` is left NULL,
deliberately -- that column means a specific beneficiary chose to
decline the other side (Marketplace_Spec.md §7); setting it to either
listing here would misrepresent a system-driven re-validation as a
personal choice neither business actually made.

WHY THIS IS SAFE TO RE-RUN, AND SAFE GOING FORWARD
--------------------------------------------------------------------------
Only ever touches rows with status='active' -- already-dismissed/
connected/expired rows are left alone. And because find_matches()'s SQL
already applies these same thresholds as WHERE clauses, a pair this
script dismisses can never be silently re-activated by persist_matches()
either -- find_matches() would not return it in the first place.

Run:
    cd packages/marketplace
    ../rag/.venv/Scripts/python.exe retire_stale_matches.py            # dry run, reports only
    ../rag/.venv/Scripts/python.exe retire_stale_matches.py --apply    # actually dismisses
"""

import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from matching import MIN_SIMILARITY, EMPLOYMENT_STRONG_SIMILARITY

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def find_stale_matches(cur) -> list[dict]:
    """
    Every active match, joined back to its two listings' current
    trade_category_id -- everything find_matches()'s SQL filters need,
    re-evaluated in Python here since we're checking already-PERSISTED
    rows, not running a fresh vector search.
    """
    cur.execute(
        """
        select mm.id, mm.match_model, mm.similarity_score,
               la.business_name as a_name, la.trade_category_id as a_category,
               lb.business_name as b_name, lb.trade_category_id as b_category
        from marketplace_matches mm
        join store_listings la on la.id = mm.listing_a_id
        join store_listings lb on lb.id = mm.listing_b_id
        where mm.status = 'active'
        """
    )
    rows = cur.fetchall()

    stale = []
    for r in rows:
        sim = float(r["similarity_score"])

        # Global floor -- every model, no exceptions.
        if sim < MIN_SIMILARITY:
            stale.append({**r, "reason": f"below global floor ({sim:.3f} < {MIN_SIMILARITY})"})
            continue

        # Employment's extra gate: same category, or a much higher bar.
        if r["match_model"] == "employment" and r["a_category"] != r["b_category"]:
            if sim < EMPLOYMENT_STRONG_SIMILARITY:
                stale.append({
                    **r,
                    "reason": f"cross-category employment below strong-similarity gate "
                              f"({sim:.3f} < {EMPLOYMENT_STRONG_SIMILARITY})",
                })

    return stale


def run(apply: bool):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    stale = find_stale_matches(cur)
    print(f"{len(stale)} active match(es) no longer clear the current quality floor:\n")
    for s in stale:
        print(f"  [{s['match_model']}] {s['a_name']} <-> {s['b_name']} "
              f"(similarity={s['similarity_score']:.3f}) -- {s['reason']}")

    if not stale:
        cur.close()
        conn.close()
        return

    if not apply:
        print(f"\nDry run -- nothing changed. Re-run with --apply to dismiss these {len(stale)}.")
        cur.close()
        conn.close()
        return

    plain_cur = conn.cursor()
    ids = [s["id"] for s in stale]
    plain_cur.execute(
        "update marketplace_matches set status = 'dismissed' where id = any(%s::uuid[])",
        (ids,),
    )
    # Same open_request_count symmetry dismiss_match() already maintains
    # for a beneficiary-initiated dismiss -- these matches stop counting
    # against either listing's rate limit too.
    plain_cur.execute(
        """
        update store_listings set open_request_count = greatest(open_request_count - 1, 0)
        where id in (
            select listing_a_id from marketplace_matches where id = any(%s::uuid[])
            union
            select listing_b_id from marketplace_matches where id = any(%s::uuid[])
        )
        """,
        (ids, ids),
    )
    conn.commit()
    plain_cur.close()
    cur.close()
    conn.close()
    print(f"\nDismissed {len(stale)} stale match(es). Left `dismissed_by_listing_id` null -- "
          "a system re-validation, not a beneficiary's choice.")


if __name__ == "__main__":
    run(apply="--apply" in sys.argv)
