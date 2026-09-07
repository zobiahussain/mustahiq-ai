"""Compatibility endpoint: real deterministic discovery, no random scores."""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.core.db import get_db
from app.portal.auth import current_staff
from app.portal import service as s
from app.portal import tables as t

router = APIRouter(prefix='/beneficiaries', tags=['matching'])


@router.get('/{beneficiary_id}/matches')
def get_beneficiary_matches(beneficiary_id: UUID, db=Depends(get_db), staff=Depends(current_staff)):
    s.profile_for(db, staff, beneficiary_id)
    programs = {str(p['id']): p['name'] for p in s.rows(db, t.programs)
                if staff['role'] == 'super_admin' or str(p['department_id']) == str(staff['department_id'])}
    return [{**m, 'program_name': programs[str(m['program_id'])]} for m in s.rows(db, t.matches)
            if str(m['beneficiary_id']) == str(beneficiary_id) and str(m['program_id']) in programs]
