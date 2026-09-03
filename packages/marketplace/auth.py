"""
request_otp() / verify_otp() -- the real version of Marketplace_Spec.md
section 2.1 and the schema's reference query G. This is the actual front
door: nothing else in the app (creating a listing, seeing matches) can
happen before this.

ONE HONEST GAP: NO SMS PROVIDER IS WIRED UP YET
----------------------------------------------------
request_otp() does everything real -- generates a code, hashes it, stores
it with a real expiry -- except actually deliver it by text message. No
SMS provider has been chosen (flagged as blocked in earlier planning).
_send_sms() below is an obvious, clearly-labeled stand-in that PRINTS the
code instead of sending it -- so this stays genuinely testable (you can
read the printed code and use it in verify_otp()) without pretending a
delivery mechanism exists that doesn't. Swap _send_sms()'s body for a
real provider call later; nothing else in this file needs to change.

WHY THE ACCOUNT ROW IS CREATED IN verify_otp(), NOT request_otp()
------------------------------------------------------------------------
Someone can request a code without ever proving they own that phone (a
wrong number, a typo, someone else's number). Creating the
beneficiary_app_accounts row only on a SUCCESSFUL verify -- "first
successful login," per earlier design -- means the accounts table only
ever holds people who actually proved phone ownership, not every
half-finished attempt.

WHAT verify_otp() RETURNS INSTEAD OF A REAL SESSION
--------------------------------------------------------
A real API would turn a successful verify into a signed JWT here. That's
services/api's job, not this file's -- this returns the beneficiary_id a
JWT would have carried, so whoever builds that layer has exactly what
they need to issue one.

SKIP_ELIGIBILITY_CHECK -- A TOGGLEABLE TESTING BYPASS, ADDED 4 SEP 2026
--------------------------------------------------------------------------
Typing a real, already-seeded phone number correctly every time you want
to test the app was slowing testing down. Set SKIP_ELIGIBILITY_CHECK=true
in .env and ANY phone number logs in -- if it doesn't already match a
real beneficiary, one is auto-provisioned on the spot (a real
beneficiary_profiles row + a real disbursed microfinance_loans row with
a trade category), so every OTHER function downstream (save_listing,
matching, everything) keeps working completely normally, unmodified --
this is the ONE place the bypass lives, not scattered special-casing
through the rest of the codebase.

This prints a loud warning on every use so it can't be silently forgotten,
and MUST be false (or simply absent from .env) before anything resembling
a real demo -- with it on, the eligibility gate this whole module is
built around does not run at all.
"""

import hashlib
import os
import secrets
import uuid

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

MAX_OTP_ATTEMPTS = 5
OTP_LENGTH = 6

SKIP_ELIGIBILITY_CHECK = os.environ.get("SKIP_ELIGIBILITY_CHECK", "false").lower() == "true"


def _hash_code(code: str) -> str:
    # sha256 of the code -- login_otps.code_hash "store a hash, never the
    # code," same reasoning as any password: if the database ever leaks,
    # a hash doesn't hand out working login codes.
    return hashlib.sha256(code.encode()).hexdigest()


def _send_sms(phone: str, message: str) -> None:
    """STAND-IN -- see file docstring. No real SMS provider chosen yet."""
    print(f"[SMS -- NOT ACTUALLY SENT, no provider wired up] to {phone}: {message}")


def _auto_provision_test_beneficiary(cur, phone: str) -> tuple[str, str]:
    """
    Only ever called when SKIP_ELIGIBILITY_CHECK is on -- see file
    docstring. Creates a real, fully-valid beneficiary_profiles row plus
    a real disbursed microfinance_loans row (Trading businesses, the
    least assumption-laden of the ten categories) so everything
    downstream of login just works, unmodified.
    """
    beneficiary_id = str(uuid.uuid4())
    cur.execute(
        "insert into beneficiary_profiles (id, full_name, phone, district, cluster_id, consent_given) "
        "values (%s, %s, %s, 'Lahore', 'LHR-01', true)",
        (beneficiary_id, f"Test User {phone[-4:]}", phone),
    )

    cur.execute("select id from trade_categories where name = 'Trading businesses'")
    trade_category_id = cur.fetchone()[0]

    cur.execute(
        "insert into microfinance_loans "
        "(loan_reference, beneficiary_id, loan_product, trade_category_id, "
        " stated_purpose_text, status, amount_disbursed, disbursed_on) "
        "values (%s, %s, 'Small Business Loan', %s, 'Auto-provisioned for testing', "
        "        'disbursed', 150000, current_date)",
        (f"TEST-{beneficiary_id[:8]}", beneficiary_id, trade_category_id),
    )
    return beneficiary_id, trade_category_id


