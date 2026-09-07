from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import get_current_staff
from app.core.db import get_db
from app.core.scorer import get_eligibility_scorer
from app.schemas.beneficiary import (
    BeneficiaryCreate,
    BeneficiaryDetail,
    BeneficiaryResponse,
    BeneficiaryUpdate,
)
from app.services.duplicate_detection import check_duplicates
from app.services.eligibility_workflows import on_profile_created_or_updated
from eligibility.persistence import SavedScorer

router = APIRouter(prefix="/beneficiaries", tags=["beneficiaries"])

UPDATABLE_FIELDS = (
    "full_name",
    "cnic",
    "phone",
    "district",
    "city",
    "cluster_id",
    "household_size",
    "dependents",
    "school_age_children",
    "marital_status",
    "monthly_income",
    "employment_status",
    "owns_home",
    "education_level",
    "has_disability",
    "chronic_illness_flag",
    "date_of_birth",
    "is_orphan",
    "prior_assistance_count",
)


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
        on_profile_created_or_updated(db, row.id, scorer)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"eligibility configuration error: {error}") from error

    return dict(row._mapping)


@router.patch("/{beneficiary_id}", response_model=BeneficiaryDetail)
def update_beneficiary(
    beneficiary_id: str,
    payload: BeneficiaryUpdate,
    db: Session = Depends(get_db),
    staff: dict = Depends(get_current_staff),
    scorer: SavedScorer = Depends(get_eligibility_scorer),
):
    try:
        parsed_beneficiary_id = UUID(beneficiary_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="beneficiary_id must be a UUID") from error

    updates = payload.model_dump(exclude_unset=True)

    set_clauses = [f"{field} = :{field}" for field in UPDATABLE_FIELDS if field in updates]
    set_clauses.append("updated_at = now()")
    parameters = {"beneficiary_id": parsed_beneficiary_id, **updates}

    row = db.execute(
        text(f"""
            update beneficiary_profiles
            set {', '.join(set_clauses)}
            where id = :beneficiary_id
            returning *
        """),
        parameters,
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Beneficiary not found")
    db.commit()

    # Trigger 1 (profile updated): re-discover against every active programme.
    try:
        on_profile_created_or_updated(db, parsed_beneficiary_id, scorer)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"eligibility configuration error: {error}") from error

    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
