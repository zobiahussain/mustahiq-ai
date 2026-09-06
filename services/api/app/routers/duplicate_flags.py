from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import get_current_staff
from app.core.db import get_db
from app.schemas.duplicate_flag import DuplicateFlagResponse, DuplicateFlagReview

router = APIRouter(prefix="/duplicate-flags", tags=["duplicate-flags"])


@router.get("/", response_model=list[DuplicateFlagResponse])
def list_pending_flags(
    db: Session = Depends(get_db),
    staff: dict = Depends(get_current_staff),
):
    rows = db.execute(
        text("""
            select
                df.id,
                df.profile_a_id,
                pa.full_name as profile_a_name,
                df.profile_b_id,
                pb.full_name as profile_b_name,
                df.similarity_score,
                df.matched_on,
                df.status,
                df.created_at
            from duplicate_flags df
            join beneficiary_profiles pa on pa.id = df.profile_a_id
            join beneficiary_profiles pb on pb.id = df.profile_b_id
            where df.status = 'pending'
            order by df.created_at desc
        """)
    ).fetchall()

    return [dict(row._mapping) for row in rows]


@router.patch("/{flag_id}", response_model=DuplicateFlagResponse)
def review_flag(
    flag_id: str,
    payload: DuplicateFlagReview,
    db: Session = Depends(get_db),
    staff: dict = Depends(get_current_staff),
):
    row = db.execute(
        text("""
            update duplicate_flags
            set status = :status,
                reviewed_by_staff_id = :staff_id,
                reviewed_at = now()
            where id = :flag_id
            returning id
        """),
        {"status": payload.status, "staff_id": staff["id"], "flag_id": flag_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Duplicate flag not found")

    db.commit()

    updated = db.execute(
        text("""
            select
                df.id,
                df.profile_a_id,
                pa.full_name as profile_a_name,
                df.profile_b_id,
                pb.full_name as profile_b_name,
                df.similarity_score,
                df.matched_on,
                df.status,
                df.created_at
            from duplicate_flags df
            join beneficiary_profiles pa on pa.id = df.profile_a_id
            join beneficiary_profiles pb on pb.id = df.profile_b_id
            where df.id = :flag_id
        """),
        {"flag_id": flag_id},
    ).fetchone()

    return dict(updated._mapping)
