"""
Marketplace_Spec.md section 11.1, "zakat graduation" -- mustahiq
(eligible to receive) to donor. graduation_events already existed in the
schema; nothing anywhere wrote to it until this file.

THE ONE DELIBERATE DESIGN RULE ACROSS ALL FIVE FUNCTIONS BELOW
--------------------------------------------------------------------
Every event here is triggered by something REAL and OBSERVABLE -- an
actual action that happened -- never a computed financial threshold.
Zakat eligibility in Islamic jurisprudence (nisab) is calculated against
total wealth/assets held for a full lunar year, using gold or silver
market rates -- this module has no visibility into anyone's actual
assets or savings (only loan and listing data), and guessing at
someone's religious financial obligation from proxies like "they got one
supply-chain match" would be a real claim to get wrong, not an
engineering shortcut to take. So: a person choosing to donate IS the
"became donor" signal, not our calculation overriding their own
judgement -- same "the system does not decide" principle already used
for availability (section 9.3).
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def _record_event(cur, beneficiary_id: str, event_type: str, listing_id: str | None = None, notes: str | None = None) -> str:
    cur.execute(
        "insert into graduation_events (beneficiary_id, event_type, listing_id, notes) "
        "values (%s, %s, %s, %s) returning id",
        (beneficiary_id, event_type, listing_id, notes),
    )
    return cur.fetchone()[0]


def record_loan_repaid(loan_id: str) -> str:
    """
    A REAL WEBHOOK TARGET, not internal logic -- called by Al-Khidmat's
    own loan-servicing system when a loan is actually repaid (per your
    own instruction: "as soon as it's repaid they'll send us through
    API"). This function does not and cannot determine repayment itself
    -- there is no repayment-tracking data anywhere in this schema, on
    purpose; that lives in Al-Khidmat's finance system, not here.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select beneficiary_id from microfinance_loans where id = %s", (loan_id,))
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        raise ValueError(f"no microfinance_loans row with id={loan_id}")
    event_id = _record_event(cur, row[0], "loan_repaid", notes=f"loan {loan_id} repaid")
    conn.commit()
    cur.close()
    conn.close()
    return event_id


def record_donation(beneficiary_id: str, amount: float, listing_id: str | None = None, note: str | None = None) -> dict:
    """
    Records the donation itself, then checks: is this the FIRST donation
    this beneficiary has ever made? If so, that first voluntary choice to
    give IS the "became_donor" graduation moment -- their own decision,
    not a threshold we computed for them.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        "select count(*) from donations where beneficiary_id = %s", (beneficiary_id,)
    )
    is_first_donation = cur.fetchone()[0] == 0

    cur.execute(
        "insert into donations (beneficiary_id, listing_id, amount, note) "
        "values (%s, %s, %s, %s) returning id",
        (beneficiary_id, listing_id, amount, note),
    )
    donation_id = cur.fetchone()[0]

    graduation_event_id = None
    if is_first_donation:
        graduation_event_id = _record_event(cur, beneficiary_id, "became_donor", listing_id=listing_id)

    conn.commit()
    cur.close()
    conn.close()
    return {"donation_id": donation_id, "graduation_event_id": graduation_event_id}


def confirm_match_connection(match_id: str, beneficiary_id: str) -> dict:
    """
    Marks a match 'connected' -- the status already existed in the
    schema, nothing set it until now. For an employment match
    specifically, this is also the real "hired_employee" moment: adds the
    actual employee row to listing_participants (not just a status flip)
    and logs the graduation event against the person who got hired, not
    the business that hired them.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        "select match_model, listing_a_id, listing_b_id from marketplace_matches where id = %s",
        (match_id,),
    )
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        raise ValueError(f"no match {match_id}")
    match_model, listing_a_id, listing_b_id = row

    if beneficiary_id and not _is_party_to_match(cur, beneficiary_id, listing_a_id, listing_b_id):
        cur.close()
        conn.close()
        raise ValueError(f"beneficiary {beneficiary_id} isn't a party to match {match_id}")

    cur.execute("update marketplace_matches set status = 'connected' where id = %s", (match_id,))

    graduation_event_id = None
    if match_model == "employment":
        cur.execute(
            "select id, seeking_workers, seeking_work, primary_beneficiary_id "
            "from store_listings where id in (%s, %s)",
            (listing_a_id, listing_b_id),
        )
        listings = {r[0]: r for r in cur.fetchall()}
        employer_listing_id = next((lid for lid, r in listings.items() if r[1]), None)  # seeking_workers
        employee_listing = next((r for r in listings.values() if r[2]), None)  # seeking_work

        if employer_listing_id and employee_listing:
            employee_beneficiary_id = employee_listing[3]
            if employee_beneficiary_id:
                cur.execute(
                    "insert into listing_participants (listing_id, beneficiary_id, role, status) "
                    "values (%s, %s, 'employee', 'confirmed') "
                    "on conflict (listing_id, beneficiary_id) do nothing",
                    (employer_listing_id, employee_beneficiary_id),
                )
                graduation_event_id = _record_event(
                    cur, employee_beneficiary_id, "hired_employee", listing_id=employer_listing_id
                )

    conn.commit()
    cur.close()
    conn.close()
    return {"connected": True, "graduation_event_id": graduation_event_id}


def _is_party_to_match(cur, beneficiary_id: str, listing_a_id: str, listing_b_id: str) -> bool:
    cur.execute(
        "select 1 from store_listings where id in (%s, %s) and primary_beneficiary_id = %s "
        "union select 1 from listing_participants where listing_id in (%s, %s) and beneficiary_id = %s",
        (listing_a_id, listing_b_id, beneficiary_id, listing_a_id, listing_b_id, beneficiary_id),
    )
    return cur.fetchone() is not None


def record_no_longer_seeking_assistance(beneficiary_id: str, notes: str | None = None) -> str:
    """
    Self-reported, deliberately -- same reasoning as became_donor.
    Nobody but the person themselves can really assert "I don't need
    help anymore"; it's a self-assessment, not something computed from
    their listing activity.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    event_id = _record_event(cur, beneficiary_id, "no_longer_seeking_assistance", notes=notes)
    conn.commit()
    cur.close()
    conn.close()
    return event_id
