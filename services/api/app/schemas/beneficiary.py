from datetime import date, datetime
from typing import Any, Optional
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


class BeneficiaryDetail(BaseModel):
    id: UUID
    full_name: str
    cnic: Optional[str] = None
    phone: Optional[str] = None
    household_size: Optional[int] = None
    dependents: Optional[int] = None
    school_age_children: Optional[int] = None
    marital_status: Optional[str] = None
    monthly_income: Optional[float] = None
    employment_status: Optional[str] = None
    owns_home: Optional[bool] = None
    district: str
    city: Optional[str] = None
    cluster_id: Optional[str] = None
    education_level: Optional[str] = None
    has_disability: Optional[bool] = None
    chronic_illness_flag: Optional[bool] = None
    date_of_birth: Optional[date] = None
    is_orphan: Optional[bool] = None
    prior_assistance_count: Optional[int] = None
    domain_attributes: Optional[dict[str, Any]] = None
    staff_notes: Optional[str] = None
    completeness_score: Optional[float] = None
    created_by_staff_id: Optional[UUID] = None
    consent_given: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None