"""Callable eligibility trigger handlers; scheduling and HTTP events remain external."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from eligibility.persistence import SavedScorer
from eligibility.prioritization import VerifiedCandidate
from eligibility.ranking_cycle import CycleCandidate, RankingCycleConfig, RankingCycleResult, run_ranking_cycle

from app.services.eligibility_matching import refresh_beneficiary_matches, refresh_program_matches


def on_profile_created_or_updated(
    db: Session,
    beneficiary_id: UUID,
    scorer: SavedScorer,
):
    """Trigger 1: refresh a profile's suggestions against every active programme."""

    return refresh_beneficiary_matches(db, beneficiary_id, scorer)


def on_program_added_or_criteria_changed(
    db: Session,
    program_id: UUID,
    scorer: SavedScorer,
):
    """Triggers 5 and 6: refresh every profile against the one changed programme."""

    return refresh_program_matches(db, program_id, scorer)


def _json_object(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("program_specific_data must be a JSON object")
    return value


def _cycle_candidate_from_row(row: Any) -> CycleCandidate:
    values = row._mapping if hasattr(row, "_mapping") else row
    supplemental = _json_object(values["program_specific_data"])
    return CycleCandidate(
        candidate=VerifiedCandidate(
            candidate_id=values["candidate_id"],
            cycles_waited=values["cycles_waited"],
            verified_income=values["verified_income"],
            verified_household_size=values["verified_household_size"],
            urgency_level=values["urgency_level"],
            dependents=supplemental.get("dependents"),
            has_disability=supplemental.get("has_disability"),
            chronic_illness_flag=supplemental.get("chronic_illness_flag"),
            prior_assistance_count=supplemental.get("prior_assistance_count"),
            school_age_children=supplemental.get("school_age_children"),
        ),
        status=values["status"],
        valid_until=values["valid_until"],
    )


def run_biweekly_ranking_cycle(
    db: Session,
    program_id: UUID,
    run_date: date,
) -> RankingCycleResult:
    """Trigger 8: expire stale applications, persist ranks, and record one cycle audit row."""

    program_row = db.execute(
        text("""
            select id, priority_weights, budget_per_cycle, capacity_per_cycle
            from programs
            where id = :program_id and active = true
        """),
        {"program_id": program_id},
    ).fetchone()
    if program_row is None:
        raise LookupError("active program not found")
    program = program_row._mapping if hasattr(program_row, "_mapping") else program_row
    priority_weights = _json_object(program["priority_weights"])

    candidate_rows = db.execute(
        text("""
            select a.id as candidate_id, a.status, a.cycles_waited,
                   v.valid_until, v.verified_income, v.verified_household_size,
                   v.urgency_level, v.program_specific_data
            from applications a
            left join verifications v on v.id = a.verification_id
            where a.program_id = :program_id
            order by a.id
        """),
        {"program_id": program_id},
    ).fetchall()

    result = run_ranking_cycle(
        [_cycle_candidate_from_row(row) for row in candidate_rows],
        RankingCycleConfig(
            program_id=program["id"],
            run_date=run_date,
            priority_weights=priority_weights,
            budget_per_cycle=program["budget_per_cycle"],
            capacity_per_cycle=program["capacity_per_cycle"],
        ),
    )

    if result.expired_candidate_ids:
        db.execute(
            text("""
                update applications
                set status = 'expired', updated_at = now()
                where id in :application_ids
                  and status in ('active', 'rolled_over')
            """).bindparams(bindparam("application_ids", expanding=True)),
            {"application_ids": result.expired_candidate_ids},
        )

    for ranked in result.ranked_candidates:
        db.execute(
            text("""
                update applications
                set need_score = :need_score,
                    score_breakdown = cast(:score_breakdown as jsonb),
                    rank_in_cycle = :rank_in_cycle,
                    status = 'ranked',
                    updated_at = now()
                where id = :application_id
                  and status in ('active', 'rolled_over')
            """),
            {
                "application_id": ranked.candidate_id,
                "need_score": ranked.overall_priority_score,
                "score_breakdown": json.dumps({key: float(value) for key, value in ranked.score_breakdown.items()}),
                "rank_in_cycle": ranked.rank,
            },
        )

    db.execute(
        text("""
            insert into ranking_cycles (
                program_id, run_at, pool_size, budget_available,
                capacity_available, weights_snapshot
            ) values (
                :program_id, :run_at, :pool_size, :budget_available,
                :capacity_available, cast(:weights_snapshot as jsonb)
            )
        """),
        {
            "program_id": result.program_id,
            "run_at": result.run_date,
            "pool_size": result.pool_size,
            "budget_available": result.budget_available,
            "capacity_available": result.capacity_available,
            "weights_snapshot": json.dumps(result.weights_snapshot, default=str),
        },
    )
    db.commit()
    return result
