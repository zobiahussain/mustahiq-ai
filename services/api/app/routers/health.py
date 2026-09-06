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
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")

@router.get("/me")
def read_current_staff(staff: dict = Depends(get_current_staff)):
    return staff