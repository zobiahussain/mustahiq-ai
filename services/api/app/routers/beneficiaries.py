from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import get_current_staff
from app.core.db import get_db
from app.schemas.beneficiary import BeneficiaryCreate, BeneficiaryResponse
from app.services.duplicate_detection import check_duplicates

router = APIRouter(prefix="/beneficiaries", tags=["beneficiaries"])


@router.post("/", response_model=BeneficiaryResponse)
def create_beneficiary(
    payload: BeneficiaryCreate,
    db: Session = Depends(get_db),
    staff: dict = Depends(get_current_staff),
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

    return dict(row._mapping)