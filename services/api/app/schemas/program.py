"""Request/response models for programme management triggers 5, 6, and 8."""

from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

REPO_ROOT = Path(__file__).resolve().parents[4]
PACKAGES_DIR = REPO_ROOT / "packages"
if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from eligibility.models import ProgramRule
from eligibility.prioritization import rank_candidates


ProgramDomain = Literal[
    "disaster_management",
    "health_services",
    "education",
    "wash",
    "orphan_care",
    "bano_qabil",
    "islamic_microfinance",
]


def _validate_criteria_structured(value: dict[str, Any]) -> dict[str, Any]:
    """Reject criteria that the pure engine could never evaluate.

    Mirrors the schema note on programs.criteria_structured: rules are
    validated against packages/eligibility's ProgramRule model before
    storage so a bad payload fails at the API boundary, not mid-rescan.
    """

    if not isinstance(value, dict):
        raise ValueError("criteria_structured must be a JSON object")
    hard_rules = value.get("hard_rules")
    if not isinstance(hard_rules, list) or not hard_rules:
        raise ValueError("criteria_structured.hard_rules must be a non-empty list")
    for rule in hard_rules:
        ProgramRule.model_validate(rule)
    return value


def _validate_priority_weights(value: Optional[dict[str, float]]) -> Optional[dict[str, float]]:
    """Reject weight sets the rubric would refuse, including entry_path.

    rank_candidates([], weights) performs the full weight validation
    (supported factors only, no entry_path, finite non-negative values
    totalling 1.0) and returns [] for a valid set.
    """

    if value is None:
        return value
    rank_candidates([], value)
    return value


class ProgramCreate(BaseModel):
    name: str
    domain: ProgramDomain
    department_id: Optional[UUID] = None
    description: Optional[str] = None
    criteria_structured: dict[str, Any]
    priority_weights: Optional[dict[str, float]] = None
    requires_explicit_application: bool = False
    budget_per_cycle: Optional[Decimal] = None
    capacity_per_cycle: Optional[int] = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value

    @field_validator("criteria_structured")
    @classmethod
    def check_criteria(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_criteria_structured(value)

    @field_validator("priority_weights")
    @classmethod
    def check_weights(cls, value: Optional[dict[str, float]]) -> Optional[dict[str, float]]:
        return _validate_priority_weights(value)


class ProgramUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[ProgramDomain] = None
    description: Optional[str] = None
    criteria_structured: Optional[dict[str, Any]] = None
    priority_weights: Optional[dict[str, float]] = None
    requires_explicit_application: Optional[bool] = None
    budget_per_cycle: Optional[Decimal] = None
    capacity_per_cycle: Optional[int] = None
    active: Optional[bool] = None

    @model_validator(mode="after")
    def at_least_one_field_set(self) -> "ProgramUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("name must not be blank")
        return value

    @field_validator("criteria_structured")
    @classmethod
    def check_criteria(cls, value: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if value is None:
            raise ValueError("criteria_structured must not be null; omit the field to leave it unchanged")
        return _validate_criteria_structured(value)

    @field_validator("priority_weights")
    @classmethod
    def check_weights(cls, value: Optional[dict[str, float]]) -> Optional[dict[str, float]]:
        if value is None:
            raise ValueError("priority_weights must not be null; omit the field to leave it unchanged")
        return _validate_priority_weights(value)


class ProgramResponse(BaseModel):
    id: UUID
    name: str
    domain: str
    department_id: Optional[UUID] = None
    description: Optional[str] = None
    requires_explicit_application: bool
    active: bool
    budget_per_cycle: Optional[Decimal] = None
    capacity_per_cycle: Optional[int] = None
    priority_weights: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RescanSummary(BaseModel):
    profiles_scanned: int
    actionable_matches: int


class ProgramWithRescanResponse(ProgramResponse):
    rescan: Optional[RescanSummary] = None


class RankingCycleRequest(BaseModel):
    run_date: Optional[date] = None


class RankingCycleCandidateOut(BaseModel):
    candidate_id: UUID
    rank: int
    need_score: Decimal
    score_breakdown: dict[str, Decimal]


class RankingCycleRunResponse(BaseModel):
    program_id: UUID
    run_date: date
    pool_size: int
    expired_application_ids: list[UUID]
    ranked_candidates: list[RankingCycleCandidateOut]
    weights_snapshot: dict[str, Any]
