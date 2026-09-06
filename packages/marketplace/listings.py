"""
set_availability() -- Marketplace_Spec.md section 8:

    "A listing carries an availability status the person controls."

Until now, availability was READ everywhere (matching.py's filters,
search.py, logistics.py all check `availability in ('seeking',
'open_to_offers')`) but the only thing that ever WROTE it was
ventures.py's automatic flip to 'committed' on venture formation. The
spec is explicit that this is something the PERSON controls -- so this
file is the missing write path: the one place a beneficiary can actually
set their own listing to open_to_offers or committed themselves (e.g. "I
just took on a big order, don't send me new supply-chain requests for a
while"), or set it back to seeking.

WHY THIS CHECKS OWNERSHIP THE SAME WAY dismiss_match()/ventures.py DO
--------------------------------------------------------------------------
Same "never trust the caller" rule used everywhere else in this module --
beneficiary_id comes from the verified JWT (services/api layer), but
THIS function still re-checks that beneficiary_id actually owns
listing_id via listing_participants, rather than assuming the API layer
already did. A function that touches the database is responsible for its
own invariants, not just whatever called it correctly this one time.
"""

import os

import psycopg2
from dotenv import load_dotenv

from involvement import get_other_involvements
from photos import list_photos

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

VALID_AVAILABILITY = ("seeking", "open_to_offers", "committed")


def set_availability(beneficiary_id: str, listing_id: str, availability: str) -> None:
    if availability not in VALID_AVAILABILITY:
        raise ValueError(
            f"invalid availability '{availability}' -- must be one of {VALID_AVAILABILITY}"
        )

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        """
        select 1 from listing_participants
        where listing_id = %s and beneficiary_id = %s
          and role = 'owner' and status = 'confirmed'
        """,
        (listing_id, beneficiary_id),
    )
    if cur.fetchone() is None:
        cur.close()
        conn.close()
        raise ValueError(
            f"beneficiary {beneficiary_id} is not a confirmed owner of listing {listing_id}"
        )

    cur.execute(
        "update store_listings set availability = %s where id = %s",
        (availability, listing_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_listing_detail(listing_id: str, viewer_beneficiary_id: str | None = None) -> dict | None:
    """
    Added 5 Sep 2026 -- direct request: "I should be able to click on my
    listing... and see their details as well. There should not be just a
    tab." No dedicated "one listing's full detail" read existed anywhere
    before this -- search.py and persist.py both return partial,
    list-shaped rows for a page of many listings; this is the one full
    detail, for one specific listing_id.

    Returns None if the listing doesn't exist (or isn't active) --
    callers turn that into a 404, this function just reports the fact.

    viewer_beneficiary_id is optional -- when given, the response
    includes is_owner, so the frontend can decide whether to show
    owner-only controls (edit availability, upload a photo) without a
    second round trip.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        """
        select sl.id, sl.business_name, sl.role, tc.name as trade_category,
               sl.product_or_service_en, sl.product_or_service_original,
               sl.skills_en, sl.skills_original,
               sl.monthly_capacity, sl.price_range,
               sl.district, sl.cluster_id, sl.city,
               sl.seeking_inputs, sl.seeking_workers, sl.seeking_partner, sl.seeking_work,
               sl.is_remote_capable, sl.output_is_physical,
               sl.will_deliver_outside_area, sl.will_relocate_for_work, sl.will_partner_outside_district,
               sl.is_women_led, sl.availability, sl.created_at
        from store_listings sl
        left join trade_categories tc on tc.id = sl.trade_category_id
        where sl.id = %s and sl.active = true
        """,
        (listing_id,),
    )
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        return None
    columns = [d[0] for d in cur.description]
    detail = dict(zip(columns, row))

    is_owner = False
    if viewer_beneficiary_id:
        cur.execute(
            """
            select 1 from listing_participants
            where listing_id = %s and beneficiary_id = %s
              and role = 'owner' and status = 'confirmed'
            """,
            (listing_id, viewer_beneficiary_id),
        )
        is_owner = cur.fetchone() is not None

    detail["is_owner"] = is_owner
    # conn=conn (not left to open their own) -- these two used to each
    # open a fresh connection, meaning ONE page load paid the ~seconds-
    # per-connect tax THREE times over. Fixed 5 Sep 2026, caught directly
    # from "it's taking so long to open." See photos.py:list_photos()'s
    # docstring for the same fix's full reasoning.
    detail["other_involvements"] = get_other_involvements(listing_id, conn=conn)
    detail["photos"] = list_photos(listing_id, conn=conn)

    cur.close()
    conn.close()
    return detail
