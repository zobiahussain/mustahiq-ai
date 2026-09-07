"""Original route paths backed by the complete staff profile contract."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.core.db import get_db
from app.portal.auth import current_staff
from app.portal.contracts import ProfileInput
from app.portal.router import create_profile, workspace
from app.portal.service import profile_for

router = APIRouter(prefix='/beneficiaries', tags=['beneficiaries'])


@router.get('/')
def list_beneficiaries(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db=Depends(get_db), staff=Depends(current_staff)):
    return workspace(db, staff)['profiles'][offset:offset + limit]


@router.get('/{beneficiary_id}')
def get_beneficiary(beneficiary_id: UUID, db=Depends(get_db), staff=Depends(current_staff)):
    return profile_for(db, staff, beneficiary_id)


@router.post('/', status_code=201)
def create_beneficiary(payload: ProfileInput, db=Depends(get_db), staff=Depends(current_staff)):
    return create_profile(payload, db, staff)['profile']
