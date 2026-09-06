from rapidfuzz import fuzz
from sqlalchemy import text
from sqlalchemy.orm import Session

FUZZY_THRESHOLD = 85  # 0-100 scale; tune later if it's too strict/loose


def check_duplicates(db: Session, new_profile_id, full_name: str, phone: str | None, cnic: str | None):
    flagged_ids = set()

    # 1. CNIC exact match first
    if cnic:
        exact_matches = db.execute(
            text("select id from beneficiary_profiles where cnic = :cnic and id != :new_id"),
            {"cnic": cnic, "new_id": new_profile_id},
        ).fetchall()
        for row in exact_matches:
            _insert_flag(db, new_profile_id, row.id, 100.0, "cnic_exact")
            flagged_ids.add(row.id)

    # 2. Fuzzy name + phone against everyone else not already flagged
    candidates = db.execute(
        text("select id, full_name, phone from beneficiary_profiles where id != :new_id"),
        {"new_id": new_profile_id},
    ).fetchall()

    for row in candidates:
        if row.id in flagged_ids:
            continue
        name_score = fuzz.token_sort_ratio(full_name, row.full_name)
        phone_score = fuzz.ratio(phone or "", row.phone or "") if phone and row.phone else 0
        combined = max(name_score, phone_score)

        if combined >= FUZZY_THRESHOLD:
            _insert_flag(db, new_profile_id, row.id, combined, "name_phone_fuzzy")

    db.commit()


def _insert_flag(db: Session, profile_a_id, profile_b_id, score, matched_on):
    db.execute(
        text("""
            insert into duplicate_flags (profile_a_id, profile_b_id, similarity_score, matched_on)
            values (:a, :b, :score, :matched_on)
        """),
        {"a": str(profile_a_id), "b": str(profile_b_id), "score": score, "matched_on": matched_on},
    )