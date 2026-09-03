"""
notify_match() -- Marketplace_Spec.md section 7: "Matches are sent to
every party involved, by SMS and email. No phone calls."

WHY THIS IS SEPARATE FROM auth.py's _send_sms
---------------------------------------------------
Different job, different data (a match notification carries WHO to tell
them about and WHY, not a one-time code) -- and auth.py deliberately
doesn't import anything from packages/marketplace, to stay a small,
standalone, independently-testable file. Duplicating the small
stand-in-send function here is worth it for that separation.

A REAL GAP, SURFACED NOT PAPERED OVER: EMAIL ISN'T ACTUALLY POSSIBLE YET
--------------------------------------------------------------------------
The spec says "SMS and email." Checked the schema before writing this,
not assumed: `email` exists on `staff_users` only -- beneficiary_profiles
has no email column anywhere, consistent with everything else about this
module (no password, no email, phone-only login, mirrors Easypaisa/
JazzCash). So for now this is SMS-only, genuinely, not a placeholder --
there's no email address to send to even if a provider existed. If email
notification is wanted for real, it needs a real decision first: add an
email column to beneficiary_profiles (optional, since most beneficiaries
plausibly don't have one) and somewhere in the app that actually asks for
it -- neither exists today.

SAME HONEST GAP AS auth.py -- NO REAL SMS PROVIDER YET EITHER
--------------------------------------------------------------------
_send_sms() below is a clearly-labeled stand-in that prints instead of
delivering, same reasoning as auth.py's version. What IS real: a
notifications row gets written for every call, with a real body and a
real status -- so once a provider exists, only this one function's body
needs to change.
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def _send_sms(phone: str, body: str) -> bool:
    """STAND-IN -- see file docstring. Returns whether it 'sent' successfully."""
    print(f"[SMS -- NOT ACTUALLY SENT, no provider wired up] to {phone}: {body}")
    return True


def notify_match(beneficiary_id: str, match_id: str, body: str) -> None:
    """
    Writes a notifications row and attempts to send it. SMS only -- see
    file docstring on why email isn't possible yet. No phone on file
    (beneficiary has never logged in, so no beneficiary_app_accounts row
    exists) still gets recorded as a 'failed' notification -- that's real
    information (this person can't be reached yet), not nothing.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        "select phone from beneficiary_app_accounts where beneficiary_id = %s",
        (beneficiary_id,),
    )
    row = cur.fetchone()
    phone = row[0] if row else None

    status = "sent" if (phone and _send_sms(phone, body)) else "failed"
    cur.execute(
        "insert into notifications (beneficiary_id, match_id, channel, body, status, sent_at) "
        "values (%s, %s, 'sms', %s, %s, case when %s = 'sent' then now() else null end)",
        (beneficiary_id, match_id, body, status, status),
    )

    conn.commit()
    cur.close()
    conn.close()