def request_otp(phone: str) -> dict:
    """
    Runs the eligibility check (schema reference query G) BEFORE sending
    anything. Returns a dict describing what happened -- never raises for
    an ineligible number, since "not eligible" is an expected, normal
    outcome here, not an error.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        """
        select bp.id as beneficiary_id, ml.trade_category_id, ml.status
        from beneficiary_profiles bp
        join microfinance_loans ml on ml.beneficiary_id = bp.id
        where bp.phone = %s
          and ml.status in ('approved', 'disbursed')
        order by ml.created_at desc
        limit 1
        """,
        (phone,),
    )
    row = cur.fetchone()

    if row is None and SKIP_ELIGIBILITY_CHECK:
        print(
            f"[SKIP_ELIGIBILITY_CHECK is ON] auto-provisioning a test beneficiary "
            f"for {phone} -- this MUST be off before anything resembling a real demo."
        )
        beneficiary_id, trade_category_id = _auto_provision_test_beneficiary(cur, phone)
        conn.commit()
        row = (beneficiary_id, trade_category_id, "disbursed")

    if row is None:
        cur.close()
        conn.close()
        return {"eligible": False, "reason": "not_found", "otp_sent": False}

    beneficiary_id, trade_category_id, status = row

    code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
    cur.execute(
        "insert into login_otps (phone, code_hash) values (%s, %s)",
        (phone, _hash_code(code)),
    )
    conn.commit()
    cur.close()
    conn.close()

    _send_sms(phone, f"Your Al-Khidmat marketplace code is {code}. Valid for 10 minutes.")

    return {
        "eligible": True,
        "otp_sent": True,
        "can_create_listing": trade_category_id is not None,
    }


def verify_otp(phone: str, code: str) -> dict:
    """
    Checks the most recent unconsumed, unexpired code for this phone.
    Returns {"verified": True, "beneficiary_id": ...} on success, or
    {"verified": False, "reason": ...} otherwise -- same "expected
    outcome, not an exception" reasoning as request_otp().
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        """
        select id, code_hash, attempts
        from login_otps
        where phone = %s
          and consumed_at is null
          and expires_at > now()
        order by created_at desc
        limit 1
        """,
        (phone,),
    )
    row = cur.fetchone()

    if row is None:
        cur.close()
        conn.close()
        return {"verified": False, "reason": "expired_or_not_found"}

    otp_id, code_hash, attempts = row

    if attempts >= MAX_OTP_ATTEMPTS:
        cur.close()
        conn.close()
        return {"verified": False, "reason": "too_many_attempts"}

    if _hash_code(code) != code_hash:
        cur.execute("update login_otps set attempts = attempts + 1 where id = %s", (otp_id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"verified": False, "reason": "wrong_code"}

    cur.execute("update login_otps set consumed_at = now() where id = %s", (otp_id,))

    cur.execute("select id from beneficiary_profiles where phone = %s", (phone,))
    beneficiary_id = cur.fetchone()[0]

    # First successful login for this phone -> create the account row now,
    # not before -- see file docstring.
    cur.execute(
        """
        insert into beneficiary_app_accounts (beneficiary_id, phone, phone_verified, last_login_at)
        values (%s, %s, true, now())
        on conflict (beneficiary_id) do update set
            last_login_at = now(),
            phone_verified = true
        """,
        (beneficiary_id, phone),
    )

    conn.commit()
    cur.close()
    conn.close()

    return {"verified": True, "beneficiary_id": beneficiary_id}


def get_me_context(beneficiary_id: str) -> dict:
    """
    GET /me/context, Marketplace_Spec.md section 3: name, district,
    cluster, trade category, and stated purpose -- everything the 5-card
    form must NEVER ask again because it's already on file.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        "select full_name, district, cluster_id from beneficiary_profiles where id = %s",
        (beneficiary_id,),
    )
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        raise ValueError(f"no beneficiary_profiles row with id={beneficiary_id}")
    full_name, district, cluster_id = row

    cur.execute(
        """
        select tc.name, ml.stated_purpose_text
        from microfinance_loans ml
        left join trade_categories tc on tc.id = ml.trade_category_id
        where ml.beneficiary_id = %s and ml.status in ('approved', 'disbursed')
        order by ml.created_at desc
        limit 1
        """,
        (beneficiary_id,),
    )
    row = cur.fetchone()
    trade_category, stated_purpose = row if row else (None, None)

    cur.close()
    conn.close()

    return {
        "full_name": full_name,
        "district": district,
        "cluster_id": cluster_id,
        "trade_category": trade_category,
        "stated_purpose": stated_purpose,
        "can_create_listing": trade_category is not None,
    }
