from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class BeneficiaryCreate(BaseModel):
    full_name: str
    cnic: Optional[str] = None
    phone: Optional[str] = None
    district: str
    city: Optional[str] = None
    household_size: Optional[int] = None
    dependents: Optional[int] = None
    monthly_income: Optional[float] = None


class BeneficiaryResponse(BaseModel):
    id: UUID
    full_name: str
    cnic: Optional[str]
    phone: Optional[str]
    district: str