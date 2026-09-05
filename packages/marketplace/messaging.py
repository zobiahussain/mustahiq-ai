"""
send_message() / get_messages() / get_contact_info() -- direct request,
5 Sep 2026: "there should be a chat within the marketplace... as soon as
you feel like you already established something, then they can call."

THE TWO-STAGE MODEL THIS IMPLEMENTS
--------------------------------------
Stage 1, open the moment a match exists: two matched parties can message
each other through the app -- send_message()/get_messages() below. No
phone number changes hands yet.

Stage 2, only after EITHER party marks the match connected (the existing
graduation.py:confirm_match_connection(), already wired to
POST /matches/{id}/connect -- nothing new needed there): get_contact_info()
starts returning the other party's name and phone. This is a deliberate,
explicit action -- not "after 5 messages" or some other opaque
threshold -- because the PERSON should be the one who decides "we've
established something, this is worth a phone call," not a number this
module picked for them. Same "the system does not decide" principle
Marketplace_Spec.md section 9.3 already uses for availability.

WHY get_contact_info() NEVER TOUCHES store_listings.embedding OR ANY
BROADER BENEFICIARY DATA
--------------------------------------------------------------------------
Only ever returns full_name + phone, for the SPECIFIC other party of a
SPECIFIC connected match the caller is verified to be part of. Never a
general "look up any beneficiary's phone" capability -- that would be a
real privacy hole this module has no business creating.

WHY _is_party_to_match() IS IMPORTED FROM graduation.py, NOT DUPLICATED
--------------------------------------------------------------------------
The exact same check (is this beneficiary actually one of the two
parties to this match, via store_listings.primary_beneficiary_id OR
listing_participants) already exists there, written for
confirm_match_connection(). Same reasoning as involvement.py's functions
being reused across persist.py/search.py/listings.py: one source of
truth for a security check, not a second copy that could quietly drift
out of sync with the first.
"""

import os

import psycopg2
from dotenv import load_dotenv

from graduation import _is_party_to_match

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def _fetch_match(cur, match_id: str):
    cur.execute(
        "select status, listing_a_id, listing_b_id from marketplace_matches where id = %s",
        (match_id,),
    )
    return cur.fetchone()


def send_message(match_id: str, sender_beneficiary_id: str, body: str) -> str:
    if not body or not body.strip():
        raise ValueError("message body can't be empty")

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    row = _fetch_match(cur, match_id)
    if row is None:
        cur.close()
        conn.close()
        raise ValueError(f"no match {match_id}")
    status, listing_a_id, listing_b_id = row

    if not _is_party_to_match(cur, sender_beneficiary_id, listing_a_id, listing_b_id):
        cur.close()
        conn.close()
        raise ValueError(f"beneficiary {sender_beneficiary_id} isn't a party to match {match_id}")

    cur.execute(
        "insert into match_messages (match_id, sender_beneficiary_id, body) values (%s, %s, %s) returning id",
        (match_id, sender_beneficiary_id, body.strip()),
    )
    message_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return message_id


def get_messages(match_id: str, viewer_beneficiary_id: str) -> list[dict]:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    row = _fetch_match(cur, match_id)
    if row is None:
        cur.close()
        conn.close()
        raise ValueError(f"no match {match_id}")
    status, listing_a_id, listing_b_id = row

    if not _is_party_to_match(cur, viewer_beneficiary_id, listing_a_id, listing_b_id):
        cur.close()
        conn.close()
        raise ValueError(f"beneficiary {viewer_beneficiary_id} isn't a party to match {match_id}")

    cur.execute(
        """
        select mm.id, mm.sender_beneficiary_id, mm.body, mm.sent_at,
               (mm.sender_beneficiary_id = %(viewer)s) as is_mine
        from match_messages mm
        where mm.match_id = %(match_id)s
        order by mm.sent_at
        """,
        {"viewer": viewer_beneficiary_id, "match_id": match_id},
    )
    columns = [d[0] for d in cur.description]
    results = [dict(zip(columns, r)) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return results


def get_contact_info(match_id: str, viewer_beneficiary_id: str) -> dict | None:
    """
    Returns {"full_name", "phone"} for the OTHER party, ONLY if
    status == 'connected' AND viewer_beneficiary_id is actually one of
    the two parties. Returns None otherwise -- "not connected yet" and
    "you're not part of this match" both just mean "nothing to show,"
    the caller doesn't need to distinguish them (an endpoint CAN turn
    the latter into a 403 if it wants to, by checking membership itself
    first -- this function stays a plain, safe read either way).

    Simplification, matching the one already used elsewhere in this
    module (notify.py's notify_match, matching_pipeline.py): uses each
    listing's primary_beneficiary_id, not the full listing_participants
    set -- a venture listing with several owners has no single "the
    other party's phone number," so this returns None for that side
    rather than guessing which owner to reveal.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    row = _fetch_match(cur, match_id)
    if row is None:
        cur.close()
        conn.close()
        return None
    status, listing_a_id, listing_b_id = row

    if status != "connected":
        cur.close()
        conn.close()
        return None
    if not _is_party_to_match(cur, viewer_beneficiary_id, listing_a_id, listing_b_id):
        cur.close()
        conn.close()
        return None

    cur.execute(
        "select id, primary_beneficiary_id from store_listings where id in (%s, %s)",
        (listing_a_id, listing_b_id),
    )
    listings = dict(cur.fetchall())  # {listing_id: primary_beneficiary_id}

    # "the other party" -- whichever listing's owner ISN'T the viewer
    other_beneficiary_id = None
    for listing_id, owner_id in listings.items():
        if owner_id and owner_id != viewer_beneficiary_id:
            other_beneficiary_id = owner_id
            break

    if other_beneficiary_id is None:
        cur.close()
        conn.close()
        return None

    cur.execute(
        "select full_name, phone from beneficiary_profiles where id = %s",
        (other_beneficiary_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        return None
    return {"full_name": row[0], "phone": row[1]}
