from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import get_current_staff
from app.core.db import get_db
from app.schemas.beneficiary import BeneficiaryCreate, BeneficiaryDetail, BeneficiaryResponse
from app.services.duplicate_detection import check_duplicates
from app.services.eligibility_matching import refresh_beneficiary_matches
from eligibility.persistence import SavedScorer

router = APIRouter(prefix="/beneficiaries", tags=["beneficiaries"])


def get_eligibility_scorer(request: Request) -> SavedScorer:
    return request.app.state.eligibility_scorer


@router.get("/", response_model=list[BeneficiaryDetail])
def list_beneficiaries(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    staff: dict = Depends(get_current_staff),
):
    rows = db.execute(
        text("select * from beneficiary_profiles order by created_at desc limit :limit offset :offset"),
        {"limit": limit, "offset": offset},
    ).fetchall()

    return [dict(row._mapping) for row in rows]


@router.get("/{beneficiary_id}", response_model=BeneficiaryDetail)
def get_beneficiary(
    beneficiary_id: str,
    db: Session = Depends(get_db),
    staff: dict = Depends(get_current_staff),
):
    row = db.execute(
        text("select * from beneficiary_profiles where id = :id"),
        {"id": beneficiary_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    return dict(row._mapping)


@router.post("/", response_model=BeneficiaryResponse)
def create_beneficiary(
    payload: BeneficiaryCreate,
    db: Session = Depends(get_db),
    staff: dict = Depends(get_current_staff),
    scorer: SavedScorer = Depends(get_eligibility_scorer),
):
    result = db.execute(
        text("""
            insert into beneficiary_profiles
                (full_name, cnic, phone, district, city, household_size, dependents, monthly_income, created_by_staff_id)
            values
                (:full_name, :cnic, :phone, :district, :city, :household_size, :dependents, :monthly_income, :staff_id)
            returning id, full_name, cnic, phone, district
        """),
        {**payload.model_dump(), "staff_id": staff["id"]},
    )
    row = result.fetchone()
    db.commit()

    check_duplicates(db, new_profile_id=row.id, full_name=row.full_name, phone=row.phone, cnic=row.cnic)
    try:
        refresh_beneficiary_matches(db, row.id, scorer)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"eligibility configuration error: {error}") from error

    return dict(row._mapping)
