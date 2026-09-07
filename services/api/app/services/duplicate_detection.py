"""Supabase-side duplicate detection (trigger 2).

The comparison logic lives in ``packages/dedup`` (framework-free, shared with
the staff portal's ``app/portal/service.detect_duplicates``). This module only
owns the database work: read every other profile, compare, and write pending
``duplicate_flags`` for the staff queue. Merging is always manual.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from dedup import FUZZY_THRESHOLD, compare  # noqa: F401  (FUZZY_THRESHOLD re-exported for callers/tests)


def check_duplicates(db: Session, new_profile_id, full_name: str, phone: str | None, cnic: str | None):
    candidates = db.execute(
        text("select id, full_name, phone, cnic from beneficiary_profiles where id != :new_id"),
        {"new_id": new_profile_id},
    ).fetchall()

    for row in candidates:
        signal = compare(
            name_a=full_name, phone_a=phone, cnic_a=cnic,
            name_b=row.full_name, phone_b=row.phone, cnic_b=getattr(row, "cnic", None),
        )
        if signal is not None:
            _insert_flag(db, new_profile_id, row.id, signal.score, signal.matched_on)

    db.commit()


def _insert_flag(db: Session, profile_a_id, profile_b_id, score, matched_on):
    db.execute(
        text("""
            insert into duplicate_flags (profile_a_id, profile_b_id, similarity_score, matched_on)
            values (:a, :b, :score, :matched_on)
        """),
        {"a": str(profile_a_id), "b": str(profile_b_id), "score": score, "matched_on": matched_on},
    )
