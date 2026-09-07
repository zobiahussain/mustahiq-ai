from uuid import UUID
from fastapi import APIRouter, Depends
from app.core.db import get_db
from app.portal.auth import current_staff
from app.portal.router import workspace, review_duplicate
from app.schemas.duplicate_flag import DuplicateFlagReview

router = APIRouter(prefix='/duplicate-flags', tags=['duplicate-flags'])


@router.get('/')
def list_pending_flags(db=Depends(get_db), staff=Depends(current_staff)):
    data = workspace(db, staff)
    profiles = {str(p['id']): p['full_name'] for p in data['profiles']}
    return [{**r, 'profile_a_name': profiles[str(r['profile_a_id'])], 'profile_b_name': profiles[str(r['profile_b_id'])]}
            for r in data['duplicates'] if r['status'] == 'pending']


@router.patch('/{flag_id}')
def review_flag(flag_id: UUID, payload: DuplicateFlagReview, db=Depends(get_db), staff=Depends(current_staff)):
    return review_duplicate(flag_id, payload.status, db, staff)
