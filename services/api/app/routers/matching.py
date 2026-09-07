from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_staff
from app.core.db import get_db
from app.schemas.matching import ProgramMatch
from app.services.eligibility_matching import get_persisted_matches

router = APIRouter(prefix="/beneficiaries", tags=["matching"])

@router.get("/{beneficiary_id}/matches", response_model=list[ProgramMatch])
def get_beneficiary_matches(
    beneficiary_id: str,
    db: Session = Depends(get_db),
    staff: dict = Depends(get_current_staff),
):
    try:
        parsed_beneficiary_id = UUID(beneficiary_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="beneficiary_id must be a UUID") from error

    return get_persisted_matches(db, parsed_beneficiary_id)
