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

CAN SOMEONE REGISTER THEMSELVES, WITH THEIR OWN DETAILS? -- NO, BY DESIGN
--------------------------------------------------------------------------
Asked directly (5 Sep 2026): does a brand-new person ever enter their own
profile and start listing on the app? The real answer is NO, and it's
not a missing feature -- it's the model. Marketplace_Spec.md section 2 is
explicit: a profile only ever originates from a STAFF-ENTERED loan
application (Al-Khidmat's own loan officer records name/district/trade
category at a facilitation centre); the marketplace's phone+OTP only
AUTHENTICATES against that existing record, it never creates a fresh
identity. This is the same "no beneficiary accounts on the eligibility
side" principle CLAUDE.md states repeatedly -- the marketplace's OTP
login is the one deliberate exception to "beneficiaries never log in,"
but it still isn't self-registration.

What full_name/district/trade_category below actually are: with
SKIP_ELIGIBILITY_CHECK on, an unrecognised phone number used to always
get the SAME generic auto-provisioned profile (Lahore, Trading
businesses) -- which made it hard to test a SPECIFIC matching scenario
(a Multan tailor meeting a Karachi grocer, say). These three optional
parameters let a TESTER supply what that generic profile would otherwise
guess, standing in for what a loan officer would have entered for real.
It is still entirely gated by SKIP_ELIGIBILITY_CHECK, still produces a
completely real, ordinary beneficiary_profiles/microfinance_loans row
indistinguishable from any other downstream, and still must be off (or
simply absent) before anything resembling a real demo.
"""

import hashlib
import os
import secrets
import uuid

import psycopg2
from dotenv import load_dotenv

from proximity import PROVINCE_BY_DISTRICT

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


def _auto_provision_test_beneficiary(
    cur,
    phone: str,
    full_name: str | None = None,
    district: str | None = None,
    trade_category: str | None = None,
) -> tuple[str, str]:
    """
    Only ever called when SKIP_ELIGIBILITY_CHECK is on -- see file
    docstring. Creates a real, fully-valid beneficiary_profiles row plus
    a real disbursed microfinance_loans row, so everything downstream of
    login just works, unmodified.

    full_name/district/trade_category are OPTIONAL -- see file docstring
    "CAN SOMEONE REGISTER THEMSELVES." Omitted, this falls back to the
    original generic default (Lahore, Trading businesses). Supplied, it
    stands in for what a loan officer would have entered.

    Raises ValueError for a district not in
    proximity.PROVINCE_BY_DISTRICT or a trade_category that isn't one of
    the real 10 -- a typo here should fail loudly, not silently produce
    a beneficiary with a district matching() can't reason about.
    """
    beneficiary_id = str(uuid.uuid4())
    name = full_name or f"Test User {phone[-4:]}"

    if district:
        if district not in PROVINCE_BY_DISTRICT:
            raise ValueError(
                f"'{district}' isn't a recognised Pakistani district -- see "
                "packages/marketplace/proximity.py's PROVINCE_BY_DISTRICT for the full list"
            )
        # Simple "first three letters" cluster convention -- same one
        # generate_seed_data.py's curated district list uses, though that
        # list assigns them by hand; this derives one on the fly so any
        # of Pakistan's ~160 districts works here, not just the ~42
        # that script chose to seed. Good enough for a testing
        # convenience: what matters is that the SAME district always
        # derives the SAME cluster_id, so two test beneficiaries in
        # "Multan" land in the same cluster and matching behaves
        # sensibly -- it doesn't need to match Al-Khidmat's real cluster
        # boundaries (nothing in this codebase has those; see
        # proximity.py's own docstring).
        cluster_id = f"{district[:3].upper()}-01"
    else:
        district, cluster_id = "Lahore", "LHR-01"

    cur.execute(
        "insert into beneficiary_profiles (id, full_name, phone, district, cluster_id, consent_given) "
        "values (%s, %s, %s, %s, %s, true)",
        (beneficiary_id, name, phone, district, cluster_id),
    )

    category_name = trade_category or "Trading businesses"
    cur.execute("select id from trade_categories where name = %s", (category_name,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(
            f"'{category_name}' isn't one of the 10 real trade categories -- "
            "see packages/data/reference_lists.md"
        )
    trade_category_id = row[0]

    cur.execute(
        "insert into microfinance_loans "
        "(loan_reference, beneficiary_id, loan_product, trade_category_id, "
        " stated_purpose_text, status, amount_disbursed, disbursed_on) "
        "values (%s, %s, 'Small Business Loan', %s, 'Auto-provisioned for testing', "
        "        'disbursed', 150000, current_date)",
        (f"TEST-{beneficiary_id[:8]}", beneficiary_id, trade_category_id),
    )
    return beneficiary_id, trade_category_id


def request_otp(
    phone: str,
    full_name: str | None = None,
    district: str | None = None,
    trade_category: str | None = None,
) -> dict:
    """
    Runs the eligibility check (schema reference query G) BEFORE sending
    anything. Returns a dict describing what happened -- never raises for
    an ineligible number, since "not eligible" is an expected, normal
    outcome here, not an error.

    full_name/district/trade_category: ONLY meaningful when
    SKIP_ELIGIBILITY_CHECK is on AND phone doesn't already match a real
    beneficiary -- see _auto_provision_test_beneficiary()'s docstring.
    Harmless to pass otherwise; they're simply never read.
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
        try:
            beneficiary_id, trade_category_id = _auto_provision_test_beneficiary(
                cur, phone, full_name, district, trade_category
            )
        except ValueError:
            cur.close()
            conn.close()
            raise
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
