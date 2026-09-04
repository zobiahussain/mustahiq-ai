"""
Four scheduled/triggered operations, none of which had any code before
this file: expiring stale matches and stale listings (Marketplace_Spec.md
sections 7 and 10), deactivating a listing when its owner's loan
defaults (section 2 / schema reference query J), and sending the
marketplace invitation SMS when a loan is recorded with a trade category
(section 2, "the invitation problem" / marketplace_invitations table).

WHY THESE ARE PLAIN FUNCTIONS, NOT ACTUAL CRON JOBS
--------------------------------------------------------
expire_stale_matches() and expire_stale_listings() are meant to run on a
schedule (Render cron, per CLAUDE.md's stack table) -- that's a
deployment-time concern, not something this local dev environment can
set up. What CAN happen here is making sure the function they'd call
actually exists and works, so wiring up the schedule later is a one-line
Render config, not a missing feature. See services/api/README.md for the
deploy note once these get an entrypoint.

deactivate_listings_for_defaulted_loan() and
send_invitation_if_eligible() are meant to be called by whatever writes
to microfinance_loans -- in production, Al-Khidmat's own loan system (the
schema's own note: "populated by Al-Khidmat's existing loan system").
Nothing in this codebase writes loan rows except seed_data.py, so these
are called from there for the demo, standing in for that real caller.
"""

import hashlib
import os
import secrets

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def expire_stale_matches() -> int:
    """
    Schema reference query E. A match nobody responded to in 7 days
    (marketplace_matches.expires_at, set at insert time) stops being
    active -- "so nobody waits indefinitely," per section 7. Also frees
    the open_request_count slot on both sides, same reasoning as
    dismiss_match() -- an expired request isn't open anymore either.
    Returns how many were expired, so a cron log line has something
    real to report.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        """
        update marketplace_matches
        set status = 'expired'
        where status = 'active' and expires_at < now()
        returning listing_a_id, listing_b_id
        """
    )
    rows = cur.fetchall()
    for listing_a_id, listing_b_id in rows:
        cur.execute(
            "update store_listings set open_request_count = greatest(open_request_count - 1, 0) "
            "where id in (%s, %s)",
            (listing_a_id, listing_b_id),
        )
    conn.commit()
    cur.close()
    conn.close()
    return len(rows)


def expire_stale_listings() -> int:
    """
    Marketplace_Spec.md section 10: "Listings expire after six months
    unless confirmed, so dead listings clean themselves up rather than
    accumulating." store_listings.expires_at already defaults to
    (created_at + 6 months) at the schema level -- this just acts on it.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        "update store_listings set active = false "
        "where active = true and expires_at < current_date "
        "returning id"
    )
    count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return count


def deactivate_listings_for_defaulted_loan(loan_id: str) -> int:
    """
    Schema reference query J. Call this whenever a microfinance_loans row
    is updated to status='defaulted'. Only deactivates listings this
    beneficiary owns SOLO (primary_beneficiary_id) -- a venture
    listing_participants row for a defaulted co-owner is deliberately
    left alone, same scoping note as the schema's own reference query.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        """
        update store_listings
        set active = false
        where primary_beneficiary_id = (
            select beneficiary_id from microfinance_loans where id = %s
        )
        and active = true
        returning id
        """,
        (loan_id,),
    )
    count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return count


def send_invitation_if_eligible(loan_id: str) -> bool:
    """
    Marketplace_Spec.md section 2, "the invitation problem." Call this
    right after a microfinance_loans row is written (insert or update) --
    it's a no-op unless trade_category_id is actually set, so it's safe
    to call unconditionally on every loan write rather than needing the
    caller to pre-check.

    Same honest stand-in pattern as auth.py/notify.py: no real SMS
    provider, so this prints instead of sending, but a real
    marketplace_invitations row is written either way.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        "select ml.trade_category_id, bp.phone from microfinance_loans ml "
        "join beneficiary_profiles bp on bp.id = ml.beneficiary_id "
        "where ml.id = %s",
        (loan_id,),
    )
    row = cur.fetchone()
    if row is None or row[0] is None:
        cur.close()
        conn.close()
        return False  # no qualifying trade category -- nothing to invite them to

    _, phone = row

    code = "".join(secrets.choice("0123456789") for _ in range(6))
    code_hash = hashlib.sha256(code.encode()).hexdigest()

    cur.execute(
        "insert into marketplace_invitations (microfinance_loan_id, code_hash, sent_at) "
        "values (%s, %s, now())",
        (loan_id, code_hash),
    )
    conn.commit()
    cur.close()
    conn.close()

    print(
        f"[SMS -- NOT ACTUALLY SENT, no provider wired up] to {phone}: "
        f"You can now list your business on the Al-Khidmat marketplace. Your code is {code}."
    )
    return True
