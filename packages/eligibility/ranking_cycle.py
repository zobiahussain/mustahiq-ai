"""Pure orchestration for one programme's verified-candidate ranking cycle."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from eligibility.prioritization import RankedCandidate, VerifiedCandidate, rank_candidates


ApplicationStatus = Literal[
    "active",
    "ranked",
    "approved",
    "disbursed",
    "rolled_over",
    "expired",
    "withdrawn",
]
RANKABLE_STATUSES = {"active", "rolled_over"}


class CycleCandidate(BaseModel):
    """An application, its verification freshness, and verified ranking facts."""

    model_config = ConfigDict(extra="forbid", strict=True)

    candidate: VerifiedCandidate
    status: ApplicationStatus
    valid_until: date | None


class RankingCycleConfig(BaseModel):
    """Caller-supplied programme configuration for one deterministic run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    program_id: UUID
    run_date: date
    priority_weights: dict[str, object]
    budget_per_cycle: Decimal | None = Field(default=None, ge=0)
    capacity_per_cycle: StrictInt | None = Field(default=None, ge=0)


class RankingCycleResult(BaseModel):
    """The data a backend later persists for a completed ranking calculation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    program_id: UUID
    run_date: date
    ranked_candidates: list[RankedCandidate]
    expired_candidate_ids: list[UUID]
    pool_size: StrictInt = Field(ge=0)
    weights_snapshot: dict[str, object]
    budget_available: Decimal | None = Field(default=None, ge=0)
    capacity_available: StrictInt | None = Field(default=None, ge=0)


def run_ranking_cycle(
    candidates: Sequence[CycleCandidate],
    config: RankingCycleConfig,
) -> RankingCycleResult:
    """Filter stale applications and rank only currently verified active candidates."""

    eligible_candidates: list[VerifiedCandidate] = []
    expired_candidate_ids: list[UUID] = []

    for cycle_candidate in candidates:
        if cycle_candidate.status not in RANKABLE_STATUSES:
            continue
        if cycle_candidate.valid_until is None:
            continue
        if cycle_candidate.valid_until < config.run_date:
            expired_candidate_ids.append(cycle_candidate.candidate.candidate_id)
            continue
        eligible_candidates.append(cycle_candidate.candidate)

    weights_snapshot = dict(config.priority_weights)
    ranked_candidates = rank_candidates(eligible_candidates, config.priority_weights)

    return RankingCycleResult(
        program_id=config.program_id,
        run_date=config.run_date,
        ranked_candidates=ranked_candidates,
        expired_candidate_ids=expired_candidate_ids,
        pool_size=len(ranked_candidates),
        weights_snapshot=weights_snapshot,
        budget_available=config.budget_per_cycle,
        capacity_available=config.capacity_per_cycle,
    )
