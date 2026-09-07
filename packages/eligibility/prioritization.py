"""Deterministic, transparent prioritisation for verified programme candidates."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator


SUPPORTED_FACTORS = (
    "income_inverse",
    "household_size",
    "urgency",
    "dependents",
    "disability",
    "chronic_illness",
    "no_prior_assistance",
    "school_age_children",
    "cycles_waited",
)
WEIGHT_TOTAL_TOLERANCE = 0.000001
URGENCY_SCORES = {"low": 0.25, "medium": 0.50, "high": 0.75, "critical": 1.00}


class VerifiedCandidate(BaseModel):
    """Verified facts used by the per-programme need-ranking rubric."""

    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_id: UUID
    cycles_waited: StrictInt = Field(ge=0)
    verified_income: Decimal | None = None
    verified_household_size: StrictInt | None = None
    urgency_level: Literal["low", "medium", "high", "critical"] | None = None
    dependents: StrictInt | None = None
    has_disability: StrictBool | None = None
    chronic_illness_flag: StrictBool | None = None
    prior_assistance_count: StrictInt | None = None
    school_age_children: StrictInt | None = None

    @field_validator("verified_income")
    @classmethod
    def validate_income(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value < 0):
            raise ValueError("verified_income must be a finite non-negative value")
        return value

    @field_validator(
        "verified_household_size",
        "dependents",
        "prior_assistance_count",
        "school_age_children",
    )
    @classmethod
    def validate_optional_counts(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("count fields must be non-negative")
        return value


class RankedCandidate(BaseModel):
    """A candidate's explainable score and deterministic position in a cycle."""

    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_id: UUID
    overall_priority_score: Decimal
    score_breakdown: dict[str, Decimal]
    rank: StrictInt = Field(gt=0)


def _validated_normalized_weights(priority_weights: Mapping[str, object]) -> dict[str, float]:
    if not priority_weights:
        raise ValueError("priority_weights must not be empty")

    converted: dict[str, float] = {}
    for factor, raw_weight in priority_weights.items():
        if factor == "entry_path":
            raise ValueError("entry_path must never be used as a prioritisation factor")
        if factor not in SUPPORTED_FACTORS:
            raise ValueError(f"unsupported prioritisation factor: {factor}")
        if isinstance(raw_weight, bool) or not isinstance(raw_weight, (int, float, Decimal)):
            raise ValueError(f"weight for '{factor}' must be numeric")

        weight = float(raw_weight)
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"weight for '{factor}' must be finite and non-negative")
        converted[factor] = weight

    total = sum(converted.values())
    if not math.isfinite(total) or abs(total - 1.0) > WEIGHT_TOTAL_TOLERANCE:
        raise ValueError("priority weights must total 1.0")

    return {factor: converted[factor] / total for factor in SUPPORTED_FACTORS if factor in converted}


def _capped_ratio(value: int | Decimal, cap: float) -> float:
    return min(float(value) / cap, 1.0)


def _factor_score(candidate: VerifiedCandidate, factor: str) -> float:
    if factor == "income_inverse":
        if candidate.verified_income is None:
            return 0.5
        return 1.0 - _capped_ratio(candidate.verified_income, 100_000.0)
    if factor == "household_size":
        return 0.0 if candidate.verified_household_size is None else _capped_ratio(candidate.verified_household_size, 10.0)
    if factor == "urgency":
        return 0.0 if candidate.urgency_level is None else URGENCY_SCORES[candidate.urgency_level]
    if factor == "dependents":
        return 0.0 if candidate.dependents is None else _capped_ratio(candidate.dependents, 10.0)
    if factor == "disability":
        return 1.0 if candidate.has_disability else 0.0
    if factor == "chronic_illness":
        return 1.0 if candidate.chronic_illness_flag else 0.0
    if factor == "no_prior_assistance":
        if candidate.prior_assistance_count is None:
            return 0.5
        return 1.0 - _capped_ratio(candidate.prior_assistance_count, 5.0)
    if factor == "school_age_children":
        return 0.0 if candidate.school_age_children is None else _capped_ratio(candidate.school_age_children, 5.0)
    if factor == "cycles_waited":
        return _capped_ratio(candidate.cycles_waited, 6.0)
    raise ValueError(f"unsupported prioritisation factor: {factor}")


def rank_candidates(
    candidates: Sequence[VerifiedCandidate],
    priority_weights: Mapping[str, object],
) -> list[RankedCandidate]:
    """Rank verified candidates using validated programme-specific priority weights."""

    normalized_weights = _validated_normalized_weights(priority_weights)
    scored: list[tuple[VerifiedCandidate, float, dict[str, float]]] = []

    for candidate in candidates:
        breakdown = {
            factor: _factor_score(candidate, factor) * weight
            for factor, weight in normalized_weights.items()
        }
        overall_score = sum(breakdown.values())
        scored.append((candidate, overall_score, breakdown))

    scored.sort(key=lambda item: (-item[1], -item[0].cycles_waited, str(item[0].candidate_id)))

    results: list[RankedCandidate] = []
    for rank, (candidate, overall_score, breakdown) in enumerate(scored, start=1):
        results.append(
            RankedCandidate(
                candidate_id=candidate.candidate_id,
                overall_priority_score=Decimal(str(overall_score)),
                score_breakdown={factor: Decimal(str(value)) for factor, value in breakdown.items()},
                rank=rank,
            )
        )
    return results
