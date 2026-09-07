"""Shared staff authentication; compatibility import for existing API routes."""
from fastapi import Depends, HTTPException
from app.portal.auth import current_staff as get_current_staff


def require_role(*allowed_roles):
    def checker(staff=Depends(get_current_staff)):
        if staff['role'] not in allowed_roles:
            raise HTTPException(403, 'Insufficient permissions')
        return staff
    return checker
