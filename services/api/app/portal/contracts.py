from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from eligibility.models import ProgramRule
from eligibility.discovery import DiscoveryDomain
from eligibility.prioritization import validate_weights


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


class Login(Contract):
    email: str = Field(min_length=3, max_length=250)
    password: str = Field(min_length=1, max_length=500)


class Refresh(Contract):
    refresh_token: str = Field(min_length=1)


class ProfileInput(Contract):
    full_name: str = Field(min_length=2, max_length=200)
    district: str = Field(min_length=2, max_length=100)
    cnic: str | None = None
    phone: str | None = Field(default=None, max_length=30)
    city: str | None = Field(default=None, max_length=100)
    cluster_id: str | None = Field(default=None, max_length=100)
    household_size: int | None = Field(default=None, ge=1, le=100)
    dependents: int | None = Field(default=None, ge=0, le=100)
    school_age_children: int | None = Field(default=None, ge=0, le=100)
    monthly_income: float | None = Field(default=None, ge=0)
    marital_status: Literal['single', 'married', 'widowed', 'divorced'] | None = None
    employment_status: Literal['unemployed', 'daily_wage', 'self_employed', 'salaried'] | None = None
    owns_home: bool | None = None
    education_level: Literal['none', 'primary', 'matric', 'intermediate', 'graduate'] | None = None
    has_disability: bool | None = None
    chronic_illness_flag: bool | None = None
    date_of_birth: date | None = None
    is_orphan: bool | None = None
    prior_assistance_count: int | None = Field(default=None, ge=0, le=1000)
    domain_attributes: dict = Field(default_factory=dict)
    staff_notes: str | None = Field(default=None, max_length=5000)
    consent_given: bool

    @field_validator('cnic')
    @classmethod
    def clean_cnic(cls, value):
        if not value:
            return None
        digits = value.replace('-', '').replace(' ', '')
        if len(digits) != 13 or not digits.isascii() or not digits.isdigit():
            raise ValueError('CNIC must contain 13 digits.')
        return digits

    @field_validator('date_of_birth')
    @classmethod
    def past_date(cls, value):
        if value and value > date.today():
            raise ValueError('Date of birth cannot be in the future.')
        return value

    @model_validator(mode='after')
    def validate_profile(self):
        if not self.consent_given:
            raise ValueError('Record consent before saving the beneficiary profile.')
        if self.household_size is not None:
            if any(n is not None and n > self.household_size for n in [self.dependents, self.school_age_children]):
                raise ValueError('Dependents and children cannot exceed household size.')
        return self


class ProgramInput(Contract):
    name: str = Field(min_length=2, max_length=200)
    department_id: UUID
    domain: DiscoveryDomain
    description: str = Field(default='', max_length=5000)
    hard_rules: list[ProgramRule] = Field(min_length=1, max_length=50)
    priority_weights: dict[str, float]
    requires_explicit_application: bool = False
    budget_per_cycle: float | None = Field(default=None, ge=0)
    capacity_per_cycle: int | None = Field(default=None, ge=0)
    cycle_frequency_days: int = Field(default=14, ge=1, le=365)
    verification_valid_days: int = Field(default=90, ge=1, le=365)
    active: bool = True

    @field_validator('priority_weights')
    @classmethod
    def weights(cls, value):
        return validate_weights(value)

    @model_validator(mode='after')
    def policy(self):
        if self.domain == 'islamic_microfinance' and not self.requires_explicit_application:
            raise ValueError('Microfinance must require an explicit application.')
        if len({r.rule_id for r in self.hard_rules}) != len(self.hard_rules):
            raise ValueError('Rule IDs must be unique.')
        return self


class Review(Contract):
    action: Literal['pooled', 'dismissed']
    notes: str = Field(default='', max_length=3000)


class ApplicationInput(Contract):
    beneficiary_id: UUID
    program_id: UUID
    amount_requested: float | None = Field(default=None, gt=0)


class VerificationInput(Contract):
    beneficiary_id: UUID
    program_id: UUID
    outcome: Literal['verified', 'no_actual_need', 'assisted_elsewhere', 'not_eligible', 'unreachable', 'declined']
    need_confirmed: bool
    assistance_elsewhere: bool
    urgency_level: Literal['low', 'medium', 'high', 'critical'] = 'medium'
    verified_income: float | None = Field(default=None, ge=0)
    verified_household_size: int | None = Field(default=None, ge=1, le=100)
    notes: str = Field(min_length=3, max_length=5000)
    amount_requested: float | None = Field(default=None, gt=0)

    @model_validator(mode='after')
    def valid_outcome(self):
        if self.outcome == 'verified' and (not self.need_confirmed or self.assistance_elsewhere or self.verified_income is None or self.verified_household_size is None):
            raise ValueError('A verified outcome requires confirmed need, no duplicate assistance, and verified income/household size.')
        return self


class Approval(Contract):
    approved: bool
    amount: float | None = Field(default=None, gt=0)


class DocumentInput(Contract):
    text: str = Field(min_length=30, max_length=60000)


class AssistantInput(Contract):
    question: str = Field(min_length=3, max_length=2000)
    program_id: UUID | None = None
