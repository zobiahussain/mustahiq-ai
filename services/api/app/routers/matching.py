"""Compatibility endpoint: real deterministic discovery, no random scores."""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.core.db import get_db
from app.portal.auth import current_staff
from app.portal.router import discovery

router = APIRouter(prefix='/beneficiaries', tags=['matching'])


@router.get('/{beneficiary_id}/matches')
def get_beneficiary_matches(beneficiary_id: UUID, db=Depends(get_db), staff=Depends(current_staff)):
    return discovery(beneficiary_id, db, staff)
