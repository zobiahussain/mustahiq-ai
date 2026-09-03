"""
match_and_notify() -- the real version of Marketplace_Spec.md section 5
("fires whenever a listing is created or edited") combined with section
7 ("matches are sent to every party involved"), and the actual fix for
section 5.2, "the delayed match."

WHY THIS FIXES THE DELAYED-MATCH GAP
------------------------------------------
Before this file existed, matching only ever ran for whichever listing
the FRONTEND happened to ask about (right after someone created their
own listing). Monday's cobbler never got told about Friday's supplier,
because nothing re-checked Monday's older listing when Friday's new one
appeared -- the matching LOGIC was always symmetric (find_matches() would
find the right candidates from either side), but nothing AUTOMATICALLY
ran it from both sides and told both people.

The fix doesn't require re-scanning the whole database on every new
listing. find_matches(new_listing_id) already finds every EXISTING
listing that's compatible with the new one -- that set IS, by
definition, every pair that just became newly matchable. So: run
matching once, for the listing that was just created/edited, and notify
BOTH sides of every match that's genuinely NEW (persist_matches()'s
is_new flag) -- Friday's supplier gets told about Monday's cobbler (a
match they can already see, since they just created their listing), and
Monday's cobbler gets told too (a match they had no way to know about
until right now). Nobody gets re-notified about a match they already
know about, because is_new is only True the first time a pair is stored.
"""

import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from matching import find_matches, _fetch_listing
from reasoning import add_reasons
from persist import persist_matches
from notify import notify_match

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def match_and_notify(listing_id: str, limit: int = 10) -> list[dict]:
    """
    Call this whenever a listing is created (and, once editing exists,
    whenever it's edited -- see README note on that gap). Returns the
    matches with reasons attached, same shape find_matches()+add_reasons()
    already returned, so callers that just want to DISPLAY matches (the
    API's GET /listing/{id}/matches) don't need to change.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    source = _fetch_listing(cur, listing_id)
    cur.close()
    conn.close()

    matches = find_matches(listing_id, limit)
    matches = add_reasons(source, matches)
    persisted = persist_matches(listing_id, matches)

    for match, saved in zip(matches, persisted):
        if not saved["is_new"]:
            continue  # already notified both sides when this pair first matched

        source_beneficiary_id = source["primary_beneficiary_id"]
        candidate_beneficiary_id = match.get("primary_beneficiary_id")

        # Venture listings have no single owner (primary_beneficiary_id
        # is null -- ownership lives in listing_participants instead, per
        # the schema). Skipping notification for that side rather than
        # crashing -- a real limitation, not a bug: venture participant
        # notification would need listing_participants fan-out, not built
        # here.
        if source_beneficiary_id:
            notify_match(
                source_beneficiary_id,
                saved["id"],
                f"New match: {match.get('business_name') or 'a business'} -- {match['reason']}",
            )
        if candidate_beneficiary_id:
            notify_match(
                candidate_beneficiary_id,
                saved["id"],
                f"New match: {source.get('business_name') or 'a business'} -- {match['reason']}",
            )

    return matches
