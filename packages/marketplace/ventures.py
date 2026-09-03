"""
form_venture() -- Marketplace_Spec.md section 9.

DESIGN CALL MADE HERE, NOT SILENTLY -- WORTH KNOWING
------------------------------------------------------------
The spec describes WHAT a venture is (a new listing, own cluster/district/
trade/role, nothing inherited, lineage recorded) but not HOW two parties
actually agree to form one. Two real options existed: a two-step
propose-then-accept flow (party A proposes, party B has to confirm before
anything happens), or a one-step flow (either party, once they've already
agreed off-app, files the paperwork themselves). Went with the SECOND:

  - Section 7 already establishes the pattern for the whole marketplace --
    "the parties connect themselves and visit a facilitation centre if
    they wish. Staff is not part of this step." Two people already had to
    find each other, talk, and decide to combine businesses BEFORE either
    one would ever call this function -- the agreement already happened
    off-app, same as every other connection in this module.
  - A propose/accept flow would be new state (a third status beyond
    active/dismissed) and a notification round-trip this module doesn't
    have anywhere else, for a decision that (per the reasoning above) is
    already made by the time anyone calls this.
  - The one real safeguard needed is making sure whoever calls this
    actually owns ONE of the listings being combined -- checked below,
    not assumed. A stranger can't file paperwork for two listings they
    have nothing to do with.

If this turns out wrong once real usage shows it, the fix is additive
(a pending-confirmation status), not a rewrite of what's here.

A VENTURE IS JUST A LISTING -- REUSES EXISTING FUNCTIONS, NOT DUPLICATED
--------------------------------------------------------------------------
The venture's own listing (business_name, trade_category, product/service,
role, district, cluster) is created the EXACT same way any listing is --
enrich_listing_text() then save_listing() (create_listing.py). This file
only handles what's SPECIFIC to a venture: linking parent listings,
recording who owns it, and freeing up each parent's own availability
status per section 9.3's table.
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def form_venture(beneficiary_id: str, venture_listing_id: str, parent_listing_ids: list[str]) -> None:
    """
    Call this AFTER creating the venture's own listing via the normal
    save_listing() flow. beneficiary_id must own at least one of
    parent_listing_ids -- checked here, never trusted from the caller,
    same reasoning as everywhere else beneficiary_id gates an action.

    Section 9.3's table: "Became a venture co-owner -> committed. His
    capacity now belongs to the venture." Applied to EVERY parent listing
    here -- not just the caller's -- since forming the venture is a joint
    fact about all the parents involved, not just whoever happened to
    click the button.
    """
    if len(parent_listing_ids) < 2:
        raise ValueError("a venture needs at least 2 parent listings to combine")
    if venture_listing_id in parent_listing_ids:
        raise ValueError("the venture listing can't be its own parent")

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    placeholders = ",".join(["%s"] * len(parent_listing_ids))
    cur.execute(
        f"select 1 from listing_participants where beneficiary_id = %s "
        f"and listing_id in ({placeholders}) and role = 'owner' and status = 'confirmed'",
        (beneficiary_id, *parent_listing_ids),
    )
    if cur.fetchone() is None:
        cur.close()
        conn.close()
        raise ValueError(
            f"beneficiary {beneficiary_id} doesn't own any of the listings being combined -- "
            "only an actual owner of one of the parent listings can form a venture from them"
        )

    for parent_id in parent_listing_ids:
        cur.execute(
            "insert into venture_lineage (venture_listing_id, parent_listing_id) values (%s, %s) "
            "on conflict (venture_listing_id, parent_listing_id) do nothing",
            (venture_listing_id, parent_id),
        )

        cur.execute(
            "select beneficiary_id from listing_participants "
            "where listing_id = %s and role = 'owner' and status = 'confirmed'",
            (parent_id,),
        )
        for (owner_id,) in cur.fetchall():
            cur.execute(
                "insert into listing_participants (listing_id, beneficiary_id, role, status) "
                "values (%s, %s, 'owner', 'confirmed') "
                "on conflict (listing_id, beneficiary_id) do nothing",
                (venture_listing_id, owner_id),
            )

        cur.execute(
            "update store_listings set availability = 'committed' where id = %s",
            (parent_id,),
        )

    conn.commit()
    cur.close()
    conn.close()
