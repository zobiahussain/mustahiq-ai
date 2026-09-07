"""Programme management endpoints that fire eligibility triggers 5, 6, and 8.

Trigger 5 (new programme added) and trigger 6 (criteria edited) re-scan every
existing beneficiary against exactly the one programme that changed. Trigger 8
(bi-weekly ranking due) is exposed as a manual/schedulable endpoint: the
scheduler itself stays external, per the workflow-layer contract.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.db import get_db
from app.core.scorer import get_eligibility_scorer
from app.schemas.program import (
    ProgramCreate,
    ProgramUpdate,
    ProgramWithRescanResponse,
    RankingCycleCandidateOut,
    RankingCycleRequest,
    RankingCycleRunResponse,
    RescanSummary,
)
from app.services.eligibility_workflows import (
    on_program_added_or_criteria_changed,
    run_biweekly_ranking_cycle,
)
from eligibility.persistence import SavedScorer


router = APIRouter(prefix="/programs", tags=["programs"])

# Fields whose changes alter matching outcomes and therefore require a rescan.
MATCHING_RELEVANT_FIELDS = {"criteria_structured", "requires_explicit_application", "domain"}

UPDATABLE_FIELDS = (
    "name",
    "domain",
    "description",
    "criteria_structured",
    "priority_weights",
    "requires_explicit_application",
    "budget_per_cycle",
    "capacity_per_cycle",
    "active",
)

PROGRAM_RETURNING_COLUMNS = """
    returning id, name, domain, department_id, description,
              requires_explicit_application, active, budget_per_cycle,
              capacity_per_cycle, priority_weights, created_at, updated_at
"""

JSONB_FIELDS = {"criteria_structured", "priority_weights"}


def _parse_uuid(value: str, label: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"{label} must be a UUID") from error


def _mapping_from_row(row: Any) -> dict[str, Any]:
    """Return a SQLAlchemy row mapping while keeping endpoint tests simple."""

    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _rescan_and_summarize(db: Session, program_id: UUID, scorer: SavedScorer) -> RescanSummary:
    """Trigger 5/6 engine action: rescan every profile against one programme."""

    try:
        results_by_beneficiary = on_program_added_or_criteria_changed(db, program_id, scorer)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"eligibility configuration error: {error}") from error

    actionable = sum(
        1
        for results in results_by_beneficiary.values()
        for result in results
        if result.status in ("pending_review", "suppressed")
    )
    return RescanSummary(profiles_scanned=len(results_by_beneficiary), actionable_matches=actionable)


@router.post("/", response_model=ProgramWithRescanResponse, status_code=201)
def create_program(
    payload: ProgramCreate,
    db: Session = Depends(get_db),
    staff: dict = Depends(require_role("department_admin", "super_admin")),
    scorer: SavedScorer = Depends(get_eligibility_scorer),
):
    row = db.execute(
        text(f"""
            insert into programs
                (name, domain, department_id, description, criteria_structured,
                 priority_weights, requires_explicit_application, budget_per_cycle,
                 capacity_per_cycle)
            values
                (:name, :domain, :department_id, :description,
                 cast(:criteria_structured as jsonb), cast(:priority_weights as jsonb),
                 :requires_explicit_application, :budget_per_cycle, :capacity_per_cycle)
            {PROGRAM_RETURNING_COLUMNS}
        """),
        {
            "name": payload.name,
            "domain": payload.domain,
            "department_id": payload.department_id,
            "description": payload.description,
            "criteria_structured": json.dumps(payload.criteria_structured),
            "priority_weights": json.dumps(payload.priority_weights or {}),
            "requires_explicit_application": payload.requires_explicit_application,
            "budget_per_cycle": payload.budget_per_cycle,
            "capacity_per_cycle": payload.capacity_per_cycle,
        },
    ).fetchone()
    db.commit()

    # Trigger 5: a newly added programme is scored against every existing profile.
    program = _mapping_from_row(row)
    rescan = _rescan_and_summarize(db, program["id"], scorer)
    return {**program, "rescan": rescan}


@router.patch("/{program_id}", response_model=ProgramWithRescanResponse)
def update_program(
    program_id: str,
    payload: ProgramUpdate,
    db: Session = Depends(get_db),
    staff: dict = Depends(require_role("department_admin", "super_admin")),
    scorer: SavedScorer = Depends(get_eligibility_scorer),
):
    parsed_program_id = _parse_uuid(program_id, "program_id")
    updates = payload.model_dump(exclude_unset=True)

    set_clauses: list[str] = []
    parameters: dict[str, Any] = {"program_id": parsed_program_id}
    for field in UPDATABLE_FIELDS:
        if field not in updates:
            continue
        value = updates[field]
        if field in JSONB_FIELDS:
            set_clauses.append(f"{field} = cast(:{field} as jsonb)")
            parameters[field] = json.dumps(value)
        else:
            set_clauses.append(f"{field} = :{field}")
            parameters[field] = value
    set_clauses.append("updated_at = now()")

    row = db.execute(
        text(f"""
            update programs
            set {', '.join(set_clauses)}
            where id = :program_id
            {PROGRAM_RETURNING_COLUMNS}
        """),
        parameters,
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Program not found")
    db.commit()

    # Trigger 6: matching-relevant edits re-scan every profile against this
    # programme -- but only while it remains active (rescan requires an
    # active programme; deactivating leaves existing matches for staff review).
    program = _mapping_from_row(row)
    rescan = None
    if MATCHING_RELEVANT_FIELDS & updates.keys() and program["active"]:
        rescan = _rescan_and_summarize(db, parsed_program_id, scorer)
    return {**program, "rescan": rescan}


@router.post("/{program_id}/ranking-cycle", response_model=RankingCycleRunResponse)
def run_program_ranking_cycle(
    program_id: str,
    payload: RankingCycleRequest | None = None,
    db: Session = Depends(get_db),
    staff: dict = Depends(require_role("department_admin", "super_admin")),
):
    parsed_program_id = _parse_uuid(program_id, "program_id")
    run_date = (payload.run_date if payload is not None else None) or date.today()

    try:
        result = run_biweekly_ranking_cycle(db, parsed_program_id, run_date)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=500, detail=f"eligibility configuration error: {error}") from error

    return RankingCycleRunResponse(
        program_id=result.program_id,
        run_date=result.run_date,
        pool_size=result.pool_size,
        expired_application_ids=result.expired_candidate_ids,
        ranked_candidates=[
            RankingCycleCandidateOut(
                candidate_id=ranked.candidate_id,
                rank=ranked.rank,
                need_score=ranked.overall_priority_score,
                score_breakdown=ranked.score_breakdown,
            )
            for ranked in result.ranked_candidates
        ],
        weights_snapshot=result.weights_snapshot,
    )
