"""Database adapters for the pure eligibility discovery engine."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from eligibility.discovery import DiscoveryProgram, DiscoveryResult, discover_profile
from eligibility.models import BeneficiaryProfile
from eligibility.persistence import SavedScorer


ACTIONABLE_MATCH_STATUSES = {"pending_review", "suppressed"}


def _mapping_from_row(row: Any) -> Mapping[str, Any]:
    """Return a SQLAlchemy row mapping while keeping this service testable."""

    return row._mapping if hasattr(row, "_mapping") else row


def beneficiary_profile_from_row(row: Any) -> BeneficiaryProfile:
    """Adapt a beneficiary_profiles row without passing unrelated SQL columns through."""

    values = _mapping_from_row(row)
    profile_values = {
        field_name: values[field_name]
        for field_name in BeneficiaryProfile.model_fields
        if field_name in values
    }
    return BeneficiaryProfile.model_validate(profile_values)


def discovery_program_from_row(row: Any) -> DiscoveryProgram:
    """Adapt one active programs row and require confirmed structured hard rules."""

    values = _mapping_from_row(row)
    criteria = values.get("criteria_structured")
    if isinstance(criteria, str):
        try:
            criteria = json.loads(criteria)
        except json.JSONDecodeError as error:
            raise ValueError("program criteria_structured must be valid JSON") from error
    if not isinstance(criteria, Mapping):
        raise ValueError("program criteria_structured must be an object")

    hard_rules = criteria.get("hard_rules")
    if not isinstance(hard_rules, list) or not hard_rules:
        raise ValueError("active programs require a non-empty criteria_structured.hard_rules list")

    return DiscoveryProgram(
        program_id=str(values["id"]),
        name=values["name"],
        domain=values["domain"],
        rules=hard_rules,
        requires_explicit_application=values["requires_explicit_application"],
    )


def _delete_obsolete_unreviewed_matches(
    db: Session,
    beneficiary_id: UUID,
    scanned_program_ids: Sequence[UUID],
    actionable_program_ids: Sequence[UUID],
) -> None:
    """Remove stale suggestions while preserving staff-reviewed outcomes."""

    if not scanned_program_ids:
        return

    query = """
        delete from match_records
        where beneficiary_id = :beneficiary_id
          and status in ('pending_review', 'suppressed')
          and program_id in :scanned_program_ids
    """
    parameters: dict[str, Any] = {
        "beneficiary_id": beneficiary_id,
        "scanned_program_ids": list(scanned_program_ids),
    }
    if actionable_program_ids:
        query += " and program_id not in :actionable_program_ids"
        parameters["actionable_program_ids"] = list(actionable_program_ids)

    statement = text(query).bindparams(
        bindparam("scanned_program_ids", expanding=True),
        *(
            [bindparam("actionable_program_ids", expanding=True)]
            if actionable_program_ids
            else []
        ),
    )
    db.execute(statement, parameters)


def _refresh_profile_for_programs(
    db: Session,
    profile_row: Any,
    programs: Sequence[DiscoveryProgram],
    scorer: SavedScorer,
) -> list[DiscoveryResult]:
    """Discover matches for one profile against a supplied programme scope."""

    profile = beneficiary_profile_from_row(profile_row)
    results = discover_profile(profile, programs, scorer)
    actionable_results = [result for result in results if result.status in ACTIONABLE_MATCH_STATUSES]

    for result in actionable_results:
        db.execute(
            text("""
                insert into match_records (beneficiary_id, program_id, score, reason, status)
                values (:beneficiary_id, :program_id, :score, :reason, :status)
                on conflict (beneficiary_id, program_id) do update
                set score = excluded.score,
                    reason = excluded.reason,
                    status = excluded.status
                where match_records.status in ('pending_review', 'suppressed')
            """),
            {
                "beneficiary_id": profile.id,
                "program_id": UUID(result.program_id),
                "score": result.score,
                "reason": result.reason,
                "status": result.status,
            },
        )

    _delete_obsolete_unreviewed_matches(
        db,
        profile.id,
        [UUID(program.program_id) for program in programs],
        [UUID(result.program_id) for result in actionable_results],
    )
    return results


def refresh_beneficiary_matches(
    db: Session,
    beneficiary_id: UUID,
    scorer: SavedScorer,
) -> list[DiscoveryResult]:
    """Run discovery for one profile and persist only actionable current suggestions."""

    profile_row = db.execute(
        text("select * from beneficiary_profiles where id = :beneficiary_id"),
        {"beneficiary_id": beneficiary_id},
    ).fetchone()
    if profile_row is None:
        raise LookupError("beneficiary not found")

    program_rows = db.execute(
        text("""
            select id, name, domain, criteria_structured, requires_explicit_application
            from programs
            where active = true
            order by id
        """)
    ).fetchall()

    programs = [discovery_program_from_row(row) for row in program_rows]
    results = _refresh_profile_for_programs(db, profile_row, programs, scorer)
    db.commit()
    return results


def refresh_program_matches(
    db: Session,
    program_id: UUID,
    scorer: SavedScorer,
) -> dict[UUID, list[DiscoveryResult]]:
    """Rescan every profile against one newly added or edited active programme."""

    program_row = db.execute(
        text("""
            select id, name, domain, criteria_structured, requires_explicit_application
            from programs
            where id = :program_id and active = true
        """),
        {"program_id": program_id},
    ).fetchone()
    if program_row is None:
        raise LookupError("active program not found")

    program = discovery_program_from_row(program_row)
    profile_rows = db.execute(text("select * from beneficiary_profiles order by id")).fetchall()
    results_by_beneficiary: dict[UUID, list[DiscoveryResult]] = {}
    for profile_row in profile_rows:
        profile = beneficiary_profile_from_row(profile_row)
        results_by_beneficiary[profile.id] = _refresh_profile_for_programs(
            db,
            profile_row,
            [program],
            scorer,
        )
    db.commit()
    return results_by_beneficiary


def get_persisted_matches(db: Session, beneficiary_id: UUID) -> list[Mapping[str, Any]]:
    """Read persisted matches without recalculating discovery during a GET request."""

    rows = db.execute(
        text("""
            select mr.program_id, p.name as program_name, mr.score, mr.reason, mr.status
            from match_records mr
            join programs p on p.id = mr.program_id
            where mr.beneficiary_id = :beneficiary_id
            order by mr.created_at desc, mr.program_id
        """),
        {"beneficiary_id": beneficiary_id},
    ).fetchall()
    return [dict(_mapping_from_row(row)) for row in rows]
