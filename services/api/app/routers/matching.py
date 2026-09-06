import random

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import get_current_staff
from app.core.db import get_db
from app.schemas.matching import ProgramMatch

router = APIRouter(prefix="/beneficiaries", tags=["matching"])

STUB_REASON = "Stub — pending Eligibility Engine integration"


@router.get("/{beneficiary_id}/matches", response_model=list[ProgramMatch])
def get_beneficiary_matches(
    beneficiary_id: str,
    db: Session = Depends(get_db),
    staff: dict = Depends(get_current_staff),
):
    rows = db.execute(
        text("select id, name from programs where active = true")
    ).fetchall()

    return [
        ProgramMatch(
            program_id=row.id,
            program_name=row.name,
            score=round(random.random(), 4),
            reason=STUB_REASON,
        )
        for row in rows
    ]
