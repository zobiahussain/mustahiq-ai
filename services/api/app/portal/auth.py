"""Supabase staff sessions, and an explicitly enabled local-demo session."""
from datetime import datetime, timedelta, timezone
import secrets

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.config import settings
from app.core.db import get_db
from .tables import staff_users

DEMO_SECRET = secrets.token_urlsafe(48)
security = HTTPBearer(auto_error=False)


def demo_token(staff_id):
    return jwt.encode({'sub': str(staff_id), 'exp': datetime.now(timezone.utc) + timedelta(hours=8), 'aud': 'staff-local-demo'}, DEMO_SECRET, algorithm='HS256')


def auth_request(path, *, body=None, token=None):
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(503, 'Supabase staff authentication is not configured.')
    headers = {'apikey': settings.supabase_anon_key}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with httpx.Client(timeout=15) as client:
            result = client.get(settings.supabase_url + '/auth/v1/' + path, headers=headers) if body is None else client.post(settings.supabase_url + '/auth/v1/' + path, headers=headers, json=body)
    except httpx.RequestError:
        raise HTTPException(503, 'Staff sign-in service is unavailable. Please retry.')
    if result.status_code >= 400:
        raise HTTPException(401, 'Invalid credentials or expired session.')
    return result.json()


def current_staff(credentials: HTTPAuthorizationCredentials | None = Depends(security), db=Depends(get_db)):
    if not credentials:
        raise HTTPException(401, 'Please sign in to your staff account.')
    if settings.portal_demo_mode:
        try:
            claims = jwt.decode(credentials.credentials, DEMO_SECRET, algorithms=['HS256'], audience='staff-local-demo')
        except jwt.InvalidTokenError:
            raise HTTPException(401, 'Demo session expired. Open the demo again.')
        condition = staff_users.c.id == claims['sub']
    else:
        user = auth_request('user', token=credentials.credentials)
        condition = staff_users.c.auth_user_id == user['id']
    row = db.execute(select(staff_users).where(condition)).mappings().first()
    if not row or not row['active']:
        raise HTTPException(403, 'No active staff account is linked to this sign-in.')
    if row['role'] not in ('area_manager', 'field_officer', 'department_admin', 'super_admin'):
        raise HTTPException(403, 'This staff role is not supported.')
    if row['role'] != 'super_admin' and not row['department_id']:
        raise HTTPException(403, 'Ask an administrator to assign your staff account to a department.')
    return dict(row)


def require_admin(staff):
    if staff['role'] not in ('department_admin', 'super_admin'):
        raise HTTPException(403, 'A department administrator must perform this action.')


def check_department(staff, department_id):
    if staff['role'] != 'super_admin' and str(staff['department_id']) != str(department_id):
        raise HTTPException(403, 'This program belongs to another department.')
