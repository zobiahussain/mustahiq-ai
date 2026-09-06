import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db

security = HTTPBearer()


def get_current_staff(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials

    resp = httpx.get(
        f"{settings.supabase_url}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": settings.supabase_anon_key,
        },
        timeout=5.0,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    auth_user_id = resp.json()["id"]

    row = db.execute(
        text("select id, full_name, role, active, department_id from staff_users where auth_user_id = :uid"),
        {"uid": auth_user_id},
    ).mappings().first()

    if row is None:
        raise HTTPException(status_code=403, detail="No staff record linked to this account")
    if not row["active"]:
        raise HTTPException(status_code=403, detail="Staff account is inactive")

    return dict(row)


def require_role(*allowed_roles: str):
    def checker(staff: dict = Depends(get_current_staff)):
        if staff["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return staff
    return checker