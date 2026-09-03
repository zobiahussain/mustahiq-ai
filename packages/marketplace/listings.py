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
