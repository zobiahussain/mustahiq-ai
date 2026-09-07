from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.auth import get_current_staff

from app.core.db import get_db

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("select 1"))
        return {"status": "ok", "db": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail='Database connection unavailable.')

@router.get("/me")
def read_current_staff(staff: dict = Depends(get_current_staff)):
    return staff
